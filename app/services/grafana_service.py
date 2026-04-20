import json
import os
import urllib.error
import urllib.request
from typing import Optional

from app.core.logger import get_logger

logger = get_logger(__name__)


class GrafanaConfigMissing(RuntimeError):
    pass


class GrafanaAPIError(RuntimeError):
    def __init__(self, status: int, body: str):
        super().__init__(f"Grafana API error {status}: {body[:200]}")
        self.status = status
        self.body = body


def _env_prefix(company: str) -> str:
    return "GRAFANA_" + company.strip().upper().replace(" ", "_")


def get_config(company: str) -> tuple[str, str]:
    prefix = _env_prefix(company)
    url = os.getenv(f"{prefix}_URL")
    token = os.getenv(f"{prefix}_TOKEN")
    if not url or not token:
        raise GrafanaConfigMissing(
            f"Missing {prefix}_URL / {prefix}_TOKEN for company '{company}'"
        )
    return url.rstrip("/"), token


def _request(method: str, url: str, token: str, body: Optional[dict] = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
            parsed = json.loads(raw) if raw else {}
            return r.status, parsed if isinstance(parsed, dict) else {"_list": parsed}
    except urllib.error.HTTPError as e:
        err_raw = ""
        try:
            err_raw = e.read().decode()
        except Exception:
            pass
        raise GrafanaAPIError(e.code, err_raw) from None


def invite_viewer(company: str, email: str, send_email: bool = True) -> dict:
    """
    Creates an invite to the current org of the company's Grafana with Viewer role.

    Returns dict with: status (invited|already_in_org|failed), invite_id, invite_url,
    email_sent, raw_error (if failed).
    """
    base_url, token = get_config(company)
    url = f"{base_url}/api/org/invites"
    payload = {
        "loginOrEmail": email,
        "name": "",
        "role": "Viewer",
        "sendEmail": bool(send_email),
    }

    try:
        status, data = _request("POST", url, token, payload)
    except GrafanaAPIError as e:
        lower = e.body.lower()
        if "already" in lower or "exists" in lower:
            return {
                "status": "already_in_org",
                "invite_id": None,
                "invite_url": None,
                "email_sent": False,
                "raw_error": e.body[:500],
            }
        logger.warning(
            "Grafana invite failed | company=%s email=%s status=%s body=%s",
            company, email, e.status, e.body[:400],
        )
        return {
            "status": "failed",
            "invite_id": None,
            "invite_url": None,
            "email_sent": False,
            "raw_error": f"HTTP {e.status}: {e.body[:500]}",
        }

    invite_info = _find_invite_after_create(base_url, token, email)

    return {
        "status": "invited",
        "invite_id": invite_info.get("id") if invite_info else None,
        "invite_url": invite_info.get("url") if invite_info else None,
        "email_sent": bool(invite_info.get("emailSent")) if invite_info else send_email,
        "raw_error": None,
    }


def _find_invite_after_create(base_url: str, token: str, email: str) -> Optional[dict]:
    try:
        status, data = _request("GET", f"{base_url}/api/org/invites", token)
        items = data.get("_list") if isinstance(data, dict) and "_list" in data else data
        if not isinstance(items, list):
            return None
        email_lc = email.lower()
        for item in items:
            if str(item.get("email", "")).lower() == email_lc:
                return item
    except Exception:
        logger.exception("Failed to fetch invites list after create")
    return None
