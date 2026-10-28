# Multimodal Construction Intelligence Platform

Full-stack starter built from the supplied requirements: React/Vite frontend, FastAPI backend, multimodal image/text analysis, site safety screening, crack screening, planning and indicative cost estimation, property valuation, daily assistant, weather advisory, and SQLite analysis history.

## Run it
Requirements: Python 3.9+, Node.js 18+.

Backend:
```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```
Frontend (second terminal):
```bash
cd frontend
npm install
npm run dev
```
Open the Vite URL (normally http://localhost:5173), or API docs at http://127.0.0.1:8000/docs.

## AI configuration
Set `AI_API_KEY`, `AI_BASE_URL`, and `AI_MODEL` in `backend/.env`. Default is an OpenAI-compatible chat-completions endpoint. Keep keys in the backend only. Without a key, the application runs in demo mode and clearly reports that image pixels are not analyzed.

## Safety and limitations
All outputs are preliminary decision support, not safety certification, structural diagnosis, formal appraisal, BOQ, or committed schedule. Keep people away from suspected imminent hazards and consult a qualified site professional. Planning rates are rough placeholders. Weather uses Open-Meteo and falls back gracefully if unavailable. Before production deployment add authentication, authorization, HTTPS, rate limits, malware scanning, managed secrets/storage, retention controls, logging, backups and tests.
