from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from farewatch.config import Settings, StayHorizon
from farewatch.db import connect

TEMPLATE = r"""<!DOCTYPE html>
<html lang="hu">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Farewatch — BUD–MAD</title>
  <style>
    :root {
      --bg: #0f1419; --card: #1a222c; --line: #2b3642; --text: #e8eef4;
      --muted: #93a4b5; --ok: #3dd68c; --partial: #f5c542; --err: #ff6b6b;
      --miss: #5c6b7a; --accent: #6cb6ff; --today: #ff8c42; --min: #3dd68c;
    }
    * { box-sizing: border-box; }
    body { margin: 0; font-family: "Segoe UI", system-ui, sans-serif; background: var(--bg); color: var(--text); line-height: 1.45; }
    main { max-width: 1100px; margin: 0 auto; padding: 28px 20px 64px; }
    h1 { font-size: 1.6rem; margin: 0 0 6px; display: flex; align-items: center; gap: 10px; }
    h1 svg { flex-shrink: 0; }
    h2 { font-size: 1.15rem; margin: 32px 0 12px; }
    h3 { font-size: 1rem; margin: 20px 0 10px; color: var(--muted); font-weight: 600; }
    .sub { color: var(--muted); margin-bottom: 24px; }
    .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }
    .card { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; }
    .card[title], .day[title] { cursor: help; }
    .card .label { color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: .04em; }
    .card .value { font-size: 1.45rem; font-weight: 650; margin-top: 4px; }
    .cal { display: flex; flex-wrap: wrap; gap: 6px; }
    .day { min-width: 58px; height: 44px; border-radius: 8px; padding: 0 6px; display: flex; align-items: center; justify-content: center; font-size: 0.78rem; color: #0b1014; font-weight: 650; font-variant-numeric: tabular-nums; }
    .day.ok { background: var(--ok); }
    .day.partial { background: var(--partial); }
    .day.error { background: var(--err); }
    .day.missing { background: var(--miss); color: #d7e0ea; }
    .legend { display: flex; gap: 14px; flex-wrap: wrap; color: var(--muted); font-size: 0.85rem; margin: 10px 0 16px; }
    .legend span { display: flex; align-items: center; gap: 6px; }
    .sw { width: 12px; height: 12px; border-radius: 3px; display: inline-block; flex-shrink: 0; }
    table { width: 100%; border-collapse: collapse; font-size: 0.92rem; }
    th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); }
    th { color: var(--muted); font-weight: 600; }
    .empty { color: var(--muted); }
    svg.chart { width: 100%; height: auto; aspect-ratio: 1000 / 280; background: var(--card); border: 1px solid var(--line); border-radius: 12px; display: block; }
    .hint { color: var(--muted); font-size: 0.85rem; }
    .about { margin: 0 0 22px; }
    .about p { margin: 0 0 10px; }
    .about p:last-child { margin-bottom: 0; }
    .schema { font-family: ui-monospace, Consolas, monospace; font-size: 0.82rem; overflow-x: auto; white-space: pre; color: #c5d4e0; }
  </style>
</head>
<body>
<main>
  <h1>
    <svg viewBox="0 0 24 24" width="32" height="32" aria-hidden="true">
      <path fill="#6cb6ff" d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z"/>
    </svg>
    BUD → MAD jegyárak
  </h1>
  <p class="sub">Utolsó frissítés: <span id="generated"></span></p>
  <div class="card about">
    <p>Hobbi archívum: a Google Flights-on <strong>nem lehet visszamenőleg</strong> megnézni, mennyibe került tegnap egy jegy, ezért minden nap lementjük a BUD→MAD közvetlen economy árakat.</p>
    <p><strong>Horizont</strong> = a gyűjtés napjától számított következő <span id="horizon-days">180</span> indulási nap, egyenként egy kereséssel (egyirányú, 1 felnőtt, HUF, basic). Nem „a 180 nap legolcsóbbja”, hanem 180 külön pillanatfelvétel.</p>
    <p><strong>Kitűzött út</strong> = mindig ugyanaz az oda-vissza csomag (2027. márc. 12. BUD→MAD + márc. 15. MAD→BUD). Az RT ár egy csomag, nem két egyirányú összege.</p>
    <p>Külön, délutáni futás: <strong>BUD→PDL</strong> 7 éjszakás oda-vissza (max 1 átszállás). A Madrid-gyűjtőtől független; a naptár minden napra mutatja, mennyit számít egy nap eltolás.</p>
  </div>
  <div class="kpis" id="kpis"></div>

  <h2>Gyűjtési napok</h2>
  <p class="hint">Egy doboz = egy naptári nap a gyűjtő futásával. Hover: keresések bontása.</p>
  <div class="legend">
    <span title="Az aznapi összes keresés sikerült vagy üres, hiba nélkül."><i class="sw" style="background:var(--ok)"></i>rendben</span>
    <span title="Ugyanazon a napon volt sikeres ÉS hibás keresés is."><i class="sw" style="background:var(--partial)"></i>részleges</span>
    <span title="Aznap nem volt sikeres keresés."><i class="sw" style="background:var(--err)"></i>hiba</span>
    <span title="Az első gyűjtés óta ez a nap kimaradt."><i class="sw" style="background:var(--miss)"></i>hiányzik</span>
  </div>
  <div class="cal" id="calendar"></div>

  <h2>Sikertelen keresések</h2>
  <div class="card" id="failures"></div>

  <h2>Kitűzött út — oda-vissza (RT), 2027. márc. 12–15.</h2>
  <svg id="pinned" class="chart" viewBox="0 0 1000 280" preserveAspectRatio="xMidYMid meet"></svg>
  <div class="legend" id="pinned-legend"></div>
  <p class="hint" id="pinned-caption"></p>
  <div class="card" id="pinned-flights"></div>

  <h2>Horizont — egyirányú (OW) napi minimum</h2>
  <svg id="horizon" class="chart" viewBox="0 0 1000 280" preserveAspectRatio="xMidYMid meet"></svg>
  <p class="hint">A vízszintes tengely a 180 napos horizont (indulásig hátralévő napok). Halvány kék: nyers min. Kék: 7 napos simított görbe. Zöld szaggatott: a horizont minimuma. Narancs pötty: a mai indulási nap (ha van adat).</p>

  <h2>Légitársaságok a horizonton</h2>
  <svg id="airlines" class="chart" viewBox="0 0 1000 280" preserveAspectRatio="xMidYMid meet"></svg>
  <div class="legend" id="airline-legend"></div>
  <div class="card" id="airline-wins"></div>

  <h2>Legolcsóbb közelgő járatok</h2>
  <div class="card" id="flights"></div>

  <section id="pdl-block">
  <h2>Azori — BUD → PDL, 7 éj, max 1 átszállás</h2>
  <p class="hint">Külön délutáni gyűjtés (15:00). Oda-vissza csomag, vissza = indulás + 7 nap. A MAD-gyűjtőtől független naptár és KPI.</p>
  <div class="kpis" id="pdl-kpis"></div>
  <h3>Gyűjtési napok (PDL)</h3>
  <div class="cal" id="pdl-calendar"></div>
  <h3>Sikertelen PDL keresések</h3>
  <div class="card" id="pdl-failures"></div>
  <h3>7 éj RT minimum indulási nap szerint</h3>
  <svg id="pdl-horizon" class="chart" viewBox="0 0 1000 280" preserveAspectRatio="xMidYMid meet"></svg>
  <h3>Légitársaságok (PDL)</h3>
  <svg id="pdl-airlines" class="chart" viewBox="0 0 1000 280" preserveAspectRatio="xMidYMid meet"></svg>
  <div class="legend" id="pdl-airline-legend"></div>
  <div class="card" id="pdl-airline-wins"></div>
  <h3>Legolcsóbb 7 éj csomagok</h3>
  <div class="card" id="pdl-flights"></div>
  </section>

  <h2>Adatszerkezet</h2>
  <div class="card">
    <p class="hint">A kanonikus tároló SQLite (<code>data/fares.sqlite3</code>), nem CSV: egy kereséshez több ajánlat tartozik, a hibás napok újrapróbálhatók, és belőle bármikor készül CSV. Export: <code>python -m farewatch analyze</code> → <code>data/reports/</code>.</p>
    <pre class="schema">snapshots     = egy keresés (dátum, OW/RT, status, forrás)
offers        = a keresés találatai (légitársaság, idő, ár)
collect_runs  = egy teljes gyűjtőfutás ideje (percben a KPI-n)
              1 snapshot → N offer</pre>
  </div>
</main>
<script type="application/json" id="payload">__PAYLOAD__</script>
<script>
const data = JSON.parse(document.getElementById("payload").textContent);
const $ = (id) => document.getElementById(id);
$("generated").textContent = data.generated_at || "—";
$("horizon-days").textContent = data.horizon_days || 180;
const COLORS = {"Wizz Air":"#c50e7a","Ryanair":"#f1c40f","Iberia":"#e74c3c","TAP Air Portugal":"#d0103a","TAP":"#d0103a","Azores Airlines":"#00a3e0","SATA":"#00a3e0"};
const HORIZON = data.horizon_days || 180;

function kpi(label, value, title) {
  const t = title ? ` title="${title.replaceAll('"','&quot;')}"` : "";
  return `<div class="card"${t}><div class="label">${label}</div><div class="value">${value}</div></div>`;
}
const last = data.last_run || {};
$("kpis").innerHTML = [
  kpi("Utolsó futás", last.collected_on || "nincs", last.run_hover || ""),
  kpi("Sikeres", last.ok ?? "—", last.ok_hover || ""),
  kpi("Hiba", last.error ?? "—", last.error_hover || ""),
  kpi("Üres / nincs járat", last.empty ?? "—", "A keresés lefutott, de azon a napon nincs közvetlen járat."),
  kpi("Kitűzött RT min", last.pinned_min != null ? Math.round(last.pinned_min).toLocaleString("hu-HU") + " Ft" : "—", last.pinned_hover || ""),
  kpi("Futási idő", last.duration_label || "—", last.duration_hover || "A teljes gyűjtés faliórája, percben."),
].join("");

$("calendar").innerHTML = (data.days || []).map(d =>
  `<div class="day ${d.kind}" title="${(d.hover||d.date).replaceAll('"','&quot;')}">${d.date.slice(5)}</div>`
).join("") || `<p class="empty">Még nincs gyűjtött nap.</p>`;

const fails = data.failures || [];
$("failures").innerHTML = fails.length
  ? `<table><thead><tr><th>Gyűjtés</th><th>Keresés</th><th>Hiba</th></tr></thead><tbody>${
      fails.map(f => `<tr><td>${f.collected_on}</td><td>${f.trip_type==="RT"?"oda-vissza (RT)":"egyirányú (OW)"} ${f.origin}–${f.dest} ${f.outbound_date}${f.return_date?" / "+f.return_date:""}</td><td>${f.error||"—"}</td></tr>`).join("")
    }</tbody></table>`
  : `<p class="empty">Nincs rögzített hiba.</p>`;

function yRange(ys) {
  const min = Math.min(...ys), max = Math.max(...ys);
  return { min, max, span: (max - min) || 1 };
}
function movingAvg(series, window=7) {
  return series.map((_, i) => {
    const a = Math.max(0, i - Math.floor(window/2));
    const b = Math.min(series.length, a + window);
    const slice = series.slice(a, b);
    return slice.reduce((s,p)=>s+p.y,0) / slice.length;
  });
}
function axisXDays(H, xOf, h, padB) {
  let ticks = "";
  for (let d = 0; d <= H; d += 30) {
    const x = xOf(d);
    ticks += `<line x1="${x.toFixed(1)}" x2="${x.toFixed(1)}" y1="${h-padB}" y2="${h-padB+6}" stroke="#5c6b7a"></line>
      <text x="${x.toFixed(1)}" y="${h-14}" text-anchor="middle" fill="#93a4b5" font-size="12">${d} nap</text>`;
  }
  return ticks + `<text x="500" y="${h-2}" text-anchor="middle" fill="#93a4b5" font-size="11">indulásig hátralévő napok (horizont: ${H} nap)</text>`;
}
function spark(id, series, yLabel) {
  const svg = $(id);
  if (!series.length) { svg.innerHTML = `<text x="20" y="140" fill="#93a4b5">Még nincs elég adat.</text>`; return; }
  const { min, max, span } = yRange(series.map(p => p.y));
  const w = 1000, h = 280, padL = 28, padR = 24, padT = 36, padB = 48;
  const pts = series.map((pt, i) => {
    const x = padL + (i / Math.max(series.length - 1, 1)) * (w - padL - padR);
    const y = h - padB - ((pt.y - min) / span) * (h - padT - padB);
    return { ...pt, px: x, py: y };
  });
  const raw = pts.map(p => `${p.px.toFixed(1)},${p.py.toFixed(1)}`).join(" ");
  const dots = pts.map(p =>
    `<circle cx="${p.px.toFixed(1)}" cy="${p.py.toFixed(1)}" r="5" fill="#6cb6ff"><title>${(p.label||"").replaceAll("<","")}</title></circle>`
  ).join("");
  svg.innerHTML = `<polyline fill="none" stroke="#6cb6ff" stroke-width="3" points="${raw}"></polyline>
    ${dots}
    <text x="20" y="22" fill="#93a4b5" font-size="14">${yLabel}: ${Math.round(min).toLocaleString("hu-HU")} – ${Math.round(max).toLocaleString("hu-HU")} Ft</text>`;
}
function sparkHorizon(id, series, yLabel, opts={}) {
  const svg = $(id);
  if (!series.length) { svg.innerHTML = `<text x="20" y="140" fill="#93a4b5">Még nincs elég adat.</text>`; return; }
  const { min, max, span } = yRange(series.map(p => p.y));
  const w = 1000, h = 280, padL = 36, padR = 28, padT = 36, padB = 48;
  const xOf = (days) => padL + (Math.max(0, Math.min(HORIZON, days)) / HORIZON) * (w - padL - padR);
  const yOf = (val) => h - padB - ((val - min) / span) * (h - padT - padB);
  const pts = series.map(pt => ({ ...pt, px: xOf(pt.days ?? 0), py: yOf(pt.y) }));
  const raw = pts.map(p => `${p.px.toFixed(1)},${p.py.toFixed(1)}`).join(" ");
  let extra = axisXDays(HORIZON, xOf, h, padB);
  extra += `<line x1="${padL}" x2="${w-padR}" y1="${h-padB}" y2="${h-padB}" stroke="#2b3642"></line>`;
  if (opts.smooth) {
    const avg = movingAvg(series, 7);
    const sm = pts.map((p,i) => `${p.px.toFixed(1)},${yOf(avg[i]).toFixed(1)}`).join(" ");
    extra += `<polyline fill="none" stroke="#6cb6ff" stroke-width="3" points="${sm}"></polyline>`;
  }
  if (opts.minLine) {
    const y = yOf(min);
    extra += `<line x1="${padL}" x2="${w-padR}" y1="${y}" y2="${y}" stroke="#3dd68c" stroke-dasharray="6 5" stroke-width="1.5"></line>
      <text x="${w-padR-8}" y="${y-6}" text-anchor="end" fill="#3dd68c" font-size="12">min ${Math.round(min).toLocaleString("hu-HU")} Ft</text>`;
  }
  const dots = pts.map(p => {
    const today = p.is_today;
    const isMin = p.is_min;
    const fill = today ? "#ff8c42" : (isMin ? "#3dd68c" : "#6cb6ff");
    const r = today || isMin ? 6.5 : 3.2;
    return `<circle cx="${p.px.toFixed(1)}" cy="${p.py.toFixed(1)}" r="${r}" fill="${fill}"><title>${(p.label||"").replaceAll("<","")}</title></circle>`;
  }).join("");
  const rawOp = opts.smooth ? "0.35" : "1";
  svg.innerHTML = `<polyline fill="none" stroke="#6cb6ff" stroke-width="2" stroke-opacity="${rawOp}" points="${raw}"></polyline>
    ${extra}${dots}
    <text x="20" y="22" fill="#93a4b5" font-size="14">${yLabel}: ${Math.round(min).toLocaleString("hu-HU")} – ${Math.round(max).toLocaleString("hu-HU")} Ft</text>`;
}
function sparkAirlinesByDate(id, seriesMap, yLabel) {
  const svg = $(id);
  const names = Object.keys(seriesMap || {});
  const dates = [...new Set(names.flatMap(n => (seriesMap[n] || []).map(p => p.x)))].sort();
  if (!names.length || !dates.length) {
    svg.innerHTML = `<text x="20" y="140" fill="#93a4b5">Még nincs elég adat.</text>`;
    return [];
  }
  const all = names.flatMap(n => seriesMap[n].map(p => p.y));
  const { min, max, span } = yRange(all);
  const w = 1000, h = 280, padL = 36, padR = 28, padT = 36, padB = 48;
  const xOf = (day) => padL + (dates.indexOf(day) / Math.max(dates.length - 1, 1)) * (w - padL - padR);
  const yOf = (val) => h - padB - ((val - min) / span) * (h - padT - padB);
  let ticks = "";
  dates.forEach((day) => {
    const x = xOf(day);
    ticks += `<line x1="${x.toFixed(1)}" x2="${x.toFixed(1)}" y1="${h-padB}" y2="${h-padB+6}" stroke="#5c6b7a"></line>
      <text x="${x.toFixed(1)}" y="${h-14}" text-anchor="middle" fill="#93a4b5" font-size="12">${day.slice(5)}</text>`;
  });
  let svgHtml = `<text x="20" y="22" fill="#93a4b5" font-size="14">${yLabel}: ${Math.round(min).toLocaleString("hu-HU")} – ${Math.round(max).toLocaleString("hu-HU")} Ft</text>
    <line x1="${padL}" x2="${w-padR}" y1="${h-padB}" y2="${h-padB}" stroke="#2b3642"></line>${ticks}`;
  names.forEach(n => {
    const col = COLORS[n] || "#6cb6ff";
    const pts = seriesMap[n].map(p => `${xOf(p.x).toFixed(1)},${yOf(p.y).toFixed(1)}`).join(" ");
    svgHtml += `<polyline fill="none" stroke="${col}" stroke-width="2.6" points="${pts}"></polyline>`;
    seriesMap[n].forEach(p => {
      svgHtml += `<circle cx="${xOf(p.x).toFixed(1)}" cy="${yOf(p.y).toFixed(1)}" r="4.5" fill="${col}"><title>${(p.label||"").replaceAll("<","")}</title></circle>`;
    });
  });
  svg.innerHTML = svgHtml;
  return names;
}
const pinnedAir = data.pinned_airline_series || {};
const pinnedMap = Object.keys(pinnedAir).length
  ? pinnedAir
  : ((data.pinned_series || []).length ? {"Minimum": data.pinned_series} : {});
const pinnedNames = sparkAirlinesByDate("pinned", pinnedMap, "Oda-vissza (RT) csomagár légitársaságonként");
$("pinned-legend").innerHTML = pinnedNames.map(n =>
  `<span><i class="sw" style="background:${COLORS[n]||"#6cb6ff"}"></i>${n}</span>`
).join("");
$("pinned-caption").textContent = pinnedNames.length
  ? "RT = round-trip csomagár (2027-03-12 BUD→MAD + 03-15 MAD→BUD), légitársaságonként a napi minimum. A vízszintes tengely a gyűjtés napja."
  : "";
const pinnedFlights = data.pinned_flights || [];
$("pinned-flights").innerHTML = pinnedFlights.length
  ? `<table><thead><tr><th>Légitársaság</th><th>RT csomag</th><th>Oda (márc. 12.)</th><th>Vissza (márc. 15.)</th></tr></thead><tbody>${
      pinnedFlights.map(f => `<tr><td>${f.airline}${f.code?" ("+f.code+")":""}</td><td>${f.price}</td><td>${f.outbound}</td><td>${f.inbound}</td></tr>`).join("")
    }</tbody></table>`
  : `<p class="empty">Még nincs járatinfo a kitűzött úthoz.</p>`;
sparkHorizon("horizon", data.horizon_series || [], "Egyirányú (OW) min", { smooth: true, minLine: true });

const air = data.airline_series || {};
const names = Object.keys(air);
if (names.length) {
  const all = names.flatMap(n => air[n].map(p => p.y));
  const { min, max, span } = yRange(all);
  const w = 1000, h = 280, padL = 36, padR = 28, padT = 36, padB = 48;
  const xOf = (days) => padL + (Math.max(0, Math.min(HORIZON, days)) / HORIZON) * (w - padL - padR);
  const yOf = (val) => h - padB - ((val-min)/span)*(h-padT-padB);
  let svg = `<text x="20" y="22" fill="#93a4b5" font-size="14">Légitársaságonkénti napi minimum a 180 napos horizonton</text>`;
  svg += `<line x1="${padL}" x2="${w-padR}" y1="${h-padB}" y2="${h-padB}" stroke="#2b3642"></line>`;
  svg += axisXDays(HORIZON, xOf, h, padB);
  names.forEach(n => {
    const series = air[n];
    if (!series.length) return;
    const col = COLORS[n] || "#6cb6ff";
    const pts = series.map(p => `${xOf(p.days ?? 0).toFixed(1)},${yOf(p.y).toFixed(1)}`).join(" ");
    svg += `<polyline fill="none" stroke="${col}" stroke-width="2.4" points="${pts}"></polyline>`;
  });
  $("airlines").innerHTML = svg;
  $("airline-legend").innerHTML = names.map(n =>
    `<span><i class="sw" style="background:${COLORS[n]||"#6cb6ff"}"></i>${n}</span>`
  ).join("");
} else {
  $("airlines").innerHTML = `<text x="20" y="140" fill="#93a4b5">Még nincs légitársaság-adat.</text>`;
}

const wins = data.airline_wins || [];
$("airline-wins").innerHTML = wins.length
  ? `<table><thead><tr><th>Légitársaság</th><th>Hányszor a legolcsóbb</th><th>Arány</th><th>Saját medián</th></tr></thead><tbody>${
      wins.map(w => `<tr><td>${w.airline}</td><td>${w.wins}</td><td>${w.share}</td><td>${w.median}</td></tr>`).join("")
    }</tbody></table>`
  : `<p class="empty">Nincs elég adat a légitársaság-összehasonlításhoz.</p>`;

const flights = data.cheapest_flights || [];
$("flights").innerHTML = flights.length
  ? `<table><thead><tr><th>Indulás</th><th>Nap múlva</th><th>Légitársaság</th><th>Járat / idő</th><th>Időtartam</th><th>Ár</th></tr></thead><tbody>${
      flights.map(f => `<tr><td>${f.date}</td><td>${f.days}</td><td>${f.airline}${f.code?" ("+f.code+")":""}</td><td>${f.flight}</td><td>${f.duration}</td><td>${f.price}</td></tr>`).join("")
    }</tbody></table>`
  : `<p class="empty">Nincs járatlista.</p>`;

const pdl = data.pdl;
if (!pdl) {
  $("pdl-block").style.display = "none";
} else {
  const pLast = pdl.last_run || {};
  $("pdl-kpis").innerHTML = [
    kpi("Utolsó PDL futás", pLast.collected_on || "nincs", pLast.run_hover || ""),
    kpi("Sikeres", pLast.ok ?? "—", pLast.ok_hover || ""),
    kpi("Hiba", pLast.error ?? "—", pLast.error_hover || ""),
    kpi("PDL 7 éj min", pLast.min_price != null ? Math.round(pLast.min_price).toLocaleString("hu-HU") + " Ft" : "—", pLast.min_hover || ""),
    kpi("Futási idő", pLast.duration_label || "—", pLast.duration_hover || ""),
  ].join("");
  $("pdl-calendar").innerHTML = (pdl.days || []).map(d =>
    `<div class="day ${d.kind}" title="${(d.hover||d.date).replaceAll('"','&quot;')}">${d.date.slice(5)}</div>`
  ).join("") || `<p class="empty">Még nincs PDL gyűjtött nap.</p>`;
  const pFails = pdl.failures || [];
  $("pdl-failures").innerHTML = pFails.length
    ? `<table><thead><tr><th>Gyűjtés</th><th>Keresés</th><th>Hiba</th></tr></thead><tbody>${
        pFails.map(f => `<tr><td>${f.collected_on}</td><td>${f.origin}–${f.dest} ${f.outbound_date}${f.return_date?" / "+f.return_date:""}</td><td>${f.error||"—"}</td></tr>`).join("")
      }</tbody></table>`
    : `<p class="empty">Nincs rögzített PDL hiba.</p>`;
  sparkHorizon("pdl-horizon", pdl.horizon_series || [], "7 éj RT min", { smooth: true, minLine: true });
  const pAir = pdl.airline_series || {};
  const pNames = Object.keys(pAir);
  if (pNames.length) {
    const all = pNames.flatMap(n => pAir[n].map(p => p.y));
    const { min, max, span } = yRange(all);
    const w = 1000, h = 280, padL = 36, padR = 28, padT = 36, padB = 48;
    const xOf = (days) => padL + (Math.max(0, Math.min(HORIZON, days)) / HORIZON) * (w - padL - padR);
    const yOf = (val) => h - padB - ((val-min)/span)*(h-padT-padB);
    let svg = `<text x="20" y="22" fill="#93a4b5" font-size="14">Légitársaságonkénti 7 éj RT minimum</text>`;
    svg += `<line x1="${padL}" x2="${w-padR}" y1="${h-padB}" y2="${h-padB}" stroke="#2b3642"></line>`;
    svg += axisXDays(HORIZON, xOf, h, padB);
    pNames.forEach(n => {
      const series = pAir[n];
      if (!series.length) return;
      const col = COLORS[n] || "#6cb6ff";
      const pts = series.map(p => `${xOf(p.days ?? 0).toFixed(1)},${yOf(p.y).toFixed(1)}`).join(" ");
      svg += `<polyline fill="none" stroke="${col}" stroke-width="2.4" points="${pts}"></polyline>`;
    });
    $("pdl-airlines").innerHTML = svg;
    $("pdl-airline-legend").innerHTML = pNames.map(n =>
      `<span><i class="sw" style="background:${COLORS[n]||"#6cb6ff"}"></i>${n}</span>`
    ).join("");
  } else {
    $("pdl-airlines").innerHTML = `<text x="20" y="140" fill="#93a4b5">Még nincs PDL légitársaság-adat.</text>`;
  }
  const pWins = pdl.airline_wins || [];
  $("pdl-airline-wins").innerHTML = pWins.length
    ? `<table><thead><tr><th>Légitársaság</th><th>Hányszor a legolcsóbb</th><th>Arány</th><th>Saját medián</th></tr></thead><tbody>${
        pWins.map(w => `<tr><td>${w.airline}</td><td>${w.wins}</td><td>${w.share}</td><td>${w.median}</td></tr>`).join("")
      }</tbody></table>`
    : `<p class="empty">Nincs elég PDL adat.</p>`;
  const pFlights = pdl.cheapest_flights || [];
  $("pdl-flights").innerHTML = pFlights.length
    ? `<table><thead><tr><th>Indulás</th><th>Vissza</th><th>Nap múlva</th><th>Légitársaság</th><th>Járat</th><th>Átszállás</th><th>Időtartam</th><th>Ár</th></tr></thead><tbody>${
        pFlights.map(f => `<tr><td>${f.date}</td><td>${f.return_date||""}</td><td>${f.days}</td><td>${f.airline}${f.code?" ("+f.code+")":""}</td><td>${f.flight}</td><td>${f.stops}</td><td>${f.duration}</td><td>${f.price}</td></tr>`).join("")
      }</tbody></table>`
    : `<p class="empty">Nincs PDL járatlista.</p>`;
}
</script>
</body>
</html>
"""


