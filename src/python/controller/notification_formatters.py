"""Pure formatting functions for Discord and Telegram notification payloads.

These functions do no I/O — they produce ready-to-POST (url, headers, body)
triples that callers dispatch via fire-and-forget threads.
"""

import json
from datetime import UTC, datetime

EVENT_LABELS: dict[str, str] = {
    "download_complete": "Download Complete",
    "extraction_complete": "Extraction Complete",
    "extraction_failed": "Extraction Failed",
    "delete_complete": "Delete Complete",
    "test": "Test Notification",
}

DISCORD_COLORS: dict[str, int] = {
    "download_complete": 0x57F287,  # green
    "extraction_complete": 0x5865F2,  # blurple
    "extraction_failed": 0xED4245,  # red
    "delete_complete": 0x99AAB5,  # grey
    "test": 0x5865F2,  # blurple
}


def format_discord(
    event_type: str,
    filename: str,
    *,
    timestamp: str | None = None,
    pair_id: str | None = None,
    full_path: str | None = None,
) -> tuple[dict[str, str], bytes]:
    """Build a Discord webhook embed payload.

    Returns (headers, body_bytes). The caller provides the webhook URL.
    """
    label = EVENT_LABELS.get(event_type, event_type)
    color = DISCORD_COLORS.get(event_type, 0x99AAB5)
    ts = timestamp or datetime.now(UTC).isoformat()
    fields: list[dict[str, str | bool]] = []
    if pair_id:
        fields.append({"name": "Pair", "value": pair_id, "inline": True})
    if full_path:
        fields.append({"name": "Path", "value": f"`{full_path}`", "inline": False})
    embed: dict[str, object] = {
        "title": f"SeedSync — {label}",
        "description": f"`{filename}`",
        "color": color,
        "timestamp": ts,
    }
    if fields:
        embed["fields"] = fields
    payload = {"embeds": [embed]}
    headers = {"Content-Type": "application/json"}
    return headers, json.dumps(payload).encode("utf-8")


def _escape_markdown(text: str) -> str:
    """Escape characters that have meaning in Telegram Markdown v1.

    Inside inline code (backtick-delimited) only backticks need escaping,
    but since we use backticks to wrap user-provided text, we strip them
    from the value to prevent premature closing of the code span.
    """
    return text.replace("`", "'")


def format_telegram(
    bot_token: str,
    chat_id: str,
    event_type: str,
    filename: str,
    *,
    pair_id: str | None = None,
    full_path: str | None = None,
) -> tuple[str, dict[str, str], bytes]:
    """Build a Telegram sendMessage payload.

    Returns (api_url, headers, body_bytes).
    """
    label = EVENT_LABELS.get(event_type, event_type)
    safe_filename = _escape_markdown(filename)
    lines = ["*SeedSync*", f"Event: `{label}`", f"File: `{safe_filename}`"]
    if pair_id:
        lines.append(f"Pair: `{_escape_markdown(pair_id)}`")
    if full_path:
        lines.append(f"Path: `{_escape_markdown(full_path)}`")
    text = "\n".join(lines)
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    headers = {"Content-Type": "application/json"}
    return url, headers, json.dumps(payload).encode("utf-8")
