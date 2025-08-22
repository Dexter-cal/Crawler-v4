from pydantic import BaseModel, Field
from typing import List, Dict, Any
import uuid

class ImplantRegistration(BaseModel):
    hostname: str
    os: str
    pid: int

class Task(BaseModel):
    task_id: str = Field(default_factory=lambda: f"task-{uuid.uuid4()}")
    command: str
    args: Dict[str, Any] = {}

class Implant(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    hostname: str
    os: str
    pid: int
    roe_tier: int = 3  # Default to the most restrictive tier
    tasks: List[Task] = []

class TaskResponse(BaseModel):
    tasks: List[Task]

class DataPayload(BaseModel):
    plugin: str
    data: str

class RegistrationResponse(BaseModel):
    implant_id: str
    token: str

# This allows Pydantic to handle the forward reference of 'Task' in the 'Implant' model.
Implant.update_forward_refs()
