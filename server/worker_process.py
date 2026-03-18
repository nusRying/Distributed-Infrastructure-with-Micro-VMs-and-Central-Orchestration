import sys
from redis import Redis
from rq import Worker, Queue
from redis_utils import redis_conn

if __name__ == '__main__':
    q = Queue('default', connection=redis_conn)
    worker = Worker([q], connection=redis_conn)
    worker.work()
