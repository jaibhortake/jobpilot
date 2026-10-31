# Plan: JobPilot Part 3 — contacts, email-address finder, application tracker
Size: L
Depends on: Part 1 (all) and Part 2 Phase 3 (`cv_versions.is_final`). Part 1/2 symbols are marked (P1)/(P2); new ones **new**.

## Summary
- **Contacts:** a contacts database where duplicate emails are impossible. Add and edit in the UI; import from CSV/xlsx, including the sheet's `Hr contacts` column.
- **Find email:** enter a person's name and company, and get up to 3 ranked email **addresses** (no message text, per the ruling). Each is labelled verified / found / pattern / guess, with a confidence and its evidence.
- **Tracker:** statuses, applications, follow-ups, and a dashboard.
- 3 phases.

## Context
Part 1 provides:
- `companies` (identity by `name_key`, nullable `domain`, `domain_source`)
- `jobs` + `job_status_events`
- `search.provider.get_search_provider` (Ddgs/Brave)
- `discovery.http`, `common.urls`
- the importer's `SheetRow.hr_contact`
- the UI system

Part 2 provides `cv_versions` (+ `is_final`) and `cover_letters`.

## Decision Source
- Decision doc: `docs/decisions/2026-10-27-jobpilot.md`.
- Decisions implemented:
  - C8 contacts and finder (address only, labels, no SMTP, `SearchProvider`) → Phases 1–2
  - C9 tracking → Phase 3
  - Lifecycle (manual transitions, backwards allowed, every change logged) → Phase 3
- Carried by another plan: C1–C5, C10 (Part 1); C6–C7 (Part 2).
- Departures: none.

## Codebase Analysis
- Existing mechanisms ledger (against Parts 1–2 as designed):
  1. Impact:
     - Extends `companies.domain` and `domain_source` (written here for the first time).
     - `JobPanel` gains an Application tab.
     - AppShell gains Contacts, Find email and Tracker nav items, so `AppShell.test.tsx` (P1/P2) now expects 8 links (updated in Phase 1 and Phase 3).
     - Part 1's dismiss endpoints are superseded by the general status endpoint (kept as thin wrappers calling `tracker.service.set_status`, so the Part 1 tests stay valid).
  2. Same job done: `SearchProvider` (P1) is reused; the directory import (P1) already parses `hr_contact`.
  3. Duplicates: none.
  4. Incumbent: extend.
  5. Dead code: none. The P1 dismiss/undismiss routes become wrappers, not dead code.
  6. Extend-incumbent: adopted.
  7. Shared state: the `companies.domain` writers are this part only (P1 never sets it, by ruling).
  8. Second pathways: one status-change function for all transitions (P1 wrappers delegate to it).
- Patterns: Part 1 patterns; `dnspython` for MX.
- Retired: nothing; the P1 dismiss logic moves into `tracker.service.set_status` (wire-before-move: the wrappers are switched in Phase 3 and the P1 dismiss seam tests must still pass).
- Security: email inputs are normalised and validated; search snippets are parsed with a regex only (no page fetching); no SMTP connections are ever opened (asserted: `test_no_smtp_import` greps `src/finder` for `smtplib`).
- Files (**new** unless marked):
```
jobpilot-backend/
  alembic/versions/{0006_contacts,0007_tracker}.py
  src/contacts/{normalize,service}.py
  src/finder/{domain,patterns,mx,service}.py
  src/tracker/service.py
  src/api/{contacts,finder,tracker}.py
  src/api/jobs.py (P1: dismiss/undismiss → wrappers)
  tests/unit/{test_normalize,test_patterns,test_finder,test_mx,test_tracker}.py
  tests/seam/{test_contacts,test_finder,test_tracker}.py
jobpilot-frontend/
  src/views/{ContactsView,FinderView,TrackerView}.tsx
  src/components/finder/CandidateCard.tsx
  src/components/jobs/{ApplicationTab,StatusMenu}.tsx
  src/components/layout/AppShell.tsx (P1)
  src/components/jobs/JobPanel.tsx (P1)
  src/api/{contacts,finder,tracker}.ts
```

## Impact Analysis
- Hunted:
  - guesses promoting themselves to evidence
  - evidence double-counted
  - wrong company domains (career hosts)
  - P1 dismiss behaviour drift
  - `applied_at` rewrites
