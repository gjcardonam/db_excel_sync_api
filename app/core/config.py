import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def load_db_config(company: str) -> dict:
    prefix = company.upper().replace(" ", "_")
    required = ["HOST", "DATABASE", "USER", "PASSWORD", "SCHEMA"]

    missing = [k for k in required if not os.getenv(f"{prefix}_{k}")]
    if missing:
        raise RuntimeError(
            f"Missing DB env vars for {prefix}: {', '.join(missing)}. "
            f"Define them in your .env"
        )

    return {
        "host": os.getenv(f"{prefix}_HOST"),
        "database": os.getenv(f"{prefix}_DATABASE"),
        "user": os.getenv(f"{prefix}_USER"),
        "password": os.getenv(f"{prefix}_PASSWORD"),
        "port": os.getenv(f"{prefix}_PORT"),
        "schema": os.getenv(f"{prefix}_SCHEMA")
    }
