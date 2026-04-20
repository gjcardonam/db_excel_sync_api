import json
import re
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.core.config import load_db_config
from app.core.database import create_pg_engine
from app.core.logger import get_logger
from app.services.companies import is_valid_company, normalize_company

logger = get_logger(__name__)

DDL_PATH = Path(__file__).resolve().parents[2] / "scripts" / "sql" / "001_access_grants.sql"

_engine: Optional[Engine] = None
_ddl_applied = False

GRANT_CMD_PATTERN = re.compile(
    r"^\s*/grant\s+(\S+@\S+)\s+(\S+)\s*$",
    re.IGNORECASE,
)


def _get_engine() -> Engine:
    global _engine
    if _engine is None:
        config = load_db_config("audit")
        _engine = create_pg_engine(config)
    return _engine


def _ensure_ddl(engine: Engine) -> None:
    global _ddl_applied
    if _ddl_applied:
        return
    ddl_sql = DDL_PATH.read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.execute(text(ddl_sql))
    _ddl_applied = True
    logger.info("Access grants schema ensured", extra={"ddl_path": str(DDL_PATH)})


def save_webhook_event(
    headers: dict,
    payload: Any,
    source_ip: Optional[str],
    event_name: Optional[str],
) -> Optional[int]:
    try:
        engine = _get_engine()
        _ensure_ddl(engine)
        with engine.begin() as conn:
            row = conn.execute(
                text(
                    "INSERT INTO clickup_webhook_events "
                    "(source_ip, event_name, headers, payload) "
                    "VALUES (:source_ip, :event_name, CAST(:headers AS jsonb), CAST(:payload AS jsonb)) "
                    "RETURNING id"
                ),
                {
                    "source_ip": source_ip,
                    "event_name": event_name,
                    "headers": json.dumps(headers, default=str, ensure_ascii=False),
                    "payload": json.dumps(payload, default=str, ensure_ascii=False),
                },
            ).first()
            return int(row[0]) if row else None
    except Exception:
        logger.exception("Failed to save clickup webhook event")
        return None


def parse_grant_command(message_text: str) -> Optional[dict]:
    if not message_text:
        return None
    m = GRANT_CMD_PATTERN.match(message_text)
    if not m:
        return None
    email = m.group(1).strip()
    company_raw = m.group(2).strip()
    return {
        "email": email,
        "company_raw": company_raw,
        "company": normalize_company(company_raw),
    }


def save_grant(
    source: str,
    user_email: str,
    company: str,
    source_ref: Optional[str] = None,
    granted_by_name: Optional[str] = None,
    granted_by_email: Optional[str] = None,
    granted_by_id: Optional[str] = None,
    raw_message: Optional[str] = None,
    notes: Optional[str] = None,
    simulated: bool = True,
    status: str = "simulated",
) -> int:
    engine = _get_engine()
    _ensure_ddl(engine)
    with engine.begin() as conn:
        row = conn.execute(
            text(
                "INSERT INTO access_grants "
                "(source, source_ref, granted_by_name, granted_by_email, granted_by_id, "
                " user_email, company, status, simulated, raw_message, notes) "
                "VALUES (:source, :source_ref, :gbn, :gbe, :gbi, "
                "        :user_email, :company, :status, :simulated, :raw_message, :notes) "
                "RETURNING id"
            ),
            {
                "source": source,
                "source_ref": source_ref,
                "gbn": granted_by_name,
                "gbe": granted_by_email,
                "gbi": granted_by_id,
                "user_email": user_email,
                "company": company,
                "status": status,
                "simulated": simulated,
                "raw_message": raw_message,
                "notes": notes,
            },
        ).first()
        return int(row[0])


def validate_company(name: str) -> bool:
    return is_valid_company(name)
