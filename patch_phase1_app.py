#!/usr/bin/env python3
"""
Patches app.js in place: adds the Name field to login, wires the forced
PIN-reset screen for first-time named (Admin/Friend) logins, and adds the
"friend" tier to the session badge. Run this from inside mymusicapp/.
"""
import pathlib
import re
import sys

PATH = pathlib.Path("app.js")

EDITS = [
    (
        '''const state = {
  authLevel: sessionStorage.getItem("jade_auth_level") || "none", // 'none' | 'guest' | 'admin'
  pin: sessionStorage.getItem("jade_pin") || "",
  pinInput: "",
  activeTab: "discover",''',
        '''const state = {
  authLevel: sessionStorage.getItem("jade_auth_level") || "none", // 'none' | 'guest' | 'view' | 'friend' | 'admin'
  pin: sessionStorage.getItem("jade_pin") || "",
  name: sessionStorage.getItem("jade_name") || "",
  username: sessionStorage.getItem("jade_username") || "",
  pinInput: "",
  activeTab: "discover",''',
    ),
    (
        '''async function submitPin(pin) {
  try {
    state.pin = pin;
    const res = await fetch(WORKER_URL + "/auth", { headers: { "X-Pin": pin } });
    const data = await res.json().catch(() => ({}));
    if (!data.level || data.level === "none") throw new Error("invalid");
    state.authLevel = data.level;

    sessionStorage.setItem("jade_pin", pin);
    sessionStorage.setItem("jade_auth_level", state.authLevel);

    pinScreen.classList.add("hidden");
    appShell.classList.remove("hidden");
    state.pinInput = "";
    renderPinDots();
    renderSessionBadge();
    renderTabLocks();
    setActiveTab("discover");
    loadInitialData();
  } catch {
    pinErrorEl.textContent = "Incorrect PIN — try again";
    pinDotsEl.querySelectorAll(".pin-dot").forEach((d) => d.classList.add("error"));
    state.pin = "";
    state.pinInput = "";
    setTimeout(renderPinDots, 500);
  }
}''',
        '''async function submitPin(pin) {
  const nameInput = document.getElementById("login-name-input");
  const name = nameInput ? nameInput.value.trim() : "";
  try {
    state.pin = pin;
    const headers = { "X-Pin": pin };
    if (name) headers["X-Name"] = name;
    const res = await fetch(WORKER_URL + "/auth", { headers });
    const data = await res.json().catch(() => ({}));
    if (!data.level || data.level === "none") throw new Error("invalid");
    state.authLevel = data.level;
    state.name = data.name || "";
    state.username = data.username || "";

    if (data.pinIsTemp) {
      // First login for a named (Admin/Friend) account — force a real PIN
      // before entering the app. Don't persist a session yet.
      pinScreen.classList.add("hidden");
      state.pinInput = "";
      renderPinDots();
      showResetPinScreen(state.username, pin);
      return;
    }

    sessionStorage.setItem("jade_pin", pin);
    sessionStorage.setItem("jade_auth_level", state.authLevel);
    sessionStorage.setItem("jade_name", state.name);
    sessionStorage.setItem("jade_username", state.username);

    pinScreen.classList.add("hidden");
    appShell.classList.remove("hidden");
    state.pinInput = "";
    renderPinDots();
    renderSessionBadge();
    renderTabLocks();
    setActiveTab("discover");
    loadInitialData();
  } catch {
    pinErrorEl.textContent = "Incorrect PIN — try again";
    pinDotsEl.querySelectorAll(".pin-dot").forEach((d) => d.classList.add("error"));
    state.pin = "";
    state.pinInput = "";
    setTimeout(renderPinDots, 500);
  }
}

// ---------------------------------------------------------------------------
// Forced PIN reset (first login for a named Admin/Friend account)
// ---------------------------------------------------------------------------
const resetPinScreen = document.getElementById("reset-pin-screen");
const resetPinDotsEl = document.getElementById("reset-pin-dots");
const resetPinErrorEl = document.getElementById("reset-pin-error");
let resetPinInput = "";
let resetPinUsername = "";
let resetPinCurrentPin = "";

function showResetPinScreen(username, currentPin) {
  resetPinUsername = username;
  resetPinCurrentPin = currentPin;
  resetPinInput = "";
  resetPinErrorEl.textContent = "";
  renderResetPinDots();
  resetPinScreen.classList.remove("hidden");
}

function renderResetPinDots() {
  const dots = resetPinDotsEl.querySelectorAll(".pin-dot");
  dots.forEach((d, i) => {
    d.classList.toggle("filled", i < resetPinInput.length);
    d.classList.remove("error");
  });
}

document.getElementById("reset-pin-keypad").addEventListener("click", (e) => {
  const btn = e.target.closest(".pin-key");
  if (!btn) return;
  const key = btn.dataset.key;
  resetPinErrorEl.textContent = "";

  if (key === "back") {
    resetPinInput = resetPinInput.slice(0, -1);
  } else if (key === "clear") {
    resetPinInput = "";
  } else if (resetPinInput.length < 4) {
    resetPinInput += key;
  }
  renderResetPinDots();

  if (resetPinInput.length === 4) {
    setTimeout(() => submitNewPin(resetPinInput), 150);
  }
});

async function submitNewPin(newPin) {
  try {
    const res = await fetch(WORKER_URL + "/auth/set-pin", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: resetPinUsername, currentPin: resetPinCurrentPin, newPin }),
    });
    const data = await res.json().catch(() => ({}));
    if (!data.ok) throw new Error(data.error || "Could not set PIN");

    state.pin = newPin;
    sessionStorage.setItem("jade_pin", newPin);
    sessionStorage.setItem("jade_auth_level", state.authLevel);
    sessionStorage.setItem("jade_name", state.name);
    sessionStorage.setItem("jade_username", state.username);

    resetPinScreen.classList.add("hidden");
    appShell.classList.remove("hidden");
    renderSessionBadge();
    renderTabLocks();
    setActiveTab("discover");
    loadInitialData();
    toast("PIN set — you\\'re in");
  } catch (err) {
    resetPinErrorEl.textContent = err.message || "Could not set PIN — try again";
    resetPinDotsEl.querySelectorAll(".pin-dot").forEach((d) => d.classList.add("error"));
    resetPinInput = "";
    setTimeout(renderResetPinDots, 500);
  }
}''',
    ),
    (
        '''document.getElementById("btn-lock").onclick = () => {
  sessionStorage.removeItem("jade_pin");
  sessionStorage.removeItem("jade_auth_level");
  state.pin = "";
  state.authLevel = "none";
  appShell.classList.add("hidden");
  landing.classList.remove("hidden");
};

const SESSION_BADGE_LABELS = { admin: "admin", view: "view", guest: "guest" };''',
        '''document.getElementById("btn-lock").onclick = () => {
  sessionStorage.removeItem("jade_pin");
  sessionStorage.removeItem("jade_auth_level");
  sessionStorage.removeItem("jade_name");
  sessionStorage.removeItem("jade_username");
  state.pin = "";
  state.authLevel = "none";
  state.name = "";
  state.username = "";
  appShell.classList.add("hidden");
  landing.classList.remove("hidden");
};

const SESSION_BADGE_LABELS = { admin: "admin", friend: "friend", view: "view", guest: "guest" };''',
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
