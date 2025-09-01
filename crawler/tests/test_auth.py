import pytest
import threading
import time
import uvicorn
import requests
import os
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from crawler.c2.main import app as main_app
from crawler.c2.api import get_db
from crawler.implant.agent_core import CrawlerAgent
from crawler.c2.database import Base

# --- Test Configuration ---
HOST = "127.0.0.1"
PORT = 8888
C2_URL = f"http://{HOST}:{PORT}/api"

# --- Test App and DB Setup ---
test_app = FastAPI()
test_app.include_router(main_app.router)

TEST_DB_URL = "sqlite:///./test_auth.db"
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
def test_auth_beacon(c2_server_and_db):
    # 1. Start agent
    agent = CrawlerAgent(c2_url=C2_URL)
    agent.BEACON_INTERVAL_SECONDS = 2
    agent_thread = threading.Thread(target=agent.run, name="AgentThread")
    agent_thread.daemon = True
    agent_thread.start()

    # Wait for a few beacons
    print("\n--- Waiting for agent to beacon multiple times ---")
    time.sleep(agent.BEACON_INTERVAL_SECONDS * 4)

    # 2. Terminate
    response = requests.get(f"{C2_URL}/admin/implants")
    implant_id = response.json()[0]['id']
    requests.post(f"{C2_URL}/admin/tasks/{implant_id}", json={"command": "terminate"})
    agent_thread.join(timeout=5)

    assert not agent_thread.is_alive(), "Agent did not terminate."
    print("Test: Finished.")
