# Handoff: JobPilot (updated 2026-11-01)

## Current state (read this first; the sections below are history)
- **The app is built and runs.** Backend `jobpilot-backend/` (FastAPI, Postgres, Alembic) and frontend `jobpilot-frontend/` (React 19, Vite). README.md has the run commands; the dev and test databases (`jobpilot`, `jobpilot_test`) exist and are migrated.
- **Built:** company directory and sheet import, discovery readers (Workday, Oracle, SmartRecruiters, Ashby, Greenhouse, Lever, iCIMS, and a generic browser + LLM reader), scoring and feedback, tracker, contacts with bulk paste and email finder. Not built: CV tailoring / PDF (Part 2), embedding scoring, an Eightfold reader.
- **2026-11-01 changes:**
  - Companies: add with a careers link, add a link to any row, rename a company, a "last check" line under every link, and a "Find careers links" batch search whose results the user accepts one by one (nothing is added unconfirmed).
  - Jobs: the "Add job" button and dialog were removed. The Check company dialog now shows the real error when a check yields nothing.
  - Checks: the generic reader follows a careers landing page to its job search (up to 3 pages) and remembers it in `ats_config.listing_url`; postings with no location are kept; a name like "rockwell" resolves when only one company matches; stuck runs are marked failed.
  - Contacts: "Sort Other emails" moves a whole email domain to a company (`POST /api/contacts/move-domain`); free-mail domains never teach the importer. On 2026-11-01 115 of 131 "Other" contacts were moved to named companies; 16 stay under Other on the user's instruction (gmail plus domains they could not name).
- **Tests:** backend unit 39, seam 18 (run on `jobpilot_test` only; `conftest.py` refuses any other database); frontend 14. Run `uv run pytest -q`, `uv run ruff check src tests`, `uv run mypy src`, then `npm run test` and `npx tsc -b`.
- **Open items:**
  - **Brave search key:** `BRAVE_API_KEY` in `jobpilot-backend/.env` is empty, so careers search falls back to the flaky free DuckDuckGo search. The user must create a key and paste it into `.env`; never print `.env`.
  - **Generic reader quality:** 74 of 124 sources are generic and depend on the LLM. Groq rate limits show as "skipped"; re-run after a minute.
  - Frontend has no view or dialog tests yet.
  - The `docs/plans/` files describe the original plan; code is the source of truth.
- Rules still in force: ask before downloading or installing anything; never print or overwrite `.env`.

## History (2026-10-27, superseded by the section above)
- Brainstorm done. Decision doc: `docs/decisions/2026-10-27-jobpilot.md`.
- An outside review returned 50 findings (listed below); the plan was split into 3 parts with the user's agreement.
- At that time no code had been written.

## User rulings made today, after the plan was written (apply tomorrow)
1. **Split the plan into 3 plans against the one decision doc:**
   - Part 1: find and rank jobs (setup, sources and ATS detection, refresh, split-view Jobs UI, add job by URL, paste JD, scoring with role filter, thumbs).
   - Part 2: materials (CV tailoring with per-change accept/revert, cover letter).
   - Part 3: contacts, email finder, tracker.

   Fix all Part 1 findings, review Part 1 to convergence, then freeze and build. Parts 2 and 3 get planned while Part 1 is built.
2. **React:** "use whichever is already installed, if not use one with minimum space". Nothing is installed globally (React is per project) and both versions are about the same size. **Use React 19**, which is compatible with the current shadcn/ui; record it as a deliberate difference from the reference project's React 18.
3. **PowerShell 7:** OK. Add `winget install --id Microsoft.PowerShell -e` to the user-run prerequisites, so the scripts use `pwsh`. **Ask before running it.**
4. **Local LLM:** Ollama models now live at `E:\ollama\models` (user env var `OLLAMA_MODELS`). `llama3.2` was deleted. Installed: `nomic-embed-text` (embeddings) and `qwen3:4b` (chosen over `qwen3:8b` because only about 2.4 GB of RAM was free; 4b fits fully in the 4 GB RTX 3050). **Update the plan:** replace `ollama/llama3.2` with `ollama/qwen3:4b` and disable thinking mode (`/no_think` or `think=false`).
5. **Never download or install anything without the user naming it first.**

