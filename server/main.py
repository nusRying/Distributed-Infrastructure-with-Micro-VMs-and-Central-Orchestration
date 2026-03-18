from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import time
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import datetime
import asyncio
from contextlib import asynccontextmanager

from redis_utils import task_queue
import tasks
import models
import schemas
from database import SessionLocal, engine
from pydantic import BaseModel

class TaskCreate(BaseModel):
    code: str
    target: str = "vm" # "vm" or "colab"

# Ensure tables exist
models.Base.metadata.create_all(bind=engine)

async def monitor_nodes_loop():
    while True:
        try:
            db = SessionLocal()
            now = datetime.datetime.utcnow()
            cutoff = now - datetime.timedelta(seconds=60)
            
            # Find silent nodes
            dead_nodes = db.query(models.Node).filter(
                models.Node.status == "online",
                models.Node.heartbeat < cutoff
            ).all()
            
            for d in dead_nodes:
                print(f"Node {d.id} ({d.hostname}) missed heartbeat, marking offline!")
                d.status = "offline"
                
                # Requeue dead tasks
                dead_tasks = db.query(models.Task).filter(
                    models.Task.node_id == d.id,
                    models.Task.status == "processing"
                ).all()
                for dt in dead_tasks:
                    print(f"Re-queueing task {dt.id} from dead node")
                    # It still has its checkpoint!
                    # Next node will get it with the checkpoint set.
                    dt.status = "queued"
                    dt.node_id = None
                    
            db.commit()
            db.close()
        except Exception as e:
            print(f"Monitor loop error: {e}")
            
        await asyncio.sleep(30)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    loop_task = asyncio.create_task(monitor_nodes_loop())
    yield
    # Shutdown
    loop_task.cancel()

app = FastAPI(
    title="Infrastructure Control Server",
    description="Orchestrator for Micro-VMs and Distributed Agents",
    version="0.1.0",
    lifespan=lifespan
)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from pydantic import BaseModel

@app.get("/")
async def root():
    return {
        "message": "Distributed Infrastructure Control Server is running",
        "timestamp": time.time(),
        "docs": "/docs"
    }

from sqlalchemy import text

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    # Test DB connection
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        print(f"DB Health check error: {e}")
        db_status = "error"
    return {"status": "healthy", "db": db_status, "version": "0.1.0"}

# --- Node Management ---

@app.post("/node/register", response_model=schemas.NodeResponse)
def register_node(node_data: schemas.NodeRegister, db: Session = Depends(get_db)):
    db_node = db.query(models.Node).filter(models.Node.hostname == node_data.hostname).first()
    if db_node:
        # Update existing node
        db_node.ip_address = node_data.ip_address
        db_node.capacity_ram_mb = node_data.capacity_ram_mb
        db_node.capacity_vcpus = node_data.capacity_vcpus
        db_node.status = "online"
        db_node.heartbeat = models.datetime.utcnow()
    else:
        # Create new node
        db_node = models.Node(
            hostname=node_data.hostname,
            ip_address=node_data.ip_address,
            capacity_ram_mb=node_data.capacity_ram_mb,
            capacity_vcpus=node_data.capacity_vcpus,
            status="online"
        )
        db.add(db_node)
    
    db.commit()
    db.refresh(db_node)
    return db_node

@app.post("/node/{node_id}/ping")
def ping_node(node_id: int, db: Session = Depends(get_db)):
    db_node = db.query(models.Node).filter(models.Node.id == node_id).first()
    if not db_node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    db_node.heartbeat = datetime.datetime.utcnow()
    db_node.status = "online"
    db.commit()
    return {"status": "ok"}

@app.get("/nodes", response_model=List[schemas.NodeResponse])
def list_nodes(db: Session = Depends(get_db)):
    return db.query(models.Node).all()

# --- Task Management ---

@app.post("/task/vm-create", response_model=Dict[str, str])
def create_vm_task(vm_data: schemas.MicroVMCreate):
    job = task_queue.enqueue(tasks.process_vm_creation, vm_data.vm_id, vm_data.node_id)
    return {"job_id": job.id, "status": "queued"}

@app.get("/job/{job_id}", response_model=schemas.JobStatusResponse)
def get_job_status(job_id: str):
    job = task_queue.fetch_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return {
        "job_id": job.id,
        "status": job.get_status(),
        "result": job.result,
        "enqueued_at": job.enqueued_at,
        "started_at": job.started_at,
        "ended_at": job.ended_at
    }

@app.post("/task", response_model=Dict[str, Any])
def create_task(task_data: TaskCreate, db: Session = Depends(get_db)):
    db_node = None
    if task_data.target == "vm":
        # simple round robin or pick any active node
        db_node = db.query(models.Node).filter(models.Node.status == "online").first()
    elif task_data.target == "colab":
        # pick a colab node if we modeled it, or pseudo node
        db_node = db.query(models.Node).filter(models.Node.hostname == "colab-worker").first()
        if not db_node:
            db_node = models.Node(hostname="colab-worker", ip_address="127.0.0.1", status="online")
            db.add(db_node)
            db.commit()
            db.refresh(db_node)

    if not db_node:
        raise HTTPException(status_code=400, detail="No suitable node available")

    task = models.Task(
        type="agent_cmd",
        payload=f'{{"code": "{task_data.code}"}}',
        status="queued",
        node_id=db_node.id
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    
    return {"id": task.id, "status": "queued", "node_id": task.node_id}

@app.get("/task/next", response_model=Optional[schemas.TaskResponse])
def get_next_task(node_id: int, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(
        models.Task.node_id == node_id,
        models.Task.status == "queued"
    ).order_by(models.Task.created_at.asc()).first()
    
    if task:
        task.status = "processing"
        db.commit()
        db.refresh(task)
        return task
    return None

@app.get("/task/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {
        "id": task.id,
        "status": task.status,
        "result": task.result,
        "checkpoint": task.checkpoint,
        "node_id": task.node_id
    }

class TaskResultUpdate(BaseModel):
    result: str

@app.post("/task/{task_id}/result")
def update_task_result(task_id: int, data: TaskResultUpdate, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.result = data.result
    task.status = "completed"
    db.commit()
    return {"status": "success"}

class TaskCheckpointUpdate(BaseModel):
    checkpoint: str

@app.post("/task/{task_id}/checkpoint")
def update_task_checkpoint(task_id: int, data: TaskCheckpointUpdate, db: Session = Depends(get_db)):
    task = db.query(models.Task).filter(models.Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.checkpoint = data.checkpoint
    db.commit()
    return {"status": "success"}

# Keep the legacy test endpoint for a bit
@app.post("/test_task/{vm_id}")
def trigger_test_task(vm_id: str, node_id: int = None):
    job = task_queue.enqueue(tasks.process_vm_creation, vm_id, node_id)
    return {"job_id": job.id, "status": "queued"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
