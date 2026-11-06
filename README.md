## Requirements

- Docker
- Python 3.12+
- Node.js 20+

## Setup

```bash
# 1. Environment (one .env at the repo root, used by Docker, the backend and Vite)
cp .env.placeholder .env

# 2. Database
docker compose up -d

# 3. Backend
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m app.seed            # creates tables and demo accounts
uvicorn app.main:app --reload # http://localhost:8000

# 4. Frontend (in a second terminal)
cd frontend
npm install
npm run dev                   # http://localhost:5173
```

Open http://localhost:5173 and pick a demo account to sign in.

`.env.placeholder` is committed with working values on purpose: there are no third-party
services or API keys yet, and the only credential is the local Docker database password.

## Tests

```bash
cd backend && pytest          # needs the database running
cd frontend && npm run build
```

## Reset the database

There are no migrations, so after changing a model:

```bash
docker compose down -v && docker compose up -d
cd backend && python -m app.seed
```
