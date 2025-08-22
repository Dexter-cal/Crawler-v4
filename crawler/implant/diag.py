import os
import platform

print("--- Diagnostic Script Start ---")
print(f"Current Working Directory: {os.getcwd()}")
print(f"Platform: {platform.system()} {platform.release()}")
print("--- Diagnostic Script End ---")
