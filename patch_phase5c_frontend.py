#!/usr/bin/env python3
"""
Adds tier-aware Browse: Admin keeps the original 6 channels, Friend gets a
3-channel fixed set plus up to 3 custom channels picked from their own
Vibes. Run this from inside mymusicapp/.
"""
import pathlib
import re
import sys

PATH = pathlib.Path("app.js")

EDITS = [
    (
        '''// Tiers: 'admin' (full access), 'view' (sees Discover/Browse UI as a preview,
// but can't actually run searches — no credits spent), 'guest' (Discover/Browse
// stay behind a locked teaser), 'none'.
function discoverBrowseVisible() {
  return state.authLevel === "admin" || state.authLevel === "view";
}
function canRunDiscoverBrowse() {
  return state.authLevel === "admin";
}''',
        '''// Tiers: 'admin' (full access), 'friend' (own API key, own tier-limited
// channels), 'view' (sees Discover/Browse UI as a preview, but can't
// actually run searches — no credits spent), 'guest' (Discover/Browse stay
// behind a locked teaser), 'none'.
function discoverBrowseVisible() {
  return state.authLevel === "admin" || state.authLevel === "view" || state.authLevel === "friend";
}
function canRunDiscoverBrowse() {
  return state.authLevel === "admin" || state.authLevel === "friend";
}''',
    ),
    (
        '  browse: { channels: {} }, // channel -> { tracks: [], loading }',
        '  browse: { channels: {}, fixedChannels: [], vibeSlots: [], vibesList: [], configLoaded: false }, // channel key -> { tracks: [], loading }',
    ),
    (
        '  if (tab === "browse") renderBrowse();',
        '  if (tab === "browse") loadBrowse();',
    ),
    (
        '''const panelBrowse = document.getElementById("panel-browse");

function renderBrowse() {
  if (!discoverBrowseVisible()) {
    panelBrowse.innerHTML = `
      <div class="panel locked-teaser">
        <h3>🔒 Browse</h3>
        <p>Six curated genre channels — Sandy Techno, RDH, Hot Girl Techno, Goth Girl Techno, Cool Remixes, House Cat — refreshed on demand.</p>
        <button class="btn" id="teaser-pin-browse">Enter Pin</button>
      </div>`;
    document.getElementById("teaser-pin-browse").onclick = () => {
      appShell.classList.add("hidden");
      pinScreen.classList.remove("hidden");
    };
    return;
  }

  panelBrowse.innerHTML = `<div class="channel-grid">
    ${BROWSE_CHANNELS.map((ch) => `
      <div class="panel channel-card" id="channel-${slug(ch)}">
        <div class="channel-head">
          <h4>${escapeHtml(ch)}</h4>
          <button class="icon-btn" data-channel="${ch}" ${canRunDiscoverBrowse() ? "" : "disabled"}>↻ refresh</button>
        </div>
        <div class="channel-body">
          <div class="empty-state">Tap refresh to generate suggestions</div>
        </div>
      </div>
    `).join("")}
  </div>
  <div id="saved-container-browse"></div>`;

  renderSavedStrip("saved-container-browse");

  panelBrowse.querySelectorAll(".icon-btn").forEach((btn) => {
    btn.onclick = () => loadBrowseChannel(btn.dataset.channel);
  });
}

function slug(s) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

async function loadBrowseChannel(channel) {
  if (!canRunDiscoverBrowse()) {
    toast("Refresh is admin-only — you're viewing a preview");
    return;
  }
  const container = document.querySelector(`#channel-${slug(channel)} .channel-body`);
  container.innerHTML = `<div class="empty-state"><span class="spinner"></span> Loading...</div>`;
  try {
    const data = await api("/browse", { method: "POST", needsAuth: true, body: { channel } });
    const tracks = data.tracks || [];
    state.browse.channels[channel].tracks = tracks;
    if (tracks.length === 0) {
      container.innerHTML = `<div class="empty-state">No suggestions returned.</div>`;
      return;
    }
    container.innerHTML = tracks
      .map(
        (t, i) => `
      <div class="channel-track">
        <div class="track-info">
          <div class="track-title">${escapeHtml(t.artist || "")}${t.track ? " — " + escapeHtml(t.track) : " — browse catalog"}</div>
          <div class="track-meta">${escapeHtml(t.label || "")}${t.release_date ? " · " + escapeHtml(t.release_date) : ""}</div>
        </div>
        <button class="add-btn" data-channel="${channel}" data-i="${i}">+</button>
      </div>`
      )
      .join("");
    container.querySelectorAll(".add-btn").forEach((btn) => {
      btn.onclick = () => {
        const t = state.browse.channels[channel].tracks[+btn.dataset.i];
        addToSavedList(t);
        btn.classList.add("added");
        btn.textContent = "✓";
      };
    });
  } catch (err) {
    container.innerHTML = errorCardHtml(err.message);
  }
}''',
        '''const panelBrowse = document.getElementById("panel-browse");

async function loadBrowse() {
  if (!discoverBrowseVisible()) {
    renderBrowse();
    return;
  }
  try {
    const data = await api("/browse-config", { needsAuth: true });
    state.browse.fixedChannels = data.fixedChannels || [];
    state.browse.vibeSlots = data.browseVibeSlots || [];
    state.browse.vibesList = data.vibesList || [];
  } catch (err) {
    toast(err.message);
    state.browse.fixedChannels = BROWSE_CHANNELS;
  }
  state.browse.configLoaded = true;
  renderBrowse();
}

// Combines this tier's fixed channels with any Vibe-based custom channels
// (Friend only) into one flat list of renderable entries.
function buildBrowseEntries() {
  const fixedNames = state.browse.fixedChannels.length ? state.browse.fixedChannels : BROWSE_CHANNELS;
  const fixed = fixedNames.map((name) => ({ key: `fixed:${name}`, label: name, kind: "fixed", channel: name }));
  const vibeEntries = (state.browse.vibeSlots || [])
    .map((id) => state.browse.vibesList.find((v) => v.id === id))
    .filter(Boolean)
    .map((v) => ({ key: `vibe:${v.id}`, label: `✦ ${v.name}`, kind: "vibe", vibeId: v.id }));
  return [...fixed, ...vibeEntries];
}

function renderVibeSlotPickerHtml() {
  const vibes = state.browse.vibesList || [];
  const slots = state.browse.vibeSlots || [];
  const optionsFor = (selectedId) => `
    <option value="">— none —</option>
    ${vibes.map((v) => `<option value="${escapeAttr(v.id)}" ${v.id === selectedId ? "selected" : ""}>${escapeHtml(v.name)} (${v.trackCount})</option>`).join("")}
  `;
  return `
    <div class="panel" style="padding:16px; margin-bottom:18px;">
      <div class="section-title" style="margin-bottom:10px;">✦ Your Custom Channels <span style="color:var(--muted); font-weight:400; text-transform:none;">(up to 3, from your Vibes)</span></div>
      ${vibes.length === 0 ? `<div class="empty-state" style="padding:0;">Import some tracks first to create Vibes</div>` : `
        <div class="seed-row">
          <select class="input" id="vibe-slot-0" style="flex:1;">${optionsFor(slots[0])}</select>
          <select class="input" id="vibe-slot-1" style="flex:1;">${optionsFor(slots[1])}</select>
          <select class="input" id="vibe-slot-2" style="flex:1;">${optionsFor(slots[2])}</select>
          <button class="btn btn-sm" id="btn-save-vibe-slots">Save</button>
        </div>
      `}
    </div>
  `;
}

function renderBrowse() {
  if (!discoverBrowseVisible()) {
    panelBrowse.innerHTML = `
      <div class="panel locked-teaser">
        <h3>🔒 Browse</h3>
        <p>Curated genre channels — refreshed on demand.</p>
        <button class="btn" id="teaser-pin-browse">Enter Pin</button>
      </div>`;
    document.getElementById("teaser-pin-browse").onclick = () => {
      appShell.classList.add("hidden");
      pinScreen.classList.remove("hidden");
    };
    return;
  }

  if (!state.browse.configLoaded) {
    panelBrowse.innerHTML = `<div class="empty-state"><span class="spinner"></span> Loading...</div>`;
    return;
  }

  const isFriend = state.authLevel === "friend";
  const entries = buildBrowseEntries();
  entries.forEach((e) => {
    if (!state.browse.channels[e.key]) state.browse.channels[e.key] = { tracks: [], loading: false };
  });

  panelBrowse.innerHTML = `
    ${isFriend ? renderVibeSlotPickerHtml() : ""}
    <div class="channel-grid">
      ${entries.map((e) => `
        <div class="panel channel-card" id="channel-${slug(e.key)}">
          <div class="channel-head">
            <h4>${escapeHtml(e.label)}</h4>
            <button class="icon-btn" data-channel-key="${escapeAttr(e.key)}" ${canRunDiscoverBrowse() ? "" : "disabled"}>↻ refresh</button>
          </div>
          <div class="channel-body">
            <div class="empty-state">Tap refresh to generate suggestions</div>
          </div>
        </div>
      `).join("")}
    </div>
    <div id="saved-container-browse"></div>
  `;

  renderSavedStrip("saved-container-browse");

  panelBrowse.querySelectorAll("[data-channel-key]").forEach((btn) => {
    btn.onclick = () => {
      const entry = entries.find((e) => e.key === btn.dataset.channelKey);
      if (entry) loadBrowseChannel(entry);
    };
  });

  if (isFriend && state.browse.vibesList.length > 0) {
    document.getElementById("btn-save-vibe-slots").onclick = async () => {
      const vibeIds = [0, 1, 2]
        .map((i) => document.getElementById(`vibe-slot-${i}`).value)
        .filter(Boolean);
      try {
        const data = await api("/browse-slots", { method: "POST", needsAuth: true, body: { vibeIds } });
        state.browse.vibeSlots = data.browseVibeSlots || [];
        toast("Channels updated");
        renderBrowse();
      } catch (err) {
        toast(err.message);
      }
    };
  }
}

function slug(s) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "-");
}

async function loadBrowseChannel(entry) {
  if (!canRunDiscoverBrowse()) {
    toast("Refresh needs admin or a Friend account — you're viewing a preview");
    return;
  }
  const container = document.querySelector(`#channel-${slug(entry.key)} .channel-body`);
  container.innerHTML = `<div class="empty-state"><span class="spinner"></span> Loading...</div>`;
  try {
    const body = entry.kind === "vibe" ? { vibeId: entry.vibeId } : { channel: entry.channel };
    const data = await api("/browse", { method: "POST", needsAuth: true, body });
    const tracks = data.tracks || [];
    state.browse.channels[entry.key].tracks = tracks;
    if (tracks.length === 0) {
      container.innerHTML = `<div class="empty-state">No suggestions returned.</div>`;
      return;
    }
    container.innerHTML = tracks
      .map(
        (t, i) => `
      <div class="channel-track">
        <div class="track-info">
          <div class="track-title">${escapeHtml(t.artist || "")}${t.track ? " — " + escapeHtml(t.track) : " — browse catalog"}</div>
          <div class="track-meta">${escapeHtml(t.label || "")}${t.release_date ? " · " + escapeHtml(t.release_date) : ""}</div>
        </div>
        <button class="add-btn" data-i="${i}">+</button>
      </div>`
      )
      .join("");
    container.querySelectorAll(".add-btn").forEach((btn) => {
      btn.onclick = () => {
        const t = state.browse.channels[entry.key].tracks[+btn.dataset.i];
        addToSavedList(t);
        btn.classList.add("added");
        btn.textContent = "✓";
      };
    });
  } catch (err) {
    container.innerHTML = errorCardHtml(err.message);
  }
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
