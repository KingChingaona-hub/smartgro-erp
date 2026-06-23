# test_setup.py
import os
import sys

print("🔍 Checking SmartGro System Setup...")

# Check Python version
print(f"✅ Python version: {sys.version}")

# Check required packages
try:
    import sqlalchemy
    print(f"✅ SQLAlchemy installed: {sqlalchemy.__version__}")
except:
    print("❌ SQLAlchemy not installed")

try:
    import psycopg2
    print("✅ psycopg2 installed")
except:
    print("❌ psycopg2 not installed")

try:
    import streamlit
    print(f"✅ Streamlit installed: {streamlit.__version__}")
except:
    print("❌ Streamlit not installed")

# Check folders
folders = [
    "backend", "backend/database", "frontend", 
    "frontend/pages", "static", "data", "backups", "logs"
]

for folder in folders:
    if os.path.exists(folder):
        print(f"✅ Folder: {folder}/ exists")
    else:
        print(f"❌ Folder: {folder}/ missing")

# Check important files
files = [
    ".env", "requirements.txt",
    "backend/database/__init__.py",
    "backend/database/config.py",
    "backend/database/models.py"
]

for file in files:
    if os.path.exists(file):
        print(f"✅ File: {file} exists")
    else:
        print(f"❌ File: {file} missing")

print("✅ Setup check complete!")