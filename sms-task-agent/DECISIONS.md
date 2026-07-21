# Next Build Phase — Decisions & Open Questions

This captures the design decisions discussed after the MVP was built, so the next
work session can pick up without re-deriving them. Nothing here is implemented yet —
it's the plan for phase 2.

---

## 1. Confidentiality tiers (screenshots may contain sensitive info)

The screenshot's journey has several exposure points. Ranked from least to most work:

| Point | Who sees it | How to close it |
|---|---|---|
| **MMS transport (Twilio + carrier)** | Mobile carrier + Twilio | **Cannot be closed while using SMS** — MMS is not end-to-end encrypted and transits the carrier. This is the hard limit of the SMS channel. |
| **Claude vision (Anthropic)** | Anthropic processes the image to read + route it | Request **Zero Data Retention** (not retained after the call), or move comprehension to a local model |
| **Storage at rest (Supabase)** | Provider holds it + the keys | **Envelope-encrypt** the image before upload so the provider only sees ciphertext |
| **Backend host (Vercel)** | Processes in memory in transit | Self-host for full control |
| **Dashboard** | Fetched to the browser | Already private (signed URLs / API-key gated) |

**Tiers:**
- **Tier 1** — keep SMS; encrypt at rest, Claude under ZDR, delete Twilio media immediately after download. Residual risk: carrier + Twilio saw the MMS in transit.
- **Tier 2** — drop SMS ingress for an encrypted HTTPS upload (iOS Shortcut / PWA); encrypt at rest; Claude under ZDR. Only Anthropic momentarily sees content, under no-retention.
- **Tier 3** — fully self-hosted, local vision model, nothing leaves your hardware. Weakest routing quality.

**Important correction:** Claude is NOT just doing OCR — it does vision **and** routing in one
call, so it receives the full image *plus* the accumulated routing-memory summaries of past
screenshots. Intelligent routing requires comprehension, and comprehension requires the
content. There is no config where Claude keeps full routing smarts yet never receives the
content. Tier 2 minimizes and de-persists that exposure; only Tier 3 eliminates it.

---

## 2. Multi-user via SMS (the deciding requirement)

Goal: after personal testing, let **team members contribute to lists via SMS** (zero-install,
anyone can text the number).

This is what SMS is good at, and the current build already supports most of it:
- Twilio webhook is built.
- `sender_phone` is already captured on every task.
- `ALLOWED_SENDERS` allowlist already exists in config.

**Tension:** SMS-for-the-team collides with the confidentiality goal. More contributors =
broader carrier/Twilio exposure, not narrower. Confidential + multi-contributor +
zero-install cannot all coexist over SMS.

**Resolving question — who sends confidential material?**
- **Only you** → use the **hybrid ingress** below. Team uses SMS; you use the encrypted
  upload for sensitive captures; confidential material never goes through the SMS door.
- **Teammates too** → SMS reintroduces the exposure for everyone. The whole team would need
  an encrypted channel (authenticated PWA with per-user logins, or a Signal group bot),
  which is more setup and loses the zero-install ease.

---

## 3. Recommended architecture: hybrid ingress

Accept **two front doors into the same pipeline** (`pipeline.process_incoming` is already
factored for this):

1. **Twilio SMS webhook** — for the team. Easy, zero-install, low friction.
2. **Encrypted HTTPS upload** (iOS Shortcut / PWA) — for your own confidential items.
   Full-resolution image (better OCR than carrier-compressed MMS), TLS in transit, no
   carrier/Twilio in the path.

**Rule:** confidential material goes through the upload, not the text.

---

## 4. Multi-user decisions to make

- **Attribution** — add a phone-number → team-member-name mapping so tasks show who
  submitted them. (`sender_phone` is captured; needs a small `contributors` table or map.)
- **Shared vs. per-person learning** — routing model is currently global. Keep it shared for
  team lists, but note: different people filing similar screenshots differently makes their
  corrections conflict and adds noise to the learned routing signal.
- **Dashboard access** — one shared API key for MVP; per-user logins later if teammates need
  to view/correct.
- **Cost** — scales linearly with team volume (more messages + more Claude calls).

---

## 5. Cost / model decisions

- **Switch the routing model from Opus to Sonnet or Haiku** before going live. Routing a
  screenshot to a list does not need Opus-tier reasoning. Haiku is ~5x cheaper. Change:
  `CLAUDE_MODEL` env var + possibly lower `effort`/thinking in `claude_client.py`. This is
  the single biggest lever on the ~$6–40/mo Claude API line.
- **Hosting alternatives considered:** Railway or Render instead of Vercel (native FastAPI,
  no serverless cold-start risk on the Twilio webhook, drop the `api/index.py` shim);
  Neon + Cloudflare R2 instead of Supabase (rewrite of `db.py` only). Keep Supabase/Vercel
  for now unless there's a reason to move.

---

## 6. Concrete phase-2 change list (when ready)

- [ ] Decide repo location (merge PR #1 into founder-legal-checklists, or move to standalone repo).
- [ ] Switch routing model to Haiku/Sonnet; tune effort.
- [ ] Add encrypted HTTPS upload endpoint alongside the Twilio webhook (hybrid ingress).
- [ ] Add envelope encryption of the screenshot before storage; decrypt via a backend
      endpoint for the dashboard (replaces the raw signed URL for encrypted images).
- [ ] Request/enable Zero Data Retention with Anthropic; delete Twilio media after download.
- [ ] Add contributor attribution (phone → name) and populate `ALLOWED_SENDERS` with the team.
- [ ] Build the iOS Shortcut for the encrypted upload (one-button / back-tap / Action button).
- [ ] Test end-to-end with live credentials (first-deploy debugging expected around the
      Supabase client calls and the Twilio-signature-behind-a-proxy logic).
