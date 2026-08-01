#!/usr/bin/env python3
"""
Patches index.html in place: adds a Name field to the PIN screen (used for
named Admin/Friend logins — leave blank for the shared View/Guest PINs) and
a new forced "set your real PIN" screen shown after a temp-PIN login.
Run this from inside mymusicapp/ (same folder as app.js).
"""
import pathlib
import re
import sys

PATH = pathlib.Path("index.html")

EDITS = [
    (
        '''.session-badge.admin{ color:var(--green); border-color:var(--green); }
.session-badge.view{ color:var(--purple); border-color:var(--purple); }
.session-badge.guest{ color:var(--pink); border-color:var(--pink); }''',
        '''.session-badge.admin{ color:var(--green); border-color:var(--green); }
.session-badge.friend{ color:var(--green); border-color:var(--green); }
.session-badge.view{ color:var(--purple); border-color:var(--purple); }
.session-badge.guest{ color:var(--pink); border-color:var(--pink); }''',
    ),
    (
        '''    <div class="panel panel-glow pin-panel">
      <h2>Enter Pin</h2>
      <p>4-digit access code</p>
      <div class="pin-dots" id="pin-dots">''',
        '''    <div class="panel panel-glow pin-panel">
      <h2>Enter Pin</h2>
      <p>4-digit access code</p>
      <input class="input" id="login-name-input" placeholder="Name (leave blank for shared PIN)" style="margin-bottom:16px;" />
      <div class="pin-dots" id="pin-dots">''',
    ),
    (
        '''      <div style="margin-top:20px;">
        <button class="btn btn-ghost btn-sm" id="btn-pin-back">← back to landing</button>
      </div>
    </div>
  </section>

  <!-- ===================== APP SHELL ===================== -->''',
        '''      <div style="margin-top:20px;">
        <button class="btn btn-ghost btn-sm" id="btn-pin-back">← back to landing</button>
      </div>
    </div>
  </section>

  <!-- ===================== FORCED PIN RESET (first login for named accounts) ===================== -->
  <section id="reset-pin-screen" class="hidden grid-bg">
    <div class="panel panel-glow pin-panel">
      <h2>Set Your PIN</h2>
      <p>First login — choose a real 4-digit PIN</p>
      <div class="pin-dots" id="reset-pin-dots">
        <div class="pin-dot"></div><div class="pin-dot"></div>
        <div class="pin-dot"></div><div class="pin-dot"></div>
      </div>
      <div class="pin-error-msg" id="reset-pin-error"></div>
      <div class="pin-keypad" id="reset-pin-keypad">
        <button class="btn pin-key" data-key="1">1</button>
        <button class="btn pin-key" data-key="2">2</button>
        <button class="btn pin-key" data-key="3">3</button>
        <button class="btn pin-key" data-key="4">4</button>
        <button class="btn pin-key" data-key="5">5</button>
        <button class="btn pin-key" data-key="6">6</button>
        <button class="btn pin-key" data-key="7">7</button>
        <button class="btn pin-key" data-key="8">8</button>
        <button class="btn pin-key" data-key="9">9</button>
        <button class="btn btn-ghost pin-key" data-key="back">⌫</button>
        <button class="btn pin-key" data-key="0">0</button>
        <button class="btn btn-ghost pin-key" data-key="clear">✕</button>
      </div>
    </div>
  </section>

  <!-- ===================== APP SHELL ===================== -->''',
    ),
]

def make_pattern(old):
    parts = re.split(r'(\s+)', old)
    parts = [p for p in parts if p != '']
    out = []
    for idx, part in enumerate(parts):
        if part.isspace():
            # Leading/trailing whitespace: allow indentation drift (spaces/tabs)
            # but never swallow a newline — that would merge this line into
            # the line before/after it. Interior whitespace (between two real
            # tokens) can freely include newlines/blank lines.
            if idx == 0 or idx == len(parts) - 1:
                out.append(r'[ \t]*')
            else:
                out.append(r'\s+')
        else:
            out.append(re.escape(part))
    return re.compile(''.join(out))


def main():
    if not PATH.exists():
        sys.exit(f"Can't find {PATH} — check you're running this from the right folder.")

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
