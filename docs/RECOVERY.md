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
- `origin/redesign/premium-frontend` (11 commits) does not contain `20d410d` and diverges from it.
  Do not treat it as a basis for further work without reconciling first.
