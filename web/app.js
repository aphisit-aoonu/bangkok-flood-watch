const TEXT = {
  th: {
    title: "เช็คสถานการณ์น้ำ",
    subtitle: "ระดับน้ำจริงจากสถานีวัด · กรุงเทพฯ และปริมณฑล · พร้อมคาดการณ์ล่วงหน้า 6 ชั่วโมง",
    updated: "อัปเดต",
    accTitle: "ทายแม่นแค่ไหน",
    accNote: "ทดสอบย้อนหลังกับข้อมูลจริงปี 2026 ที่ระบบไม่เคยเห็น (เลือกวิธีจากปี 2025) · ค่าคลาดเคลื่อนเฉลี่ย",
    accBase: "เดาว่าเท่าเดิม",
    accOurs: "พยากรณ์ของเรา",
    accLess: "แม่นขึ้น",
    listTitle: "สถานี",
    all: "ทั้งหมด",
    over: "ล้นตลิ่ง", near: "ใกล้ล้น", rising: "น้ำขึ้นเร็ว", normal: "ปกติ", stale: "ไม่มีข้อมูลล่าสุด",
    toBank: "ถึงตลิ่ง", overBy: "ล้นแล้ว", cm: "ซม.", cmh: "ซม./ชม.",
    level: "ระดับน้ำ", bank: "ตลิ่งต่ำสุด", trend: "แนวโน้ม", msl: "ม.รทก.",
    in1: "อีก 1 ชม.", in3: "อีก 3 ชม.", in6: "อีก 6 ชม.",
    past: "24 ชม. ที่ผ่านมา", forecast: "คาดการณ์", bankLine: "ระดับตลิ่ง",
    willOverflow: h => `คาดว่าน้ำจะถึงตลิ่งภายใน ${h} ชม. ถ้าแนวโน้มยังเป็นแบบนี้`,
    isOver: cm => `ตอนนี้น้ำสูงกว่าตลิ่ง ${cm} ซม.`,
    falling: "น้ำกำลังลด",
    source: "ข้อมูล: สถาบันสารสนเทศทรัพยากรน้ำ (สสน.) · ThaiWater",
    warning: "เป็นการประมาณ ห้ามใช้แทนประกาศของทางการ",
    reading: "วัดเมื่อ",
  },
  en: {
    title: "Bangkok Flood Watch",
    subtitle: "Live water levels from gauge stations · Bangkok & nearby · with a 6-hour forecast",
    updated: "Updated",
    accTitle: "How accurate is it?",
    accNote: "Tested on real 2026 data the model never saw (methods picked on 2025) · mean absolute error",
    accBase: "Assume no change",
    accOurs: "Our forecast",
    accLess: "less error",
    listTitle: "Stations",
    all: "All",
    over: "Over bank", near: "Near bank", rising: "Rising fast", normal: "Normal", stale: "No recent data",
    toBank: "to bank", overBy: "over", cm: "cm", cmh: "cm/h",
    level: "Water level", bank: "Lowest bank", trend: "Trend", msl: "m MSL",
    in1: "In 1 h", in3: "In 3 h", in6: "In 6 h",
    past: "Last 24 h", forecast: "Forecast", bankLine: "Bank level",
    willOverflow: h => `Likely to reach the bank within ${h} h if the trend holds`,
    isOver: cm => `Water is ${cm} cm above the bank right now`,
    falling: "Water is going down",
    source: "Data: Hydro-Informatics Institute (HII) · ThaiWater",
    warning: "Estimates only. Always follow official announcements.",
    reading: "Measured",
  },
};
const COLORS = { over: "--over", near: "--near", rising: "--rising", normal: "--normal", stale: "--stale" };
const ORDER = { over: 0, near: 1, rising: 2, normal: 3, stale: 4 };

let lang = "th";
try { lang = localStorage.getItem("floodwatch-lang") || "th"; } catch (e) {}
let data = null, accuracy = null, filter = "all", selected = null, map, markers = {};

const $ = id => document.getElementById(id);
const t = key => TEXT[lang][key];
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const color = s => css(COLORS[s.stale ? "stale" : s.status]);
const stateOf = s => (s.stale ? "stale" : s.status);
const name = s => (lang === "th" ? s.name_th || s.name_en : s.name_en || s.name_th);
const cm = m => Math.round(Math.abs(m) * 100);
const fmtTime = iso => {
  const d = new Date(iso);
  return d.toLocaleString(lang === "th" ? "th-TH" : "en-GB", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
};

function marginText(s) {
  if (s.margin == null) return "–";
  return s.margin < 0 ? `+${cm(s.margin)} ${t("cm")}` : `${cm(s.margin)} ${t("cm")}`;
}

function applyText() {
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-t]").forEach(el => (el.textContent = t(el.dataset.t)));
  $("lang").textContent = lang === "th" ? "EN" : "ไทย";
  if (data) $("updated").textContent = `${t("updated")} ${fmtTime(data.generated)}`;
}

