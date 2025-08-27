import os
import sys
import time
import psutil
import uuid

class Evasion:
    def __init__(self):
        self.results = {}

    def get_username(self):
        """Checks for common sandbox usernames."""
        common_names = ["sandbox", "test", "virus", "malware", "vm", "user"]
        try:
            username = os.getlogin().lower()
            if username in common_names:
                self.results["username"] = f"Insecure username detected: {username}"
        except Exception:
            # os.getlogin() can fail in some environments
            username = psutil.Process().username().lower()
            if username in common_names:
                self.results["username"] = f"Insecure username detected: {username}"


    def get_mac_address(self):
        """Checks for MAC addresses of known VM vendors."""
        # Using uuid.getnode() is a simple way to get the MAC address
        mac = ':'.join(("%012X" % uuid.getnode())[i:i+2] for i in range(0, 12, 2))

        # Prefixes for VMWare, VirtualBox, Hyper-V, etc.
        vm_mac_prefixes = [
            "00:05:69", # VMWare
            "00:0C:29", # VMWare
            "00:1C:14", # VMWare
            "00:50:56", # VMWare
            "08:00:27", # VirtualBox
            "00:03:FF", # Microsoft Hyper-V
            "00:15:5D", # Microsoft Hyper-V
        ]

        for prefix in vm_mac_prefixes:
            if mac.upper().startswith(prefix):
                self.results["mac_address"] = f"VM-associated MAC address detected: {mac}"
                break

    def check_hardware(self):
        """Checks for suspicious hardware configurations (low CPU/RAM)."""
        cpu_count = psutil.cpu_count()
        if cpu_count < 2:
            self.results["hardware_cpu"] = f"Low CPU core count: {cpu_count}"

        ram_gb = psutil.virtual_memory().total / (1024**3)
        if ram_gb < 2.0:
            self.results["hardware_ram"] = f"Low RAM amount: {ram_gb:.2f} GB"

    def check_time_acceleration(self):
        """Checks for time acceleration by comparing sleep time with elapsed time."""
        sleep_duration = 5
        start_time = time.time()
        time.sleep(sleep_duration)
        end_time = time.time()

        elapsed = end_time - start_time
        if elapsed < (sleep_duration * 0.8): # If time passed significantly faster
            self.results["time_acceleration"] = f"Detected accelerated time. Slept for {sleep_duration}s but only {elapsed:.2f}s passed."

    def run(self):
        """Runs all evasion checks."""
        self.get_username()
        self.get_mac_address()
        self.check_hardware()
        # Disabling time check for now as it slows down tests, can be enabled for production
        # self.check_time_acceleration()

        if not self.results:
            return {"status": "No sandbox indicators detected."}

        return self.results

def load():
    """Entry point for the plugin loader."""
    return Evasion()
