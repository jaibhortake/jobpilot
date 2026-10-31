# Plan: JobPilot Part 2 — tailored CV (max ATS, truthful) and cover letter
Size: L
Depends on: Part 1 complete (`docs/plans/new/jobpilot-part1-discovery.md`). This plan names Part 1 symbols as **(P1)** and new ones as **new**.

## Summary
- A **Tailor CV** page: paste a job description, company and title, and get a one-page PDF built from the master LaTeX CV, with an ATS score before and after.
- The tool rewords and reorders bullets (fact-checked), lists the JD keywords missing from the CV for the user to confirm (only confirmed skills are added, to the Skills section), and lets the user accept or revert every change before the final PDF.
- The same panel works from any job in the Jobs list.
- A fact-checked, editable cover letter.
- 4 phases.

## Context
- Part 1 provides:
  - `jobs` with `description`, and `POST /api/jobs/manual` (P1)
  - `cv_masters` with `facts` from `profile.cv_parser.parse_tex` (P1)
  - `llm.router.complete` (P1) with presets
  - `matching.roles.tokenize` (P1)
  - `JobPanel` tabs (P1), the UI Design System (P1)
- Master CV: `E:\Job hunting\Bhortake_Jai_Resume\resume_faangpath.tex` + `resume.cls`. It is read and never written; it is copied to `data/cv/master/` at compile time.
- `jai_cv_hardware.pdf` has no tex, so it is not tailorable (shown as PDF only).

## Decision Source
- Decision doc: `docs/decisions/2026-10-27-jobpilot.md`.
- Decisions implemented:
  - C6 tailoring incl. 2026-10-28 rulings (standalone page, ATS max via confirmed skills, accept/revert, no automatic status) → Phases 1–3
  - C7 cover letter → Phase 4
  - C10 adds tasks `tailor`, `fact_check`, `cover` → Phase 1
- Carried by another plan: C1–C5 (Part 1), C8–C9 (Part 3).
- Departures: none.

## Assumptions
- A1: The user runs the MiKTeX install and the warm-up compile (Phase 1 prerequisite). The builder halts and asks.
- A2: Part 1 is merged and green.

## Codebase Analysis
- Existing mechanisms ledger (against Part 1 as designed):
  1. Impact: extends `jobs` (no column change), `cv_masters.facts` (adds nothing; reads it), the presets in `settings.toml [llm.presets.*]` (adds 3 task keys to each), `JobPanel` (adds 2 tabs), AppShell sidebar (adds "Tailor CV").
  2. Same job done: `cv_parser` (P1) already yields bullets with ids, skills, entities and numbers. Reused, not duplicated.
  3. Duplicates: none. The ATS keyword extraction reuses `matching/skills_vocab.txt` (P1) and `roles.tokenize` (P1).
  4. Incumbent: extend.
  5. Dead code: none.
  6. Extend-incumbent: adopted.
  7. Shared state: `data/cv/` files; the Ollama/Groq quota (shared with Part 1 checks).
  8. Second pathways: one tailoring service used by both the Tailor page and JobPanel.
- Patterns:
  - **LangGraph** `StateGraph` for the tailoring pipeline (reference project idiom). Needed for the retry edge from fact-check to plan.
  - Otherwise Part 1 patterns.
- Retired: nothing.
- Security:
  - LLM text is inserted into LaTeX only through `cv.latex.escape_tex`.
  - `pdflatex -no-shell-escape -interaction=nonstopmode -halt-on-error`.
  - Compile runs in a fresh temp dir per version under `data/cv/versions/`.
  - User-confirmed skill strings are validated: ≤40 chars, matching `^[\w .+#/-]+$`.
