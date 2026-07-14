const API = "";

// ---------- sound effects ----------
const VOLUME_KEY = "kotoba-volume";
const storedVolume = parseInt(localStorage.getItem(VOLUME_KEY), 10);
let masterVolume = Number.isFinite(storedVolume) ? Math.min(100, Math.max(0, storedVolume)) : 70;
let volumeBeforeMute = masterVolume || 70;

let _ac = null;
let _masterGain = null;
function ac() {
  const AC = window.AudioContext || window.webkitAudioContext;
  if (!AC) return null;
  if (!_ac) {
    _ac = new AC();
    _masterGain = _ac.createGain();
    _masterGain.gain.value = masterVolume / 100;
    _masterGain.connect(_ac.destination);
  }
  if (_ac.state === "suspended") _ac.resume();
  return _ac;
}

function setVolume(value) {
  masterVolume = Math.min(100, Math.max(0, value));
  localStorage.setItem(VOLUME_KEY, String(masterVolume));
  if (_masterGain) _masterGain.gain.value = masterVolume / 100;

  const audioEl = document.getElementById("rv-audio-el");
  if (audioEl) audioEl.volume = masterVolume / 100;

  const slider = document.getElementById("volume-slider");
  slider.value = masterVolume;
  slider.style.background = `linear-gradient(to right, var(--accent) ${masterVolume}%, var(--border) ${masterVolume}%)`;
  document.getElementById("volume-icon").classList.toggle("muted", masterVolume === 0);
}

document.getElementById("volume-slider").addEventListener("input", (e) => {
  setVolume(parseInt(e.target.value, 10));
});

document.getElementById("volume-slider").addEventListener("change", (e) => {
  e.target.blur();
});

document.getElementById("volume-icon").addEventListener("click", () => {
  if (masterVolume > 0) {
    volumeBeforeMute = masterVolume;
    setVolume(0);
  } else {
    setVolume(volumeBeforeMute || 70);
  }
});

setVolume(masterVolume);

function playSwoosh() {
  const ctx = ac();
  if (!ctx) return;
  const dur = 0.35;
  const t = ctx.currentTime;
  const buf = ctx.createBuffer(1, Math.floor(ctx.sampleRate * dur), ctx.sampleRate);
  const d = buf.getChannelData(0);
  for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * (1 - i / d.length);
  const src = ctx.createBufferSource();
  src.buffer = buf;
  const filt = ctx.createBiquadFilter();
  filt.type = "bandpass";
  filt.Q.value = 0.8;
  filt.frequency.setValueAtTime(1400, t);
  filt.frequency.exponentialRampToValueAtTime(350, t + dur);
  const g = ctx.createGain();
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(0.06, t + 0.06);
  g.gain.exponentialRampToValueAtTime(0.0001, t + dur);
  src.connect(filt);
  filt.connect(g);
  g.connect(_masterGain);
  src.start(t);
  src.stop(t + dur);
}

function playBell(quality) {
  const ctx = ac();
  if (!ctx) return;
  const freq = { 0: 440, 2: 523.25, 3: 659.25, 4: 783.99, 5: 987.77 }[quality] || 659.25;
  const t = ctx.currentTime;
  const g = ctx.createGain();
  g.gain.setValueAtTime(0.0001, t);
  g.gain.exponentialRampToValueAtTime(0.07, t + 0.012);
  g.gain.exponentialRampToValueAtTime(0.0001, t + 0.6);
  g.connect(_masterGain);
  [[1, 1], [2.76, 0.25]].forEach(([mult, amp]) => {
    const o = ctx.createOscillator();
    o.type = "sine";
    o.frequency.value = freq * mult;
    const og = ctx.createGain();
    og.gain.value = amp;
    o.connect(og);
    og.connect(g);
    o.start(t);
    o.stop(t + 0.6);
  });
}

// ---------- tabs ----------
let panelAnimFlip = false;

