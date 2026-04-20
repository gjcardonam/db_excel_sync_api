import json
import os
import urllib.error
import urllib.request
from typing import Optional

from app.core.logger import get_logger

logger = get_logger(__name__)

CHAT_MESSAGE_URL = (
    "https://api.clickup.com/api/v3/workspaces/{workspace_id}"
    "/chat/channels/{channel_id}/messages"
)
CHAT_REPLY_URL = (
    "https://api.clickup.com/api/v3/workspaces/{workspace_id}"
    "/chat/messages/{message_id}/replies"
)


def _token() -> Optional[str]:
    return os.getenv("CLICKUP_API_TOKEN") or None


def _workspace_id() -> Optional[str]:
    return os.getenv("CLICKUP_WORKSPACE_ID") or None


def _post(url: str, content: str, log_ref: str) -> Optional[str]:
    token = _token()
    if not token:
        logger.warning("Skipping chat post — missing CLICKUP_API_TOKEN")
        return None
    body = json.dumps({
        "type": "message",
        "content": content,
        "content_format": "text/md",
    }).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
            return str(data.get("id")) if data.get("id") is not None else None
    except urllib.error.HTTPError as e:
        err_body = ""
        try:
            err_body = e.read().decode()[:500]
        except Exception:
            pass
        logger.warning(
            "ClickUp chat post failed | status=%s ref=%s body=%s",
            e.code, log_ref, err_body,
        )
        return None
    except Exception:
        logger.exception("ClickUp chat post raised | ref=%s", log_ref)
        return None


def post_message(channel_id: str, content: str) -> Optional[str]:
    workspace_id = _workspace_id()
    if not workspace_id or not channel_id:
        logger.warning(
            "Skipping chat post — missing config | has_workspace=%s channel=%s",
            bool(workspace_id), channel_id,
        )
        return None
    url = CHAT_MESSAGE_URL.format(workspace_id=workspace_id, channel_id=channel_id)
    return _post(url, content, log_ref=f"channel={channel_id}")


def post_reply(message_id: str, content: str) -> Optional[str]:
    workspace_id = _workspace_id()
    if not workspace_id or not message_id:
        logger.warning(
            "Skipping chat reply — missing config | has_workspace=%s message=%s",
            bool(workspace_id), message_id,
        )
        return None
    url = CHAT_REPLY_URL.format(workspace_id=workspace_id, message_id=message_id)
    return _post(url, content, log_ref=f"reply_to={message_id}")
