#!/usr/bin/env python3
"""
Cron runner for job scraper.
Usage: python run_scraper.py
Designed to be triggered every 2-3 hours via cron.
"""

import sys
import os
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from job_scraper import main, asyncio

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(0 if exit_code > 0 else 1)