function positionTabIndicator() {
  const active = document.querySelector(".tab-btn.active");
  const indicator = document.getElementById("tab-indicator");
  if (!active || !indicator) return;
  indicator.style.left = active.offsetLeft + "px";
  indicator.style.top = active.offsetTop + "px";
  indicator.style.width = active.offsetWidth + "px";
  indicator.style.height = active.offsetHeight + "px";
}

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.classList.contains("active")) return;
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    positionTabIndicator();
    if (btn.dataset.tab === "recent") loadRecent();

    panelAnimFlip = !panelAnimFlip;
    const wrap = document.getElementById("panel-anim-wrap");
    wrap.classList.remove("anim-a", "anim-b");
    void wrap.offsetWidth; // restart animation
    wrap.classList.add(panelAnimFlip ? "anim-a" : "anim-b");
  });
});

window.addEventListener("resize", positionTabIndicator);
if (document.fonts && document.fonts.ready) document.fonts.ready.then(positionTabIndicator);
positionTabIndicator();

function setOffline(isOffline) {
  document.getElementById("offline-badge").classList.toggle("hidden", !isOffline);
}

async function apiFetch(url, options) {
  try {
    const res = await fetch(url, options);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `${res.status} ${res.statusText}`);
    }
    setOffline(false);
    return await res.json();
  } catch (err) {
    if (err instanceof TypeError) {
      setOffline(true);
    }
    throw err;
  }
}

function renderAudio(audioPath) {
  if (!audioPath) return "";
  return `<div class="audio-row"><button class="pill-ghost play-audio-btn" data-audio="/audio/${encodeURIComponent(audioPath)}">▶ Play audio</button></div>`;
}

let sharedAudioEl = null;

document.addEventListener("click", (e) => {
  if (!e.target.classList.contains("play-audio-btn")) return;
  if (!sharedAudioEl) sharedAudioEl = new Audio();
  sharedAudioEl.src = e.target.dataset.audio;
  sharedAudioEl.play();
});

function escapeAttr(str) {
  return String(str).replace(/&/g, "&amp;").replace(/"/g, "&quot;");
}

function escapeHtml(str) {
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

// Render a card's sentence with the target word colored. Prefers the deck's
// own <b></b> markup (preserved at import as `highlight`) — it marks WHICH
// occurrence is the target, which substring matching can't (人 appears twice
// in あの人はいい人です。). Falls back to first-occurrence headword match for
// cards imported before highlights were stored.
function renderJapanese(card) {
  if (card.highlight && card.highlight.includes("<b>")) {
    return card.highlight
      .split(/(<b>|<\/b>)/)
      .map((part) =>
        part === "<b>" ? '<span class="hl-word">' : part === "</b>" ? "</span>" : escapeHtml(part)
      )
      .join("");
  }
  const jp = escapeHtml(card.japanese);
  const hw = card.headword ? escapeHtml(card.headword) : "";
  if (hw && jp.includes(hw)) return jp.replace(hw, `<span class="hl-word">${hw}</span>`);
  return jp;
}

// The target word's definition line, shown above the sentence translation
// once the answer is revealed. The word itself isn't repeated — it's already
// highlighted in the sentence — so this is just its hiragana reading (when
// that adds information beyond the word itself) plus the meaning.
function renderWordDef(card) {
  if (!card.word_meaning) return "";
  const reading =
    card.word_reading && card.word_reading !== card.headword
      ? `<span class="word-def-reading">${escapeHtml(card.word_reading)}</span>`
      : "";
  return `${reading}<span class="word-def-meaning">${escapeHtml(card.word_meaning)}</span>`;
}

let breakdownSlotCounter = 0;

function renderBreakdownButton(japanese) {
  const slotId = `bd-slot-${breakdownSlotCounter++}`;
  return `<button class="breakdown-btn pill-dark" data-japanese="${escapeAttr(japanese)}" data-target="${slotId}">Breakdown ↴</button>
    <div id="${slotId}" class="breakdown-slot"></div>`;
}

// Same reading-pill + translation + breakdown reveal, gated behind a Show
// Answer button, used everywhere a card's Japanese is shown up front —
// mirrors the Review tab's reveal flow instead of exposing the answer immediately.
function renderRevealBlock(card) {
  const wordDef = renderWordDef(card);
  const image = card.image_path
    ? `<img class="word-image" src="/images/${encodeURIComponent(card.image_path)}" alt="" loading="lazy">`
    : "";
  return `<button class="pill-accent show-answer-btn">Show Answer</button>
    <div class="result-reveal hidden">
      ${image}
      ${wordDef ? `<div class="word-def">${wordDef}</div>` : ""}
      ${card.reading ? `<div class="reading-pill">${card.reading}</div>` : ""}
      <div class="english">${card.english}</div>
      ${renderBreakdownButton(card.japanese)}
    </div>`;
}

document.addEventListener("click", (e) => {
  if (!e.target.classList.contains("show-answer-btn")) return;
  const reveal = e.target.nextElementSibling;
  const nowHidden = reveal.classList.toggle("hidden");
  if (!nowHidden) playSwoosh();
  e.target.textContent = nowHidden ? "Show Answer" : "Minimize";
});

document.addEventListener("click", async (e) => {
  if (!e.target.classList.contains("breakdown-btn")) return;
  const btn = e.target;
  const japanese = btn.dataset.japanese;
  const slot = document.getElementById(btn.dataset.target);
  btn.classList.add("hidden");
  slot.textContent = "Loading...";
  try {
    const data = await apiFetch(`${API}/breakdown`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ japanese }),
    });
    slot.innerHTML = renderBreakdownTable(data.breakdown);
  } catch (err) {
    slot.textContent = "AI unavailable — breakdown offline.";
  }
});