def _kind(ok: int, error: int, empty: int) -> str:
    if error and ok:
        return "partial"
    if error:
        return "error"
    if ok or empty:
        return "ok"
    return "missing"


def _job_label(row: Any) -> str:
    trip = "oda-vissza (RT)" if row["trip_type"] == "RT" else "egyirányú (OW)"
    ret = f" / {row['return_date']}" if row["return_date"] else ""
    return f"{trip} {row['origin']}–{row['dest']} {row['outbound_date']}{ret}"


def _ft(amount: float) -> str:
    return f"{amount:,.0f} Ft".replace(",", " ")


def _hhmm(value: str | None) -> str:
    if not value or "T" not in value:
        return "—"
    return value.split("T", 1)[1][:5]


def _flight_label(value: str | None) -> str:
    if not value:
        return "—"
    if any(char.isdigit() for char in value) and any(char.isalpha() for char in value):
        return value
    return "—"


def _leg_label(flight: str | None, departure: str | None, arrival: str | None) -> str:
    number = _flight_label(flight)
    times = f"{_hhmm(departure)}–{_hhmm(arrival)}"
    if number == "—" and times == "—–—":
        return "—"
    if number == "—":
        return f"hivatalos idő {times}"
    return f"{number} · {times}"


def _best_ow_leg(
    conn,
    *,
    collected_on: str,
    source: str,
    airline: str,
    origin: str,
    dest: str,
    outbound_date: str,
) -> Any:
    return conn.execute(
        """
        SELECT o.outbound_flights, o.departure_at, o.arrival_at
        FROM snapshots s
        JOIN offers o ON o.snapshot_id = s.id
        WHERE s.trip_type = 'OW'
          AND s.origin = ?
          AND s.dest = ?
          AND s.outbound_date = ?
          AND s.collected_on = ?
          AND s.source = ?
          AND s.status = 'ok'
          AND o.airline = ?
        ORDER BY o.price_amount
        LIMIT 1
        """,
        (origin, dest, outbound_date, collected_on, source, airline),
    ).fetchone()


