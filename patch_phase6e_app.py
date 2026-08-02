#!/usr/bin/env python3
"""
Small follow-up to the Crate two-pane redesign: when a specific List/Vibe is
open in the right pane, its name in the left sidebar's section-box preview
now gets a star + green/bold highlight, not just the section box's border.
Run this from inside mymusicapp/.
"""
import pathlib
import re
import sys

PATH = pathlib.Path("app.js")

EDITS = [
    (
        '''              : preview.map((item) => `
                  <div class="section-box-preview-item" data-open-item="${sec.key}" data-item-id="${escapeAttr(String(item.id))}">
                    ${escapeHtml(item.label)}
                  </div>`).join("")''',
        '''              : preview.map((item) => {
                  const isOpen = isActive && String(item.id) === String(c.activeItemId);
                  return `
                  <div class="section-box-preview-item ${isOpen ? "open" : ""}" data-open-item="${sec.key}" data-item-id="${escapeAttr(String(item.id))}">
                    ${isOpen ? '<span class="star filled">★</span> ' : ""}${escapeHtml(item.label)}
                  </div>`;
                }).join("")''',
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

    if "section-box-preview-item ${isOpen" in text:
        print(f"{PATH}: open-item highlight already present — skipping (already patched).")
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
