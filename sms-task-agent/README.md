# SMS Screenshot Task Agent

One-button screenshot + SMS → intelligent task creation with learning-based auto-routing.

Text a screenshot (optionally with a note like *"Batcave, due Friday"*) to a dedicated
Twilio number. Claude reads the image, parses your instructions, routes the task to the
right list, and it appears in your dashboard within seconds. Blank submissions get
smarter over time: every explicit instruction and every dashboard correction becomes a
training example the router learns from.

```
Flic button → iPhone screenshot → SMS/MMS → Twilio webhook
    → FastAPI backend → Claude (vision + routing) → Supabase (tasks + learning memory)
    → Web dashboard (view / filter / correct)
```

## What's here

| Path | What it is |
|---|---|
| `supabase/schema.sql` | Tasks table, `routing_examples` learning memory, storage bucket |
| `backend/` | FastAPI app: Twilio webhook, Claude integration, dashboard API (deploys to Vercel) |
| `dashboard/` | Static web dashboard (deploys to Netlify) |
| `.env.example` | Every environment variable the backend needs |

## How the learning works

1. **Explicit routing** — `"Investment Engine, due Friday"` files the task to that list and
   records an `explicit` training example (screenshot summary + keywords → list).
2. **Auto routing** — a blank submission makes Claude route it using the accumulated
   examples as few-shot context, with a confidence score. The decision is recorded as a
   weak `auto_confirmed` example.
3. **Corrections** — moving a task to a different list in the dashboard records a
   `correction` example, the strongest signal. Ground-truth examples are always fed to
   the router first.

The dashboard's **"What I've learned"** panel shows training-example counts per list and
live auto-routing accuracy (auto-routed tasks that you *didn't* have to correct).

## Setup

### 1. Supabase

1. Create a project at [supabase.com](https://supabase.com).
2. Open the SQL editor and run `supabase/schema.sql`.
3. Grab **Project URL** and the **service_role key** from Project Settings → API.

### 2. Backend (Vercel)

```bash
cd backend
npx vercel --prod
```

Set the environment variables from `.env.example` in the Vercel project settings
(`ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `TWILIO_ACCOUNT_SID`,
`TWILIO_AUTH_TOKEN`, `DASHBOARD_API_KEY`, optionally `ALLOWED_SENDERS` and
`USER_TIMEZONE`), then redeploy. Note the deployment URL.

Local development instead:

```bash
cd backend
pip install -r requirements.txt
cp ../.env.example .env   # fill in values, then:
env $(cat .env | xargs) uvicorn app.main:app --reload
```

### 3. Twilio

1. Buy an SMS/MMS-capable number (MMS requires a US/Canada number).
2. In Phone Numbers → your number → Messaging, set **"A message comes in"** to
   `https://<your-vercel-url>/webhooks/twilio/sms` (HTTP POST).
3. Optional but recommended: set `ALLOWED_SENDERS` to your phone number so only you can
   create tasks.

### 4. Dashboard (Netlify)

```bash
cd dashboard
npx netlify deploy --prod --dir .
```

Open the site, and in **Settings** enter your Vercel backend URL and the
`DASHBOARD_API_KEY` you chose. Works fine on iPhone Safari — add it to your home screen.

## Usage

| You send | What happens |
|---|---|
| Screenshot + `"Batcave, due Friday"` | Filed to **Batcave**, due date set to next Friday |
| Screenshot + `"Investment Engine, high priority"` | Filed with priority `high` |
| Screenshot alone | Auto-routed from learned patterns, with a confidence score |
| Text only, no image | The text itself becomes the task and is parsed/routed the same way |

Every message gets an SMS confirmation back:
`✅ "Review term sheet redlines" → Investment Engine (due 2026-07-17)`.

## Success metric

Blank submissions routed correctly 80%+ after 10–15 training examples — track it live in
the dashboard's "What I've learned" panel.

## Out of scope (MVP)

Mobile app wrapper, analytics/reporting, multi-user, recurring tasks.
