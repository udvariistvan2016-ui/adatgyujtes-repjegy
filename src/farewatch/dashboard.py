from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from farewatch.config import Settings
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
  <p class="hint" id="pinned-caption"></p>

  <h2>Horizont — egyirányú (OW) napi minimum</h2>
  <svg id="horizon" class="chart" viewBox="0 0 1000 280" preserveAspectRatio="xMidYMid meet"></svg>
  <p class="hint">A vízszintes tengely a 180 napos horizont (indulásig hátralévő napok). Halvány kék: nyers min. Kék: 7 napos simított görbe. Zöld szaggatott: a horizont minimuma. Narancs pötty: a mai indulási nap (ha van adat).</p>

  <h2>Légitársaságok a horizonton</h2>
  <svg id="airlines" class="chart" viewBox="0 0 1000 280" preserveAspectRatio="xMidYMid meet"></svg>
  <div class="legend" id="airline-legend"></div>
  <div class="card" id="airline-wins"></div>

  <h2>Legolcsóbb közelgő járatok</h2>
  <div class="card" id="flights"></div>

  <h2>Adatszerkezet</h2>
  <div class="card">
    <p class="hint">A kanonikus tároló SQLite (<code>data/fares.sqlite3</code>), nem CSV: egy kereséshez több ajánlat tartozik, a hibás napok újrapróbálhatók, és belőle bármikor készül CSV. Export: <code>python -m farewatch analyze</code> → <code>data/reports/</code>.</p>
    <pre class="schema">snapshots  = egy keresés (dátum, OW/RT, status, forrás)
offers     = a keresés találatai (légitársaság, idő, ár)
           1 snapshot → N offer</pre>
  </div>
</main>
<script type="application/json" id="payload">__PAYLOAD__</script>
<script>
const data = JSON.parse(document.getElementById("payload").textContent);
const $ = (id) => document.getElementById(id);
$("generated").textContent = data.generated_at || "—";
$("horizon-days").textContent = data.horizon_days || 180;
const COLORS = {"Wizz Air":"#c50e7a","Ryanair":"#f1c40f","Iberia":"#e74c3c"};
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
spark("pinned", data.pinned_series || [], "Oda-vissza (RT) csomagár");
sparkHorizon("horizon", data.horizon_series || [], "Egyirányú (OW) min", { smooth: true, minLine: true });
$("pinned-caption").textContent = (data.pinned_series || []).length
  ? "RT = round-trip: oda-vissza csomag (2027-03-12 + 03-15). Hover: melyik napon mértük."
  : "";

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


def _duration(minutes: int | None) -> str:
    if not minutes:
        return "—"
    hours, mins = divmod(int(minutes), 60)
    return f"{hours}ó {mins:02d}p"


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
        GROUP BY collected_on
        ORDER BY collected_on
        """,
        (source,),
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
        job_rows = conn.execute(
            """
            SELECT trip_type, origin, dest, outbound_date, return_date, status, offer_count
            FROM snapshots
            WHERE collected_on = ? AND source = ?
            ORDER BY trip_type, outbound_date
            """,
            (last_date, source),
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
              AND s.outbound_date = '2027-03-12'
              AND s.return_date = '2027-03-15'
              AND s.collected_on = ?
              AND s.source = ?
              AND s.status = 'ok'
            """,
            (last_date, source),
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
            ORDER BY collected_on DESC, outbound_date
            LIMIT 80
            """,
            (source,),
        )
    ]
    pinned_series = []
    for row in conn.execute(
        """
        SELECT s.collected_on, MIN(o.price_amount) AS min_price
        FROM snapshots s
        JOIN offers o ON o.snapshot_id = s.id
        WHERE s.trip_type = 'RT'
          AND s.outbound_date = '2027-03-12'
          AND s.return_date = '2027-03-15'
          AND s.status = 'ok'
          AND s.source = ?
        GROUP BY s.collected_on
        ORDER BY s.collected_on
        """,
        (source,),
    ):
        price = float(row["min_price"])
        pinned_series.append(
            {
                "x": row["collected_on"],
                "y": price,
                "label": f"{row['collected_on']} · oda-vissza (RT) {_ft(price)}",
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
                    "flight": (
                        f"{best['outbound_flights'] or 'közvetlen'} "
                        f"{_hhmm(best['departure_at'])}–{_hhmm(best['arrival_at'])}"
                    ).strip(),
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
        "horizon_series": horizon_series,
        "airline_series": airline_series,
        "airline_wins": airline_wins,
        "cheapest_flights": cheapest_flights,
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
            "horizon_series": [],
            "airline_series": {},
            "airline_wins": [],
            "cheapest_flights": [],
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
