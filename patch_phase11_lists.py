#!/usr/bin/env python3
"""
Converts Lists to real-id references (matches Vibes/Genres, was previously
addressed by array position). Removes the manual "add track" forms from
List and Vibe track-views. Replaces the old per-row delete-X in List's
track-view with the same checkbox + select-all + bulk-delete pattern
Genres already has, and adds a shared "Add selected to..." control (Lists
and Vibes, with create-new options) to List's Edit mode.

This patch covers My Lists specifically. Vibe Curation's equivalent
checkbox/bulk-add conversion + manual-add removal is a separate patch,
coming next -- kept apart so each is independently verifiable.

Run this from inside mymusicapp/.
"""
import pathlib
import re
import sys

PATH = pathlib.Path("app.js")

EDITS = [
    (
        '  if (key === "lists") {\n    return c.lists.slice(0, 5).map((l, i) => ({ id: i, label: l.name }));\n  }',
        '  if (key === "lists") {\n    return c.lists.slice(0, 5).map((l) => ({ id: l.id, label: l.name }));\n  }',
    ),
    (
        '      state.crate.activeItemId = key === "lists" ? +rawId : rawId;',
        '      state.crate.activeItemId = rawId;',
    ),
    (
        'async function loadCrate() {',
        '// Lists are addressed by real id now (matches Vibes/Genres), not array\n// position — this is the one lookup point everything else should use.\nfunction crateFindList(id) {\n  return state.crate.lists.find((l) => l.id === id);\n}\n\nasync function loadCrate() {',
    ),
    (
        '  const target = state.crate.lists[state.crate.activeItemId] || state.crate.lists[0];',
        '  const target = crateFindList(state.crate.activeItemId) || state.crate.lists[0];',
    ),
    (
        '  const isLists = section === "lists";\n  const rawRows = isLists\n    ? c.lists.map((l, i) => ({ id: i, name: l.name, trackCount: l.tracks.length, updatedAt: l.updatedAt || null }))\n    : c.vibesList.map((v) => ({ id: v.id, name: v.name, trackCount: v.trackCount, updatedAt: v.updatedAt || null, isActiveInBrowse: v.isActiveInBrowse }));',
        '  const isLists = section === "lists";\n  const rawRows = isLists\n    ? c.lists.map((l) => ({ id: l.id, name: l.name, trackCount: l.tracks.length, updatedAt: l.updatedAt || null }))\n    : c.vibesList.map((v) => ({ id: v.id, name: v.name, trackCount: v.trackCount, updatedAt: v.updatedAt || null, isActiveInBrowse: v.isActiveInBrowse }));',
    ),
    (
        '      state.crate.activeItemId = isLists ? +rawId : rawId;',
        '      state.crate.activeItemId = rawId;',
    ),
    (
        'function crateCreateNewList() {\n  const name = prompt("List name:", "Untitled List");\n  if (!name) return;\n  const now = new Date().toISOString();\n  state.crate.lists.push({ name, locked: false, tracks: [], createdAt: now, updatedAt: now });\n  state.crate.activeSection = "lists";\n  state.crate.activeItemId = state.crate.lists.length - 1;\n  persistCrate();\n  renderCrateSidebar();\n  renderCrateMain();\n}',
        'function crateCreateNewList() {\n  const name = prompt("List name:", "Untitled List");\n  if (!name) return;\n  const now = new Date().toISOString();\n  const newList = { id: crypto.randomUUID(), name, locked: false, trackIds: [], tracks: [], createdAt: now, updatedAt: now };\n  state.crate.lists.push(newList);\n  state.crate.activeSection = "lists";\n  state.crate.activeItemId = newList.id;\n  persistCrate();\n  renderCrateSidebar();\n  renderCrateMain();\n}',
    ),
    (
        '  if (section === "lists" && state.crate.lists[state.crate.activeItemId]) {',
        '  if (section === "lists" && crateFindList(state.crate.activeItemId)) {',
    ),
    (
        'function renderCrateMainList(el, isAdmin) {\n  const list = state.crate.lists[state.crate.activeItemId];\n\n  if (!list) {\n    el.innerHTML = `<div class="empty-state">Select or create a list</div>`;\n    return;\n  }\n\n  crateResetTrackViewIfNewItem(`lists:${state.crate.activeItemId}`);\n\n  const dragEnabled = isAdmin && crateCanReorder();\n  const showRemove = isAdmin && state.crate.editMode;\n  const rows = crateFilterAndSortTracks(list.tracks);\n\n  el.innerHTML = `\n    <div class="channel-head">\n      <h4 class="crate-heading">${escapeHtml(list.name)}</h4>\n      <div style="display:flex; gap:8px; flex-wrap:wrap;">\n        ${isAdmin ? `<button class="icon-btn" id="btn-toggle-lock">${list.locked ? "🔒 locked" : "🔓 unlocked"}</button>` : ""}\n        ${isAdmin ? `<button class="icon-btn" id="btn-rename-list">rename</button>` : ""}\n        ${isAdmin ? `<button class="icon-btn" id="btn-delete-list">delete</button>` : ""}\n        ${isAdmin ? `<button class="icon-btn" id="btn-edit-mode">${state.crate.editMode ? "done" : "edit"}</button>` : ""}\n        <button class="icon-btn" id="btn-export-list">export .txt</button>\n      </div>\n    </div>\n\n    <textarea class="input" id="track-description" rows="2" placeholder="Description — optional, what does this sound like?" style="margin-top:12px;" ${isAdmin ? "" : "disabled"}>${escapeHtml(list.description || "")}</textarea>\n\n    <div class="track-meta-row">${crateTrackMetaRowHtml({ createdAt: list.createdAt, updatedAt: list.updatedAt, trackCount: list.tracks.length })}</div>\n\n    <div class="seed-row" style="margin-top:14px;">\n      <input class="input" id="track-search" placeholder="Search tracks..." value="${escapeAttr(state.crate.trackSearchQuery)}" style="flex:1;" />\n    </div>\n\n    ${isAdmin && !state.crate.editMode ? `\n      <div class="seed-row" style="margin-top:10px;">\n        <input class="input" id="manual-artist" placeholder="Artist" style="flex:1;" />\n        <input class="input" id="manual-track" placeholder="Track" style="flex:1;" />\n        <button class="btn btn-sm" id="btn-add-manual">Add</button>\n      </div>\n    ` : ""}\n\n    <div id="crate-tracks" style="margin-top:12px;"></div>\n  `;\n\n  document.getElementById("crate-tracks").innerHTML = crateTrackTableHtml(rows, { dragEnabled, showRemove });\n  crateWireTrackSortHeaders(el, () => renderCrateMainList(el, isAdmin));\n\n  document.getElementById("track-search").oninput = (e) => {\n    state.crate.trackSearchQuery = e.target.value;\n    renderCrateMainList(el, isAdmin);\n  };\n\n  document.getElementById("track-description").onchange = (e) => {\n    if (!isAdmin) return;\n    list.description = e.target.value;\n    list.updatedAt = new Date().toISOString();\n    persistCrate();\n  };\n\n  if (isAdmin) {\n    document.getElementById("btn-toggle-lock").onclick = () => {\n      list.locked = !list.locked;\n      list.updatedAt = new Date().toISOString();\n      persistCrate();\n      renderCrate();\n    };\n    document.getElementById("btn-rename-list").onclick = () => {\n      const name = prompt("Rename list:", list.name);\n      if (!name) return;\n      list.name = name;\n      list.updatedAt = new Date().toISOString();\n      persistCrate();\n      renderCrate();\n    };\n    document.getElementById("btn-delete-list").onclick = () => {\n      if (!confirm(`Delete "${list.name}"?`)) return;\n      state.crate.lists.splice(state.crate.activeItemId, 1);\n      state.crate.activeItemId = null;\n      persistCrate();\n      renderCrate();\n    };\n    document.getElementById("btn-edit-mode").onclick = () => {\n      state.crate.editMode = !state.crate.editMode;\n      renderCrateMainList(el, isAdmin);\n    };\n    const addManualBtn = document.getElementById("btn-add-manual");\n    if (addManualBtn) {\n      addManualBtn.onclick = () => {\n        const artist = document.getElementById("manual-artist").value.trim();\n        const track = document.getElementById("manual-track").value.trim();\n        if (!artist) return;\n        list.tracks.push({ artist, track, label: "", bpm: "", key: "", time: "", genre: "", notes: "", audioUrl: null });\n        list.updatedAt = new Date().toISOString();\n        persistCrate();\n        renderCrateMainList(el, isAdmin);\n      };\n    }\n  }\n\n  document.getElementById("btn-export-list").onclick = () => exportListAsTxt(list);\n\n  const tracksContainer = document.getElementById("crate-tracks");\n\n  if (showRemove) {\n    tracksContainer.querySelectorAll("[data-track-remove-i]").forEach((btn) => {\n      btn.onclick = () => {\n        list.tracks.splice(+btn.dataset.trackRemoveI, 1);\n        list.updatedAt = new Date().toISOString();\n        persistCrate();\n        renderCrateMainList(el, isAdmin);\n      };\n    });\n  }\n\n  if (dragEnabled) {\n    setupListDragReorder(tracksContainer, list, el, isAdmin);\n  }\n}\n\nfunction setupListDragReorder(container, list, el, isAdmin) {\n  let dragIndex = null;\n  container.querySelectorAll("[data-track-orig-i]").forEach((row) => {\n    row.addEventListener("dragstart", () => {\n      dragIndex = +row.dataset.trackOrigI;\n      row.classList.add("dragging");\n    });\n    row.addEventListener("dragend", () => row.classList.remove("dragging"));\n    row.addEventListener("dragover", (e) => e.preventDefault());\n    row.addEventListener("drop", () => {\n      const dropIndex = +row.dataset.trackOrigI;\n      if (dragIndex === null || dragIndex === dropIndex) return;\n      const [moved] = list.tracks.splice(dragIndex, 1);\n      list.tracks.splice(dropIndex, 0, moved);\n      list.updatedAt = new Date().toISOString();\n      persistCrate();\n      renderCrateMainList(el, isAdmin);\n    });\n  });\n}',
        '// Shared "Add selected to..." control — one dropdown grouping Lists and\n// Vibes together (with create-new options in each group), used from every\n// Edit-mode action bar (Lists, Vibes, Genres, Imported).\nfunction crateBulkAddSelectHtml(excludeListId, excludeVibeId) {\n  return `\n    <select class="input" id="bulk-add-target" style="flex:1; min-width:160px;">\n      <option value="">Add selected to...</option>\n      <optgroup label="Lists">\n        <option value="list:__new__">+ Create new list...</option>\n        ${state.crate.lists.filter((l) => l.id !== excludeListId).map((l) => `<option value="list:${escapeAttr(l.id)}">${escapeHtml(l.name)}</option>`).join("")}\n      </optgroup>\n      <optgroup label="Vibes">\n        <option value="vibe:__new__">+ Create new vibe...</option>\n        ${state.crate.vibesList.filter((v) => v.id !== excludeVibeId).map((v) => `<option value="vibe:${escapeAttr(v.id)}">${escapeHtml(v.name)}</option>`).join("")}\n      </optgroup>\n    </select>\n    <button class="btn btn-sm" id="btn-bulk-add">Add</button>\n  `;\n}\n\nasync function crateHandleBulkAdd(selectedIds, onDone) {\n  const select = document.getElementById("bulk-add-target");\n  if (!select) return;\n  const value = select.value;\n  if (!value) {\n    toast("Pick a destination first");\n    return;\n  }\n  if (selectedIds.size === 0) {\n    toast("Select at least one track");\n    return;\n  }\n  const [kind, target] = value.split(":");\n  try {\n    if (kind === "list") {\n      const body = { uploadIds: [...selectedIds] };\n      if (target === "__new__") {\n        const name = prompt("New list name:");\n        if (!name || !name.trim()) return;\n        body.newListName = name.trim();\n      } else {\n        body.listId = target;\n      }\n      await api("/crate/add-tracks", { method: "POST", needsAuth: true, body });\n      toast("Added to list");\n    } else {\n      const body = { uploadIds: [...selectedIds] };\n      if (target === "__new__") {\n        const name = prompt("New vibe name:");\n        if (!name || !name.trim()) return;\n        body.newVibeName = name.trim();\n      } else {\n        body.vibeId = target;\n      }\n      await api("/vibes/add-existing-tracks", { method: "POST", needsAuth: true, body });\n      toast("Added to vibe");\n    }\n    onDone();\n  } catch (err) {\n    toast(err.message);\n  }\n}\n\nfunction crateUpdateTracksSelectedCount() {\n  const el = document.getElementById("tracks-selected-count");\n  if (el) el.textContent = `${state.crate.selectedTrackIds.size} selected`;\n}\n\nfunction renderCrateMainList(el, isAdmin) {\n  const list = crateFindList(state.crate.activeItemId);\n\n  if (!list) {\n    el.innerHTML = `<div class="empty-state">Select or create a list</div>`;\n    return;\n  }\n\n  crateResetTrackViewIfNewItem(`lists:${list.id}`);\n\n  const dragEnabled = isAdmin && crateCanReorder();\n  const checkboxEnabled = isAdmin && state.crate.editMode;\n  const rows = crateFilterAndSortTracks(list.tracks);\n\n  el.innerHTML = `\n    <div class="channel-head">\n      <h4 class="crate-heading">${escapeHtml(list.name)}</h4>\n      <div style="display:flex; gap:8px; flex-wrap:wrap;">\n        ${isAdmin ? `<button class="icon-btn" id="btn-toggle-lock">${list.locked ? "🔒 locked" : "🔓 unlocked"}</button>` : ""}\n        ${isAdmin ? `<button class="icon-btn" id="btn-rename-list">rename</button>` : ""}\n        ${isAdmin ? `<button class="icon-btn" id="btn-delete-list">delete</button>` : ""}\n        ${isAdmin ? `<button class="icon-btn" id="btn-edit-mode">${state.crate.editMode ? "done" : "edit"}</button>` : ""}\n        <button class="icon-btn" id="btn-export-list">export .txt</button>\n      </div>\n    </div>\n\n    <textarea class="input" id="track-description" rows="2" placeholder="Description — optional, what does this sound like?" style="margin-top:12px;" ${isAdmin ? "" : "disabled"}>${escapeHtml(list.description || "")}</textarea>\n\n    <div class="track-meta-row">${crateTrackMetaRowHtml({ createdAt: list.createdAt, updatedAt: list.updatedAt, trackCount: list.tracks.length })}</div>\n\n    <div class="seed-row" style="margin-top:14px;">\n      <input class="input" id="track-search" placeholder="Search tracks..." value="${escapeAttr(state.crate.trackSearchQuery)}" style="flex:1;" />\n    </div>\n\n    ${checkboxEnabled ? `\n      <div class="seed-row" style="margin-top:10px; align-items:center; flex-wrap:wrap;">\n        <button class="btn btn-sm" id="btn-delete-selected-tracks">Delete Selected</button>\n        ${crateBulkAddSelectHtml(list.id, null)}\n      </div>\n      <div style="margin-top:6px; color:var(--muted); font-size:10.5px;" id="tracks-selected-count"></div>\n    ` : ""}\n\n    <div id="crate-tracks" style="margin-top:12px;"></div>\n  `;\n\n  document.getElementById("crate-tracks").innerHTML = crateTrackTableHtml(rows, { dragEnabled, showRemove: false, checkboxEnabled, selectedIds: state.crate.selectedTrackIds });\n  crateWireTrackSortHeaders(el, () => renderCrateMainList(el, isAdmin));\n\n  document.getElementById("track-search").oninput = (e) => {\n    state.crate.trackSearchQuery = e.target.value;\n    renderCrateMainList(el, isAdmin);\n  };\n\n  document.getElementById("track-description").onchange = (e) => {\n    if (!isAdmin) return;\n    list.description = e.target.value;\n    list.updatedAt = new Date().toISOString();\n    persistCrate();\n  };\n\n  if (isAdmin) {\n    document.getElementById("btn-toggle-lock").onclick = () => {\n      list.locked = !list.locked;\n      list.updatedAt = new Date().toISOString();\n      persistCrate();\n      renderCrate();\n    };\n    document.getElementById("btn-rename-list").onclick = () => {\n      const name = prompt("Rename list:", list.name);\n      if (!name) return;\n      list.name = name;\n      list.updatedAt = new Date().toISOString();\n      persistCrate();\n      renderCrate();\n    };\n    document.getElementById("btn-delete-list").onclick = () => {\n      if (!confirm(`Delete "${list.name}"?`)) return;\n      state.crate.lists = state.crate.lists.filter((l) => l.id !== list.id);\n      state.crate.activeItemId = null;\n      persistCrate();\n      renderCrate();\n    };\n    document.getElementById("btn-edit-mode").onclick = () => {\n      state.crate.editMode = !state.crate.editMode;\n      state.crate.selectedTrackIds = new Set();\n      renderCrateMainList(el, isAdmin);\n    };\n  }\n\n  document.getElementById("btn-export-list").onclick = () => exportListAsTxt(list);\n\n  const tracksContainer = document.getElementById("crate-tracks");\n\n  if (checkboxEnabled) {\n    crateUpdateTracksSelectedCount();\n\n    tracksContainer.querySelectorAll(".track-select-checkbox").forEach((cb) => {\n      cb.onchange = () => {\n        if (cb.checked) state.crate.selectedTrackIds.add(cb.dataset.trackId);\n        else state.crate.selectedTrackIds.delete(cb.dataset.trackId);\n        crateUpdateTracksSelectedCount();\n      };\n    });\n\n    const selectAllCb = document.getElementById("track-select-all");\n    if (selectAllCb) {\n      selectAllCb.onchange = () => {\n        if (selectAllCb.checked) rows.forEach((t) => state.crate.selectedTrackIds.add(t.id));\n        else rows.forEach((t) => state.crate.selectedTrackIds.delete(t.id));\n        renderCrateMainList(el, isAdmin);\n      };\n    }\n\n    document.getElementById("btn-delete-selected-tracks").onclick = () => {\n      if (state.crate.selectedTrackIds.size === 0) {\n        toast("Select at least one track");\n        return;\n      }\n      const removing = state.crate.selectedTrackIds;\n      list.trackIds = (list.trackIds || []).filter((id) => !removing.has(id));\n      list.tracks = list.tracks.filter((t) => !removing.has(t.id));\n      list.updatedAt = new Date().toISOString();\n      state.crate.selectedTrackIds = new Set();\n      persistCrate();\n      renderCrateMainList(el, isAdmin);\n    };\n\n    document.getElementById("btn-bulk-add").onclick = () => {\n      crateHandleBulkAdd(state.crate.selectedTrackIds, () => {\n        state.crate.selectedTrackIds = new Set();\n        loadCrate();\n      });\n    };\n  }\n\n  if (dragEnabled) {\n    setupListDragReorder(tracksContainer, list, el, isAdmin);\n  }\n}\n\nfunction setupListDragReorder(container, list, el, isAdmin) {\n  let dragIndex = null;\n  container.querySelectorAll("[data-track-orig-i]").forEach((row) => {\n    row.addEventListener("dragstart", () => {\n      dragIndex = +row.dataset.trackOrigI;\n      row.classList.add("dragging");\n    });\n    row.addEventListener("dragend", () => row.classList.remove("dragging"));\n    row.addEventListener("dragover", (e) => e.preventDefault());\n    row.addEventListener("drop", () => {\n      const dropIndex = +row.dataset.trackOrigI;\n      if (dragIndex === null || dragIndex === dropIndex) return;\n      const [moved] = list.tracks.splice(dragIndex, 1);\n      list.tracks.splice(dropIndex, 0, moved);\n      list.trackIds = list.tracks.map((t) => t.id);\n      list.updatedAt = new Date().toISOString();\n      persistCrate();\n      renderCrateMainList(el, isAdmin);\n    });\n  });\n}',
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

    if "crateFindList" in text:
        print(f"{PATH}: Lists-to-references conversion already present -- skipping (already patched).")
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
