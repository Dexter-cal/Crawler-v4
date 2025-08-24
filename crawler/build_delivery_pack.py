import os
import json
import base64
import argparse

# --- Configuration ---
AGENT_LOADER_PATH = os.path.join("implant", "agent.py")
OUTPUT_PACK_PATH = "delivery_pack.json"

def build_pack(target_os: str):
    """
    Creates a delivery pack containing the implant payload, tailored
    for a specific target operating system.
    """
    print(f"[*] Building delivery pack for target OS: {target_os}")

    # 1. Read the implant loader code
    print(f"[*] Reading agent loader from: {AGENT_LOADER_PATH}")
    try:
        with open(AGENT_LOADER_PATH, 'rb') as f:
            agent_code = f.read()
    except FileNotFoundError:
        print(f"[!] Error: Agent loader not found at '{AGENT_LOADER_PATH}'.")
        return

    # 2. Obfuscate the payload (simple base64 for this PoC)
    encoded_payload = base64.b64encode(agent_code).decode('utf-8')

    # 3. Create the "smart" delivery pack structure
    # This structure can be expanded with more target-specific info,
    # different payloads, or configuration details.
    delivery_pack = {
        "metadata": {
            "target_os": target_os,
            "pack_version": "1.0",
            "description": "Simulated Zero-Click Delivery Pack"
        },
        "payload": {
            "type": "python_b64",
            "content": encoded_payload
        }
    }

    # 4. Save the pack to a file
    print(f"[*] Saving delivery pack to: {OUTPUT_PACK_PATH}")
    with open(OUTPUT_PACK_PATH, "w") as f:
        json.dump(delivery_pack, f, indent=2)

    print("[+] Delivery pack created successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crawler Delivery Pack Builder")
    parser.add_argument(
        "--os",
        type=str,
        default="linux",
        choices=["linux", "windows"],
        help="The target operating system for the payload."
    )
    args = parser.parse_args()

    # Ensure we are in the 'crawler' directory context
    if os.path.basename(os.getcwd()) != "crawler":
        if os.path.isdir("crawler"):
            os.chdir("crawler")
        else:
            print("[!] Error: Please run this script from the project root or 'crawler' directory.")
            exit(1)

    build_pack(target_os=args.os)
