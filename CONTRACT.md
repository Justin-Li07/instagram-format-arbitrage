# Format Arbitrage Tracker — build contract

Every builder agent reads this first. Stay inside **your own folders**, and code against the names and signatures defined here, even if another agent hasn't written that part yet. Don't run git commands; the lead commits each piece.

## Stack
- Backend: Python 3.12, FastAPI, SQLAlchemy 2.x (typed `Mapped[...]` models), SQLite at `backend/formatarb.db` (env `FA_DB_URL` overrides), pytest.
- Embeddings: `sentence-transformers` model `all-MiniLM-L6-v2` (384-dim) if it can be installed, otherwise a deterministic fallback (hashed character n-gram TF vector, 384-dim, L2-normalized). Same interface either way.
- Frontend: Vite + React + TypeScript, Recharts, plain CSS. Dev server on 5173, proxies `/api` to `http://localhost:8000`.
- Python deps go in `backend/requirements.txt`. Each agent may append lines, but never delete other lines.

## What the app does
It tracks "format arbitrage" on Instagram Reels. Each FORMAT is treated like a market:
- **PRICE** = median views per reel in that format.
- **SUPPLY** = new reels per week in that format.

The app finds outlier reels, especially from small creators, labels their format and hook, stores every scrape as history, and shows which formats have high price and low supply. It also flags formats whose window is closing (supply rising while price falls).

## Folder ownership
| Agent | Owns |
|---|---|
| data | `backend/app/db/`, `backend/app/ingest/`, `backend/app/embeddings/`, `backend/scripts/`, `backend/tests/test_data_*.py` |
| analytics | `backend/app/analytics/`, `backend/tests/test_analytics_*.py` |
| backend | `backend/app/main.py`, `backend/app/api/`, `backend/app/schemas.py`, `backend/app/config.py`, `backend/tests/test_api_*.py`, `backend/README.md` |
| frontend | `frontend/` |
Shared, lead-owned: `CONTRACT.md`, `README.md`, `SCAN_METHOD.md`, `scripts/` (legacy), `.gitignore`.
`backend/app/__init__.py` and each package's `__init__.py` are created by the agent that owns that package.

## Raw input format (what the scrapers produce)
`data/<niche>/scan-<YYYY-MM-DD>[suffix].jsonl` contains one creator per line:
```json
{"u":"steph.osmak","f":"107K","r":["DdKD20tJSfr 34.4M","Db3uZ4Hpocf 55.8K","DvxviGps5F 5,181"]}
```
`f` is the follower count. It may be null or look like "7,482", "22.7K" or "1.3M". Each `r` entry is a reel code, a space, and its view count. Niches are `engineering`, `university-life`, `startups-tech` and `growth-viral`. The scrape timestamp is the file date, unless the importer is given an explicit `scraped_at`.

Labels input: `data/<niche>/labels-<date>.jsonl` contains one reel per line:
```json
{"code":"DeGHQ_CuBFv","format":"Text-over-B-roll + caption list","hook":"x engineering certifications you can start TONIGHT","caption":"...","duration_s":6.2,"on_screen":"solo creator","style":"text-over-broll","posted_at":null}
```

## Data layer (`backend/app/db/`) — data agent
`backend/app/db/session.py`: `engine`, `SessionLocal`, `get_session()` (a FastAPI dependency that yields a Session), `init_db()` (create_all).
`backend/app/db/models.py`, with a `Base = DeclarativeBase` subclass:
- `Creator`: id, username (unique), niche, first_seen_at, last_seen_at
- `CreatorSnapshot`: id, creator_id→Creator, scraped_at, followers (int|None), scrape_run_id
- `Reel`: id, code (unique), creator_id, caption (str|None), duration_s (float|None), posted_at (datetime|None), first_seen_at
- `ReelSnapshot`: id, reel_id, scraped_at, views (int), likes (int|None), comments (int|None), scrape_run_id
- `ScrapeRun`: id, niche, source (file path or "api"), started_at, creators_count, reels_count
- `Format`: id, name (unique), description, style (str|None)
- `ReelLabel`: reel_id (PK, FK), format_id→Format, hook_text, on_screen, style, labeled_at, labeled_by ("agent"|"user")
- `HookEmbedding`: reel_id (PK), model (str), dim (int), vector (LargeBinary, float32 bytes)

Snapshots are never overwritten. Every scrape adds rows, and that's how history and velocity work.

`backend/app/ingest/parse.py`: `parse_count(s: str|None) -> int|None` ("34.4M" becomes 34400000, "5,181" becomes 5181)
`backend/app/ingest/importer.py`:
- `import_scan_file(session, path: str, niche: str|None=None, scraped_at: datetime|None=None) -> ScrapeRun` (the niche comes from the folder name if not given)
- `import_scan_records(session, records: list[dict], niche: str, scraped_at: datetime, source: str="api") -> ScrapeRun`
- `import_labels(session, records: list[dict]) -> int` (upserts Format and ReelLabel, sets caption/duration/posted_at on Reel, and embeds the hook)
`backend/app/embeddings/embedder.py`:
- `get_embedder()` returns an object with `.model_name: str`, `.dim: int` and `.embed(texts: list[str]) -> numpy.ndarray (n, dim) float32, L2-normalized`
- `upsert_hook_embedding(session, reel_id, text)`
- `similar_hooks(session, text: str|None=None, reel_code: str|None=None, k=10) -> list[tuple[Reel, ReelLabel, float]]` (cosine)
`backend/scripts/import_all.py`: walks `../data/*/scan-*.jsonl` and `labels-*.jsonl` and imports everything, skipping files already imported (match ScrapeRun.source).

