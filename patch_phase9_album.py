#!/usr/bin/env python3
"""
Adds Album capture to both Rekordbox parsers — same class of fix as the
earlier Time field gap. Tested against real export data: 169/170 tracks
captured Album correctly (the one miss has no Album tag in the source file).
Run this from inside mymusicapp/.
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
      time: formatSecondsAsTime(el.getAttribute("TotalTime")),
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
      album: el.getAttribute("Album") || "",
      genre: el.getAttribute("Genre") || "",
      bpm: el.getAttribute("AverageBpm") || "",
      key: el.getAttribute("Tonality") || "",
      time: formatSecondsAsTime(el.getAttribute("TotalTime")),
      label: el.getAttribute("Label") || "",
    });
  });
  return tracks;
}''',
    ),
    (
        '''  const trackIdx = colIndex("Track Title", "Name");
  const artistIdx = colIndex("Artist");
  const genreIdx = colIndex("Genre");
  const bpmIdx = colIndex("BPM");
  const keyIdx = colIndex("Key", "Tonality");
  const timeIdx = colIndex("Time");
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
      time: timeIdx !== -1 ? (cols[timeIdx] || "").trim() : "",
      label: labelIdx !== -1 ? (cols[labelIdx] || "").trim() : "",
    });
  }''',
        '''  const trackIdx = colIndex("Track Title", "Name");
  const artistIdx = colIndex("Artist");
  const albumIdx = colIndex("Album");
  const genreIdx = colIndex("Genre");
  const bpmIdx = colIndex("BPM");
  const keyIdx = colIndex("Key", "Tonality");
  const timeIdx = colIndex("Time");
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
      album: albumIdx !== -1 ? (cols[albumIdx] || "").trim() : "",
      genre: genreIdx !== -1 ? (cols[genreIdx] || "").trim() : "",
      bpm: bpmIdx !== -1 ? (cols[bpmIdx] || "").trim() : "",
      key: keyIdx !== -1 ? (cols[keyIdx] || "").trim() : "",
      time: timeIdx !== -1 ? (cols[timeIdx] || "").trim() : "",
      label: labelIdx !== -1 ? (cols[labelIdx] || "").trim() : "",
    });
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

    if "el.getAttribute(\"Album\")" in text:
        print(f"{PATH}: Album capture already present — skipping (already patched).")
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
