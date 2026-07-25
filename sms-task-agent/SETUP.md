# Setup — What You Need To Do

Stack decision: **Supabase** (database + screenshot storage), Vercel (backend), Netlify (dashboard), Twilio (SMS).

---

## Important: what actually blocks the build

**Nothing here blocks writing the phase-2 code.** The interpretive prompt, forced why-on-edit,
schema changes, and dashboard work can all be built without your credentials.

What this setup unlocks is **deploying and testing**. Recommended sequencing:

1. **Now:** Part A (create accounts, gather credentials) + Part C (answer the open decisions).
2. **After the phase-2 build:** Part B (run the SQL, deploy, configure).

Why wait on the SQL: phase 2 adds columns (edit `reason`, interpretive fields like
needs-response and stated-vs-inferred deadline). Running `schema.sql` now means running a
migration later. Running it once, after, is cleaner.

---

## Part A — Do now (~30 min, no rush)

### A1. Supabase
1. Create a project at https://supabase.com (free tier is fine).
2. Choose a region near you.
3. Save the database password somewhere safe.
4. Go to **Project Settings → API** and copy:
   - **Project URL** → `SUPABASE_URL`
   - **`service_role` key** (NOT the `anon` key) → `SUPABASE_SERVICE_ROLE_KEY`

> ⚠️ The `service_role` key bypasses row-level security. Treat it like a root password —
> backend only, never in the dashboard or any client-side code.

**Do NOT run `supabase/schema.sql` yet** — that's Part B, after the phase-2 schema is final.

### A2. Anthropic API key
1. Get an API key from https://platform.claude.com → `ANTHROPIC_API_KEY`.
2. Set a **monthly spend limit** on the account so a bug can't run up a bill.
3. *(If confidentiality matters)* Contact Anthropic about **Zero Data Retention** for the
   account — see `DECISIONS.md` §1. Screenshots are sent to the API for interpretation.

### A3. Twilio
1. Create an account at https://twilio.com.
2. Buy a phone number — **must be US or Canada and MMS-capable** (MMS is required to
   receive images; many international numbers are SMS-only).
3. From the Console dashboard, copy:
   - **Account SID** → `TWILIO_ACCOUNT_SID`
   - **Auth Token** → `TWILIO_AUTH_TOKEN`
4. Note the phone number itself — you'll text screenshots to it.

### A4. Accounts for hosting
- **Vercel** (https://vercel.com) — sign in with GitHub. Note: the free Hobby tier is
  non-commercial; if this becomes a team/business tool, that's a paid tier (~$20/mo) or a
  reason to move to Railway/Render (see `DECISIONS.md` §5).
- **Netlify** (https://netlify.com) — sign in with GitHub. Free tier is fine.

### A5. Generate a dashboard API key
Any long random string — this gates the dashboard API. E.g.:
```
openssl rand -hex 32
```
Save it as `DASHBOARD_API_KEY`.

### A6. Your phone number
In E.164 format (e.g. `+15551234567`) → `ALLOWED_SENDERS`. Only listed numbers can create
tasks. Team members' numbers get added here later.

---

## Part B — After the phase-2 build (~1 hr)

### B1. Run the database schema
In Supabase → **SQL Editor**, paste and run the final `supabase/schema.sql`. This creates the
`tasks` and `routing_examples` tables and the private `screenshots` storage bucket.

### B2. Deploy the backend to Vercel
From `sms-task-agent/backend/`:
```
npx vercel --prod
```
Then in the Vercel project settings, add every environment variable from `.env.example`:
`ANTHROPIC_API_KEY`, `CLAUDE_MODEL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
`TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `ALLOWED_SENDERS`, `DASHBOARD_API_KEY`,
`USER_TIMEZONE`. **Redeploy after adding them** (env vars aren't picked up retroactively).

Note the deployment URL.

### B3. Point Twilio at the webhook
Twilio Console → **Phone Numbers → your number → Messaging**.
Set **"A message comes in"** to:
```
https://<your-vercel-url>/webhooks/twilio/sms
```
Method: **HTTP POST**. Save.

### B4. Deploy the dashboard to Netlify
From `sms-task-agent/dashboard/`:
```
npx netlify deploy --prod --dir .
```
Open the site → **Settings** → enter your Vercel backend URL and `DASHBOARD_API_KEY`.
On iPhone, add it to your home screen so it behaves like an app.

### B5. Test
Text a screenshot to the Twilio number with something like `Batcave, due Friday`.
Expect an SMS confirmation within ~30s and the task in the dashboard.

**Expect some first-deploy debugging** — the code has never run against live services.
Most likely spots: the Supabase client call shapes, and Twilio signature validation behind
Vercel's proxy. Vercel's function logs are the place to look.

### B6. (Optional) Flic button
Configure the button to trigger the screenshot + send. On iOS an Apple Shortcut bound to
back-tap or the Action button works too.

---

## Part C — Decisions I still need from you

| # | Decision | Options / recommendation |
|---|---|---|
| C1 | **Repo location** | Merge draft PR #1 into `founder-legal-checklists`, or create an empty repo at github.com/new and tell me the name (I can't create repos — 403). |
| C2 | **Routing model** | Recommend **Haiku** (~5x cheaper) or **Sonnet**. Interpretive reading is more demanding than plain routing, so Sonnet is the safer default; Haiku if cost matters more. Biggest lever on the monthly bill. |
| C3 | **Your timezone** | For resolving "Friday" / "tomorrow". Default currently `America/Los_Angeles`. |
| C4 | **Starting task lists** | Give me 3–6 list names + a one-line description of what belongs in each (e.g. "Investment Engine — fund/LP/deal items"). Seeds the router so it isn't cold on day one. |
| C5 | **Why-on-edit scope** | Recorded as "every edit asks why" per your preference. Confirm, or narrow to signal-bearing fields only (list, due date, priority, interpreted action) — see `DECISIONS.md` §7b. |

C1 is the only one needed before I start; C2–C5 are needed before the build is finished.

---

## Cost expectations

| Service | Monthly |
|---|---|
| Twilio | ~$2–6 (number + per-message) |
| Supabase | $0 (free tier) |
| Netlify | $0 |
| Vercel | $0 (Hobby; ~$20 if commercial use) |
| Claude API | ~$6–40 — depends on volume and model choice (C2) |
| **Total** | **~$8–50/mo**, dominated by Claude API |
