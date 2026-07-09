const API = "";

// ---------- tabs ----------
document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
  });
});

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
  return `<audio controls src="/audio/${encodeURIComponent(audioPath)}" style="display:block;margin:0.6rem auto;"></audio>`;
}

function escapeAttr(str) {
  return String(str).replace(/&/g, "&amp;").replace(/"/g, "&quot;");
}

let breakdownSlotCounter = 0;

function renderBreakdownButton(japanese) {
  const slotId = `bd-slot-${breakdownSlotCounter++}`;
  return `<button class="breakdown-btn" data-japanese="${escapeAttr(japanese)}" data-target="${slotId}">Break this down</button>
    <div id="${slotId}" class="breakdown-slot"></div>`;
}

document.addEventListener("click", async (e) => {
  if (!e.target.classList.contains("breakdown-btn")) return;
  const btn = e.target;
  const japanese = btn.dataset.japanese;
  const slot = document.getElementById(btn.dataset.target);
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
    .map(
      (t) => `<tr>
        <td>${t.token}</td><td>${t.reading}</td><td>${t.dictionary_form}</td>
        <td>${t.part_of_speech}</td><td>${t.meaning}</td><td>${t.grammar_note}</td>
      </tr>`
    )
    .join("");
  return `<table>
    <thead><tr><th>Token</th><th>Reading</th><th>Dict. form</th><th>POS</th><th>Meaning</th><th>Note</th></tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
}

// ---------- review ----------
let dueQueue = [];
let currentCard = null;

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
  nextCard();
}

function nextCard() {
  document.getElementById("rv-reveal").classList.add("hidden");
  document.getElementById("rv-grades").classList.add("hidden");
  document.getElementById("rv-show").classList.remove("hidden");
  document.getElementById("rv-breakdown-table").innerHTML = "";

  currentCard = dueQueue.shift() || null;
  const cardEl = document.getElementById("review-card");
  const emptyEl = document.getElementById("review-empty");

  if (!currentCard) {
    cardEl.classList.add("hidden");
    emptyEl.classList.remove("hidden");
    return;
  }
  emptyEl.classList.add("hidden");
  cardEl.classList.remove("hidden");
  document.getElementById("rv-japanese").textContent = currentCard.japanese;
  document.getElementById("rv-audio").innerHTML = renderAudio(currentCard.audio_path);
  document.getElementById("rv-reading").textContent = currentCard.reading || "";
  document.getElementById("rv-english").textContent = currentCard.english;
  const count = currentCard.review_count || 0;
  document.getElementById("rv-review-count").textContent =
    count === 0 ? "New card" : `Reviewed ${count} time${count === 1 ? "" : "s"}`;
}

document.getElementById("rv-show").addEventListener("click", () => {
  document.getElementById("rv-reveal").classList.remove("hidden");
  document.getElementById("rv-grades").classList.remove("hidden");
  document.getElementById("rv-show").classList.add("hidden");
});

document.getElementById("rv-breakdown-btn").addEventListener("click", async () => {
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

document.querySelectorAll(".grade-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const quality = parseInt(btn.dataset.q, 10);
    const gradedCard = currentCard;
    const result = await apiFetch(`${API}/review/grade`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ card_id: gradedCard.id, quality }),
    });

    gradedCard.review_count = result.review_count;
    const distance = computeRequeueDistance(quality, result.repetitions);
    const insertAt = Math.min(dueQueue.length, distance);
    dueQueue.splice(insertAt, 0, gradedCard);

    nextCard();
  });
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
          <div class="jp-text" style="font-size:1.2rem">${r.card.japanese}</div>
          ${renderAudio(r.card.audio_path)}
          <div class="english">${r.card.english}</div>
          ${renderBreakdownButton(r.card.japanese)}
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
        (s, i) => `<div class="result-item">
          <strong>${i + 1}. ${s.english}</strong>
          <details><summary>Reveal</summary>
            <div class="jp-text" style="font-size:1.2rem">${s.japanese}</div>
            <div class="reading">${s.hiragana}</div>
            ${renderBreakdownTable(s.breakdown)}
          </details>
        </div>`
      )
      .join("") || "<p>No drill sentences generated — try a different grammar point.</p>";
  } catch (err) {
    resultsEl.textContent = err.message || "AI unavailable — drill generation requires the Cohere API.";
  }
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
        <div>${p.card_a.japanese} <span class="english">(${p.card_a.english})</span></div>
        ${renderBreakdownButton(p.card_a.japanese)}
        <div>${p.card_b.japanese} <span class="english">(${p.card_b.english})</span></div>
        ${renderBreakdownButton(p.card_b.japanese)}
      </div>`
    )
    .join("") || "<p>No confusions detected yet.</p>";
});

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
  const payload = {
    japanese: document.getElementById("add-japanese").value.trim(),
    reading: document.getElementById("add-reading").value.trim(),
    english: document.getElementById("add-english").value.trim(),
    tags: document.getElementById("add-tags").value.trim(),
  };
  if (!payload.japanese || !payload.english) return;
  await apiFetch(`${API}/cards`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
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
