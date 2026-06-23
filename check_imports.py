# check_imports.py
import os
import re

def check_imports():
    """Check all Python files for db_adapter imports"""
    
    files_to_check = []
    
    for root, dirs, files in os.walk("backend"):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                with open(filepath, "r") as f:
                    content = f.read()
                if "from backend.core.db_adapter import" in content:
                    files_to_check.append(filepath)
    
    print("Files that import from db_adapter:")
    for f in files_to_check:
        print(f"  - {f}")

if __name__ == "__main__":
    check_imports()