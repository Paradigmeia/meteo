# AGENTS.md

## Project
Family dashboard (Ascain) tracking room temp/humidity from Shelly H&T Gen3 sensors plus local Open-Meteo weather. Backend: single-file FastAPI + aiosqlite (SQLite). Frontend: React + Vite, single page, no router.

## Language: write everything in French
Code comments, docstrings, identifiers, test titles, commit messages and docs are French throughout. A new English comment or commit message stands out as foreign.

## Docs (read before changing behavior)
- `SPEC.md` — functional spec (API contract, UI behavior, color palette).
- `PLAN.md` — architecture + decision log ("Décision 1..24"). The repo's code comments cite these (`cf. décision 6`); consult the relevant decision before touching behavior. §2 has the deploy arborescence.
- `PROJECT.md` — status + changelog. After a merged change, append an entry and commit as `docs: update PROJECT.md [meteo]`.
- `docs/ui-mockup.html` — UI reference mockup.

## Commands
Backend (`backend/`):
- Setup: `python3 -m venv venv && venv/bin/pip install -r requirements-dev.txt`
- Run: `venv/bin/uvicorn main:app --port 8042` (loads `backend/.env`: `API_KEY`, `DATABASE_PATH`, `PORT`)
- Tests: `venv/bin/pytest` (single file `test_main.py`). No backend linter/typecheck configured.

Frontend (`frontend/`):
- `npm ci && npm run dev | build | test | lint`
- Dev server has **no proxy**: fetches are relative (`/api/...`) unless `frontend/.env.local` sets `VITE_API_URL=http://127.0.0.1:8042`, so point it at the running backend.

Deploy (server only, runs at `/home/debian/meteo`, never locally):
- `scripts/install.sh` (one-time), `scripts/update.sh` (git pull → `npm ci`+`npm test`+build → restart). `update.sh` re-executes itself after the pull by design. Uses systemd `maison-temp.service` + `nginx/maison-temp.conf`.

## Architecture
- `backend/main.py` routes:
  - `GET|POST /api/releve/{slug}` — Shelly webhook, authenticated. POST uses `X-API-Key` header and requires `temp`; GET carries `key` in the URL (firmware constraint) and receives temp and hum as **two separate events**, sending the literal `"null"`/empty string for an absent measure.
  - `GET /api/sondes`, `GET /api/releves/{slug}` (`?period=` or `?from=&to=`, capped at 365 days), `GET /api/meteo` — **public by design**; CORS allows only `https://meteo.paradigme.me`.
- Frontend: `App.jsx` switches views (Dashboard/Detail/Analyse) by state, no router. Data hooks poll every 30 s. Charts are hand-rolled SVG (`chartUtils.js`, `HistoriqueChart.jsx`, `AnalyseChart.jsx`) — no Chart.js despite SPEC. Icons are inline Tabler SVGs; nginx CSP is `'self'` only, so **never add external assets/URLs**.

## Invariants & gotchas
- `releves.recu_le` is TEXT compared lexicographically by SQLite. Always write ISO-8601 UTC with `+00:00` suffix (`datetime.now(timezone.utc).isoformat()`), never `Z`, and normalize free-range bounds to UTC before `isoformat()` (`_parse_recu_le`). Tests enforce this.
- Non-finite floats: Pydantic accepts `NaN`/`±inf`; a single stored non-finite value breaks JSON serialization of the **whole** read response. Bounds/clamp on write (`models.py`: temp −100..100, humidity clamped 0..100 with ±5 tolerance), neutralize on read (`_finite_or_none`, `_walk_non_finite`).
- Shelly emits each event once and never retries — data loss is permanent. The single uvicorn worker must not block on heavy reads; aggregation intentionally runs in SQL (`_aggregate_sql`, Décision 24), falling back to Python `_aggregate`.
- Backend tests (`test_main.py`: set `API_KEY`/`DATABASE_PATH` in the `config` module **before** importing `main`). The test DB is shared by the whole module: give each test its own sonde slug (`_sonde_de_test`) and disjoint UTC windows. The autouse `_refuse_le_repli_silencieux` fixture fails any test that slides onto the Python aggregation fallback silently.
- Frontend unit tests: colocated `*.test.jsx` files must start with `// @vitest-environment jsdom`.

## Commits
Conventional-style prefix + issue ref, French summary: `fix(#67): …`, `feat(#60): …`, `test(#67): …`, `chore(#38): …`. Branches like `fix/67-aggregation-sql`. Keep the repo's habit of explanatory, multi-assertion tests that cite the issue they protect.

## Périmètre et fin de session

- On s'arrête à la PR ouverte : jamais de merge, de déploiement, de SSH, de commande serveur ni de migration de base. Le déploiement relève de `scripts/install.sh` et `scripts/update.sh`, sur le serveur uniquement.
- En fin de session, poster un commentaire sur la PR (via `gh pr comment`) décrivant en français : ce qui a été fait, ce qui a coincé, et ce dont on n'est pas sûr.