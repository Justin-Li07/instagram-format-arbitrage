"""Import every data/<niche>/scan-*.jsonl and labels-*.jsonl into the DB.

Scan files already imported (matching ScrapeRun.source) are skipped. Label files are
upserts, so re-running them is harmless. Usage (from backend/):

    python scripts/import_all.py [--data-dir ../data]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import select  # noqa: E402

from app.db.models import ScrapeRun  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402
from app.ingest.importer import import_labels_file, import_scan_file, source_for_path  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", default=str(BACKEND_DIR.parent / "data"))
    args = ap.parse_args(argv)
    data_dir = Path(args.data_dir)

    init_db()
    with SessionLocal() as session:
        done = set(session.scalars(select(ScrapeRun.source)))
        n_new = n_skip = 0
        for path in sorted(data_dir.glob("*/scan-*.jsonl")):
            if source_for_path(path) in done:
                n_skip += 1
                print(f"skip   {path.relative_to(data_dir)} (already imported)")
                continue
            run = import_scan_file(session, str(path))
            n_new += 1
            print(f"import {path.relative_to(data_dir)}: run {run.id}, "
                  f"{run.creators_count} creators, {run.reels_count} reels")
        n_labels = 0
        for path in sorted(data_dir.glob("*/labels-*.jsonl")):
            n = import_labels_file(session, str(path))
            n_labels += n
            print(f"labels {path.relative_to(data_dir)}: {n} labels upserted")
    print(f"done: {n_new} scan files imported, {n_skip} skipped, {n_labels} labels")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
