import os
import psutil
import uuid

class Evasion:
    def __init__(self):
        self.type = "one-shot"

    def run(self, args: dict):
        results = {}
        if args.get("force_trigger", False):
            results["test_trigger"] = "Rule engine test trigger enabled."
        self._get_username(results)
        self._get_mac_address(results)
        self._check_hardware(results)
        if not results:
            return {"status": "No sandbox indicators detected."}
        return results

    def _get_username(self, results: dict):
        common_names = ["sandbox", "test", "virus", "malware", "vm", "user"]
        try:
            username = os.getlogin().lower()
            if username in common_names:
                results["username"] = f"Insecure username detected: {username}"
        except Exception:
            username = psutil.Process().username().lower()
            if username in common_names:
                results["username"] = f"Insecure username detected: {username}"

    def _get_mac_address(self, results: dict):
        mac = ':'.join(("%012X" % uuid.getnode())[i:i+2] for i in range(0, 12, 2))
        vm_mac_prefixes = ["00:05:69", "00:0C:29", "00:1C:14", "00:50:56", "08:00:27", "00:03:FF", "00:15:5D"]
        for prefix in vm_mac_prefixes:
            if mac.upper().startswith(prefix):
                results["mac_address"] = f"VM-associated MAC address detected: {mac}"
                break

    def _check_hardware(self, results: dict):
        if psutil.cpu_count() < 2:
            results["hardware_cpu"] = f"Low CPU core count: {psutil.cpu_count()}"
        if psutil.virtual_memory().total / (1024**3) < 2.0:
            results["hardware_ram"] = f"Low RAM amount: {psutil.virtual_memory().total / (1024**3):.2f} GB"

def load():
    return Evasion()
