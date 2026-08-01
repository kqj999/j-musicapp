#!/usr/bin/env python3
"""
Phase 3 frontend patch (app.js): adds the Admin tab — user list + create
user form. Run this from inside mymusicapp/.
"""
import pathlib
import re
import sys

PATH = pathlib.Path("app.js")

EDITS = [
    (
        '''  crate: { lists: [], activeListIndex: 0, loading: false },
  mixes: { list: [], loading: false },
  profile: null,
};''',
        '''  crate: { lists: [], activeListIndex: 0, loading: false },
  mixes: { list: [], loading: false },
  profile: null,
  adminUsers: [],
};''',
    ),
    (
        '''function renderProfileTabVisibility() {
  const btn = document.querySelector('.tab-btn[data-tab="profile"]');
  if (btn) btn.classList.toggle("hidden", !state.username);
}''',
        '''function renderProfileTabVisibility() {
  const btn = document.querySelector('.tab-btn[data-tab="profile"]');
  if (btn) btn.classList.toggle("hidden", !state.username);
}

// Admin tab is admin-tier only (works with either the flat APP_PIN fallback
// or a named admin login — user management doesn't need to know "which
// admin", unlike Profile).
function renderAdminTabVisibility() {
  const btn = document.querySelector('.tab-btn[data-tab="admin"]');
  if (btn) btn.classList.toggle("hidden", state.authLevel !== "admin");
}''',
    ),
    (
        '  renderProfileTabVisibility();',
        '  renderProfileTabVisibility();\n  renderAdminTabVisibility();',
        "all",
    ),
    (
        '''  if (tab === "mixes") renderMixes();
  if (tab === "profile") loadProfile();
}''',
        '''  if (tab === "mixes") renderMixes();
  if (tab === "profile") loadProfile();
  if (tab === "admin") loadAdmin();
}''',
    ),
    (
        '''// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------''',
        '''// ============================================================================
// ADMIN TAB
// ============================================================================
const panelAdmin = document.getElementById("panel-admin");
let adminSelectedTier = "friend";

async function loadAdmin() {
  try {
    const data = await api("/admin/users", { needsAuth: true });
    state.adminUsers = data.users || [];
  } catch (err) {
    toast(err.message);
  }
  renderAdmin();
}

function renderAdmin() {
  const users = state.adminUsers || [];

  panelAdmin.innerHTML = `
    <div class="section-title">✦ Users</div>
    <div id="admin-user-list"></div>

    <div class="section-title" style="margin-top:28px;">✦ Create User</div>
    <div class="seed-row">
      <input class="input" id="admin-new-username" placeholder="username (lowercase, no spaces)" />
      <input class="input" id="admin-new-name" placeholder="Display name" />
    </div>
    <div class="seed-row" style="margin-top:10px; align-items:center;">
      <input class="input" id="admin-new-temppin" placeholder="Temp PIN" style="flex:1;" />
      <div class="pill-row" id="admin-new-tier-pills" style="margin-bottom:0;">
        <button type="button" class="pill ${adminSelectedTier === "friend" ? "active" : ""}" data-tier="friend">Friend</button>
        <button type="button" class="pill ${adminSelectedTier === "admin" ? "active" : ""}" data-tier="admin">Admin</button>
      </div>
      <button class="btn btn-sm btn-primary" id="btn-create-user">Create</button>
    </div>
  `;

  const listEl = document.getElementById("admin-user-list");
  listEl.innerHTML = users.length === 0
    ? `<div class="empty-state">No users yet</div>`
    : users.map((u) => `
        <div class="channel-track">
          <div class="track-info">
            <div class="track-title">${escapeHtml(u.name)} <span style="color:var(--muted);">(${escapeHtml(u.username)})</span></div>
            <div class="track-meta">${escapeHtml(u.tier)}${u.pinIsTemp ? " · temp PIN not yet set" : ""}</div>
          </div>
        </div>`).join("");

  document.getElementById("admin-new-tier-pills").querySelectorAll(".pill").forEach((p) => {
    p.onclick = () => {
      adminSelectedTier = p.dataset.tier;
      renderAdmin();
    };
  });

  document.getElementById("btn-create-user").onclick = async () => {
    const username = document.getElementById("admin-new-username").value.trim();
    const name = document.getElementById("admin-new-name").value.trim();
    const tempPin = document.getElementById("admin-new-temppin").value.trim();
    if (!username || !name || !tempPin) {
      toast("Fill in username, name, and a temp PIN");
      return;
    }
    try {
      await api("/admin/create-user", {
        method: "POST",
        needsAuth: true,
        body: { username, name, tempPin, tier: adminSelectedTier },
      });
      toast(`Created ${name} as ${adminSelectedTier}`);
      loadAdmin();
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