def _duration(minutes: int | None) -> str:
    if not minutes:
        return "—"
    hours, mins = divmod(int(minutes), 60)
    return f"{hours}ó {mins:02d}p"


def _minutes_label(seconds: float) -> str:
    minutes = seconds / 60
    if minutes < 0.05:
        return "0 perc"
    rounded = round(minutes, 1)
    if abs(rounded - round(rounded)) < 1e-6:
        return f"{int(round(rounded))} perc"
    return f"{rounded:.1f}".replace(".", ",") + " perc"


def _parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _duration_for_day(
    conn,
    collected_on: str,
    source: str,
    *,
    scope: str = "mad",
    origin: str | None = None,
    dest: str | None = None,
    include_reverse: bool = False,
) -> dict[str, Any]:
    retry_note = (
        "A 17:00-es újrapróba külön, rövidebb futás."
        if scope == "stay"
        else "A 12:00-es újrapróba külön, rövidebb futás."
    )
    row = conn.execute(
        """
        SELECT duration_seconds, planned, skipped, ok, empty, error,
               started_at, finished_at
        FROM collect_runs
        WHERE collected_on = ? AND source = ? AND IFNULL(scope, 'mad') = ?
        ORDER BY (ok + empty + error) DESC, duration_seconds DESC
        LIMIT 1
        """,
        (collected_on, source, scope),
    ).fetchone()
    if row and row["duration_seconds"] is not None:
        seconds = float(row["duration_seconds"])
        return {
            "duration_minutes": round(seconds / 60, 1),
            "duration_label": _minutes_label(seconds),
            "duration_hover": (
                f"Teljes gyűjtés faliórája: {_minutes_label(seconds)} "
                f"({row['started_at']} → {row['finished_at']}). "
                f"Keresés: {row['ok']} ok, {row['error']} hiba, "
                f"{row['empty']} üres, {row['skipped']} kihagyva. "
                f"{retry_note}"
            ),
        }
    route_sql = ""
    route_params: list[Any] = [collected_on, source]
    if origin and dest:
        if include_reverse:
            route_sql = " AND ((origin = ? AND dest = ?) OR (origin = ? AND dest = ?))"
            route_params.extend([origin, dest, dest, origin])
        else:
            route_sql = " AND origin = ? AND dest = ?"
            route_params.extend([origin, dest])
    span = conn.execute(
        f"""
        SELECT MIN(collected_at) AS first_at, MAX(collected_at) AS last_at
        FROM snapshots
        WHERE collected_on = ? AND source = ?{route_sql}
        """,
        route_params,
    ).fetchone()
    start = _parse_iso(span["first_at"]) if span and span["first_at"] else None
    end = _parse_iso(span["last_at"]) if span and span["last_at"] else None
    if start and end:
        seconds = max((end - start).total_seconds(), 0.0)
        return {
            "duration_minutes": round(seconds / 60, 1),
            "duration_label": _minutes_label(seconds),
            "duration_hover": (
                f"Becsült idő az első és utolsó keresés között: "
                f"{_minutes_label(seconds)}. A pontos mérés a következő "
                "teljes gyűjtéstől lesz a collect_runs táblában."
            ),
        }
    return {
        "duration_minutes": None,
        "duration_label": "—",
        "duration_hover": "Még nincs mért futási idő.",
    }


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    mid = len(ordered) // 2
    if not ordered:
        return 0.0
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _resolve_source(conn, settings: Settings) -> str:
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM snapshots WHERE source = ?",
        (settings.source,),
    ).fetchone()["n"]
    if n:
        return settings.source
    row = conn.execute(
        "SELECT source FROM snapshots ORDER BY collected_at DESC LIMIT 1"
    ).fetchone()
    return str(row["source"]) if row else settings.source


