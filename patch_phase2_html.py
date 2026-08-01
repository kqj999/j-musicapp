#!/usr/bin/env python3
"""
Phase 2 frontend patch (HTML): adds the Profile tab button + panel.
Run this from inside mymusicapp/ (same folder as app.js).
"""
import pathlib
import re
import sys

PATH = pathlib.Path("index.html")

EDITS = [
    (
        '''    <div class="tabbar">
      <button class="tab-btn active" data-tab="discover">Discover<span class="lock-icon" id="lock-discover"></span></button>
      <button class="tab-btn" data-tab="browse">Browse<span class="lock-icon" id="lock-browse"></span></button>
      <button class="tab-btn" data-tab="crate">Crate</button>
      <button class="tab-btn" data-tab="mixes">Mixes</button>
    </div>

    <!-- ---------- DISCOVER ---------- -->
    <div class="tab-panel active" id="panel-discover"></div>

    <!-- ---------- BROWSE ---------- -->
    <div class="tab-panel" id="panel-browse"></div>

    <!-- ---------- CRATE ---------- -->
    <div class="tab-panel" id="panel-crate"></div>

    <!-- ---------- MIXES ---------- -->
    <div class="tab-panel" id="panel-mixes"></div>
  </section>''',
        '''    <div class="tabbar">
      <button class="tab-btn active" data-tab="discover">Discover<span class="lock-icon" id="lock-discover"></span></button>
      <button class="tab-btn" data-tab="browse">Browse<span class="lock-icon" id="lock-browse"></span></button>
      <button class="tab-btn" data-tab="crate">Crate</button>
      <button class="tab-btn" data-tab="mixes">Mixes</button>
      <button class="tab-btn hidden" data-tab="profile">Profile</button>
    </div>

    <!-- ---------- DISCOVER ---------- -->
    <div class="tab-panel active" id="panel-discover"></div>

    <!-- ---------- BROWSE ---------- -->
    <div class="tab-panel" id="panel-browse"></div>

    <!-- ---------- CRATE ---------- -->
    <div class="tab-panel" id="panel-crate"></div>

    <!-- ---------- MIXES ---------- -->
    <div class="tab-panel" id="panel-mixes"></div>

    <!-- ---------- PROFILE ---------- -->
    <div class="tab-panel" id="panel-profile"></div>
  </section>''',
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
