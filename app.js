/* ============================================================================
   JADE — frontend logic
   Edit WORKER_URL below once your Cloudflare Worker is deployed.
   ============================================================================ */

const WORKER_URL = "https://jade-music-proxy.kqj.workers.dev";

const VIBE_PILLS = ["Sandy Techno", "RDH", "Goth Girl Techno", "Gothy Meowwave", "Hot Girl Techno", "House Cat"];
const BROWSE_CHANNELS = ["Sandy Techno", "RDH Techno", "Hot Girl Techno", "Goth Girl Techno", "Cool Remixes", "House Cat"];

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const state = {
  authLevel: sessionStorage.getItem("jade_auth_level") || "none", // 'none' | 'guest' | 'view' | 'friend' | 'admin'
  pin: sessionStorage.getItem("jade_pin") || "",
  name: sessionStorage.getItem("jade_name") || "",
  username: sessionStorage.getItem("jade_username") || "",
  pinInput: "",
  activeTab: "discover",

  discover: { activeVibe: null, seeds: [], directions: null, savedTracks: [], loading: false },
  browse: { channels: {}, fixedChannels: [], vibeSlots: [], vibesList: [], configLoaded: false }, // channel key -> { tracks: [], loading }
  crate: {
    lists: [], loading: false,
    activeSection: "lists", // "jadeslist" | "lists" | "vibes" | "genres" | "imports"
    activeItemId: null,     // list index (number) for Lists, vibe id (string) for Vibes
    vibesList: [], vibesLoaded: false,
    expanded: { lists: true, vibes: false, genres: false, imports: false },
    sort: { lists: { col: "name", dir: "asc" }, vibes: { col: "name", dir: "asc" } },
    genresList: [], uncategorizedCount: 0, genresLoaded: false,
    genresListEditMode: false, selectedGenreNames: new Set(),
    selectedTrackIds: new Set(), pendingNewGenreName: null,
    batchesList: [], batchesLoaded: false,
    batchesListEditMode: false, selectedBatchIds: new Set(),
    trackViewSort: { col: null, dir: "asc" },
    editMode: false,
    trackSearchQuery: "",
    _lastItemKey: null,
  },
  mixes: { list: [], loading: false },
  profile: null,
  adminUsers: [],
  importState: { tracks: [], fileName: "", mode: "update-collection", vibesList: [], loading: false },
};

BROWSE_CHANNELS.forEach((c) => (state.browse.channels[c] = { tracks: [], loading: false }));