function renderStats() {
  const live = data.stations.filter(s => !s.stale);
  $("stats").innerHTML = ["over", "near", "rising", "normal"].map(k => `
    <div class="stat ${filter === k ? "on" : ""}" data-f="${k}">
      <b style="color:${css(COLORS[k])}">${live.filter(s => s.status === k).length}</b>
      <span>${t(k)}</span>
    </div>`).join("");
  $("stats").querySelectorAll(".stat").forEach(el => (el.onclick = () => setFilter(filter === el.dataset.f ? "all" : el.dataset.f)));
}

function renderAccuracy() {
  if (!accuracy) { $("acc").closest("section").hidden = true; return; }
  const max = Math.max(...accuracy.rows.map(r => r.baseline_cm));
  $("acc").innerHTML = accuracy.rows.map(r => `
    <div class="acc-row">
      <span class="h">+${r.h}h</span>
      <div class="bars">
        <div class="bar base" style="width:${(r.baseline_cm / max) * 100}%" title="${r.baseline_cm} cm"></div>
        <div class="bar ours" style="width:${(r.ours_cm / max) * 100}%" title="${r.ours_cm} cm"></div>
      </div>
      <span class="gain">−${Math.round(r.better_pct)}%</span>
    </div>`).join("") + `
    <div class="acc-key">
      <span><i style="background:${css("--stale")};opacity:.55"></i>${t("accBase")} ${accuracy.rows.at(-1).baseline_cm} ${t("cm")}</span>
      <span><i style="background:${css("--accent")}"></i>${t("accOurs")} ${accuracy.rows.at(-1).ours_cm} ${t("cm")}</span>
    </div>`;
}

function renderFilters() {
  $("filters").innerHTML = ["all", "over", "near"].map(k =>
    `<button class="chip ${filter === k ? "on" : ""}" data-f="${k}" type="button">${t(k)}</button>`).join("");
  $("filters").querySelectorAll(".chip").forEach(el => (el.onclick = () => setFilter(el.dataset.f)));
}

function visible() {
  return data.stations
    .filter(s => filter === "all" || (!s.stale && s.status === filter))
    .sort((a, b) => ORDER[stateOf(a)] - ORDER[stateOf(b)] || (a.margin ?? 99) - (b.margin ?? 99));
}

function renderList() {
  $("list").innerHTML = visible().map(s => `
    <li class="item ${selected === s.id ? "sel" : ""}" data-id="${s.id}">
      <span class="dot" style="background:${color(s)}"></span>
      <div><div class="name">${name(s)}</div><div class="where">${s.province_en} · ${t(stateOf(s))}</div></div>
      <div class="val">${marginText(s)}<small>${s.margin != null && s.margin < 0 ? t("overBy") : t("toBank")}</small></div>
    </li>`).join("");
  $("list").querySelectorAll(".item").forEach(el => (el.onclick = () => select(+el.dataset.id, true)));
}

function renderMarkers() {
  Object.values(markers).forEach(m => m.remove());
  markers = {};
  const shown = new Set(visible().map(s => s.id));
  data.stations.forEach(s => {
    const on = shown.has(s.id);
    const m = L.circleMarker([s.lat, s.lon], {
      radius: s.id === selected ? 11 : stateOf(s) === "over" ? 8 : 7,
      color: "#fff", weight: 2, fillColor: color(s), fillOpacity: on ? 0.95 : 0.15, opacity: on ? 1 : 0.3,
    }).addTo(map);
    m.bindTooltip(`<b>${name(s)}</b><br>${t(stateOf(s))} · ${marginText(s)}`, { direction: "top", offset: [0, -6] });
    m.on("click", () => select(s.id, false));
    markers[s.id] = m;
  });
}

function renderLegend() {
  $("legend").innerHTML = ["over", "near", "rising", "normal", "stale"].map(k =>
    `<span><i class="dot" style="background:${css(COLORS[k])}"></i>${t(k)}</span>`).join("");
}