## Analytics (`backend/app/analytics/`) — analytics agent
Pure query and compute functions. Each one takes `session` as its first argument and returns plain dicts or dataclasses (JSON-friendly). It must work with only one snapshot per reel, and get richer as more snapshots arrive.
- `outliers.py`: `find_outliers(session, niche=None, min_multiple=10.0, small_creator_max_followers=10_000, small_creator_min_views=100_000, limit=200) -> list[dict]`. Uses each reel's latest snapshot. The multiple = views / the creator's median views (over the latest snapshots). Each dict has: code, url, creator, niche, followers, views, creator_median, multiple, is_small_creator, format, hook.
- `velocity.py`: `reel_velocity(session, niche=None) -> list[dict]`. For reels with at least 2 snapshots: views_per_hour between the latest two snapshots, plus views_per_hour_per_1k_followers. If posted_at is known and there's 1 snapshot, use views / hours since posting. Fields: code, creator, followers, views, views_per_hour, velocity_per_1k_followers, hours_observed.
  `velocity_vs_followers(session, niche=None) -> list[dict]` gives scatter points (followers, views, multiple, velocity, code, creator) and a `bucket` ("<10K", "10–50K", "50–250K", "250K–1M", "1M+").
  `bucket_summary(session, niche=None) -> list[dict]`: per follower bucket, the median views, the outlier rate and the top format.
- `formats.py`: `format_market(session, niche=None, weeks=8) -> list[dict]`. Per Format: price (median latest views of its reels), supply (reels first seen per week, averaged over the last `weeks`), n_reels, n_creators, small_creator_share, score = price / (supply+1), status ("opportunity" | "crowded" | "closing" | "new"), with "closing" meaning supply is up and price is down over the last 2 weeks vs the previous 2.
  `format_timeseries(session, format_id) -> list[dict]` has weekly {week, median_views, new_posts}.
- `hooks.py`: `top_hooks(session, niche=None, limit=50) -> list[dict]` lists hooks of outlier reels with their format, views and multiple.
- `creators.py`: `creator_summary(session, username) -> dict` (follower history, reel count, median, outlier reels) and `list_creators(session, niche=None) -> list[dict]`.

## API (`backend/app/main.py`, `backend/app/api/`) — backend agent
FastAPI app `app` in `backend/app/main.py`. Run it with `uvicorn app.main:app --reload` from `backend/`. Add CORS for localhost:5173. Every route is under `/api`. Pydantic response models go in `app/schemas.py`. Call the data and analytics functions above and don't re-implement them.
- `GET /api/health`
- `GET /api/niches` returns a list of {niche, creators, reels, last_scraped_at}
- `GET /api/runs` lists ScrapeRuns
- `POST /api/ingest/scan` takes JSON {niche, scraped_at?, records:[raw lines]} and returns the run
- `POST /api/ingest/labels` takes JSON {records:[label lines]}
- `GET /api/outliers?niche=&min_multiple=&limit=`
- `GET /api/formats?niche=&weeks=` (the format market)
- `GET /api/formats/{id}/timeseries`
- `GET /api/velocity?niche=` (velocity_vs_followers points) and `GET /api/velocity/buckets?niche=`
- `GET /api/hooks?niche=` and `GET /api/hooks/similar?text=|code=&k=`
- `GET /api/creators?niche=` and `GET /api/creators/{username}`
- `GET /api/reels/{code}` returns the reel with its snapshot history, label and creator

## Frontend (`frontend/`) — frontend agent
A dark, clean dashboard. The niche selector at the top has "All" plus the 4 niches. Pages (react-router):
1. **Formats**: the market table (format, price, supply, score, status badge, creators), sorted by score, with a click-through to a weekly price/supply line chart.
2. **Outliers**: a table of outlier reels (creator, followers, views, × median, format, hook, link to instagram.com/reel/<code>) with a toggle for "small creators only".
3. **Velocity vs following**: a scatter of followers (log x) against views or multiple (log y), coloured by follower bucket, plus a bucket summary cards row.
4. **Hooks**: top hooks list, plus a search box for similar hooks (calls /api/hooks/similar?text=).
5. **Creators**: a list, and a detail page with a follower history line and their reels.
6. **Runs / Import**: the scrape history and a paste box that POSTs raw JSONL lines to /api/ingest/scan.
All API calls go through `frontend/src/api.ts` with typed responses that match the contract. Handle empty and loading states.