// ---------------------------------------------------------------------------
// API helper
// ---------------------------------------------------------------------------
async function api(path, { method = "GET", body = null, needsAuth = false } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (needsAuth && state.pin) headers["X-Pin"] = state.pin;
  if (needsAuth && state.username) headers["X-Name"] = state.username;
  const res = await fetch(WORKER_URL + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

// Uploads a File to the Worker's R2-backed media store. type is 'audio' or 'cover'.
// Returns the full playable/viewable URL.
async function uploadMedia(file, type) {
  const res = await fetch(`${WORKER_URL}/media/upload?type=${type}`, {
    method: "POST",
    headers: {
      "Content-Type": file.type,
      "X-Pin": state.pin,
    },
    body: file,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Upload failed (${res.status})`);
  return WORKER_URL + data.url;
}

function toast(msg) {
  const t = document.createElement("div");
  t.className = "toast";
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 2200);
}

// ---------------------------------------------------------------------------
// Landing / PIN flow
// ---------------------------------------------------------------------------
const landing = document.getElementById("landing");
const pinScreen = document.getElementById("pin-screen");
const appShell = document.getElementById("app-shell");

document.getElementById("btn-goto-mixes").onclick = () => {
  landing.classList.add("hidden");
  appShell.classList.remove("hidden");
  setActiveTab("mixes");
  renderSessionBadge();
  renderTabLocks();
  renderProfileTabVisibility();
  renderAdminTabVisibility();
  renderImportTabVisibility();
};

document.getElementById("btn-goto-pin").onclick = () => {
  landing.classList.add("hidden");
  pinScreen.classList.remove("hidden");
};

document.getElementById("btn-pin-back").onclick = () => {
  pinScreen.classList.add("hidden");
  landing.classList.remove("hidden");
  state.pinInput = "";
  renderPinDots();
};

const pinDotsEl = document.getElementById("pin-dots");
const pinErrorEl = document.getElementById("pin-error");

function renderPinDots() {
  const dots = pinDotsEl.querySelectorAll(".pin-dot");
  dots.forEach((d, i) => {
    d.classList.toggle("filled", i < state.pinInput.length);
    d.classList.remove("error");
  });
}

document.getElementById("pin-keypad").addEventListener("click", (e) => {
  const btn = e.target.closest(".pin-key");
  if (!btn) return;
  const key = btn.dataset.key;
  pinErrorEl.textContent = "";

  if (key === "back") {
    state.pinInput = state.pinInput.slice(0, -1);
  } else if (key === "clear") {
    state.pinInput = "";
  } else if (state.pinInput.length < 4) {
    state.pinInput += key;
  }
  renderPinDots();

  if (state.pinInput.length === 4) {
    setTimeout(() => submitPin(state.pinInput), 150);
  }
});

// Tiers: 'admin' (full access), 'friend' (own API key, own tier-limited
// channels), 'view' (sees Discover/Browse UI as a preview, but can't
// actually run searches — no credits spent), 'guest' (Discover/Browse stay
// behind a locked teaser), 'none'.
function discoverBrowseVisible() {
  return state.authLevel === "admin" || state.authLevel === "view" || state.authLevel === "friend";
}
function canRunDiscoverBrowse() {
  return state.authLevel === "admin" || state.authLevel === "friend";
}

async function submitPin(pin) {
  const nameInput = document.getElementById("login-name-input");
  const name = nameInput ? nameInput.value.trim() : "";
  try {
    state.pin = pin;
    const headers = { "X-Pin": pin };
    if (name) headers["X-Name"] = name;
    const res = await fetch(WORKER_URL + "/auth", { headers });
    const data = await res.json().catch(() => ({}));
    if (!data.level || data.level === "none") throw new Error("invalid");
    state.authLevel = data.level;
    state.name = data.name || "";
    state.username = data.username || "";

    if (data.pinIsTemp) {
      // First login for a named (Admin/Friend) account — force a real PIN
      // before entering the app. Don't persist a session yet.
      pinScreen.classList.add("hidden");
      state.pinInput = "";
      renderPinDots();
      showResetPinScreen(state.username, pin);
      return;
    }

    sessionStorage.setItem("jade_pin", pin);
    sessionStorage.setItem("jade_auth_level", state.authLevel);
    sessionStorage.setItem("jade_name", state.name);
    sessionStorage.setItem("jade_username", state.username);

    pinScreen.classList.add("hidden");
    appShell.classList.remove("hidden");
    state.pinInput = "";
    renderPinDots();
  renderSessionBadge();
  renderTabLocks();
  renderProfileTabVisibility();
  renderAdminTabVisibility();
  renderImportTabVisibility();
    setActiveTab("discover");
    loadInitialData();
  } catch {
    pinErrorEl.textContent = "Incorrect PIN — try again";
    pinDotsEl.querySelectorAll(".pin-dot").forEach((d) => d.classList.add("error"));
    state.pin = "";
    state.pinInput = "";
    setTimeout(renderPinDots, 500);
  }
}

// ---------------------------------------------------------------------------
// Forced PIN reset (first login for a named Admin/Friend account)
// ---------------------------------------------------------------------------
const resetPinScreen = document.getElementById("reset-pin-screen");
const resetPinDotsEl = document.getElementById("reset-pin-dots");
const resetPinErrorEl = document.getElementById("reset-pin-error");
let resetPinInput = "";
let resetPinUsername = "";
let resetPinCurrentPin = "";

function showResetPinScreen(username, currentPin) {
  resetPinUsername = username;
  resetPinCurrentPin = currentPin;
  resetPinInput = "";
  resetPinErrorEl.textContent = "";
  renderResetPinDots();
  resetPinScreen.classList.remove("hidden");
}

function renderResetPinDots() {
  const dots = resetPinDotsEl.querySelectorAll(".pin-dot");
  dots.forEach((d, i) => {
    d.classList.toggle("filled", i < resetPinInput.length);
    d.classList.remove("error");
  });
}

document.getElementById("reset-pin-keypad").addEventListener("click", (e) => {
  const btn = e.target.closest(".pin-key");
  if (!btn) return;
  const key = btn.dataset.key;
  resetPinErrorEl.textContent = "";

  if (key === "back") {
    resetPinInput = resetPinInput.slice(0, -1);
  } else if (key === "clear") {
    resetPinInput = "";
  } else if (resetPinInput.length < 4) {
    resetPinInput += key;
  }
  renderResetPinDots();

  if (resetPinInput.length === 4) {
    setTimeout(() => submitNewPin(resetPinInput), 150);
  }
});

async function submitNewPin(newPin) {
  try {
    const res = await fetch(WORKER_URL + "/auth/set-pin", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: resetPinUsername, currentPin: resetPinCurrentPin, newPin }),
    });
    const data = await res.json().catch(() => ({}));
    if (!data.ok) throw new Error(data.error || "Could not set PIN");

    state.pin = newPin;
    sessionStorage.setItem("jade_pin", newPin);
    sessionStorage.setItem("jade_auth_level", state.authLevel);
    sessionStorage.setItem("jade_name", state.name);
    sessionStorage.setItem("jade_username", state.username);

    resetPinScreen.classList.add("hidden");
    appShell.classList.remove("hidden");
  renderSessionBadge();
  renderTabLocks();
  renderProfileTabVisibility();
  renderAdminTabVisibility();
  renderImportTabVisibility();
    setActiveTab("discover");
    loadInitialData();
    toast("PIN set — you\'re in");
  } catch (err) {
    resetPinErrorEl.textContent = err.message || "Could not set PIN — try again";
    resetPinDotsEl.querySelectorAll(".pin-dot").forEach((d) => d.classList.add("error"));
    resetPinInput = "";
    setTimeout(renderResetPinDots, 500);
  }
}

document.getElementById("btn-lock").onclick = () => {
  sessionStorage.removeItem("jade_pin");
  sessionStorage.removeItem("jade_auth_level");
  sessionStorage.removeItem("jade_name");
  sessionStorage.removeItem("jade_username");
  state.pin = "";
  state.authLevel = "none";
  state.name = "";
  state.username = "";
  appShell.classList.add("hidden");
  landing.classList.remove("hidden");
};

const SESSION_BADGE_LABELS = { admin: "admin", friend: "friend", view: "view", guest: "guest" };

function renderSessionBadge() {
  const el = document.getElementById("session-badge");
  el.textContent = SESSION_BADGE_LABELS[state.authLevel] || "no pin";
  el.className = "session-badge " + (SESSION_BADGE_LABELS[state.authLevel] ? state.authLevel : "");
}

function renderTabLocks() {
  const locked = !discoverBrowseVisible();
  document.getElementById("lock-discover").textContent = locked ? "🔒" : "";
  document.getElementById("lock-browse").textContent = locked ? "🔒" : "";
}

// Profile tab only makes sense for a named login (Admin/Friend) — View/Guest
// use the shared PINs and have no username to look up.
function renderProfileTabVisibility() {
  const btn = document.querySelector('.tab-btn[data-tab="profile"]');
  if (btn) btn.classList.toggle("hidden", !state.username);
}

// Admin tab is admin-tier only (works with either the flat APP_PIN fallback
// or a named admin login — user management doesn't need to know "which
// admin", unlike Profile).
function renderAdminTabVisibility() {
  const btn = document.querySelector('.tab-btn[data-tab="admin"]');
  if (btn) btn.classList.toggle("hidden", state.authLevel !== "admin");
}

// Import (Rekordbox) is per-user data (Vibes/Uploads), same requirement as
// Profile — needs a named login, not just the shared PIN.
function renderImportTabVisibility() {
  const btn = document.querySelector('.tab-btn[data-tab="import"]');
  if (btn) btn.classList.toggle("hidden", !state.username);
}

// If a PIN session already exists (page reload), resume it
if (state.authLevel !== "none" && state.pin) {
  landing.classList.add("hidden");
  appShell.classList.remove("hidden");
  renderSessionBadge();
  renderTabLocks();
  renderProfileTabVisibility();
  renderAdminTabVisibility();
  renderImportTabVisibility();
}

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.onclick = () => setActiveTab(btn.dataset.tab);
});

function setActiveTab(tab) {
  state.activeTab = tab;
  document.querySelectorAll(".tab-btn").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("active", p.id === "panel-" + tab));

  if (tab === "discover") renderDiscover();
  if (tab === "browse") loadBrowse();
  if (tab === "crate") renderCrate();
  if (tab === "mixes") renderMixes();
  if (tab === "profile") loadProfile();
  if (tab === "admin") loadAdmin();
  if (tab === "import") renderImport();
}

function loadInitialData() {
  if (state.authLevel === "admin") {
    loadCrate();
  } else if (state.authLevel === "guest" || state.authLevel === "view" || state.authLevel === "friend") {
    loadPublicCrate();
  }
  loadCrateVibes();
  loadCrateGenres();
  loadCrateBatches();
  loadMixes();
}

// ============================================================================
// GLOBAL AUDIO PLAYER
// ============================================================================
const audioEl = document.getElementById("global-audio-el");
const playerBar = document.getElementById("player-bar");

const player = {
  queue: [], // array of { artist, track, audioUrl }
  index: 0,
  listName: "",
  playing: false,
};

function playQueue(tracks, startIndex, listName) {
  const playable = tracks.filter((t) => t.audioUrl);
  if (playable.length === 0) {
    toast("No uploaded audio in this list yet");
    return;
  }
  // map startIndex (index within full track array) to index within playable subset
  const target = tracks[startIndex];
  let idx = playable.indexOf(target);
  if (idx === -1) idx = 0;

  player.queue = playable;
  player.index = idx;
  player.listName = listName;
  loadAndPlayCurrent();
}

function loadAndPlayCurrent() {
  const t = player.queue[player.index];
  if (!t) return;
  audioEl.src = t.audioUrl;
  audioEl.play().catch(() => {});
  player.playing = true;
  renderPlayerBar();
}

function playerTogglePause() {
  if (audioEl.paused) {
    audioEl.play().catch(() => {});
    player.playing = true;
  } else {
    audioEl.pause();
    player.playing = false;
  }
  renderPlayerBar();
}

function playerNext() {
  if (player.index < player.queue.length - 1) {
    player.index += 1;
    loadAndPlayCurrent();
  } else {
    audioEl.pause();
    player.playing = false;
    renderPlayerBar();
  }
}

function playerPrev() {
  if (player.index > 0) {
    player.index -= 1;
    loadAndPlayCurrent();
  }
}

audioEl.addEventListener("ended", playerNext);
audioEl.addEventListener("timeupdate", updateProgressFill);
audioEl.addEventListener("play", () => { player.playing = true; renderPlayerBar(); });
audioEl.addEventListener("pause", () => { player.playing = false; renderPlayerBar(); });

function updateProgressFill() {
  const fill = document.getElementById("player-progress-fill");
  if (!fill || !audioEl.duration) return;
  fill.style.width = `${(audioEl.currentTime / audioEl.duration) * 100}%`;
}

function renderPlayerBar() {
  const t = player.queue[player.index];
  if (!t) {
    playerBar.classList.add("hidden");
    document.body.classList.remove("has-player");
    return;
  }
  playerBar.classList.remove("hidden");
  document.body.classList.add("has-player");

  playerBar.innerHTML = `
    <div class="player-controls">
      <button class="icon-btn" id="player-prev">⏮</button>
      <button class="btn btn-sm btn-primary" id="player-toggle">${player.playing ? "⏸" : "▶"}</button>
      <button class="icon-btn" id="player-next">⏭</button>
    </div>
    <div class="player-info">
      <div class="player-track">${escapeHtml(t.artist)}${t.track ? " — " + escapeHtml(t.track) : ""}</div>
      <div class="player-list">${escapeHtml(player.listName)} · ${player.index + 1}/${player.queue.length}</div>
    </div>
    <div class="player-progress" id="player-progress">
      <div class="player-progress-fill" id="player-progress-fill"></div>
    </div>
  `;

  document.getElementById("player-toggle").onclick = playerTogglePause;
  document.getElementById("player-next").onclick = playerNext;
  document.getElementById("player-prev").onclick = playerPrev;
  document.getElementById("player-progress").onclick = (e) => {
    if (!audioEl.duration) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    audioEl.currentTime = pct * audioEl.duration;
  };
}

// ============================================================================
// MODAL (used by Mixes editor)
// ============================================================================
const modalOverlay = document.getElementById("modal-overlay");

function openModal(html, onMount) {
  modalOverlay.innerHTML = `<div class="panel panel-glow modal-panel">${html}</div>`;
  modalOverlay.classList.remove("hidden");
  modalOverlay.onclick = (e) => {
    if (e.target === modalOverlay) closeModal();
  };
  if (onMount) onMount(modalOverlay);
}

function closeModal() {
  modalOverlay.classList.add("hidden");
  modalOverlay.innerHTML = "";
}

// ============================================================================
// DISCOVER TAB
// ============================================================================
const panelDiscover = document.getElementById("panel-discover");

function renderDiscover() {
  if (!discoverBrowseVisible()) {
    panelDiscover.innerHTML = `
      <div class="panel locked-teaser">
        <h3>🔒 Discover</h3>
        <p>Discover generates three fresh directions — Deeper, Lateral, Wild Card — from any seed track, artist, or vibe, tuned to Jade's exact taste and library.</p>
        <button class="btn" id="teaser-pin-discover">Enter Pin</button>
      </div>`;
    document.getElementById("teaser-pin-discover").onclick = () => {
      appShell.classList.add("hidden");
      pinScreen.classList.remove("hidden");
    };
    return;
  }

  const d = state.discover;

  panelDiscover.innerHTML = `
    <div class="section-title"><span class="star">✦</span> Vibe</div>
    <div class="pill-row" id="vibe-pills"></div>

    <div class="section-title"><span class="star">✦</span> Seeds <span style="color:var(--muted); font-weight:400; text-transform:none;">(up to 3 — artist, track, or vibe)</span></div>
    <div class="seed-row">
      <input class="input" id="seed-input" placeholder="e.g. Mython, Bespoke, dusty hypnotic groove..." ${canRunDiscoverBrowse() ? "" : "disabled"} />
      <button class="btn" id="btn-add-seed" ${canRunDiscoverBrowse() ? "" : "disabled"}>Add</button>
    </div>
    <div class="seed-chips" id="seed-chips"></div>

    <button class="btn btn-primary" id="btn-search" ${d.loading || !canRunDiscoverBrowse() ? "disabled" : ""}>
      ${d.loading ? '<span class="spinner"></span> Searching...' : "🔍 Search"}
    </button>

    <div id="directions-container"></div>
    <div id="saved-container-discover"></div>
  `;

  renderVibePills();
  renderSeedChips();
  renderDirections();
  renderSavedStrip("saved-container-discover");

  document.getElementById("btn-add-seed").onclick = addSeedFromInput;
  document.getElementById("seed-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter") addSeedFromInput();
  });
  document.getElementById("btn-search").onclick = runDiscoverSearch;
}

function renderVibePills() {
  const el = document.getElementById("vibe-pills");
  el.innerHTML = VIBE_PILLS.map(
    (v) => `<button class="pill ${state.discover.activeVibe === v ? "active" : ""}" data-vibe="${v}" ${canRunDiscoverBrowse() ? "" : "disabled"}>${v}</button>`
  ).join("");
  el.querySelectorAll(".pill").forEach((p) => {
    p.onclick = () => {
      state.discover.activeVibe = state.discover.activeVibe === p.dataset.vibe ? null : p.dataset.vibe;
      renderVibePills();
    };
  });
}

function addSeedFromInput() {
  const input = document.getElementById("seed-input");
  const val = input.value.trim();
  if (!val) return;
  if (state.discover.seeds.length >= 3) {
    toast("Max 3 seeds — remove one first");
    return;
  }
  state.discover.seeds.push(val);
  input.value = "";
  renderSeedChips();
}

function renderSeedChips() {
  const el = document.getElementById("seed-chips");
  el.innerHTML = state.discover.seeds
    .map((s, i) => `<div class="seed-chip">${escapeHtml(s)} <button data-i="${i}">✕</button></div>`)
    .join("");
  el.querySelectorAll("button").forEach((b) => {
    b.onclick = () => {
      state.discover.seeds.splice(+b.dataset.i, 1);
      renderSeedChips();
    };
  });
}

async function runDiscoverSearch() {
  if (!canRunDiscoverBrowse()) {
    toast("Search is admin-only — you're viewing a preview");
    return;
  }
  if (state.discover.seeds.length === 0 && !state.discover.activeVibe) {
    toast("Add a seed or pick a vibe first");
    return;
  }
  state.discover.loading = true;
  renderDiscover();
  try {
    const data = await api("/discover", {
      method: "POST",
      needsAuth: true,
      body: { seeds: state.discover.seeds, vibe: state.discover.activeVibe },
    });
    state.discover.directions = data.directions || [];
  } catch (err) {
    toast(err.message);
  } finally {
    state.discover.loading = false;
    renderDiscover();
  }
}

async function refineFromSaved() {
  if (!canRunDiscoverBrowse()) {
    toast("Search is admin-only — you're viewing a preview");
    return;
  }
  if (state.discover.savedTracks.length === 0) return;
  state.discover.loading = true;
  renderDiscover();
  try {
    const data = await api("/discover", {
      method: "POST",
      needsAuth: true,
      body: { refine_from: state.discover.savedTracks },
    });
    state.discover.directions = data.directions || [];
  } catch (err) {
    toast(err.message);
  } finally {
    state.discover.loading = false;
    renderDiscover();
  }
}

function directionClass(label) {
  const l = (label || "").toLowerCase();
  if (l.includes("deeper")) return "deeper";
  if (l.includes("lateral")) return "lateral";
  return "wild-card";
}

function renderDirections() {
  const el = document.getElementById("directions-container");
  if (!el) return;
  const dirs = state.discover.directions;
  if (!dirs) {
    el.innerHTML = "";
    return;
  }
  if (dirs.length === 0) {
    el.innerHTML = `<div class="empty-state">No directions returned. Try different seeds.</div>`;
    return;
  }

  el.innerHTML = `<div class="directions-grid">
    ${dirs
      .map(
        (dir, di) => `
      <div class="panel direction-card ${directionClass(dir.label)}">
        <div class="direction-label">${escapeHtml(dir.label || "")}</div>
        <div class="direction-why">${escapeHtml(dir.why || "")}</div>
        ${(dir.suggestions || [])
          .map(
            (s, si) => `
          <div class="track-row">
            <div class="track-info">
              <div class="track-title">${escapeHtml(s.artist || "")}${s.track ? " — " + escapeHtml(s.track) : " — browse catalog"}</div>
              <div class="track-meta">${escapeHtml(s.label || "")}${s.label ? " · " : ""}${escapeHtml(s.note || "")}</div>
            </div>
            <button class="add-btn" data-di="${di}" data-si="${si}">+</button>
          </div>`
          )
          .join("")}
      </div>`
      )
      .join("")}
  </div>`;

  el.querySelectorAll(".add-btn").forEach((btn) => {
    btn.onclick = () => {
      const dir = dirs[+btn.dataset.di];
      const s = dir.suggestions[+btn.dataset.si];
      addToSavedList(s);
      btn.classList.add("added");
      btn.textContent = "✓";
    };
  });
}

function addToSavedList(track) {
  state.discover.savedTracks.push(track);
  renderSavedStrip("saved-container-discover");
  renderSavedStrip("saved-container-browse");
  toast(`Saved ${track.artist}${track.track ? " — " + track.track : ""}`);
}

function renderSavedStrip(containerId) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const saved = state.discover.savedTracks;
  if (saved.length === 0) {
    el.innerHTML = "";
    return;
  }
  el.innerHTML = `
    <div class="panel saved-strip">
      <div class="section-title">✦ Saved this session (${saved.length})</div>
      <div class="saved-list">
        ${saved.map((t) => `<div class="saved-chip">${escapeHtml(t.artist)}${t.track ? " — " + escapeHtml(t.track) : ""}</div>`).join("")}
      </div>
      <div style="display:flex; gap:10px; flex-wrap:wrap;">
        <button class="btn btn-pink btn-sm" data-action="refine">↻ Refine from this list</button>
        <button class="btn btn-primary btn-sm" data-action="save-crate">Save all to Crate</button>
      </div>
    </div>`;
  el.querySelector('[data-action="refine"]').onclick = refineFromSaved;
  el.querySelector('[data-action="save-crate"]').onclick = () => saveTracksToCrate(state.discover.savedTracks);
}

// ============================================================================
// BROWSE TAB
// ============================================================================
const panelBrowse = document.getElementById("panel-browse");

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
}

// ============================================================================
// CRATE TAB
// ============================================================================
const panelCrate = document.getElementById("panel-crate");

// Lists are addressed by real id now (matches Vibes/Genres), not array
// position — this is the one lookup point everything else should use.
function crateFindList(id) {
  return state.crate.lists.find((l) => l.id === id);
}

async function loadCrate() {
  state.crate.loading = true;
  try {
    const data = await api("/crate", { needsAuth: true });
    state.crate.lists = data.lists || [];
  } catch (err) {
    toast(err.message);
  } finally {
    state.crate.loading = false;
    if (state.activeTab === "crate") renderCrate();
  }
}

async function loadPublicCrate() {
  try {
    const data = await api("/public-crate", { needsAuth: true });
    state.crate.lists = data.lists || [];
  } catch (err) {
    toast(err.message);
  } finally {
    if (state.activeTab === "crate") renderCrate();
  }
}

// Vibes are per-user (Admin or Friend, named login required) — reuses the
// GET /vibes endpoint Import already built in Phase 5. Guest/View/flat-PIN
// admin just see an empty Vibes section.
async function loadCrateVibes() {
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
}

// Source of Truth — one row per import batch (Discovered Tracks from
// Discover/Browse "+", plus one per file you've run through Import).
async function loadCrateBatches() {
  if (!state.username) {
    state.crate.batchesList = [];
    state.crate.batchesLoaded = true;
    return;
  }
  try {
    const data = await api("/imports", { needsAuth: true });
    state.crate.batchesList = data.batches || [];
  } catch (err) {
    state.crate.batchesList = [];
  }
  state.crate.batchesLoaded = true;
  if (state.activeTab === "crate") renderCrate();
}

async function persistCrate() {
  if (state.authLevel !== "admin") return;
  try {
    await api("/crate", { method: "POST", needsAuth: true, body: { lists: state.crate.lists } });
  } catch (err) {
    toast("Save failed: " + err.message);
  }
}

// The "+" save button on Discover/Browse. Creates real Uploads (not
// disconnected copies) filed under the reserved Discovered Tracks batch —
// any named user can use this now, not just Admin, since it's scoped to
// their own Uploads same as Vibes/Genres/Import already are.
async function saveTracksToCrate(tracks) {
  if (!state.username) {
    toast("Log in with your name to save tracks");
    return;
  }
  try {
    await api("/imports/save-discovered", { method: "POST", needsAuth: true, body: { tracks } });
    toast(`Saved ${tracks.length} track(s) to Discovered Tracks`);
    loadCrateBatches();
  } catch (err) {
    toast(err.message);
  }
}

function renderCrate() {
  if (state.authLevel === "none") {
    panelCrate.innerHTML = `<div class="panel locked-teaser"><h3>Crate</h3><p>Enter a PIN to view saved lists.</p></div>`;
    return;
  }

  panelCrate.innerHTML = `
    <div class="crate-layout">
      <div class="crate-sidebar-shell" id="crate-sidebar"></div>
      <div class="panel crate-main" id="crate-main"></div>
    </div>
  `;

  renderCrateSidebar();
  renderCrateMain();
}

const CRATE_SECTIONS = [
  { key: "lists", label: "My Lists" },
  { key: "vibes", label: "Vibe Curation" },
  { key: "genres", label: "Genres" },
  { key: "imports", label: "Source of Truth" },
];

// Returns up to 5 preview items { id, label } for a section box, plus the
// full count (used nowhere yet but kept for parity with a possible "+N more").
function crateSectionPreviewItems(key) {
  const c = state.crate;
  if (key === "lists") {
    return c.lists.slice(0, 5).map((l) => ({ id: l.id, label: l.name }));
  }
  if (key === "vibes") {
    return c.vibesList.slice(0, 5).map((v) => ({ id: v.id, label: v.name }));
  }
  if (key === "genres") {
    const items = c.uncategorizedCount > 0 ? [{ id: "Uncategorized", label: "Uncategorized" }] : [];
    return items.concat(c.genresList.slice(0, Math.max(0, 5 - items.length)).map((g) => ({ id: g.name, label: g.name })));
  }
  if (key === "imports") {
    const sorted = [...c.batchesList].sort((a, b) => (a.id === "discovered" ? -1 : b.id === "discovered" ? 1 : 0));
    return sorted.slice(0, 5).map((b) => ({ id: b.id, label: b.filename }));
  }
  return [];
}

function renderCrateSidebar() {
  const el = document.getElementById("crate-sidebar");
  const c = state.crate;

  const jadesListHtml = `
    <div class="jades-list-pinned ${c.activeSection === "jadeslist" ? "active" : ""}" data-section="jadeslist">
      <span class="star">★</span> <span class="crate-box-title">Jade's List</span>
    </div>
  `;

  const boxesHtml = CRATE_SECTIONS.map((sec) => {
    const expanded = c.expanded[sec.key];
    const isActive = c.activeSection === sec.key;
    const preview = expanded ? crateSectionPreviewItems(sec.key) : [];
    return `
      <div class="section-box ${isActive ? "active" : ""}">
        <div class="section-box-header">
          <span class="crate-box-title" data-open-section="${sec.key}">${sec.label}</span>
          <span class="tree-caret" data-toggle-section="${sec.key}">${expanded ? "▾" : "▸"}</span>
        </div>
        ${expanded ? `
          <div class="section-box-preview">
            ${preview.length === 0
              ? `<div class="crate-tree-empty">${sec.key === "lists" || sec.key === "vibes" || sec.key === "genres" || sec.key === "imports" ? "Nothing here yet" : "Coming in a future step"}</div>`
              : preview.map((item) => {
                  const isOpen = isActive && String(item.id) === String(c.activeItemId);
                  return `
                  <div class="section-box-preview-item ${isOpen ? "open" : ""}" data-open-item="${sec.key}" data-item-id="${escapeAttr(String(item.id))}">
                    ${isOpen ? '<span class="star filled">★</span> ' : ""}${escapeHtml(item.label)}
                  </div>`;
                }).join("")
            }
          </div>
        ` : ""}
      </div>
    `;
  }).join("");

  el.innerHTML = jadesListHtml + boxesHtml;

  el.querySelector('[data-section="jadeslist"]').onclick = () => {
    state.crate.activeSection = "jadeslist";
    state.crate.activeItemId = null;
    renderCrateSidebar();
    renderCrateMain();
  };

  // Clicking the title opens the section's list-view (and expands its box).
  el.querySelectorAll("[data-open-section]").forEach((titleEl) => {
    titleEl.onclick = () => {
      const key = titleEl.dataset.openSection;
      state.crate.activeSection = key;
      state.crate.activeItemId = null;
      state.crate.expanded[key] = true;
      renderCrateSidebar();
      renderCrateMain();
    };
  });

  // The caret ONLY toggles the preview open/closed — doesn't touch the right pane.
  el.querySelectorAll("[data-toggle-section]").forEach((caretEl) => {
    caretEl.onclick = (e) => {
      e.stopPropagation();
      const key = caretEl.dataset.toggleSection;
      state.crate.expanded[key] = !state.crate.expanded[key];
      renderCrateSidebar();
    };
  });

  // Clicking a preview item opens that item's track-view directly.
  el.querySelectorAll("[data-open-item]").forEach((itemEl) => {
    itemEl.onclick = () => {
      const key = itemEl.dataset.openItem;
      const rawId = itemEl.dataset.itemId;
      state.crate.activeSection = key;
      state.crate.activeItemId = rawId;
      renderCrateSidebar();
      renderCrateMain();
    };
  });
}

function crateSortIndicator(section, col) {
  const s = state.crate.sort[section];
  if (!s || s.col !== col) return "";
  return s.dir === "asc" ? " ▲" : " ▼";
}

function crateSortRows(section, rows) {
  const s = state.crate.sort[section];
  if (!s) return rows;
  const sorted = [...rows].sort((a, b) => {
    let av = a[s.col], bv = b[s.col];
    if (s.col === "trackCount") { av = av || 0; bv = bv || 0; }
    else { av = (av || "").toString().toLowerCase(); bv = (bv || "").toString().toLowerCase(); }
    if (av < bv) return s.dir === "asc" ? -1 : 1;
    if (av > bv) return s.dir === "asc" ? 1 : -1;
    return 0;
  });
  // Vibes active-in-Browse always float to the top, regardless of sort.
  if (section === "vibes") {
    sorted.sort((a, b) => (b.isActiveInBrowse ? 1 : 0) - (a.isActiveInBrowse ? 1 : 0));
  }
  return sorted;
}

function renderCrateListView(el, section) {
  const c = state.crate;
  const sectionLabel = CRATE_SECTIONS.find((s) => s.key === section).label;

  if (section === "imports") {
    renderCrateBatchesListView(el);
    return;
  }

  if (section === "genres") {
    renderCrateGenresListView(el);
    return;
  }

  const isLists = section === "lists";
  const rawRows = isLists
    ? c.lists.map((l) => ({ id: l.id, name: l.name, trackCount: l.tracks.length, updatedAt: l.updatedAt || null }))
    : c.vibesList.map((v) => ({ id: v.id, name: v.name, trackCount: v.trackCount, updatedAt: v.updatedAt || null, isActiveInBrowse: v.isActiveInBrowse }));

  const rows = crateSortRows(section, rawRows);
  const curateLabel = isLists ? "+ New List" : "+ Curate Vibe";
  const canCurate = isLists ? state.authLevel === "admin" : !!state.username;

  el.innerHTML = `
    <div class="channel-head">
      <h4 class="crate-heading">${escapeHtml(sectionLabel)}</h4>
      ${canCurate ? `<button class="btn btn-sm btn-primary" id="btn-curate">${curateLabel}</button>` : ""}
    </div>
    ${rows.length === 0 ? `<div class="empty-state" style="padding:40px 0;">Nothing here yet</div>` : `
      <table class="crate-list-table">
        <thead>
          <tr>
            <th data-sort-col="name">Title${crateSortIndicator(section, "name")}</th>
            <th data-sort-col="trackCount"># of Tracks${crateSortIndicator(section, "trackCount")}</th>
            <th data-sort-col="updatedAt">Last Updated${crateSortIndicator(section, "updatedAt")}</th>
          </tr>
        </thead>
        <tbody>
          ${rows.map((r) => `
            <tr class="crate-list-row ${r.isActiveInBrowse ? "browse-active" : ""}" data-open-row="${escapeAttr(String(r.id))}">
              <td>${r.isActiveInBrowse ? '<span class="star filled">★</span> ' : ""}${escapeHtml(r.name)}</td>
              <td>${r.trackCount}</td>
              <td>${r.updatedAt ? new Date(r.updatedAt).toLocaleDateString() : "—"}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `}
  `;

  el.querySelectorAll("[data-sort-col]").forEach((th) => {
    th.onclick = () => {
      const col = th.dataset.sortCol;
      const s = state.crate.sort[section];
      if (s.col === col) s.dir = s.dir === "asc" ? "desc" : "asc";
      else { s.col = col; s.dir = "asc"; }
      renderCrateMain();
    };
  });

  el.querySelectorAll("[data-open-row]").forEach((row) => {
    row.onclick = () => {
      const rawId = row.dataset.openRow;
      state.crate.activeItemId = rawId;
      renderCrateMain();
      renderCrateSidebar();
    };
  });

  const curateBtn = document.getElementById("btn-curate");
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
  const editMode = state.crate.genresListEditMode;

  el.innerHTML = `
    <div class="channel-head">
      <h4 class="crate-heading">Genres</h4>
      <div style="display:flex; gap:8px; flex-wrap:wrap;">
        <button class="btn btn-sm btn-primary" id="btn-create-genre">+ Create Genre</button>
        ${genres.length > 0 ? `<button class="icon-btn" id="btn-genres-edit-mode">${editMode ? "done" : "edit"}</button>` : ""}
      </div>
    </div>
    ${editMode ? `
      <div class="seed-row" style="margin-top:10px; align-items:center;">
        <button class="btn btn-sm" id="btn-delete-selected-genres">Delete Selected</button>
        <span id="genres-selected-count" style="color:var(--muted); font-size:10.5px;"></span>
      </div>
    ` : ""}
    ${genres.length === 0 && uncatCount === 0 ? `<div class="empty-state" style="padding:40px 0;">Nothing here yet</div>` : `
      <table class="crate-list-table" style="margin-top:14px;">
        <thead>
          <tr>
            ${editMode ? `<th><input type="checkbox" id="genres-select-all" ${genres.length > 0 && genres.every((g) => state.crate.selectedGenreNames.has(g.name)) ? "checked" : ""} /></th>` : ""}
            <th>Title</th>
            <th># of Tracks</th>
          </tr>
        </thead>
        <tbody>
          ${uncatCount > 0 ? `
            <tr class="crate-list-row" data-open-genre="Uncategorized">
              ${editMode ? `<td></td>` : ""}
              <td><em>Uncategorized</em></td>
              <td>${uncatCount}</td>
            </tr>
          ` : ""}
          ${genres.map((g) => `
            <tr class="crate-list-row" data-open-genre="${escapeAttr(g.name)}">
              ${editMode ? `<td><input type="checkbox" class="genre-select-checkbox" data-genre-name="${escapeAttr(g.name)}" ${state.crate.selectedGenreNames.has(g.name) ? "checked" : ""} /></td>` : ""}
              <td>${escapeHtml(g.name)}</td>
              <td>${g.trackCount}</td>
            </tr>
          `).join("")}
        </tbody>
      </table>
    `}
  `;

  el.querySelectorAll("[data-open-genre]").forEach((row) => {
    row.onclick = (e) => {
      if (e.target.type === "checkbox") return;
      state.crate.activeItemId = row.dataset.openGenre;
      renderCrateMain();
      renderCrateSidebar();
    };
  });

  document.getElementById("btn-create-genre").onclick = crateCreateNewGenre;

  const editBtn = document.getElementById("btn-genres-edit-mode");
  if (editBtn) {
    editBtn.onclick = () => {
      state.crate.genresListEditMode = !state.crate.genresListEditMode;
      state.crate.selectedGenreNames = new Set();
      renderCrateGenresListView(el);
    };
  }

  if (editMode) {
    crateUpdateGenresSelectedCount();

    el.querySelectorAll(".genre-select-checkbox").forEach((cb) => {
      cb.onchange = () => {
        if (cb.checked) state.crate.selectedGenreNames.add(cb.dataset.genreName);
        else state.crate.selectedGenreNames.delete(cb.dataset.genreName);
        crateUpdateGenresSelectedCount();
      };
    });

    const selectAllCb = document.getElementById("genres-select-all");
    if (selectAllCb) {
      selectAllCb.onchange = () => {
        if (selectAllCb.checked) genres.forEach((g) => state.crate.selectedGenreNames.add(g.name));
        else state.crate.selectedGenreNames.clear();
        renderCrateGenresListView(el);
      };
    }

    document.getElementById("btn-delete-selected-genres").onclick = async () => {
      const names = [...state.crate.selectedGenreNames];
      if (names.length === 0) {
        toast("Select at least one genre");
        return;
      }
      if (!confirm(`Delete ${names.length} genre(s)? Tracks inside move to Uncategorized.`)) return;
      try {
        for (const name of names) {
          const detail = await api(`/genres/${encodeURIComponent(name)}`, { needsAuth: true });
          const ids = detail.tracks.map((t) => t.id);
          if (ids.length > 0) {
            await api("/genres/assign", { method: "POST", needsAuth: true, body: { uploadIds: ids, genre: "" } });
          }
        }
        state.crate.selectedGenreNames = new Set();
        toast("Deleted");
        await loadCrateGenres();
        renderCrateMain();
        renderCrateSidebar();
      } catch (err) {
        toast(err.message);
      }
    };
  }
}

function crateUpdateGenresSelectedCount() {
  const el = document.getElementById("genres-selected-count");
  if (el) el.textContent = `${state.crate.selectedGenreNames.size} selected`;
}

// "+ Create Genre" from the list-view: since Genre only exists once it has
// tracks (no empty placeholder), this stages the new name and jumps into
// Uncategorized with Edit mode on, ready to select tracks and move them in.
function crateCreateNewGenre() {
  const name = prompt("New genre name:");
  if (!name || !name.trim()) return;
  state.crate.pendingNewGenreName = name.trim();
  state.crate.activeSection = "genres";
  state.crate.activeItemId = "Uncategorized";
  state.crate.editMode = true;
  state.crate.selectedTrackIds = new Set();
  renderCrateMain();
  renderCrateSidebar();
  toast(`Select tracks below, then move them to "${name.trim()}"`);
}

// Source of Truth — Discovered Tracks (the reserved batch from Discover/
// Browse's "+") always pinned first, then every file you've run through
// Import, grouped under "Uploaded Lists" and sorted most-recent-first.
function crateBatchModeLabel(mode) {
  if (mode === "update-collection") return "Update Collection";
  if (mode === "add-to-vibe") return "Add to Vibe";
  if (mode === "create-vibe") return "Create Vibe";
  if (mode === "discover") return "Discovered";
  return mode || "—";
}

function crateBatchRowHtml(b, editMode, isDiscovered) {
  return `
    <tr class="crate-list-row" data-open-batch="${escapeAttr(b.id)}">
      ${editMode ? `<td><input type="checkbox" class="batch-select-checkbox" data-batch-id="${escapeAttr(b.id)}" ${state.crate.selectedBatchIds.has(b.id) ? "checked" : ""} /></td>` : ""}
      <td>${isDiscovered ? '<span class="star filled">★</span> ' : ""}${escapeHtml(b.filename)}</td>
      <td>${b.createdAt ? new Date(b.createdAt).toLocaleDateString() : "—"}</td>
      <td>${b.trackCount}</td>
      <td>${escapeHtml(crateBatchModeLabel(b.mode))}</td>
    </tr>
  `;
}

function renderCrateBatchesListView(el) {
  const batches = state.crate.batchesList;
  const editMode = state.crate.batchesListEditMode;
  const discovered = batches.find((b) => b.id === "discovered");
  const fileBatches = batches
    .filter((b) => b.id !== "discovered")
    .sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));

  el.innerHTML = `
    <div class="channel-head">
      <h4 class="crate-heading">Source of Truth</h4>
      ${batches.length > 0 ? `<button class="icon-btn" id="btn-batches-edit-mode">${editMode ? "done" : "edit"}</button>` : ""}
    </div>
    ${editMode ? `
      <div class="seed-row" style="margin-top:10px; align-items:center;">
        <button class="btn btn-sm" id="btn-delete-selected-batches">Delete Selected</button>
        <span id="batches-selected-count" style="color:var(--muted); font-size:10.5px;"></span>
      </div>
    ` : ""}
    ${batches.length === 0 ? `<div class="empty-state" style="padding:40px 0;">Nothing here yet</div>` : `
      <table class="crate-list-table" style="margin-top:14px;">
        <thead>
          <tr>
            ${editMode ? `<th><input type="checkbox" id="batches-select-all" /></th>` : ""}
            <th>Title</th>
            <th>Date Created</th>
            <th># of Tracks</th>
            <th>Import Mode</th>
          </tr>
        </thead>
        <tbody>
          ${discovered ? crateBatchRowHtml(discovered, editMode, true) : ""}
          ${fileBatches.length > 0 ? `<tr><td colspan="${editMode ? 5 : 4}" style="padding:14px 12px 6px; color:var(--muted); font-size:10.5px; text-transform:uppercase; letter-spacing:0.06em;">Uploaded Lists</td></tr>` : ""}
          ${fileBatches.map((b) => crateBatchRowHtml(b, editMode, false)).join("")}
        </tbody>
      </table>
    `}
  `;

  el.querySelectorAll("[data-open-batch]").forEach((row) => {
    row.onclick = (e) => {
      if (e.target.type === "checkbox") return;
      state.crate.activeItemId = row.dataset.openBatch;
      renderCrateMain();
      renderCrateSidebar();
    };
  });

  const editBtn = document.getElementById("btn-batches-edit-mode");
  if (editBtn) {
    editBtn.onclick = () => {
      state.crate.batchesListEditMode = !state.crate.batchesListEditMode;
      state.crate.selectedBatchIds = new Set();
      renderCrateBatchesListView(el);
    };
  }

  if (editMode) {
    const countEl = document.getElementById("batches-selected-count");
    if (countEl) countEl.textContent = `${state.crate.selectedBatchIds.size} selected`;

    el.querySelectorAll(".batch-select-checkbox").forEach((cb) => {
      cb.onchange = () => {
        if (cb.checked) state.crate.selectedBatchIds.add(cb.dataset.batchId);
        else state.crate.selectedBatchIds.delete(cb.dataset.batchId);
        const c = document.getElementById("batches-selected-count");
        if (c) c.textContent = `${state.crate.selectedBatchIds.size} selected`;
      };
    });

    const selectAllCb = document.getElementById("batches-select-all");
    if (selectAllCb) {
      selectAllCb.onchange = () => {
        const allIds = batches.map((b) => b.id);
        if (selectAllCb.checked) allIds.forEach((id) => state.crate.selectedBatchIds.add(id));
        else state.crate.selectedBatchIds.clear();
        renderCrateBatchesListView(el);
      };
    }

    document.getElementById("btn-delete-selected-batches").onclick = async () => {
      const ids = [...state.crate.selectedBatchIds];
      if (ids.length === 0) {
        toast("Select at least one row");
        return;
      }
      if (!confirm(`Delete ${ids.length} ${ids.length === 1 ? "entry" : "entries"}? This deletes every track inside from your database completely.`)) return;
      try {
        await api("/imports/delete", { method: "POST", needsAuth: true, body: { batchIds: ids } });
        state.crate.selectedBatchIds = new Set();
        toast("Deleted");
        await loadCrateBatches();
        renderCrateMain();
        renderCrateSidebar();
      } catch (err) {
        toast(err.message);
      }
    };
  }
}

function crateCreateNewList() {
  const name = prompt("List name:", "Untitled List");
  if (!name) return;
  const now = new Date().toISOString();
  const newList = { id: crypto.randomUUID(), name, locked: false, trackIds: [], tracks: [], createdAt: now, updatedAt: now };
  state.crate.lists.push(newList);
  state.crate.activeSection = "lists";
  state.crate.activeItemId = newList.id;
  persistCrate();
  renderCrateSidebar();
  renderCrateMain();
}

async function crateCreateNewVibe() {
  const name = prompt("Vibe name:", "Untitled Vibe");
  if (!name) return;
  try {
    const data = await api("/vibes", { method: "POST", needsAuth: true, body: { name } });
    state.crate.vibesList.push({
      id: data.vibe.id, name: data.vibe.name, trackCount: 0,
      updatedAt: data.vibe.updatedAt, isActiveInBrowse: false,
    });
    state.crate.activeSection = "vibes";
    state.crate.activeItemId = data.vibe.id;
    renderCrateSidebar();
    renderCrateMain();
  } catch (err) {
    toast(err.message);
  }
}

function renderCrateMain() {
  const el = document.getElementById("crate-main");
  const isAdmin = state.authLevel === "admin";
  const section = state.crate.activeSection;

  if (section === "jadeslist") {
    el.innerHTML = `<div class="empty-state">Jade's List — coming in a future step</div>`;
    return;
  }

  if (state.crate.activeItemId === null) {
    renderCrateListView(el, section);
    return;
  }

  if (section === "vibes") {
    loadCrateVibeDetail(el);
    return;
  }

  if (section === "genres") {
    loadCrateGenreDetail(el);
    return;
  }

  if (section === "imports") {
    loadCrateBatchDetail(el);
    return;
  }

  if (section === "lists" && crateFindList(state.crate.activeItemId)) {
    renderCrateMainList(el, isAdmin);
    return;
  }

  renderCrateListView(el, section);
}

// ---------------------------------------------------------------------------
// Shared track-view helpers (used by both List and Vibe detail views)
// ---------------------------------------------------------------------------

// Only reset per-item view state (edit mode, search, sort) when actually
// switching to a different item — not on every re-render of the same one.
function crateResetTrackViewIfNewItem(key) {
  if (state.crate._lastItemKey !== key) {
    state.crate.editMode = false;
    state.crate.trackSearchQuery = "";
    state.crate.trackViewSort = { col: null, dir: "asc" };
    state.crate.selectedTrackIds = new Set();
    state.crate._lastItemKey = key;
  }
}

function crateTrackSortIndicator(col) {
  const s = state.crate.trackViewSort;
  if (s.col !== col) return "";
  return s.dir === "asc" ? " ▲" : " ▼";
}

// Filters by the search box and sorts by the active column, while carrying
// each track's original array index (__i) through — needed so remove/reorder
// operate on the real underlying array even when the display is filtered or
// sorted differently from storage order.
function crateFilterAndSortTracks(tracks) {
  const withIndex = tracks.map((t, i) => ({ ...t, __i: i }));
  const q = state.crate.trackSearchQuery.trim().toLowerCase();
  let result = q
    ? withIndex.filter((t) => `${t.artist || ""} ${t.track || ""}`.toLowerCase().includes(q))
    : withIndex;
  const sort = state.crate.trackViewSort;
  if (sort.col) {
    result = [...result].sort((a, b) => {
      let av = a[sort.col], bv = b[sort.col];
      if (sort.col === "bpm") { av = parseFloat(av) || 0; bv = parseFloat(bv) || 0; }
      else { av = (av || "").toString().toLowerCase(); bv = (bv || "").toString().toLowerCase(); }
      if (av < bv) return sort.dir === "asc" ? -1 : 1;
      if (av > bv) return sort.dir === "asc" ? 1 : -1;
      return 0;
    });
  }
  return result;
}

// Reorder only makes sense against the natural (unfiltered, unsorted) order —
// dragging rows around a filtered/sorted view wouldn't map cleanly back to
// storage order, so Edit mode's drag-to-reorder is disabled while either is active.
function crateCanReorder() {
  return state.crate.editMode && !state.crate.trackSearchQuery.trim() && !state.crate.trackViewSort.col;
}

// Builds the Rekordbox-style sortable table. `showRemove` controls the trailing
// delete column (Edit mode only); `dragEnabled` controls the drag handle column.
function crateTrackTableHtml(rows, { dragEnabled, showRemove, checkboxEnabled, selectedIds }) {
  if (rows.length === 0) {
    return `<div class="empty-state">${state.crate.trackSearchQuery ? "No matches" : "No tracks yet"}</div>`;
  }
  const allSelected = checkboxEnabled && rows.length > 0 && rows.every((t) => selectedIds.has(t.id));
  return `
    <table class="crate-track-table">
      <thead>
        <tr>
          ${dragEnabled ? `<th></th>` : ""}
          ${checkboxEnabled ? `<th><input type="checkbox" id="track-select-all" ${allSelected ? "checked" : ""} /></th><th></th>` : ""}
          <th data-track-sort-col="track">Track Title${crateTrackSortIndicator("track")}</th>
          <th data-track-sort-col="artist">Artist${crateTrackSortIndicator("artist")}</th>
          <th data-track-sort-col="bpm">BPM${crateTrackSortIndicator("bpm")}</th>
          <th data-track-sort-col="key">Key${crateTrackSortIndicator("key")}</th>
          <th data-track-sort-col="time">Time${crateTrackSortIndicator("time")}</th>
          <th data-track-sort-col="genre">Genre${crateTrackSortIndicator("genre")}</th>
          <th data-track-sort-col="addedAt">Date Added${crateTrackSortIndicator("addedAt")}</th>
          ${showRemove ? `<th></th>` : ""}
        </tr>
      </thead>
      <tbody>
        ${rows.map((t) => `
          <tr draggable="${dragEnabled}" data-track-orig-i="${t.__i}">
            ${dragEnabled ? `<td class="drag-handle-cell">⠿</td>` : ""}
            ${checkboxEnabled ? `<td><input type="checkbox" class="track-select-checkbox" data-track-id="${escapeAttr(t.id)}" ${selectedIds.has(t.id) ? "checked" : ""} /></td><td><button class="icon-btn track-edit-pencil" data-track-edit-id="${escapeAttr(t.id)}" title="Edit track">✎</button></td>` : ""}
            <td class="track-cell-title">${escapeHtml(t.track || "—")}</td>
            <td class="track-cell-artist">${escapeHtml(t.artist || "—")}</td>
            <td>${escapeHtml(t.bpm ? String(t.bpm) : "—")}</td>
            <td>${escapeHtml(t.key || "—")}</td>
            <td>${escapeHtml(t.time || "—")}</td>
            <td>${escapeHtml(t.genre || "—")}</td>
            <td>${t.addedAt ? new Date(t.addedAt).toLocaleDateString() : "—"}</td>
            ${showRemove ? `<td><button class="icon-btn" data-track-remove-i="${t.__i}">✕</button></td>` : ""}
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function crateWireTrackSortHeaders(containerEl, onResort) {
  containerEl.querySelectorAll("[data-track-sort-col]").forEach((th) => {
    th.onclick = () => {
      const col = th.dataset.trackSortCol;
      const s = state.crate.trackViewSort;
      if (s.col === col) s.dir = s.dir === "asc" ? "desc" : "asc";
      else { s.col = col; s.dir = "asc"; }
      onResort();
    };
  });
}

// Wires the pencil-edit buttons rendered alongside checkboxes in Edit mode.
// Shared across every track-view (Lists, Vibes, Genres, Source of Truth) —
// they're all just different lenses onto the same Upload records, so
// editing works identically no matter where you open it from.
function crateWireTrackEditPencils(containerEl, rows, onSaved) {
  containerEl.querySelectorAll(".track-edit-pencil").forEach((btn) => {
    btn.onclick = (e) => {
      e.stopPropagation();
      const track = rows.find((t) => t.id === btn.dataset.trackEditId);
      if (track) crateOpenTrackEditPopup(track, onSaved);
    };
  });
}

function crateCloseTrackEditPopup() {
  const overlay = document.getElementById("track-edit-overlay");
  if (overlay) overlay.remove();
}

// The pencil-edit popup: editable fields for one track's own data, plus an
// "Appears on" section (Lists + Vibes referencing it). Saving edits the
// Upload directly, so the change is visible everywhere that track is
// referenced the moment you close this. onSaved is called after a
// successful save so the calling track-view can refresh itself.
function crateOpenTrackEditPopup(track, onSaved) {
  crateCloseTrackEditPopup();

  const overlay = document.createElement("div");
  overlay.className = "track-edit-overlay";
  overlay.id = "track-edit-overlay";
  overlay.onclick = (e) => {
    if (e.target === overlay) crateCloseTrackEditPopup();
  };
  document.body.appendChild(overlay);

  overlay.innerHTML = `
    <div class="track-edit-modal">
      <div class="channel-head">
        <h4 class="crate-heading" style="font-size:20px;">Edit Track</h4>
        <button class="icon-btn" id="btn-close-track-edit">✕</button>
      </div>
      <div class="track-edit-fields">
        <label>Title<input class="input" id="edit-track-title" value="${escapeAttr(track.track || "")}" /></label>
        <label>Artist<input class="input" id="edit-track-artist" value="${escapeAttr(track.artist || "")}" /></label>
        <label>Album<input class="input" id="edit-track-album" value="${escapeAttr(track.album || "")}" /></label>
        <label>BPM<input class="input" id="edit-track-bpm" value="${escapeAttr(track.bpm || "")}" /></label>
        <label>Key<input class="input" id="edit-track-key" value="${escapeAttr(track.key || "")}" /></label>
        <label>Time<input class="input" id="edit-track-time" value="${escapeAttr(track.time || "")}" /></label>
        <label>Genre<input class="input" id="edit-track-genre" value="${escapeAttr(track.genre || "")}" /></label>
        <label>Notes<textarea class="input" id="edit-track-notes" rows="2">${escapeHtml(track.notes || "")}</textarea></label>
      </div>
      <button class="btn btn-sm btn-primary" id="btn-save-track-edit" style="margin-top:14px;">Save</button>
      <div class="track-edit-appears-on" id="track-appears-on"><span class="spinner"></span> Loading Appears On...</div>
    </div>
  `;

  document.getElementById("btn-close-track-edit").onclick = crateCloseTrackEditPopup;

  document.getElementById("btn-save-track-edit").onclick = async () => {
    const fields = {
      track: document.getElementById("edit-track-title").value.trim(),
      artist: document.getElementById("edit-track-artist").value.trim(),
      album: document.getElementById("edit-track-album").value.trim(),
      bpm: document.getElementById("edit-track-bpm").value.trim(),
      key: document.getElementById("edit-track-key").value.trim(),
      time: document.getElementById("edit-track-time").value.trim(),
      genre: document.getElementById("edit-track-genre").value.trim(),
      notes: document.getElementById("edit-track-notes").value.trim(),
    };
    try {
      await api("/imports/edit-track", { method: "POST", needsAuth: true, body: { uploadId: track.id, ...fields } });
      toast("Saved");
      crateCloseTrackEditPopup();
      if (onSaved) onSaved();
    } catch (err) {
      toast(err.message);
    }
  };

  api(`/imports/appears-on/${encodeURIComponent(track.id)}`, { needsAuth: true })
    .then((ao) => {
      const aoEl = document.getElementById("track-appears-on");
      if (!aoEl) return;
      const listsHtml = ao.lists.length > 0
        ? ao.lists.map((l) => escapeHtml(l.name)).join("<br>")
        : "<em>none</em>";
      const vibesHtml = ao.vibes.length > 0
        ? ao.vibes.map((v) => escapeHtml(v.name)).join("<br>")
        : "<em>none</em>";
      aoEl.innerHTML = `
        <div class="track-meta-row" style="line-height:1.8; font-size:11px;">
          <strong>My Lists (${ao.lists.length})</strong><br>${listsHtml}
          <br><br>
          <strong>Vibe Curation (${ao.vibes.length})</strong><br>${vibesHtml}
        </div>
      `;
    })
    .catch(() => {
      const aoEl = document.getElementById("track-appears-on");
      if (aoEl) aoEl.textContent = "Couldn't load Appears On.";
    });
}

function crateTrackMetaRowHtml(item) {
  const parts = [];
  if (item.createdAt) parts.push(`Created ${new Date(item.createdAt).toLocaleDateString()}`);
  if (item.updatedAt) parts.push(`Updated ${new Date(item.updatedAt).toLocaleDateString()}`);
  parts.push(`${item.trackCount} track${item.trackCount === 1 ? "" : "s"}`);
  return parts.join(" · ");
}

// ---------------------------------------------------------------------------
// Vibe track-view
// ---------------------------------------------------------------------------

async function loadCrateVibeDetail(el) {
  el.innerHTML = `<div class="empty-state"><span class="spinner"></span> Loading...</div>`;
  try {
    const detail = await api(`/vibes/${state.crate.activeItemId}`, { needsAuth: true });
    renderCrateVibeDetail(el, detail);
  } catch (err) {
    el.innerHTML = errorCardHtml(err.message);
  }
}

function renderCrateVibeDetail(el, vibe) {
  crateResetTrackViewIfNewItem(`vibes:${vibe.id}`);

  const dragEnabled = crateCanReorder();
  const checkboxEnabled = state.crate.editMode;
  const rows = crateFilterAndSortTracks(vibe.tracks);

  el.innerHTML = `
    <div class="channel-head">
      <div style="display:flex; align-items:center; gap:10px;">
        <span class="star ${vibe.isActiveInBrowse ? "filled" : "outline"}">★</span>
        <h4 class="crate-heading">${escapeHtml(vibe.name)}</h4>
      </div>
      <div style="display:flex; gap:8px; flex-wrap:wrap;">
        <button class="icon-btn" id="btn-back-to-vibes">← all vibes</button>
        <button class="icon-btn" id="btn-rename-vibe">rename</button>
        <button class="icon-btn" id="btn-delete-vibe">delete</button>
        <button class="icon-btn" id="btn-edit-mode">${state.crate.editMode ? "done" : "edit"}</button>
      </div>
    </div>

    <textarea class="input" id="track-description" rows="2" placeholder="Description — optional, what does this sound like?" style="margin-top:12px;">${escapeHtml(vibe.description || "")}</textarea>

    <div class="track-meta-row">${crateTrackMetaRowHtml({ createdAt: vibe.createdAt, updatedAt: vibe.updatedAt, trackCount: vibe.tracks.length })}</div>

    <div class="seed-row" style="margin-top:14px;">
      <input class="input" id="track-search" placeholder="Search tracks..." value="${escapeAttr(state.crate.trackSearchQuery)}" style="flex:1;" />
    </div>

    ${checkboxEnabled ? `
      <div class="seed-row" style="margin-top:10px; align-items:center; flex-wrap:wrap;">
        <button class="btn btn-sm" id="btn-delete-selected-tracks">Delete Selected</button>
        ${crateBulkAddSelectHtml(null, vibe.id)}
      </div>
      <div style="margin-top:6px; color:var(--muted); font-size:10.5px;" id="tracks-selected-count"></div>
    ` : ""}

    <div id="vibe-tracks" style="margin-top:12px;"></div>
  `;

  document.getElementById("vibe-tracks").innerHTML = crateTrackTableHtml(rows, { dragEnabled, showRemove: false, checkboxEnabled, selectedIds: state.crate.selectedTrackIds });
  crateWireTrackSortHeaders(el, () => renderCrateVibeDetail(el, vibe));
  crateWireTrackEditPencils(document.getElementById("vibe-tracks"), rows, () => loadCrateVibeDetail(el));

  document.getElementById("track-search").oninput = (e) => {
    state.crate.trackSearchQuery = e.target.value;
    renderCrateVibeDetail(el, vibe);
  };

  document.getElementById("track-description").onchange = async (e) => {
    try {
      await api("/vibes/description", { method: "POST", needsAuth: true, body: { vibeId: vibe.id, description: e.target.value } });
      vibe.description = e.target.value;
      const idx = state.crate.vibesList.findIndex((v) => v.id === vibe.id);
      if (idx !== -1) state.crate.vibesList[idx].description = e.target.value;
    } catch (err) {
      toast(err.message);
    }
  };

  document.getElementById("btn-back-to-vibes").onclick = () => {
    state.crate.activeItemId = null;
    renderCrateMain();
    renderCrateSidebar();
  };

  document.getElementById("btn-rename-vibe").onclick = async () => {
    const name = prompt("Rename vibe:", vibe.name);
    if (!name) return;
    try {
      await api("/vibes/rename", { method: "POST", needsAuth: true, body: { vibeId: vibe.id, name } });
      const idx = state.crate.vibesList.findIndex((v) => v.id === vibe.id);
      if (idx !== -1) state.crate.vibesList[idx].name = name;
      loadCrateVibeDetail(el);
      renderCrateSidebar();
    } catch (err) {
      toast(err.message);
    }
  };

  document.getElementById("btn-delete-vibe").onclick = async () => {
    if (!confirm(`Delete "${vibe.name}"? This removes the Vibe (tracks stay in Imported).`)) return;
    try {
      await api("/vibes/delete", { method: "POST", needsAuth: true, body: { vibeId: vibe.id } });
      state.crate.vibesList = state.crate.vibesList.filter((v) => v.id !== vibe.id);
      state.crate.activeItemId = null;
      renderCrateMain();
      renderCrateSidebar();
      toast("Deleted");
    } catch (err) {
      toast(err.message);
    }
  };

  document.getElementById("btn-edit-mode").onclick = () => {
    state.crate.editMode = !state.crate.editMode;
    state.crate.selectedTrackIds = new Set();
    renderCrateVibeDetail(el, vibe);
  };

  const tracksContainer = document.getElementById("vibe-tracks");

  if (checkboxEnabled) {
    crateUpdateTracksSelectedCount();

    tracksContainer.querySelectorAll(".track-select-checkbox").forEach((cb) => {
      cb.onchange = () => {
        if (cb.checked) state.crate.selectedTrackIds.add(cb.dataset.trackId);
        else state.crate.selectedTrackIds.delete(cb.dataset.trackId);
        crateUpdateTracksSelectedCount();
      };
    });

    const selectAllCb = document.getElementById("track-select-all");
    if (selectAllCb) {
      selectAllCb.onchange = () => {
        if (selectAllCb.checked) rows.forEach((t) => state.crate.selectedTrackIds.add(t.id));
        else rows.forEach((t) => state.crate.selectedTrackIds.delete(t.id));
        renderCrateVibeDetail(el, vibe);
      };
    }

    document.getElementById("btn-delete-selected-tracks").onclick = async () => {
      const ids = [...state.crate.selectedTrackIds];
      if (ids.length === 0) {
        toast("Select at least one track");
        return;
      }
      try {
        for (const uploadId of ids) {
          await api("/vibes/remove-track", { method: "POST", needsAuth: true, body: { vibeId: vibe.id, uploadId } });
        }
        const idx = state.crate.vibesList.findIndex((v) => v.id === vibe.id);
        if (idx !== -1) state.crate.vibesList[idx].trackCount -= ids.length;
        state.crate.selectedTrackIds = new Set();
        loadCrateVibeDetail(el);
      } catch (err) {
        toast(err.message);
      }
    };

    document.getElementById("btn-bulk-add").onclick = () => {
      crateHandleBulkAdd(state.crate.selectedTrackIds, () => {
        state.crate.selectedTrackIds = new Set();
        loadCrate();
      });
    };
  }

  if (dragEnabled) {
    setupVibeDragReorder(tracksContainer, vibe, el);
  }
}

function setupVibeDragReorder(container, vibe, el) {
  let dragIndex = null;
  container.querySelectorAll("[data-track-orig-i]").forEach((row) => {
    row.addEventListener("dragstart", () => {
      dragIndex = +row.dataset.trackOrigI;
      row.classList.add("dragging");
    });
    row.addEventListener("dragend", () => row.classList.remove("dragging"));
    row.addEventListener("dragover", (e) => e.preventDefault());
    row.addEventListener("drop", async () => {
      const dropIndex = +row.dataset.trackOrigI;
      if (dragIndex === null || dragIndex === dropIndex) return;
      const newTracks = [...vibe.tracks];
      const [moved] = newTracks.splice(dragIndex, 1);
      newTracks.splice(dropIndex, 0, moved);
      const newOrder = newTracks.map((t) => t.id);
      try {
        await api("/vibes/reorder", { method: "POST", needsAuth: true, body: { vibeId: vibe.id, trackIds: newOrder } });
        vibe.tracks = newTracks;
        renderCrateVibeDetail(el, vibe);
      } catch (err) {
        toast(err.message);
      }
    });
  });
}

// ---------------------------------------------------------------------------
// List track-view
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
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

  const editMode = state.crate.editMode;
  const rows = crateFilterAndSortTracks(genre.tracks);

  el.innerHTML = `
    <div class="channel-head">
      <h4 class="crate-heading">${escapeHtml(genre.name)}</h4>
      <div style="display:flex; gap:8px; flex-wrap:wrap;">
        <button class="icon-btn" id="btn-back-to-genres">← all genres</button>
        <button class="icon-btn" id="btn-edit-mode">${editMode ? "done" : "edit"}</button>
      </div>
    </div>

    <div class="track-meta-row">${genre.tracks.length} track${genre.tracks.length === 1 ? "" : "s"}</div>

    <div class="seed-row" style="margin-top:14px;">
      <input class="input" id="track-search" placeholder="Search tracks..." value="${escapeAttr(state.crate.trackSearchQuery)}" style="flex:1;" />
    </div>

    ${editMode ? `
      <div class="seed-row" style="margin-top:10px; align-items:center;">
        <select class="input" id="genre-move-target" style="flex:1;">
          <option value="">Move selected to...</option>
          ${state.crate.pendingNewGenreName ? `<option value="${escapeAttr(state.crate.pendingNewGenreName)}" selected>+ ${escapeHtml(state.crate.pendingNewGenreName)} (new)</option>` : ""}
          <option value="__new__">+ Create new genre...</option>
          <option value="Uncategorized">Uncategorized</option>
          ${state.crate.genresList.filter((g) => g.name !== genre.name).map((g) => `<option value="${escapeAttr(g.name)}">${escapeHtml(g.name)}</option>`).join("")}
        </select>
        <button class="btn btn-sm" id="btn-apply-genre-move">Apply</button>
      </div>
      <div style="margin-top:6px; color:var(--muted); font-size:10.5px;" id="genre-selected-count"></div>
    ` : ""}

    <div id="genre-tracks" style="margin-top:12px;"></div>
  `;

  document.getElementById("genre-tracks").innerHTML = crateTrackTableHtml(rows, {
    dragEnabled: false, showRemove: false,
    checkboxEnabled: editMode, selectedIds: state.crate.selectedTrackIds,
  });
  crateWireTrackSortHeaders(el, () => renderCrateGenreDetail(el, genre));
  crateWireTrackEditPencils(document.getElementById("genre-tracks"), rows, () => loadCrateGenreDetail(el));

  document.getElementById("track-search").oninput = (e) => {
    state.crate.trackSearchQuery = e.target.value;
    renderCrateGenreDetail(el, genre);
  };

  document.getElementById("btn-back-to-genres").onclick = () => {
    state.crate.activeItemId = null;
    state.crate.pendingNewGenreName = null;
    renderCrateMain();
    renderCrateSidebar();
  };

  document.getElementById("btn-edit-mode").onclick = () => {
    state.crate.editMode = !state.crate.editMode;
    state.crate.selectedTrackIds = new Set();
    renderCrateGenreDetail(el, genre);
  };

  if (editMode) {
    crateUpdateGenreSelectedCount();

    document.querySelectorAll(".track-select-checkbox").forEach((cb) => {
      cb.onchange = () => {
        if (cb.checked) state.crate.selectedTrackIds.add(cb.dataset.trackId);
        else state.crate.selectedTrackIds.delete(cb.dataset.trackId);
        crateUpdateGenreSelectedCount();
      };
    });

    const selectAllCb = document.getElementById("track-select-all");
    if (selectAllCb) {
      selectAllCb.onchange = () => {
        if (selectAllCb.checked) rows.forEach((t) => state.crate.selectedTrackIds.add(t.id));
        else rows.forEach((t) => state.crate.selectedTrackIds.delete(t.id));
        renderCrateGenreDetail(el, genre);
      };
    }

    document.getElementById("btn-apply-genre-move").onclick = async () => {
      const target = document.getElementById("genre-move-target").value;
      if (!target) {
        toast("Pick a target first");
        return;
      }
      if (state.crate.selectedTrackIds.size === 0) {
        toast("Select at least one track");
        return;
      }
      let newGenre = target;
      if (target === "__new__") {
        const name = prompt("New genre name:");
        if (!name || !name.trim()) return;
        newGenre = name.trim();
      } else if (target === "Uncategorized") {
        newGenre = "";
      }
      try {
        await api("/genres/assign", {
          method: "POST", needsAuth: true,
          body: { uploadIds: [...state.crate.selectedTrackIds], genre: newGenre },
        });
        toast(`Moved ${state.crate.selectedTrackIds.size} track(s)`);
        state.crate.selectedTrackIds = new Set();
        state.crate.pendingNewGenreName = null;
        await loadCrateGenres();
        loadCrateGenreDetail(el);
      } catch (err) {
        toast(err.message);
      }
    };
  }
}

function crateUpdateGenreSelectedCount() {
  const el = document.getElementById("genre-selected-count");
  if (el) el.textContent = `${state.crate.selectedTrackIds.size} selected`;
}

// ---------------------------------------------------------------------------
// Source of Truth track-view — the tracks inside one batch (Discovered
// Tracks or a file import). Edit mode: checkbox multi-select, Delete
// Selected (deletes the track from your database completely — same cascade
// as any other delete-track-from-Imports action), and the shared
// Add-to-List/Vibe control.
// ---------------------------------------------------------------------------

async function loadCrateBatchDetail(el) {
  el.innerHTML = `<div class="empty-state"><span class="spinner"></span> Loading...</div>`;
  try {
    const detail = await api(`/imports/${encodeURIComponent(state.crate.activeItemId)}`, { needsAuth: true });
    renderCrateBatchDetail(el, detail);
  } catch (err) {
    el.innerHTML = errorCardHtml(err.message);
  }
}

function renderCrateBatchDetail(el, batch) {
  crateResetTrackViewIfNewItem(`imports:${batch.id}`);

  const editMode = state.crate.editMode;
  const rows = crateFilterAndSortTracks(batch.tracks);

  el.innerHTML = `
    <div class="channel-head">
      <h4 class="crate-heading">${escapeHtml(batch.filename)}</h4>
      <div style="display:flex; gap:8px; flex-wrap:wrap;">
        <button class="icon-btn" id="btn-back-to-batches">← source of truth</button>
        <button class="icon-btn" id="btn-edit-mode">${editMode ? "done" : "edit"}</button>
      </div>
    </div>

    <div class="track-meta-row">${batch.createdAt ? `Created ${new Date(batch.createdAt).toLocaleDateString()} · ` : ""}${crateBatchModeLabel(batch.mode)} · ${batch.tracks.length} track${batch.tracks.length === 1 ? "" : "s"}</div>

    <div class="seed-row" style="margin-top:14px;">
      <input class="input" id="track-search" placeholder="Search tracks..." value="${escapeAttr(state.crate.trackSearchQuery)}" style="flex:1;" />
    </div>

    ${editMode ? `
      <div class="seed-row" style="margin-top:10px; align-items:center; flex-wrap:wrap;">
        <button class="btn btn-sm" id="btn-delete-selected-tracks">Delete Selected</button>
        ${crateBulkAddSelectHtml(null, null)}
      </div>
      <div style="margin-top:6px; color:var(--muted); font-size:10.5px;" id="tracks-selected-count"></div>
    ` : ""}

    <div id="batch-tracks" style="margin-top:12px;"></div>
  `;

  document.getElementById("batch-tracks").innerHTML = crateTrackTableHtml(rows, { dragEnabled: false, showRemove: false, checkboxEnabled: editMode, selectedIds: state.crate.selectedTrackIds });
  crateWireTrackSortHeaders(el, () => renderCrateBatchDetail(el, batch));
  crateWireTrackEditPencils(document.getElementById("batch-tracks"), rows, () => loadCrateBatchDetail(el));

  document.getElementById("track-search").oninput = (e) => {
    state.crate.trackSearchQuery = e.target.value;
    renderCrateBatchDetail(el, batch);
  };

  document.getElementById("btn-back-to-batches").onclick = () => {
    state.crate.activeItemId = null;
    renderCrateMain();
    renderCrateSidebar();
  };

  document.getElementById("btn-edit-mode").onclick = () => {
    state.crate.editMode = !state.crate.editMode;
    state.crate.selectedTrackIds = new Set();
    renderCrateBatchDetail(el, batch);
  };

  if (editMode) {
    crateUpdateTracksSelectedCount();

    document.querySelectorAll(".track-select-checkbox").forEach((cb) => {
      cb.onchange = () => {
        if (cb.checked) state.crate.selectedTrackIds.add(cb.dataset.trackId);
        else state.crate.selectedTrackIds.delete(cb.dataset.trackId);
        crateUpdateTracksSelectedCount();
      };
    });

    const selectAllCb = document.getElementById("track-select-all");
    if (selectAllCb) {
      selectAllCb.onchange = () => {
        if (selectAllCb.checked) rows.forEach((t) => state.crate.selectedTrackIds.add(t.id));
        else rows.forEach((t) => state.crate.selectedTrackIds.delete(t.id));
        renderCrateBatchDetail(el, batch);
      };
    }

    document.getElementById("btn-delete-selected-tracks").onclick = async () => {
      const ids = [...state.crate.selectedTrackIds];
      if (ids.length === 0) {
        toast("Select at least one track");
        return;
      }
      if (!confirm(`Delete ${ids.length} track${ids.length === 1 ? "" : "s"}? This removes them from your database completely.`)) return;
      try {
        await api("/imports/delete-tracks", { method: "POST", needsAuth: true, body: { batchId: batch.id, uploadIds: ids } });
        state.crate.selectedTrackIds = new Set();
        toast("Deleted");
        await loadCrateBatches();
        loadCrateBatchDetail(el);
      } catch (err) {
        toast(err.message);
      }
    };

    document.getElementById("btn-bulk-add").onclick = () => {
      crateHandleBulkAdd(state.crate.selectedTrackIds, () => {
        state.crate.selectedTrackIds = new Set();
        loadCrate();
      });
    };
  }
}

// Shared "Add selected to..." control — one dropdown grouping Lists and
// Vibes together (with create-new options in each group), used from every
// Edit-mode action bar (Lists, Vibes, Genres, Imported).
function crateBulkAddSelectHtml(excludeListId, excludeVibeId) {
  return `
    <select class="input" id="bulk-add-target" style="flex:1; min-width:160px;">
      <option value="">Add selected to...</option>
      <optgroup label="Lists">
        <option value="list:__new__">+ Create new list...</option>
        ${state.crate.lists.filter((l) => l.id !== excludeListId).map((l) => `<option value="list:${escapeAttr(l.id)}">${escapeHtml(l.name)}</option>`).join("")}
      </optgroup>
      <optgroup label="Vibes">
        <option value="vibe:__new__">+ Create new vibe...</option>
        ${state.crate.vibesList.filter((v) => v.id !== excludeVibeId).map((v) => `<option value="vibe:${escapeAttr(v.id)}">${escapeHtml(v.name)}</option>`).join("")}
      </optgroup>
    </select>
    <button class="btn btn-sm" id="btn-bulk-add">Add</button>
  `;
}

async function crateHandleBulkAdd(selectedIds, onDone) {
  const select = document.getElementById("bulk-add-target");
  if (!select) return;
  const value = select.value;
  if (!value) {
    toast("Pick a destination first");
    return;
  }
  if (selectedIds.size === 0) {
    toast("Select at least one track");
    return;
  }
  const [kind, target] = value.split(":");
  try {
    if (kind === "list") {
      const body = { uploadIds: [...selectedIds] };
      if (target === "__new__") {
        const name = prompt("New list name:");
        if (!name || !name.trim()) return;
        body.newListName = name.trim();
      } else {
        body.listId = target;
      }
      await api("/crate/add-tracks", { method: "POST", needsAuth: true, body });
      toast("Added to list");
    } else {
      const body = { uploadIds: [...selectedIds] };
      if (target === "__new__") {
        const name = prompt("New vibe name:");
        if (!name || !name.trim()) return;
        body.newVibeName = name.trim();
      } else {
        body.vibeId = target;
      }
      await api("/vibes/add-existing-tracks", { method: "POST", needsAuth: true, body });
      toast("Added to vibe");
    }
    onDone();
  } catch (err) {
    toast(err.message);
  }
}

function crateUpdateTracksSelectedCount() {
  const el = document.getElementById("tracks-selected-count");
  if (el) el.textContent = `${state.crate.selectedTrackIds.size} selected`;
}

function renderCrateMainList(el, isAdmin) {
  const list = crateFindList(state.crate.activeItemId);

  if (!list) {
    el.innerHTML = `<div class="empty-state">Select or create a list</div>`;
    return;
  }

  crateResetTrackViewIfNewItem(`lists:${list.id}`);

  const dragEnabled = isAdmin && crateCanReorder();
  const checkboxEnabled = isAdmin && state.crate.editMode;
  const rows = crateFilterAndSortTracks(list.tracks);

  el.innerHTML = `
    <div class="channel-head">
      <h4 class="crate-heading">${escapeHtml(list.name)}</h4>
      <div style="display:flex; gap:8px; flex-wrap:wrap;">
        ${isAdmin ? `<button class="icon-btn" id="btn-toggle-lock">${list.locked ? "🔒 locked" : "🔓 unlocked"}</button>` : ""}
        ${isAdmin ? `<button class="icon-btn" id="btn-rename-list">rename</button>` : ""}
        ${isAdmin ? `<button class="icon-btn" id="btn-delete-list">delete</button>` : ""}
        ${isAdmin ? `<button class="icon-btn" id="btn-edit-mode">${state.crate.editMode ? "done" : "edit"}</button>` : ""}
        <button class="icon-btn" id="btn-export-list">export .txt</button>
      </div>
    </div>

    <textarea class="input" id="track-description" rows="2" placeholder="Description — optional, what does this sound like?" style="margin-top:12px;" ${isAdmin ? "" : "disabled"}>${escapeHtml(list.description || "")}</textarea>

    <div class="track-meta-row">${crateTrackMetaRowHtml({ createdAt: list.createdAt, updatedAt: list.updatedAt, trackCount: list.tracks.length })}</div>

    <div class="seed-row" style="margin-top:14px;">
      <input class="input" id="track-search" placeholder="Search tracks..." value="${escapeAttr(state.crate.trackSearchQuery)}" style="flex:1;" />
    </div>

    ${checkboxEnabled ? `
      <div class="seed-row" style="margin-top:10px; align-items:center; flex-wrap:wrap;">
        <button class="btn btn-sm" id="btn-delete-selected-tracks">Delete Selected</button>
        ${crateBulkAddSelectHtml(list.id, null)}
      </div>
      <div style="margin-top:6px; color:var(--muted); font-size:10.5px;" id="tracks-selected-count"></div>
    ` : ""}

    <div id="crate-tracks" style="margin-top:12px;"></div>
  `;

  document.getElementById("crate-tracks").innerHTML = crateTrackTableHtml(rows, { dragEnabled, showRemove: false, checkboxEnabled, selectedIds: state.crate.selectedTrackIds });
  crateWireTrackSortHeaders(el, () => renderCrateMainList(el, isAdmin));
  crateWireTrackEditPencils(document.getElementById("crate-tracks"), rows, async () => {
    await loadCrate();
    renderCrateMainList(el, isAdmin);
  });

  document.getElementById("track-search").oninput = (e) => {
    state.crate.trackSearchQuery = e.target.value;
    renderCrateMainList(el, isAdmin);
  };

  document.getElementById("track-description").onchange = (e) => {
    if (!isAdmin) return;
    list.description = e.target.value;
    list.updatedAt = new Date().toISOString();
    persistCrate();
  };

  if (isAdmin) {
    document.getElementById("btn-toggle-lock").onclick = () => {
      list.locked = !list.locked;
      list.updatedAt = new Date().toISOString();
      persistCrate();
      renderCrate();
    };
    document.getElementById("btn-rename-list").onclick = () => {
      const name = prompt("Rename list:", list.name);
      if (!name) return;
      list.name = name;
      list.updatedAt = new Date().toISOString();
      persistCrate();
      renderCrate();
    };
    document.getElementById("btn-delete-list").onclick = () => {
      if (!confirm(`Delete "${list.name}"?`)) return;
      state.crate.lists = state.crate.lists.filter((l) => l.id !== list.id);
      state.crate.activeItemId = null;
      persistCrate();
      renderCrate();
    };
    document.getElementById("btn-edit-mode").onclick = () => {
      state.crate.editMode = !state.crate.editMode;
      state.crate.selectedTrackIds = new Set();
      renderCrateMainList(el, isAdmin);
    };
  }

  document.getElementById("btn-export-list").onclick = () => exportListAsTxt(list);

  const tracksContainer = document.getElementById("crate-tracks");

  if (checkboxEnabled) {
    crateUpdateTracksSelectedCount();

    tracksContainer.querySelectorAll(".track-select-checkbox").forEach((cb) => {
      cb.onchange = () => {
        if (cb.checked) state.crate.selectedTrackIds.add(cb.dataset.trackId);
        else state.crate.selectedTrackIds.delete(cb.dataset.trackId);
        crateUpdateTracksSelectedCount();
      };
    });

    const selectAllCb = document.getElementById("track-select-all");
    if (selectAllCb) {
      selectAllCb.onchange = () => {
        if (selectAllCb.checked) rows.forEach((t) => state.crate.selectedTrackIds.add(t.id));
        else rows.forEach((t) => state.crate.selectedTrackIds.delete(t.id));
        renderCrateMainList(el, isAdmin);
      };
    }

    document.getElementById("btn-delete-selected-tracks").onclick = () => {
      if (state.crate.selectedTrackIds.size === 0) {
        toast("Select at least one track");
        return;
      }
      const removing = state.crate.selectedTrackIds;
      list.trackIds = (list.trackIds || []).filter((id) => !removing.has(id));
      list.tracks = list.tracks.filter((t) => !removing.has(t.id));
      list.updatedAt = new Date().toISOString();
      state.crate.selectedTrackIds = new Set();
      persistCrate();
      renderCrateMainList(el, isAdmin);
    };

    document.getElementById("btn-bulk-add").onclick = () => {
      crateHandleBulkAdd(state.crate.selectedTrackIds, () => {
        state.crate.selectedTrackIds = new Set();
        loadCrate();
      });
    };
  }

  if (dragEnabled) {
    setupListDragReorder(tracksContainer, list, el, isAdmin);
  }
}

function setupListDragReorder(container, list, el, isAdmin) {
  let dragIndex = null;
  container.querySelectorAll("[data-track-orig-i]").forEach((row) => {
    row.addEventListener("dragstart", () => {
      dragIndex = +row.dataset.trackOrigI;
      row.classList.add("dragging");
    });
    row.addEventListener("dragend", () => row.classList.remove("dragging"));
    row.addEventListener("dragover", (e) => e.preventDefault());
    row.addEventListener("drop", () => {
      const dropIndex = +row.dataset.trackOrigI;
      if (dragIndex === null || dragIndex === dropIndex) return;
      const [moved] = list.tracks.splice(dragIndex, 1);
      list.tracks.splice(dropIndex, 0, moved);
      list.trackIds = list.tracks.map((t) => t.id);
      list.updatedAt = new Date().toISOString();
      persistCrate();
      renderCrateMainList(el, isAdmin);
    });
  });
}

function exportListAsTxt(list) {
  const lines = list.tracks.map(
    (t) => `${t.artist}${t.track ? " - " + t.track : ""}${t.label ? " [" + t.label + "]" : ""}${t.bpm ? " " + t.bpm + "bpm" : ""}${t.key ? " " + t.key : ""}`
  );
  const blob = new Blob([lines.join("\n")], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${slug(list.name)}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}

// ============================================================================
// MIXES TAB (public)
// ============================================================================
const panelMixes = document.getElementById("panel-mixes");

async function loadMixes() {
  state.mixes.loading = true;
  try {
    const data = await api("/mixes");
    state.mixes.list = data.mixes || [];
  } catch (err) {
    console.error(err);
  } finally {
    state.mixes.loading = false;
    if (state.activeTab === "mixes") renderMixes();
  }
}

function youtubeEmbedUrl(url) {
  // Handles youtu.be/ID, youtube.com/watch?v=ID, youtube.com/embed/ID, youtube.com/live/ID
  const patterns = [
    /youtu\.be\/([a-zA-Z0-9_-]{6,})/,
    /youtube\.com\/watch\?v=([a-zA-Z0-9_-]{6,})/,
    /youtube\.com\/embed\/([a-zA-Z0-9_-]{6,})/,
    /youtube\.com\/live\/([a-zA-Z0-9_-]{6,})/,
  ];
  for (const re of patterns) {
    const match = url.match(re);
    if (match) return `https://www.youtube.com/embed/${match[1]}`;
  }
  return null;
}

function embedFor(url, type) {
  if (!url) return "";

  if (type === "video") {
    const ytUrl = youtubeEmbedUrl(url);
    if (ytUrl) {
      return `<div class="mix-embed-frame video-frame"><iframe src="${ytUrl}" allow="autoplay; encrypted-media" allowfullscreen></iframe></div>`;
    }
    if (url.includes("mixcloud.com")) {
      const feed = encodeURIComponent(new URL(url).pathname);
      return `<div class="mix-embed-frame"><iframe height="400" src="https://www.mixcloud.com/widget/iframe/?hide_cover=0&feed=${feed}" allow="autoplay"></iframe></div>`;
    }
    return `<a href="${url}" target="_blank" rel="noopener" class="btn btn-sm">Watch ↗</a>`;
  }

  // Audio — classic horizontal SoundCloud/Mixcloud bar player
  if (url.includes("soundcloud.com")) {
    return `<div class="mix-embed-frame"><iframe height="166" src="https://w.soundcloud.com/player/?url=${encodeURIComponent(url)}&color=%23b3ff00&auto_play=false&show_artwork=true&show_user=true"></iframe></div>`;
  }
  if (url.includes("mixcloud.com")) {
    const feed = encodeURIComponent(new URL(url).pathname);
    return `<div class="mix-embed-frame"><iframe height="120" src="https://www.mixcloud.com/widget/iframe/?hide_cover=1&feed=${feed}" allow="autoplay"></iframe></div>`;
  }
  if (url.includes("spotify.com")) {
    const embedUrl = url.replace("open.spotify.com/", "open.spotify.com/embed/");
    return `<div class="mix-embed-frame"><iframe height="152" src="${embedUrl}" allow="encrypted-media"></iframe></div>`;
  }
  return `<a href="${url}" target="_blank" rel="noopener" class="btn btn-sm">Listen ↗</a>`;
}

const MAX_PINNED_PER_SECTION = 3;

function renderMixes() {
  const isAdmin = state.authLevel === "admin";
  const mixes = state.mixes.list;

  panelMixes.innerHTML = `
    ${isAdmin ? '<button class="btn btn-primary btn-sm" id="btn-add-mix" style="margin-bottom:24px;">+ Add Mix</button>' : ""}
    ${mixes.length === 0 ? '<div class="empty-state">No mixes uploaded yet.</div>' : `
      <div class="mix-section">
        <div class="section-title">🎧 Audio</div>
        <div class="mix-grid" id="mix-grid-audio"></div>
      </div>
      <div class="mix-section">
        <div class="section-title">🎥 Video</div>
        <div class="mix-grid" id="mix-grid-video"></div>
      </div>
    `}
  `;

  if (mixes.length === 0) return;

  renderMixSection("audio", document.getElementById("mix-grid-audio"), isAdmin);
  renderMixSection("video", document.getElementById("mix-grid-video"), isAdmin);

  if (isAdmin) {
    document.getElementById("btn-add-mix").onclick = () => openMixEditor(null);
  }
}

function mixCardHtml(m, i, isAdmin) {
  return `
    <div class="panel mix-card ${m.pinned ? "pinned" : ""}" draggable="${isAdmin}" data-i="${i}">
      <div class="mix-body">
        <div class="mix-title">${m.pinned ? '<span class="mix-pin-star">★</span> ' : ""}${escapeHtml(m.title || "Untitled Mix")}</div>
        <div class="mix-date">${escapeHtml(m.date || "")}</div>
        <div class="mix-embed">${embedFor(m.link, m.type)}</div>
        <div class="mix-desc">${escapeHtml(m.description || "")}</div>
        ${isAdmin ? `<div style="display:flex; gap:8px; margin-top:12px; flex-wrap:wrap;">
          <button class="icon-btn" data-pin="${i}">${m.pinned ? "★ unpin" : "☆ pin"}</button>
          <button class="icon-btn" data-edit="${i}">edit</button>
          <button class="icon-btn" data-delete="${i}">delete</button>
        </div>` : ""}
      </div>
    </div>`;
}

function renderMixSection(type, grid, isAdmin) {
  if (!grid) return;
  const entries = state.mixes.list
    .map((m, i) => ({ m, i }))
    .filter(({ m }) => (m.type || "audio") === type);

  if (entries.length === 0) {
    grid.innerHTML = `<div class="empty-state">No ${type} mixes yet.</div>`;
    return;
  }

  grid.innerHTML = entries.map(({ m, i }) => mixCardHtml(m, i, isAdmin)).join("");

  if (isAdmin) {
    grid.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => openMixEditor(+b.dataset.edit)));
    grid.querySelectorAll("[data-delete]").forEach((b) => (b.onclick = () => deleteMix(+b.dataset.delete)));
    grid.querySelectorAll("[data-pin]").forEach((b) => (b.onclick = () => toggleMixPin(+b.dataset.pin, type)));
    setupMixDragReorder(grid);
  }
}

function toggleMixPin(index, type) {
  const mix = state.mixes.list[index];
  if (!mix) return;

  if (!mix.pinned) {
    const pinnedCount = state.mixes.list.filter((m) => m.pinned && (m.type || "audio") === type).length;
    if (pinnedCount >= MAX_PINNED_PER_SECTION) {
      toast(`You can only pin up to ${MAX_PINNED_PER_SECTION} ${type} mixes — unpin one first`);
      return;
    }
  }

  mix.pinned = !mix.pinned;

  // Keep pinned mixes grouped at the front within their own type, preserving relative order.
  const sameType = state.mixes.list.filter((m) => (m.type || "audio") === type);
  const otherType = state.mixes.list.filter((m) => (m.type || "audio") !== type);
  const pinned = sameType.filter((m) => m.pinned);
  const unpinned = sameType.filter((m) => !m.pinned);
  state.mixes.list = [...otherType, ...pinned, ...unpinned];

  persistMixes();
}

function setupMixDragReorder(container) {
  let dragIndex = null;
  container.querySelectorAll(".mix-card").forEach((card) => {
    card.addEventListener("dragstart", () => {
      dragIndex = +card.dataset.i;
      card.classList.add("dragging");
    });
    card.addEventListener("dragend", () => card.classList.remove("dragging"));
    card.addEventListener("dragover", (e) => e.preventDefault());
    card.addEventListener("drop", () => {
      const dropIndex = +card.dataset.i;
      if (dragIndex === null || dragIndex === dropIndex) return;
      const [moved] = state.mixes.list.splice(dragIndex, 1);
      state.mixes.list.splice(dropIndex, 0, moved);
      persistMixes();
    });
  });
}

function openMixEditor(index) {
  const existing = index !== null ? { ...state.mixes.list[index] } : { title: "", description: "", date: "", link: "", type: "audio" };
  let selectedType = existing.type || "audio";

  const html = `
    <h3>${index !== null ? "Edit Mix" : "Add Mix"}</h3>

    <div class="modal-field">
      <label class="modal-label">Type</label>
      <div class="pill-row" id="mix-type-pills" style="margin-bottom:0;">
        <button type="button" class="pill ${selectedType === "audio" ? "active" : ""}" data-type="audio">🎧 Audio</button>
        <button type="button" class="pill ${selectedType === "video" ? "active" : ""}" data-type="video">🎥 Video</button>
      </div>
    </div>

    <div class="modal-field">
      <label class="modal-label">Title</label>
      <input class="input" id="mix-title" value="${escapeAttr(existing.title)}" placeholder="Desert Dust · Spring 2025" />
    </div>

    <div class="modal-field">
      <label class="modal-label">Description / vibe notes</label>
      <textarea class="input" id="mix-description" rows="3" placeholder="What this mix sounds like...">${escapeHtml(existing.description)}</textarea>
    </div>

    <div class="modal-field">
      <label class="modal-label">Date</label>
      <input class="input" id="mix-date" value="${escapeAttr(existing.date)}" placeholder="Spring 2025" />
    </div>

    <div class="modal-field">
      <label class="modal-label">Link (SoundCloud / Mixcloud / Spotify / YouTube URL)</label>
      <input class="input" id="mix-link" value="${escapeAttr(existing.link)}" placeholder="https://..." />
    </div>

    <div class="modal-actions">
      <button class="btn btn-ghost btn-sm" id="mix-cancel">Cancel</button>
      <button class="btn btn-primary btn-sm" id="mix-save">Save Mix</button>
    </div>
  `;

  openModal(html, () => {
    document.getElementById("mix-cancel").onclick = closeModal;

    document.getElementById("mix-type-pills").querySelectorAll(".pill").forEach((p) => {
      p.onclick = () => {
        selectedType = p.dataset.type;
        document.getElementById("mix-type-pills").querySelectorAll(".pill").forEach((pp) => pp.classList.toggle("active", pp.dataset.type === selectedType));
      };
    });

    document.getElementById("mix-save").onclick = () => {
      const mix = {
        title: document.getElementById("mix-title").value.trim() || "Untitled Mix",
        description: document.getElementById("mix-description").value.trim(),
        date: document.getElementById("mix-date").value.trim(),
        link: document.getElementById("mix-link").value.trim(),
        type: selectedType,
        pinned: existing.pinned || false,
      };
      if (index !== null) {
        state.mixes.list[index] = mix;
      } else {
        state.mixes.list.push(mix);
      }
      closeModal();
      persistMixes();
    };
  });
}

async function deleteMix(index) {
  if (!confirm("Delete this mix?")) return;
  state.mixes.list.splice(index, 1);
  persistMixes();
}

async function persistMixes() {
  try {
    await api("/mixes", { method: "POST", needsAuth: true, body: { mixes: state.mixes.list } });
    renderMixes();
  } catch (err) {
    toast("Save failed: " + err.message);
  }
}

// ---------------------------------------------------------------------------
// Utils
// ---------------------------------------------------------------------------
function errorCardHtml(message) {
  return `
    <div class="error-card">
      <span class="error-icon">⚠</span>
      <div class="error-title">Something went wrong</div>
      <div class="error-message">${escapeHtml(message)}</div>
    </div>`;
}

function escapeHtml(str) {
  return String(str ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function escapeAttr(str) {
  return escapeHtml(str);
}

// ============================================================================
// PROFILE TAB
// ============================================================================
const panelProfile = document.getElementById("panel-profile");

async function loadProfile() {
  if (!state.username) {
    panelProfile.innerHTML = `
      <div class="panel locked-teaser">
        <h3>Profile</h3>
        <p>Log in with your name (not just the shared PIN) to use Profile.</p>
      </div>`;
    return;
  }
  try {
    state.profile = await api("/profile", { needsAuth: true });
  } catch (err) {
    toast(err.message);
  }
  renderProfile();
}

function renderProfile() {
  const p = state.profile;
  const apiKeyPlaceholder = p && p.hasApiKey
    ? "•••••••• (already set — enter a new key to replace)"
    : "sk-ant-...";

  panelProfile.innerHTML = `
    <div class="section-title">✦ Change PIN</div>
    <div class="seed-row">
      <input class="input" id="profile-current-pin" placeholder="Current PIN" />
      <input class="input" id="profile-new-pin" placeholder="New PIN" />
      <button class="btn btn-sm" id="btn-change-pin">Save</button>
    </div>

    <div class="section-title" style="margin-top:28px;">✦ Anthropic API Key</div>
    <p style="color:var(--muted); font-size:11px; line-height:1.6; max-width:480px;">
      This is separate from your claude.ai login — it's a developer key that lets Discover/Browse
      run under your own account instead of Jade's. Get one at
      <a href="https://console.anthropic.com" target="_blank" rel="noopener" style="color:var(--green);">console.anthropic.com</a>.
    </p>
    <div class="seed-row">
      <input class="input" id="profile-api-key" type="password" placeholder="${escapeAttr(apiKeyPlaceholder)}" />
      <button class="btn btn-sm" id="btn-save-api-key">Save</button>
    </div>

    <div class="section-title" style="margin-top:28px;">✦ Badges</div>
    <div id="profile-badges"></div>
  `;

  const badgesEl = document.getElementById("profile-badges");
  const badges = (p && p.badges) || [];
  badgesEl.innerHTML = badges.length === 0
    ? `<div class="empty-state">No badges yet</div>`
    : badges.map((b) => `
        <div class="channel-track">
          <div class="track-info">
            <div class="track-title">${escapeHtml(b.name || "")}</div>
            <div class="track-meta">${escapeHtml(b.description || "")}</div>
          </div>
        </div>`).join("");

  document.getElementById("btn-change-pin").onclick = async () => {
    const currentPin = document.getElementById("profile-current-pin").value.trim();
    const newPin = document.getElementById("profile-new-pin").value.trim();
    if (!currentPin || !newPin) {
      toast("Enter both PINs");
      return;
    }
    try {
      const res = await fetch(WORKER_URL + "/auth/set-pin", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: state.username, currentPin, newPin }),
      });
      const data = await res.json().catch(() => ({}));
      if (!data.ok) throw new Error(data.error || "Could not change PIN");
      state.pin = newPin;
      sessionStorage.setItem("jade_pin", newPin);
      document.getElementById("profile-current-pin").value = "";
      document.getElementById("profile-new-pin").value = "";
      toast("PIN updated");
    } catch (err) {
      toast(err.message);
    }
  };

  document.getElementById("btn-save-api-key").onclick = async () => {
    const apiKey = document.getElementById("profile-api-key").value.trim();
    if (!apiKey) {
      toast("Enter an API key first");
      return;
    }
    try {
      const res = await fetch(WORKER_URL + "/profile/api-key", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: state.username, pin: state.pin, apiKey }),
      });
      const data = await res.json().catch(() => ({}));
      if (!data.ok) throw new Error(data.error || "Could not save API key");
      state.profile = { ...(state.profile || {}), hasApiKey: true };
      document.getElementById("profile-api-key").value = "";
      toast("API key saved");
      renderProfile();
    } catch (err) {
      toast(err.message);
    }
  };
}

