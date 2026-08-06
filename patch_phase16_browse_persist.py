#!/usr/bin/env python3
"""
Fixes Browse results appearing to vanish when you switch tabs and come
back. The generated tracks were never actually lost — state.browse.channels
keeps them fine. renderBrowse()'s card template just always showed the
"Tap refresh..." placeholder regardless of whether that channel already had
results sitting in memory. Pulls the track-card markup into a shared
helper so the initial render and the post-refresh render can never drift
into two different versions of the same thing.

Same caveat as recent patches in this thread: built entirely from pasted
fragments, not a full copy of app.js. Every edit is anchored to text
you've personally pasted back. Run this from inside mymusicapp/.
"""
import pathlib
import re
import sys

PATH = pathlib.Path("app.js")

EDITS = [
    (
        '''      ${entries.map((e) => `
        <div class="panel channel-card" id="channel-${slug(e.key)}">
          <div class="channel-head">
            <h4>${escapeHtml(e.label)}</h4>
            <button class="icon-btn" data-channel-key="${escapeAttr(e.key)}" ${canRunDiscoverBrowse() ? "" : "disabled"}>↻ refresh</button>
          </div>
          <div class="channel-body">
            <div class="empty-state">Tap refresh to generate suggestions</div>
          </div>
        </div>
      `).join("")}''',
        '''      ${entries.map((e) => `
        <div class="panel channel-card" id="channel-${slug(e.key)}">
          <div class="channel-head">
            <h4>${escapeHtml(e.label)}</h4>
            <button class="icon-btn" data-channel-key="${escapeAttr(e.key)}" ${canRunDiscoverBrowse() ? "" : "disabled"}>↻ refresh</button>
          </div>
          <div class="channel-body">
            ${browseChannelBodyHtml(e, state.browse.channels[e.key] || { tracks: [] })}
          </div>
        </div>
      `).join("")}''',
    ),
    (
        '''  panelBrowse.querySelectorAll("[data-channel-key]").forEach((btn) => {
    btn.onclick = () => {
      const entry = entries.find((e) => e.key === btn.dataset.channelKey);
      if (entry) loadBrowseChannel(entry);
    };
  });''',
        '''  panelBrowse.querySelectorAll("[data-channel-key]").forEach((btn) => {
    btn.onclick = () => {
      const entry = entries.find((e) => e.key === btn.dataset.channelKey);
      if (entry) loadBrowseChannel(entry);
    };
  });

  // Re-wire the + buttons for any channel that already had results sitting
  // in memory from before the tab switch — loadBrowseChannel only wires
  // these after a fresh fetch, so already-populated cards need it here too.
  entries.forEach((e) => {
    const existingContainer = document.querySelector(`#channel-${slug(e.key)} .channel-body`);
    if (existingContainer) wireBrowseChannelAddButtons(e, existingContainer);
  });''',
    ),
    (
        '''async function loadBrowseChannel(entry) {
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
        '''// Shared by renderBrowse() (rendering already-loaded results on a fresh
// page render / tab switch) and loadBrowseChannel() (rendering just-fetched
// results after a refresh) — one source of truth for what a channel's
// track list looks like, so the two call sites can't drift apart.
function browseChannelBodyHtml(entry, channelState) {
  const tracks = (channelState && channelState.tracks) || [];
  if (tracks.length === 0) {
    return `<div class="empty-state">Tap refresh to generate suggestions</div>`;
  }
  return tracks
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
}

function wireBrowseChannelAddButtons(entry, container) {
  container.querySelectorAll(".add-btn").forEach((btn) => {
    btn.onclick = () => {
      const t = state.browse.channels[entry.key].tracks[+btn.dataset.i];
      addToSavedList(t);
      btn.classList.add("added");
      btn.textContent = "✓";
    };
  });
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
    container.innerHTML = browseChannelBodyHtml(entry, state.browse.channels[entry.key]);
    wireBrowseChannelAddButtons(entry, container);
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

    if "browseChannelBodyHtml" in text:
        print(f"{PATH}: already patched — skipping.")
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
