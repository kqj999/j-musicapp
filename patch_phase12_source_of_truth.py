#!/usr/bin/env python3
"""
Source of Truth: renames "Imported" and makes it real -- Discovered Tracks
(the reserved batch from Discover/Browse's "+") pinned first, then every
file you've run through Import, grouped under "Uploaded Lists". Click a
row for a Rekordbox-style track-view with the same Edit-mode checkbox +
Delete Selected + Add-to-List/Vibe pattern as everywhere else. Deleting a
batch (or tracks within one) is a real, permanent database delete -- both
carry a confirm warning saying so.

Also rewires the "+" save button on Discover/Browse: it now creates real
Uploads via the Discovered Tracks batch instead of copying disconnected
data into a List, and is open to any named user, not just Admin.

Requires patch_phase11_lists.py and patch_phase11c_vibes.py to already be
applied (reuses their shared helpers). Run this from inside mymusicapp/.
"""
import pathlib
import re
import sys

PATH = pathlib.Path("app.js")

EDITS = [
    (
        '  { key: "imports", label: "Imported" },',
        '  { key: "imports", label: "Source of Truth" },',
    ),
    (
        '    selectedTrackIds: new Set(), pendingNewGenreName: null,\n    trackViewSort: { col: null, dir: "asc" },',
        '    selectedTrackIds: new Set(), pendingNewGenreName: null,\n    batchesList: [], batchesLoaded: false,\n    batchesListEditMode: false, selectedBatchIds: new Set(),\n    trackViewSort: { col: null, dir: "asc" },',
    ),
    (
        'async function loadCrateGenres() {\n  if (!state.username) {\n    state.crate.genresList = [];\n    state.crate.uncategorizedCount = 0;\n    state.crate.genresLoaded = true;\n    return;\n  }\n  try {\n    const data = await api("/genres", { needsAuth: true });\n    state.crate.genresList = data.genres || [];\n    state.crate.uncategorizedCount = data.uncategorizedCount || 0;\n  } catch (err) {\n    state.crate.genresList = [];\n    state.crate.uncategorizedCount = 0;\n  }\n  state.crate.genresLoaded = true;\n  if (state.activeTab === "crate") renderCrate();\n}',
        'async function loadCrateGenres() {\n  if (!state.username) {\n    state.crate.genresList = [];\n    state.crate.uncategorizedCount = 0;\n    state.crate.genresLoaded = true;\n    return;\n  }\n  try {\n    const data = await api("/genres", { needsAuth: true });\n    state.crate.genresList = data.genres || [];\n    state.crate.uncategorizedCount = data.uncategorizedCount || 0;\n  } catch (err) {\n    state.crate.genresList = [];\n    state.crate.uncategorizedCount = 0;\n  }\n  state.crate.genresLoaded = true;\n  if (state.activeTab === "crate") renderCrate();\n}\n\n// Source of Truth — one row per import batch (Discovered Tracks from\n// Discover/Browse "+", plus one per file you\'ve run through Import).\nasync function loadCrateBatches() {\n  if (!state.username) {\n    state.crate.batchesList = [];\n    state.crate.batchesLoaded = true;\n    return;\n  }\n  try {\n    const data = await api("/imports", { needsAuth: true });\n    state.crate.batchesList = data.batches || [];\n  } catch (err) {\n    state.crate.batchesList = [];\n  }\n  state.crate.batchesLoaded = true;\n  if (state.activeTab === "crate") renderCrate();\n}',
    ),
    (
        '  loadCrateVibes();\n  loadCrateGenres();\n  loadMixes();\n}',
        '  loadCrateVibes();\n  loadCrateGenres();\n  loadCrateBatches();\n  loadMixes();\n}',
    ),
    (
        '  if (key === "genres") {\n    const items = c.uncategorizedCount > 0 ? [{ id: "Uncategorized", label: "Uncategorized" }] : [];\n    return items.concat(c.genresList.slice(0, Math.max(0, 5 - items.length)).map((g) => ({ id: g.name, label: g.name })));\n  }\n  return [];\n}',
        '  if (key === "genres") {\n    const items = c.uncategorizedCount > 0 ? [{ id: "Uncategorized", label: "Uncategorized" }] : [];\n    return items.concat(c.genresList.slice(0, Math.max(0, 5 - items.length)).map((g) => ({ id: g.name, label: g.name })));\n  }\n  if (key === "imports") {\n    const sorted = [...c.batchesList].sort((a, b) => (a.id === "discovered" ? -1 : b.id === "discovered" ? 1 : 0));\n    return sorted.slice(0, 5).map((b) => ({ id: b.id, label: b.filename }));\n  }\n  return [];\n}',
    ),
    (
        '              ? `<div class="crate-tree-empty">${sec.key === "lists" || sec.key === "vibes" || sec.key === "genres" ? "Nothing here yet" : "Coming in a future step"}</div>`',
        '              ? `<div class="crate-tree-empty">${sec.key === "lists" || sec.key === "vibes" || sec.key === "genres" || sec.key === "imports" ? "Nothing here yet" : "Coming in a future step"}</div>`',
    ),
    (
        '  if (section === "imports") {\n    el.innerHTML = `\n      <div class="channel-head"><h4 class="crate-heading">${escapeHtml(sectionLabel)}</h4></div>\n      <div class="empty-state" style="padding:40px 0;">Coming in a future step</div>\n    `;\n    return;\n  }',
        '  if (section === "imports") {\n    renderCrateBatchesListView(el);\n    return;\n  }',
    ),
    (
        'function crateCreateNewGenre() {\n  const name = prompt("New genre name:");\n  if (!name || !name.trim()) return;\n  state.crate.pendingNewGenreName = name.trim();\n  state.crate.activeSection = "genres";\n  state.crate.activeItemId = "Uncategorized";\n  state.crate.editMode = true;\n  state.crate.selectedTrackIds = new Set();\n  renderCrateMain();\n  renderCrateSidebar();\n  toast(`Select tracks below, then move them to "${name.trim()}"`);\n}',
        'function crateCreateNewGenre() {\n  const name = prompt("New genre name:");\n  if (!name || !name.trim()) return;\n  state.crate.pendingNewGenreName = name.trim();\n  state.crate.activeSection = "genres";\n  state.crate.activeItemId = "Uncategorized";\n  state.crate.editMode = true;\n  state.crate.selectedTrackIds = new Set();\n  renderCrateMain();\n  renderCrateSidebar();\n  toast(`Select tracks below, then move them to "${name.trim()}"`);\n}\n\n// Source of Truth — Discovered Tracks (the reserved batch from Discover/\n// Browse\'s "+") always pinned first, then every file you\'ve run through\n// Import, grouped under "Uploaded Lists" and sorted most-recent-first.\nfunction crateBatchModeLabel(mode) {\n  if (mode === "update-collection") return "Update Collection";\n  if (mode === "add-to-vibe") return "Add to Vibe";\n  if (mode === "create-vibe") return "Create Vibe";\n  if (mode === "discover") return "Discovered";\n  return mode || "—";\n}\n\nfunction crateBatchRowHtml(b, editMode, isDiscovered) {\n  return `\n    <tr class="crate-list-row" data-open-batch="${escapeAttr(b.id)}">\n      ${editMode ? `<td><input type="checkbox" class="batch-select-checkbox" data-batch-id="${escapeAttr(b.id)}" ${state.crate.selectedBatchIds.has(b.id) ? "checked" : ""} /></td>` : ""}\n      <td>${isDiscovered ? \'<span class="star filled">★</span> \' : ""}${escapeHtml(b.filename)}</td>\n      <td>${b.createdAt ? new Date(b.createdAt).toLocaleDateString() : "—"}</td>\n      <td>${b.trackCount}</td>\n      <td>${escapeHtml(crateBatchModeLabel(b.mode))}</td>\n    </tr>\n  `;\n}\n\nfunction renderCrateBatchesListView(el) {\n  const batches = state.crate.batchesList;\n  const editMode = state.crate.batchesListEditMode;\n  const discovered = batches.find((b) => b.id === "discovered");\n  const fileBatches = batches\n    .filter((b) => b.id !== "discovered")\n    .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));\n\n  el.innerHTML = `\n    <div class="channel-head">\n      <h4 class="crate-heading">Source of Truth</h4>\n      ${batches.length > 0 ? `<button class="icon-btn" id="btn-batches-edit-mode">${editMode ? "done" : "edit"}</button>` : ""}\n    </div>\n    ${editMode ? `\n      <div class="seed-row" style="margin-top:10px; align-items:center;">\n        <button class="btn btn-sm" id="btn-delete-selected-batches">Delete Selected</button>\n        <span id="batches-selected-count" style="color:var(--muted); font-size:10.5px;"></span>\n      </div>\n    ` : ""}\n    ${batches.length === 0 ? `<div class="empty-state" style="padding:40px 0;">Nothing here yet</div>` : `\n      <table class="crate-list-table" style="margin-top:14px;">\n        <thead>\n          <tr>\n            ${editMode ? `<th><input type="checkbox" id="batches-select-all" /></th>` : ""}\n            <th>Title</th>\n            <th>Date Created</th>\n            <th># of Tracks</th>\n            <th>Import Mode</th>\n          </tr>\n        </thead>\n        <tbody>\n          ${discovered ? crateBatchRowHtml(discovered, editMode, true) : ""}\n          ${fileBatches.length > 0 ? `<tr><td colspan="${editMode ? 5 : 4}" style="padding:14px 12px 6px; color:var(--muted); font-size:10.5px; text-transform:uppercase; letter-spacing:0.06em;">Uploaded Lists</td></tr>` : ""}\n          ${fileBatches.map((b) => crateBatchRowHtml(b, editMode, false)).join("")}\n        </tbody>\n      </table>\n    `}\n  `;\n\n  el.querySelectorAll("[data-open-batch]").forEach((row) => {\n    row.onclick = (e) => {\n      if (e.target.type === "checkbox") return;\n      state.crate.activeItemId = row.dataset.openBatch;\n      renderCrateMain();\n      renderCrateSidebar();\n    };\n  });\n\n  const editBtn = document.getElementById("btn-batches-edit-mode");\n  if (editBtn) {\n    editBtn.onclick = () => {\n      state.crate.batchesListEditMode = !state.crate.batchesListEditMode;\n      state.crate.selectedBatchIds = new Set();\n      renderCrateBatchesListView(el);\n    };\n  }\n\n  if (editMode) {\n    const countEl = document.getElementById("batches-selected-count");\n    if (countEl) countEl.textContent = `${state.crate.selectedBatchIds.size} selected`;\n\n    el.querySelectorAll(".batch-select-checkbox").forEach((cb) => {\n      cb.onchange = () => {\n        if (cb.checked) state.crate.selectedBatchIds.add(cb.dataset.batchId);\n        else state.crate.selectedBatchIds.delete(cb.dataset.batchId);\n        const c = document.getElementById("batches-selected-count");\n        if (c) c.textContent = `${state.crate.selectedBatchIds.size} selected`;\n      };\n    });\n\n    const selectAllCb = document.getElementById("batches-select-all");\n    if (selectAllCb) {\n      selectAllCb.onchange = () => {\n        const allIds = batches.map((b) => b.id);\n        if (selectAllCb.checked) allIds.forEach((id) => state.crate.selectedBatchIds.add(id));\n        else state.crate.selectedBatchIds.clear();\n        renderCrateBatchesListView(el);\n      };\n    }\n\n    document.getElementById("btn-delete-selected-batches").onclick = async () => {\n      const ids = [...state.crate.selectedBatchIds];\n      if (ids.length === 0) {\n        toast("Select at least one row");\n        return;\n      }\n      if (!confirm(`Delete ${ids.length} ${ids.length === 1 ? "entry" : "entries"}? This deletes every track inside from your database completely.`)) return;\n      try {\n        await api("/imports/delete", { method: "POST", needsAuth: true, body: { batchIds: ids } });\n        state.crate.selectedBatchIds = new Set();\n        toast("Deleted");\n        await loadCrateBatches();\n        renderCrateMain();\n        renderCrateSidebar();\n      } catch (err) {\n        toast(err.message);\n      }\n    };\n  }\n}',
    ),
    (
        '  if (section === "genres") {\n    loadCrateGenreDetail(el);\n    return;\n  }\n\n  if (section === "lists" && crateFindList(state.crate.activeItemId)) {',
        '  if (section === "genres") {\n    loadCrateGenreDetail(el);\n    return;\n  }\n\n  if (section === "imports") {\n    loadCrateBatchDetail(el);\n    return;\n  }\n\n  if (section === "lists" && crateFindList(state.crate.activeItemId)) {',
    ),
    (
        'function saveTracksToCrate(tracks) {\n  if (state.authLevel !== "admin") {\n    toast("Admin access required to save to Crate");\n    return;\n  }\n  if (state.crate.lists.length === 0) {\n    state.crate.lists.push({ name: "New List", locked: false, tracks: [] });\n  }\n  const target = crateFindList(state.crate.activeItemId) || state.crate.lists[0];\n  tracks.forEach((t) =>\n    target.tracks.push({ artist: t.artist || "", track: t.track || "", label: t.label || "", bpm: t.bpm || "", key: t.key || "", notes: "", audioUrl: null })\n  );\n  persistCrate();\n  toast(`Added ${tracks.length} track(s) to "${target.name}"`);\n  if (state.activeTab === "crate") renderCrate();\n}',
        '// The "+" save button on Discover/Browse. Creates real Uploads (not\n// disconnected copies) filed under the reserved Discovered Tracks batch —\n// any named user can use this now, not just Admin, since it\'s scoped to\n// their own Uploads same as Vibes/Genres/Import already are.\nasync function saveTracksToCrate(tracks) {\n  if (!state.username) {\n    toast("Log in with your name to save tracks");\n    return;\n  }\n  try {\n    await api("/imports/save-discovered", { method: "POST", needsAuth: true, body: { tracks } });\n    toast(`Saved ${tracks.length} track(s) to Discovered Tracks`);\n    loadCrateBatches();\n  } catch (err) {\n    toast(err.message);\n  }\n}',
    ),
    (
        '// Shared "Add selected to..." control — one dropdown grouping Lists and',
        '// ---------------------------------------------------------------------------\n// Source of Truth track-view — the tracks inside one batch (Discovered\n// Tracks or a file import). Edit mode: checkbox multi-select, Delete\n// Selected (deletes the track from your database completely — same cascade\n// as any other delete-track-from-Imports action), and the shared\n// Add-to-List/Vibe control.\n// ---------------------------------------------------------------------------\n\nasync function loadCrateBatchDetail(el) {\n  el.innerHTML = `<div class="empty-state"><span class="spinner"></span> Loading...</div>`;\n  try {\n    const detail = await api(`/imports/${encodeURIComponent(state.crate.activeItemId)}`, { needsAuth: true });\n    renderCrateBatchDetail(el, detail);\n  } catch (err) {\n    el.innerHTML = errorCardHtml(err.message);\n  }\n}\n\nfunction renderCrateBatchDetail(el, batch) {\n  crateResetTrackViewIfNewItem(`imports:${batch.id}`);\n\n  const editMode = state.crate.editMode;\n  const rows = crateFilterAndSortTracks(batch.tracks);\n\n  el.innerHTML = `\n    <div class="channel-head">\n      <h4 class="crate-heading">${escapeHtml(batch.filename)}</h4>\n      <div style="display:flex; gap:8px; flex-wrap:wrap;">\n        <button class="icon-btn" id="btn-back-to-batches">← source of truth</button>\n        <button class="icon-btn" id="btn-edit-mode">${editMode ? "done" : "edit"}</button>\n      </div>\n    </div>\n\n    <div class="track-meta-row">${batch.createdAt ? `Created ${new Date(batch.createdAt).toLocaleDateString()} · ` : ""}${crateBatchModeLabel(batch.mode)} · ${batch.tracks.length} track${batch.tracks.length === 1 ? "" : "s"}</div>\n\n    <div class="seed-row" style="margin-top:14px;">\n      <input class="input" id="track-search" placeholder="Search tracks..." value="${escapeAttr(state.crate.trackSearchQuery)}" style="flex:1;" />\n    </div>\n\n    ${editMode ? `\n      <div class="seed-row" style="margin-top:10px; align-items:center; flex-wrap:wrap;">\n        <button class="btn btn-sm" id="btn-delete-selected-tracks">Delete Selected</button>\n        ${crateBulkAddSelectHtml(null, null)}\n      </div>\n      <div style="margin-top:6px; color:var(--muted); font-size:10.5px;" id="tracks-selected-count"></div>\n    ` : ""}\n\n    <div id="batch-tracks" style="margin-top:12px;"></div>\n  `;\n\n  document.getElementById("batch-tracks").innerHTML = crateTrackTableHtml(rows, { dragEnabled: false, showRemove: false, checkboxEnabled: editMode, selectedIds: state.crate.selectedTrackIds });\n  crateWireTrackSortHeaders(el, () => renderCrateBatchDetail(el, batch));\n\n  document.getElementById("track-search").oninput = (e) => {\n    state.crate.trackSearchQuery = e.target.value;\n    renderCrateBatchDetail(el, batch);\n  };\n\n  document.getElementById("btn-back-to-batches").onclick = () => {\n    state.crate.activeItemId = null;\n    renderCrateMain();\n    renderCrateSidebar();\n  };\n\n  document.getElementById("btn-edit-mode").onclick = () => {\n    state.crate.editMode = !state.crate.editMode;\n    state.crate.selectedTrackIds = new Set();\n    renderCrateBatchDetail(el, batch);\n  };\n\n  if (editMode) {\n    crateUpdateTracksSelectedCount();\n\n    document.querySelectorAll(".track-select-checkbox").forEach((cb) => {\n      cb.onchange = () => {\n        if (cb.checked) state.crate.selectedTrackIds.add(cb.dataset.trackId);\n        else state.crate.selectedTrackIds.delete(cb.dataset.trackId);\n        crateUpdateTracksSelectedCount();\n      };\n    });\n\n    const selectAllCb = document.getElementById("track-select-all");\n    if (selectAllCb) {\n      selectAllCb.onchange = () => {\n        if (selectAllCb.checked) rows.forEach((t) => state.crate.selectedTrackIds.add(t.id));\n        else rows.forEach((t) => state.crate.selectedTrackIds.delete(t.id));\n        renderCrateBatchDetail(el, batch);\n      };\n    }\n\n    document.getElementById("btn-delete-selected-tracks").onclick = async () => {\n      const ids = [...state.crate.selectedTrackIds];\n      if (ids.length === 0) {\n        toast("Select at least one track");\n        return;\n      }\n      if (!confirm(`Delete ${ids.length} track${ids.length === 1 ? "" : "s"}? This removes them from your database completely.`)) return;\n      try {\n        await api("/imports/delete-tracks", { method: "POST", needsAuth: true, body: { batchId: batch.id, uploadIds: ids } });\n        state.crate.selectedTrackIds = new Set();\n        toast("Deleted");\n        await loadCrateBatches();\n        loadCrateBatchDetail(el);\n      } catch (err) {\n        toast(err.message);\n      }\n    };\n\n    document.getElementById("btn-bulk-add").onclick = () => {\n      crateHandleBulkAdd(state.crate.selectedTrackIds, () => {\n        state.crate.selectedTrackIds = new Set();\n        loadCrate();\n      });\n    };\n  }\n}\n\n// Shared "Add selected to..." control — one dropdown grouping Lists and',
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
        sys.exit(f"Can't find {PATH} -- run this from the mymusicapp/ folder.")

    text = PATH.read_text(encoding="utf-8")

    if "crateBulkAddSelectHtml" not in text:
        sys.exit("This requires patch_phase11_lists.py and patch_phase11c_vibes.py to be applied "
                  "first (crateBulkAddSelectHtml not found). Run those first, then this one.")

    if "renderCrateBatchesListView" in text:
        print(f"{PATH}: Source of Truth already present -- skipping (already patched).")
        return

    for i, edit in enumerate(EDITS, 1):
        old, new = edit[0], edit[1]
        mode = edit[2] if len(edit) > 2 else "one"
        pattern = make_pattern(old)
        matches = list(pattern.finditer(text))
        count = len(matches)
        if count == 0:
            first_line = old.strip().splitlines()[0][:50]
            sys.exit(f"Edit {i}/{len(EDITS)} FAILED -- expected text not found, even allowing for "
                      f"whitespace/formatting differences. Your {PATH.name} differs from what this "
                      f"script expects in a real way, not just formatting. No changes written.\n"
                      f"Send me the output of: grep -n {first_line!r} {PATH}")
        if mode == "one" and count > 1:
            sys.exit(f"Edit {i}/{len(EDITS)} FAILED -- expected text found {count} times, expected 1. "
                      f"No changes written.")
        if mode == "all":
            text = pattern.sub(lambda m: new, text)
        else:
            text = pattern.sub(lambda m: new, text, count=1)
        print(f"Edit {i}/{len(EDITS)} applied ({count} occurrence" + ("s" if count != 1 else "") + ").")

    PATH.write_text(text, encoding="utf-8")
    print(f"\nDone -- {PATH} patched successfully.")


if __name__ == "__main__":
    main()
