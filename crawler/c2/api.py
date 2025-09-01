from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict
import uuid
import json

from . import models, security, comms
from .database import SessionLocal

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

ROE_GATES = {1: [], 2: [], 3: []}

@router.post("/register", response_model=models.RegistrationResponse)
def register_implant(registration: models.ImplantBase, db: Session = Depends(get_db)):
    implant_id = str(uuid.uuid4())
    db_implant = models.Implant(id=implant_id, **registration.model_dump())
    db.add(db_implant)
    db.commit()
    db.refresh(db_implant)
    token = security.create_access_token(data={"sub": implant_id})
    return {"implant_id": implant_id, "token": token}

@router.get("/tasks", response_model=models.TaskResponse)
def get_tasks(db: Session = Depends(get_db), current_implant_id: str = Depends(security.get_current_implant_id)):
    tasks = db.query(models.Task).filter(models.Task.implant_id == current_implant_id, models.Task.status == "pending").all()
    for task in tasks:
        task.status = "dispatched"
    db.commit()
    return {"tasks": tasks}

@router.post("/tasks/result")
def submit_task_result(payload: models.TaskResult, db: Session = Depends(get_db), current_implant_id: str = Depends(security.get_current_implant_id)):
    task = db.query(models.Task).filter(models.Task.id == payload.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    task.result = payload.result
    task.status = "completed"
    db.commit()
    return {"status": "result recorded"}

@router.get("/admin/implants", response_model=List[models.ImplantSchema])
def list_implants(db: Session = Depends(get_db)):
    return db.query(models.Implant).all()

@router.post("/admin/tasks/{implant_id}", response_model=models.TaskSchema)
def add_task(implant_id: str, task: models.TaskCreate, db: Session = Depends(get_db)):
    db_task = models.Task(**task.model_dump(), implant_id=implant_id)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task
