# Backend setup

Python 3.11+ required. From this directory:

    python -m venv .venv
    source .venv/bin/activate   # Windows: .venv\\Scripts\\Activate.ps1
    pip install -r requirements.txt
    cp .env.example .env        # Windows: Copy-Item .env.example .env
    uvicorn app.main:app --reload

API docs: http://127.0.0.1:8000/docs
Health: http://127.0.0.1:8000/health
Tests: pytest -q

Default local SQLite file is devsync.db. Change SECRET_KEY and configure DATABASE_URL/CORS_ORIGINS before any shared deployment. Login accepts OAuth2 form fields username=email and password=password.