- Files (**new** unless marked (P1)):
```
jobpilot-backend/
  alembic/versions/0004_materials.py
  src/cv/{latex,compile,fact_check,ats,keywords,tailor_graph,service}.py
  src/cover/{generator,template.tex}
  src/api/materials.py
  src/llm/router.py (P1: LlmTask literal gains tailor|fact_check|cover)
  settings.toml (P1: presets gain 3 keys; [cv] gains pdflatex, compile_timeout)
  tests/unit/{test_latex,test_fact_check,test_ats,test_keywords,test_compile,test_cover}.py
  tests/seam/{test_tailor,test_cover}.py
jobpilot-frontend/
  src/views/TailorView.tsx
  src/components/materials/{TailorWorkbench,ChangeList,MissingKeywords,AtsScoreCard,PdfPreview,CoverLetterEditor}.tsx
  src/components/jobs/JobPanel.tsx (P1: + CV and Cover letter tabs)
  src/components/layout/AppShell.tsx (P1: + sidebar item)
  src/api/materials.ts
```

## Impact Analysis
- Hunted: writes to the master tex (forbidden); LaTeX injection; compile hangs blocking the event loop; quota exhaustion shared with discovery; status changes nobody asked for.
- Index: no index; Part 1 plan read for names.
- Changes meaning: 2.
  - (a) `LlmTask` gains 3 values: every preset must define them, or `complete` raises `KeyError` → covered by `test_presets_define_all_tasks`.
  - (b) `JobPanel` gains tabs.

Structural
- Layers: DB → `cv.service` → `api/materials` → `TailorWorkbench` (used by TailorView and JobPanel). One name: `cv_version`.
- Backward: `settings.toml` presets (3 presets × 3 keys); `LlmTask` literal; `JobPanel` tab list; the AppShell nav list and its test (`AppShell.test.tsx` expects 4 links in P1, so it now expects 5: **updated in Phase 2**).
- Edges: the LangGraph node registry; the msw handlers.
- Forward: pdflatex (MiKTeX), pypdf, LLM providers.

Functional
- Flows: paste JD → tailor; job → tailor; confirm missing skills → re-render; accept/revert → re-render; cover generate/edit/export.
- Storage pairs:
  - `cv_versions`: service writes, API/UI read.
  - `confirmed_skills`: the user writes via the API; `cv.service` reads.
  - `cover_letters`: the generator and the user's edits write; the API reads.

Consolidation
- One tailoring service; `fact_check` is reused by the cover letter; `compile` is reused by the cover letter.
- Verdict: one way per job.

## Test Commands
As Part 1 (T1–T4), plus marker `latex` (real pdflatex), which is included in T4 via `scripts/check.ps1` (P1, which gains `uv run pytest -q -m latex`).

## State and Data Contracts
Migration `0004_materials`:

| table | columns | constraints |
|---|---|---|
| cv_versions | id, job_id FK ON DELETE CASCADE, cv_master_id FK, parent_version_id FK nullable, tex text, pdf_path, plan JSONB (order, rewrites, drop, skills_order, added_skills), decisions JSONB {bullet_id: "accepted"/"reverted"}, fact_check JSONB, ats_before JSONB, ats_after JSONB, model text, created_at | |
| confirmed_skills | id, skill text, skill_key (generated `lower(btrim(skill))`), created_at | UNIQUE(skill_key) |
| cover_letters | id, job_id FK ON DELETE CASCADE, body text, pdf_path nullable, fact_check JSONB, model, created_at, updated_at | |

- Identity: a version is immutable once created. Re-render (accept/revert/added skills) creates a new version with `parent_version_id`.
- Authority:
  - The master tex is the only fact source.
  - `confirmed_skills` is user-declared truth, used only in the Skills line.
  - Versions are derived and kept for audit.
- Invariants:
  - Preamble/header/Education/Certifications/Accomplishments/Languages are byte-identical to the master: asserted by `cv.latex.assert_frozen_sections(master, out)` before compile, which raises `FrozenSectionChanged`.
  - The Skills line ⊆ master skills ∪ confirmed skills: asserted in `render`.
- Downgrade drops the 3 tables.

## Failure Modes and Interactions
- pdflatex:
  - Run via `await asyncio.to_thread(subprocess.run, [...], timeout=settings.cv.compile_timeout (default 120))`, twice.
  - A non-zero exit → `LatexError(log_tail=last 40 lines)` → API 422 `latex_error` with the log tail.
  - `FileNotFoundError` → 503 `pdflatex_missing` with "Install MiKTeX (see setup)".
