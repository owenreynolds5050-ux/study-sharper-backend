# app/services/job_queue.py
import asyncio
from typing import Dict, List, Optional, Tuple
from enum import Enum
import psutil
from datetime import datetime
from app.core.database import supabase

class JobType(str, Enum):
    TEXT_EXTRACTION = "text_extraction"
    OCR = "ocr"
    AUDIO_TRANSCRIPTION = "audio_transcription"
    EMBEDDING_GENERATION = "embedding"

class JobPriority(int, Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3

class JobQueue:
    """
    Job queue system to prevent server crashes from concurrent heavy operations.
    Limits OCR jobs to 2 concurrent to prevent memory issues.
    """
    def __init__(self):
        self.queues: Dict[JobType, asyncio.PriorityQueue] = {
            job_type: asyncio.PriorityQueue() for job_type in JobType
        }
        self.active_jobs: Dict[JobType, int] = {job_type: 0 for job_type in JobType}
        
        # CRITICAL: Limit concurrent jobs to prevent crashes
        self.max_concurrent_jobs = {
            JobType.TEXT_EXTRACTION: 5,
            JobType.OCR: 2,  # Keep at 2 to prevent memory crashes
            JobType.AUDIO_TRANSCRIPTION: 3,
            JobType.EMBEDDING_GENERATION: 10
        }
        
        self.memory_threshold = 0.80  # 80% RAM usage limit
        self.workers: Dict[JobType, List[asyncio.Task]] = {}
        self._running = False
        
    def check_memory(self) -> bool:
        """Check if system has enough memory to process jobs"""
        try:
            memory = psutil.virtual_memory()
            return memory.percent / 100 < self.memory_threshold
        except Exception:
            return True  # If check fails, allow processing
    
    async def add_job(
        self, 
        job_type: JobType, 
        job_data: dict, 
        priority: JobPriority = JobPriority.NORMAL
    ) -> str:
        """Add job to queue and create database record"""
        
        # Check memory before accepting job
        if not self.check_memory():
            raise MemoryError("System memory usage too high. Please try again later.")
        
        # Create job record in database
        job_record = supabase.table("processing_jobs").insert({
            "file_id": job_data["file_id"],
            "user_id": job_data["user_id"],
            "job_type": job_type.value,
            "status": "queued",
            "priority": priority.value
        }).execute()
        
        job_id = job_record.data[0]["id"]
        job_data["job_id"] = job_id
        
        # Add to queue (negative priority for max-heap behavior)
        await self.queues[job_type].put((-priority.value, datetime.now(), job_data))
        
        print(f"✓ Job {job_id} added to {job_type.value} queue")
        return job_id
    
    async def process_job(self, job_type: JobType):
        """Worker that processes jobs from queue"""
        
        while self._running:
            try:
                # Wait for job with timeout to allow graceful shutdown
                try:
                    priority, timestamp, job_data = await asyncio.wait_for(
                        self.queues[job_type].get(), 
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Wait if at concurrency limit or low memory
                while (self.active_jobs[job_type] >= self.max_concurrent_jobs[job_type] or
                       not self.check_memory()):
                    if not self._running:
                        # Re-queue the job if shutting down
                        await self.queues[job_type].put((priority, timestamp, job_data))
                        return
                    await asyncio.sleep(1)
                
                self.active_jobs[job_type] += 1
                
                # Update job status to processing
                supabase.table("processing_jobs").update({
                    "status": "processing",
                    "started_at": datetime.now().isoformat()
                }).eq("id", job_data["job_id"]).execute()
                
                # Process the job
                try:
                    from app.services.file_processor import process_file
                    await process_file(job_data, job_type)
                    
                    # Mark as completed
                    supabase.table("processing_jobs").update({
                        "status": "completed",
                        "completed_at": datetime.now().isoformat()
                    }).eq("id", job_data["job_id"]).execute()
                    
                    print(f"✓ Job {job_data['job_id']} completed")
                    
                except Exception as e:
                    print(f"✗ Job {job_data['job_id']} failed: {str(e)}")
                    
                    # Update attempts and mark as failed if max attempts reached
                    job_record = supabase.table("processing_jobs").select("attempts").eq("id", job_data["job_id"]).execute()
                    attempts = job_record.data[0]["attempts"] + 1
                    
                    if attempts >= 3:
                        supabase.table("processing_jobs").update({
                            "status": "failed",
                            "attempts": attempts,
                            "error_message": str(e),
                            "completed_at": datetime.now().isoformat()
                        }).eq("id", job_data["job_id"]).execute()
                    else:
                        # Retry by re-queueing
                        supabase.table("processing_jobs").update({
                            "status": "queued",
                            "attempts": attempts,
                            "error_message": str(e)
                        }).eq("id", job_data["job_id"]).execute()
                        
                        await self.queues[job_type].put((priority, datetime.now(), job_data))
                
                finally:
                    self.active_jobs[job_type] -= 1
                    self.queues[job_type].task_done()
                    
            except Exception as e:
                print(f"Worker error for {job_type.value}: {e}")
                if job_type in self.active_jobs and self.active_jobs[job_type] > 0:
                    self.active_jobs[job_type] -= 1
    
    def start_workers(self):
        """Start worker tasks for each job type"""
        if self._running:
            return
            
        self._running = True
        
        for job_type in JobType:
            num_workers = self.max_concurrent_jobs[job_type]
            self.workers[job_type] = [
                asyncio.create_task(self.process_job(job_type))
                for _ in range(num_workers)
            ]
        
        print(f"✓ Job queue workers started")
    
    async def stop_workers(self):
        """Stop all worker tasks gracefully"""
        self._running = False
        
        # Cancel all workers
        for workers in self.workers.values():
            for worker in workers:
                worker.cancel()
        
        # Wait for cancellation
        for workers in self.workers.values():
            await asyncio.gather(*workers, return_exceptions=True)
        
        print("✓ Job queue workers stopped")
    
    def get_queue_status(self) -> dict:
        """Get current queue status for monitoring"""
        return {
            job_type.value: {
                "queued": self.queues[job_type].qsize(),
                "active": self.active_jobs[job_type],
                "max_concurrent": self.max_concurrent_jobs[job_type]
            }
            for job_type in JobType
        }

# Global job queue instance
job_queue = JobQueue()
