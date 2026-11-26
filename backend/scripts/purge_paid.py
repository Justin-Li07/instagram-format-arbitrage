"""Wipe paid-partnership reels: they are brand-boosted, so they must never reach the data or analytics.

1. Paid codes = every {"paid": true} record in data/*/labels-*.jsonl (kept there as a permanent blocklist) plus
   every reel already flagged is_paid_partnership in the DB.
2. Delete those reels (snapshots, labels, hook embeddings) from the DB.
3. Strip those reels from data/*/scan-*.jsonl so a re-import cannot bring them back.

Safe to re-run; import_all.py runs it at the end. Usage (from backend/): python scripts/purge_paid.py [--data-dir ../data]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import delete, select  # noqa: E402

from app.db.models import HookEmbedding, Reel, ReelLabel, ReelSnapshot  # noqa: E402
from app.db.session import SessionLocal, init_db  # noqa: E402


def paid_codes_from_labels(data_dir: Path) -> set[str]:
    codes: set[str] = set()
    for p in sorted(data_dir.glob("*/labels-*.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("paid") and rec.get("code"):
                codes.add(rec["code"])
    return codes


def strip_scan_files(data_dir: Path, paid: set[str]) -> int:
    removed = 0
    for p in sorted(data_dir.glob("*/scan-*.jsonl")):
        out, changed = [], False
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            keep = [r for r in rec.get("r", []) if r.split(" ", 1)[0] not in paid]
            if len(keep) != len(rec.get("r", [])):
                removed += len(rec["r"]) - len(keep)
                changed = True
                rec["r"] = keep
            out.append(json.dumps(rec, ensure_ascii=False))
        if changed:
            p.write_text("\n".join(out) + "\n", encoding="utf-8")
    return removed


def purge(data_dir: Path) -> dict:
    init_db()
    paid = paid_codes_from_labels(data_dir)
    with SessionLocal() as s:
        paid |= set(s.scalars(select(Reel.code).where(Reel.is_paid_partnership.is_(True))))
        ids = list(s.scalars(select(Reel.id).where(Reel.code.in_(paid)))) if paid else []
        if ids:
            s.execute(delete(HookEmbedding).where(HookEmbedding.reel_id.in_(ids)))
            s.execute(delete(ReelLabel).where(ReelLabel.reel_id.in_(ids)))
            s.execute(delete(ReelSnapshot).where(ReelSnapshot.reel_id.in_(ids)))
            s.execute(delete(Reel).where(Reel.id.in_(ids)))
        s.commit()
    return {"paid_codes": len(paid), "db_reels_deleted": len(ids), "scan_entries_stripped": strip_scan_files(data_dir, paid)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-dir", default=str(BACKEND_DIR.parent / "data"))
    args = ap.parse_args(argv)
    print(purge(Path(args.data_dir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
