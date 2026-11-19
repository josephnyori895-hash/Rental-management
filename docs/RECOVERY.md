# Recovery baseline — handoff note

Status: **verified baseline landed** on `main`. Design work is frozen until this commit is reviewed.

## Why this commit exists

`origin/main` sat at `f0427df` while 36 commits of auth/landing work lived only on
`codex/rental-auth-polish`, unmerged. That branch was fast-forwarded into local `main`
(`20d410d`) and could not compile on its own. Separately, a large body of work — payments
integrations, the in-process scheduler, rent-run automation and their tests — existed only
as untracked files on a developer machine and had never been committed at all.

This commit lands the working tree so the repository, not the laptop, is the source of truth.

## Defects found and repaired

1. `frontend/src/lib/api.ts` — dropped five exports still imported elsewhere:
   `listStaff`, `assignCaretaker`, `createProperty`, `createUnit`, `runRent`.
   Symptom: five `TS2305` build errors in `Onboarding.tsx`, `Properties.tsx`, `Payments.tsx`.
2. `backend/app/core/config.py` — the committed version lacked `REMINDERS_ENABLED`,
   `REMINDER_HOUR_UTC`, `RENT_RUN_ENABLED`, `RENT_RUN_HOUR_UTC`, `AIRTEL_*`, `FLUTTERWAVE_*`.
   Symptom: `AttributeError: 'Settings' object has no attribute 'REMINDERS_ENABLED'` at startup.
   The production-secrets `model_validator` from `codex/rental-auth-polish` is retained.
3. `frontend/public/sw.js` — cache-first for every GET with a static cache name, so a deployed
   build could never supersede a cached shell. Now: network-first for navigations, cache-first
   only for hashed assets, stale caches deleted on activate.

## Verification performed before this commit

| Check | Command | Result |
|---|---|---|
| Types | `npx tsc --noEmit` | 0 errors |
| Bundle | `npm run build` | pass, `index-xdKOfwYw.js` |
| Import | `python -c "import app.main"` | OK |
| Settings | `settings.REMINDERS_ENABLED` etc. | all load |
| Tests | `pytest tests/test_rent_run.py tests/test_scheduler.py` | 27 passed |
| Migrations | `alembic upgrade head` | at head (`f6a7b8c9d0e1`) |
| Secrets | `backend/.env` | gitignored, not tracked |

## Scope note

No behaviour was rewritten in the recovered modules — they are committed as they were written
and tested. The only authored change in this commit is the service worker strategy above.

## Known gaps

- No password-reset endpoint exists in `app/auth/router.py`. Do not present recovery as functional.
- `POST /auth/register` accepts an optional `mpesa` configuration block; it is part of the contract.
- `GET/POST /auth/staff` exist and are used by the properties screen.
- `origin/redesign/premium-frontend` (11 commits) does not contain `20d410d) and diverges from it.
  Do not treat it as a basis for further work without reconciling first.

## Redesign reconciliation — local-agent handoff

**Authority and starting point**

- The only approved redesign base is commit `ad655377718ce1df39d00d6686e3d46b671cca1f`
  (short SHA `ad65537`). GitHub comparison confirmed `main) was identical to this commit
  at the time this handoff was prepared (0 ahead / 0 behind).
- Do not use `20d410d`, `f0427df`, or the existing `redesign/premium-frontend` head as a base.
- The existing `redesign/premium-frontend` branch is divergent: 11 commits ahead of its merge
  base and 39 commits behind `ad65537`; its merge base is `f0427df`. Do not continue,
  merge, rebase, reset, or force-push that branch before an explicit reconciliation decision.
- Preserve the old branch as a read-only reference. Do not delete it.

**Local-agent task: read-only reconciliation audit first**

1. Fetch the latest repository refs and confirm the exact SHA of `main`, `ad65537`, and
   `redesign/premium-frontend`. Report any changes since this note was written.
2. Confirm the local working tree is clean and that the local checkout contains the full
   recovery commit. If it is not clean, stop and report every modified, staged, and untracked
   path. Do not stash, reset, clean, overwrite, or discard anything.
3. Compare the complete old redesign branch diff against `ad65537`, not merely its latest
   commit. Inspect all 11 branch-only commits and all changed files. For each change classify:
   - **KEEP**: safe, self-contained UI improvement compatible with the recovered baseline;
   - **ADAPT**: useful design work that must be rewritten against current components/contracts;
   - **DROP**: obsolete, duplicate, unsafe, misleading, or incompatible work.
4. Pay special attention to `frontend/src/lib/api.ts`, `frontend/src/App.tsx`,
   public routing, login/register flows, and stylesheet import order. Verify all five restored
   API exports remain present and preserve existing request/response contracts, including the
   optional `mpesa` registration block and staff endpoints.
5. Inspect the old `Welcome` page for API contract drift, client-side validation, error/loading
   handling, password visibility, responsive behaviour, accessibility, and claims about
   capabilities. There is no password-reset endpoint: do not add a working-looking reset flow
   or link. Do not fabricate demo metrics or imply illustrative dashboard data is live.
6. Inspect global CSS overrides for regressions to authenticated screens. Avoid broad selectors
   that silently recolour every existing Tailwind class unless verified across all app pages.
7. Return a file-by-file reconciliation table with the old branch commit(s), current baseline
   counterpart, KEEP/ADAPT/DROP decision, rationale, and proposed implementation approach.
   Include risks, missing files, API assumptions, and tests needed.

**Hard stop rules during this audit**

- Read-only only: no edits, commits, pushes, merges, rebases, resets, branch creation, deploys,
  migrations, or production changes.
- Do not report source inspection as a successful build or browser test.
- Do not claim the local machine was inspected unless the local agent actually ran the commands.
- Do not invent missing code or infer that a path is unchanged when it was not inspected.
- If any unexpected divergence, dirty working-tree content, missing recovery file, or failed
  contract check is found, stop and report it before implementation.

**After the audit — implementation gate**

Wait for the user to approve the reconciliation report. Only then create the new branch
`redesign/premium-frontend-v2` directly from exact commit `ad655377718ce1df39d00d6686e3d46b671cca1f`.
Do not reuse or move the old branch. Port only approved KEEP/ADAPT items, preserving all
existing backend/data wiring. Run TypeScript, production build, backend import and relevant
tests; then run real Chromium checks at desktop, tablet and mobile widths. Report exact commands,
results, screenshots or traces, and unresolved issues. No production deployment without separate
explicit approval.

**Agent report format**

- Confirmed local HEAD and working-tree status
- Confirmed remote refs and ancestry
- Full list of 11 old branch-only commits
- File-by-file KEEP / ADAPT / DROP table
- API/auth compatibility findings
- CSS/layout/accessibility findings
- Test plan and exact verification evidence
- Blockers and questions requiring user approval

