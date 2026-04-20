import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Request
from sqlalchemy import text

from app.core.logger import get_logger
from app.services.access_grant_service import (
    _get_engine,
    parse_grant_command,
    save_grant,
    save_webhook_event,
    validate_company,
)
from app.services.clickup_chat_service import (
    post_message as clickup_post_message,
    post_reply as clickup_post_reply,
)
from app.services.companies import VALID_COMPANIES
from app.services.grafana_service import (
    GrafanaConfigMissing,
    invite_viewer as grafana_invite_viewer,
)

router = APIRouter()
logger = get_logger(__name__)

DUMP_DIR = Path("logs/webhooks/clickup")

MESSAGE_TEXT_KEYS = ("text_content", "text", "message", "content", "body", "messageText", "message_text")
AUTHOR_ID_KEYS = ("userid", "user_id", "userId", "id")
MESSAGE_ID_KEYS = ("object_id", "id", "messageId", "message_id")
CHANNEL_ID_KEYS = ("parent", "channel_id", "channelId", "root_parent_id")


def _deep_find_first(obj: Any, keys: tuple) -> Optional[Any]:
    """Breadth-first search for the first non-empty value at any of the given keys."""
    if not isinstance(obj, dict):
        return None
    queue = [obj]
    seen_ids = set()
    while queue:
        current = queue.pop(0)
        oid = id(current)
        if oid in seen_ids:
            continue
        seen_ids.add(oid)
        for k in keys:
            if k in current and current[k] not in (None, "", {}, []):
                return current[k]
        for v in current.values():
            if isinstance(v, dict):
                queue.append(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        queue.append(item)
    return None


def _find_message_text(payload: Any) -> Optional[str]:
    if isinstance(payload, str):
        return payload
    value = _deep_find_first(payload, MESSAGE_TEXT_KEYS)
    if isinstance(value, str):
        return value.rstrip("\n\r\t ")
    return None


def _find_author_id(payload: Any) -> Optional[str]:
    value = _deep_find_first(payload, AUTHOR_ID_KEYS)
    return str(value) if value not in (None, "") else None


def _find_message_id(payload: Any) -> Optional[str]:
    value = _deep_find_first(payload, MESSAGE_ID_KEYS)
    return str(value) if value not in (None, "") else None


def _find_channel_id(payload: Any) -> Optional[str]:
    value = _deep_find_first(payload, CHANNEL_ID_KEYS)
    return str(value) if value not in (None, "") else None


def _is_grant_command(text_value: Optional[str]) -> bool:
    if not text_value:
        return False
    return text_value.lstrip().lower().startswith("/grant")


BOT_PREFIX = "🤖 **access-bot** · "


def _reply(message_id: Optional[str], channel_id: Optional[str], content: str) -> None:
    full = BOT_PREFIX + content
    try:
        if message_id:
            if clickup_post_reply(message_id, full):
                return
        if channel_id:
            clickup_post_message(channel_id, full)
    except Exception:
        logger.exception("Failed to post chat reply")


def _companies_hint(limit: int = 10) -> str:
    sample = sorted(VALID_COMPANIES)[:limit]
    return ", ".join(sample) + (", ..." if len(VALID_COMPANIES) > limit else "")


def _dump_to_file(record: dict) -> None:
    try:
        DUMP_DIR.mkdir(parents=True, exist_ok=True)
        ts = record["received_at"].replace(":", "-").replace(".", "-")
        (DUMP_DIR / f"{ts}.json").write_text(
            json.dumps(record, indent=2, default=str, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        logger.exception("Failed to dump clickup webhook to disk")


@router.post("/webhooks/clickup/grafana-access")
async def clickup_grafana_access_webhook(request: Request):
    source_ip = request.client.host if request.client else None
    headers = dict(request.headers)

    try:
        payload = await request.json()
    except Exception:
        raw = await request.body()
        payload = {"_raw": raw.decode("utf-8", errors="replace")}

    event_name = (
        headers.get("x-clickup-event")
        or headers.get("X-Clickup-Event")
        or (payload.get("event") if isinstance(payload, dict) else None)
    )
    received_at = datetime.now(timezone.utc).isoformat()

    _dump_to_file({
        "received_at": received_at,
        "source_ip": source_ip,
        "event_name": event_name,
        "headers": headers,
        "payload": payload,
    })

    event_id = save_webhook_event(headers, payload, source_ip, event_name)

    message_text = _find_message_text(payload)
    author_id = _find_author_id(payload)
    message_id = _find_message_id(payload)
    channel_id = _find_channel_id(payload)

    logger.info(
        "ClickUp webhook received | ip=%s event=%s event_id=%s message_text=%r author_id=%s channel_id=%s",
        source_ip,
        event_name,
        event_id,
        message_text,
        author_id,
        channel_id,
    )

    if not message_text:
        return {
            "status": "received",
            "event_id": event_id,
            "parsed": False,
            "reason": "no_message_text_found",
        }

    cmd = parse_grant_command(message_text)
    if not cmd:
        if _is_grant_command(message_text):
            _reply(
                message_id,
                channel_id,
                "✗ Invalid format. Use: `/grant <email> <company>`",
            )
        return {
            "status": "received",
            "event_id": event_id,
            "parsed": False,
            "reason": "not_a_grant_command",
            "message_text": message_text,
        }

    if not validate_company(cmd["company_raw"]):
        logger.warning(
            "Grant command with unknown company | company=%s",
            cmd["company_raw"],
        )
        _reply(
            message_id,
            channel_id,
            f"✗ Unknown company `{cmd['company_raw']}`. Valid: {_companies_hint()}",
        )
        return {
            "status": "received",
            "event_id": event_id,
            "parsed": True,
            "grant_created": False,
            "reason": "unknown_company",
            "company": cmd["company_raw"],
        }

    try:
        grafana_result = grafana_invite_viewer(cmd["company"], cmd["email"])
    except GrafanaConfigMissing:
        logger.warning("Grafana not configured for %s", cmd["company"])
        _reply(
            message_id,
            channel_id,
            f"✗ Grafana for `{cmd['company']}` is not configured yet. "
            f"Set `GRAFANA_{cmd['company'].upper()}_URL` and `_TOKEN` in .env.",
        )
        try:
            save_grant(
                source="clickup_chat",
                source_ref=message_id,
                granted_by_id=author_id,
                user_email=cmd["email"],
                company=cmd["company"],
                raw_message=message_text,
                notes=f"channel_id={channel_id}; grafana config missing",
                simulated=False,
                status="config_missing",
            )
        except Exception:
            logger.exception("Also failed to record config_missing grant")
        return {
            "status": "received",
            "event_id": event_id,
            "parsed": True,
            "grant_created": False,
            "reason": "grafana_config_missing",
            "company": cmd["company"],
        }
    except Exception as e:
        logger.exception("Unexpected error calling Grafana")
        _reply(message_id, channel_id, "✗ Internal error talking to Grafana. Try again in a moment.")
        return {
            "status": "received",
            "event_id": event_id,
            "parsed": True,
            "grant_created": False,
            "reason": "grafana_unexpected_error",
            "error": str(e),
        }

    notes_parts = []
    if channel_id:
        notes_parts.append(f"channel_id={channel_id}")
    if grafana_result.get("invite_url"):
        notes_parts.append(f"invite_url={grafana_result['invite_url']}")
    if grafana_result.get("email_sent") is not None:
        notes_parts.append(f"email_sent={grafana_result['email_sent']}")
    if grafana_result.get("raw_error"):
        notes_parts.append(f"error={grafana_result['raw_error'][:200]}")

    try:
        grant_id = save_grant(
            source="clickup_chat",
            source_ref=message_id,
            granted_by_id=author_id,
            user_email=cmd["email"],
            company=cmd["company"],
            raw_message=message_text,
            notes="; ".join(notes_parts) if notes_parts else None,
            simulated=False,
            status=grafana_result["status"],
        )
    except Exception as e:
        logger.exception("Failed to record access grant")
        _reply(message_id, channel_id, "✗ Grafana call done but failed to record audit row. Check logs.")
        return {
            "status": "received",
            "event_id": event_id,
            "parsed": True,
            "grant_created": False,
            "reason": "persistence_error",
            "error": str(e),
        }

    if event_id is not None:
        try:
            engine = _get_engine()
            with engine.begin() as conn:
                conn.execute(
                    text("UPDATE clickup_webhook_events SET processed = true WHERE id = :id"),
                    {"id": event_id},
                )
        except Exception:
            logger.exception("Failed to mark webhook event as processed")

    logger.info(
        "Access grant recorded | grant_id=%s user=%s company=%s grafana_status=%s",
        grant_id, cmd["email"], cmd["company"], grafana_result["status"],
    )

    if grafana_result["status"] == "invited":
        email_note = "" if grafana_result.get("email_sent") else " (email not sent — check SMTP)"
        _reply(
            message_id,
            channel_id,
            f"✓ Invite sent to `{cmd['email']}` for `{cmd['company']}` as Viewer"
            f"{email_note} (grant #{grant_id})",
        )
    elif grafana_result["status"] == "already_in_org":
        _reply(
            message_id,
            channel_id,
            f"ℹ `{cmd['email']}` already has access to `{cmd['company']}` (grant #{grant_id})",
        )
    else:  # failed
        err_short = (grafana_result.get("raw_error") or "unknown")[:200]
        _reply(
            message_id,
            channel_id,
            f"✗ Grafana error for `{cmd['company']}`: {err_short}",
        )

    return {
        "status": "received",
        "event_id": event_id,
        "parsed": True,
        "grant_created": True,
        "grant_id": grant_id,
        "grafana_status": grafana_result["status"],
        "user_email": cmd["email"],
        "company": cmd["company"],
    }


@router.get("/webhooks/clickup/grants/recent")
def list_recent_grants(limit: int = 20):
    try:
        engine = _get_engine()
        with engine.begin() as conn:
            rows = conn.execute(
                text(
                    "SELECT id, created_at, source, granted_by_name, user_email, "
                    "       company, status, simulated "
                    "FROM access_grants ORDER BY created_at DESC LIMIT :limit"
                ),
                {"limit": limit},
            ).mappings().all()
        return {"count": len(rows), "grants": [dict(r) for r in rows]}
    except Exception as e:
        logger.exception("Failed to list recent grants")
        return {"count": 0, "grants": [], "error": str(e)}