## Outside review findings to fix (Part 1 first; P2/P3 noted)
Part 1:
- Generic sources should report a page kind (listing/landing/login/blocked), use a `no_listings` status, and give a "paste the job-search URL" hint; store found-before vs kept-after filter counts.
- ATS detection should also use URL patterns: `pid=`/`domain=` means Eightfold (Microsoft, Lam, Ericsson, Deere); `/sites/` means Oracle (oracle, ti, honeywell). Add an HTML sniff for greenhouse/lever/ashby/workday embeds.
- Descriptions: fetch them for every job missing one, newest first, across runs; fetch on demand when a job is opened; add a "Paste JD" box. Store `jobs.page_text`.
- Workday: use the India `locationCountry` facet in `appliedFacets`, add Indian-city aliases, store unmatched jobs and let the scorer filter them instead of the reader dropping them.
- Role hard filter (title must match role synonyms). Default excludes add `senior, sr, lead, manager, staff, architect`. Keywords add `genai, ml`. Match tokens, not substrings ("ai" ≠ "maintenance").
- Undated jobs from a source's first crawl count as date-unknown and sort after dated ones.
- Rescore on a profile change and on a default-CV change (or apply hard filters at query time).
- "Add job by URL" action, plus manual job entry.
- Refresh: run different hosts concurrently (4); Workday stops paging at jobs older than the last crawl or 30+ days; add a cancel flag; run phases crawling → describing → scoring; a hook failure is kept separate from the crawl status.
- Free preset: small extraction inputs (about 4k tokens); map 413 to its own error; treat `LlmUnavailable` like exhausted and short-circuit.
- At startup, mark **all** `running` runs as failed (plus an optional heartbeat).
- Close rule: on re-sighting, restore the pre-close status; close only on a complete crawl (no cap hit, same query); generic sources close after 2 consecutive misses; log a close event.
- Generic `external_id`: strip only tracking query params; dedupe every batch by `external_id` before the upsert.
- `posted_at`: keep `min(existing, parsed)`.
- Feedback: stopwords/IDF, per-feature normalisation, clamp total ±0.3, rebuild weights from scratch, add `skill:` features, control test. Add a "Hide similar" action on 👎 (decision commitment 4, missing from the plan).
- Embeddings cached (already changed to Ollama + `job_embeddings`); embed the CV per section, not truncated.
- Company domain: never take it from a career-page URL; keep a hosted-ATS host list; use `tldextract`; resolve the companies identity mismatch (name vs domain) or record it as a departure.
- Source DELETE: cascade the child tables (job_scores, feedback, events, versions).
- Sources UI: `last_success_at`, editable URL, ATS type and `ats_config`.
- Executability:
  - `pwsh` (now a prerequisite).
  - Postgres install with `--interactive`; full path to psql, which isn't on PATH.
  - Dynaconf: `environments=True`, or drop the `[default]` tables.
  - mypy overrides; ruff with `Annotated` dependencies (B008).
  - React 19 + shadcn alias steps (`@/*` in both tsconfigs, the vite alias, `@types/node`, `shadcn init -d`); a `matchMedia` stub in the test setup.
  - Tests must never touch the dev DB (conftest sets `DATABASE_URL` = `TEST_DATABASE_URL` before import); Alembic downgrade drops the enum types.
  - TOML Windows paths in single quotes.
  - `curl.exe` in PowerShell.
- Security: allow only http(s) hrefs; `TrustedHostMiddleware`; require a custom header on mutating requests (CSRF).
- Keyboard shortcuts are ignored inside inputs; the NEW flag is computed per source; the shortlist/dismiss keys need the status API (move it earlier or ship the keys with it).
- Remote jobs count only if they name India or no country.
- Proof: parametrize ATS detection over **all** sheet URLs; add a re-sighting/cap/shortlisted close test; a health `db:false` test; run the Proactor test under a forced Selector loop.

