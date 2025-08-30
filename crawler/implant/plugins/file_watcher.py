import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from typing import List, Dict, Any

class FileWatcherEventHandler(FileSystemEventHandler):
    def __init__(self, event_buffer: List[Dict[str, Any]], lock: threading.Lock, extensions: List[str]):
        self.event_buffer = event_buffer
        self.lock = lock
        self.extensions = [ext.lower() for ext in extensions]

    def _should_log(self, event_path: str) -> bool:
        if not self.extensions:
            return True
        return any(event_path.lower().endswith(ext) for ext in self.extensions)

    def on_created(self, event):
        if not event.is_directory and self._should_log(event.src_path):
            with self.lock:
                self.event_buffer.append({"event_type": "created", "path": event.src_path})

    def on_deleted(self, event):
        if not event.is_directory and self._should_log(event.src_path):
            with self.lock:
                self.event_buffer.append({"event_type": "deleted", "path": event.src_path})

    def on_modified(self, event):
        if not event.is_directory and self._should_log(event.src_path):
            with self.lock:
                self.event_buffer.append({"event_type": "modified", "path": event.src_path})

class FileWatcher:
    """A long-running plugin to watch for file system events."""
    def __init__(self):
        self.type = "long-running"
        self.observer = None
        self.event_buffer: List[Dict[str, Any]] = []
        self.lock = threading.Lock()
        self.is_running = False

    def start(self, args: Dict[str, Any]):
        if self.is_running:
            return

        directory = args.get("directory", ".")
        extensions = args.get("extensions", [])

        event_handler = FileWatcherEventHandler(self.event_buffer, self.lock, extensions)
        self.observer = Observer()
        self.observer.schedule(event_handler, directory, recursive=True)

        self.observer.start()
        self.is_running = True
        print(f"File watcher started on directory: {directory}")

    def stop(self):
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join()
        self.is_running = False
        print("File watcher stopped.")

    def get_data(self) -> List[Dict[str, Any]]:
        with self.lock:
            data_to_send = list(self.event_buffer)
            self.event_buffer.clear()
        return data_to_send

def load():
    """Entry point for the plugin loader."""
    return FileWatcher()
