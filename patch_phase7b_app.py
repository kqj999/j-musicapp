#!/usr/bin/env python3
"""
Genres Step 1 frontend: the Genres section box becomes real — auto-populated
folders (with Uncategorized pinned first), a simple Title/# of Tracks
list-view, and a read-only track-view reusing the same sortable-table/search
helpers already built for Lists and Vibes. Mass-assign/reassignment is Step 2.
Run this from inside mymusicapp/.
"""
import pathlib
import re
import sys

PATH = pathlib.Path("app.js")

EDITS = [
    (
        '    sort: { lists: { col: "name", dir: "asc" }, vibes: { col: "name", dir: "asc" } },',
        '''    sort: { lists: { col: "name", dir: "asc" }, vibes: { col: "name", dir: "asc" } },
    genresList: [], uncategorizedCount: 0, genresLoaded: false,''',
    ),
    (
        '''  loadCrateVibes();
  loadMixes();
}''',
        '''  loadCrateVibes();
  loadCrateGenres();
  loadMixes();
}''',
    ),
    (
        '''async function loadCrateVibes() {
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
        '''async function loadCrateVibes() {
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
}

// Genre is computed from Uploads, not its own stored entity like Vibes —
// same load pattern, different endpoint.
async function loadCrateGenres() {
  if (!state.username) {
    state.crate.genresList = [];
    state.crate.uncategorizedCount = 0;
    state.crate.genresLoaded = true;
    return;
  }
  try {
    const data = await api("/genres", { needsAuth: true });
    state.crate.genresList = data.genres || [];
    state.crate.uncategorizedCount = data.uncategorizedCount || 0;
  } catch (err) {
    state.crate.genresList = [];
    state.crate.uncategorizedCount = 0;
  }
  state.crate.genresLoaded = true;
  if (state.activeTab === "crate") renderCrate();
}''',
    ),
    (
        '''function crateSectionPreviewItems(key) {
  const c = state.crate;
  if (key === "lists") {
    return c.lists.slice(0, 5).map((l, i) => ({ id: i, label: l.name }));
  }
  if (key === "vibes") {
    return c.vibesList.slice(0, 5).map((v) => ({ id: v.id, label: v.name }));
  }
  return [];
}''',
        '''function crateSectionPreviewItems(key) {
  const c = state.crate;
  if (key === "lists") {
    return c.lists.slice(0, 5).map((l, i) => ({ id: i, label: l.name }));
  }
  if (key === "vibes") {
    return c.vibesList.slice(0, 5).map((v) => ({ id: v.id, label: v.name }));
  }
  if (key === "genres") {
    const items = c.uncategorizedCount > 0 ? [{ id: "Uncategorized", label: "Uncategorized" }] : [];
    return items.concat(c.genresList.slice(0, Math.max(0, 5 - items.length)).map((g) => ({ id: g.name, label: g.name })));
  }
  return [];
}''',
    ),
    (
        '''              ? `<div class="crate-tree-empty">${sec.key === "lists" || sec.key === "vibes" ? "Nothing here yet" : "Coming in a future step"}</div>`''',
        '''              ? `<div class="crate-tree-empty">${sec.key === "lists" || sec.key === "vibes" || sec.key === "genres" ? "Nothing here yet" : "Coming in a future step"}</div>`''',
    ),
    (
        '''function renderCrateListView(el, section) {
  const c = state.crate;
  const sectionLabel = CRATE_SECTIONS.find((s) => s.key === section).label;

  if (section === "genres" || section === "imports") {
    el.innerHTML = `
      <div class="channel-head"><h4 class="crate-heading">${escapeHtml(sectionLabel)}</h4></div>
      <div class="empty-state" style="padding:40px 0;">Coming in a future step</div>
    `;
    return;
  }

  const isLists = section === "lists";''',
        '''function renderCrateListView(el, section) {
  const c = state.crate;
  const sectionLabel = CRATE_SECTIONS.find((s) => s.key === section).label;

  if (section === "imports") {
    el.innerHTML = `
      <div class="channel-head"><h4 class="crate-heading">${escapeHtml(sectionLabel)}</h4></div>
      <div class="empty-state" style="padding:40px 0;">Coming in a future step</div>
    `;
    return;
  }

  if (section === "genres") {
    renderCrateGenresListView(el);
    return;
  }

  const isLists = section === "lists";''',
    ),
    (
        '''  const curateBtn = document.getElementById("btn-curate");
  if (curateBtn) {
    curateBtn.onclick = isLists ? crateCreateNewList : crateCreateNewVibe;
  }
}

function crateCreateNewList() {''',
        '''  const curateBtn = document.getElementById("btn-curate");
  if (curateBtn) {
    curateBtn.onclick = isLists ? crateCreateNewList : crateCreateNewVibe;
  }
}

// Genres is a simple two-column list-view (no "Last Updated" — Genre is
// computed from Uploads, not its own stored entity, so there's no natural
// per-folder timestamp to show). Uncategorized is pinned first when present.
function renderCrateGenresListView(el) {
  const genres = state.crate.genresList;
  const uncatCount = state.crate.uncategorizedCount;

  el.innerHTML = `
    <div class="channel-head"><h4 class="crate-heading">Genres</h4></div>
    ${genres.length === 0 && uncatCount === 0 ? `<div class="empty-state" style="padding:40px 0;">Nothing here yet</div>` : `
      <table class="crate-list-table">
        <thead>
          <tr>
            <th>Title</th>
            <th># of Tracks</th>
          </tr>
        </thead>
        <tbody>
          ${uncatCount > 0 ? `
            <tr class="crate-list-row" data-open-genre="Uncategorized">
              <td><em>Uncategorized</em></td>
              <td>${uncatCount}</td>
            </tr>
          ` : ""}
          ${genres.map((g) => `
            <tr class="crate-list-row" data-open-genre="${escapeAttr(g.name)}">
              <td>${escapeHtml(g.name)}</td>
              <td>${g.trackCount}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `}
  `;

  el.querySelectorAll("[data-open-genre]").forEach((row) => {
    row.onclick = () => {
      state.crate.activeItemId = row.dataset.openGenre;
      renderCrateMain();
      renderCrateSidebar();
    };
  });
}

function crateCreateNewList() {''',
    ),
    (
        '''  if (section === "vibes") {
    loadCrateVibeDetail(el);
    return;
  }

  if (section === "lists" && state.crate.lists[state.crate.activeItemId]) {''',
        '''  if (section === "vibes") {
    loadCrateVibeDetail(el);
    return;
  }

  if (section === "genres") {
    loadCrateGenreDetail(el);
    return;
  }

  if (section === "lists" && state.crate.lists[state.crate.activeItemId]) {''',
    ),
    (
        'function renderCrateMainList(el, isAdmin) {',
        '''// ---------------------------------------------------------------------------
// Genre track-view — read-only browsing for Step 1 (mass-assign/reassign
// comes in Step 2). No rename/delete/description — Genre isn't a stored
// entity, it's computed live from Uploads' own genre field.
// ---------------------------------------------------------------------------

async function loadCrateGenreDetail(el) {
  el.innerHTML = `<div class="empty-state"><span class="spinner"></span> Loading...</div>`;
  try {
    const detail = await api(`/genres/${encodeURIComponent(state.crate.activeItemId)}`, { needsAuth: true });
    renderCrateGenreDetail(el, detail);
  } catch (err) {
    el.innerHTML = errorCardHtml(err.message);
  }
}

function renderCrateGenreDetail(el, genre) {
  crateResetTrackViewIfNewItem(`genres:${genre.name}`);

  const rows = crateFilterAndSortTracks(genre.tracks);

  el.innerHTML = `
    <div class="channel-head">
      <h4 class="crate-heading">${escapeHtml(genre.name)}</h4>
      <button class="icon-btn" id="btn-back-to-genres">← all genres</button>
    </div>

    <div class="track-meta-row">${genre.tracks.length} track${genre.tracks.length === 1 ? "" : "s"}</div>

    <div class="seed-row" style="margin-top:14px;">
      <input class="input" id="track-search" placeholder="Search tracks..." value="${escapeAttr(state.crate.trackSearchQuery)}" style="flex:1;" />
    </div>

    <div id="genre-tracks" style="margin-top:12px;"></div>
  `;

  document.getElementById("genre-tracks").innerHTML = crateTrackTableHtml(rows, { dragEnabled: false, showRemove: false });
  crateWireTrackSortHeaders(el, () => renderCrateGenreDetail(el, genre));

  document.getElementById("track-search").oninput = (e) => {
    state.crate.trackSearchQuery = e.target.value;
    renderCrateGenreDetail(el, genre);
  };

  document.getElementById("btn-back-to-genres").onclick = () => {
    state.crate.activeItemId = null;
    renderCrateMain();
    renderCrateSidebar();
  };
}

function renderCrateMainList(el, isAdmin) {''',
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

    if "loadCrateGenreDetail" in text:
        print(f"{PATH}: Genres frontend already present — skipping (already patched).")
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
