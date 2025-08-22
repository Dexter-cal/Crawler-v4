import datetime
import threading
import time
from typing import List, Dict, Any

from .base_plugin import BasePlugin

class DummyPlugin(BasePlugin):
    """
    A safe, dependency-free plugin for testing the core agent functionality.
    It generates simple, static data to verify the data exfiltration pipeline.
    """
    def __init__(self):
        self.is_running = False
        self._data_buffer: List[Dict[str, Any]] = []
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def get_name(self) -> str:
        return "dummy"

    def _generate_data(self):
        """A simple loop to generate data periodically."""
        while self.is_running:
            with self._lock:
                data_entry = {
                    "timestamp_utc": datetime.datetime.utcnow().isoformat(),
                    "log_type": "dummy_data",
                    "content": "This is a test payload from the dummy plugin."
                }
                self._data_buffer.append(data_entry)
            time.sleep(5) # Generate data every 5 seconds

    def start(self, args: Dict[str, Any]):
        """Starts the dummy data generation in a background thread."""
        if self.is_running:
            print("Dummy plugin is already running.")
            return

        print("Starting dummy plugin...")
        self.is_running = True
        self._thread = threading.Thread(target=self._generate_data)
        self._thread.daemon = True
        self._thread.start()
        print("Dummy plugin started successfully.")

    def stop(self):
        """Stops the dummy data generation."""
        if not self.is_running:
            print("Dummy plugin is not running.")
            return

        print("Stopping dummy plugin...")
        self.is_running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._thread = None
        print("Dummy plugin stopped.")

    def get_data(self) -> List[Dict[str, Any]]:
        """Retrieves generated data and clears the internal buffer."""
        with self._lock:
            data_to_send = list(self._data_buffer) # Create a copy
            self._data_buffer.clear() # Clear the buffer
            return data_to_send
