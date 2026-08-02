#!/usr/bin/env python3
"""
Phase 6 step 1: adds CSS for the Crate sidebar tree (headers, carets,
nested items, empty states). Run this from inside mymusicapp/.
"""
import pathlib
import re
import sys

PATH = pathlib.Path("index.html")

EDITS = [
    (
        '.crate-sidebar{ padding:16px; align-self:start; }',
        '''.crate-sidebar{ padding:16px; align-self:start; }
.crate-tree-header{
  display:flex;
  align-items:center;
  gap:6px;
  padding:10px 8px;
  font-size:12px;
  font-weight:700;
  letter-spacing:0.04em;
  text-transform:uppercase;
  cursor:pointer;
  color:var(--muted);
  border-left:3px solid transparent;
}
.crate-tree-header:hover{ background:#141414; color:var(--text); }
.crate-tree-header.active{
  border-left-color:var(--green);
  color:var(--green);
  background:#141414;
}
.crate-tree-header.pinned{ margin-bottom:8px; border-bottom:1px solid var(--border); padding-bottom:14px; }
.tree-caret{ display:inline-block; width:12px; color:var(--muted); font-size:10px; }
.crate-tree-children{ padding-left:20px; }
.crate-tree-item{
  padding:8px 8px;
  font-size:11.5px;
  cursor:pointer;
  color:var(--text);
  border-left:3px solid transparent;
  white-space:nowrap;
  overflow:hidden;
  text-overflow:ellipsis;
}
.crate-tree-item:hover{ background:#141414; }
.crate-tree-item.active{
  border-left-color:var(--green);
  color:var(--green);
  background:#141414;
}
.crate-tree-empty{
  padding:8px 8px;
  font-size:10.5px;
  color:var(--muted);
  font-style:italic;
}''',
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

    if ".crate-tree-header{" in text:
        print(f"{PATH}: crate-tree-header CSS already present — skipping (already patched).")
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
