async function loadJSON(path) {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`Failed to load ${path}: ${res.status}`);
  return res.json();
}

function monthYear(isoDate) {
  return new Date(`${isoDate}T00:00:00Z`).toLocaleDateString("en-US", { month: "long", year: "numeric", timeZone: "UTC" });
}

function renderSubtitle(overall) {
  document.getElementById("subtitle").textContent =
    `Based on ${overall.n_total_cases.toLocaleString()} service requests opened ` +
    `${monthYear(overall.first_opened)} – ${monthYear(overall.last_opened)}.`;
}

function renderOverallStats(overall) {
  const el = document.getElementById("overall-stats");
  const stats = [
    { label: "Median resolution time", value: `${(overall.median_hours / 24).toFixed(1)} days` },
    { label: "Total cases", value: overall.n_total_cases.toLocaleString() },
    { label: "90th percentile", value: `${(overall.p90_hours / 24).toFixed(1)} days` },
    { label: "Still open", value: overall.n_open.toLocaleString() },
    {
      label: "Unknown location",
      value: overall.n_unknown_location.toLocaleString(),
      note: `${((overall.n_unknown_location / overall.n_total_cases) * 100).toFixed(1)}% of cases`,
    },
  ];
  el.innerHTML = stats
    .map(
      (s) =>
        `<div class="stat"><div class="value">${s.value}</div><div class="label">${s.label}</div>` +
        (s.note ? `<div class="note">${s.note}</div>` : "") +
        `</div>`
    )
    .join("");
}

// Neighborhoods with fewer closed cases than this get a dashed outline and a
// caution in the tooltip; their medians are noisy.
const LOW_VOLUME_N = 300;

// Light -> dark = faster -> slower.
const MAP_COLORS = ["#e3eee8", "#b5d3c1", "#7fb494", "#4b8f6b", "#25583d"];

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

// Upper-exclusive bin edges that split `values` into `bins` equal-sized groups.
function quantileEdges(values, bins) {
  const sorted = [...values].sort((a, b) => a - b);
  const edges = [];
  for (let i = 1; i < bins; i++) edges.push(sorted[Math.floor((sorted.length * i) / bins)]);
  return edges;
}

function binIndex(value, edges) {
  let i = 0;
  while (i < edges.length && value >= edges[i]) i++;
  return i;
}

function renderMapLegend(edges) {
  const fmt = (h) => h.toFixed(1);
  const labels = edges.map((e, i) => (i === 0 ? `under ${fmt(e)} h` : `${fmt(edges[i - 1])}–${fmt(e)} h`));
  labels.push(`${fmt(edges[edges.length - 1])} h and over`);
  const items = labels.map(
    (label, i) =>
      `<span class="legend-item"><span class="legend-swatch" style="background:${MAP_COLORS[i]}"></span>${label}</span>`
  );
  items.push(
    `<span class="legend-item"><span class="legend-swatch low-volume"></span>Fewer than ${LOW_VOLUME_N} closed cases</span>`
  );
  document.getElementById("map-legend").innerHTML = items.join("");
}

function renderNeighborhoodMap(geojson, byNeighborhood) {
  const stats = new Map(byNeighborhood.neighborhoods.map((n) => [n.neighborhood, n]));
  const edges = quantileEdges(
    byNeighborhood.neighborhoods.map((n) => n.median_hours),
    MAP_COLORS.length
  );

  // zoomSnap lets fitBounds pick a tighter zoom than whole levels would allow.
  const map = L.map("map", { scrollWheelZoom: false, zoomSnap: 0.25 });
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
    maxZoom: 18,
    className: "basemap-muted",
  }).addTo(map);

  const styleFor = (feature) => {
    const s = stats.get(feature.properties.name);
    return {
      fillColor: MAP_COLORS[binIndex(s.median_hours, edges)],
      fillOpacity: 0.85,
      color: s.n_closed < LOW_VOLUME_N ? "#6b6b6b" : "#ffffff",
      weight: s.n_closed < LOW_VOLUME_N ? 1.5 : 1,
      dashArray: s.n_closed < LOW_VOLUME_N ? "4 3" : null,
    };
  };

  const layer = L.geoJSON(geojson, {
    style: styleFor,
    onEachFeature: (feature, lyr) => {
      const s = stats.get(feature.properties.name);
      const lowVolume = s.n_closed < LOW_VOLUME_N;
      lyr.bindTooltip(
        `<div class="map-tooltip"><strong>${escapeHtml(s.neighborhood)}</strong>` +
          `Median: ${s.median_hours.toFixed(1)} h (${(s.median_hours / 24).toFixed(1)} days)<br>` +
          `90th percentile: ${(s.p90_hours / 24).toFixed(1)} days<br>` +
          `${s.n_cases.toLocaleString()} cases` +
          (lowVolume ? `<br><span class="low-volume-flag">Low volume — interpret with caution</span>` : "") +
          `</div>`,
        { sticky: true }
      );
      lyr.on({
        mouseover: () => lyr.setStyle({ weight: 3, color: "#1a1a1a" }),
        mouseout: () => layer.resetStyle(lyr),
      });
    },
  }).addTo(map);
  map.fitBounds(layer.getBounds());

  renderMapLegend(edges);

  const unknown = byNeighborhood["Unknown location"];
  const outside = byNeighborhood["Outside neighborhoods"];
  const total = byNeighborhood.neighborhoods.reduce((sum, n) => sum + n.n_cases, 0) + unknown.n_cases + outside.n_cases;
  document.getElementById("map-notes").innerHTML =
    `<strong>Not on the map:</strong> ${unknown.n_cases.toLocaleString()} cases ` +
    `(${((unknown.n_cases / total) * 100).toFixed(1)}%) have no location; their median is ` +
    `${unknown.median_hours.toFixed(1)} h. Another ${outside.n_cases.toLocaleString()} have coordinates ` +
    `that fall outside every neighborhood boundary.<br>` +
    `<strong>Read with care:</strong> a neighborhood's median reflects the mix of request types ` +
    `reported there, not only how quickly the city responds. Fast-closing types such as animal complaints ` +
    `can dominate a neighborhood's number.`;
}

async function main() {
  const [overall, byNeighborhood, boundaries] = await Promise.all([
    loadJSON("../data/processed/overall.json"),
    loadJSON("../data/processed/by_neighborhood.json"),
    loadJSON("../data/processed/neighborhoods.geojson"),
  ]);
  renderSubtitle(overall);
  renderOverallStats(overall);
  renderNeighborhoodMap(boundaries, byNeighborhood);
}

main().catch((err) => {
  console.error(err);
  document.body.insertAdjacentHTML(
    "beforeend",
    `<p style="color:red">Error loading data: ${err.message}. Serve the repo root (not web/, not file://) and open /web/ — see README.</p>`
  );
});
