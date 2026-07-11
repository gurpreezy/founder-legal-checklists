"""Supabase access layer. The backend uses the service-role key (bypasses RLS)."""

import mimetypes
import uuid
from functools import lru_cache

from supabase import Client, create_client

from .config import settings


@lru_cache(maxsize=1)
def get_client() -> Client:
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


# ---------- screenshots ----------

def upload_screenshot(image_bytes: bytes, content_type: str) -> str:
    """Store the screenshot in Supabase Storage and return its object path."""
    ext = mimetypes.guess_extension(content_type) or ".png"
    path = f"{uuid.uuid4()}{ext}"
    get_client().storage.from_(settings.screenshot_bucket).upload(
        path, image_bytes, {"content-type": content_type}
    )
    return path


def signed_screenshot_url(path: str, expires_in: int = 3600) -> str | None:
    if not path:
        return None
    res = get_client().storage.from_(settings.screenshot_bucket).create_signed_url(
        path, expires_in
    )
    return res.get("signedURL") or res.get("signedUrl")


# ---------- tasks ----------

def insert_task(task: dict) -> dict:
    res = get_client().table("tasks").insert(task).execute()
    return res.data[0]


def list_tasks(assigned_list: str | None = None, status: str | None = None) -> list[dict]:
    query = get_client().table("tasks").select("*").order("created_at", desc=True)
    if assigned_list:
        query = query.eq("assigned_list", assigned_list)
    if status:
        query = query.eq("status", status)
    return query.execute().data


def get_task(task_id: str) -> dict | None:
    res = get_client().table("tasks").select("*").eq("id", task_id).execute()
    return res.data[0] if res.data else None


def update_task(task_id: str, fields: dict) -> dict | None:
    res = get_client().table("tasks").update(fields).eq("id", task_id).execute()
    return res.data[0] if res.data else None


def delete_task(task_id: str) -> None:
    get_client().table("tasks").delete().eq("id", task_id).execute()


# ---------- routing examples (the learning memory) ----------

def insert_routing_example(example: dict) -> dict:
    res = get_client().table("routing_examples").insert(example).execute()
    return res.data[0]


def recent_routing_examples(limit: int = 40) -> list[dict]:
    """Most recent labeled examples, ground truth (explicit/correction) first."""
    client = get_client()
    ground_truth = (
        client.table("routing_examples")
        .select("summary, keywords, assigned_list, source")
        .in_("source", ["explicit", "correction"])
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data
    )
    remaining = limit - len(ground_truth)
    auto = []
    if remaining > 0:
        auto = (
            client.table("routing_examples")
            .select("summary, keywords, assigned_list, source")
            .eq("source", "auto_confirmed")
            .order("created_at", desc=True)
            .limit(remaining)
            .execute()
            .data
        )
    return ground_truth + auto


def known_lists() -> list[str]:
    """Distinct task lists seen so far, most used first."""
    rows = get_client().table("tasks").select("assigned_list").execute().data
    counts: dict[str, int] = {}
    for row in rows:
        name = row["assigned_list"]
        counts[name] = counts.get(name, 0) + 1
    return [name for name, _ in sorted(counts.items(), key=lambda kv: -kv[1])]


def routing_stats() -> dict:
    """Aggregate stats for the dashboard's 'what the agent learned' view."""
    client = get_client()
    examples = (
        client.table("routing_examples").select("assigned_list, source").execute().data
    )
    tasks = client.table("tasks").select("routing_source").execute().data

    by_list: dict[str, dict] = {}
    for ex in examples:
        bucket = by_list.setdefault(
            ex["assigned_list"], {"explicit": 0, "correction": 0, "auto_confirmed": 0}
        )
        bucket[ex["source"]] += 1

    auto_routed = sum(1 for t in tasks if t["routing_source"] in ("auto", "corrected"))
    corrected = sum(1 for t in tasks if t["routing_source"] == "corrected")
    accuracy = None
    if auto_routed:
        accuracy = round((auto_routed - corrected) / auto_routed, 3)

    return {
        "training_examples": len(examples),
        "examples_by_list": by_list,
        "auto_routed_tasks": auto_routed,
        "corrections": corrected,
        "auto_routing_accuracy": accuracy,
    }
