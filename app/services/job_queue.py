# app/services/job_queue.py
import asyncio
from typing import Dict, List
from enum import Enum
import psutil
from datetime import datetime
from app.core.database import supabase
from app.core.websocket import ws_manager
import logging

logger = logging.getLogger(__name__)

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

        logger.info("✓ Job %s added to %s queue", job_id, job_type.value)
        return job_id
    
    async def process_job(self, job_type: JobType):
        """Worker that processes jobs from queue"""

        while self._running:
            try:
                try:
                    priority, timestamp, job_data = await asyncio.wait_for(
                        self.queues[job_type].get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    # Backfill from database when queue is empty
                    queued_job = supabase.table("processing_jobs").select("*") \
                        .eq("job_type", job_type.value) \
                        .eq("status", "queued") \
                        .order("priority", desc=True) \
                        .order("created_at") \
                        .limit(1) \
                        .execute()

                    if queued_job.data:
                        job = queued_job.data[0]
                        job_data = {
                            "job_id": job["id"],
                            "file_id": job["file_id"],
                            "user_id": job["user_id"],
                            "storage_path": job.get("storage_path"),
                            "file_type": job.get("file_type"),
                            "priority": job.get("priority", JobPriority.NORMAL.value)
                        }
                        await self.queues[job_type].put((-
                            job_data.get("priority", JobPriority.NORMAL.value),
                            datetime.now(),
                            job_data
                        ))
                    continue

                while (self.active_jobs[job_type] >= self.max_concurrent_jobs[job_type] or
                       not self.check_memory()):
                    if not self._running:
                        await self.queues[job_type].put((priority, timestamp, job_data))
                        return
                    await asyncio.sleep(1)

                self.active_jobs[job_type] += 1
                job_id = job_data["job_id"]

                supabase.table("processing_jobs").update({
                    "status": "processing",
                    "started_at": datetime.now().isoformat()
                }).eq("id", job_id).execute()

                await ws_manager.send_file_update(job_data["user_id"], job_data["file_id"], {
                    "status": "processing",
                    "job_id": job_id,
                    "job_type": job_type.value
                })

                try:
                    from app.services.file_processor import process_file
                    await process_file(job_data, job_type)

                    supabase.table("processing_jobs").update({
                        "status": "completed",
                        "completed_at": datetime.now().isoformat()
                    }).eq("id", job_id).execute()

                    await ws_manager.send_file_update(job_data["user_id"], job_data["file_id"], {
                        "status": "completed",
                        "job_id": job_id,
                        "job_type": job_type.value
                    })

                except Exception as e:
                    logger.exception("✗ Job %s failed", job_id)

                    job_record = supabase.table("processing_jobs").select("attempts").eq("id", job_id).execute()
                    attempts = job_record.data[0]["attempts"] + 1 if job_record.data else 1

                    supabase.table("processing_jobs").update({
                        "status": "failed",
                        "attempts": attempts,
                        "error_message": str(e),
                        "completed_at": datetime.now().isoformat()
                    }).eq("id", job_id).execute()

                    await ws_manager.send_file_update(job_data["user_id"], job_data["file_id"], {
                        "status": "failed",
                        "job_id": job_id,
                        "job_type": job_type.value,
                        "error": str(e)
                    })

                finally:
                    self.active_jobs[job_type] -= 1
                    self.queues[job_type].task_done()

            except Exception as e:
                logger.exception("Worker error for %s", job_type.value)
                if self.active_jobs[job_type] > 0:
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
