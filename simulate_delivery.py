import os
import json
import base64
import platform
import sys

# --- Configuration ---
DELIVERY_PACK_PATH = os.path.join("crawler", "delivery_pack.json")

def simulate_vulnerable_app():
    """
    Simulates a vulnerable application that receives and processes a
    malicious data blob (our delivery pack).
    """
    print("[*] Simulated Target App: Received a data packet.")

    # 1. Read the delivery pack
    try:
        with open(DELIVERY_PACK_PATH, "r") as f:
            delivery_pack = json.load(f)
        print("[*] Simulated Target App: Parsed data packet as JSON.")
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[!] Simulated Target App: Received malformed or missing data packet. Ignoring. ({e})")
        return

    # 2. "Smart" check: The app checks if the payload is for its OS
    metadata = delivery_pack.get("metadata", {})
    target_os = metadata.get("target_os")
    current_os = platform.system().lower()

    print(f"[*] Simulated Target App: Packet is for '{target_os}', this system is '{current_os}'.")
    if target_os != current_os:
        print("[!] Simulated Target App: OS mismatch. Payload is not for this system. Ignoring.")
        return

    # 3. "Vulnerability Triggered": The app processes the payload
    payload = delivery_pack.get("payload", {})
    if payload.get("type") == "python_b64":
        print("[+] Simulated Target App: Vulnerability triggered! Processing python_b64 payload.")
        encoded_content = payload.get("content")

        try:
            # 4. Decode and execute
            decoded_code = base64.b64decode(encoded_content)

            # Add project root to path to resolve 'crawler' package imports
            sys.path.insert(0, os.getcwd())

            print("[+] Simulated Target App: Executing embedded payload in memory...")
            # The exec call will now run the agent loader
            exec(decoded_code, {'__name__': '__main__'})

        except Exception as e:
            print(f"[!] Simulated Target App: Error during payload execution. ({e})")
    else:
        print("[!] Simulated Target App: Unknown payload type. Ignoring.")

if __name__ == "__main__":
    simulate_vulnerable_app()
