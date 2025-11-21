# Repository Guidelines

## Project Structure & Module Organization
The monorepo is split by runtime: `nodejs-services/` hosts the Express frontend (`frontend`) and WhatsApp adapters (`wa-clientes`, `wa-proveedores`), while `python-services/` contains the FastAPI AI workloads (`ai-clientes`, `ai-proveedores`, `ai-search`) plus `shared-lib/` helpers and `validate_quality.py`. Docs, env references, and compose files sit at the root (`docs/`, `ENVIRONMENT_MAPPING.md`, `docker-compose.yml`). Each service keeps features under `apps/`, `packages/`, `flows/`, or `templates/`, with tests beside the code in `tests/` or `__tests__/`.

## Build, Test & Development Commands
- `cd nodejs-services/frontend && npm install && npm run dev` — hot-reload the modular frontend/BFF.
- `npm run lint`, `npm run format:check`, `npm run quality-check` — ESLint, Prettier, and audit checks for Node packages.
- `docker compose up -d search-token ai-clientes ai-proveedores` — bring up the Python APIs plus Redis/PostGIS mocks.
- `python python-services/validate_quality.py --service ai-clientes [--fix]` — run the Python quality stack (Black, isort, Flake8, MyPy, Bandit).
- `python -m pytest tests/`, `python -m pytest -m integration`, `pytest --cov=. --cov-report=html` — execute unit, integration, and coverage suites.

## Coding Style & Naming Conventions
Node services use Prettier (2 spaces, single quotes) plus ESLint/`eslint-config-prettier`; keep controllers, routes, and shared utilities under workspace folders (`apps/*`, `packages/*`). Python modules follow Black’s 88-character line width, snake_case files, and FastAPI endpoints, with domain logic in `services/` or `flows/`. Run `validate_quality.py` (or at least `black`, `isort`, `flake8`, `mypy`) before committing, and align Dockerfile names with their services.

## Testing Guidelines
Prefer pytest suites with descriptive names (`test_<feature>_<behavior>`), keeping unit specs under `tests/unit` and integration/load checks under `tests/integration` or `tests/load`. Mock OpenAI, Supabase, Redis, and WhatsApp dependencies via fixtures; reserve live calls for dockerized smoke tests. Keep `pytest --cov=. --cov-report=html` near the baseline and update request/response examples in `docs/` when APIs change.

## Commit & Pull Request Guidelines
Git history follows Conventional Commits (`feat:`, `fix:`, `chore:`); keep summaries imperative and scope each commit narrowly. PRs should outline impact, list affected services, link issues, and attach screenshots or sample payloads for UI/API updates. Document verification steps (commands, pytest output) and call out any new env vars or feature flags reviewers need.

## Security & Configuration Tips
Never commit secrets; copy from service `.env.example` files and keep overrides local. Central mappings live in `ENVIRONMENT_MAPPING.md`, and docker-compose entries should reference those keys. Document new env variables in both the service README and `docs/`, keep PostGIS migrations next to `python-services/ai-proveedores`, and redact WhatsApp webhook URLs or chat logs before sharing.
