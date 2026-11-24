"""Find format-arbitrage outliers in a scan file.
Usage: python outliers.py <scan.jsonl>
Rule (from the seed reel): views >= 10x creator's median, or creator < 10K followers with 100K+ views."""
import json, sys, statistics

def num(s):
    s = s.replace(",", "").strip()
    mult = {"K": 1e3, "M": 1e6}.get(s[-1:], 1)
    return float(s[:-1] if mult != 1 else s) * mult

rows = []
for line in open(sys.argv[1], encoding="utf-8"):
    c = json.loads(line)
    f = num(c["f"]) if c.get("f") else None
    reels = [(r.split(" ", 1)[0], num(r.split(" ", 1)[1])) for r in c["r"] if " " in r]
    med = statistics.median(v for _, v in reels)
    for code, v in reels:
        mult = v / med
        small = f is not None and f < 10_000 and v >= 100_000
        if mult >= 10 or small:
            rows.append((mult, c["u"], f, med, code, v, small))

rows.sort(reverse=True)
print(f"{'x median':>8}  {'creator':22} {'followers':>9} {'median':>8} {'views':>9}  url")
for mult, u, f, med, code, v, small in rows:
    print(f"{mult:8.1f}  {u:22} {f or 0:9.0f} {med:8.0f} {v:9.0f}  https://www.instagram.com/reel/{code}/" + ("  <10K acct" if small else ""))
print(f"\n{len(rows)} outliers")
