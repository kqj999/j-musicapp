#!/usr/bin/env python3
"""
Phase 5 frontend patch (app.js): adds the Import tab. Run this from inside
mymusicapp/.
"""
import pathlib
import re
import sys

PATH = pathlib.Path("app.js")

EDITS = [
    (
        '''  profile: null,
  adminUsers: [],
};''',
        '''  profile: null,
  adminUsers: [],
  importState: { tracks: [], fileName: "", mode: "update-collection", vibesList: [], loading: false },
};''',
    ),
    (
        '''function renderAdminTabVisibility() {
  const btn = document.querySelector('.tab-btn[data-tab="admin"]');
  if (btn) btn.classList.toggle("hidden", state.authLevel !== "admin");
}''',
        '''function renderAdminTabVisibility() {
  const btn = document.querySelector('.tab-btn[data-tab="admin"]');
  if (btn) btn.classList.toggle("hidden", state.authLevel !== "admin");
}

// Import (Rekordbox) is per-user data (Vibes/Uploads), same requirement as
// Profile — needs a named login, not just the shared PIN.
function renderImportTabVisibility() {
  const btn = document.querySelector('.tab-btn[data-tab="import"]');
  if (btn) btn.classList.toggle("hidden", !state.username);
}''',
    ),
    (
        '  renderAdminTabVisibility();',
        '  renderAdminTabVisibility();\n  renderImportTabVisibility();',
        "all",
    ),
    (
        '''  if (tab === "admin") loadAdmin();
}''',
        '''  if (tab === "admin") loadAdmin();
  if (tab === "import") renderImport();
}''',
    ),
    (
        '''// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------''',
        '''// ============================================================================
// IMPORT TAB (Rekordbox)
// ============================================================================
const panelImport = document.getElementById("panel-import");

// Parses a Rekordbox XML export in the browser — never sent to the Worker as
// raw XML, only as already-parsed track objects.
function parseRekordboxXML(xmlText) {
  const parser = new DOMParser();
  const doc = parser.parseFromString(xmlText, "text/xml");
  if (doc.querySelector("parsererror")) {
    throw new Error("That doesn't look like a valid Rekordbox XML export.");
  }
  const trackEls = doc.querySelectorAll("COLLECTION > TRACK");
  const tracks = [];
  trackEls.forEach((el) => {
    tracks.push({
      artist: el.getAttribute("Artist") || "",
      track: el.getAttribute("Name") || "",
      genre: el.getAttribute("Genre") || "",
      bpm: el.getAttribute("AverageBpm") || "",
      key: el.getAttribute("Tonality") || "",
      label: el.getAttribute("Label") || "",
    });
  });
  return tracks;
}

// Simple counter/label, not a hard gate — per spec, just guidance.
function trackCountGuidance(n) {
  if (n < 15) return "Very small sample";
  if (n < 30) return "Shaky signal";
  if (n < 50) return "Solid signal";
  return "Strong signal";
}

async function loadImportVibes() {
  try {
    const data = await api("/vibes", { needsAuth: true });
    state.importState.vibesList = data.vibes || [];
  } catch (err) {
    toast(err.message);
  }
}

function renderImport() {
  if (!state.username) {
    panelImport.innerHTML = `
      <div class="panel locked-teaser">
        <h3>Import</h3>
        <p>Log in with your name (not just the shared PIN) to import a Rekordbox library.</p>
      </div>`;
    return;
  }

  const imp = state.importState;
  const hasTracks = imp.tracks.length > 0;

  panelImport.innerHTML = `
    <div class="panel" style="padding:18px; margin-bottom:22px;">
      <p style="color:var(--muted); font-size:11.5px; line-height:1.6; margin:0;">
        For best results, organize into playlists by vibe/genre in Rekordbox before exporting.
      </p>
    </div>

    <div class="section-title">✦ Rekordbox XML</div>
    <div class="seed-row">
      <input class="input" id="import-file-input" type="file" accept=".xml" style="flex:1;" />
    </div>
    <div id="import-file-status" style="margin-top:10px; color:var(--muted); font-size:11px;">
      ${hasTracks ? `${imp.fileName} — ${imp.tracks.length} tracks (${trackCountGuidance(imp.tracks.length)})` : ""}
    </div>

    ${hasTracks ? `
      <div class="section-title" style="margin-top:24px;">✦ Description <span style="color:var(--muted); font-weight:400; text-transform:none;">(optional — what does this sound like?)</span></div>
      <textarea class="input" id="import-description" rows="2" placeholder="e.g. dusty hypnotic warehouse stuff"></textarea>

      <div class="section-title" style="margin-top:24px;">✦ Import Mode</div>
      <div class="pill-row" id="import-mode-pills">
        <button type="button" class="pill ${imp.mode === "update-collection" ? "active" : ""}" data-mode="update-collection">Update Collection</button>
        <button type="button" class="pill ${imp.mode === "add-to-vibe" ? "active" : ""}" data-mode="add-to-vibe">Add to Existing Vibe</button>
        <button type="button" class="pill ${imp.mode === "create-vibe" ? "active" : ""}" data-mode="create-vibe">Create New Vibe</button>
      </div>

      ${imp.mode === "update-collection" ? `
        <p style="color:var(--muted); font-size:11px; line-height:1.6;">
          Sorts tracks into Vibes by their Rekordbox genre tag, creating new Vibes for genres you don't have yet.
          Tracks with no genre tag land in an "Uncategorized" Vibe.
        </p>
      ` : ""}

      ${imp.mode === "add-to-vibe" ? `
        <p style="color:var(--muted); font-size:11px; line-height:1.6;">Ignores genre tags — every track goes into the Vibe you pick.</p>
        <div class="seed-row">
          <select class="input" id="import-target-vibe" style="flex:1;">
            <option value="">${imp.vibesList.length === 0 ? "No vibes yet — create one first" : "Choose a Vibe..."}</option>
            ${imp.vibesList.map((v) => `<option value="${escapeAttr(v.id)}">${escapeHtml(v.name)} (${v.trackCount})</option>`).join("")}
          </select>
        </div>
      ` : ""}

      ${imp.mode === "create-vibe" ? `
        <p style="color:var(--muted); font-size:11px; line-height:1.6;">Ignores genre tags — every track becomes the seed for one new Vibe.</p>
        <div class="seed-row">
          <input class="input" id="import-new-vibe-name" placeholder="New Vibe name" style="flex:1;" />
        </div>
      ` : ""}

      <button class="btn btn-primary" id="btn-run-import" style="margin-top:18px;" ${imp.loading ? "disabled" : ""}>
        ${imp.loading ? '<span class="spinner"></span> Importing...' : "Import"}
      </button>
    ` : ""}
  `;

  document.getElementById("import-file-input").onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    try {
      const text = await file.text();
      const tracks = parseRekordboxXML(text);
      if (tracks.length === 0) {
        toast("No tracks found in that file's COLLECTION section");
        return;
      }
      imp.tracks = tracks;
      imp.fileName = file.name;
      renderImport();
    } catch (err) {
      toast(err.message);
    }
  };

  if (!hasTracks) return;

  document.getElementById("import-mode-pills").querySelectorAll(".pill").forEach((p) => {
    p.onclick = async () => {
      imp.mode = p.dataset.mode;
      if (imp.mode === "add-to-vibe" && imp.vibesList.length === 0) {
        await loadImportVibes();
      }
      renderImport();
    };
  });

  document.getElementById("btn-run-import").onclick = async () => {
    const description = document.getElementById("import-description").value.trim() || null;
    const body = { mode: imp.mode, tracks: imp.tracks, description };

    if (imp.mode === "add-to-vibe") {
      const targetVibeId = document.getElementById("import-target-vibe").value;
      if (!targetVibeId) {
        toast("Pick a Vibe first");
        return;
      }
      body.targetVibeId = targetVibeId;
    }
    if (imp.mode === "create-vibe") {
      const newVibeName = document.getElementById("import-new-vibe-name").value.trim();
      if (!newVibeName) {
        toast("Name the new Vibe first");
        return;
      }
      body.newVibeName = newVibeName;
    }

    imp.loading = true;
    renderImport();
    try {
      const data = await api("/import/rekordbox", { method: "POST", needsAuth: true, body });
      const vibeNames = (data.vibes || []).map((v) => `${v.name} (${v.trackCount})`).join(", ");
      toast(`Imported ${data.imported} track(s) → ${vibeNames}`);
      imp.tracks = [];
      imp.fileName = "";
      imp.vibesList = [];
    } catch (err) {
      toast(err.message);
    } finally {
      imp.loading = false;
      renderImport();
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
