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
    # Accept both the original and the new polymorphic type
    if payload.get("type") in ["python_b64", "python_b64_polymorphic"]:
        print(f"[+] Simulated Target App: Vulnerability triggered! Processing {payload.get('type')} payload.")
        encoded_content = payload.get("content")

        try:
            # 4. Decode and execute
            decoded_code = base64.b64decode(encoded_content)

            # Define the globals for the execution context.
            # Setting '__package__' is crucial for relative imports to work correctly.
            exec_globals = {
                '__name__': '__main__',
                '__package__': 'crawler.implant'
            }

            # Add project root to path to resolve top-level 'crawler' package
            sys.path.insert(0, os.getcwd())

            print("[+] Simulated Target App: Executing embedded payload in memory...")
            exec(decoded_code, exec_globals)

        except Exception as e:
            print(f"[!] Simulated Target App: Error during payload execution. ({e})")
    else:
        print("[!] Simulated Target App: Unknown payload type. Ignoring.")

if __name__ == "__main__":
    simulate_vulnerable_app()
