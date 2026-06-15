import os
import json
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

def load_db_config(company: str) -> dict:
    prefix = company.upper().replace(" ", "_")
    required = ["HOST", "DATABASE", "USER", "PASSWORD", "SCHEMA"]

    missing = [k for k in required if not os.getenv(f"{prefix}_{k}")]
    if missing:
        logger.error("Missing DB env vars for %s: %s", prefix, ", ".join(missing))
        raise RuntimeError(
            f"Database configuration incomplete for company: {company}"
        )

    return {
        "host": os.getenv(f"{prefix}_HOST"),
        "database": os.getenv(f"{prefix}_DATABASE"),
        "user": os.getenv(f"{prefix}_USER"),
        "password": os.getenv(f"{prefix}_PASSWORD"),
        "port": os.getenv(f"{prefix}_PORT") or "5432",
        "schema": os.getenv(f"{prefix}_SCHEMA"),
    }
