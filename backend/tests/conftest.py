
# Add backend/ to sys.path so tests can import app modules
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
