"""
Simple script to validate the centralized job queue poller.

Usage:
    python scripts/test_job_queue_poller.py

Prerequisites:
    - Ensure the FastAPI app (or whichever process runs `job_queue.start_workers()`) is running.
    - Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in environment.
"""

import asyncio
import os
import time
from datetime import datetime

from app.core.database import supabase
from app.services.job_queue import job_queue, JobType, JobPriority


TEST_FILE_ID = "test-file-id"
TEST_USER_ID = "test-user-id"
TEST_JOB_TYPE = JobType.TEXT_EXTRACTION


async def insert_test_job() -> str:
    """Insert a test job directly into the processing_jobs table."""
    response = supabase.table("processing_jobs").insert({
        "file_id": TEST_FILE_ID,
        "user_id": TEST_USER_ID,
        "job_type": TEST_JOB_TYPE.value,
        "status": "queued",
        "priority": JobPriority.NORMAL.value,
        "created_at": datetime.utcnow().isoformat(),
    }).execute()

    job_id = response.data[0]["id"]
    print(f"[test] Inserted test job {job_id}")
    return job_id


async def wait_for_job(queue, job_id: str, timeout: float = 10.0) -> bool:
    """Wait until the job appears in the local queue."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        # Peek into queue contents by iterating over internal list
        items = list(queue._queue)  # type: ignore[attr-defined]
        for priority, _, job_data in items:
            if job_data.get("job_id") == job_id:
                print(f"[test] Job {job_id} found in queue with priority {priority}")
                return True
        await asyncio.sleep(0.5)
    return False


async def main():
    print("[test] Starting job queue poller test")

    if not job_queue._running:
        job_queue.start_workers()
        print("[test] Started job queue workers")

    job_id = await insert_test_job()

    # Wait for poller to run at least twice
    print("[test] Waiting up to 10 seconds for poller to fetch the job...")
    found = await wait_for_job(job_queue.queues[TEST_JOB_TYPE], job_id, timeout=12.0)

    if found:
        print("[test] SUCCESS: Poller fetched job and enqueued it locally")
    else:
        print("[test] FAILURE: Job was not enqueued by poller within timeout")

    # Cleanup inserted job
    supabase.table("processing_jobs").delete().eq("id", job_id).execute()
    print(f"[test] Cleaned up test job {job_id}")

    # Stop workers if we started them here
    if job_queue._running:
        await job_queue.stop_workers()
        print("[test] Stopped job queue workers")


if __name__ == "__main__":
    asyncio.run(main())
