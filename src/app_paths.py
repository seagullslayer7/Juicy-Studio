"""Application data lives beside the executable or above the source folder."""
from pathlib import Path
import sys

APP_ROOT = (Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False)
            else Path(__file__).resolve().parent.parent)
