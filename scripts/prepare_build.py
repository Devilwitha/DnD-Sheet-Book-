"""
Prepare build-time resources for packaging the APK.

This script will create the SQLite source database at
`utils/data/dnd.db` by calling the repository's build_database.create_database()
function. Run this on the build host (your machine or CI) before invoking
`buildozer android debug` / `buildozer android release` so the DB file is
included in the APK assets.

Usage:
    python scripts/prepare_build.py
"""
import os
import sys

repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Ensure project root is on sys.path so imports work
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

try:
    from utils import build_database
except Exception as e:
    print(f"Error importing build_database: {e}")
    raise

print("Creating source database for packaging: utils/data/dnd.db")
try:
    build_database.create_database()
    print("Database created successfully.")
except Exception as e:
    print(f"Failed to create database: {e}")
    raise
