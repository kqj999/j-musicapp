#!/usr/bin/env python3
"""
The pencil-edit popup: a small icon appears next to the checkbox on every
track row in Edit mode (Lists, Vibes, Genres, Source of Truth -- all four,
since they're just different views onto the same Upload records). Clicking
it opens a popup with editable fields (Title, Artist, Album, BPM, Key,
Time, Genre, Notes) plus an "Appears On" section showing every List and
Vibe that references the track. Saving edits the Upload directly, so the
change shows up everywhere that track appears.

Requires patch_phase11_lists.py, patch_phase11c_vibes.py, and
patch_phase12_source_of_truth.py to already be applied. Run this from
inside mymusicapp/.
"""
import pathlib
import re
import sys

PATH = pathlib.Path("app.js")

EDITS = [
    (
        '          ${dragEnabled ? `<th></th>` : ""}\n          ${checkboxEnabled ? `<th><input type="checkbox" id="track-select-all" ${allSelected ? "checked" : ""} /></th>` : ""}\n          <th data-track-sort-col="track">Track Title${crateTrackSortIndicator("track")}</th>\n          <th data-track-sort-col="artist">Artist${crateTrackSortIndicator("artist")}</th>\n          <th data-track-sort-col="bpm">BPM${crateTrackSortIndicator("bpm")}</th>\n          <th data-track-sort-col="key">Key${crateTrackSortIndicator("key")}</th>\n          <th data-track-sort-col="time">Time${crateTrackSortIndicator("time")}</th>\n          <th data-track-sort-col="genre">Genre${crateTrackSortIndicator("genre")}</th>\n          <th data-track-sort-col="addedAt">Date Added${crateTrackSortIndicator("addedAt")}</th>\n          ${showRemove ? `<th></th>` : ""}\n        </tr>\n      </thead>\n      <tbody>\n        ${rows.map((t) => `\n          <tr draggable="${dragEnabled}" data-track-orig-i="${t.__i}">\n            ${dragEnabled ? `<td class="drag-handle-cell">⠿</td>` : ""}\n            ${checkboxEnabled ? `<td><input type="checkbox" class="track-select-checkbox" data-track-id="${escapeAttr(t.id)}" ${selectedIds.has(t.id) ? "checked" : ""} /></td>` : ""}',
        '          ${dragEnabled ? `<th></th>` : ""}\n          ${checkboxEnabled ? `<th><input type="checkbox" id="track-select-all" ${allSelected ? "checked" : ""} /></th><th></th>` : ""}\n          <th data-track-sort-col="track">Track Title${crateTrackSortIndicator("track")}</th>\n          <th data-track-sort-col="artist">Artist${crateTrackSortIndicator("artist")}</th>\n          <th data-track-sort-col="bpm">BPM${crateTrackSortIndicator("bpm")}</th>\n          <th data-track-sort-col="key">Key${crateTrackSortIndicator("key")}</th>\n          <th data-track-sort-col="time">Time${crateTrackSortIndicator("time")}</th>\n          <th data-track-sort-col="genre">Genre${crateTrackSortIndicator("genre")}</th>\n          <th data-track-sort-col="addedAt">Date Added${crateTrackSortIndicator("addedAt")}</th>\n          ${showRemove ? `<th></th>` : ""}\n        </tr>\n      </thead>\n      <tbody>\n        ${rows.map((t) => `\n          <tr draggable="${dragEnabled}" data-track-orig-i="${t.__i}">\n            ${dragEnabled ? `<td class="drag-handle-cell">⠿</td>` : ""}\n            ${checkboxEnabled ? `<td><input type="checkbox" class="track-select-checkbox" data-track-id="${escapeAttr(t.id)}" ${selectedIds.has(t.id) ? "checked" : ""} /></td><td><button class="icon-btn track-edit-pencil" data-track-edit-id="${escapeAttr(t.id)}" title="Edit track">✎</button></td>` : ""}',
    ),
    (
        '  document.getElementById("vibe-tracks").innerHTML = crateTrackTableHtml(rows, { dragEnabled, showRemove: false, checkboxEnabled, selectedIds: state.crate.selectedTrackIds });\n  crateWireTrackSortHeaders(el, () => renderCrateVibeDetail(el, vibe));',
        '  document.getElementById("vibe-tracks").innerHTML = crateTrackTableHtml(rows, { dragEnabled, showRemove: false, checkboxEnabled, selectedIds: state.crate.selectedTrackIds });\n  crateWireTrackSortHeaders(el, () => renderCrateVibeDetail(el, vibe));\n  crateWireTrackEditPencils(document.getElementById("vibe-tracks"), rows, () => loadCrateVibeDetail(el));',
    ),
    (
        '  crateWireTrackSortHeaders(el, () => renderCrateGenreDetail(el, genre));',
        '  crateWireTrackSortHeaders(el, () => renderCrateGenreDetail(el, genre));\n  crateWireTrackEditPencils(document.getElementById("genre-tracks"), rows, () => loadCrateGenreDetail(el));',
    ),
    (
        '  crateWireTrackSortHeaders(el, () => renderCrateBatchDetail(el, batch));',
        '  crateWireTrackSortHeaders(el, () => renderCrateBatchDetail(el, batch));\n  crateWireTrackEditPencils(document.getElementById("batch-tracks"), rows, () => loadCrateBatchDetail(el));',
    ),
    (
        '  document.getElementById("crate-tracks").innerHTML = crateTrackTableHtml(rows, { dragEnabled, showRemove: false, checkboxEnabled, selectedIds: state.crate.selectedTrackIds });\n  crateWireTrackSortHeaders(el, () => renderCrateMainList(el, isAdmin));',
        '  document.getElementById("crate-tracks").innerHTML = crateTrackTableHtml(rows, { dragEnabled, showRemove: false, checkboxEnabled, selectedIds: state.crate.selectedTrackIds });\n  crateWireTrackSortHeaders(el, () => renderCrateMainList(el, isAdmin));\n  crateWireTrackEditPencils(document.getElementById("crate-tracks"), rows, async () => {\n    await loadCrate();\n    renderCrateMainList(el, isAdmin);\n  });',
    ),
    (
        'function crateWireTrackSortHeaders(containerEl, onResort) {\n  containerEl.querySelectorAll("[data-track-sort-col]").forEach((th) => {\n    th.onclick = () => {\n      const col = th.dataset.trackSortCol;\n      const s = state.crate.trackViewSort;\n      if (s.col === col) s.dir = s.dir === "asc" ? "desc" : "asc";\n      else { s.col = col; s.dir = "asc"; }\n      onResort();\n    };\n  });\n}',
        'function crateWireTrackSortHeaders(containerEl, onResort) {\n  containerEl.querySelectorAll("[data-track-sort-col]").forEach((th) => {\n    th.onclick = () => {\n      const col = th.dataset.trackSortCol;\n      const s = state.crate.trackViewSort;\n      if (s.col === col) s.dir = s.dir === "asc" ? "desc" : "asc";\n      else { s.col = col; s.dir = "asc"; }\n      onResort();\n    };\n  });\n}\n\n// Wires the pencil-edit buttons rendered alongside checkboxes in Edit mode.\n// Shared across every track-view (Lists, Vibes, Genres, Source of Truth) —\n// they\'re all just different lenses onto the same Upload records, so\n// editing works identically no matter where you open it from.\nfunction crateWireTrackEditPencils(containerEl, rows, onSaved) {\n  containerEl.querySelectorAll(".track-edit-pencil").forEach((btn) => {\n    btn.onclick = (e) => {\n      e.stopPropagation();\n      const track = rows.find((t) => t.id === btn.dataset.trackEditId);\n      if (track) crateOpenTrackEditPopup(track, onSaved);\n    };\n  });\n}\n\nfunction crateCloseTrackEditPopup() {\n  const overlay = document.getElementById("track-edit-overlay");\n  if (overlay) overlay.remove();\n}\n\n// The pencil-edit popup: editable fields for one track\'s own data, plus an\n// "Appears on" section (Lists + Vibes referencing it). Saving edits the\n// Upload directly, so the change is visible everywhere that track is\n// referenced the moment you close this. onSaved is called after a\n// successful save so the calling track-view can refresh itself.\nfunction crateOpenTrackEditPopup(track, onSaved) {\n  crateCloseTrackEditPopup();\n\n  const overlay = document.createElement("div");\n  overlay.className = "track-edit-overlay";\n  overlay.id = "track-edit-overlay";\n  overlay.onclick = (e) => {\n    if (e.target === overlay) crateCloseTrackEditPopup();\n  };\n  document.body.appendChild(overlay);\n\n  overlay.innerHTML = `\n    <div class="track-edit-modal">\n      <div class="channel-head">\n        <h4 class="crate-heading" style="font-size:20px;">Edit Track</h4>\n        <button class="icon-btn" id="btn-close-track-edit">✕</button>\n      </div>\n      <div class="track-edit-fields">\n        <label>Title<input class="input" id="edit-track-title" value="${escapeAttr(track.track || "")}" /></label>\n        <label>Artist<input class="input" id="edit-track-artist" value="${escapeAttr(track.artist || "")}" /></label>\n        <label>Album<input class="input" id="edit-track-album" value="${escapeAttr(track.album || "")}" /></label>\n        <label>BPM<input class="input" id="edit-track-bpm" value="${escapeAttr(track.bpm || "")}" /></label>\n        <label>Key<input class="input" id="edit-track-key" value="${escapeAttr(track.key || "")}" /></label>\n        <label>Time<input class="input" id="edit-track-time" value="${escapeAttr(track.time || "")}" /></label>\n        <label>Genre<input class="input" id="edit-track-genre" value="${escapeAttr(track.genre || "")}" /></label>\n        <label>Notes<textarea class="input" id="edit-track-notes" rows="2">${escapeHtml(track.notes || "")}</textarea></label>\n      </div>\n      <button class="btn btn-sm btn-primary" id="btn-save-track-edit" style="margin-top:14px;">Save</button>\n      <div class="track-edit-appears-on" id="track-appears-on"><span class="spinner"></span> Loading Appears On...</div>\n    </div>\n  `;\n\n  document.getElementById("btn-close-track-edit").onclick = crateCloseTrackEditPopup;\n\n  document.getElementById("btn-save-track-edit").onclick = async () => {\n    const fields = {\n      track: document.getElementById("edit-track-title").value.trim(),\n      artist: document.getElementById("edit-track-artist").value.trim(),\n      album: document.getElementById("edit-track-album").value.trim(),\n      bpm: document.getElementById("edit-track-bpm").value.trim(),\n      key: document.getElementById("edit-track-key").value.trim(),\n      time: document.getElementById("edit-track-time").value.trim(),\n      genre: document.getElementById("edit-track-genre").value.trim(),\n      notes: document.getElementById("edit-track-notes").value.trim(),\n    };\n    try {\n      await api("/imports/edit-track", { method: "POST", needsAuth: true, body: { uploadId: track.id, ...fields } });\n      toast("Saved");\n      crateCloseTrackEditPopup();\n      if (onSaved) onSaved();\n    } catch (err) {\n      toast(err.message);\n    }\n  };\n\n  api(`/imports/appears-on/${encodeURIComponent(track.id)}`, { needsAuth: true })\n    .then((ao) => {\n      const aoEl = document.getElementById("track-appears-on");\n      if (!aoEl) return;\n      const listsHtml = ao.lists.length > 0\n        ? ao.lists.map((l) => escapeHtml(l.name)).join("<br>")\n        : "<em>none</em>";\n      const vibesHtml = ao.vibes.length > 0\n        ? ao.vibes.map((v) => escapeHtml(v.name)).join("<br>")\n        : "<em>none</em>";\n      aoEl.innerHTML = `\n        <div class="track-meta-row" style="line-height:1.8; font-size:11px;">\n          <strong>My Lists (${ao.lists.length})</strong><br>${listsHtml}\n          <br><br>\n          <strong>Vibe Curation (${ao.vibes.length})</strong><br>${vibesHtml}\n        </div>\n      `;\n    })\n    .catch(() => {\n      const aoEl = document.getElementById("track-appears-on");\n      if (aoEl) aoEl.textContent = "Couldn\'t load Appears On.";\n    });\n}',
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

    if "renderCrateBatchesListView" not in text:
        sys.exit("This requires patch_phase12_source_of_truth.py to be applied first "
                  "(renderCrateBatchesListView not found). Run that first, then this one.")

    if "crateOpenTrackEditPopup" in text:
        print(f"{PATH}: pencil-edit popup already present -- skipping (already patched).")
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