// ============================================================================
// ADMIN TAB
// ============================================================================
const panelAdmin = document.getElementById("panel-admin");
let adminSelectedTier = "friend";

async function loadAdmin() {
  try {
    const data = await api("/admin/users", { needsAuth: true });
    state.adminUsers = data.users || [];
  } catch (err) {
    toast(err.message);
  }
  renderAdmin();
}

function renderAdmin() {
  const users = state.adminUsers || [];

  panelAdmin.innerHTML = `
    <div class="section-title">✦ Users</div>
    <div id="admin-user-list"></div>

    <div class="section-title" style="margin-top:28px;">✦ Create User</div>
    <div class="seed-row">
      <input class="input" id="admin-new-username" placeholder="username (lowercase, no spaces)" />
      <input class="input" id="admin-new-name" placeholder="Display name" />
    </div>
    <div class="seed-row" style="margin-top:10px; align-items:center;">
      <input class="input" id="admin-new-temppin" placeholder="Temp PIN" style="flex:1;" />
      <div class="pill-row" id="admin-new-tier-pills" style="margin-bottom:0;">
        <button type="button" class="pill ${adminSelectedTier === "friend" ? "active" : ""}" data-tier="friend">Friend</button>
        <button type="button" class="pill ${adminSelectedTier === "admin" ? "active" : ""}" data-tier="admin">Admin</button>
      </div>
      <button class="btn btn-sm btn-primary" id="btn-create-user">Create</button>
    </div>
  `;

  const listEl = document.getElementById("admin-user-list");
  listEl.innerHTML = users.length === 0
    ? `<div class="empty-state">No users yet</div>`
    : users.map((u) => `
        <div class="channel-track">
          <div class="track-info">
            <div class="track-title">${escapeHtml(u.name)} <span style="color:var(--muted);">(${escapeHtml(u.username)})</span></div>
            <div class="track-meta">${escapeHtml(u.tier)}${u.pinIsTemp ? " · temp PIN not yet set" : ""}</div>
          </div>
          <div style="display:flex; gap:8px;">
            <button class="icon-btn" data-rename="${escapeAttr(u.username)}">rename</button>
            <button class="icon-btn" data-toggle-tier="${escapeAttr(u.username)}" data-current-tier="${escapeAttr(u.tier)}">${u.tier === "admin" ? "make friend" : "make admin"}</button>
            <button class="icon-btn" data-delete-user="${escapeAttr(u.username)}">delete</button>
          </div>
        </div>`).join("");

  listEl.querySelectorAll("[data-rename]").forEach((btn) => {
    btn.onclick = async () => {
      const username = btn.dataset.rename;
      const newName = prompt("New display name:");
      if (!newName) return;
      try {
        await api("/admin/edit-user", { method: "POST", needsAuth: true, body: { username, name: newName } });
        toast("Renamed");
        loadAdmin();
      } catch (err) {
        toast(err.message);
      }
    };
  });

  listEl.querySelectorAll("[data-toggle-tier]").forEach((btn) => {
    btn.onclick = async () => {
      const username = btn.dataset.toggleTier;
      const newTier = btn.dataset.currentTier === "admin" ? "friend" : "admin";
      try {
        await api("/admin/edit-user", { method: "POST", needsAuth: true, body: { username, tier: newTier } });
        toast(`${username} is now ${newTier}`);
        loadAdmin();
      } catch (err) {
        toast(err.message);
      }
    };
  });

  listEl.querySelectorAll("[data-delete-user]").forEach((btn) => {
    btn.onclick = async () => {
      const username = btn.dataset.deleteUser;
      if (!confirm(`Delete user "${username}"? This can't be undone.`)) return;
      try {
        await api("/admin/delete-user", { method: "POST", needsAuth: true, body: { username } });
        toast("Deleted");
        loadAdmin();
      } catch (err) {
        toast(err.message);
      }
    };
  });

  document.getElementById("admin-new-tier-pills").querySelectorAll(".pill").forEach((p) => {
    p.onclick = () => {
      adminSelectedTier = p.dataset.tier;
      renderAdmin();
    };
  });

  document.getElementById("btn-create-user").onclick = async () => {
    const username = document.getElementById("admin-new-username").value.trim();
    const name = document.getElementById("admin-new-name").value.trim();
    const tempPin = document.getElementById("admin-new-temppin").value.trim();
    if (!username || !name || !tempPin) {
      toast("Fill in username, name, and a temp PIN");
      return;
    }
    try {
      await api("/admin/create-user", {
        method: "POST",
        needsAuth: true,
        body: { username, name, tempPin, tier: adminSelectedTier },
      });
      toast(`Created ${name} as ${adminSelectedTier}`);
      loadAdmin();
    } catch (err) {
      toast(err.message);
    }
  };
}