- LLM:
  - `RateLimited` → 429 `llm_rate_limited` ("try again in a minute or switch preset").
  - `RequestTooLarge` → JD trimmed to the budget (`input_budget("tailor")`) and retried once, else 413 `jd_too_long`.
  - `LlmUnavailable` → 503.
  - `LlmBadOutput` → 502 `llm_bad_output` ("the model returned something unusable — try again or switch preset").
- Tailor duration: 3 LLM calls (analyze, plan, fact_check batch) + compile, typically 20–60 s. It runs synchronously in the request (single user) with a UI progress state; the request timeout is 180 s on the client.
- Page length: `ats.pages > 1` → the UI warns "2 pages — revert or drop items to fit one page". There is no automatic trimming.
- Interaction with Part 1: no status change on the job (ruling). The quota is shared: when a Part 1 check is running, tailor still proceeds (independent calls).

## Value Paths and Seam Tests
- paste JD → manual job → tailor → PDF: `test_tailor_from_pasted_jd` (TailorView flow through the API: POST /api/tailor/start, then the version, the pdf exists, ats_after present).
- confirmed skill → appears in the Skills line only: `test_confirmed_skill_added_to_skills_only`.
- revert → new version with the original bullet: `test_revert_creates_child_version`.
- fabrication blocked: `test_fabricated_claims_reverted`.
- frozen sections: `test_frozen_sections_unchanged`.
- cover letter: `test_cover_letter_keeps_intro_and_blocks_claims`.

All use real Postgres + real pdflatex (marker `latex`) with the LLM faked at `litellm.acompletion` (the external boundary).

## Phases

### Phase 1: LaTeX render/compile, ATS scorer, keyword extraction
Goal: from the CVs page, "Score against a JD" shows the current CV's ATS score and missing keywords, and "Compile master" proves pdflatex works.

**User-run prerequisite (halt and ask):**
```powershell
winget install --id MiKTeX.MiKTeX -e
# open MiKTeX Console once → Settings → "Always install missing packages on-the-fly"
# warm-up (installs the packages resume.cls needs), in a new pwsh:
$t = New-Item -ItemType Directory -Force "$env:TEMP\cvwarm"; Copy-Item "E:\Job hunting\Bhortake_Jai_Resume\*" $t; Push-Location $t; pdflatex -interaction=nonstopmode resume_faangpath.tex; Pop-Location
```
Dependency: `pypdf>=5,<6` (`uv add`; pre-approved with the plan).

