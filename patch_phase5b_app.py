#!/usr/bin/env python3
"""
Adds Rekordbox TXT playlist-export support to the Import tab, alongside the
existing XML collection import. Run this from inside mymusicapp/.
"""
import pathlib
import re
import sys

PATH = pathlib.Path("app.js")

EDITS = [
    (
        '''function parseRekordboxXML(xmlText) {
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
}''',
        '''function parseRekordboxXML(xmlText) {
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

// Rekordbox's "Export Playlist to TXT" is tab-separated, but the file itself
// is usually UTF-16 (with a byte-order-mark) rather than UTF-8 — reading it
// as plain text mangles special characters, so decode by BOM first.
function decodeRekordboxTextFile(buffer) {
  const bytes = new Uint8Array(buffer);
  if (bytes.length >= 2 && bytes[0] === 0xff && bytes[1] === 0xfe) {
    return new TextDecoder("utf-16le").decode(bytes.slice(2));
  }
  if (bytes.length >= 2 && bytes[0] === 0xfe && bytes[1] === 0xff) {
    return new TextDecoder("utf-16be").decode(bytes.slice(2));
  }
  return new TextDecoder("utf-8").decode(bytes);
}

// Parses a Rekordbox "Export Playlist to TXT" file — tab-separated, header
// row names columns (varies slightly by Rekordbox version), one track per
// line after that.
function parseRekordboxTXT(text) {
  const lines = text.replace(/\\r\\n/g, "\\n").replace(/\\r/g, "\\n").split("\\n").filter((l) => l.trim() !== "");
  if (lines.length < 2) return [];

  const headers = lines[0].split("\\t").map((h) => h.trim());
  const colIndex = (...names) => {
    for (const name of names) {
      const i = headers.findIndex((h) => h.toLowerCase() === name.toLowerCase());
      if (i !== -1) return i;
    }
    return -1;
  };

  const trackIdx = colIndex("Track Title", "Name");
  const artistIdx = colIndex("Artist");
  const genreIdx = colIndex("Genre");
  const bpmIdx = colIndex("BPM");
  const keyIdx = colIndex("Key", "Tonality");
  const labelIdx = colIndex("Label");

  const tracks = [];
  for (let i = 1; i < lines.length; i++) {
    const cols = lines[i].split("\\t");
    const artist = artistIdx !== -1 ? (cols[artistIdx] || "").trim() : "";
    const track = trackIdx !== -1 ? (cols[trackIdx] || "").trim() : "";
    if (!artist && !track) continue;
    tracks.push({
      artist,
      track,
      genre: genreIdx !== -1 ? (cols[genreIdx] || "").trim() : "",
      bpm: bpmIdx !== -1 ? (cols[bpmIdx] || "").trim() : "",
      key: keyIdx !== -1 ? (cols[keyIdx] || "").trim() : "",
      label: labelIdx !== -1 ? (cols[labelIdx] || "").trim() : "",
    });
  }
  return tracks;
}''',
    ),
    (
        '        For best results, organize into playlists by vibe/genre in Rekordbox before exporting.',
        '''        For best results, organize into playlists by vibe/genre in Rekordbox before exporting. A full XML
        collection export or a single playlist exported to TXT both work — TXT is usually the better pick
        if you want to import just one playlist rather than your whole library.''',
    ),
    (
        '<div class="section-title">✦ Rekordbox XML</div>',
        '<div class="section-title">✦ Rekordbox Export (XML or TXT)</div>',
    ),
    (
        '<input class="input" id="import-file-input" type="file" accept=".xml" style="flex:1;" />',
        '<input class="input" id="import-file-input" type="file" accept=".xml,.txt" style="flex:1;" />',
    ),
    (
        '''  document.getElementById("import-file-input").onchange = async (e) => {
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
  };''',
        '''  document.getElementById("import-file-input").onchange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    try {
      const isTxt = file.name.toLowerCase().endsWith(".txt");
      let tracks;
      if (isTxt) {
        const buffer = await file.arrayBuffer();
        const text = decodeRekordboxTextFile(buffer);
        tracks = parseRekordboxTXT(text);
      } else {
        const text = await file.text();
        tracks = parseRekordboxXML(text);
      }
      if (tracks.length === 0) {
        toast(isTxt
          ? "No tracks found — check this is a Rekordbox playlist exported to TXT"
          : "No tracks found in that file's COLLECTION section");
        return;
      }
      imp.tracks = tracks;
      imp.fileName = file.name;
      renderImport();
    } catch (err) {
      toast(err.message);
    }
  };''',
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
