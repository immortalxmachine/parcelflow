#!/usr/bin/env python
"""Thin entrypoint so the pipeline can be run as `python pipeline.py ...`.

Adds ``src`` to the path and delegates to parcelflow.cli.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from parcelflow.cli import main  # noqa: E402

if __name__ == "__main__":
    main()
