import pytest
import threading
import time
import uvicorn
import requests
import os
import json
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
C2_RULES_FILE = os.path.join("crawler", "c2", "rules.json")

# --- Test App and DB Setup ---
test_app = FastAPI()
test_app.include_router(main_app.router)

TEST_DB_URL = "sqlite:///./test_chained_analysis.db"
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
    if os.path.exists(TEST_DB_URL.replace("sqlite:///", "")):
        os.remove(TEST_DB_URL.replace("sqlite:///", ""))
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
    if os.path.exists(TEST_DB_URL.replace("sqlite:///", "")):
        os.remove(TEST_DB_URL.replace("sqlite:///", ""))

# --- The Test ---
def test_chained_analysis(c2_server_and_db):
    if os.path.exists(C2_RULES_FILE): os.remove(C2_RULES_FILE)

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

    # 3. Setup Rule and Mock
    rule_content = [{"name": "Analyze_Profiler_Results", "condition": {"plugin": "system_profiler", "result_not_empty": True}, "action": {"type": "analyze_with_llm", "prompt_template": "Profile data: {trigger_data}"}}]
    with open(C2_RULES_FILE, "w") as f: json.dump(rule_content, f)

    print("\n--- RELOADING RULE ENGINE ---")
    from crawler.c2.api import rule_engine
    rule_engine.rules = rule_engine._load_rules()
    print("--- FINISHED RELOADING ---")

    mock_llm_response = {"choices": [{"message": {"content": json.dumps({"anomaly": "found"})}}]}

    with patch('crawler.implant.plugins.llm_analyzer.requests.post') as mock_llm_post:
        mock_llm_post.return_value.status_code = 200
        mock_llm_post.return_value.json.return_value = mock_llm_response
        mock_llm_post.return_value.raise_for_status.return_value = None

        # 4. Run system_profiler to trigger the rule
        profiler_task = {"command": "start_plugin", "args": {"plugin_name": "system_profiler"}}
        requests.post(f"{C2_URL}/admin/tasks/{implant_id}", json=profiler_task)

        print("Test: Waiting for chained analysis to complete...")
        time.sleep(agent.BEACON_INTERVAL_SECONDS * 3)

        # 5. Verify the chain
        response = requests.get(f"{C2_URL}/admin/tasks/{implant_id}")
        tasks = response.json()

        profiler_done = any(t['args'].get('plugin_name') == 'system_profiler' and t['status'] == 'completed' for t in tasks)
        llm_done = any(t['args'].get('plugin_name') == 'llm_analyzer' and t['status'] == 'completed' for t in tasks)

        assert profiler_done, "Profiler task did not complete."
        assert llm_done, "Chained LLM task did not complete."

        mock_llm_post.assert_called_once()
        sent_prompt = mock_llm_post.call_args.kwargs['json']['messages'][0]['content']
        assert "Profile data" in sent_prompt
        assert "'os'" in sent_prompt
        print("Test: Verified chained analysis rule correctly triggered and completed.")

    # 6. Cleanup
    if os.path.exists(C2_RULES_FILE): os.remove(C2_RULES_FILE)
    requests.post(f"{C2_URL}/admin/tasks/{implant_id}", json={"command": "terminate"})
    agent_thread.join(timeout=5)
    print("Test: Finished.")