function renderBreakdownTable(breakdown) {
  const rows = breakdown
    .map((t) => {
      const word = t.dictionary_form || t.token;
      const isPunct = (t.part_of_speech || "").toLowerCase().includes("punct");
      const exampleBtn = isPunct
        ? ""
        : `<button class="example-btn" data-word="${escapeAttr(word)}" data-reading="${escapeAttr(t.reading || "")}">Example</button>`;
      return `<tr>
        <td>${t.token}</td><td>${t.reading}</td><td>${t.dictionary_form}</td>
        <td>${t.part_of_speech}</td><td>${t.meaning}</td><td>${t.grammar_note}</td>
        <td>${exampleBtn}</td>
      </tr>`;
    })
    .join("");
  return `<table>
    <thead><tr><th>Token</th><th>Reading</th><th>Dict. form</th><th>POS</th><th>Meaning</th><th>Note</th><th></th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

// Wrap the target word inside an example sentence. The sentence usually
// contains an inflected surface form (食べます for 食べる), so fall back to
// progressively shorter prefixes of the target — a kanji stem may match down
// to a single character, but a pure-kana prefix must keep at least two so a
// lone kana can't false-match a particle.
const KANJI_RE = /[一-鿿]/;

function highlightIn(sentence, target, className) {
  const esc = escapeHtml(sentence);
  if (!target) return esc;
  for (let len = target.length; len >= 1; len--) {
    const prefix = target.slice(0, len);
    if (len < (KANJI_RE.test(prefix) ? 1 : 2)) break;
    const escPrefix = escapeHtml(prefix);
    if (esc.includes(escPrefix)) {
      return esc.replace(escPrefix, `<span class="${className}">${escPrefix}</span>`);
    }
  }
  return esc;
}

// "Example" button on a breakdown row: generate (or fetch from cache) one
// example sentence for that token and insert it as a full-width row directly
// beneath — pure sentence, hiragana rendering, then the English translation.
// Once generated, the button toggles the row: Example <-> Minimize.
document.addEventListener("click", async (e) => {
  if (!e.target.classList.contains("example-btn")) return;
  const btn = e.target;
  const tokenRow = btn.closest("tr");

  const existingRow = tokenRow.nextElementSibling;
  if (existingRow && existingRow.classList.contains("example-row")) {
    const nowHidden = existingRow.classList.toggle("hidden");
    btn.textContent = nowHidden ? "Example" : "Minimize";
    return;
  }

  const word = btn.dataset.word;
  const reading = btn.dataset.reading || "";
  btn.disabled = true;
  btn.textContent = "...";
  try {
    const ex = await apiFetch(`${API}/example`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ word }),
    });
    const exampleRow = document.createElement("tr");
    exampleRow.className = "example-row";
    exampleRow.innerHTML = `<td colspan="7">
      <div class="ex-jp">${highlightIn(ex.japanese, word, "hl-word")}</div>
      <div class="ex-hira">${highlightIn(ex.hiragana, reading || word, "ex-hl-dark")}</div>
      <div class="ex-en">${escapeHtml(ex.english)}</div>
    </td>`;
    tokenRow.after(exampleRow);
    btn.disabled = false;
    btn.textContent = "Minimize";
  } catch (err) {
    btn.disabled = false;
    btn.textContent = "offline";
    setTimeout(() => {
      btn.textContent = "Example";
    }, 2000);
  }
});

// ---------- review ----------
let dueQueue = [];
let currentCard = null;
let sessionPosition = 1;
let grading = false;
let lastGraded = null;
let gradeHistory = []; // session-local qualities, newest last — feeds the streak flame

// How many other cards get shown before a just-graded card resurfaces this
// session. This is separate from — and in addition to — the long-term SM-2
// due_date the same grade also sets on the backend for future days.
//
// Not a flat per-grade lookup: distance compounds with `repetitions` (SM-2's
// count of consecutive good grades, returned by /review/grade — it resets to
// 0 the moment a card is graded Hard or Very Hard). Each grade tier has its
// own base distance and its own growth rate per repetition, so a card
// consistently graded Very Easy gets pushed out of the session fast, a
// Medium card grows more slowly, and a Hard/Very Hard grade always snaps
// back to a short distance regardless of prior history (repetitions is 0
// again the instant it resets).
const GRADE_TIERS = {
  0: { base: 2, growth: 1.0 }, // Very Hard — never compounds, always ~immediate
  2: { base: 3, growth: 1.15 }, // Hard
  3: { base: 5, growth: 1.3 }, // Medium
  4: { base: 8, growth: 1.6 }, // Easy
  5: { base: 12, growth: 2.0 }, // Very Easy — compounds fastest
};

function computeRequeueDistance(quality, repetitions) {
  const tier = GRADE_TIERS[quality] ?? GRADE_TIERS[3];
  return Math.round(tier.base * Math.pow(tier.growth, repetitions));
}

async function loadDue() {
  dueQueue = await apiFetch(`${API}/review/due`);
  sessionPosition = 1;
  lastGraded = null;
  gradeHistory = [];
  updateStreak(false);
  document.getElementById("rv-back-btn").classList.add("hidden");
  showCard();
}

// ---------- streak ----------
// Consecutive Easy / Very Easy grades this session. The flame appears at 2,
// warms through tiers as the run grows, and resets the moment anything below
// Easy is graded. Session-local, like the requeue clock.
function currentStreak() {
  let n = 0;
  for (let i = gradeHistory.length - 1; i >= 0 && gradeHistory[i] >= 4; i--) n++;
  return n;
}

function updateStreak(grew) {
  const el = document.getElementById("rv-streak");
  const n = currentStreak();
  el.classList.toggle("hidden", n < 2);
  if (n < 2) {
    el.classList.remove("streak-warm", "streak-hot", "streak-blaze", "streak-pop");
    return;
  }
  document.getElementById("rv-streak-count").textContent = n;
  el.classList.toggle("streak-warm", n >= 3 && n < 6);
  el.classList.toggle("streak-hot", n >= 6 && n < 10);
  el.classList.toggle("streak-blaze", n >= 10);
  if (grew) {
    el.classList.remove("streak-pop");
    void el.offsetWidth; // restart the pop animation
    el.classList.add("streak-pop");
  }
}

function showCard() {
  document.getElementById("rv-reveal").classList.add("hidden");
  document.getElementById("rv-grades").classList.add("hidden");
  document.getElementById("rv-show-wrap").classList.remove("hidden");
  document.getElementById("rv-breakdown-table").innerHTML = "";
  document.getElementById("rv-breakdown-btn").classList.remove("hidden");
  document.getElementById("rv-play-audio").classList.add("hidden");

  currentCard = dueQueue.shift() || null;
  const cardWrap = document.getElementById("review-card-wrap");
  const sessionBar = document.getElementById("review-session-bar");
  const emptyEl = document.getElementById("review-empty");

  if (!currentCard) {
    cardWrap.classList.add("hidden");
    sessionBar.classList.add("hidden");
    emptyEl.classList.remove("hidden");
    return;
  }
  emptyEl.classList.add("hidden");
  cardWrap.classList.remove("hidden");
  sessionBar.classList.remove("hidden");
  populateCardDOM(currentCard);
}

function populateCardDOM(card) {
  document.getElementById("rv-position").textContent = sessionPosition;
  document.getElementById("rv-japanese").innerHTML = renderJapanese(card);

  const imageEl = document.getElementById("rv-word-image");
  if (card.image_path) {
    imageEl.src = `/images/${encodeURIComponent(card.image_path)}`;
    imageEl.classList.remove("hidden");
  } else {
    imageEl.removeAttribute("src");
    imageEl.classList.add("hidden");
  }

  const wordDefEl = document.getElementById("rv-word-def");
  const wordDef = renderWordDef(card);
  wordDefEl.innerHTML = wordDef;
  wordDefEl.classList.toggle("hidden", !wordDef);

  const audioEl = document.getElementById("rv-audio-el");
  const playBtn = document.getElementById("rv-play-audio");
  if (card.audio_path) {
    audioEl.src = `/audio/${encodeURIComponent(card.audio_path)}`;
    playBtn.classList.remove("hidden");
  } else {
    audioEl.removeAttribute("src");
    playBtn.classList.add("hidden");
  }

  document.getElementById("rv-reading").textContent = card.reading || "";
  document.getElementById("rv-english").textContent = card.english;
  const count = card.review_count || 0;
  document.getElementById("rv-review-count").textContent =
    count === 0 ? "New card" : `Reviewed ${count} time${count === 1 ? "" : "s"}`;
}

document.getElementById("rv-play-audio").addEventListener("click", () => {
  const audioEl = document.getElementById("rv-audio-el");
  if (audioEl.src) audioEl.play();
});

function revealCard() {
  playSwoosh();
  document.getElementById("rv-reveal").classList.remove("hidden");
  document.getElementById("rv-grades").classList.remove("hidden");
  document.getElementById("rv-show-wrap").classList.add("hidden");
}

document.getElementById("rv-show").addEventListener("click", revealCard);

document.getElementById("rv-breakdown-btn").addEventListener("click", async (e) => {
  e.target.classList.add("hidden");
  const el = document.getElementById("rv-breakdown-table");
  el.textContent = "Loading...";
  try {
    const data = await apiFetch(`${API}/breakdown`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ japanese: currentCard.japanese, card_id: currentCard.id }),
    });
    el.innerHTML = renderBreakdownTable(data.breakdown);
  } catch (err) {
    el.textContent = "AI unavailable — breakdown offline.";
  }
});

async function gradeCard(quality) {
  if (grading || !currentCard) return;
  grading = true;
  playBell(quality);
  const gradedCard = currentCard;
  lastGraded = { card: gradedCard, prevReviewCount: gradedCard.review_count };

  const cardEl = document.getElementById("review-card");
  cardEl.classList.add("anim-out");

  const result = await apiFetch(`${API}/review/grade`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ card_id: gradedCard.id, quality }),
  });

  gradedCard.review_count = result.review_count;
  const distance = computeRequeueDistance(quality, result.repetitions);
  const insertAt = Math.min(dueQueue.length, distance);
  dueQueue.splice(insertAt, 0, gradedCard);
  sessionPosition += 1;
  gradeHistory.push(quality);
  updateStreak(quality >= 4);
  document.getElementById("rv-back-btn").classList.remove("hidden");

  setTimeout(() => {
    showCard();
    cardEl.classList.remove("anim-out");
    cardEl.classList.add("anim-in");
    setTimeout(() => {
      cardEl.classList.remove("anim-in");
      grading = false;
    }, 340);
  }, 230);
}

document.querySelectorAll(".grade-btn").forEach((btn) => {
  btn.addEventListener("click", () => gradeCard(parseInt(btn.dataset.q, 10)));
});

async function goBack() {
  if (!lastGraded || grading) return;
  grading = true;
  playSwoosh(); // fire before the await — same sound as Show Answer, and keeps it tied to the click gesture
  try {
    await apiFetch(`${API}/review/undo`, { method: "POST" });
  } catch (err) {
    grading = false;
    return;
  }

  const idx = dueQueue.indexOf(lastGraded.card);
  if (idx !== -1) dueQueue.splice(idx, 1);
  if (currentCard) dueQueue.unshift(currentCard);

  lastGraded.card.review_count = lastGraded.prevReviewCount;
  currentCard = lastGraded.card;
  sessionPosition = Math.max(1, sessionPosition - 1);
  gradeHistory.pop();
  updateStreak(false);

  document.getElementById("review-empty").classList.add("hidden");
  document.getElementById("review-card-wrap").classList.remove("hidden");
  document.getElementById("review-session-bar").classList.remove("hidden");
  populateCardDOM(currentCard);
  document.getElementById("rv-reveal").classList.remove("hidden");
  document.getElementById("rv-grades").classList.remove("hidden");
  document.getElementById("rv-show-wrap").classList.add("hidden");

  lastGraded = null;
  document.getElementById("rv-back-btn").classList.add("hidden");
  grading = false;
}

document.getElementById("rv-back-btn").addEventListener("click", goBack);

document.addEventListener("keydown", (e) => {
  if (!document.getElementById("tab-review").classList.contains("active")) return;
  const tag = (e.target.tagName || "").toLowerCase();
  if (tag === "input" || tag === "textarea") return;
  const revealed = !document.getElementById("rv-reveal").classList.contains("hidden");
  if (e.code === "Space" && !revealed && currentCard) {
    e.preventDefault();
    revealCard();
  } else if (revealed && ["1", "2", "3", "4", "5"].includes(e.key)) {
    gradeCard([0, 2, 3, 4, 5][parseInt(e.key, 10) - 1]);
  } else if (e.code === "Backspace" && lastGraded) {
    e.preventDefault();
    goBack();
  }
});

// ---------- search ----------
document.getElementById("search-btn").addEventListener("click", async () => {
  const q = document.getElementById("search-input").value.trim();
  if (!q) return;
  const resultsEl = document.getElementById("search-results");
  resultsEl.textContent = "Searching...";
  try {
    const results = await apiFetch(`${API}/search?q=${encodeURIComponent(q)}`);
    resultsEl.innerHTML = results
      .map(
        (r) => `<div class="result-item">
          <span class="score">${r.score.toFixed(3)}</span>
          <div class="jp-text">${renderJapanese(r.card)}</div>
          ${renderAudio(r.card.audio_path)}
          ${renderRevealBlock(r.card)}
        </div>`
      )
      .join("") || "<p>No results.</p>";
  } catch (err) {
    resultsEl.textContent = "AI unavailable — search requires the Cohere API.";
  }
});

// ---------- drill ----------
document.getElementById("drill-btn").addEventListener("click", async () => {
  const grammarPoint = document.getElementById("drill-grammar").value.trim();
  const resultsEl = document.getElementById("drill-results");
  resultsEl.textContent = "Generating...";
  try {
    const data = await apiFetch(`${API}/drill`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ grammar_point: grammarPoint, count: 3 }),
    });
    resultsEl.innerHTML = data.sentences
      .map(
        (s, i) => `<div class="result-item drill-item">
          <div class="drill-head">
            <span class="drill-number">${i + 1}</span>
            <div class="drill-english">${s.english}</div>
          </div>
          <div class="drill-body hidden">
            <div class="jp-text">${s.japanese}</div>
            <div class="reading-pill">${s.hiragana}</div>
            ${renderBreakdownTable(s.breakdown)}
          </div>
          <div class="drill-toggle-wrap">
            <button class="drill-toggle-btn pill-accent">Show Answer</button>
          </div>
        </div>`
      )
      .join("") || "<p>No drill sentences generated — try a different grammar point.</p>";
  } catch (err) {
    resultsEl.textContent = err.message || "AI unavailable — drill generation requires the Cohere API.";
  }
});

document.getElementById("drill-results").addEventListener("click", (e) => {
  if (!e.target.classList.contains("drill-toggle-btn")) return;
  const body = e.target.closest(".drill-item").querySelector(".drill-body");
  const nowHidden = body.classList.toggle("hidden");
  if (!nowHidden) playSwoosh();
  e.target.textContent = nowHidden ? "Show Answer" : "Minimize";
});

// ---------- confusions ----------
document.getElementById("confusions-btn").addEventListener("click", async () => {
  const resultsEl = document.getElementById("confusions-results");
  resultsEl.textContent = "Analyzing...";
  const pairs = await apiFetch(`${API}/confusions`);
  resultsEl.innerHTML = pairs
    .map(
      (p) => `<div class="result-item">
        <span class="score">sim ${p.similarity.toFixed(3)} · ${p.combined_lapses} lapses</span>
        <div class="jp-text">${renderJapanese(p.card_a)}</div>
        ${renderRevealBlock(p.card_a)}
        <div class="confusion-vs"><div class="line"></div><span>VS</span><div class="line"></div></div>
        <div class="jp-text">${renderJapanese(p.card_b)}</div>
        ${renderRevealBlock(p.card_b)}
      </div>`
    )
    .join("") || "<p>No confusions detected yet.</p>";
});

// ---------- recent ----------
const QUALITY_LABELS = { 0: "Very Hard", 2: "Hard", 3: "Medium", 4: "Easy", 5: "Very Easy" };

function relativeTime(isoString) {
  const graded = new Date(isoString + "Z"); // SQLite CURRENT_TIMESTAMP is UTC, no offset in the string
  const seconds = Math.max(0, Math.floor((Date.now() - graded.getTime()) / 1000));
  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

async function loadRecent() {
  const resultsEl = document.getElementById("recent-results");
  resultsEl.textContent = "Loading...";
  const entries = await apiFetch(`${API}/review/recent?limit=20`);
  resultsEl.innerHTML = entries
    .map(
      (entry) => `<div class="result-item">
        <span class="score quality-badge" data-q="${entry.quality}">${QUALITY_LABELS[entry.quality] || entry.quality} · ${relativeTime(entry.graded_at)}</span>
        <div class="jp-text">${renderJapanese(entry.card)}</div>
        ${renderAudio(entry.card.audio_path)}
        ${renderRevealBlock(entry.card)}
      </div>`
    )
    .join("") || "<p>No cards reviewed yet.</p>";
}

// ---------- kana chart ----------
// Gojūon layout: rows are consonant groups, columns the five vowels.
// Each cell is [hiragana, katakana, romaji]; null marks a historical gap.
const KANA_CHART = [
  [["あ", "ア", "a"], ["い", "イ", "i"], ["う", "ウ", "u"], ["え", "エ", "e"], ["お", "オ", "o"]],
  [["か", "カ", "ka"], ["き", "キ", "ki"], ["く", "ク", "ku"], ["け", "ケ", "ke"], ["こ", "コ", "ko"]],
  [["さ", "サ", "sa"], ["し", "シ", "shi"], ["す", "ス", "su"], ["せ", "セ", "se"], ["そ", "ソ", "so"]],
  [["た", "タ", "ta"], ["ち", "チ", "chi"], ["つ", "ツ", "tsu"], ["て", "テ", "te"], ["と", "ト", "to"]],
  [["な", "ナ", "na"], ["に", "ニ", "ni"], ["ぬ", "ヌ", "nu"], ["ね", "ネ", "ne"], ["の", "ノ", "no"]],
  [["は", "ハ", "ha"], ["ひ", "ヒ", "hi"], ["ふ", "フ", "fu"], ["へ", "ヘ", "he"], ["ほ", "ホ", "ho"]],
  [["ま", "マ", "ma"], ["み", "ミ", "mi"], ["む", "ム", "mu"], ["め", "メ", "me"], ["も", "モ", "mo"]],
  [["や", "ヤ", "ya"], null, ["ゆ", "ユ", "yu"], null, ["よ", "ヨ", "yo"]],
  [["ら", "ラ", "ra"], ["り", "リ", "ri"], ["る", "ル", "ru"], ["れ", "レ", "re"], ["ろ", "ロ", "ro"]],
  [["わ", "ワ", "wa"], null, null, null, ["を", "ヲ", "wo"]],
  [["ん", "ン", "n"], null, null, null, null],
];

function renderKanaChart(mode) {
  const idx = mode === "kata" ? 1 : 0;
  const filled = (r, c) =>
    r >= 0 && r < KANA_CHART.length && c >= 0 && c < 5 && KANA_CHART[r][c] !== null;

  // The empty slots are cut out of the chart's silhouette entirely, so each
  // cell only draws a border where a real neighbor exists, and corners get
  // beveled wherever the outline turns (no neighbor above AND to the side).
  document.getElementById("kana-chart").innerHTML = KANA_CHART.map((row, r) =>
    row
      .map((cell, c) => {
        if (!cell) return `<div class="kana-cell empty"></div>`;
        const cls = ["kana-cell"];
        if (filled(r, c + 1)) cls.push("b-r");
        if (filled(r + 1, c)) cls.push("b-b");
        if (!filled(r - 1, c) && !filled(r, c - 1)) cls.push("r-tl");
        if (!filled(r - 1, c) && !filled(r, c + 1)) cls.push("r-tr");
        if (!filled(r + 1, c) && !filled(r, c - 1)) cls.push("r-bl");
        if (!filled(r + 1, c) && !filled(r, c + 1)) cls.push("r-br");
        return `<div class="${cls.join(" ")}"><div class="kana">${cell[idx]}</div><div class="romaji">${cell[2]}</div></div>`;
      })
      .join("")
  ).join("");
}

document.querySelectorAll(".kana-toggle-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    if (btn.classList.contains("active")) return;
    document.querySelectorAll(".kana-toggle-btn").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    btn.closest(".kana-toggle").classList.toggle("kata", btn.dataset.kana === "kata");
    renderKanaChart(btn.dataset.kana);
  });
});

renderKanaChart("hira");

// ---------- import ----------
document.getElementById("import-btn").addEventListener("click", async () => {
  const fileInput = document.getElementById("import-file");
  if (!fileInput.files.length) return;
  const formData = new FormData();
  formData.append("file", fileInput.files[0]);
  const resultEl = document.getElementById("import-result");
  resultEl.textContent = "Importing...";
  try {
    const data = await apiFetch(`${API}/cards/import`, { method: "POST", body: formData });
    resultEl.textContent = `Imported ${data.imported}, skipped ${data.skipped_duplicates} duplicates (${data.embed_calls} embed calls).`;
    refreshStats();
    loadDue();
  } catch (err) {
    resultEl.textContent = `Import failed: ${err.message}`;
  }
});

document.getElementById("add-btn").addEventListener("click", async () => {
  const japanese = document.getElementById("add-japanese").value.trim();
  const english = document.getElementById("add-english").value.trim();
  const resultEl = document.getElementById("add-result");
  if (!japanese || !english) return;
  await apiFetch(`${API}/cards`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      japanese,
      english,
      reading: document.getElementById("add-reading").value.trim(),
      tags: document.getElementById("add-tags").value.trim(),
    }),
  });
  resultEl.textContent = `Added 「${japanese}」`;
  ["add-japanese", "add-reading", "add-english", "add-tags"].forEach(
    (id) => (document.getElementById(id).value = "")
  );
  refreshStats();
  loadDue();
});

// ---------- stats ----------
async function refreshStats() {
  try {
    const stats = await apiFetch(`${API}/api/stats`);
    document.getElementById("stats-line").textContent =
      `${stats.card_count} cards · ${stats.total_calls} Cohere calls logged`;
  } catch (err) {
    // stats are best-effort
  }
}

loadDue();
refreshStats();
