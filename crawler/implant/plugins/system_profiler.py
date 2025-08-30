import platform
import socket
import os
import psutil
from typing import Dict, Any

class SystemProfiler:
    def __init__(self):
        self.type = "one-shot"

    def run(self, args: dict) -> Dict[str, Any]:
        profile = {}
        profile['os'] = {'system': platform.system(), 'release': platform.release(), 'version': platform.version(), 'architecture': platform.machine(), 'hostname': socket.gethostname()}
        try:
            profile['user'] = {'login_name': os.getlogin(), 'home_dir': os.path.expanduser("~")}
        except Exception:
            profile['user'] = "Could not determine user info."
        profile['cpu'] = {'physical_cores': psutil.cpu_count(logical=False), 'total_cores': psutil.cpu_count(logical=True), 'cpu_usage_percent': psutil.cpu_percent(interval=1)}
        mem = psutil.virtual_memory()
        profile['memory'] = {'total_gb': round(mem.total / (1024**3), 2), 'available_gb': round(mem.available / (1024**3), 2), 'used_percent': mem.percent}
        partitions = psutil.disk_partitions()
        disk_info = []
        for p in partitions:
            try:
                usage = psutil.disk_usage(p.mountpoint)
                disk_info.append({'device': p.device, 'mountpoint': p.mountpoint, 'filesystem': p.fstype, 'total_gb': round(usage.total / (1024**3), 2), 'used_percent': usage.percent})
            except Exception: continue
        profile['disks'] = disk_info
        net_if_addrs = psutil.net_if_addrs()
        network_info = []
        for interface, addrs in net_if_addrs.items():
            if_info = {'interface': interface, 'mac': '', 'ipv4': '', 'ipv6': ''}
            for addr in addrs:
                if addr.family == psutil.AF_LINK: if_info['mac'] = addr.address
                elif addr.family == socket.AF_INET: if_info['ipv4'] = addr.address
                elif addr.family == socket.AF_INET6: if_info['ipv6'] = addr.address
            network_info.append(if_info)
        profile['network'] = network_info
        return profile

def load():
    return SystemProfiler()
