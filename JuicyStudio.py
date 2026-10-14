"""Launch Juicy Studio from a checkout or the packaged application."""
from pathlib import Path
import sys

if not getattr(sys, 'frozen', False):
    sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))

from JuicyCensorApp import main

if __name__ == '__main__':
    raise SystemExit(main())
