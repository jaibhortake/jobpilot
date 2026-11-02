# Decision: Apply Assist (autofill job applications)
Date: 2026-11-02

## Problem
Applying is the most boring part: the same details and answers are typed into every company site by hand.

## Existing mechanisms
1. Job record (url, description, company): `Job` in src/db/models.py (source read).
2. Applied status + event log: `POST /api/jobs/{id}/status`, `JobStatusEvent` (source read).
3. LLM drafting from JD + CV: `cover_letter` in src/api/jobs.py, `llm.router.complete` (source read).
4. Search profile: `Profile` holds search filters only; no personal details (source read).
5. Answer bank: none. CV file store: none (PDFs in `E:\Job hunting\`).
6. API guard: `X-JobPilot: 1` header + CORS for the web app only; an extension origin must be added.
7. Extend, not compete: the extension reuses job status, LLM router and CSRF header.
8. No second pathway: "Mark applied" goes through the same status/event code as the tracker.

## Approaches considered
- A. Copy panel in the web app. Cheap, still manual.
- B. Generic label-matching Chrome extension. Works on any site; weak on Workday widgets.
- C. Per-site adapters only. Accurate on 7 sites, nothing elsewhere, high upkeep.
- E. (ideal, then adjusted) B as the core + site fixes only where B fails. Adjustments: static software CV until Part 2 tailoring (cost: not tailored); no passwords stored (cost: user logs into each Workday tenant).

## Decision
Chosen approach: E.
- Chrome extension (MV3) runs in the user's Chrome; fills, never submits.
- Field matching: applicant details by label synonyms, then the answer bank by token overlap, then an LLM draft (qwen3 via the router) for free-text questions, using the job's description when the page URL matches a known job.
- Each filled field is marked green (profile/exact answer), yellow (fuzzy or LLM draft), red (unknown).
- "Save answers" stores what the user corrected back into the bank.
- CV upload: always `Jai_Bhortake_CV.pdf` (configurable in settings.toml `[apply] cv_path`).
- LinkedIn and Naukri are off until the user enables them per site in the popup.
- First site fix: Workday (custom dropdown buttons, multi-step; fill runs per step).
- "Mark applied" sets the matching job to `applied` via the existing status rules.
- Email applications: later, separate feature.
What would reverse this: if the generic filler fails on most sites, switch to C for those sites.
Scenario table: not a rule change.

## What the user sees
- "I open an application page and click Fill" -> fields fill and are colour-coded; nothing is submitted.
- "I fix a guess and click Save answers" -> next form fills it green.
- "I click Mark applied" -> the job shows Applied in the tracker (or "job not in JobPilot" if unknown).
- Surfaces: extension popup, the page's form, new "Apply profile" page in the web app, tracker.

## Consequences
- Enables later: tailored CV upload (Part 2), email drafts, more site fixes.
- Risk: LinkedIn/Naukri anti-automation terms; mitigated by off-by-default.

## Amendments