def _pdl_payload(
    conn,
    settings: Settings,
    source: str,
    today: date,
    horizon: StayHorizon,
) -> dict[str, Any]:
    origin, dest = horizon.origin, horizon.dest
    day_rows = conn.execute(
        """
        SELECT collected_on,
               SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) AS ok,
               SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error,
               SUM(CASE WHEN status = 'empty' THEN 1 ELSE 0 END) AS empty
        FROM snapshots
        WHERE source = ?
          AND origin = ?
          AND dest = ?
          AND trip_type = 'RT'
        GROUP BY collected_on
        ORDER BY collected_on
        """,
        (source, origin, dest),
    ).fetchall()
    by_day = {
        row["collected_on"]: {
            "ok": int(row["ok"] or 0),
            "error": int(row["error"] or 0),
            "empty": int(row["empty"] or 0),
        }
        for row in day_rows
    }
    days: list[dict[str, Any]] = []
    if by_day:
        cursor = date.fromisoformat(min(by_day))
        while cursor <= today:
            key = cursor.isoformat()
            stats = by_day.get(key, {"ok": 0, "error": 0, "empty": 0})
            kind = _kind(stats["ok"], stats["error"], stats["empty"]) if key in by_day else "missing"
            kind_hu = {
                "ok": "rendben",
                "partial": "részleges: volt siker és hiba is",
                "error": "hiba: aznap nem volt sikeres keresés",
                "missing": "hiányzik: nem futott a gyűjtő",
            }[kind]
            hover = (
                f"{key} — {kind_hu}. "
                f"Sikeres: {stats['ok']}, hiba: {stats['error']}, üres: {stats['empty']}."
            )
            days.append({"date": key, "kind": kind, "hover": hover, **stats})
            cursor += timedelta(days=1)

    last_date = max(by_day) if by_day else None
    last_run: dict[str, Any] = {
        "collected_on": last_date,
        "ok": 0,
        "error": 0,
        "empty": 0,
        "min_price": None,
        "duration_label": "—",
        "duration_hover": "Még nincs mért PDL futás.",
        "ok_hover": "",
        "error_hover": "",
        "run_hover": "",
        "min_hover": "A 7 éjszakás BUD–PDL csomag legolcsóbb ára az utolsó Azori gyűjtésből.",
    }
    if last_date:
        last_run.update(by_day[last_date])
        last_run.update(
            _duration_for_day(
                conn,
                last_date,
                source,
                scope="stay",
                origin=origin,
                dest=dest,
            )
        )
        last_run["run_hover"] = f"PDL gyűjtés napja: {last_date}, forrás: {source}."
        cheapest = conn.execute(
            """
            SELECT MIN(o.price_amount) AS min_price
            FROM snapshots s
            JOIN offers o ON o.snapshot_id = s.id
            WHERE s.trip_type = 'RT'
              AND s.origin = ?
              AND s.dest = ?
              AND s.collected_on = ?
              AND s.source = ?
              AND s.status = 'ok'
            """,
            (origin, dest, last_date, source),
        ).fetchone()
        last_run["min_price"] = cheapest["min_price"] if cheapest else None
        if last_run["min_price"] is not None:
            last_run["min_hover"] = (
                f"A {last_date}-i PDL gyűjtésből: {horizon.stay_nights} éj "
                f"{origin}→{dest} csomag minimuma ({source})."
            )
        last_run["ok_hover"] = f"{last_run['ok']} sikeres PDL keresés."
        last_run["error_hover"] = f"{last_run['error']} hibás PDL keresés."

    failures = [
        dict(row)
        for row in conn.execute(
            """
            SELECT collected_on, trip_type, origin, dest, outbound_date, return_date, error
            FROM snapshots
            WHERE status = 'error' AND source = ?
              AND origin = ? AND dest = ?
            ORDER BY collected_on DESC, outbound_date
            LIMIT 40
            """,
            (source, origin, dest),
        )
    ]

    horizon_series: list[dict[str, Any]] = []
    airline_series: dict[str, list[dict[str, Any]]] = {}
    airline_wins: list[dict[str, Any]] = []
    cheapest_flights: list[dict[str, Any]] = []
    if last_date:
        collected = date.fromisoformat(last_date)
        offer_rows = conn.execute(
            """
            SELECT s.outbound_date, s.return_date, o.airline, o.airline_code,
                   o.departure_at, o.arrival_at, o.price_amount, o.duration_minutes,
                   o.outbound_flights, o.stops
            FROM snapshots s
            JOIN offers o ON o.snapshot_id = s.id
            WHERE s.trip_type = 'RT'
              AND s.origin = ?
              AND s.dest = ?
              AND s.status = 'ok'
              AND s.collected_on = ?
              AND s.source = ?
            ORDER BY s.outbound_date, o.price_amount
            """,
            (origin, dest, last_date, source),
        ).fetchall()
        by_date: dict[str, list[Any]] = {}
        by_airline: dict[str, dict[str, float]] = {}
        for row in offer_rows:
            by_date.setdefault(row["outbound_date"], []).append(row)
            name = row["airline"] or "ismeretlen"
            prices = by_airline.setdefault(name, {})
            key = row["outbound_date"]
            amount = float(row["price_amount"])
            prices[key] = amount if key not in prices else min(prices[key], amount)

        min_price = None
        for outbound, rows in by_date.items():
            best = rows[0]
            price = float(best["price_amount"])
            if min_price is None or price < min_price:
                min_price = price
            days_left = (date.fromisoformat(outbound) - collected).days
            horizon_series.append(
                {
                    "x": outbound,
                    "y": price,
                    "days": days_left,
                    "is_today": outbound == today.isoformat(),
                    "is_min": False,
                    "airline": best["airline"],
                    "label": (
                        f"{outbound} / {best['return_date']} · {days_left} nap múlva · "
                        f"{_ft(price)} · {best['airline'] or ''} "
                        f"{_hhmm(best['departure_at'])} · {best['stops']} átszállás"
                    ),
                }
            )
        if min_price is not None:
            for point in horizon_series:
                point["is_min"] = abs(point["y"] - min_price) < 0.5

        for name, prices in sorted(by_airline.items()):
            airline_series[name] = [
                {
                    "x": day,
                    "y": amount,
                    "days": (date.fromisoformat(day) - collected).days,
                    "label": f"{name} · {day} · {_ft(amount)}",
                }
                for day, amount in sorted(prices.items())
            ]

        wins: dict[str, int] = {}
        all_prices: dict[str, list[float]] = {}
        for rows in by_date.values():
            winner = rows[0]["airline"] or "ismeretlen"
            wins[winner] = wins.get(winner, 0) + 1
        for name, prices in by_airline.items():
            all_prices[name] = list(prices.values())
        total_days = sum(wins.values()) or 1
        airline_wins = [
            {
                "airline": name,
                "wins": count,
                "share": f"{100 * count / total_days:.0f}%",
                "median": _ft(_median(all_prices.get(name, []))),
            }
            for name, count in sorted(wins.items(), key=lambda item: -item[1])
        ]

        ranked = []
        for outbound, rows in by_date.items():
            best = rows[0]
            ranked.append((float(best["price_amount"]), outbound, best))
        ranked.sort(key=lambda item: (item[0], item[1]))
        for price, outbound, best in ranked[:12]:
            days_left = (date.fromisoformat(outbound) - collected).days
            cheapest_flights.append(
                {
                    "date": outbound,
                    "return_date": best["return_date"] or "",
                    "days": days_left,
                    "airline": best["airline"] or "—",
                    "code": best["airline_code"] or "",
                    "flight": _leg_label(
                        best["outbound_flights"],
                        best["departure_at"],
                        best["arrival_at"],
                    ),
                    "stops": int(best["stops"] or 0),
                    "duration": _duration(best["duration_minutes"]),
                    "price": _ft(price),
                }
            )

    return {
        "origin": origin,
        "dest": dest,
        "stay_nights": horizon.stay_nights,
        "max_stops": horizon.max_stops,
        "horizon_days": horizon.horizon_days,
        "last_run": last_run,
        "days": days,
        "failures": failures,
        "horizon_series": horizon_series,
        "airline_series": airline_series,
        "airline_wins": airline_wins,
        "cheapest_flights": cheapest_flights,
    }


