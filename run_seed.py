# run_seed.py

import sys
import os

# Always ensure root is in PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Now safely import your seeding function
from src.scripts.dev_seed_data import seed_activity_and_splits

if __name__ == "__main__":
    seed_activity_and_splits()
