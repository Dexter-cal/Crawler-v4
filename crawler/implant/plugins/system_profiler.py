import platform
import socket
import os
import psutil
import datetime
from typing import List, Dict, Any

from .base_plugin import BasePlugin

class SystemProfilerPlugin(BasePlugin):
    """
    A plugin to gather a comprehensive profile of the target system.
    This is a one-shot plugin; it collects data when started and does not
    run a persistent background thread.
    """

    def __init__(self):
        self._data_buffer: List[Dict[str, Any]] = []

    def get_name(self) -> str:
        return "system_profiler"

    def start(self, args: Dict[str, Any]):
        """Collects all system information and stores it in the buffer."""
        print("Starting system profiler plugin...")
        profile = self._get_system_profile()

        data_entry = {
            "timestamp_utc": datetime.datetime.utcnow().isoformat(),
            "log_type": "system_profile",
            "content": profile
        }
        self._data_buffer.append(data_entry)
        print("System profile collected.")

    def stop(self):
        # This is a one-shot plugin, so stop does nothing.
        pass

    def get_data(self) -> List[Dict[str, Any]]:
        """Returns the collected profile and clears the buffer."""
        data_to_send = list(self._data_buffer)
        self._data_buffer.clear()
        return data_to_send

    def _get_system_profile(self) -> Dict[str, Any]:
        """Gathers various system details."""
        profile = {}

        # OS Info
        profile['os'] = {
            'system': platform.system(),
            'release': platform.release(),
            'version': platform.version(),
            'architecture': platform.machine(),
            'hostname': socket.gethostname()
        }

        # User Info
        try:
            profile['user'] = {
                'login_name': os.getlogin(),
                'home_dir': os.path.expanduser("~")
            }
        except Exception:
            profile['user'] = "Could not determine user info."

        # CPU Info
        profile['cpu'] = {
            'physical_cores': psutil.cpu_count(logical=False),
            'total_cores': psutil.cpu_count(logical=True),
            'cpu_usage_percent': psutil.cpu_percent(interval=1)
        }

        # Memory Info
        mem = psutil.virtual_memory()
        profile['memory'] = {
            'total_gb': round(mem.total / (1024**3), 2),
            'available_gb': round(mem.available / (1024**3), 2),
            'used_percent': mem.percent
        }

        # Disk Info
        partitions = psutil.disk_partitions()
        disk_info = []
        for p in partitions:
            try:
                usage = psutil.disk_usage(p.mountpoint)
                disk_info.append({
                    'device': p.device,
                    'mountpoint': p.mountpoint,
                    'filesystem': p.fstype,
                    'total_gb': round(usage.total / (1024**3), 2),
                    'used_percent': usage.percent
                })
            except Exception:
                continue
        profile['disks'] = disk_info

        # Network Info
        net_if_addrs = psutil.net_if_addrs()
        network_info = []
        for interface, addrs in net_if_addrs.items():
            if_info = {'interface': interface, 'mac': '', 'ipv4': '', 'ipv6': ''}
            for addr in addrs:
                if addr.family == psutil.AF_LINK:
                    if_info['mac'] = addr.address
                elif addr.family == socket.AF_INET:
                    if_info['ipv4'] = addr.address
                elif addr.family == socket.AF_INET6:
                    if_info['ipv6'] = addr.address
            network_info.append(if_info)
        profile['network'] = network_info

        return profile
