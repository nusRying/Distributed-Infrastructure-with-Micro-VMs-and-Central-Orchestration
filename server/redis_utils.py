from redis import Redis
import os
import sys

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_conn = Redis.from_url(REDIS_URL)

try:
    from rq import Queue
    task_queue = Queue("default", connection=redis_conn)
except (ImportError, ValueError):
    # Fallback for Windows where 'fork' is not available
    class MockQueue:
        def enqueue(self, func, *args, **kwargs):
            print(f"MockQueue: Enqueued {func.__name__} (not actually running on Windows)")
            class MockJob:
                id = "mock-job-id"
                def get_status(self): return "started"
            return MockJob()
        def fetch_job(self, job_id):
            return None
    task_queue = MockQueue()
