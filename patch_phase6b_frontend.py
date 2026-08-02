#!/usr/bin/env python3
"""
Phase 6 step 2 frontend: full Vibe curation in Crate — create, rename,
delete, view actual tracks, add/remove tracks. Run this from inside
mymusicapp/.
"""
import pathlib
import re
import sys

PATH = pathlib.Path("app.js")

EDITS = [
    (
        '''    ${isAdmin && c.expanded.lists ? '<button class="btn btn-sm" id="btn-new-list" style="margin-top:10px; width:100%;">+ New List</button>' : ""}
  `;''',
        '''    ${isAdmin && c.expanded.lists ? '<button class="btn btn-sm" id="btn-new-list" style="margin-top:10px; width:100%;">+ New List</button>' : ""}
    ${state.username && c.expanded.vibes ? '<button class="btn btn-sm" id="btn-new-vibe" style="margin-top:10px; width:100%;">+ New Vibe</button>' : ""}
  `;''',
    ),
    (
        '''  if (isAdmin) {
    const newListBtn = document.getElementById("btn-new-list");
    if (newListBtn) {
      newListBtn.onclick = () => {
        const name = prompt("List name:", "Untitled List");
        if (!name) return;
        state.crate.lists.push({ name, locked: false, tracks: [] });
        state.crate.activeSection = "lists";
        state.crate.activeListIndex = state.crate.lists.length - 1;
        persistCrate();
        renderCrateSidebar();
        renderCrateMain();
      };
    }
  }
}''',
        '''  if (isAdmin) {
    const newListBtn = document.getElementById("btn-new-list");
    if (newListBtn) {
      newListBtn.onclick = () => {
        const name = prompt("List name:", "Untitled List");
        if (!name) return;
        state.crate.lists.push({ name, locked: false, tracks: [] });
        state.crate.activeSection = "lists";
        state.crate.activeListIndex = state.crate.lists.length - 1;
        persistCrate();
        renderCrateSidebar();
        renderCrateMain();
      };
    }
  }

  const newVibeBtn = document.getElementById("btn-new-vibe");
  if (newVibeBtn) {
    newVibeBtn.onclick = async () => {
      const name = prompt("Vibe name:", "Untitled Vibe");
      if (!name) return;
      try {
        const data = await api("/vibes", { method: "POST", needsAuth: true, body: { name } });
        state.crate.vibesList.push({ id: data.vibe.id, name: data.vibe.name, trackCount: 0 });
        state.crate.activeSection = "vibes";
        state.crate.activeVibeId = data.vibe.id;
        renderCrateSidebar();
        renderCrateMain();
      } catch (err) {
        toast(err.message);
      }
    };
  }
}''',
    ),
    (
        '''  if (section === "vibes") {
    if (state.crate.activeVibeId) renderCrateMainVibeDetail(el);
    else renderCrateVibesOverview(el);
    return;
  }''',
        '''  if (section === "vibes") {
    if (state.crate.activeVibeId) loadCrateVibeDetail(el);
    else renderCrateVibesOverview(el);
    return;
  }''',
    ),
    (
        '''function renderCrateMainVibeDetail(el) {
  const vibe = state.crate.vibesList.find((v) => v.id === state.crate.activeVibeId);
  if (!vibe) {
    renderCrateVibesOverview(el);
    return;
  }
  el.innerHTML = `
    <div class="channel-head">
      <h4>✦ ${escapeHtml(vibe.name)}</h4>
      <button class="icon-btn" id="btn-back-to-vibes">← all vibes</button>
    </div>
    <div class="empty-state" style="padding:30px 0;">${vibe.trackCount} track${vibe.trackCount === 1 ? "" : "s"} — full track browsing coming in a future step</div>
  `;
  document.getElementById("btn-back-to-vibes").onclick = () => {
    state.crate.activeVibeId = null;
    renderCrateMain();
    renderCrateSidebar();
  };
}''',
        '''async function loadCrateVibeDetail(el) {
  el.innerHTML = `<div class="empty-state"><span class="spinner"></span> Loading...</div>`;
  try {
    const detail = await api(`/vibes/${state.crate.activeVibeId}`, { needsAuth: true });
    renderCrateVibeDetail(el, detail);
  } catch (err) {
    el.innerHTML = errorCardHtml(err.message);
  }
}

function renderCrateVibeDetail(el, vibe) {
  el.innerHTML = `
    <div class="channel-head">
      <h4>✦ ${escapeHtml(vibe.name)}</h4>
      <div style="display:flex; gap:8px; flex-wrap:wrap;">
        <button class="icon-btn" id="btn-back-to-vibes">← all vibes</button>
        <button class="icon-btn" id="btn-rename-vibe">rename</button>
        <button class="icon-btn" id="btn-delete-vibe">delete</button>
      </div>
    </div>
    <div class="seed-row" style="margin-top:14px;">
      <input class="input" id="vibe-manual-artist" placeholder="Artist" style="flex:1;" />
      <input class="input" id="vibe-manual-track" placeholder="Track" style="flex:1;" />
      <button class="btn btn-sm" id="btn-vibe-add-manual">Add</button>
    </div>
    <div id="vibe-tracks" style="margin-top:10px;"></div>
  `;

  const tracksEl = document.getElementById("vibe-tracks");
  if (vibe.tracks.length === 0) {
    tracksEl.innerHTML = `<div class="empty-state">No tracks in this Vibe yet</div>`;
  } else {
    tracksEl.innerHTML = vibe.tracks
      .map(
        (t) => `
      <div class="crate-track-row">
        <span class="drag-handle"></span>
        <div>
          <div class="track-title">${escapeHtml(t.artist)}${t.track ? " — " + escapeHtml(t.track) : ""}</div>
          <div class="track-meta">${escapeHtml(t.genre || "")}${t.bpm ? " · " + escapeHtml(String(t.bpm)) + " BPM" : ""}${t.key ? " · " + escapeHtml(t.key) : ""}</div>
        </div>
        <span></span>
        <button class="icon-btn" data-remove-track="${escapeAttr(t.id)}">✕</button>
      </div>`
      )
      .join("");
  }

  document.getElementById("btn-back-to-vibes").onclick = () => {
    state.crate.activeVibeId = null;
    renderCrateMain();
    renderCrateSidebar();
  };

  document.getElementById("btn-rename-vibe").onclick = async () => {
    const name = prompt("Rename vibe:", vibe.name);
    if (!name) return;
    try {
      await api("/vibes/rename", { method: "POST", needsAuth: true, body: { vibeId: vibe.id, name } });
      const idx = state.crate.vibesList.findIndex((v) => v.id === vibe.id);
      if (idx !== -1) state.crate.vibesList[idx].name = name;
      loadCrateVibeDetail(el);
      renderCrateSidebar();
    } catch (err) {
      toast(err.message);
    }
  };

  document.getElementById("btn-delete-vibe").onclick = async () => {
    if (!confirm(`Delete "${vibe.name}"? This removes the Vibe (tracks stay in Imports).`)) return;
    try {
      await api("/vibes/delete", { method: "POST", needsAuth: true, body: { vibeId: vibe.id } });
      state.crate.vibesList = state.crate.vibesList.filter((v) => v.id !== vibe.id);
      state.crate.activeVibeId = null;
      renderCrateMain();
      renderCrateSidebar();
      toast("Deleted");
    } catch (err) {
      toast(err.message);
    }
  };

  document.getElementById("btn-vibe-add-manual").onclick = async () => {
    const artist = document.getElementById("vibe-manual-artist").value.trim();
    const track = document.getElementById("vibe-manual-track").value.trim();
    if (!artist) return;
    try {
      await api("/vibes/add-track", { method: "POST", needsAuth: true, body: { vibeId: vibe.id, artist, track } });
      const idx = state.crate.vibesList.findIndex((v) => v.id === vibe.id);
      if (idx !== -1) state.crate.vibesList[idx].trackCount += 1;
      loadCrateVibeDetail(el);
    } catch (err) {
      toast(err.message);
    }
  };

  tracksEl.querySelectorAll("[data-remove-track]").forEach((btn) => {
    btn.onclick = async () => {
      try {
        await api("/vibes/remove-track", {
          method: "POST",
          needsAuth: true,
          body: { vibeId: vibe.id, uploadId: btn.dataset.removeTrack },
        });
        const idx = state.crate.vibesList.findIndex((v) => v.id === vibe.id);
        if (idx !== -1) state.crate.vibesList[idx].trackCount -= 1;
        loadCrateVibeDetail(el);
      } catch (err) {
        toast(err.message);
      }
    };
  });
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
