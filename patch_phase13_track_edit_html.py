#!/usr/bin/env python3
"""
CSS for the pencil-edit popup (Title/Artist/Album/BPM/Key/Time/Genre/Notes
fields + Appears On section). Run this from inside mymusicapp/.
"""
import pathlib
import re
import sys

PATH = pathlib.Path("index.html")

NEW_CSS = '''.track-edit-overlay{
  position:fixed;
  top:0; left:0; right:0; bottom:0;
  background:rgba(0,0,0,0.75);
  display:flex;
  align-items:center;
  justify-content:center;
  z-index:1000;
  padding:20px;
}
.track-edit-modal{
  background:var(--panel);
  border:2px solid var(--green);
  max-width:480px;
  width:100%;
  max-height:85vh;
  overflow-y:auto;
  padding:20px;
}
.track-edit-fields{
  display:flex;
  flex-direction:column;
  gap:10px;
  margin-top:12px;
}
.track-edit-fields label{
  display:flex;
  flex-direction:column;
  gap:4px;
  font-size:10.5px;
  color:var(--muted);
  text-transform:uppercase;
  letter-spacing:0.05em;
}
.track-edit-appears-on{
  margin-top:16px;
  padding-top:16px;
  border-top:1px solid var(--border);
}'''

EDITS = [
    (
        'input[type="checkbox"]{\n  accent-color:var(--green);\n  cursor:pointer;\n}',
        'input[type="checkbox"]{\n  accent-color:var(--green);\n  cursor:pointer;\n}\n' + NEW_CSS,
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

    if ".track-edit-overlay{" in text:
        print(f"{PATH}: pencil-edit popup CSS already present — skipping (already patched).")
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
