from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_superuser = Column(Boolean, default=False)

class Node(Base):
    __tablename__ = "nodes"
    id = Column(Integer, primary_key=True, index=True)
    hostname = Column(String, unique=True, index=True, nullable=False)
    ip_address = Column(String, nullable=False)
    status = Column(String, default="offline") # online, offline, error
    capacity_ram_mb = Column(Integer)
    capacity_vcpus = Column(Integer)
    heartbeat = Column(DateTime, default=datetime.utcnow)
    
    vms = relationship("MicroVM", back_populates="node")

class MicroVM(Base):
    __tablename__ = "microvms"
    id = Column(Integer, primary_key=True, index=True)
    vm_id = Column(String, unique=True, index=True, nullable=False) 
    node_id = Column(Integer, ForeignKey("nodes.id"))
    status = Column(String, default="pending") # pending, running, stopped, error
    vcpus = Column(Integer, default=1)
    memory_mb = Column(Integer, default=512)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    node = relationship("Node", back_populates="vms")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    type = Column(String, nullable=False) # vm_create, agent_cmd
    status = Column(String, default="queued") # queued, processing, completed, failed
    payload = Column(String) # JSON string
    result = Column(String) # JSON string
    checkpoint = Column(String) # JSON string of partial state
    node_id = Column(Integer, ForeignKey("nodes.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    node = relationship("Node")
