"""End-to-end intake pipeline: media -> Claude extraction -> Supabase task + learning."""

import requests

from . import claude_client, db
from .config import settings


def download_twilio_media(media_url: str) -> tuple[bytes, str]:
    """Twilio media URLs require HTTP basic auth with the account credentials."""
    resp = requests.get(
        media_url,
        auth=(settings.twilio_account_sid, settings.twilio_auth_token),
        timeout=30,
        allow_redirects=True,
    )
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
    return resp.content, content_type


def process_incoming(sms_text: str, media_url: str | None, sender: str) -> dict:
    """Handle one inbound SMS/MMS. Returns the created task row."""
    lists = db.known_lists()
    examples = db.recent_routing_examples()

    screenshot_path = None
    if media_url:
        image_bytes, content_type = download_twilio_media(media_url)
        screenshot_path = db.upload_screenshot(image_bytes, content_type)
        extraction = claude_client.extract_task(
            image_bytes, content_type, sms_text, lists, examples
        )
    else:
        extraction = claude_client.parse_text_only(sms_text, lists, examples)

    routing_source = "explicit" if extraction.explicit_list else "auto"
    task = db.insert_task(
        {
            "screenshot_url": screenshot_path,
            "extracted_text": extraction.extracted_text,
            "title": extraction.title,
            "assigned_list": extraction.suggested_list,
            "due_date": extraction.due_date,
            "priority": extraction.priority,
            "routing_source": routing_source,
            "confidence_score": extraction.confidence,
            "sms_body": sms_text or None,
            "sender_phone": sender,
        }
    )

    # Feed the learning memory. Explicit instructions are ground truth; the
    # agent's own decisions are recorded as weaker 'auto_confirmed' examples
    # (they get overwritten by a 'correction' example if the user reroutes it).
    db.insert_routing_example(
        {
            "task_id": task["id"],
            "summary": extraction.summary,
            "keywords": extraction.keywords,
            "assigned_list": extraction.suggested_list,
            "source": "explicit" if routing_source == "explicit" else "auto_confirmed",
        }
    )
    return task


def record_correction(task: dict, new_list: str) -> None:
    """Called when the user reroutes a task in the dashboard: this is the
    strongest learning signal the system gets."""
    db.insert_routing_example(
        {
            "task_id": task["id"],
            "summary": task.get("title") or (task.get("extracted_text") or "")[:120],
            "keywords": [],
            "assigned_list": new_list,
            "source": "correction",
        }
    )
