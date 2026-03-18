from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class NodeBase(BaseModel):
    hostname: str
    ip_address: str
    capacity_ram_mb: int
    capacity_vcpus: int

class NodeRegister(NodeBase):
    pass

class NodeResponse(NodeBase):
    id: int
    status: str
    heartbeat: datetime

    class Config:
        from_attributes = True

class MicroVMBase(BaseModel):
    vm_id: str
    vcpus: int = 1
    memory_mb: int = 512

class MicroVMCreate(MicroVMBase):
    node_id: Optional[int] = None

class MicroVMResponse(MicroVMBase):
    id: int
    node_id: Optional[int]
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class TaskBase(BaseModel):
    type: str
    payload: Optional[str] = None
    node_id: Optional[int] = None

class TaskResponse(TaskBase):
    id: int
    status: str
    result: Optional[str] = None
    checkpoint: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    result: Optional[Any] = None
    enqueued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