def build_payload(conn, settings: Settings, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    generated = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    source = _resolve_source(conn, settings)
    day_rows = conn.execute(
        """
        SELECT collected_on,
               SUM(CASE WHEN status = 'ok' THEN 1 ELSE 0 END) AS ok,
               SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) AS error,
               SUM(CASE WHEN status = 'empty' THEN 1 ELSE 0 END) AS empty
        FROM snapshots
        WHERE source = ?
          AND (
                (origin = ? AND dest = ?)
             OR (origin = ? AND dest = ?)
          )
        GROUP BY collected_on
        ORDER BY collected_on
        """,
        (source, settings.origin, settings.dest, settings.dest, settings.origin),
    ).fetchall()
    by_day = {
        row["collected_on"]: {
            "ok": int(row["ok"] or 0),
            "error": int(row["error"] or 0),
            "empty": int(row["empty"] or 0),
        }
        for row in day_rows
    }
    days = []
    if by_day:
        cursor = date.fromisoformat(min(by_day))
        while cursor <= today:
            key = cursor.isoformat()
            stats = by_day.get(key, {"ok": 0, "error": 0, "empty": 0})
            kind = _kind(stats["ok"], stats["error"], stats["empty"]) if key in by_day else "missing"
            kind_hu = {
                "ok": "rendben",
                "partial": "részleges: volt siker és hiba is",
                "error": "hiba: aznap nem volt sikeres keresés",
                "missing": "hiányzik: nem futott a gyűjtő",
            }[kind]
            hover = (
                f"{key} — {kind_hu}. "
                f"Sikeres: {stats['ok']}, hiba: {stats['error']}, üres: {stats['empty']}."
            )
            days.append({"date": key, "kind": kind, "hover": hover, **stats})
            cursor += timedelta(days=1)

    last_date = max(by_day) if by_day else None
    last_run: dict[str, Any] = {
        "collected_on": last_date,
        "ok": 0,
        "error": 0,
        "empty": 0,
        "pinned_min": None,
        "duration_minutes": None,
        "duration_label": "—",
        "duration_hover": "Még nincs mért futási idő.",
        "ok_hover": "",
        "error_hover": "",
        "run_hover": "",
        "pinned_hover": (
            "A 2027-03-12 oda / 03-15 vissza csomag legolcsóbb ára az utolsó "
            "gyűjtésből. RT = round-trip (oda-vissza), nem két egyirányú összege."
        ),
    }
    if last_date:
        last_run.update(by_day[last_date])
        last_run.update(
            _duration_for_day(
                conn,
                last_date,
                source,
                scope="mad",
                origin=settings.origin,
                dest=settings.dest,
                include_reverse=True,
            )
        )
        job_rows = conn.execute(
            """
            SELECT trip_type, origin, dest, outbound_date, return_date, status, offer_count
            FROM snapshots
            WHERE collected_on = ? AND source = ?
              AND (
                    (origin = ? AND dest = ?)
                 OR (origin = ? AND dest = ?)
              )
            ORDER BY trip_type, outbound_date
            """,
            (last_date, source, settings.origin, settings.dest, settings.dest, settings.origin),
        ).fetchall()
        ok_jobs = [row for row in job_rows if row["status"] == "ok"]
        err_jobs = [row for row in job_rows if row["status"] == "error"]
        if len(ok_jobs) <= 8:
            last_run["ok_hover"] = (
                f"{len(ok_jobs)} sikeres keresés: "
                + "; ".join(_job_label(row) for row in ok_jobs)
            )
        else:
            n_ow = sum(1 for row in ok_jobs if row["trip_type"] == "OW")
            n_rt = sum(1 for row in ok_jobs if row["trip_type"] == "RT")
            last_run["ok_hover"] = (
                f"{len(ok_jobs)} sikeres keresés: {n_ow} egyirányú (OW), "
                f"{n_rt} oda-vissza (RT)."
            )
        last_run["error_hover"] = (
            f"{len(err_jobs)} hibás keresés."
            + (
                " " + "; ".join(_job_label(row) for row in err_jobs[:8])
                if err_jobs
                else ""
            )
        )
        last_run["run_hover"] = f"Gyűjtés napja: {last_date}, forrás: {source}."
        pinned = conn.execute(
            """
            SELECT MIN(o.price_amount) AS min_price
            FROM snapshots s
            JOIN offers o ON o.snapshot_id = s.id
            WHERE s.trip_type = 'RT'
              AND s.origin = ?
              AND s.dest = ?
              AND s.outbound_date = '2027-03-12'
              AND s.return_date = '2027-03-15'
              AND s.collected_on = ?
              AND s.source = ?
              AND s.status = 'ok'
            """,
            (settings.origin, settings.dest, last_date, source),
        ).fetchone()
        last_run["pinned_min"] = pinned["min_price"] if pinned else None
        if last_run["pinned_min"] is not None:
            last_run["pinned_hover"] = (
                f"A {last_date}-i gyűjtésből: 2027-03-12 BUD→MAD + 2027-03-15 MAD→BUD "
                f"csomag legolcsóbb ára ({source}). RT = oda-vissza, nem két OW összege."
            )

    failures = [
        dict(row)
        for row in conn.execute(
            """
            SELECT collected_on, trip_type, origin, dest, outbound_date, return_date, error
            FROM snapshots
            WHERE status = 'error' AND source = ?
              AND (
                    (origin = ? AND dest = ?)
                 OR (origin = ? AND dest = ?)
              )
            ORDER BY collected_on DESC, outbound_date
            LIMIT 80
            """,
            (source, settings.origin, settings.dest, settings.dest, settings.origin),
        )
    ]
    pinned_series = []
    pinned_airline_series: dict[str, list[dict[str, Any]]] = {}
    by_day_air: dict[str, dict[str, float]] = {}
    for row in conn.execute(
        """
        SELECT s.collected_on, o.airline, MIN(o.price_amount) AS min_price
        FROM snapshots s
        JOIN offers o ON o.snapshot_id = s.id
        WHERE s.trip_type = 'RT'
          AND s.origin = ?
          AND s.dest = ?
          AND s.outbound_date = '2027-03-12'
          AND s.return_date = '2027-03-15'
          AND s.status = 'ok'
          AND s.source = ?
        GROUP BY s.collected_on, o.airline
        ORDER BY s.collected_on, o.airline
        """,
        (settings.origin, settings.dest, source),
    ):
        day = row["collected_on"]
        name = row["airline"] or "ismeretlen"
        price = float(row["min_price"])
        by_day_air.setdefault(day, {})[name] = price
        pinned_airline_series.setdefault(name, []).append(
            {
                "x": day,
                "y": price,
                "label": f"{day} · {name} · {_ft(price)}",
            }
        )
    for day, prices in sorted(by_day_air.items()):
        cheapest = min(prices.values())
        pinned_series.append(
            {
                "x": day,
                "y": cheapest,
                "label": f"{day} · oda-vissza (RT) {_ft(cheapest)}",
            }
        )

    pinned_flights: list[dict[str, Any]] = []
    if last_date:
        seen_airlines: set[str] = set()
        for row in conn.execute(
            """
            SELECT o.airline, o.airline_code, o.price_amount, o.outbound_flights,
                   o.return_flights, o.departure_at, o.arrival_at,
                   o.return_departure_at, o.return_arrival_at
            FROM snapshots s
            JOIN offers o ON o.snapshot_id = s.id
            WHERE s.trip_type = 'RT'
              AND s.origin = ?
              AND s.dest = ?
              AND s.outbound_date = '2027-03-12'
              AND s.return_date = '2027-03-15'
              AND s.status = 'ok'
              AND s.collected_on = ?
              AND s.source = ?
            ORDER BY o.price_amount
            """,
            (settings.origin, settings.dest, last_date, source),
        ):
            name = row["airline"] or "ismeretlen"
            if name in seen_airlines:
                continue
            seen_airlines.add(name)
            out_flight = row["outbound_flights"]
            out_dep, out_arr = row["departure_at"], row["arrival_at"]
            in_flight = row["return_flights"]
            in_dep, in_arr = row["return_departure_at"], row["return_arrival_at"]
            if _flight_label(out_flight) == "—" or not out_dep:
                ow_out = _best_ow_leg(
                    conn,
                    collected_on=last_date,
                    source=source,
                    airline=name,
                    origin=settings.origin,
                    dest=settings.dest,
                    outbound_date="2027-03-12",
                )
                if ow_out:
                    if _flight_label(out_flight) == "—":
                        out_flight = ow_out["outbound_flights"]
                    out_dep = out_dep or ow_out["departure_at"]
                    out_arr = out_arr or ow_out["arrival_at"]
            if _flight_label(in_flight) == "—" or not in_dep:
                ow_in = _best_ow_leg(
                    conn,
                    collected_on=last_date,
                    source=source,
                    airline=name,
                    origin=settings.dest,
                    dest=settings.origin,
                    outbound_date="2027-03-15",
                )
                if ow_in:
                    if _flight_label(in_flight) == "—":
                        in_flight = ow_in["outbound_flights"]
                    in_dep = in_dep or ow_in["departure_at"]
                    in_arr = in_arr or ow_in["arrival_at"]
            pinned_flights.append(
                {
                    "airline": name,
                    "code": row["airline_code"] or "",
                    "price": _ft(float(row["price_amount"])),
                    "outbound": _leg_label(out_flight, out_dep, out_arr),
                    "inbound": _leg_label(in_flight, in_dep, in_arr),
                }
            )

    horizon_series: list[dict[str, Any]] = []
    airline_series: dict[str, list[dict[str, Any]]] = {}
    airline_wins: list[dict[str, Any]] = []
    cheapest_flights: list[dict[str, Any]] = []
    if last_date:
        collected = date.fromisoformat(last_date)
        offer_rows = conn.execute(
            """
            SELECT s.outbound_date, o.airline, o.airline_code, o.departure_at,
                   o.arrival_at, o.price_amount, o.duration_minutes, o.outbound_flights
            FROM snapshots s
            JOIN offers o ON o.snapshot_id = s.id
            WHERE s.trip_type = 'OW'
              AND s.origin = ?
              AND s.dest = ?
              AND s.status = 'ok'
              AND s.collected_on = ?
              AND s.source = ?
            ORDER BY s.outbound_date, o.price_amount
            """,
            (settings.origin, settings.dest, last_date, source),
        ).fetchall()
        by_date: dict[str, list[Any]] = {}
        by_airline: dict[str, dict[str, float]] = {}
        for row in offer_rows:
            by_date.setdefault(row["outbound_date"], []).append(row)
            name = row["airline"] or "ismeretlen"
            prices = by_airline.setdefault(name, {})
            key = row["outbound_date"]
            amount = float(row["price_amount"])
            prices[key] = amount if key not in prices else min(prices[key], amount)

        min_price = None
        for outbound, rows in by_date.items():
            best = rows[0]
            price = float(best["price_amount"])
            if min_price is None or price < min_price:
                min_price = price
            days_left = (date.fromisoformat(outbound) - collected).days
            horizon_series.append(
                {
                    "x": outbound,
                    "y": price,
                    "days": days_left,
                    "is_today": outbound == today.isoformat(),
                    "is_min": False,
                    "airline": best["airline"],
                    "label": (
                        f"{outbound} · {days_left} nap múlva · {_ft(price)} · "
                        f"{best['airline'] or ''} {_hhmm(best['departure_at'])}"
                    ),
                }
            )
        if min_price is not None:
            for point in horizon_series:
                point["is_min"] = abs(point["y"] - min_price) < 0.5

        for name, prices in sorted(by_airline.items()):
            airline_series[name] = [
                {
                    "x": day,
                    "y": amount,
                    "days": (date.fromisoformat(day) - collected).days,
                    "label": f"{name} · {day} · {_ft(amount)}",
                }
                for day, amount in sorted(prices.items())
            ]

        wins: dict[str, int] = {}
        all_prices: dict[str, list[float]] = {}
        for rows in by_date.values():
            winner = rows[0]["airline"] or "ismeretlen"
            wins[winner] = wins.get(winner, 0) + 1
        for name, prices in by_airline.items():
            all_prices[name] = list(prices.values())
        total_days = sum(wins.values()) or 1
        airline_wins = [
            {
                "airline": name,
                "wins": count,
                "share": f"{100 * count / total_days:.0f}%",
                "median": _ft(_median(all_prices.get(name, []))),
            }
            for name, count in sorted(wins.items(), key=lambda item: -item[1])
        ]

        ranked = []
        for outbound, rows in by_date.items():
            best = rows[0]
            ranked.append((float(best["price_amount"]), outbound, best))
        ranked.sort(key=lambda item: (item[0], item[1]))
        for price, outbound, best in ranked[:12]:
            days_left = (date.fromisoformat(outbound) - collected).days
            cheapest_flights.append(
                {
                    "date": outbound,
                    "days": days_left,
                    "airline": best["airline"] or "—",
                    "code": best["airline_code"] or "",
                    "flight": _leg_label(
                        best["outbound_flights"],
                        best["departure_at"],
                        best["arrival_at"],
                    ),
                    "duration": _duration(best["duration_minutes"]),
                    "price": _ft(price),
                }
            )

    return {
        "generated_at": generated,
        "source": source,
        "horizon_days": settings.horizon_days,
        "last_run": last_run,
        "days": days,
        "failures": failures,
        "pinned_series": pinned_series,
        "pinned_airline_series": pinned_airline_series,
        "pinned_flights": pinned_flights,
        "horizon_series": horizon_series,
        "airline_series": airline_series,
        "airline_wins": airline_wins,
        "cheapest_flights": cheapest_flights,
        "pdl": (
            _pdl_payload(conn, settings, source, today, settings.stay_horizons[0])
            if settings.stay_horizons
            else None
        ),
    }


def write_dashboard(settings: Settings, today: date | None = None) -> Path:
    settings.docs_dir.mkdir(parents=True, exist_ok=True)
    (settings.docs_dir / ".nojekyll").write_text("", encoding="utf-8")
    if not settings.db_path.exists():
        payload: dict[str, Any] = {
            "generated_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M"),
            "horizon_days": settings.horizon_days,
            "last_run": {},
            "days": [],
            "failures": [],
            "pinned_series": [],
            "pinned_airline_series": {},
            "pinned_flights": [],
            "horizon_series": [],
            "airline_series": {},
            "airline_wins": [],
            "cheapest_flights": [],
            "pdl": None,
        }
    else:
        conn = connect(settings.db_path)
        try:
            payload = build_payload(conn, settings, today=today)
        finally:
            conn.close()
    encoded = json.dumps(payload, ensure_ascii=False).replace("<", "\\u003c")
    html = TEMPLATE.replace("__PAYLOAD__", encoded)
    path = settings.docs_dir / "index.html"
    path.write_text(html, encoding="utf-8")
    return path
