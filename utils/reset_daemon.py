import os
import sys
import json


def reset_processed_dirs(file_path=".processed_dirs.txt"):
    if os.path.exists(file_path):
        os.remove(file_path)
        print(f"Removed {file_path}")
    else:
        print(f"No {file_path} found")
    
    empty_state = {"processed": []}
    with open(file_path, 'w') as f:
        json.dump(empty_state, f)
    print(f"Created empty {file_path}")

if __name__ == "__main__":
    reset_processed_dirs()
    print("\nProcessed directories reset. Restart the daemon to reprocess all directories.")