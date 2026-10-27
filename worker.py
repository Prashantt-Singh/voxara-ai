"""
Voxara AI - Root Worker Shim
Delegates execution to backend/worker.py regardless of whether invoked from root or backend.
"""

import os
import sys

# Ensure backend directory is in sys.path
backend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Change working directory to backend so relative config and database paths work seamlessly
os.chdir(backend_dir)

from worker import main

if __name__ == "__main__":
    main()