Files:
- `settings.toml [cv]` (P1) gains `pdflatex = 'pdflatex'`, `compile_timeout = 120`, `master_dir = 'E:\Job hunting\Bhortake_Jai_Resume'`; `[llm.presets.free]` gains `tailor/fact_check/cover = "groq/llama-3.3-70b-versatile"`; `local` gains `"ollama/qwen3:4b"` for each; `claude` gains `tailor/cover = "anthropic/claude-sonnet-5-5"`, `fact_check = "anthropic/claude-haiku-5-5"`; `[llm.budgets]` gains `tailor = 14000`.
- `src/llm/router.py` (P1): `LlmTask = Literal["extract","classify","tailor","fact_check","cover"]`.
- `src/cv/latex.py`:
  - `escape_tex(s) -> str` (`\` → `\textbackslash{}`, then `& % $ # _ { } ~ ^`).
  - `render(master_tex, facts: CvFacts, plan: TailorPlan, decisions: dict[str,str], added_skills: list[str]) -> str`:
    - Rebuilds only the bodies of the Experience, Projects and Skills `rSection`s.
    - Experience: entries in `plan.order["experience"]` order (all entries kept); each `\item` text = the rewrite if `decisions[id]=="accepted"`, else the original.
    - Projects: reordered; `plan.drop` removes whole project entries only.
    - Skills: `\textbf{Technical Skills:}` + `plan.skills_order` (a permutation of the master skills) + `added_skills` (confirmed only) appended; the Soft Skills line is unchanged.
    - Everything else is byte-identical.
  - `assert_frozen_sections(master, out)`.
- `src/cv/compile.py`: `async def compile_tex(tex: str, out_dir: Path) -> Path` (copies `resume.cls` from `master_dir`, writes `main.tex`, runs pdflatex ×2 via `to_thread`, returns `main.pdf`); `LatexError`, `PdflatexMissing`.
- `src/cv/keywords.py`:
  - `async def jd_keywords(jd_text) -> JdKeywords(must_have: list[str], nice_to_have: list[str], role_title: str)`.
  - Deterministic first: vocab phrases (`matching/skills_vocab.txt` (P1) ∪ master skills) found in the JD via phrase match on normalised text.
  - Then one `classify`-task LLM call returns up to 25 more `{keyword, must_have: bool}`, kept only if they appear verbatim (case-insensitive) in the JD. This prevents invented keywords.
- `src/cv/ats.py` `ats_score(pdf_path, kw: JdKeywords) -> AtsReport`:
  - Fields: `score:int, coverage:float, format_ok: dict[str,bool], covered: list[str], missing_must: list[str], missing_nice: list[str], pages:int`.
  - Text from `pypdf`.
  - Coverage = (2·|must covered| + |nice covered|) / (2·|must| + |nice|); a phrase counts as covered if it is present in the normalised text.
  - Format checks:
    - text extractable (≥500 chars)
    - 1 page
    - standard headings present (Education, Skills, Experience)
    - email and phone present
    - no image-only pages
  - Score = round(85·coverage + 15·(passed checks / 5)).
- `src/api/materials.py`: `POST /api/cvs/{id}/ats {jd_text}` → AtsReport of the master PDF compiled fresh (cached by the tex hash in `data/cv/master_cache/`); `POST /api/cvs/{id}/compile` → `{ok, pages}`.
- Frontend `CvsView` (P1): a "Check ATS against a job description" dialog (textarea → `AtsScoreCard`: score ring, covered/missing chips, format checklist); a "Test compile" button.

Test criteria:
- [ ] `uv run pytest tests/unit/test_latex.py -q`:
  - Empty plan + no decisions → output == master (byte-equal).
  - Escaping of `& % $ # _ { } ~ ^ \`.
  - `assert_frozen_sections` raises when the Education text is altered (mutation case).
  - `added_skills` appear only on the Technical Skills line.
- [ ] `uv run pytest tests/unit/test_keywords.py tests/unit/test_ats.py -q`:
  - An LLM keyword not present in the JD is dropped.
  - Coverage maths on a fixed text.
  - A 2-page fixture PDF → `pages=2` and format check failed.
- [ ] `uv run pytest tests/unit/test_compile.py -q -m latex` → the master compiles to 1 page in <120 s; broken tex → `LatexError` with a non-empty tail.
- [ ] `uv run pytest tests/unit/test_presets.py -q` → `test_presets_define_all_tasks`: each preset defines all 5 tasks.
- [ ] Vitest `CvsView.test.tsx` (P1, extended): the ATS dialog renders the score and missing chips from msw.

### Phase 2: Tailoring pipeline, Tailor page, missing-skill confirmation
Goal: paste a JD on the Tailor CV page (or open a job's CV tab) → tailored PDF, ATS before→after, change list, missing keywords to confirm.
Files:
- Migration `0004_materials`.
- `src/cv/fact_check.py` `check(facts: CvFacts, rewrites: dict[str,str]) -> FactCheckResult(ok: list[str], reverted: list[Reverted(bullet_id, reasons: list[str], offending: list[str])])`. Deterministic rules per rewrite, against **its own source bullet `b`**:
  - (a) Numbers: every number token in the rewrite is in `numbers(b.text)`.
  - (b) Terms: every *term* in the rewrite occurs (normalised substring) in `b.text`, `b.entry_title`, `b.entry_org`, or the master Technical Skills list. Terms are:
    - vocab phrases
    - tokens with an inner capital or all-caps ≥2 (`LangChain`, `AWS`, `LLMs`)
    - any capitalised word not at sentence start and not in `cv/common_words.txt` (**new**, ~3 000 common English words)
    - Title-Case runs ≥2
  - (c) Organisations and titles: any org or title name from `facts.entities` other than `b.entry_org`/`b.entry_title` in the rewrite → reverted ("moved fact from another entry").

  Then one batched `fact_check` LLM call over the surviving rewrites returns `[{id, supported: bool, unsupported: [str]}]`; unsupported → reverted.
- `src/cv/tailor_graph.py`: LangGraph `StateGraph(TailorState)`:
  - Nodes:
    1. `analyze` (`jd_keywords` from Phase 1)
    2. `plan`: the `tailor` task with CvFacts (bullet ids + text) + keywords. It returns `TailorPlan(order: dict[str, list[str]], rewrites: dict[str,str], drop: list[str], skills_order: list[str])`.
       - Prompt rules: reword only where the bullet already states the fact; use the JD's vocabulary for the same facts; never add tools, numbers, orgs or titles; skills_order must be a permutation.
       - Validated: unknown ids are dropped; skills_order ≠ permutation → the master order is used.
    3. `fact_check`
    4. `render_compile`: all surviving rewrites default to `accepted`.
    5. `score`: `ats_before` from the master cache, `ats_after` from the new PDF.
  - Edge: if more than 50% of rewrites were reverted → back to `plan` once with the reasons; the second pass continues regardless.
- `src/cv/service.py`:
  - `async def tailor(job_id, cv_master_id) -> CvVersion`; the job must have a description of at least 200 chars, else 422 `jd_missing` ("paste the job description first").
  - `async def rerender(version_id, decisions: dict[str,str], added_skills: list[str]) -> CvVersion`: a new child version; only skills from `confirmed_skills` are accepted, others → 422 `skill_not_confirmed`.
  - `confirm_skills(skills) -> list[str]` (upsert); `list_confirmed()`; `delete_confirmed(id)`.
- `src/api/materials.py`:
  - `POST /api/tailor/start {company_name, title, jd_text, cv_master_id?}`: creates the manual job via the Part 1 service (`origin=manual`, `description_source=pasted`), then tailors → 201 `{job_id, version}`.
  - `POST /api/jobs/{id}/tailor {cv_master_id?}` → 201 version.
  - `GET /api/jobs/{id}/cv-versions`, `GET /api/cv-versions/{id}` (plan, decisions, fact_check, ats_before, ats_after, missing keywords), `GET /api/cv-versions/{id}/pdf`, `GET /api/cv-versions/{id}/tex`.
  - `POST /api/cv-versions/{id}/rerender {decisions, added_skills}`.
  - `GET/POST/DELETE /api/confirmed-skills`.
- Frontend:
  - `views/TailorView.tsx` (sidebar "Tailor CV", icon FileText): step 1 form (Company, Job title, JD textarea, CV select defaulting to the default CV); step 2 `TailorWorkbench`.
  - `TailorWorkbench`, used by both the page and the JobPanel "CV" tab:
    - Left: `AtsScoreCard` before → after (two rings with the delta), `MissingKeywords`, `ChangeList`.
    - `MissingKeywords`: the missing must-haves first, as checkboxes "I genuinely have this skill"; previously confirmed skills are pre-ticked; "Add selected & re-render".
    - `ChangeList`: each bullet shows original vs rewritten, with an Accept/Revert toggle; reverted-by-checker items are shown locked with the reason.
    - Right: `PdfPreview` (iframe of the version PDF; a page-count badge; the 2-page warning); Download PDF / Download .tex; a version dropdown.
    - Progress states: "Analysing JD… Rewriting… Checking facts… Compiling… Scoring…" (client-side stepper during the request), plus error toasts per Failure Modes.
  - `AppShell.test.tsx` (P1) updated to expect 5 nav links.

Test criteria:
- [ ] `uv run pytest tests/unit/test_fact_check.py -q`:
  - "Kubernetes" added → reverted.
  - "97%" → "99%" reverted.
  - A rephrase starting "Built …" with the same facts → ok.
  - "…at Google" in the KPIT bullet → reverted (single capitalised word, rule b).
  - The KPIT bullet gaining "Neo4j" (from the Accionlabs bullet) → reverted (rule b against its own bullet; Neo4j isn't in the Technical Skills list, so it's verified not to be there).
  - Mutation check: with rule (b) removed, the Kubernetes and Neo4j cases pass, so the test fails.
- [ ] Seam `tests/seam/test_tailor.py` (-m "seam and latex"):
  - `test_tailor_from_pasted_jd`: a manual job is created; the version PDF exists, 1 page; `ats_after.score ≥ ats_before.score` with the fake plan using JD vocabulary.
  - `test_fabricated_claims_reverted`.
  - `test_frozen_sections_unchanged`.
  - `test_confirmed_skill_added_to_skills_only`: confirm "FastAPI" → rerender → the tex Skills line contains FastAPI, and no `\item` contains FastAPI.
  - `test_unconfirmed_skill_422`.
  - `test_revert_creates_child_version`.
  - `test_job_status_unchanged_after_tailor`.
  - `test_jd_missing_422`.
- [ ] Vitest `TailorView.test.tsx` + `TailorWorkbench.test.tsx`: the form → workbench; ticking a missing keyword and "Add selected" posts rerender with `added_skills`; the revert toggle posts decisions; the 2-page warning shows when `pages=2`; a 429 shows the rate-limit toast.

### Phase 3: Version history and polish
Goal: compare versions, and reuse a tailored version from the job panel.
- `GET /api/jobs/{id}/cv-versions` already exists. Add `GET /api/cv-versions/{a}/diff/{b}` → per-bullet differences + ATS delta.
- `TailorWorkbench`: a version dropdown with "Compare with…" (side-by-side `ChangeList` diff) and "Mark as final" (stores `cv_versions.is_final` bool, migration `0005_cv_final`; one final per job via a partial unique index). Part 3's tracker links the final version to the application.
- JobPanel "CV" tab: shows the latest or final version summary (ATS score, page count) with "Open workbench".

Test criteria:
- [ ] Seam `test_mark_final_unique_per_job` (a second final unmarks the first, in one transaction).
- [ ] `test_diff_versions` → reverted bullet listed, ATS delta.
- [ ] Vitest: Compare shows both columns; Mark as final updates the badge.

### Phase 4: Cover letter
Goal: "Generate cover letter" on a job (JobPanel tab or the Tailor workbench) gives an editable, fact-checked letter and a PDF.
- `src/cover/generator.py` `async def generate(job_id) -> CoverLetter`:
  - Inputs: CvFacts + confirmed skills, the JD, company name, job title.
  - `cover` task: ≤300 words, 3–4 paragraphs, no placeholders, signed with the CV name.
  - Claim check, per sentence:
    - A sentence is a *claim* if it contains I/my/me **and** a term (Phase 2 definition).
    - Claim terms must occur in the CV facts or confirmed skills; the JD's terms, the company name and the job title are allowed in non-claim position (e.g. "I am applying for the Software Engineer role at Rockwell Automation" is fine because those terms come from the JD, the company or the title).
    - Numbers in claims must be in `facts.numbers` (which excludes list numbering, phone, PIN and years; `cv_parser`, Part 1 Phase 5).
    - Then one `fact_check` LLM call over the claim sentences.
  - Failing sentences → **regenerate once** with the list of unsupported claims to avoid; still failing → those sentences are removed and listed (`fact_check.removed`).
- `src/cover/template.tex`: article 11pt, the header name/contact taken from the master's `\name`/`\address` lines, the date, "Dear Hiring Team at {company},", the body paragraphs (escaped), the sign-off.
- `PUT /api/cover-letters/{id} {body}` recompiles the PDF; the user's edits are not fact-checked (the user is the author) but are shown with a note "edited by you".
- API: `POST /api/jobs/{id}/cover-letter` → 201; `GET /api/jobs/{id}/cover-letters`; `GET /api/cover-letters/{id}/pdf`.
- Frontend `CoverLetterEditor`: Generate → textarea with the letter, a removed-claims list, Save (PUT), Download PDF, Copy text.

Test criteria:
- [ ] `uv run pytest tests/unit/test_cover.py -q`:
  - The intro "I am applying for the Software Engineer role at Rockwell Automation" survives.
  - "I led a team of 20 engineers" → regenerated, then removed if repeated.
  - "I have 4 years of experience" → removed (4 is the paper count in the CV, but a claim's numbers must come from the matching fact; years-of-experience claims are always checked by the LLM step, faked here as unsupported).
  - ≤300 words.
- [ ] Seam `test_cover_letter_keeps_intro_and_blocks_claims` (-m "seam and latex") → saved, PDF exists.
- [ ] Vitest: generate → edit → save sends PUT; the removed list renders.
- [ ] `pwsh -File scripts/check.ps1` → exit 0.

## End-to-end check (manual)
1. Tailor CV → paste a real GenAI JD (Company, Title) → workbench shows ATS before (e.g. 55) → after (higher), a 1-page PDF, a change list.
2. Tick 1–2 missing skills you genuinely have → re-render → they appear only in Technical Skills; the ATS score rises.
3. Revert one rewrite → a new version with the original wording.
4. Open the PDF: Education, Certifications, Accomplishments and Languages are identical to your master; every bullet is still true.
5. Cover letter → generate → edit → PDF.

## Risks and Mitigations
- Groq 70B on the Free preset may rate-limit on long JDs → JD budget trimming, a 429 message, switch to Claude later.
- `qwen3:4b` (Local preset) is weak at rewriting → the Local preset is labelled lower quality in Settings; the fact check protects truth regardless of model.
- The MiKTeX first compile is slow → the warm-up step; a 120 s timeout.
- An ATS score is a heuristic proxy (real ATS systems differ) → shown as "ATS keyword match", with its components visible.

## Out of Scope
Free rewriting; auto-trimming to one page; editing the master CV; tailoring the hardware CV (it needs a .tex); email message text (ruled out).

## Review Passes
- Rounds: 1 (author pass; an outside review is offered before approval).
- Impact: the `LlmTask`/preset coupling (test added); the AppShell nav test updated in Phase 2; the master file is never written (compile copies into a temp dir); the event loop is protected via `to_thread`.
- Consolidation: one tailoring service for two surfaces; fact_check and compile are reused by the cover letter; the keywords reuse the P1 vocab.
- Removal: nothing removed.
- Logic: walked:
  - fabrication via a new tool, a changed number, a cross-entry org/tool move, and a single-word org
  - an unconfirmed added skill
  - a skills permutation violated
  - all rewrites reverted (retry once)
  - a 2-page result
  - a missing JD
  - the cover intro vs claims, and number-source confusion
  - concurrent tailor + a Part 1 check (independent)
- Behaviour: walked TailorView (form → progress → workbench), JobPanel CV tab, the missing-keyword confirm loop, accept/revert, versions/compare/final, the cover editor, and the error toasts; matched against the decision doc's new What the User Sees lines.
- Business sense: as Jai, "max ATS" is met by confirmed skills and JD vocabulary while bullets stay true; the score shows the before/after delta so the benefit is visible; no automatic status change (ruling).
- Contracts: C6 incl. the 2026-10-28 rulings and C7 are mapped; C10 tasks are added; no departures.
- Proof: mutation checks on the fact-check rules and frozen sections; a skills-only placement test; an unconfirmed-skill 422; the cover intro survival test.
- Coherence: migrations 0004 (P2) and 0005 (P3) follow Part 1's 0003; the Phase 1 tests need no tables.
- Executability: the MiKTeX install and warm-up are user-run with exact commands; `pypdf` is pre-approved; every Part 1 name used is marked (P1) and exists in the Part 1 plan. The `classify` and `tailor` tasks are defined in presets in Phase 1 before use in Phase 2.

## Amendment Log
None yet.
