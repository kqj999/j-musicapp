#!/usr/bin/env python3
"""
Crate UI Redesign Part A: two-pane layout with Jade's List pinned, 4
collapsible section boxes (My Lists, Vibe Curation, Genres, Imported) with
previews and active-state highlighting, and a sortable list-view table
(Title / # of Tracks / Last Updated) with the Curate button and the
active-in-Browse star/bump-to-top treatment for Vibes.

Unifies the old activeListIndex/activeVibeId fields into one activeItemId,
so this also touches the existing track-detail functions (renderCrateMainList,
loadCrateVibeDetail, renderCrateVibeDetail) — their content is unchanged for
now, just the field rename. Their full redesign (universal track-view header,
description field, search, sortable columns, Edit mode) is Part B, coming next.

Run this from inside mymusicapp/.
"""
import pathlib
import re
import sys

PATH = pathlib.Path("app.js")

EDITS = [
    (
        '''  crate: {
    lists: [], activeListIndex: -1, loading: false,
    activeSection: "lists",
    activeVibeId: null,
    vibesList: [], vibesLoaded: false,
    expanded: { lists: true, vibes: false, genres: false, imports: false },
  },''',
        '''  crate: {
    lists: [], loading: false,
    activeSection: "lists", // "jadeslist" | "lists" | "vibes" | "genres" | "imports"
    activeItemId: null,     // list index (number) for Lists, vibe id (string) for Vibes
    vibesList: [], vibesLoaded: false,
    expanded: { lists: true, vibes: false, genres: false, imports: false },
    sort: { lists: { col: "name", dir: "asc" }, vibes: { col: "name", dir: "asc" } },
  },''',
    ),
    (
        '  const target = state.crate.lists[state.crate.activeListIndex] || state.crate.lists[0];',
        '  const target = state.crate.lists[state.crate.activeItemId] || state.crate.lists[0];',
    ),
    (
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
    ${state.username && c.expanded.vibes ? '<button class="btn btn-sm" id="btn-new-vibe" style="margin-top:10px; width:100%;">+ New Vibe</button>' : ""}
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
    if (state.crate.activeVibeId) loadCrateVibeDetail(el);
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
}''',
        '''function renderCrate() {
  if (state.authLevel === "none") {
    panelCrate.innerHTML = `<div class="panel locked-teaser"><h3>Crate</h3><p>Enter a PIN to view saved lists.</p></div>`;
    return;
  }

  panelCrate.innerHTML = `
    <div class="crate-layout">
      <div class="crate-sidebar-shell" id="crate-sidebar"></div>
      <div class="panel crate-main" id="crate-main"></div>
    </div>
  `;

  renderCrateSidebar();
  renderCrateMain();
}

const CRATE_SECTIONS = [
  { key: "lists", label: "My Lists" },
  { key: "vibes", label: "Vibe Curation" },
  { key: "genres", label: "Genres" },
  { key: "imports", label: "Imported" },
];

// Returns up to 5 preview items { id, label } for a section box, plus the
// full count (used nowhere yet but kept for parity with a possible "+N more").
function crateSectionPreviewItems(key) {
  const c = state.crate;
  if (key === "lists") {
    return c.lists.slice(0, 5).map((l, i) => ({ id: i, label: l.name }));
  }
  if (key === "vibes") {
    return c.vibesList.slice(0, 5).map((v) => ({ id: v.id, label: v.name }));
  }
  return [];
}

function renderCrateSidebar() {
  const el = document.getElementById("crate-sidebar");
  const c = state.crate;

  const jadesListHtml = `
    <div class="jades-list-pinned ${c.activeSection === "jadeslist" ? "active" : ""}" data-section="jadeslist">
      <span class="star">★</span> <span class="crate-box-title">Jade's List</span>
    </div>
  `;

  const boxesHtml = CRATE_SECTIONS.map((sec) => {
    const expanded = c.expanded[sec.key];
    const isActive = c.activeSection === sec.key;
    const preview = expanded ? crateSectionPreviewItems(sec.key) : [];
    return `
      <div class="section-box ${isActive ? "active" : ""}">
        <div class="section-box-header">
          <span class="crate-box-title" data-open-section="${sec.key}">${sec.label}</span>
          <span class="tree-caret" data-toggle-section="${sec.key}">${expanded ? "▾" : "▸"}</span>
        </div>
        ${expanded ? `
          <div class="section-box-preview">
            ${preview.length === 0
              ? `<div class="crate-tree-empty">${sec.key === "lists" || sec.key === "vibes" ? "Nothing here yet" : "Coming in a future step"}</div>`
              : preview.map((item) => `
                  <div class="section-box-preview-item" data-open-item="${sec.key}" data-item-id="${escapeAttr(String(item.id))}">
                    ${escapeHtml(item.label)}
                  </div>`).join("")
            }
          </div>
        ` : ""}
      </div>
    `;
  }).join("");

  el.innerHTML = jadesListHtml + boxesHtml;

  el.querySelector('[data-section="jadeslist"]').onclick = () => {
    state.crate.activeSection = "jadeslist";
    state.crate.activeItemId = null;
    renderCrateSidebar();
    renderCrateMain();
  };

  // Clicking the title opens the section's list-view (and expands its box).
  el.querySelectorAll("[data-open-section]").forEach((titleEl) => {
    titleEl.onclick = () => {
      const key = titleEl.dataset.openSection;
      state.crate.activeSection = key;
      state.crate.activeItemId = null;
      state.crate.expanded[key] = true;
      renderCrateSidebar();
      renderCrateMain();
    };
  });

  // The caret ONLY toggles the preview open/closed — doesn't touch the right pane.
  el.querySelectorAll("[data-toggle-section]").forEach((caretEl) => {
    caretEl.onclick = (e) => {
      e.stopPropagation();
      const key = caretEl.dataset.toggleSection;
      state.crate.expanded[key] = !state.crate.expanded[key];
      renderCrateSidebar();
    };
  });

  // Clicking a preview item opens that item's track-view directly.
  el.querySelectorAll("[data-open-item]").forEach((itemEl) => {
    itemEl.onclick = () => {
      const key = itemEl.dataset.openItem;
      const rawId = itemEl.dataset.itemId;
      state.crate.activeSection = key;
      state.crate.activeItemId = key === "lists" ? +rawId : rawId;
      renderCrateSidebar();
      renderCrateMain();
    };
  });
}

function crateSortIndicator(section, col) {
  const s = state.crate.sort[section];
  if (!s || s.col !== col) return "";
  return s.dir === "asc" ? " ▲" : " ▼";
}

function crateSortRows(section, rows) {
  const s = state.crate.sort[section];
  if (!s) return rows;
  const sorted = [...rows].sort((a, b) => {
    let av = a[s.col], bv = b[s.col];
    if (s.col === "trackCount") { av = av || 0; bv = bv || 0; }
    else { av = (av || "").toString().toLowerCase(); bv = (bv || "").toString().toLowerCase(); }
    if (av < bv) return s.dir === "asc" ? -1 : 1;
    if (av > bv) return s.dir === "asc" ? 1 : -1;
    return 0;
  });
  // Vibes active-in-Browse always float to the top, regardless of sort.
  if (section === "vibes") {
    sorted.sort((a, b) => (b.isActiveInBrowse ? 1 : 0) - (a.isActiveInBrowse ? 1 : 0));
  }
  return sorted;
}

function renderCrateListView(el, section) {
  const c = state.crate;
  const sectionLabel = CRATE_SECTIONS.find((s) => s.key === section).label;

  if (section === "genres" || section === "imports") {
    el.innerHTML = `
      <div class="channel-head"><h4 class="crate-heading">${escapeHtml(sectionLabel)}</h4></div>
      <div class="empty-state" style="padding:40px 0;">Coming in a future step</div>
    `;
    return;
  }

  const isLists = section === "lists";
  const rawRows = isLists
    ? c.lists.map((l, i) => ({ id: i, name: l.name, trackCount: l.tracks.length, updatedAt: l.updatedAt || null }))
    : c.vibesList.map((v) => ({ id: v.id, name: v.name, trackCount: v.trackCount, updatedAt: v.updatedAt || null, isActiveInBrowse: v.isActiveInBrowse }));

  const rows = crateSortRows(section, rawRows);
  const curateLabel = isLists ? "+ New List" : "+ Curate Vibe";
  const canCurate = isLists ? state.authLevel === "admin" : !!state.username;

  el.innerHTML = `
    <div class="channel-head">
      <h4 class="crate-heading">${escapeHtml(sectionLabel)}</h4>
      ${canCurate ? `<button class="btn btn-sm btn-primary" id="btn-curate">${curateLabel}</button>` : ""}
    </div>
    ${rows.length === 0 ? `<div class="empty-state" style="padding:40px 0;">Nothing here yet</div>` : `
      <table class="crate-list-table">
        <thead>
          <tr>
            <th data-sort-col="name">Title${crateSortIndicator(section, "name")}</th>
            <th data-sort-col="trackCount"># of Tracks${crateSortIndicator(section, "trackCount")}</th>
            <th data-sort-col="updatedAt">Last Updated${crateSortIndicator(section, "updatedAt")}</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((r) => `
            <tr class="crate-list-row ${r.isActiveInBrowse ? "browse-active" : ""}" data-open-row="${escapeAttr(String(r.id))}">
              <td>${r.isActiveInBrowse ? '<span class="star filled">★</span> ' : ""}${escapeHtml(r.name)}</td>
              <td>${r.trackCount}</td>
              <td>${r.updatedAt ? new Date(r.updatedAt).toLocaleDateString() : "—"}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `}
  `;

  el.querySelectorAll("[data-sort-col]").forEach((th) => {
    th.onclick = () => {
      const col = th.dataset.sortCol;
      const s = state.crate.sort[section];
      if (s.col === col) s.dir = s.dir === "asc" ? "desc" : "asc";
      else { s.col = col; s.dir = "asc"; }
      renderCrateMain();
    };
  });

  el.querySelectorAll("[data-open-row]").forEach((row) => {
    row.onclick = () => {
      const rawId = row.dataset.openRow;
      state.crate.activeItemId = isLists ? +rawId : rawId;
      renderCrateMain();
      renderCrateSidebar();
    };
  });

  const curateBtn = document.getElementById("btn-curate");
  if (curateBtn) {
    curateBtn.onclick = isLists ? crateCreateNewList : crateCreateNewVibe;
  }
}

function crateCreateNewList() {
  const name = prompt("List name:", "Untitled List");
  if (!name) return;
  const now = new Date().toISOString();
  state.crate.lists.push({ name, locked: false, tracks: [], createdAt: now, updatedAt: now });
  state.crate.activeSection = "lists";
  state.crate.activeItemId = state.crate.lists.length - 1;
  persistCrate();
  renderCrateSidebar();
  renderCrateMain();
}

async function crateCreateNewVibe() {
  const name = prompt("Vibe name:", "Untitled Vibe");
  if (!name) return;
  try {
    const data = await api("/vibes", { method: "POST", needsAuth: true, body: { name } });
    state.crate.vibesList.push({
      id: data.vibe.id, name: data.vibe.name, trackCount: 0,
      updatedAt: data.vibe.updatedAt, isActiveInBrowse: false,
    });
    state.crate.activeSection = "vibes";
    state.crate.activeItemId = data.vibe.id;
    renderCrateSidebar();
    renderCrateMain();
  } catch (err) {
    toast(err.message);
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

  if (state.crate.activeItemId === null) {
    renderCrateListView(el, section);
    return;
  }

  if (section === "vibes") {
    loadCrateVibeDetail(el);
    return;
  }

  if (section === "lists" && state.crate.lists[state.crate.activeItemId]) {
    renderCrateMainList(el, isAdmin);
    return;
  }

  renderCrateListView(el, section);
}''',
    ),
    (
        'state.crate.activeVibeId',
        'state.crate.activeItemId',
        'all',
    ),
    (
        'state.crate.activeListIndex',
        'state.crate.activeItemId',
        'all',
    ),
    (
        'state.crate.activeItemId = -1;',
        'state.crate.activeItemId = null;',
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

    if "section-box-header" in text:
        print(f"{PATH}: Crate redesign (Part A) already present — skipping (already patched).")
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
