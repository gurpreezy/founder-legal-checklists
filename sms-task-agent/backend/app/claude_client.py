"""Claude vision + instruction parsing + learned routing, in a single API call.

The model receives the screenshot, the raw SMS text, the lists seen so far, and
the labeled routing examples accumulated in Supabase (few-shot memory). It
returns a structured extraction including the routing decision and confidence.
"""

import base64
from datetime import datetime
from typing import List, Literal, Optional
from zoneinfo import ZoneInfo

import anthropic
from pydantic import BaseModel, Field

from .config import settings

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key)


class TaskExtraction(BaseModel):
    title: str = Field(description="Short actionable task title, under 80 chars")
    extracted_text: str = Field(description="All meaningful text read from the screenshot")
    summary: str = Field(description="One-sentence description of what the screenshot shows")
    keywords: List[str] = Field(description="3-8 lowercase keywords describing the content")
    explicit_list: Optional[str] = Field(
        description="Task list explicitly named in the SMS text, or null if none was named"
    )
    suggested_list: str = Field(
        description="The task list this belongs in (the explicit list if given, otherwise your best routing decision)"
    )
    confidence: float = Field(description="Routing confidence from 0 to 1")
    due_date: Optional[str] = Field(
        description="Due date as YYYY-MM-DD if one was stated or implied in the SMS, else null"
    )
    priority: Optional[Literal["low", "medium", "high"]] = Field(
        description="Priority if stated or clearly implied, else null"
    )


SYSTEM_PROMPT = """You are the routing brain of a personal task-capture agent. The user \
photographs things on their screen and texts the screenshot to you, sometimes with a short \
note like "Batcave, due Friday" naming a task list and metadata, and sometimes with no text \
at all.

Your job on every message:
1. Read the screenshot and extract its meaningful text and intent.
2. Parse the SMS text for an explicit task list name, due date, and priority. List names \
are personal and can be arbitrary ("Batcave", "Investment Engine") — treat the first \
non-date, non-priority phrase as the list name when the structure suggests one.
3. Decide which task list the task belongs in. If the SMS names a list, use it verbatim. \
If not, route it yourself: the routing examples provided show which kinds of screenshots \
the user has filed to which lists before — match against those patterns first, and prefer \
an existing list over inventing a new one. If nothing matches and no lists exist yet, use \
"Inbox".
4. Report an honest confidence: near 1.0 for explicit lists, lower when guessing from few \
or conflicting examples.

Resolve relative dates ("Friday", "tomorrow", "next week") against the current date you \
are given, choosing the next future occurrence."""


def _today() -> str:
    now = datetime.now(ZoneInfo(settings.timezone))
    return now.strftime("%A, %Y-%m-%d")


def _format_examples(examples: list[dict]) -> str:
    if not examples:
        return "No routing examples yet — the user is just getting started."
    lines = []
    for ex in examples:
        kw = ", ".join(ex.get("keywords") or [])
        lines.append(
            f'- [{ex["source"]}] "{ex["summary"]}" (keywords: {kw}) -> {ex["assigned_list"]}'
        )
    return "\n".join(lines)


def extract_task(
    image_bytes: bytes,
    image_media_type: str,
    sms_text: str,
    lists: list[str],
    routing_examples: list[dict],
) -> TaskExtraction:
    image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

    context = f"""Current date: {_today()}

SMS text from the user (may be empty): {sms_text or "(none)"}

Task lists the user already has, most used first: {", ".join(lists) or "(none yet)"}

Routing examples learned so far (source 'explicit' and 'correction' are ground truth,
'auto_confirmed' are the agent's own past decisions):
{_format_examples(routing_examples)}

Extract the task from the screenshot and route it."""

    response = _client.messages.parse(
        model=settings.claude_model,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": image_media_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": context},
                ],
            }
        ],
        output_format=TaskExtraction,
    )
    return response.parsed_output


def parse_text_only(sms_text: str, lists: list[str], routing_examples: list[dict]) -> TaskExtraction:
    """Fallback for SMS with no image: treat the text itself as the task."""
    context = f"""Current date: {_today()}

The user sent a text-only task (no screenshot): {sms_text}

Task lists the user already has, most used first: {", ".join(lists) or "(none yet)"}

Routing examples learned so far:
{_format_examples(routing_examples)}

Treat the message text as the task content itself; still parse any list name, due date,
and priority out of it, and route what remains."""

    response = _client.messages.parse(
        model=settings.claude_model,
        max_tokens=16000,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": context}],
        output_format=TaskExtraction,
    )
    return response.parsed_output
