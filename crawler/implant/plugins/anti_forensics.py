import os
import secrets

class AntiForensics:
    """
    A plugin to perform actions that make forensic analysis more difficult.
    """
    def run(self, args: dict):
        """
        Executes the anti-forensics command.
        Currently supports 'secure_delete'.
        """
        file_path = args.get("file_path")
        if not file_path:
            return {"status": "error", "message": "Missing 'file_path' argument."}

        return self._secure_delete(file_path)

    def _secure_delete(self, file_path: str):
        """
        Overwrites a file with random data multiple times before deleting it.
        """
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return {"status": "error", "message": f"File not found or is not a regular file: {file_path}"}

        try:
            # Get the file size
            file_size = os.path.getsize(file_path)

            # Open in binary write mode
            with open(file_path, "wb") as f:
                # Pass 1: Overwrite with random data
                f.write(secrets.token_bytes(file_size))
                f.flush()
                os.fsync(f.fileno())

                # Pass 2: Overwrite with more random data
                f.seek(0)
                f.write(secrets.token_bytes(file_size))
                f.flush()
                os.fsync(f.fileno())

                # Pass 3: Overwrite with zeros
                f.seek(0)
                f.write(b'\x00' * file_size)
                f.flush()
                os.fsync(f.fileno())

            # Finally, delete the file
            os.remove(file_path)

            return {"status": "success", "message": f"Successfully secure-deleted '{file_path}'."}

        except Exception as e:
            return {"status": "error", "message": f"Failed to secure-delete '{file_path}': {e}"}

def load():
    """Entry point for the plugin loader."""
    return AntiForensics()
