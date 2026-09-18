async function loadJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`);
  return res.json();
}

function renderOverallStats(overall) {
  const el = document.getElementById("overall-stats");
  const stats = [
    { label: "Median resolution time", value: `${(overall.median_hours / 24).toFixed(1)} days` },
    { label: "Total cases", value: overall.n_total_cases.toLocaleString() },
    { label: "90th percentile", value: `${(overall.p90_hours / 24).toFixed(1)} days` },
    { label: "Still open", value: overall.n_open.toLocaleString() },
  ];
  el.innerHTML = stats
    .map(
      (s) => `<div class="stat"><div class="value">${s.value}</div><div class="label">${s.label}</div></div>`
    )
    .join("");
}

function renderTypeChart(byType) {
  // Show the 15 slowest-to-resolve types with a meaningful volume (n >= 50)
  // so rare, noisy categories don't dominate the chart.
  const filtered = byType.filter((d) => d.n >= 50).slice(0, 15);

  const ctx = document.getElementById("typeChart");
  new Chart(ctx, {
    type: "bar",
    data: {
      labels: filtered.map((d) => d.type),
      datasets: [
        {
          label: "Median resolution time (hours)",
          data: filtered.map((d) => d.median_hours),
          backgroundColor: "#2f6f4f",
        },
      ],
    },
    options: {
      indexAxis: "y",
      plugins: { legend: { display: false } },
      scales: {
        x: { title: { display: true, text: "Hours to resolve (median)" } },
      },
    },
  });
}

async function main() {
  const [overall, byType] = await Promise.all([
    loadJSON("../data/processed/overall.json"),
    loadJSON("../data/processed/by_type.json"),
  ]);
  renderOverallStats(overall);
  renderTypeChart(byType);
}

main().catch((err) => {
  console.error(err);
  document.body.insertAdjacentHTML(
    "beforeend",
    `<p style="color:red">Error loading data: ${err.message}. Are you running this from a local server (not file://)?</p>`
  );
});
