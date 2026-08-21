from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from farewatch.config import Settings
from farewatch.db import connect

TEMPLATE = """<!DOCTYPE html>
<html lang="hu">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Farewatch — BUD–MAD</title>
  <style>
    :root {
      --bg: #0f1419;
      --card: #1a222c;
      --line: #2b3642;
      --text: #e8eef4;
      --muted: #93a4b5;
      --ok: #3dd68c;
      --partial: #f5c542;
      --err: #ff6b6b;
      --miss: #5c6b7a;
      --accent: #6cb6ff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.45;
    }
    main { max-width: 1080px; margin: 0 auto; padding: 28px 20px 64px; }
    h1 { font-size: 1.6rem; margin: 0 0 6px; }
    h2 { font-size: 1.15rem; margin: 32px 0 12px; }
    .sub { color: var(--muted); margin-bottom: 24px; }
    .kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; }
    .card {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 14px 16px;
    }
    .card[title], .day[title] { cursor: help; }
    .card .label { color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: .04em; }
    .card .value { font-size: 1.45rem; font-weight: 650; margin-top: 4px; }
    .cal { display: flex; flex-wrap: wrap; gap: 6px; }
    .day {
      min-width: 58px; height: 44px; border-radius: 8px; padding: 0 6px;
      display: flex; align-items: center; justify-content: center;
      font-size: 0.78rem; color: #0b1014; font-weight: 650; font-variant-numeric: tabular-nums;
    }
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
    svg { width: 100%; height: 200px; background: var(--card); border: 1px solid var(--line); border-radius: 12px; }
    .hint { color: var(--muted); font-size: 0.85rem; }
  </style>
</head>
<body>
<main>
  <h1>BUD → MAD jegyárak</h1>
  <p class="sub">Utolsó frissítés: <span id="generated"></span></p>
  <div class="kpis" id="kpis"></div>

  <h2>Gyűjtési napok</h2>
  <p class="hint">Egy doboz = egy naptári nap, amikor a gyűjtő futott (vagy ki kellett volna futnia az első nap óta). A hónap–nap a dobozon van; a hover a keresések bontását mutatja.</p>
  <div class="legend">
    <span title="Az aznapi összes keresés sikerült vagy üres (nincs járat), hiba nélkül."><i class="sw" style="background:var(--ok)"></i>rendben</span>
    <span title="Ugyanazon a napon volt sikeres ÉS hibás keresés is. A hibásak újrafuttatáskor újrapróbálódnak."><i class="sw" style="background:var(--partial)"></i>részleges</span>
    <span title="Az aznapi keresések elhasaltak, siker nélkül."><i class="sw" style="background:var(--err)"></i>hiba</span>
    <span title="Az első gyűjtés óta ez a naptári nap kimaradt (nem futott a script)."><i class="sw" style="background:var(--miss)"></i>hiányzik</span>
  </div>
  <div class="cal" id="calendar"></div>

  <h2>Sikertelen keresések</h2>
  <div class="card" id="failures"></div>

  <h2>Kitűzött út — oda-vissza (RT), 2027. márc. 12–15.</h2>
  <svg id="pinned" viewBox="0 0 1000 200" preserveAspectRatio="none"></svg>
  <p class="hint" id="pinned-caption"></p>

  <h2>Legutóbbi horizont — egyirányú (OW) napi minimum</h2>
  <svg id="horizon" viewBox="0 0 1000 200" preserveAspectRatio="none"></svg>
  <p class="hint">OW = one-way, egyirányú jegy. A görbe a mai gyűjtés 180 indulási napjának minimumát mutatja. Hover: dátum, hány nap múlva, ár.</p>
</main>
<script type="application/json" id="payload">__PAYLOAD__</script>
<script>
const data = JSON.parse(document.getElementById("payload").textContent);
const $ = (id) => document.getElementById(id);
$("generated").textContent = data.generated_at || "—";

function kpi(label, value, title) {
  const t = title ? ` title="${title.replaceAll('"', '&quot;')}"` : "";
  return `<div class="card"${t}><div class="label">${label}</div><div class="value">${value}</div></div>`;
}
const last = data.last_run || {};
const pinnedTitle = last.pinned_hover || "A 2027-03-12 oda / 03-15 vissza csomag legolcsóbb ára az utolsó gyűjtésből. RT = round-trip, oda-vissza; nem két egyirányú összege.";
$("kpis").innerHTML = [
  kpi("Utolsó futás", last.collected_on || "nincs", last.run_hover || ""),
  kpi("Sikeres", last.ok ?? "—", last.ok_hover || "Hány keresés tért vissza árral aznap."),
  kpi("Hiba", last.error ?? "—", last.error_hover || "Hány keresés hasalt el (hálózat, Google, parser)."),
  kpi("Üres / nincs járat", last.empty ?? "—", "A keresés lefutott, de azon a napon nincs közvetlen járat."),
  kpi("Kitűzött RT min", last.pinned_min != null ? Math.round(last.pinned_min).toLocaleString("hu-HU") + " Ft" : "—", pinnedTitle),
].join("");

$("calendar").innerHTML = (data.days || []).map(d => {
  const cls = d.kind;
  const title = d.hover || d.date;
  const label = d.date.slice(5);
  return `<div class="day ${cls}" title="${title.replaceAll('"', '&quot;')}">${label}</div>`;
}).join("") || `<p class="empty">Még nincs gyűjtött nap.</p>`;

const fails = data.failures || [];
$("failures").innerHTML = fails.length
  ? `<table><thead><tr><th>Gyűjtés</th><th>Keresés</th><th>Hiba</th></tr></thead><tbody>${
      fails.map(f => `<tr><td>${f.collected_on}</td><td>${f.trip_type === "RT" ? "oda-vissza (RT)" : "egyirányú (OW)"} ${f.origin}–${f.dest} ${f.outbound_date}${f.return_date ? " / "+f.return_date : ""}</td><td>${f.error || "—"}</td></tr>`).join("")
    }</tbody></table>`
  : `<p class="empty">Nincs rögzített hiba.</p>`;

function spark(id, series, yLabel) {
  const svg = $(id);
  if (!series.length) {
    svg.innerHTML = `<text x="20" y="100" fill="#93a4b5">Még nincs elég adat.</text>`;
    return;
  }
  const ys = series.map(p => p.y);
  const min = Math.min(...ys), max = Math.max(...ys);
  const span = (max - min) || 1;
  const w = 1000, h = 200, pad = 28;
  const pts = series.map((pt, i) => {
    const x = pad + (i / Math.max(series.length - 1, 1)) * (w - 2 * pad);
    const y = h - pad - ((pt.y - min) / span) * (h - 2 * pad);
    return { x, y, label: pt.label || `${pt.x}: ${Math.round(pt.y)} Ft` };
  });
  const line = pts.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(" ");
  const dots = pts.map(p =>
    `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="5" fill="#6cb6ff"><title>${p.label.replaceAll("<", "")}</title></circle>`
  ).join("");
  svg.innerHTML = `<polyline fill="none" stroke="#6cb6ff" stroke-width="3" points="${line}"></polyline>
    ${dots}
    <text x="20" y="22" fill="#93a4b5" font-size="14">${yLabel}: ${Math.round(min).toLocaleString("hu-HU")} – ${Math.round(max).toLocaleString("hu-HU")} Ft</text>`;
}
spark("pinned", data.pinned_series || [], "Oda-vissza (RT) csomagár");
spark("horizon", data.horizon_series || [], "Egyirányú (OW) min");
$("pinned-caption").textContent = (data.pinned_series || []).length
  ? "RT = round-trip: egy oda-vissza csomag ára (2027-03-12 BUD→MAD + 03-15 MAD→BUD). Hover a ponton: melyik napon mértük. Nem két egyirányú összege."
  : "";
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
                "label": (
                    f"{row['collected_on']} · oda-vissza (RT) csomagár "
                    f"{price:,.0f} Ft".replace(",", " ")
                ),
            }
        )
    horizon_series = []
    if last_date:
        collected = date.fromisoformat(last_date)
        for row in conn.execute(
            """
            SELECT s.outbound_date, MIN(o.price_amount) AS min_price
            FROM snapshots s
            JOIN offers o ON o.snapshot_id = s.id
            WHERE s.trip_type = 'OW'
              AND s.origin = ?
              AND s.dest = ?
              AND s.status = 'ok'
              AND s.collected_on = ?
              AND s.source = ?
            GROUP BY s.outbound_date
            ORDER BY s.outbound_date
            """,
            (settings.origin, settings.dest, last_date, source),
        ):
            outbound = date.fromisoformat(row["outbound_date"])
            days_left = (outbound - collected).days
            price = float(row["min_price"])
            horizon_series.append(
                {
                    "x": row["outbound_date"],
                    "y": price,
                    "days": days_left,
                    "label": (
                        f"{row['outbound_date']} · {days_left} nap múlva · "
                        f"{price:,.0f} Ft".replace(",", " ")
                    ),
                }
            )
    return {
        "generated_at": generated,
        "source": source,
        "last_run": last_run,
        "days": days,
        "failures": failures,
        "pinned_series": pinned_series,
        "horizon_series": horizon_series,
    }


def write_dashboard(settings: Settings, today: date | None = None) -> Path:
    settings.docs_dir.mkdir(parents=True, exist_ok=True)
    (settings.docs_dir / ".nojekyll").write_text("", encoding="utf-8")
    if not settings.db_path.exists():
        payload: dict[str, Any] = {
            "generated_at": datetime.now().astimezone().strftime("%Y-%m-%d %H:%M"),
            "last_run": {},
            "days": [],
            "failures": [],
            "pinned_series": [],
            "horizon_series": [],
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
