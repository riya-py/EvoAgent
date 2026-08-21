# AI Arena

Multi-agent LLM competition/evolution system. Built phase by phase — see
`backend/PHASES.md` for the full 20-phase roadmap and current status.

## Setup

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

## Run

```bash
uvicorn app.main:app --reload
```

Then check:

```bash
curl http://localhost:8000/api/health
```

## Test

```bash
python3 -m pytest tests/ -v
```