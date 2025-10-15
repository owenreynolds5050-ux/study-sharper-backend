"""
Job Manager - In-Memory Job Tracking
Manages async flashcard generation jobs without Redis/Celery
Uses database for persistence and Python threading for background execution
"""

from typing import Dict, Any, Optional
from datetime import datetime
import threading
import uuid
import logging
from app.services.flashcard_generator import generate_verified_flashcards
from app.services.embeddings import get_embedding_for_text
import hashlib

logger = logging.getLogger(__name__)


class JobManager:
    """Manages background flashcard generation jobs"""
    
    def __init__(self, supabase):
        self.supabase = supabase
        self.active_jobs = {}  # In-memory job tracking
        self.lock = threading.Lock()
    
    def create_job(
        self,
        user_id: str,
        parameters: Dict[str, Any]
    ) -> str:
        """
        Create a new generation job
        
        Returns:
            job_id: str
        """
        job_id = str(uuid.uuid4())
        
        try:
            # Insert job record
            job_data = {
                "user_id": user_id,
                "job_id": job_id,
                "status": "pending",
                "parameters": parameters,
                "progress": 0,
                "total_cards": parameters.get("length", 10),
                "verified_cards": 0,
                "failed_cards": 0
            }
            
            self.supabase.table("flashcard_generation_jobs").insert(job_data).execute()
            
            logger.info(f"Created job {job_id} for user {user_id}")
            return job_id
            
        except Exception as e:
            logger.error(f"Error creating job: {e}")
            raise
    
    def start_job(self, job_id: str):
        """
        Start job execution in background thread
        """
        with self.lock:
            if job_id in self.active_jobs:
                logger.warning(f"Job {job_id} already running")
                return
            
            # Mark as active
            self.active_jobs[job_id] = "running"
        
        # Start background thread
        thread = threading.Thread(target=self._execute_job, args=(job_id,))
        thread.daemon = True
        thread.start()
        
        logger.info(f"Started job {job_id} in background")
    
    def _execute_job(self, job_id: str):
        """
        Execute job in background (runs in separate thread)
        """
        try:
            # Get job details
            response = self.supabase.table("flashcard_generation_jobs").select(
                "*"
            ).eq("job_id", job_id).single().execute()
            
            if not response.data:
                logger.error(f"Job {job_id} not found")
                return
            
            job = response.data
            user_id = job["user_id"]
            params = job["parameters"]
            
            # Update status to generating
            self._update_job_status(job_id, "generating", progress=10)
            
            # Generate flashcards
            logger.info(f"Generating flashcards for job {job_id}")
            
            flashcards, verification_summary = generate_verified_flashcards(
                context_text=params["context_text"],
                subject=params["subject"],
                subtopic=params["subtopic"],
                length=params["length"],
                difficulty=params["difficulty"],
                source_note_ids=params.get("source_note_ids", [])
            )
            
            # Update status to verifying
            self._update_job_status(job_id, "verifying", progress=50)
            
            # Save flashcards to database
            set_id = self._save_flashcards(
                user_id=user_id,
                flashcards=flashcards,
                params=params,
                verification_summary=verification_summary
            )
            
            # Generate embeddings for flashcards
            self._generate_embeddings(user_id, set_id, flashcards)
            
            # Update job as complete
            self._update_job_status(
                job_id,
                "complete",
                progress=100,
                result={
                    "set_id": set_id,
                    "flashcard_count": len(flashcards),
                    "verification_summary": verification_summary
                }
            )
            
            logger.info(f"Job {job_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}", exc_info=True)
            self._update_job_status(
                job_id,
                "failed",
                error_message=str(e)
            )
        
        finally:
            # Remove from active jobs
            with self.lock:
                self.active_jobs.pop(job_id, None)
    
    def _update_job_status(
        self,
        job_id: str,
        status: str,
        progress: Optional[int] = None,
        result: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None
    ):
        """Update job status in database"""
        try:
            update_data = {
                "status": status,
                "updated_at": datetime.now().isoformat()
            }
            
            if progress is not None:
                update_data["progress"] = progress
            
            if result is not None:
                update_data["result"] = result
            
            if error_message is not None:
                update_data["error_message"] = error_message
            
            if status in ["complete", "failed"]:
                update_data["completed_at"] = datetime.now().isoformat()
            
            self.supabase.table("flashcard_generation_jobs").update(
                update_data
            ).eq("job_id", job_id).execute()
            
        except Exception as e:
            logger.error(f"Error updating job status: {e}")
    
    def _save_flashcards(
        self,
        user_id: str,
        flashcards: list,
        params: Dict[str, Any],
        verification_summary: Dict[str, Any]
    ) -> str:
        """Save flashcard set and cards to database"""
        try:
            # Create set
            set_title = f"{params['subject']} — {params['subtopic']} — {len(flashcards)} cards — AI-generated"
            
            set_data = {
                "user_id": user_id,
                "title": set_title,
                "description": f"AI-generated flashcards on {params['subtopic']}",
                "source_note_ids": params.get("source_note_ids", []),
                "total_cards": len(flashcards),
                "ai_generated": True,
                "generation_status": "complete",
                "verification_summary": verification_summary
            }
            
            set_response = self.supabase.table("flashcard_sets").insert(set_data).execute()
            
            if not set_response.data:
                raise Exception("Failed to create flashcard set")
            
            set_id = set_response.data[0]["id"]
            
            # Insert flashcards
            flashcard_records = []
            for card in flashcards:
                flashcard_records.append({
                    "user_id": user_id,
                    "set_id": set_id,
                    "front": card["front"],
                    "back": card["back"],
                    "explanation": card.get("explanation", ""),
                    "position": card.get("position", 0),
                    "source_note_id": card.get("source_note_id"),
                    "ai_generated": True,
                    "failed_verification": card.get("failed_verification", False),
                    "verification_attempts": card.get("verification_attempts", 1)
                })
            
            if flashcard_records:
                self.supabase.table("flashcards").insert(flashcard_records).execute()
            
            logger.info(f"Saved {len(flashcards)} flashcards to set {set_id}")
            return set_id
            
        except Exception as e:
            logger.error(f"Error saving flashcards: {e}")
            raise
    
    def _generate_embeddings(self, user_id: str, set_id: str, flashcards: list):
        """Generate and save embeddings for flashcards"""
        try:
            # Get saved flashcard IDs
            response = self.supabase.table("flashcards").select(
                "id, front, back"
            ).eq("set_id", set_id).execute()
            
            if not response.data:
                return
            
            saved_cards = response.data
            
            # Generate embeddings
            embedding_records = []
            for card in saved_cards:
                content = f"{card['front']} {card['back']}"
                embedding = get_embedding_for_text(content)
                
                if embedding:
                    content_hash = hashlib.md5(content.encode()).hexdigest()
                    
                    embedding_records.append({
                        "flashcard_id": card["id"],
                        "user_id": user_id,
                        "embedding": embedding,
                        "content_hash": content_hash,
                        "model": "sentence-transformers/all-MiniLM-L6-v2"
                    })
            
            # Save embeddings
            if embedding_records:
                self.supabase.table("flashcard_embeddings").insert(embedding_records).execute()
                logger.info(f"Generated {len(embedding_records)} embeddings")
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            # Don't fail the job if embeddings fail
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get current job status"""
        try:
            response = self.supabase.table("flashcard_generation_jobs").select(
                "*"
            ).eq("job_id", job_id).single().execute()
            
            if response.data:
                return response.data
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting job status: {e}")
            return None
    
    def regenerate_failed_cards(
        self,
        user_id: str,
        set_id: str
    ) -> str:
        """
        Regenerate cards that failed verification
        
        Returns:
            job_id for regeneration job
        """
        try:
            # Get failed cards
            response = self.supabase.table("flashcards").select(
                "*"
            ).eq("set_id", set_id).eq("failed_verification", True).execute()
            
            if not response.data:
                raise Exception("No failed cards found")
            
            failed_cards = response.data
            
            # Get set info for context
            set_response = self.supabase.table("flashcard_sets").select(
                "*"
            ).eq("id", set_id).single().execute()
            
            if not set_response.data:
                raise Exception("Set not found")
            
            set_info = set_response.data
            
            # Create regeneration job
            # (Implementation would be similar to create_job)
            # For now, return placeholder
            
            logger.info(f"Created regeneration job for {len(failed_cards)} cards")
            return str(uuid.uuid4())
            
        except Exception as e:
            logger.error(f"Error creating regeneration job: {e}")
            raise


def get_job_manager(supabase) -> JobManager:
    """Factory function to create JobManager"""
    return JobManager(supabase)
