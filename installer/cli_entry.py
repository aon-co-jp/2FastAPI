# PyInstaller entry point for the .deb / .pkg command line build (no GUI toolkit needed).
import sys
from tofastapi.cli import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
