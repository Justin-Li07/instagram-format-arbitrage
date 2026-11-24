# Format Arbitrage Tracker: backend

FastAPI + SQLAlchemy 2 + SQLite. Every scrape is stored as new snapshot rows, so history and velocity build up over time.

## Setup (Windows, from `backend/`)
```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

## Database
By default the database is `backend/formatarb.db`. Set `FA_DB_URL` to use another one, for example:
```powershell
$env:FA_DB_URL = "sqlite:///C:/tmp/other.db"
```
Tables are created automatically when the server starts (`init_db()`).

## Import the scraped data
This walks `../data/*/scan-*.jsonl` and `labels-*.jsonl` and imports everything. Files that are already imported (matched on `ScrapeRun.source`) are skipped, so you can safely re-run it after each new scrape.
```powershell
.venv\Scripts\python scripts\import_all.py
```
You can also POST raw lines to `/api/ingest/scan` (for example, from the Runs / Import page).

## Run the API
```powershell
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```
- Interactive docs are at http://localhost:8000/docs.
- CORS allows http://localhost:5173 (the Vite dev server). Set `FA_CORS_ORIGINS` (comma-separated) to change it.

## Routes (all under `/api`)
| Method | Path | Notes |
|---|---|---|
| GET | `/health` | |
| GET | `/niches` | `{niche, creators, reels, last_scraped_at}` for the 4 niches |
| GET | `/runs?niche=&limit=` | scrape history, newest first |
| POST | `/ingest/scan` | body `{niche, scraped_at?, records:[{u,f,r}]}`; returns the run (201) |
| POST | `/ingest/labels` | body `{records:[label lines]}`; returns `{imported}` |
| GET | `/outliers?niche=&min_multiple=&limit=` | `min_multiple > 0`; `limit` 1–1000 |
| GET | `/formats?niche=&weeks=` | the format market (price, supply, score, status) |
| GET | `/formats/{id}/timeseries` | weekly median views and new posts; 404 for an unknown format |
| GET | `/velocity?niche=` | scatter points (followers vs views/velocity) |
| GET | `/velocity/buckets?niche=` | summary per follower bucket |
| GET | `/hooks?niche=&limit=` | top hooks from outlier reels |
| GET | `/hooks/similar?text=` or `?code=`, plus `&k=` | similar hooks by cosine similarity; 404 for an unknown code |
| GET | `/creators?niche=` | |
| GET | `/creators/{username}` | 404 for an unknown creator |
| GET | `/reels/{code}` | the reel, its snapshot history, label and creator; 404 for an unknown reel |

`niche` must be one of `engineering`, `university-life`, `startups-tech` or `growth-viral`, or left out for all niches. Any other value returns 422.

## Tests
```powershell
.venv\Scripts\python -m pytest -q
```
The API tests (`tests/test_api_*.py`) run against a temporary SQLite database, so they never touch `formatarb.db`.
