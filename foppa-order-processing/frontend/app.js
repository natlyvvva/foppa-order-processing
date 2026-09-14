const form = document.querySelector("#extractForm");
const statusEl = document.querySelector("#status");
const summaryEl = document.querySelector("#summary");
const itemsEl = document.querySelector("#items");
const jsonEl = document.querySelector("#jsonOutput");
const feedbackButton = document.querySelector("#feedbackButton");
const sampleButton = document.querySelector("#sampleButton");
const clearButton = document.querySelector("#clearButton");
const thresholdSlider = document.querySelector("#thresholdSlider");
const thresholdValue = document.querySelector("#thresholdValue");

let lastResult = null;

const sampleText = `Mango puree 1
Sonnenblumenoel Big Chef 2
180er Eier L 4
morgen liefern`;

// ── Threshold slider: update badge in real time ──────────────────────────────
thresholdSlider.addEventListener("input", () => {
  thresholdValue.textContent = thresholdSlider.value;
});

function scoreClass(score) {
  if (score >= 85) return "good";
  if (score >= 65) return "warn";
  return "bad";
}

function renderResult(result) {
  lastResult = result;
  feedbackButton.disabled = false;

  const threshold = parseInt(thresholdSlider.value, 10);

  summaryEl.className = "summary";
  summaryEl.innerHTML = `
    <strong>${result.live_gemini ? "Live Gemini" : "Demo mode"}</strong>
    using <code>${result.model}</code><br>
    Customer: <strong>${result.customer_code}</strong><br>
    Delivery note: ${result.matched.delivery_note || "None"}<br>
    <span class="threshold-info">Threshold used: <strong>${threshold}</strong></span>
  `;

  const rows = result.matched.items
    .map((item) => {
      const selected = item.selected;
      const alternatives = item.alternatives.length
        ? item.alternatives.map((alt) => `${alt.code} (${alt.score})`).join(", ")
        : "None";

      // Highlight rows where score is below current threshold
      const belowThreshold = selected.score < threshold ? ' class="below-threshold"' : '';

      return `
        <tr${belowThreshold}>
          <td>${item.raw_text}</td>
          <td><strong>${selected.code}</strong><br>${selected.description}</td>
          <td>${item.requested_quantity ?? ""} ${item.requested_unit_hint ?? ""}</td>
          <td><span class="score ${scoreClass(selected.score)}">${selected.score}</span><br>${selected.stage}</td>
          <td class="alternatives">${alternatives}</td>
        </tr>
      `;
    })
    .join("");

  itemsEl.innerHTML = `
    <table class="item-table">
      <thead>
        <tr>
          <th>Raw item</th>
          <th>Selected article</th>
          <th>Qty</th>
          <th>Score</th>
          <th>Alternatives</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  `;

  jsonEl.textContent = JSON.stringify(result, null, 2);
}

async function loadHealth() {
  try {
    const response = await fetch("/api/health");
    const data = await response.json();
    statusEl.textContent = data.live_gemini
      ? `Live Gemini enabled: ${data.model}`
      : "Demo mode: set GEMINI_API_KEY for live extraction";
  } catch (error) {
    statusEl.textContent = "Backend is not reachable";
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  feedbackButton.disabled = true;
  summaryEl.className = "summary empty";
  summaryEl.textContent = "Extracting...";
  itemsEl.innerHTML = "";
  jsonEl.textContent = "{}";

  // FormData automatically includes the threshold field (name="threshold")
  const formData = new FormData(form);

  const response = await fetch("/api/extract", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const detail = await response.text();
    summaryEl.textContent = `Extraction failed: ${detail}`;
    return;
  }

  renderResult(await response.json());
});

feedbackButton.addEventListener("click", async () => {
  if (!lastResult) return;

  feedbackButton.disabled = true;
  const payload = {
    customer_code: lastResult.customer_code,
    finalized_order: lastResult.matched,
    reviewer_note: "Prototype review feedback",
  };

  const response = await fetch("/api/feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  feedbackButton.disabled = false;
  if (response.ok) {
    feedbackButton.textContent = "Feedback sent ✓";
    setTimeout(() => {
      feedbackButton.textContent = "Send feedback";
    }, 1600);
  }
});

sampleButton.addEventListener("click", () => {
  form.elements.text.value = sampleText;
});

clearButton.addEventListener("click", () => {
  form.reset();
  thresholdValue.textContent = "85";
  lastResult = null;
  feedbackButton.disabled = true;
  summaryEl.className = "summary empty";
  summaryEl.textContent = "No extraction yet.";
  itemsEl.innerHTML = "";
  jsonEl.textContent = "{}";
});

loadHealth();
