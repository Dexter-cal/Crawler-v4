from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from pydantic import BaseModel
from typing import List
import json

from .database import Base

# ==============================================================================
# SQLAlchemy Models (Define Database Tables)
# ==============================================================================

class Implant(Base):
    __tablename__ = "implants"
    id = Column(String, primary_key=True, index=True)
    hostname = Column(String, index=True)
    os = Column(String)
    pid = Column(Integer)
    roe_tier = Column(Integer, default=3)
    tasks = relationship("Task", back_populates="implant", cascade="all, delete-orphan")

class Task(Base):
    __tablename__ = "tasks"
    id = Column(Integer, primary_key=True, index=True)
    command = Column(String)
    args_json = Column(Text, name="args")
    implant_id = Column(String, ForeignKey("implants.id"))
    implant = relationship("Implant", back_populates="tasks")

    @property
    def args(self):
        return json.loads(self.args_json) if self.args_json else {}
    @args.setter
    def args(self, value):
        self.args_json = json.dumps(value)

# ==============================================================================
# Pydantic Schemas (Define API Data Shapes)
# ==============================================================================

class TaskBase(BaseModel):
    command: str
    args: dict = {}

class TaskCreate(TaskBase):
    pass

class TaskSchema(TaskBase):
    id: int
    implant_id: str
    class Config:
        from_attributes = True

class TaskResponse(BaseModel):
    tasks: List[TaskSchema] = []

class ImplantBase(BaseModel):
    hostname: str
    os: str
    pid: int

class ImplantCreate(ImplantBase):
    id: str
    roe_tier: int = 3

class ImplantSchema(ImplantBase):
    id: str
    roe_tier: int
    tasks: List[TaskSchema] = []
    class Config:
        from_attributes = True

class RegistrationResponse(BaseModel):
    implant_id: str
    token: str

class DataPayload(BaseModel):
    plugin: str
    data: str
