#!/usr/bin/env python3
"""Morning routine script - extracts OmniFocus tasks and calls API for morning brief."""

import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import requests

# Configure logging
LOG_DIR = Path.home() / ".local" / "log" / "morning-routine"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "morning_routine.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

# Configuration
API_BASE_URL = os.environ.get(
    "PRODUCTIVITY_API_URL",
    "https://el5c54bhs2.execute-api.us-east-1.amazonaws.com",
)
SCRIPT_DIR = Path(__file__).parent
OMNIFOCUS_SCRIPT = SCRIPT_DIR / "extract_omnifocus.applescript"


def extract_omnifocus_tasks() -> list[dict]:
    """Extract tasks from OmniFocus using AppleScript."""
    logger.info("Extracting tasks from OmniFocus...")

    try:
        result = subprocess.run(
            ["osascript", str(OMNIFOCUS_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            logger.error(f"AppleScript error: {result.stderr}")
            return []

        tasks = json.loads(result.stdout.strip())
        logger.info(f"Extracted {len(tasks)} tasks from OmniFocus")
        return tasks

    except subprocess.TimeoutExpired:
        logger.error("OmniFocus extraction timed out")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse OmniFocus output: {e}")
        return []
    except Exception as e:
        logger.error(f"Error extracting OmniFocus tasks: {e}")
        return []


def call_morning_brief_api(tasks: list[dict]) -> dict | None:
    """Call the morning brief API endpoint."""
    logger.info("Calling morning brief API...")

    url = f"{API_BASE_URL}/routines/morning-brief"
    payload = {
        "tasks": tasks,
        "include_calendar": False,  # TODO: Add calendar integration
        "generate_summary": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        response.raise_for_status()

        result = response.json()
        logger.info(f"Morning brief API response: {result.get('message', 'success')}")
        return result

    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        return None


def main():
    """Main entry point for morning routine."""
    logger.info("=" * 50)
    logger.info("Starting morning routine")
    logger.info("=" * 50)

    # Step 1: Extract OmniFocus tasks
    tasks = extract_omnifocus_tasks()

    if not tasks:
        logger.warning("No tasks extracted from OmniFocus")
        # Continue anyway - API will still generate a brief

    # Step 2: Call morning brief API
    result = call_morning_brief_api(tasks)

    if result and result.get("success"):
        logger.info("Morning routine completed successfully")
        logger.info(f"Daily note updated: {result.get('path', 'unknown')}")
        return 0
    else:
        logger.error("Morning routine failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
