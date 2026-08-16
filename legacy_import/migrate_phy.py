"""Historical-import runner for TITAN.W1 .phy money files.

Usage:
    python3 migrate_phy.py /path/to/Files/DBI [--out out_dir] [--limit N]

For each recognized .phy file:
  - known layout  -> decode and write <name>.jsonl (one JSON record per line)
  - unknown file  -> write a raw <name>.reclen report (detected length + hex header)
so unknown layouts can be filled in later from samples.

Also emits a summary `migration_report.json` describing what was imported
vs what needs layout work.
"""
import argparse
import json
import os
import sys

from phy_reader import detect_record_len
from layouts import ALL_LAYOUTS, layout_for
from phy_reader import decode_record


def migrate_file(path: str, out_dir: str, limit: int):
    base = os.path.basename(path)
    lay = layout_for(path)
    if lay is None:
        reclen = detect_record_len(path)
        report = {
            "file": path,
            "layout": None,
            "record_len": reclen,
            "status": "UNKNOWN_LAYOUT",
        }
        # raw header dump to seed future layout work
        with open(path, "rb") as fh:
            data = fh.read(2048)
        dump = os.path.join(out_dir, base + ".hex")
        with open(dump, "w") as fh:
            rl = reclen or 1
            k = 0
            for i in range(0, min(len(data), rl * 6), rl):
                rec = data[i : i + rl]
                fh.write(f"-- rec {k+1}\n{rec.hex()}\n")
                k += 1
        report["hex_dump"] = dump
        return report

    lay.resolve_sizes()
    out_path = os.path.join(out_dir, base + ".jsonl")
    count = 0
    with open(path, "rb") as fh:
        data = fh.read()
    rec_len = lay.record_len
    total = len(data) // rec_len
    with open(out_path, "w", encoding="utf-8") as out:
        for i in range(min(total, limit) if limit else total):
            rec = data[i * rec_len : (i + 1) * rec_len]
            fields = decode_record(rec, lay)
            fields["_recno"] = i + 1
            fields["_source"] = path
            out.write(json.dumps(fields, ensure_ascii=False) + "\n")
            count += 1
    return {
        "file": path,
        "layout": lay.name,
        "record_len": rec_len,
        "records_total": total,
        "records_written": count,
        "jsonl": out_path,
        "status": "OK",
    }


def main():
    ap = argparse.ArgumentParser(description="Migrate TITAN .phy money files")
    ap.add_argument("dbi_dir", help="legacy Files/DBI directory (or single .phy file)")
    ap.add_argument("--out", default=".", help="output directory for JSONL + report")
    ap.add_argument("--limit", type=int, default=None, help="cap records per file")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    src = args.dbi_dir
    if os.path.isdir(src):
        files = sorted(
            os.path.join(src, f)
            for f in os.listdir(src)
            if f.lower().endswith((".phy", ".Phy", ".PHY"))
        )
    else:
        files = [src]

    results = []
    for f in files:
        if not os.path.isfile(f):
            continue
        try:
            r = migrate_file(f, args.out, args.limit)
            results.append(r)
            tag = r["status"]
            print(f"[{tag:14s}] {os.path.basename(f)}")
            if tag == "OK":
                print(f"   reclen={r['record_len']} records={r['records_written']}/{r['records_total']} -> {r['jsonl']}")
            else:
                print(f"   reclen={r['record_len']} hex dump -> {r.get('hex_dump')}")
        except Exception as e:
            results.append({"file": f, "status": "ERROR", "error": str(e)})
            print(f"[ERROR         ] {os.path.basename(f)}: {e}")

    report_path = os.path.join(args.out, "migration_report.json")
    with open(report_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, ensure_ascii=False)
    print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()