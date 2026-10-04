"""
Root entrypoint for Streamlit Community Cloud and local execution.
Forwards execution to app/Home.py.
"""
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import runpy

runpy.run_path(str(root_dir / "app" / "Home.py"), run_name="__main__")
