
from collections import deque
from pathlib import Path


# Project ke logs folder ka path
LOG_FILE = (
    Path(__file__).resolve().parent.parent
    / "logs"
    / "fastapi.log"
)


def get_log_evidence():

    # File nahi mili toh clearly batao
    if not LOG_FILE.is_file():
        return {
            "status": "unavailable",
            "reason": "FastAPI log file not found",
            "entries": []
        }

    # Sirf latest 500 lines read karo
    with LOG_FILE.open(
        "r",
        encoding="utf-8",
        errors="replace"
    ) as file:
        recent_lines = list(deque(file, maxlen=500))

    # Relevant error indicators
    keywords = (
        "error",
        "exception",
        "traceback",
        "status=500",
        "status=502",
        "status=503",
        "status=504"
    )

    matching_logs = []

    for line in recent_lines:
        if any(word in line.lower() for word in keywords):
            matching_logs.append(line.strip()[:400])

    # AI ko unlimited logs nahi bhejenge
    return {
        "status": "available",
        "source": "Recent FastAPI application logs",
        "entries": matching_logs[-8:],
        "note": "Recent logs; not necessarily from incident time"
    }

