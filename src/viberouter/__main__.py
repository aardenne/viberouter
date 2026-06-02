"""VibeRouter CLI entry point."""

import sys
import os
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

from viberouter.cli import app

if __name__ == "__main__":
    app()