function chartSvg(s) {
  const W = 348, H = 170, P = { l: 34, r: 8, t: 10, b: 22 };
  const past = s.chart.map(([time, v]) => [new Date(time).getTime(), v]);
  const now = new Date(s.time).getTime();
  const fc = [[now, s.level], ...s.forecast.map(f => [now + f.h * 3600e3, f.level])];
  const all = [...past, ...fc].map(p => p[1]).concat(s.bank != null ? [s.bank] : []);
  let lo = Math.min(...all), hi = Math.max(...all);
  const pad = Math.max(0.1, (hi - lo) * 0.12); lo -= pad; hi += pad;
  const t0 = past.length ? past[0][0] : now - 24 * 3600e3, t1 = fc.at(-1)[0];
  const x = v => P.l + ((v - t0) / (t1 - t0)) * (W - P.l - P.r);
  const y = v => P.t + (1 - (v - lo) / (hi - lo)) * (H - P.t - P.b);
  const path = pts => pts.map((p, i) => `${i ? "L" : "M"}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join("");
  const ticks = [lo + pad, (lo + hi) / 2, hi - pad];
  const area = past.length ? `${path(past)}L${x(past.at(-1)[0])},${H - P.b}L${x(past[0][0])},${H - P.b}Z` : "";
  return `<svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${t("past")}">
    ${ticks.map(v => `<line class="grid" x1="${P.l}" x2="${W - P.r}" y1="${y(v)}" y2="${y(v)}"/><text x="${P.l - 5}" y="${y(v) + 3}" text-anchor="end">${v.toFixed(1)}</text>`).join("")}
    ${s.bank != null ? `<line class="bank" x1="${P.l}" x2="${W - P.r}" y1="${y(s.bank)}" y2="${y(s.bank)}"/>` : ""}
    <path class="area" d="${area}"/>
    <path class="past" d="${path(past)}"/>
    <line class="now" x1="${x(now)}" x2="${x(now)}" y1="${P.t}" y2="${H - P.b}"/>
    <path class="fc" d="${path(fc)}"/>
    ${fc.slice(1).map(p => `<circle class="fcdot" cx="${x(p[0])}" cy="${y(p[1])}" r="3.2"/>`).join("")}
    <text x="${P.l}" y="${H - 6}">−24h</text>
    <text x="${x(now)}" y="${H - 6}" text-anchor="middle">${lang === "th" ? "ตอนนี้" : "now"}</text>
    <text x="${W - P.r}" y="${H - 6}" text-anchor="end">+6h</text>
  </svg>`;
}

function renderDetail() {
  const box = $("detail");
  const s = data.stations.find(x => x.id === selected);
  if (!s) { box.hidden = true; return; }
  const st = stateOf(s);
  let callout = "";
  if (s.margin != null && s.margin < 0) callout = t("isOver")(cm(s.margin));
  else if (s.overflow_within_h) callout = t("willOverflow")(s.overflow_within_h);
  else if (s.slope_cm_h != null && s.slope_cm_h <= -3) callout = t("falling");
  const fc = h => s.forecast.find(f => f.h === h);
  const delta = h => { const d = Math.round((fc(h).level - s.level) * 100); return `${d > 0 ? "+" : ""}${d} ${t("cm")}`; };
  box.innerHTML = `
    <button class="close" type="button" aria-label="close">×</button>
    <div><span class="badge" style="background:${color(s)}">${t(st)}</span></div>
    <div class="d-title">${name(s)}<div class="muted">${s.province_en} · ${t("reading")} ${fmtTime(s.time)}</div></div>
    ${callout ? `<div class="callout" style="background:color-mix(in srgb, ${color(s)} 14%, transparent)">${callout}</div>` : ""}
    <div class="d-grid">
      <div><b>${s.level.toFixed(2)}</b><span>${t("level")} (${t("msl")})</span></div>
      <div><b>${marginText(s)}</b><span>${s.margin != null && s.margin < 0 ? t("overBy") : t("toBank")}</span></div>
      <div><b>${s.slope_cm_h == null ? "–" : (s.slope_cm_h > 0 ? "+" : "") + s.slope_cm_h}</b><span>${t("trend")} ${t("cmh")}</span></div>
      <div><b>${delta(1)}</b><span>${t("in1")}</span></div>
      <div><b>${delta(3)}</b><span>${t("in3")}</span></div>
      <div><b>${delta(6)}</b><span>${t("in6")}</span></div>
    </div>
    ${chartSvg(s)}
    <div class="chart-key"><span><i></i>${t("past")}</span><span><i class="d"></i>${t("forecast")}</span>${s.bank != null ? `<span><i class="b"></i>${t("bankLine")}</span>` : ""}</div>`;
  box.querySelector(".close").onclick = () => select(null);
  box.hidden = false;
}

function select(id, fly) {
  selected = id;
  renderList(); renderMarkers(); renderDetail();
  const s = data.stations.find(x => x.id === id);
  if (s && fly) map.flyTo([s.lat, s.lon], Math.max(map.getZoom(), 11), { duration: 0.6 });
}

function setFilter(f) {
  filter = f;
  renderStats(); renderFilters(); renderList(); renderMarkers();
}

function renderAll() {
  applyText(); renderStats(); renderAccuracy(); renderFilters(); renderList(); renderMarkers(); renderLegend(); renderDetail();
}

$("lang").onclick = () => {
  lang = lang === "th" ? "en" : "th";
  try { localStorage.setItem("floodwatch-lang", lang); } catch (e) {}
  renderAll();
};

async function init() {
  const theme = new URLSearchParams(location.search).get("theme");
  if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme;
  map = L.map("map", { zoomControl: true }).setView([13.95, 100.45], 9);
  L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 18,
  }).addTo(map);
  applyText();
  data = await (await fetch("data/stations.json")).json();
  try { accuracy = await (await fetch("data/accuracy.json")).json(); } catch (e) { accuracy = null; }
  const params = new URLSearchParams(location.search);
  if (params.get("station")) selected = +params.get("station");
  renderAll();
  map.fitBounds(L.latLngBounds(data.stations.map(s => [s.lat, s.lon])), { padding: [30, 30] });
}
init();
