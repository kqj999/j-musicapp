#!/usr/bin/env python3
"""
Phase 2 frontend patch (app.js): adds the Profile tab logic — X-Name header
on authenticated calls, profile state, tab show/hide, and the change-PIN /
API-key / badges UI. Run this from inside mymusicapp/.
"""
import pathlib
import re
import sys

PATH = pathlib.Path("app.js")

EDITS = [
    (
        '''async function api(path, { method = "GET", body = null, needsAuth = false } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (needsAuth && state.pin) headers["X-Pin"] = state.pin;
  const res = await fetch(WORKER_URL + path, {''',
        '''async function api(path, { method = "GET", body = null, needsAuth = false } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (needsAuth && state.pin) headers["X-Pin"] = state.pin;
  if (needsAuth && state.username) headers["X-Name"] = state.username;
  const res = await fetch(WORKER_URL + path, {''',
    ),
    (
        '''  crate: { lists: [], activeListIndex: 0, loading: false },
  mixes: { list: [], loading: false },
};''',
        '''  crate: { lists: [], activeListIndex: 0, loading: false },
  mixes: { list: [], loading: false },
  profile: null,
};''',
    ),
    (
        '''  renderSessionBadge();
  renderTabLocks();''',
        '''  renderSessionBadge();
  renderTabLocks();
  renderProfileTabVisibility();''',
        "all",
    ),
    (
        '''function renderTabLocks() {
  const locked = !discoverBrowseVisible();
  document.getElementById("lock-discover").textContent = locked ? "🔒" : "";
  document.getElementById("lock-browse").textContent = locked ? "🔒" : "";
}''',
        '''function renderTabLocks() {
  const locked = !discoverBrowseVisible();
  document.getElementById("lock-discover").textContent = locked ? "🔒" : "";
  document.getElementById("lock-browse").textContent = locked ? "🔒" : "";
}

// Profile tab only makes sense for a named login (Admin/Friend) — View/Guest
// use the shared PINs and have no username to look up.
function renderProfileTabVisibility() {
  const btn = document.querySelector('.tab-btn[data-tab="profile"]');
  if (btn) btn.classList.toggle("hidden", !state.username);
}''',
    ),
    (
        '''  if (tab === "discover") renderDiscover();
  if (tab === "browse") renderBrowse();
  if (tab === "crate") renderCrate();
  if (tab === "mixes") renderMixes();
}''',
        '''  if (tab === "discover") renderDiscover();
  if (tab === "browse") renderBrowse();
  if (tab === "crate") renderCrate();
  if (tab === "mixes") renderMixes();
  if (tab === "profile") loadProfile();
}''',
    ),
    (
        '''// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------''',
        '''// ============================================================================
// PROFILE TAB
// ============================================================================
const panelProfile = document.getElementById("panel-profile");

async function loadProfile() {
  if (!state.username) {
    panelProfile.innerHTML = `
      <div class="panel locked-teaser">
        <h3>Profile</h3>
        <p>Log in with your name (not just the shared PIN) to use Profile.</p>
      </div>`;
    return;
  }
  try {
    state.profile = await api("/profile", { needsAuth: true });
  } catch (err) {
    toast(err.message);
  }
  renderProfile();
}

function renderProfile() {
  const p = state.profile;
  const apiKeyPlaceholder = p && p.hasApiKey
    ? "•••••••• (already set — enter a new key to replace)"
    : "sk-ant-...";

  panelProfile.innerHTML = `
    <div class="section-title">✦ Change PIN</div>
    <div class="seed-row">
      <input class="input" id="profile-current-pin" placeholder="Current PIN" />
      <input class="input" id="profile-new-pin" placeholder="New PIN" />
      <button class="btn btn-sm" id="btn-change-pin">Save</button>
    </div>

    <div class="section-title" style="margin-top:28px;">✦ Anthropic API Key</div>
    <p style="color:var(--muted); font-size:11px; line-height:1.6; max-width:480px;">
      This is separate from your claude.ai login — it's a developer key that lets Discover/Browse
      run under your own account instead of Jade's. Get one at
      <a href="https://console.anthropic.com" target="_blank" rel="noopener" style="color:var(--green);">console.anthropic.com</a>.
    </p>
    <div class="seed-row">
      <input class="input" id="profile-api-key" type="password" placeholder="${escapeAttr(apiKeyPlaceholder)}" />
      <button class="btn btn-sm" id="btn-save-api-key">Save</button>
    </div>

    <div class="section-title" style="margin-top:28px;">✦ Badges</div>
    <div id="profile-badges"></div>
  `;

  const badgesEl = document.getElementById("profile-badges");
  const badges = (p && p.badges) || [];
  badgesEl.innerHTML = badges.length === 0
    ? `<div class="empty-state">No badges yet</div>`
    : badges.map((b) => `
        <div class="channel-track">
          <div class="track-info">
            <div class="track-title">${escapeHtml(b.name || "")}</div>
            <div class="track-meta">${escapeHtml(b.description || "")}</div>
          </div>
        </div>`).join("");

  document.getElementById("btn-change-pin").onclick = async () => {
    const currentPin = document.getElementById("profile-current-pin").value.trim();
    const newPin = document.getElementById("profile-new-pin").value.trim();
    if (!currentPin || !newPin) {
      toast("Enter both PINs");
      return;
    }
    try {
      const res = await fetch(WORKER_URL + "/auth/set-pin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: state.username, currentPin, newPin }),
      });
      const data = await res.json().catch(() => ({}));
      if (!data.ok) throw new Error(data.error || "Could not change PIN");
      state.pin = newPin;
      sessionStorage.setItem("jade_pin", newPin);
      document.getElementById("profile-current-pin").value = "";
      document.getElementById("profile-new-pin").value = "";
      toast("PIN updated");
    } catch (err) {
      toast(err.message);
    }
  };

  document.getElementById("btn-save-api-key").onclick = async () => {
    const apiKey = document.getElementById("profile-api-key").value.trim();
    if (!apiKey) {
      toast("Enter an API key first");
      return;
    }
    try {
      const res = await fetch(WORKER_URL + "/profile/api-key", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: state.username, pin: state.pin, apiKey }),
      });
      const data = await res.json().catch(() => ({}));
      if (!data.ok) throw new Error(data.error || "Could not save API key");
      state.profile = { ...(state.profile || {}), hasApiKey: true };
      document.getElementById("profile-api-key").value = "";
      toast("API key saved");
      renderProfile();
    } catch (err) {
      toast(err.message);
    }
  };
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------''',
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
