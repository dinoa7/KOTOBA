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
    await apiFetch(`${API}/review/grade`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ card_id: currentCard.id, quality: parseInt(btn.dataset.q, 10) }),
    });
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
      .join("");
  } catch (err) {
    resultsEl.textContent = "AI unavailable — drill generation requires the Cohere API.";
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
        <div>${p.card_b.japanese} <span class="english">(${p.card_b.english})</span></div>
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
