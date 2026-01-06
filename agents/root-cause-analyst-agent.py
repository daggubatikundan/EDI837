#!/usr/bin/env python3
"""Root Cause Analyst Agent

Parses EDI 835/277CA files (using the provided `EDIParserAgent`) and
extracts CARC (Claim Adjustment Reason Codes) and RARC (Remittance Advice
Remark Codes) from common segments such as `CAS` and `LQ`.

Usage:
  python agents/root-cause-analyst-agent.py --path agents/835-files/* --output summary.json
"""
import argparse
import glob
import json
import csv
import os
from typing import Dict, List, Any

from parser_agent import EDIParserAgent


def _fields_from_segment(seg: Dict[str, Any]) -> List[Any]:
    """Reconstruct ordered fields from a parsed segment dict.

    The parser returns keys like 'field_0','field_1',... for unknown
    segments. This helper returns a list of values ordered by index.
    """
    idxs = []
    for k in seg.keys():
        if k.startswith("field_"):
            try:
                idxs.append(int(k.split("_")[1]))
            except Exception:
                continue
    if not idxs:
        return []
    max_i = max(idxs)
    return [seg.get(f"field_{i}") for i in range(0, max_i + 1)]


def extract_codes(segments: Dict[str, List[Dict[str, Any]]]) -> Dict[str, List[Dict[str, Any]]]:
    """Extract CARC and RARC candidate codes from parsed segments.

    Returns dict with keys: 'carc' and 'rarc', each a list of entries.
    Each entry contains at least: file_segment, code, amount (if available), and raw_fields.
    """
    carc_list = []
    rarc_list = []

    # CAS segments commonly contain CARC codes: CAS*group*REASON1*AMT1*REASON2*AMT2...
    for cas in segments.get("CAS", []):
        fields = _fields_from_segment(cas)
        if not fields:
            continue
        group = fields[1] if len(fields) > 1 else None
        # reason codes typically start at index 2, paired with amounts
        for i in range(2, len(fields), 2):
            code = fields[i] if i < len(fields) else None
            amount = fields[i + 1] if (i + 1) < len(fields) else None
            if code:
                carc_list.append({
                    "segment": "CAS",
                    "group": group,
                    "code": code,
                    "amount": amount,
                    "raw": fields,
                })

    # LQ segments often carry remark codes (RARC/MISC). LQ*qualifier*code
    for lq in segments.get("LQ", []):
        fields = _fields_from_segment(lq)
        if len(fields) >= 3:
            qualifier = fields[1]
            code = fields[2]
            rarc_list.append({
                "segment": "LQ",
                "qualifier": qualifier,
                "code": code,
                "raw": fields,
            })

    # Some implementations place remark codes in other segments (e.g., REF, NTE)
    # Search generically for plausible-looking codes (alphanumeric like 'M123' or 3-digit numeric)
    def _search_generic_for_codes(seg_name: str):
        for seg in segments.get(seg_name, []):
            fields = _fields_from_segment(seg)
            for f in fields[1:]:
                if not f:
                    continue
                # simple heuristics:
                if (len(f) == 3 and f.isdigit()) or (len(f) >= 2 and any(c.isalpha() for c in f)):
                    # treat as remark-like candidate if not already captured
                    rarc_list.append({
                        "segment": seg_name,
                        "code": f,
                        "raw": fields,
                    })

    for seg_name in ("REF", "NTE", "K3", "PLB"):
        _search_generic_for_codes(seg_name)

    return {"carc": carc_list, "rarc": rarc_list}


def analyze_file(fp: str) -> Dict[str, Any]:
    parser = EDIParserAgent()
    try:
        segments = parser.parse_edi(fp)
    except Exception as e:
        return {"error": str(e)}

    codes = extract_codes(segments)
    return codes


def analyze_folder(path_pattern: str) -> Dict[str, Any]:
    results = {}
    files = glob.glob(path_pattern)
    if not files and os.path.isfile(path_pattern):
        files = [path_pattern]

    for fp in files:
        try:
            results[fp] = analyze_file(fp)
        except Exception as e:
            results[fp] = {"error": str(e)}

    return results


def write_csv_from_results(results: Dict[str, Any], csv_path: str):
    rows = []
    for fp, dat in results.items():
        if not isinstance(dat, dict):
            continue
        for c in dat.get("carc", []):
            rows.append({
                "file": fp,
                "segment": c.get("segment"),
                "type": "CARC",
                "code": c.get("code"),
                "amount": c.get("amount"),
                "qualifier": c.get("group"),
            })
        for r in dat.get("rarc", []):
            rows.append({
                "file": fp,
                "segment": r.get("segment"),
                "type": "RARC",
                "code": r.get("code"),
                "amount": None,
                "qualifier": r.get("qualifier"),
            })

    fieldnames = ["file", "segment", "type", "code", "amount", "qualifier"]
    with open(csv_path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def main():
    parser = argparse.ArgumentParser(description="Root Cause Analyst: extract CARC/RARC from EDI files")
    parser.add_argument("--path", default="agents/835-files/*", help="Glob or file path to EDI files")
    parser.add_argument("--output", help="Write JSON summary to this file (stdout if omitted)")
    parser.add_argument("--csv", help="Also write flattened CSV to this path")
    args = parser.parse_args()

    results = analyze_folder(args.path)

    if args.output:
        with open(args.output, "w") as fh:
            json.dump(results, fh, indent=2)
        print(f"Wrote JSON summary to {args.output}")
    else:
        print(json.dumps(results, indent=2))

    if args.csv:
        write_csv_from_results(results, args.csv)
        print(f"Wrote CSV to {args.csv}")


if __name__ == "__main__":
    main()
