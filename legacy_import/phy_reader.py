"""PHY fixed-record reader for TITAN.W1 legacy .phy files.

VB6 random-access files: fixed-length records, record 1 at offset 0,
no header. Type codes:
  I2  int16 LE
  I4  int32 LE
  R4  float32 LE
  R8  float64 LE
  CURR 8-byte VB Currency (scaled int64 / 10000)
  STR  fixed-length string (raw bytes, may be ANSI or UTF-16)
  BOOL int16 (0 / -1)
  VAR  16-byte VB Variant
  RAW  opaque bytes
"""
import struct
import sys
from dataclasses import dataclass, field
from typing import List, Optional

FORMATS = {
    "I2": ("h", 2),
    "I4": ("i", 4),
    "R4": ("f", 4),
    "R8": ("d", 8),
    "CURR": ("q", 8),
    "BOOL": ("h", 2),
}


@dataclass
class Field:
    name: str
    type: str
    offset: int
    size: Optional[int] = None  # for STR/RAW; None => use FORMATS size
    encoding: str = "ansi"      # ansi | utf16 for STR


@dataclass
class Layout:
    name: str
    record_len: int
    fields: List[Field]

    def resolve_sizes(self) -> None:
        for f in self.fields:
            if f.type in FORMATS:
                f.size = FORMATS[f.type][1]


def read_value(rec: bytes, f: Field):
    off = f.offset
    if f.type in FORMATS:
        fmt, size = FORMATS[f.type]
        return struct.unpack_from("<" + fmt, rec, off)[0]
    if f.type == "STR":
        size = f.size or (len(rec) - off)
        raw = rec[off : off + size]
        if f.encoding == "utf16":
            raw = raw.rstrip(b"\x00")
            try:
                return raw.decode("utf-16-le", errors="replace")
            except Exception:
                return raw.hex()
        # fixed-length string, space/null padded; Arabic text is cp1256
        try:
            return raw.decode("cp1256", errors="replace").rstrip(" \x00")
        except Exception:
            return raw.hex()
    if f.type == "VAR":
        # VB Variant: byte0 = vt, bytes2.. = payload (vt=2 => string BSTR pointer)
        raw = rec[off : off + 16]
        vt = raw[0]
        return {"vt": vt, "raw": raw.hex()}
    if f.type == "RAW":
        size = f.size or (len(rec) - off)
        raw = rec[off : off + size]
        if not raw.strip(b"\x00"):
            return ""
        # summarize opaque regions: keep bytes with any nonzero content, trimmed
        return raw.rstrip(b"\x00").hex()
    raise ValueError(f"unknown type {f.type}")


def decode_record(rec: bytes, layout: Layout):
    layout.resolve_sizes()
    out = {}
    for f in sorted(layout.fields, key=lambda x: x.offset):
        out[f.name] = read_value(rec, f)
    return out


def read_records(path: str, layout: Layout, limit: Optional[int] = None):
    layout.resolve_sizes()
    rec_len = layout.record_len
    with open(path, "rb") as fh:
        data = fh.read()
    n = len(data) // rec_len
    if limit:
        n = min(n, limit)
    for i in range(n):
        rec = data[i * rec_len : (i + 1) * rec_len]
        yield i + 1, decode_record(rec, layout)


def detect_record_len(path: str) -> Optional[int]:
    """Guess record length from file size factors (1..8 records minimum)."""
    import os
    from collections import Counter

    size = os.path.getsize(path)
    if size == 0:
        return None
    cand = [d for d in range(4, 20000) if size % d == 0 and size // d > 0]
    # prefer lengths that give >= 3 records and are plausible (>= 4 bytes)
    cand = [d for d in cand if size // d >= 3]
    if not cand:
        return size
    # pick the smallest plausible record length that yields an integer record count
    cand.sort()
    return cand[0]


if __name__ == "__main__":
    # CLI: phy_reader.py <file> <reclen> [limit]  -> dump decoded fields as JSONL
    path = sys.argv[1]
    reclen = int(sys.argv[2]) if len(sys.argv) > 2 else None
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    if not reclen:
        reclen = detect_record_len(path)
        print(f"# detected reclen={reclen}", file=sys.stderr)
    if not reclen:
        sys.exit("could not determine record length")
    # if no layout known, dump raw header bytes of first records
    with open(path, "rb") as fh:
        data = fh.read()
    n = len(data) // reclen
    print(f"# file={path} size={len(data)} reclen={reclen} records={n}", file=sys.stderr)
    for i in range(min(n, limit)):
        rec = data[i * reclen : (i + 1) * reclen]
        print(f"-- rec {i+1} (first 64B hex): {rec[:64].hex()}")
        # ANSI + UTF16 renders
        print(f"   ansi : {rec[:64].split(chr(0).encode())[0].decode('cp1256', errors='replace')!r}")