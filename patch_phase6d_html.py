#!/usr/bin/env python3
"""
Crate UI Redesign Part A: adds CSS for the two-pane layout — pinned Jade's
List, collapsible section boxes with active-state highlighting, big
JADE-style section headings, and the sortable list-view table with the
active-in-Browse row treatment. Run this from inside mymusicapp/.
"""
import pathlib
import re
import sys

PATH = pathlib.Path("index.html")

NEW_CSS = '''.crate-sidebar-shell{
  display:flex;
  flex-direction:column;
  gap:12px;
}
.jades-list-pinned{
  display:flex;
  align-items:center;
  gap:8px;
  padding:14px 16px;
  font-size:13px;
  font-weight:700;
  letter-spacing:0.04em;
  text-transform:uppercase;
  color:var(--green);
  background:var(--panel);
  border:1.5px solid var(--green);
  cursor:pointer;
}
.jades-list-pinned.active{
  box-shadow:0 0 10px rgba(179,255,0,0.3);
}
.section-box{
  background:var(--panel);
  border:2px solid var(--border);
  transition:border-color 0.15s ease;
}
.section-box.active{
  border-color:var(--green);
  box-shadow:0 0 10px rgba(179,255,0,0.2);
}
.section-box-header{
  display:flex;
  align-items:center;
  justify-content:space-between;
  padding:14px 16px;
  cursor:pointer;
}
.crate-box-title{
  font-family:var(--font-display);
  font-size:18px;
  letter-spacing:0.02em;
  color:var(--green);
  text-transform:uppercase;
  cursor:pointer;
}
.section-box-preview{
  padding:0 16px 14px;
  border-top:1px solid var(--border);
}
.section-box-preview-item{
  padding:8px 4px;
  font-size:11.5px;
  color:var(--text);
  cursor:pointer;
  border-top:1px solid var(--border);
}
.section-box-preview-item:first-child{ border-top:none; }
.section-box-preview-item:hover{ color:var(--green); }
.crate-heading{
  font-family:var(--font-display);
  font-size:26px;
  letter-spacing:0.02em;
  color:var(--green);
  text-transform:uppercase;
}
.crate-list-table{
  width:100%;
  border-collapse:collapse;
  margin-top:14px;
  font-size:12.5px;
}
.crate-list-table th{
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
.crate-list-table th:hover{ color:var(--text); }
.crate-list-row{
  cursor:pointer;
  border-bottom:1px solid var(--border);
}
.crate-list-row:hover{ background:#141414; }
.crate-list-row td{ padding:12px; }
.crate-list-row.browse-active td:first-child{
  color:var(--green);
  font-weight:700;
}
.star.filled{ color:var(--green); }'''

EDITS = [
    (
        '.crate-tree-empty{\n  padding:8px 8px;\n  font-size:10.5px;\n  color:var(--muted);\n  font-style:italic;\n}',
        '.crate-tree-empty{\n  padding:8px 8px;\n  font-size:10.5px;\n  color:var(--muted);\n  font-style:italic;\n}\n' + NEW_CSS,
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

    if ".crate-sidebar-shell{" in text:
        print(f"{PATH}: Crate redesign CSS already present — skipping (already patched).")
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
