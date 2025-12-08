#!/usr/bin/env python3
"""Morning routine script - extracts OmniFocus tasks and calls API for morning brief.

This script is IDEMPOTENT - it can be safely run multiple times on the same day.
Each run will REPLACE (not append) the Tasks section in the daily note.
"""

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


def extract_omnifocus_data() -> dict:
    """Extract tasks and inbox info from OmniFocus using AppleScript.

    Returns:
        Dict with keys: tasks (list), inbox_count (int), inbox_titles (list)
    """
    logger.info("Extracting data from OmniFocus...")

    try:
        result = subprocess.run(
            ["osascript", str(OMNIFOCUS_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode != 0:
            logger.error(f"AppleScript error: {result.stderr}")
            return {"tasks": [], "inbox_count": 0, "inbox_titles": []}

        data = json.loads(result.stdout.strip())

        tasks = data.get("tasks", [])
        inbox_count = data.get("inbox_count", 0)
        inbox_titles = data.get("inbox_titles", [])

        logger.info(f"Extracted {len(tasks)} flagged tasks, {inbox_count} inbox items")
        return {
            "tasks": tasks,
            "inbox_count": inbox_count,
            "inbox_titles": inbox_titles,
        }

    except subprocess.TimeoutExpired:
        logger.error("OmniFocus extraction timed out")
        return {"tasks": [], "inbox_count": 0, "inbox_titles": []}
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse OmniFocus output: {e}")
        return {"tasks": [], "inbox_count": 0, "inbox_titles": []}
    except Exception as e:
        logger.error(f"Error extracting OmniFocus data: {e}")
        return {"tasks": [], "inbox_count": 0, "inbox_titles": []}


def call_morning_brief_api(data: dict) -> dict | None:
    """Call the morning brief API endpoint.

    Args:
        data: Dict with tasks, inbox_count, inbox_titles

    Returns:
        API response dict or None on failure
    """
    logger.info("Calling morning brief API...")

    url = f"{API_BASE_URL}/routines/morning-brief"
    payload = {
        "tasks": data["tasks"],
        "inbox_count": data["inbox_count"],
        "inbox_titles": data["inbox_titles"],
        "include_calendar": False,  # TODO: Add calendar integration
        "generate_summary": True,
    }

    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()

        result = response.json()
        logger.info(f"Morning brief API response: {result.get('message', 'success')}")
        return result

    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {e}")
        if hasattr(e, "response") and e.response is not None:
            logger.error(f"Response body: {e.response.text}")
        return None


def main():
    """Main entry point for morning routine.

    This is IDEMPOTENT - safe to run multiple times.
    """
    logger.info("=" * 50)
    logger.info("Starting morning routine (idempotent)")
    logger.info("=" * 50)

    # Step 1: Extract OmniFocus data
    data = extract_omnifocus_data()

    if not data["tasks"] and data["inbox_count"] == 0:
        logger.warning("No tasks or inbox items found in OmniFocus")
        # Continue anyway - API will still generate a brief

    # Step 2: Call morning brief API (replaces Tasks section)
    result = call_morning_brief_api(data)

    if result and result.get("success"):
        logger.info("Morning routine completed successfully")
        logger.info(f"Daily note updated: {result.get('path', 'unknown')}")
        logger.info(f"Summary: {result.get('message', '')}")
        return 0
    else:
        logger.error("Morning routine failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
