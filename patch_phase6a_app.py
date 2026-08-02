#!/usr/bin/env python3
"""
Phase 6 step 1: Crate sidebar becomes a collapsible tree (Jade's List, Lists,
Vibes, Genres, Imports) with a polymorphic main panel (section overview vs
item detail). Lists keeps all existing functionality unchanged. Vibes shows
real names/counts (reusing the Phase 5 /vibes endpoint) with full track
browsing deferred. Genres/Imports/Jade's List are structural placeholders
for now. Run this from inside mymusicapp/.
"""
import pathlib
import re
import sys

PATH = pathlib.Path("app.js")

EDITS = [
    (
        '  crate: { lists: [], activeListIndex: 0, loading: false },',
        '''  crate: {
    lists: [], activeListIndex: -1, loading: false,
    activeSection: "lists",
    activeVibeId: null,
    vibesList: [], vibesLoaded: false,
    expanded: { lists: true, vibes: false, genres: false, imports: false },
  },''',
    ),
    (
        '''function loadInitialData() {
  if (state.authLevel === "admin") {
    loadCrate();
  } else if (state.authLevel === "guest" || state.authLevel === "view") {
    loadPublicCrate();
  }
  loadMixes();
}''',
        '''function loadInitialData() {
  if (state.authLevel === "admin") {
    loadCrate();
  } else if (state.authLevel === "guest" || state.authLevel === "view" || state.authLevel === "friend") {
    loadPublicCrate();
  }
  loadCrateVibes();
  loadMixes();
}''',
    ),
    (
        '''async function loadPublicCrate() {
  try {
    const data = await api("/public-crate", { needsAuth: true });
    state.crate.lists = data.lists || [];
  } catch (err) {
    toast(err.message);
  } finally {
    if (state.activeTab === "crate") renderCrate();
  }
}''',
        '''async function loadPublicCrate() {
  try {
    const data = await api("/public-crate", { needsAuth: true });
    state.crate.lists = data.lists || [];
  } catch (err) {
    toast(err.message);
  } finally {
    if (state.activeTab === "crate") renderCrate();
  }
}

// Vibes are per-user (Admin or Friend, named login required) — reuses the
// GET /vibes endpoint Import already built in Phase 5. Guest/View/flat-PIN
// admin just see an empty Vibes section.
async function loadCrateVibes() {
  if (!state.username) {
    state.crate.vibesList = [];
    state.crate.vibesLoaded = true;
    return;
  }
  try {
    const data = await api("/vibes", { needsAuth: true });
    state.crate.vibesList = data.vibes || [];
  } catch (err) {
    state.crate.vibesList = [];
  }
  state.crate.vibesLoaded = true;
  if (state.activeTab === "crate") renderCrate();
}''',
    ),
    (
        '''function renderCrate() {
  if (state.authLevel === "none") {
    panelCrate.innerHTML = `<div class="panel locked-teaser"><h3>Crate</h3><p>Enter a PIN to view saved lists.</p></div>`;
    return;
  }

  const lists = state.crate.lists;
  const isAdmin = state.authLevel === "admin";

  panelCrate.innerHTML = `
    <div class="crate-layout">
      <div class="panel crate-sidebar">
        <div class="section-title">✦ Lists</div>
        <div id="crate-list-items"></div>
        ${isAdmin ? '<button class="btn btn-sm" id="btn-new-list" style="margin-top:10px; width:100%;">+ New List</button>' : ""}
      </div>
      <div class="panel crate-main" id="crate-main"></div>
    </div>
  `;

  renderCrateSidebar();
  renderCrateMain();

  if (isAdmin) {
    document.getElementById("btn-new-list").onclick = () => {
      const name = prompt("List name:", "Untitled List");
      if (!name) return;
      state.crate.lists.push({ name, locked: false, tracks: [] });
      state.crate.activeListIndex = state.crate.lists.length - 1;
      persistCrate();
      renderCrate();
    };
  }
}

function renderCrateSidebar() {
  const el = document.getElementById("crate-list-items");
  const lists = state.crate.lists;
  if (lists.length === 0) {
    el.innerHTML = `<div class="empty-state" style="padding:20px 0;">No lists yet</div>`;
    return;
  }
  el.innerHTML = lists
    .map(
      (l, i) => `
    <div class="crate-list-item ${i === state.crate.activeListIndex ? "active" : ""}" data-i="${i}">
      <span>${escapeHtml(l.name)}</span>
      <span>${l.locked ? "🔒" : "🔓"}</span>
    </div>`
    )
    .join("");
  el.querySelectorAll(".crate-list-item").forEach((item) => {
    item.onclick = () => {
      state.crate.activeListIndex = +item.dataset.i;
      renderCrate();
    };
  });
}

function renderCrateMain() {
  const el = document.getElementById("crate-main");
  const list = state.crate.lists[state.crate.activeListIndex];
  const isAdmin = state.authLevel === "admin";

  if (!list) {
    el.innerHTML = `<div class="empty-state">Select or create a list</div>`;
    return;
  }

  el.innerHTML = `
    <div class="channel-head">
      <h4>${escapeHtml(list.name)}</h4>
      <div style="display:flex; gap:8px; flex-wrap:wrap;">
        <button class="icon-btn" id="btn-play-list">▶ play list</button>
        ${isAdmin ? `<button class="icon-btn" id="btn-toggle-lock">${list.locked ? "🔒 locked" : "🔓 unlocked"}</button>` : ""}
        ${isAdmin ? `<button class="icon-btn" id="btn-rename-list">rename</button>` : ""}
        ${isAdmin ? `<button class="icon-btn" id="btn-delete-list">delete</button>` : ""}
        <button class="icon-btn" id="btn-export-list">export .txt</button>
      </div>
    </div>
    ${isAdmin ? `
      <div class="seed-row" style="margin-top:14px;">
        <input class="input" id="manual-artist" placeholder="Artist" style="flex:1;" />
        <input class="input" id="manual-track" placeholder="Track" style="flex:1;" />
        <button class="btn btn-sm" id="btn-add-manual">Add</button>
      </div>
    ` : ""}
    <div id="crate-tracks" style="margin-top:10px;"></div>
  `;

  renderCrateTracks(list, isAdmin);

  if (isAdmin) {
    document.getElementById("btn-toggle-lock").onclick = () => {
      list.locked = !list.locked;
      persistCrate();
      renderCrate();
    };
    document.getElementById("btn-rename-list").onclick = () => {
      const name = prompt("Rename list:", list.name);
      if (!name) return;
      list.name = name;
      persistCrate();
      renderCrate();
    };
    document.getElementById("btn-delete-list").onclick = () => {
      if (!confirm(`Delete "${list.name}"?`)) return;
      state.crate.lists.splice(state.crate.activeListIndex, 1);
      state.crate.activeListIndex = 0;
      persistCrate();
      renderCrate();
    };
    document.getElementById("btn-add-manual").onclick = () => {
      const artist = document.getElementById("manual-artist").value.trim();
      const track = document.getElementById("manual-track").value.trim();
      if (!artist) return;
      list.tracks.push({ artist, track, label: "", bpm: "", key: "", notes: "", audioUrl: null });
      persistCrate();
      renderCrate();
    };
  }

  document.getElementById("btn-export-list").onclick = () => exportListAsTxt(list);
  document.getElementById("btn-play-list").onclick = () => playQueue(list.tracks, 0, list.name);
}''',
        '''function renderCrate() {
  if (state.authLevel === "none") {
    panelCrate.innerHTML = `<div class="panel locked-teaser"><h3>Crate</h3><p>Enter a PIN to view saved lists.</p></div>`;
    return;
  }

  panelCrate.innerHTML = `
    <div class="crate-layout">
      <div class="panel crate-sidebar" id="crate-sidebar"></div>
      <div class="panel crate-main" id="crate-main"></div>
    </div>
  `;

  renderCrateSidebar();
  renderCrateMain();
}

const CRATE_TREE_SECTIONS = [
  { key: "lists", label: "Lists" },
  { key: "vibes", label: "Vibes" },
  { key: "genres", label: "Genres" },
  { key: "imports", label: "Imports" },
];

function renderCrateSidebar() {
  const el = document.getElementById("crate-sidebar");
  const isAdmin = state.authLevel === "admin";
  const c = state.crate;

  const childrenHtml = (key) => {
    if (!c.expanded[key]) return "";
    if (key === "lists") {
      if (c.lists.length === 0) return `<div class="crate-tree-empty">No lists yet</div>`;
      return c.lists.map((l, i) => `
        <div class="crate-tree-item ${c.activeSection === "lists" && c.activeListIndex === i ? "active" : ""}" data-open-list="${i}">
          ${escapeHtml(l.name)}
        </div>`).join("");
    }
    if (key === "vibes") {
      if (c.vibesList.length === 0) return `<div class="crate-tree-empty">No vibes yet</div>`;
      return c.vibesList.map((v) => `
        <div class="crate-tree-item ${c.activeSection === "vibes" && c.activeVibeId === v.id ? "active" : ""}" data-open-vibe="${escapeAttr(v.id)}">
          ${escapeHtml(v.name)}
        </div>`).join("");
    }
    return `<div class="crate-tree-empty">Coming in a future step</div>`;
  };

  el.innerHTML = `
    <div class="crate-tree-header pinned ${c.activeSection === "jadeslist" ? "active" : ""}" data-section="jadeslist">
      <span class="star">★</span> Jade's List
    </div>
    ${CRATE_TREE_SECTIONS.map((sec) => `
      <div class="crate-tree-section">
        <div class="crate-tree-header ${c.activeSection === sec.key ? "active" : ""}" data-section="${sec.key}">
          <span class="tree-caret">${c.expanded[sec.key] ? "▾" : "▸"}</span> ${sec.label}
        </div>
        <div class="crate-tree-children">${childrenHtml(sec.key)}</div>
      </div>
    `).join("")}
    ${isAdmin && c.expanded.lists ? '<button class="btn btn-sm" id="btn-new-list" style="margin-top:10px; width:100%;">+ New List</button>' : ""}
  `;

  el.querySelector('[data-section="jadeslist"]').onclick = () => {
    state.crate.activeSection = "jadeslist";
    renderCrateSidebar();
    renderCrateMain();
  };

  el.querySelectorAll('.crate-tree-header[data-section]:not(.pinned)').forEach((headerEl) => {
    headerEl.onclick = () => {
      const key = headerEl.dataset.section;
      state.crate.expanded[key] = !state.crate.expanded[key];
      state.crate.activeSection = key;
      if (key === "lists") state.crate.activeListIndex = -1;
      if (key === "vibes") state.crate.activeVibeId = null;
      renderCrateSidebar();
      renderCrateMain();
    };
  });

  el.querySelectorAll("[data-open-list]").forEach((item) => {
    item.onclick = (e) => {
      e.stopPropagation();
      state.crate.activeSection = "lists";
      state.crate.activeListIndex = +item.dataset.openList;
      renderCrateSidebar();
      renderCrateMain();
    };
  });

  el.querySelectorAll("[data-open-vibe]").forEach((item) => {
    item.onclick = (e) => {
      e.stopPropagation();
      state.crate.activeSection = "vibes";
      state.crate.activeVibeId = item.dataset.openVibe;
      renderCrateSidebar();
      renderCrateMain();
    };
  });

  if (isAdmin) {
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
}

function renderCrateMain() {
  const el = document.getElementById("crate-main");
  const isAdmin = state.authLevel === "admin";
  const section = state.crate.activeSection;

  if (section === "jadeslist") {
    el.innerHTML = `<div class="empty-state">Jade's List — coming in a future step</div>`;
    return;
  }
  if (section === "genres") {
    el.innerHTML = `<div class="empty-state">Genres — coming in a future step</div>`;
    return;
  }
  if (section === "imports") {
    el.innerHTML = `<div class="empty-state">Imports — coming in a future step</div>`;
    return;
  }
  if (section === "vibes") {
    if (state.crate.activeVibeId) renderCrateMainVibeDetail(el);
    else renderCrateVibesOverview(el);
    return;
  }

  if (state.crate.activeListIndex >= 0 && state.crate.lists[state.crate.activeListIndex]) {
    renderCrateMainList(el, isAdmin);
  } else {
    renderCrateListsOverview(el);
  }
}

function renderCrateListsOverview(el) {
  const lists = state.crate.lists;
  el.innerHTML = `
    <div class="channel-head"><h4>Lists</h4></div>
    ${lists.length === 0 ? `<div class="empty-state">No lists yet</div>` : `
      <div class="channel-grid">
        ${lists.map((l, i) => `
          <div class="panel channel-card" data-open-list="${i}" style="cursor:pointer;">
            <div class="channel-head">
              <h4>${escapeHtml(l.name)}</h4>
              <span>${l.locked ? "🔒" : "🔓"}</span>
            </div>
            <div class="empty-state" style="padding:10px 0;">${l.tracks.length} track${l.tracks.length === 1 ? "" : "s"}</div>
          </div>
        `).join("")}
      </div>
    `}
  `;
  el.querySelectorAll("[data-open-list]").forEach((card) => {
    card.onclick = () => {
      state.crate.activeListIndex = +card.dataset.openList;
      renderCrateMain();
      renderCrateSidebar();
    };
  });
}

function renderCrateVibesOverview(el) {
  const vibes = state.crate.vibesList;
  el.innerHTML = `
    <div class="channel-head"><h4>Vibes</h4></div>
    ${vibes.length === 0 ? `<div class="empty-state">No vibes yet — import some tracks first</div>` : `
      <div class="channel-grid">
        ${vibes.map((v) => `
          <div class="panel channel-card" data-open-vibe="${escapeAttr(v.id)}" style="cursor:pointer;">
            <div class="channel-head"><h4>✦ ${escapeHtml(v.name)}</h4></div>
            <div class="empty-state" style="padding:10px 0;">${v.trackCount} track${v.trackCount === 1 ? "" : "s"}</div>
          </div>
        `).join("")}
      </div>
    `}
  `;
  el.querySelectorAll("[data-open-vibe]").forEach((card) => {
    card.onclick = () => {
      state.crate.activeVibeId = card.dataset.openVibe;
      renderCrateMain();
      renderCrateSidebar();
    };
  });
}

function renderCrateMainVibeDetail(el) {
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
}

function renderCrateMainList(el, isAdmin) {
  const list = state.crate.lists[state.crate.activeListIndex];

  if (!list) {
    el.innerHTML = `<div class="empty-state">Select or create a list</div>`;
    return;
  }

  el.innerHTML = `
    <div class="channel-head">
      <h4>${escapeHtml(list.name)}</h4>
      <div style="display:flex; gap:8px; flex-wrap:wrap;">
        <button class="icon-btn" id="btn-play-list">▶ play list</button>
        ${isAdmin ? `<button class="icon-btn" id="btn-toggle-lock">${list.locked ? "🔒 locked" : "🔓 unlocked"}</button>` : ""}
        ${isAdmin ? `<button class="icon-btn" id="btn-rename-list">rename</button>` : ""}
        ${isAdmin ? `<button class="icon-btn" id="btn-delete-list">delete</button>` : ""}
        <button class="icon-btn" id="btn-export-list">export .txt</button>
      </div>
    </div>
    ${isAdmin ? `
      <div class="seed-row" style="margin-top:14px;">
        <input class="input" id="manual-artist" placeholder="Artist" style="flex:1;" />
        <input class="input" id="manual-track" placeholder="Track" style="flex:1;" />
        <button class="btn btn-sm" id="btn-add-manual">Add</button>
      </div>
    ` : ""}
    <div id="crate-tracks" style="margin-top:10px;"></div>
  `;

  renderCrateTracks(list, isAdmin);

  if (isAdmin) {
    document.getElementById("btn-toggle-lock").onclick = () => {
      list.locked = !list.locked;
      persistCrate();
      renderCrate();
    };
    document.getElementById("btn-rename-list").onclick = () => {
      const name = prompt("Rename list:", list.name);
      if (!name) return;
      list.name = name;
      persistCrate();
      renderCrate();
    };
    document.getElementById("btn-delete-list").onclick = () => {
      if (!confirm(`Delete "${list.name}"?`)) return;
      state.crate.lists.splice(state.crate.activeListIndex, 1);
      state.crate.activeListIndex = -1;
      persistCrate();
      renderCrate();
    };
    document.getElementById("btn-add-manual").onclick = () => {
      const artist = document.getElementById("manual-artist").value.trim();
      const track = document.getElementById("manual-track").value.trim();
      if (!artist) return;
      list.tracks.push({ artist, track, label: "", bpm: "", key: "", notes: "", audioUrl: null });
      persistCrate();
      renderCrate();
    };
  }

  document.getElementById("btn-export-list").onclick = () => exportListAsTxt(list);
  document.getElementById("btn-play-list").onclick = () => playQueue(list.tracks, 0, list.name);
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
