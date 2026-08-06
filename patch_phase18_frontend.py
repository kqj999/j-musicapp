#!/usr/bin/env python3
"""
Phase 3 frontend: the picker that used to be Friend-only ("Your Custom
Channels") is now shown to any named user, and relabels itself to
"Shared Vibes" for the owner specifically — same component, same Save
button, just what it controls (and who sees the result) differs. Channel
cards gain a description line, sourced from each Vibe's own description
(with the owner's auto-generated "Shared by..." fallback for the shared
row, computed server-side).

Requires the app.js state from patch_phase16_browse_persist.py already
applied (reuses browseChannelBodyHtml/wireBrowseChannelAddButtons).
Run this from inside mymusicapp/.
"""
import pathlib
import re
import sys

PATH = pathlib.Path("app.js")

EDITS = [
    (
        '''function buildBrowseEntries() {
  const fixedNames = state.browse.fixedChannels.length ? state.browse.fixedChannels : BROWSE_CHANNELS;
  const fixed = fixedNames.map((name) => ({ key: `fixed:${name}`, label: name, kind: "fixed", channel: name }));
  const vibeEntries = (state.browse.vibeSlots || [])
    .map((id) => state.browse.vibesList.find((v) => v.id === id))
    .filter(Boolean)
    .map((v) => ({ key: `vibe:${v.id}`, label: `✦ ${v.name}`, kind: "vibe", vibeId: v.id }));
  return [...fixed, ...vibeEntries];
}''',
        '''function buildBrowseEntries() {
  const shared = (state.browse.sharedVibes || []).map((v) => ({
    key: `shared:${v.id}`,
    label: `★ ${v.name}`,
    kind: "vibe",
    vibeId: v.id,
    shared: true,
    description: v.description || "",
  }));
  const personal = (state.browse.vibeSlots || [])
    .map((id) => state.browse.vibesList.find((v) => v.id === id))
    .filter(Boolean)
    .map((v) => ({
      key: `vibe:${v.id}`,
      label: `✦ ${v.name}`,
      kind: "vibe",
      vibeId: v.id,
      shared: false,
      description: v.description || "",
    }));
  return [...shared, ...personal];
}''',
    ),
    (
        '''function renderVibeSlotPickerHtml() {
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
}''',
        '''function renderVibeSlotPickerHtml() {
  const vibes = state.browse.vibesList || [];
  const slots = state.browse.vibeSlots || [];
  const isOwner = !!state.browse.isOwner;
  const optionsFor = (selectedId) => `
    <option value="">— none —</option>
    ${vibes.map((v) => `<option value="${escapeAttr(v.id)}" ${v.id === selectedId ? "selected" : ""}>${escapeHtml(v.name)} (${v.trackCount})</option>`).join("")}
  `;
  const title = isOwner ? "★ Shared Vibes" : "✦ Your Custom Channels";
  const subtitle = isOwner ? "up to 3 — shown to every account as the top row" : "up to 3, from your Vibes";
  return `
    <div class="panel" style="padding:16px; margin-bottom:18px;">
      <div class="section-title" style="margin-bottom:10px;">${title} <span style="color:var(--muted); font-weight:400; text-transform:none;">(${subtitle})</span></div>
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
}''',
    ),
    (
        '''async function loadBrowse() {
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
}''',
        '''async function loadBrowse() {
  if (!discoverBrowseVisible()) {
    renderBrowse();
    return;
  }
  try {
    const data = await api("/browse-config", { needsAuth: true });
    state.browse.isOwner = !!data.isOwner;
    state.browse.sharedVibes = data.sharedVibes || [];
    state.browse.vibeSlots = data.vibeSlots || [];
    state.browse.vibesList = data.vibesList || [];
  } catch (err) {
    toast(err.message);
    state.browse.sharedVibes = [];
    state.browse.vibeSlots = [];
    state.browse.vibesList = [];
  }
  state.browse.configLoaded = true;
  renderBrowse();
}''',
    ),
    (
        '${isFriend ? renderVibeSlotPickerHtml() : ""}',
        '${state.username ? renderVibeSlotPickerHtml() : ""}',
    ),
    (
        '''        <div class="panel channel-card" id="channel-${slug(e.key)}">
          <div class="channel-head">
            <h4>${escapeHtml(e.label)}</h4>
            <button class="icon-btn" data-channel-key="${escapeAttr(e.key)}" ${canRunDiscoverBrowse() ? "" : "disabled"}>↻ refresh</button>
          </div>
          <div class="channel-body">''',
        '''        <div class="panel channel-card" id="channel-${slug(e.key)}">
          <div class="channel-head">
            <h4>${escapeHtml(e.label)}</h4>
            <button class="icon-btn" data-channel-key="${escapeAttr(e.key)}" ${canRunDiscoverBrowse() ? "" : "disabled"}>↻ refresh</button>
          </div>
          ${e.description ? `<div class="channel-description" style="padding:0 16px 10px; color:var(--muted); font-size:11px;">${escapeHtml(e.description)}</div>` : ""}
          <div class="channel-body">''',
    ),
    (
        'if (isFriend && state.browse.vibesList.length > 0) {',
        'if (state.username && state.browse.vibesList.length > 0) {',
    ),
    (
        'const body = entry.kind === "vibe" ? { vibeId: entry.vibeId } : { channel: entry.channel };',
        'const body = { vibeId: entry.vibeId, shared: !!entry.shared };',
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

    if "sharedVibes" in text:
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