- Changes meaning: 2 things.
  - `companies.domain`: first writer here. Its readers are the finder (here) and the P2 cover letter (doesn't read it).
  - The P1 dismiss endpoints: same behaviour, new implementation.
- Storage pairs:
  - `contacts`: the UI, import and finder-save write; the finder and UI read.
  - `email_evidence`: the finder writes, the finder reads (recomputed, not accumulated).
  - `applications`: the tracker writes, the dashboard and JobPanel read.
  - `job_status_events`: set_status writes, the Activity tab reads.
- Consolidation: one status function; one search provider.
- Verdict: fewer ways (dismiss is merged into status).

## Test Commands
As Part 1/2. A new `live` test `test_ddgs_live` (manual).

## State and Data Contracts
Migration `0006_contacts`:

| table | columns | constraints |
|---|---|---|
| contacts | id, full_name nullable, first_key, last_key (normalised ascii lowercase, nullable), company_id FK nullable, email, email_key (generated `lower(btrim(email))`), role nullable, label (`verified/found/pattern/guess`), confidence float8, evidence JSONB, notes, created_at, updated_at | UNIQUE(email_key) |
| email_evidence | id, domain, email_key, local_part, person_first, person_last, source (`verified_contact/found_snippet`), url nullable, seen_at | UNIQUE(domain, email_key) |

Migration `0007_tracker`:

| table | columns | constraints |
|---|---|---|
| applications | id, job_id FK UNIQUE ON DELETE CASCADE, applied_at date, cv_version_id FK nullable, cv_master_id FK nullable, cover_letter_id FK nullable, contact_id FK nullable, follow_up_on date nullable, response text nullable, updated_at | (both CV fields nullable: the user may record an application before choosing which CV) |

- Identity:
  - A contact is identified by its email key. A person is (first_key, last_key, company_id), not unique: one person may have two emails.
  - Evidence is unique per (domain, email). Pattern support is **recomputed** from `email_evidence` on each find, never incremented.
- Authority:
  - `verified` is set only by the user (UI add or edit, import).
  - The finder never writes `verified` and never overwrites an existing contact.
  - Evidence comes only from `verified` contacts and verbatim snippet emails **with an adjacent name** (`found_snippet`); `pattern`/`guess` contacts are never evidence.
- `companies.domain`:
  - set when (a) the user saves a verified contact with a non-free-mail domain and the company's domain is null (→ `domain_source=verified_contact`), or (b) the user confirms a finder-proposed domain (→ `search_confirmed`);
  - never overwritten automatically once set; the user can edit it on the Companies page (P1 view gains a Domain field).
- Lifecycle (tracker):
  - Any status → any status except `closed` (system-only). Each change logs an event with `actor=user`.
  - Entering `applied`: if no `applications` row exists, insert one with `applied_at=today`, `cv_version_id` = the final version (P2) or null, `follow_up_on=today+7`. If it exists, nothing is overwritten.
  - `applied_at` and every application field are editable via PATCH.
- Downgrades drop the tables.

## Failure Modes and Interactions
- Search:
  - `ddgs` errors or rate-limits → the finder returns candidates from patterns and priors only, with the warning "web search unavailable — results are based on email patterns only".
  - Brave 401 → falls back to Ddgs with the same warning.
- MX (`dnspython`, timeout 5 s):
  - `NXDOMAIN` or `NoAnswer` → `mx=False`: confidences ×0.3, evidence "domain has no mail server".
  - `Timeout` or `NoNameservers` → `mx=None` (unknown): no penalty, evidence "couldn't check the mail server".
- Duplicate email → 409 `duplicate_email` `{existing_id}`; import duplicates are counted, not errors.
- Status to `closed` → 400 `invalid_status`.

## Value Paths and Seam Tests
- `test_contact_duplicate_409_and_import_counts`
- `test_import_sheet_hr_contacts` (P1 `SheetRow.hr_contact` → contacts as verified)
- `test_verified_contact_sets_company_domain`
- `test_finder_pattern_from_verified`
- `test_finder_labels_per_candidate`
- `test_finder_evidence_not_double_counted`
- `test_finder_never_overwrites_verified`
- `test_status_change_logs_and_creates_application_once`
- `test_dismiss_wrappers_still_work`

## Phases

### Phase 1: Contacts database
Goal: add, edit, import and search contacts; duplicates are impossible; company domains get learned from verified emails.
- Migration `0006_contacts`.
- `src/contacts/normalize.py`:
  - `normalize_email(s) -> str | None`: trim, lowercase, regex `^[^@\s]+@[^@\s]+\.[^@\s]{2,}$`.
  - `split_name(full) -> (first_key, last_key)`:
    - strips honorifics (Mr, Ms, Mrs, Dr, Prof)
    - ASCII via NFKD
    - lowercase
    - first token = first name, last token = last name
    - a single token gives (token, None)
  - `FREE_MAIL = {gmail.com, yahoo.com, yahoo.co.in, outlook.com, hotmail.com, live.com, icloud.com, proton.me, protonmail.com, rediffmail.com}`.
- `src/contacts/service.py`:
  - `create(...)`: label `verified`, confidence 1.0; 409 on duplicate; sets the company domain if the conditions in Contracts hold.
  - `update`, `delete`, `list(q, company_id, label)`.
  - `import_file(bytes, filename)`: columns `name`, `email`, `company`, `role`, case-insensitive. The sheet's `hr contacts` column is also accepted as `email`, with the company taken from `company`. Returns `ImportResult(created, duplicates, invalid, details)`.
  - The Part 1 directory import also calls `contacts.service.import_sheet_rows(rows)` for rows with `hr_contact` (Part 1's importer already returns them).
- `src/api/contacts.py`: `GET /api/contacts?q=&company_id=&label=`, `POST`, `PATCH /{id}`, `DELETE /{id}`, `POST /api/contacts/import`, `GET /api/contacts/check?email=` → `{exists, id?}` (live duplicate check).
- Frontend `ContactsView`:
  - a table with search and a label filter
  - an add dialog with a live duplicate check (debounced 300 ms, "Already saved — open")
  - inline edit
  - import with a result toast and details
  - the empty state "No contacts yet — add or import".
- The Companies page (P1) gains an editable Domain field showing `domain_source`. AppShell gains Contacts.
Test criteria:
- [ ] `uv run pytest tests/unit/test_normalize.py -q`:
  - `"  John.Doe@ACME.com "` → `john.doe@acme.com`.
  - `"Dr. Priya Sharma"` → (`priya`, `sharma`).
  - `"Ånand Kumar"` → (`anand`, `kumar`).
  - an invalid email → None.
- [ ] Seam `test_contact_duplicate_409_and_import_counts`: `A@x.com` then `a@X.com ` → 409 with the existing id; an import of 4 rows (1 DB dup, 1 in-file dup, 1 invalid) → created 1, duplicates 2, invalid 1.
- [ ] Seam `test_import_sheet_hr_contacts` and `test_verified_contact_sets_company_domain`: a gmail contact doesn't set the domain; an `@rockwellautomation.com` contact sets it with `domain_source=verified_contact`; a second domain doesn't overwrite it.
- [ ] Vitest `ContactsView.test.tsx`: the duplicate warning shows before submit; the import toast counts.

### Phase 2: Email-address finder
Goal: name + company → up to 3 ranked addresses with labels, confidence and evidence; Save adds one to contacts.
- Migration: none. `email_evidence` is created in `0006_contacts` (Phase 1) and first written here.
- `src/finder/patterns.py`:
  - `PATTERNS = ["first.last","firstlast","flast","f.last","first","first_last","last.first","firstl","first-last","lastf"]`.
  - `render(p, first, last) -> str|None` (None if `last` is required but missing).
  - `classify(local, first, last) -> str|None` (which pattern produced this local part).
  - `PRIORS = {first.last:.40, firstlast:.12, flast:.12, f.last:.08, first:.08, first_last:.06, last.first:.04, firstl:.04, first-last:.03, lastf:.03}`.
- `src/finder/domain.py` `async def resolve_domain(session, company) -> DomainResult(domain|None, source, needs_confirmation: bool, candidates: list[str])`:
  1. If `companies.domain` is set → use it.
  2. Else, if there is a verified contact at the company with a non-free-mail domain → that domain.
  3. Else search `"{company} official website"` and take up to 5 hits:
     - Registrable domains via `tldextract` (P1 dependency).
     - Excluded: aggregators (P1 list) and hosted-ATS hosts (`myworkdayjobs.com, oraclecloud.com, smartrecruiters.com, ashbyhq.com, greenhouse.io, lever.co, icims.com, eightfold.ai, avature.net, mokahr.com, taleo.net, successfactors.com, jobvite.com, workable.com, phenompeople.com`).
     - Kept if the domain contains an alphanumeric token (≥4 chars) of the company name.
     - Returns `needs_confirmation=True` with the candidates.

  The UI asks the user to pick one; it is saved to the company with `domain_source=search_confirmed`.
- `src/finder/mx.py` `async def mx_status(domain) -> bool|None` (Contracts semantics; cached 1 h).
- `src/finder/service.py` `async def find(name, company, domain=None) -> FinderResult(candidates, domain, mx, warnings)`:
  1. Normalise the name.
  2. If an existing contact with the same (first_key, last_key, company) exists → return it alone, with its stored label (`verified` stays verified).
  3. Resolve the domain (explicit `domain` param wins). Needs confirmation → return early `{needs_domain_confirmation, candidates}`.
  4. Search via `SearchProvider`: `"\"{first} {last}\" \"@{domain}\""` and `"{first} {last}" {company} email`, 8 hits each.
     - Regex-extract emails at `@{domain}` from snippets.
     - For each: if the local part classifies as a pattern **for a name that appears within 60 chars of it in the same snippet**, upsert `email_evidence(source=found_snippet, person names, url)`.
     - If the email equals a rendering for **this** person → candidate label `found`, confidence 0.9, evidence url.
  5. Evidence set E = `email_evidence` rows for the domain + verified contacts at the domain with names, recomputed into `support[p]` = count of distinct emails classifying as p (verified counts 2, snippet 1).
  6. Candidates per pattern p with a rendering:
     - if `support[p] > 0` → label `pattern`, confidence = 0.45 + 0.45 × support[p]/Σsupport (cap 0.85), evidence "N addresses at {domain} use {p}";
     - else → label `guess`, confidence = 0.45 × PRIORS[p]/0.40 (max 0.45), evidence "common format (no examples found at {domain})".

     Sort by (label rank found > pattern > guess, confidence) and take the top 3.
  7. If mx is False → confidences ×0.3 and a warning; if mx is None → a warning only.
  8. Never writes contacts.
- `src/api/finder.py`:
  - `POST /api/finder {name, company, domain?}` → FinderResult or `{needs_domain_confirmation, candidates}`.
  - `POST /api/finder/confirm-domain {company, domain}`.
  - `POST /api/finder/save {email, name, company, label, confidence, evidence}` → creates a contact with that label (never `verified`; the user can edit the label to verified on the Contacts page after confirming by other means); 409 on duplicate.
  - `get_search_provider` is a dependency (P1).
- Frontend `FinderView` (sidebar "Find email"):
  - Form fields: Name, Company (autocomplete from the directory), optional Domain.
  - The domain-confirmation step: radio candidates + "Type domain".
  - `CandidateCard`s: the email in mono, a label badge (verified green, found blue, pattern amber, guess grey), confidence %, evidence bullets (links open in a new tab), Copy and Save buttons.
  - A banner "Guesses aren't verified — they may bounce" when no candidate is found/verified; warnings shown.
  - JobPanel Overview gains "Find a contact at {company}", which opens the FinderView with the company prefilled.
  - AppShell gains Find email.
Test criteria:
- [ ] `uv run pytest tests/unit/test_patterns.py tests/unit/test_finder.py tests/unit/test_mx.py -q` (fake SearchProvider, fake MX):
  - (a) 2 verified contacts at acme.com use flast → the top is `psharma@acme.com`, label pattern, confidence ≥0.7; the **2nd and 3rd candidates are label guess** (zero support).
  - (b) No data → all guess, the top first.last at 0.45.
  - (c) A snippet "Priya Sharma — priya.sharma@acme.com" → found 0.9, first.
  - (d) A snippet email without a nearby name → no evidence row.
  - (e) Running find twice → `support` unchanged (`test_finder_evidence_not_double_counted`).
  - (f) An existing verified contact → returned alone, label verified.
  - (g) NXDOMAIN → ×0.3; Timeout → no penalty + warning.
  - (h) Only `metacareers.com` and `linkedin.com` hits → needs_domain_confirmation with no candidates, so the user types the domain.
  - (i) `test_no_smtp_import`.
- [ ] Seam `test_finder_pattern_from_verified`, `test_finder_labels_per_candidate`, `test_finder_never_overwrites_verified` (saving a guess for an email that exists as verified → 409; the existing row is unchanged).
- [ ] Vitest `FinderView.test.tsx`: the domain confirmation flow; the guess banner; Save posts with label guess.
- [ ] Live (manual) `-m live test_ddgs_live` → ≥1 hit for "Rockwell Automation official website".

### Phase 3: Application tracker and dashboard
Goal: move jobs through statuses, record applications and follow-ups, and see a dashboard.
- Migration `0007_tracker`.
- `src/tracker/service.py`:
  - `set_status(session, job_id, to, note=None)`: validation per Contracts; logs an event (actor user); the `applied` rule (insert-once).
  - `update_application(job_id, **fields)` (`applied_at`, `follow_up_on`, `response`, `contact_id`, `cv_version_id`, `cv_master_id`, `cover_letter_id`), validating that FKs belong to the same job, or for `cv_master_id` any master.
  - `dashboard()` → `{counts_by_status, applied_last_7d, follow_ups_due: [...] (follow_up_on ≤ today and status in applied/interview), recent_events: [...20]}`.
- `src/api/tracker.py`: `POST /api/jobs/{id}/status {to, note?}`; `GET/PATCH /api/jobs/{id}/application`; `GET /api/tracker/dashboard`; `GET /api/jobs/{id}/events` (P1 Activity already reads events: keep the shape).
- `src/api/jobs.py` (P1): `dismiss`/`undismiss` become wrappers over `set_status` (same responses).
- Frontend:
  - `StatusMenu` in JobPanel and as a quick action in JobList rows (Shortlist, Applied, Interview, Offer, Rejected, Dismiss).
  - `ApplicationTab` in JobPanel:
    - applied date
    - CV used (the final version from P2, or "Hardware CV (PDF)")
    - cover letter
    - contact picker (contacts at the company)
    - follow-up date
    - response
  - `TrackerView` (sidebar "Tracker", badge = follow-ups due): count cards, a "Follow-ups due" list with "Done → next date (+7)", a board of status columns (cards open the job), and recent activity.
  - The Jobs filter chips gain Status.
  - Hotkey `s` = shortlist (ignored in inputs).
  - AppShell gains Tracker (8 links total; the test is updated).
Test criteria:
- [ ] `uv run pytest tests/unit/test_tracker.py -q`:
  - Entering applied creates the application once.
  - interview → applied again keeps the original `applied_at`.
  - PATCH applied_at works.
  - Manual `closed` → error.
  - Hardware CV via `cv_master_id` accepted.
- [ ] Seam `test_status_change_logs_and_creates_application_once`, `test_dismiss_wrappers_still_work` (the P1 dismiss seam test still passes unchanged), `test_dashboard_follow_ups_due`.
- [ ] Vitest `TrackerView.test.tsx`, `ApplicationTab.test.tsx`: counts render; Done moves the date; the contact picker lists only company contacts; `s` while typing does nothing.
- [ ] `pwsh -File scripts/check.ps1` → exit 0.

## End-to-end check (manual)
1. Contacts → add `someone@rockwellautomation.com` as verified → the Rockwell domain is learned; adding it again in uppercase → "Already saved".
2. Find email → "Priya Sharma", Rockwell → pattern-based candidates with evidence; Copy; Save as guess.
3. Find email at a company with no data → domain confirmation → guesses with the banner.
4. A job → Applied → the Application tab shows today, the final CV and a follow-up in 7 days; Tracker shows it under Applied; move the follow-up to yesterday → "Follow-ups due" lists it.

## Risks and Mitigations
- Pattern guesses bounce → explicit labels/confidence, never shown as verified.
- `ddgs` instability → pattern-only fallback with a warning; Brave via a key.
- Wrong company domain → user confirmation required; never derived from career hosts.

## Out of Scope
Writing email messages (ruled out); sending email; SMTP verification; LinkedIn; paid finder APIs (a later provider slot).

## Review Passes
- Rounds: 1 (author pass; an outside review is offered before approval).
- Impact: the first writer of `companies.domain`; the P1 dismiss routes migrated with their tests kept; the AppShell nav count updated per phase.
- Consolidation: one status function; reuse of SearchProvider, tldextract and the URL safety function.
- Removal: the P1 dismiss implementation moves into `set_status`; the wrappers keep the routes.
- Logic: zero-support labels; evidence recomputed, not accumulated; snippet emails without names; guess contacts excluded from evidence; MX timeout vs NXDOMAIN; an existing verified contact; career-host domains; re-entering applied; the hardware CV.
- Behaviour: walked Contacts (empty, add, dup, import), Finder (domain confirm, results, banner, save), Tracker, the JobPanel Application tab, and the StatusMenu.
- Business sense: as Jai, a name + company gives honest ranked addresses; "Find a contact at {company}" from a job removes retyping.
- Contracts: C8 (address only, per the 2026-10-28 ruling) and C9 mapped.
- Proof: per-candidate label assertions, a double-count test, the no-SMTP grep, the applied_at preservation test, the wrappers' regression test.
- Coherence: migrations 0006/0007 after Part 2's 0005; the `email_evidence` table is created in 0006 (Phase 1) and used in Phase 2.
- Executability: `dnspython>=2.6,<3` is pre-approved with this plan (`uv add`, Phase 2); all P1/P2 names come from those plans.

## Amendment Log
None yet.
