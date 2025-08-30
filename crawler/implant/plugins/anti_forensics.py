import os
import secrets

class AntiForensics:
    def __init__(self):
        self.type = "one-shot"

    def run(self, args: dict):
        file_path = args.get("file_path")
        if not file_path:
            return {"status": "error", "message": "Missing 'file_path' argument."}
        return self._secure_delete(file_path)

    def _secure_delete(self, file_path: str):
        if not os.path.exists(file_path) or not os.path.isfile(file_path):
            return {"status": "error", "message": f"File not found: {file_path}"}
        try:
            with open(file_path, "wb") as f:
                file_size = os.path.getsize(file_path)
                for _ in range(3):
                    f.write(secrets.token_bytes(file_size))
                    f.flush()
                    os.fsync(f.fileno())
                    f.seek(0)
            os.remove(file_path)
            return {"status": "success", "message": f"Successfully secure-deleted '{file_path}'."}
        except Exception as e:
            return {"status": "error", "message": f"Failed to secure-delete '{file_path}': {e}"}

def load():
    return AntiForensics()
