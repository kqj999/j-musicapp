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
  browse: { channels: {} }, // channel -> { tracks: [], loading }
  crate: { lists: [], activeListIndex: 0, loading: false },
  mixes: { list: [], loading: false },
};

BROWSE_CHANNELS.forEach((c) => (state.browse.channels[c] = { tracks: [], loading: false }));

// ---------------------------------------------------------------------------
// API helper
// ---------------------------------------------------------------------------
async function api(path, { method = "GET", body = null, needsAuth = false } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (needsAuth && state.pin) headers["X-Pin"] = state.pin;
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

// Tiers: 'admin' (full access), 'view' (sees Discover/Browse UI as a preview,
// but can't actually run searches — no credits spent), 'guest' (Discover/Browse
// stay behind a locked teaser), 'none'.
function discoverBrowseVisible() {
  return state.authLevel === "admin" || state.authLevel === "view";
}
function canRunDiscoverBrowse() {
  return state.authLevel === "admin";
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

// If a PIN session already exists (page reload), resume it
if (state.authLevel !== "none" && state.pin) {
  landing.classList.add("hidden");
  appShell.classList.remove("hidden");
  renderSessionBadge();
  renderTabLocks();
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
  if (tab === "browse") renderBrowse();
  if (tab === "crate") renderCrate();
  if (tab === "mixes") renderMixes();
}

function loadInitialData() {
  if (state.authLevel === "admin") {
    loadCrate();
  } else if (state.authLevel === "guest" || state.authLevel === "view") {
    loadPublicCrate();
  }
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
}

// ============================================================================
// CRATE TAB
// ============================================================================
const panelCrate = document.getElementById("panel-crate");

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

async function persistCrate() {
  if (state.authLevel !== "admin") return;
  try {
    await api("/crate", { method: "POST", needsAuth: true, body: { lists: state.crate.lists } });
  } catch (err) {
    toast("Save failed: " + err.message);
  }
}

function saveTracksToCrate(tracks) {
  if (state.authLevel !== "admin") {
    toast("Admin access required to save to Crate");
    return;
  }
  if (state.crate.lists.length === 0) {
    state.crate.lists.push({ name: "New List", locked: false, tracks: [] });
  }
  const target = state.crate.lists[state.crate.activeListIndex] || state.crate.lists[0];
  tracks.forEach((t) =>
    target.tracks.push({ artist: t.artist || "", track: t.track || "", label: t.label || "", bpm: t.bpm || "", key: t.key || "", notes: "", audioUrl: null })
  );
  persistCrate();
  toast(`Added ${tracks.length} track(s) to "${target.name}"`);
  if (state.activeTab === "crate") renderCrate();
}

function renderCrate() {
  if (state.authLevel === "none") {
    panelCrate.innerHTML = `<div class="panel locked-teaser"><h3>Crate</h3><p>Enter a PIN to view saved lists.</p></div>`;
    return;
  }

  const lists = state.crate.lists;
  const isAdmin = state.authLevel === "admin";

  panelCrate.innerHTML = `
    <div class="crate-layout">
      <div class="panel crate-sidebar">
        <div class="section-title">✦ Lists</div>
        <div id="crate-list-items"></div>
        ${isAdmin ? '<button class="btn btn-sm" id="btn-new-list" style="margin-top:10px; width:100%;">+ New List</button>' : ""}
      </div>
      <div class="panel crate-main" id="crate-main"></div>
    </div>
  `;

  renderCrateSidebar();
  renderCrateMain();

  if (isAdmin) {
    document.getElementById("btn-new-list").onclick = () => {
      const name = prompt("List name:", "Untitled List");
      if (!name) return;
      state.crate.lists.push({ name, locked: false, tracks: [] });
      state.crate.activeListIndex = state.crate.lists.length - 1;
      persistCrate();
      renderCrate();
    };
  }
}

function renderCrateSidebar() {
  const el = document.getElementById("crate-list-items");
  const lists = state.crate.lists;
  if (lists.length === 0) {
    el.innerHTML = `<div class="empty-state" style="padding:20px 0;">No lists yet</div>`;
    return;
  }
  el.innerHTML = lists
    .map(
      (l, i) => `
    <div class="crate-list-item ${i === state.crate.activeListIndex ? "active" : ""}" data-i="${i}">
      <span>${escapeHtml(l.name)}</span>
      <span>${l.locked ? "🔒" : "🔓"}</span>
    </div>`
    )
    .join("");
  el.querySelectorAll(".crate-list-item").forEach((item) => {
    item.onclick = () => {
      state.crate.activeListIndex = +item.dataset.i;
      renderCrate();
    };
  });
}

function renderCrateMain() {
  const el = document.getElementById("crate-main");
  const list = state.crate.lists[state.crate.activeListIndex];
  const isAdmin = state.authLevel === "admin";

  if (!list) {
    el.innerHTML = `<div class="empty-state">Select or create a list</div>`;
    return;
  }

  el.innerHTML = `
    <div class="channel-head">
      <h4>${escapeHtml(list.name)}</h4>
      <div style="display:flex; gap:8px; flex-wrap:wrap;">
        <button class="icon-btn" id="btn-play-list">▶ play list</button>
        ${isAdmin ? `<button class="icon-btn" id="btn-toggle-lock">${list.locked ? "🔒 locked" : "🔓 unlocked"}</button>` : ""}
        ${isAdmin ? `<button class="icon-btn" id="btn-rename-list">rename</button>` : ""}
        ${isAdmin ? `<button class="icon-btn" id="btn-delete-list">delete</button>` : ""}
        <button class="icon-btn" id="btn-export-list">export .txt</button>
      </div>
    </div>
    ${isAdmin ? `
      <div class="seed-row" style="margin-top:14px;">
        <input class="input" id="manual-artist" placeholder="Artist" style="flex:1;" />
        <input class="input" id="manual-track" placeholder="Track" style="flex:1;" />
        <button class="btn btn-sm" id="btn-add-manual">Add</button>
      </div>
    ` : ""}
    <div id="crate-tracks" style="margin-top:10px;"></div>
  `;

  renderCrateTracks(list, isAdmin);

  if (isAdmin) {
    document.getElementById("btn-toggle-lock").onclick = () => {
      list.locked = !list.locked;
      persistCrate();
      renderCrate();
    };
    document.getElementById("btn-rename-list").onclick = () => {
      const name = prompt("Rename list:", list.name);
      if (!name) return;
      list.name = name;
      persistCrate();
      renderCrate();
    };
    document.getElementById("btn-delete-list").onclick = () => {
      if (!confirm(`Delete "${list.name}"?`)) return;
      state.crate.lists.splice(state.crate.activeListIndex, 1);
      state.crate.activeListIndex = 0;
      persistCrate();
      renderCrate();
    };
    document.getElementById("btn-add-manual").onclick = () => {
      const artist = document.getElementById("manual-artist").value.trim();
      const track = document.getElementById("manual-track").value.trim();
      if (!artist) return;
      list.tracks.push({ artist, track, label: "", bpm: "", key: "", notes: "", audioUrl: null });
      persistCrate();
      renderCrate();
    };
  }

  document.getElementById("btn-export-list").onclick = () => exportListAsTxt(list);
  document.getElementById("btn-play-list").onclick = () => playQueue(list.tracks, 0, list.name);
}

function renderCrateTracks(list, isAdmin) {
  const el = document.getElementById("crate-tracks");
  if (list.tracks.length === 0) {
    el.innerHTML = `<div class="empty-state">No tracks in this list yet</div>`;
    return;
  }
  el.innerHTML = list.tracks
    .map(
      (t, i) => `
    <div class="crate-track-row" draggable="${isAdmin}" data-i="${i}">
      <span class="drag-handle">${isAdmin ? "⠿" : ""}</span>
      <div>
        <div class="track-title">${escapeHtml(t.artist)}${t.track ? " — " + escapeHtml(t.track) : ""}</div>
        <div class="track-meta">${escapeHtml(t.label || "")} ${t.bpm ? "· " + t.bpm + " BPM" : ""} ${t.key ? "· " + escapeHtml(t.key) : ""} ${t.audioUrl ? "· 🎵 audio uploaded" : ""}</div>
        ${isAdmin ? `<input class="crate-notes" data-i="${i}" placeholder="notes..." value="${escapeAttr(t.notes || "")}" />` : t.notes ? `<div class="track-meta">${escapeHtml(t.notes)}</div>` : ""}
        ${isAdmin ? `
          <label class="icon-btn" style="display:inline-block; margin-top:6px; cursor:pointer;">
            ${t.audioUrl ? "replace audio" : "upload audio"}
            <input type="file" accept="audio/mpeg,audio/wav,audio/mp3,.mp3,.wav" data-audio-upload="${i}" style="display:none;" />
          </label>
          <span class="upload-progress" data-upload-status="${i}"></span>
        ` : ""}
      </div>
      <button class="icon-btn" data-play="${i}" ${t.audioUrl ? "" : "disabled"} title="${t.audioUrl ? "Play" : "No audio uploaded"}">▶</button>
      ${isAdmin ? `<button class="icon-btn" data-remove="${i}">✕</button>` : "<span></span>"}
    </div>`
    )
    .join("");

  if (isAdmin) {
    el.querySelectorAll(".crate-notes").forEach((input) => {
      input.onchange = () => {
        list.tracks[+input.dataset.i].notes = input.value;
        persistCrate();
      };
    });
    el.querySelectorAll("[data-remove]").forEach((btn) => {
      btn.onclick = () => {
        list.tracks.splice(+btn.dataset.remove, 1);
        persistCrate();
        renderCrateMain();
      };
    });
    el.querySelectorAll("[data-audio-upload]").forEach((input) => {
      input.onchange = async () => {
        const file = input.files[0];
        if (!file) return;
        const i = +input.dataset.audioUpload;
        const statusEl = document.querySelector(`[data-upload-status="${i}"]`);
        statusEl.textContent = "uploading...";
        try {
          const url = await uploadMedia(file, "audio");
          list.tracks[i].audioUrl = url;
          await persistCrate();
          toast("Audio uploaded");
          renderCrateMain();
        } catch (err) {
          statusEl.textContent = "";
          toast("Upload failed: " + err.message);
        }
      };
    });
    setupDragReorder(el, list);
  }

  el.querySelectorAll("[data-play]").forEach((btn) => {
    if (btn.disabled) return;
    btn.onclick = () => playQueue(list.tracks, +btn.dataset.play, list.name);
  });
}

function setupDragReorder(container, list) {
  let dragIndex = null;
  container.querySelectorAll(".crate-track-row").forEach((row) => {
    row.addEventListener("dragstart", () => {
      dragIndex = +row.dataset.i;
      row.classList.add("dragging");
    });
    row.addEventListener("dragend", () => row.classList.remove("dragging"));
    row.addEventListener("dragover", (e) => e.preventDefault());
    row.addEventListener("drop", () => {
      const dropIndex = +row.dataset.i;
      if (dragIndex === null || dragIndex === dropIndex) return;
      const [moved] = list.tracks.splice(dragIndex, 1);
      list.tracks.splice(dropIndex, 0, moved);
      persistCrate();
      renderCrateMain();
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
