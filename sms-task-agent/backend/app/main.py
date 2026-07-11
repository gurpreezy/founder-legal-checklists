"""FastAPI app: Twilio webhook + dashboard API."""

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from . import db, pipeline
from .config import settings

app = FastAPI(title="SMS Screenshot Task Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # single-user MVP; the API key is the gate
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- auth helpers ----------

def require_dashboard_key(request: Request) -> None:
    key = request.headers.get("x-api-key", "")
    if not settings.dashboard_api_key or key != settings.dashboard_api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


async def validate_twilio(request: Request, form: dict) -> None:
    if settings.allowed_senders and form.get("From") not in settings.allowed_senders:
        raise HTTPException(status_code=403, detail="Sender not allowed")
    if not settings.validate_twilio_signature:
        return
    validator = RequestValidator(settings.twilio_auth_token)
    signature = request.headers.get("X-Twilio-Signature", "")
    url = str(request.url)
    # Behind a proxy (Vercel), reconstruct the public https URL Twilio signed.
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if forwarded_proto and forwarded_host:
        url = f"{forwarded_proto}://{forwarded_host}{request.url.path}"
        if request.url.query:
            url += f"?{request.url.query}"
    if not validator.validate(url, form, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")


# ---------- Twilio webhook ----------

@app.post("/webhooks/twilio/sms")
async def twilio_sms(request: Request) -> Response:
    form = dict((await request.form()).items())
    await validate_twilio(request, form)

    sms_text = (form.get("Body") or "").strip()
    media_url = form.get("MediaUrl0")
    sender = form.get("From", "")

    twiml = MessagingResponse()
    try:
        task = pipeline.process_incoming(sms_text, media_url, sender)
        reply = f"✅ “{task['title']}” → {task['assigned_list']}"
        if task.get("due_date"):
            reply += f" (due {task['due_date']})"
        if task["routing_source"] == "auto":
            confidence = task.get("confidence_score")
            if confidence is not None:
                reply += f" [auto, {round(confidence * 100)}% sure]"
    except Exception:
        reply = "⚠️ Couldn't process that one. Try again or check the dashboard."
    twiml.message(reply)
    return Response(content=str(twiml), media_type="application/xml")


# ---------- dashboard API ----------

class TaskUpdate(BaseModel):
    title: str | None = None
    assigned_list: str | None = None
    due_date: str | None = None
    priority: str | None = None
    status: str | None = None


@app.get("/api/tasks", dependencies=[Depends(require_dashboard_key)])
def get_tasks(list: str | None = None, status: str | None = None) -> dict:
    tasks = db.list_tasks(assigned_list=list, status=status)
    for task in tasks:
        task["screenshot_signed_url"] = db.signed_screenshot_url(task.get("screenshot_url"))
    return {"tasks": tasks, "lists": db.known_lists()}


@app.patch("/api/tasks/{task_id}", dependencies=[Depends(require_dashboard_key)])
def patch_task(task_id: str, update: TaskUpdate) -> dict:
    existing = db.get_task(task_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Task not found")

    fields = {k: v for k, v in update.model_dump().items() if v is not None}
    rerouted = (
        "assigned_list" in fields and fields["assigned_list"] != existing["assigned_list"]
    )
    if rerouted:
        fields["routing_source"] = "corrected"

    updated = db.update_task(task_id, fields)
    if rerouted and updated:
        pipeline.record_correction(existing, fields["assigned_list"])
    return updated or {}


@app.delete("/api/tasks/{task_id}", dependencies=[Depends(require_dashboard_key)])
def remove_task(task_id: str) -> dict:
    db.delete_task(task_id)
    return {"deleted": task_id}


@app.get("/api/insights", dependencies=[Depends(require_dashboard_key)])
def get_insights() -> dict:
    return db.routing_stats()


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}