Part 2 (materials): the fact check binds orgs and titles per bullet, single-capitalised-word terms, substring rules, cross-bullet transfer test; per-rewrite accept/revert + re-render; no automatic `materials_ready`; the cover letter allows JD/company terms, uses the LLM claim check, excludes list numbering/phone/PIN/years from numbers, and regenerates rather than deleting; pdflatex via `to_thread`, a MiKTeX warm-up compile; hardware CV: `applications.cv_master_id`, pdf master not allowed as the scoring default; the end-to-end step 4 must be concrete.

Part 3 (contacts/finder/tracker): per-candidate labels (support>0 → pattern); snippet emails only feed inference with an adjacent name; recompute patterns, never accumulate; count only verified/found contacts; MX timeout ≠ no MX; "Find contact at this company" with generic addresses; `applied_at` set on insert only and patchable.

## Update 2026-10-28
- New rulings:
  - **No "Refresh all":** the user checks one company at a time by name or link; the sheet is a directory. An unknown company → careers-page search → the user confirms.
  - **Company identity by name.**
  - The `qwen3:4b` model via Ollama; the app strips `</think>`.

  All written into the decision doc.
- Probes: the Workday India `locationCountry` facet works; the Eightfold API refuses ("Not authorized for PCSX"), so Eightfold sites use the browser reader.
- Part 1 plan written: `docs/plans/new/jobpilot-part1-discovery.md` (6 phases). The old single plan was renamed `jobpilot-unsplit-draft.md` (reference for Parts 2–3).
- Later the same day:
  - Rulings: a standalone Tailor CV page (paste JD); max ATS via user-confirmed missing skills (Skills section only); per-bullet accept/revert; email finder = address only; plan all 3 parts, build 1→2→3.
  - Parts 2 and 3 written: `jobpilot-part2-materials.md`, `jobpilot-part3-contacts-tracker.md`.
- Next: outside review of all 3 parts if the user wants it → approval → `mv` to `active/` → Phase 0 (halt for user-run installs: PowerShell 7, Postgres 17 `--interactive`, DB creation, `.env` DB URLs).

## Build status (2026-10-28)
- Part 1 plan approved and moved to `docs/plans/active/` (decision doc is now frozen). Parts 2–3 are still in `new/` and need the full ten-pass review before activation.
- **Phase 0 done:** backend (FastAPI app factory, security middleware, `/api/health`; 5 tests, ruff + mypy clean) and frontend (Vite + React 19 + Tailwind + shadcn, app shell, command palette, theme menu, health dot; 14 tests, tsc, build). `scripts/check.ps1` passes in 52 s; `scripts/dev.ps1` written.
- **Version notes:**
  - TypeScript 7 has no `baseUrl`; `paths` is used alone.
  - msw 3 uses `onUnhandledFrame`.
  - shadcn's new style is Base UI (`render` prop, not `asChild`).
  - `UV_NATIVE_TLS=1` is needed for uv on this machine (TLS inspection); the scripts set it.
- **Blocked on the user:** install PowerShell 7 and Postgres 17, create `jobpilot` and `jobpilot_test`, and fill `DATABASE_URL` / `TEST_DATABASE_URL` in `jobpilot-backend/.env`. The `conftest.py` refuses a test URL whose DB name doesn't end in `_test`.
- Next: Phase 1 (company directory, ATS detection). Its unit tests need no database; its migration and seam tests do.

## Next step (original, 2026-10-27)
Rewrite `docs/plans/new/` as `jobpilot-part1-discovery.md` (+ stubs for part 2/3 or plan them later). Fold in the rulings and Part 1 findings, update the decision doc while it's editable (React 19, pwsh, qwen3:4b, split), run the ten plan passes to convergence, then offer an outside review again → user approval → `mv` to `docs/plans/active/` → Phase 0 (stop at user-run installs: PowerShell 7, Postgres 17 `--interactive`, MiKTeX — asking first).
