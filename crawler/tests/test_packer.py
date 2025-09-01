import os
import subprocess
import sys
import shutil

# This test needs to be able to import the packer
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from tools import packer

TEST_TMP_DIR = "test_packer_tmp"

def setup_module(module):
    """Create a temporary directory structure for the test."""
    if os.path.exists(TEST_TMP_DIR):
        shutil.rmtree(TEST_TMP_DIR)
    os.makedirs(os.path.join(TEST_TMP_DIR, "crawler/implant/plugins"))

    # Create dummy agent core
    with open(os.path.join(TEST_TMP_DIR, "crawler/implant/agent_core.py"), "w") as f:
        f.write('class CrawlerAgent:\n    def run(self):\n        print("Agent run method called")\n')

    # Create dummy plugin
    with open(os.path.join(TEST_TMP_DIR, "crawler/implant/plugins/dummy_plugin.py"), "w") as f:
        f.write('print("Hello from dummy plugin")\n')

def teardown_module(module):
    """Clean up the temporary directory."""
    if os.path.exists(TEST_TMP_DIR):
        shutil.rmtree(TEST_TMP_DIR)
    if os.path.exists("packed_test_agent.py"):
        os.remove("packed_test_agent.py")


def test_packer_and_stub():
    """
    Tests that the packer can create a stub that successfully executes the payload.
    """
    # Temporarily change directory to the test setup so the packer finds the files
    original_cwd = os.getcwd()
    os.chdir(TEST_TMP_DIR)

    try:
        # 1. Create the payload string from the dummy files
        payload_string = packer.create_payload()
        assert 'Hello from dummy plugin' in payload_string
        assert 'CrawlerAgent' in payload_string

        # 2. Pack the payload into a stub file
        output_filename = "packed_test_agent.py"
        packer.pack(payload_string, output_filename)
        assert os.path.exists(output_filename)

        # 3. Run the packed stub and capture its output
        result = subprocess.run([sys.executable, output_filename], capture_output=True, text=True)

        assert result.returncode == 0, f"Packed stub failed with stderr: {result.stderr}"
        assert "Hello from dummy plugin" in result.stdout

        print("Packer test successful: Stub executed the payload correctly.")

    finally:
        # Change back to the original directory
        os.chdir(original_cwd)