// ============================================================================
// IMPORT TAB (Rekordbox)
// ============================================================================
const panelImport = document.getElementById("panel-import");

// Rekordbox XML stores duration as TotalTime in whole seconds — convert to
// the same MM:SS format the TXT export already uses.
function formatSecondsAsTime(totalSeconds) {
  const s = parseInt(totalSeconds, 10);
  if (!s || isNaN(s) || s < 0) return "";
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

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
      album: el.getAttribute("Album") || "",
      genre: el.getAttribute("Genre") || "",
      bpm: el.getAttribute("AverageBpm") || "",
      key: el.getAttribute("Tonality") || "",
      time: formatSecondsAsTime(el.getAttribute("TotalTime")),
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
  const lines = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n").filter((l) => l.trim() !== "");
  if (lines.length < 2) return [];

  const headers = lines[0].split("\t").map((h) => h.trim());
  const colIndex = (...names) => {
    for (const name of names) {
      const i = headers.findIndex((h) => h.toLowerCase() === name.toLowerCase());
      if (i !== -1) return i;
    }
    return -1;
  };

  const trackIdx = colIndex("Track Title", "Name");
  const artistIdx = colIndex("Artist");
  const albumIdx = colIndex("Album");
  const genreIdx = colIndex("Genre");
  const bpmIdx = colIndex("BPM");
  const keyIdx = colIndex("Key", "Tonality");
  const timeIdx = colIndex("Time");
  const labelIdx = colIndex("Label");

  const tracks = [];
  for (let i = 1; i < lines.length; i++) {
    const cols = lines[i].split("\t");
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
  }
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
        For best results, organize into playlists by vibe/genre in Rekordbox before exporting. A full XML
        collection export or a single playlist exported to TXT both work — TXT is usually the better pick
        if you want to import just one playlist rather than your whole library.
      </p>
    </div>

    <div class="section-title">✦ Rekordbox Export (XML or TXT)</div>
    <div class="seed-row">
      <input class="input" id="import-file-input" type="file" accept=".xml,.txt" style="flex:1;" />
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
    const body = { mode: imp.mode, tracks: imp.tracks, description, filename: imp.fileName };

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
// ---------------------------------------------------------------------------
renderPinDots();
if (state.authLevel !== "none") {
  loadInitialData();
  setActiveTab("discover");
} else {
  loadMixes();
}
