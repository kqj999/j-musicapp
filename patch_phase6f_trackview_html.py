#!/usr/bin/env python3
"""
Crate UI Redesign Part B: CSS for the universal track-view — sortable table,
bigger/bolder title+artist cells, drag handles, and the filled/outline star
states. Run this from inside mymusicapp/.
"""
import pathlib
import re
import sys

PATH = pathlib.Path("index.html")

NEW_CSS = '''.star.outline{
  color:transparent;
  -webkit-text-stroke:1.5px var(--green);
}
.track-meta-row{
  margin-top:8px;
  color:var(--muted);
  font-size:10.5px;
}
.crate-track-table{
  width:100%;
  border-collapse:collapse;
  font-size:12.5px;
}
.crate-track-table th{
  text-align:left;
  padding:10px 12px;
  font-size:10.5px;
  letter-spacing:0.06em;
  text-transform:uppercase;
  color:var(--muted);
  border-bottom:2px solid var(--border);
  cursor:pointer;
  user-select:none;
  white-space:nowrap;
}
.crate-track-table th:hover{ color:var(--text); }
.crate-track-table tbody tr{
  border-bottom:1px solid var(--border);
}
.crate-track-table tbody tr.dragging{ opacity:0.4; }
.crate-track-table td{
  padding:11px 12px;
  color:var(--text);
}
.track-cell-title{
  font-size:14px;
  font-weight:700;
}
.track-cell-artist{
  font-size:13px;
  font-weight:600;
  color:#ccc;
}
.drag-handle-cell{
  width:20px;
  color:var(--muted);
  cursor:grab;
}'''

EDITS = [
    (
        '.star.filled{ color:var(--green); }',
        '.star.filled{ color:var(--green); }\n' + NEW_CSS,
    ),
]


def make_pattern(old):
    parts = re.split(r'(\s+)', old)
    parts = [p for p in parts if p != '']
    out = []
    for idx, part in enumerate(parts):
        if part.isspace():
            if idx == 0 or idx == len(parts) - 1:
                out.append(r'[ \t]*')
            else:
                out.append(r'\s+')
        else:
            out.append(re.escape(part))
    return re.compile(''.join(out))


def main():
    if not PATH.exists():
        sys.exit(f"Can't find {PATH} — run this from the mymusicapp/ folder.")

    text = PATH.read_text(encoding="utf-8")

    if ".crate-track-table{" in text:
        print(f"{PATH}: track-view CSS already present — skipping (already patched).")
        return

    for i, edit in enumerate(EDITS, 1):
        old, new = edit[0], edit[1]
        mode = edit[2] if len(edit) > 2 else "one"
        pattern = make_pattern(old)
        matches = list(pattern.finditer(text))
        count = len(matches)
        if count == 0:
            first_line = old.strip().splitlines()[0][:50]
            sys.exit(f"Edit {i}/{len(EDITS)} FAILED — expected text not found, even allowing for "
                      f"whitespace/formatting differences. Your {PATH.name} differs from what this "
                      f"script expects in a real way, not just formatting. No changes written.\n"
                      f"Send me the output of: grep -n {first_line!r} {PATH}")
        if mode == "one" and count > 1:
            sys.exit(f"Edit {i}/{len(EDITS)} FAILED — expected text found {count} times, expected 1. "
                      f"No changes written.")
        if mode == "all":
            text = pattern.sub(lambda m: new, text)
        else:
            text = pattern.sub(lambda m: new, text, count=1)
        print(f"Edit {i}/{len(EDITS)} applied ({count} occurrence{'s' if count != 1 else ''}).")

    PATH.write_text(text, encoding="utf-8")
    print(f"\nDone — {PATH} patched successfully.")


if __name__ == "__main__":
    main()
