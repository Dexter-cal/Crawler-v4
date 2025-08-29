import os
import sys
import time
import psutil
import uuid

class Evasion:
    def __init__(self):
        pass

    def run(self, args: dict):
        """Runs all evasion checks."""
        results = {} # Use a local variable for stateless operation
        if args.get("force_trigger", False):
            results["test_trigger"] = "Rule engine test trigger enabled."

        self._get_username(results)
        self._get_mac_address(results)
        self._check_hardware(results)
        # self._check_time_acceleration(results)

        if not results:
            return {"status": "No sandbox indicators detected."}

        return results

    def _get_username(self, results: dict):
        """Checks for common sandbox usernames."""
        common_names = ["sandbox", "test", "virus", "malware", "vm", "user"]
        try:
            username = os.getlogin().lower()
            if username in common_names:
                results["username"] = f"Insecure username detected: {username}"
        except Exception:
            # os.getlogin() can fail in some environments
            username = psutil.Process().username().lower()
            if username in common_names:
                results["username"] = f"Insecure username detected: {username}"


    def _get_mac_address(self, results: dict):
        """Checks for MAC addresses of known VM vendors."""
        mac = ':'.join(("%012X" % uuid.getnode())[i:i+2] for i in range(0, 12, 2))

        vm_mac_prefixes = [
            "00:05:69", "00:0C:29", "00:1C:14", "00:50:56", # VMWare
            "08:00:27", # VirtualBox
            "00:03:FF", "00:15:5D", # Microsoft Hyper-V
        ]

        for prefix in vm_mac_prefixes:
            if mac.upper().startswith(prefix):
                results["mac_address"] = f"VM-associated MAC address detected: {mac}"
                break

    def _check_hardware(self, results: dict):
        """Checks for suspicious hardware configurations (low CPU/RAM)."""
        cpu_count = psutil.cpu_count()
        if cpu_count < 2:
            results["hardware_cpu"] = f"Low CPU core count: {cpu_count}"

        ram_gb = psutil.virtual_memory().total / (1024**3)
        if ram_gb < 2.0:
            results["hardware_ram"] = f"Low RAM amount: {ram_gb:.2f} GB"

    def _check_time_acceleration(self, results: dict):
        """Checks for time acceleration by comparing sleep time with elapsed time."""
        sleep_duration = 5
        start_time = time.time()
        time.sleep(sleep_duration)
        end_time = time.time()

        elapsed = end_time - start_time
        if elapsed < (sleep_duration * 0.8):
            results["time_acceleration"] = f"Detected accelerated time. Slept for {sleep_duration}s but only {elapsed:.2f}s passed."

def load():
    """Entry point for the plugin loader."""
    return Evasion()
