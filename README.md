# Format Arbitrage Tracker

Finds Instagram Reel **formats** that are paying off (high median views, called PRICE) but that few people are posting yet (low new posts per week, called SUPPLY), especially formats where small creators are breaking out.

- `backend/`: FastAPI + SQLite. Stores every scrape as history, plus hook embeddings and analytics.
- `frontend/`: React dashboard.
- `SCAN_METHOD.md`: how the scraper agents collect data.
- `CONTRACT.md`: architecture and API contract.

Raw scraped data (`data/`) and the local database are not committed.
