#!/usr/bin/env python3
"""
Adds edit (rename + tier toggle) and delete actions to each user row in the
Admin tab. Run this from inside mymusicapp/.
"""
import pathlib
import re
import sys

PATH = pathlib.Path("app.js")

EDITS = [
    (
        '''  const listEl = document.getElementById("admin-user-list");
  listEl.innerHTML = users.length === 0
    ? `<div class="empty-state">No users yet</div>`
    : users.map((u) => `
        <div class="channel-track">
          <div class="track-info">
            <div class="track-title">${escapeHtml(u.name)} <span style="color:var(--muted);">(${escapeHtml(u.username)})</span></div>
            <div class="track-meta">${escapeHtml(u.tier)}${u.pinIsTemp ? " · temp PIN not yet set" : ""}</div>
          </div>
        </div>`).join("");''',
        '''  const listEl = document.getElementById("admin-user-list");
  listEl.innerHTML = users.length === 0
    ? `<div class="empty-state">No users yet</div>`
    : users.map((u) => `
        <div class="channel-track">
          <div class="track-info">
            <div class="track-title">${escapeHtml(u.name)} <span style="color:var(--muted);">(${escapeHtml(u.username)})</span></div>
            <div class="track-meta">${escapeHtml(u.tier)}${u.pinIsTemp ? " · temp PIN not yet set" : ""}</div>
          </div>
          <div style="display:flex; gap:8px;">
            <button class="icon-btn" data-rename="${escapeAttr(u.username)}">rename</button>
            <button class="icon-btn" data-toggle-tier="${escapeAttr(u.username)}" data-current-tier="${escapeAttr(u.tier)}">${u.tier === "admin" ? "make friend" : "make admin"}</button>
            <button class="icon-btn" data-delete-user="${escapeAttr(u.username)}">delete</button>
          </div>
        </div>`).join("");

  listEl.querySelectorAll("[data-rename]").forEach((btn) => {
    btn.onclick = async () => {
      const username = btn.dataset.rename;
      const newName = prompt("New display name:");
      if (!newName) return;
      try {
        await api("/admin/edit-user", { method: "POST", needsAuth: true, body: { username, name: newName } });
        toast("Renamed");
        loadAdmin();
      } catch (err) {
        toast(err.message);
      }
    };
  });

  listEl.querySelectorAll("[data-toggle-tier]").forEach((btn) => {
    btn.onclick = async () => {
      const username = btn.dataset.toggleTier;
      const newTier = btn.dataset.currentTier === "admin" ? "friend" : "admin";
      try {
        await api("/admin/edit-user", { method: "POST", needsAuth: true, body: { username, tier: newTier } });
        toast(`${username} is now ${newTier}`);
        loadAdmin();
      } catch (err) {
        toast(err.message);
      }
    };
  });

  listEl.querySelectorAll("[data-delete-user]").forEach((btn) => {
    btn.onclick = async () => {
      const username = btn.dataset.deleteUser;
      if (!confirm(`Delete user "${username}"? This can't be undone.`)) return;
      try {
        await api("/admin/delete-user", { method: "POST", needsAuth: true, body: { username } });
        toast("Deleted");
        loadAdmin();
      } catch (err) {
        toast(err.message);
      }
    };
  });''',
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
