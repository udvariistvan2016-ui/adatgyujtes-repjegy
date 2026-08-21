# Farewatch — BUD–MAD jegyár-gyűjtő

Napi pillanatfelvétel Budapest–Madrid jegyárakról. Visszamenőleg ez az adat nem rekonstruálható.

Repo: https://github.com/udvariistvan2016-ui/adatgyujtes-repjegy

## Mit gyűjt

- **Horizont:** egyirányú BUD→MAD, economy, 1 felnőtt, csak közvetlen, **180 nap** előre, HUF, megjelenő legalacsonyabb (basic) ár.
- **Kitűzött út:** oda-vissza **2027-03-12 → 2027-03-15**, plusz egy-egy egyirányú ugyanerre a két napra (oda BUD–MAD, vissza MAD–BUD).

A scope a [`config.yaml`](config.yaml) fájlban van rögzítve.

## Forrás

Hivatalos hobbi jegyár-API 2026-ban gyakorlatilag nincs (Amadeus Self-Service leállt; Kiwi/Skyscanner partnerprogram).

Az első adapter **Google Flights** a [`fast-flights`](https://pypi.org/project/fast-flights/) könyvtáron keresztül: egy keresésből kijön Wizz, Ryanair és Iberia. Ez nyilvános listát olvas, nem foglal, nem lép login mögé. A Google ToS-a az automatizálást korlátozza — a gyűjtő szándékosan lassú (kb. 2.5 s szünet kérések között), személyes archívumra való.

A `source` adapter cserélhető. Teszthez / próbaüzemhez: `--source mock`.

EU-ból a Google először cookie-falat mutat; a gyűjtő egy általános consent sütivel kéri a keresőt. Ha a parser üres oldalt kap, a snapshot `status=error` lesz, a futás a következő dátummal folytatódik.

Oda-vissza keresésnél a Google gyakran csak az **oda járatot** listázza a csomagár mellett (vissza láb a kiválasztás után jön). A kitűzött út RT ára így is gyűlik; a vissza egyirányú (MAD→BUD, 03-15) külön sor.

## Telepítés

Python 3.11+.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Próba hálózat nélkül:

```powershell
python -m farewatch collect --source mock --limit 3
python -m farewatch status
python -m farewatch analyze
```

Éles, egy dátum (Google):

```powershell
python -m farewatch collect --date 2026-08-22
```

Teljes napi futás (~180 dátum + kitűzött RT, kb. 15–40 perc):

```powershell
python -m farewatch collect
```

Ha a mai nap már lefutott sikeresen: `--force` mindent felülír.
Ha **csak hibás** keresések voltak, futtasd újra ugyanazt a parancsot — a hibásak automatikusan újrapróbálódnak, a sikerest kihagyja.

A futás végén a kimenet: `planned=… ok=… empty=… error=…`. Ha `error>0`, érdemes 30–60 perc múlva újra futtatni (Google consent / átmeneti tiltás). A dashboard naptárán a piros/sárga napok ugyanezt mutatják.

## Dashboard (GitHub Pages)

A `docs/index.html` statikus oldal: utolsó futás, gyűjtési naptár (siker / hiba / hiányzó nap), sikertelen keresések, kitűzött út ára.

Élő: https://udvariistvan2016-ui.github.io/adatgyujtes-repjegy/

```powershell
python -m farewatch dashboard
```

A napi `scripts\collect.ps1` a gyűjtés előtt **3–18 perc véletlen késleltetést** tart (hogy ne 10:00-kor pontosan induljon), utána HTML + git push. Kézi, azonnali futás: `.\scripts\collect.ps1 -NoDelay`. Kérések között ~5.5–8.5 s szünet van.

## Tárolás

A kanonikus adat **SQLite**, nem napi CSV. Egy kereséshez több ajánlat tartozik, a hibás nap újrapróbálható (unique kulcs), és SQL-lel aggregálható. A CSV **export**, nem a forrás.

- `data/fares.sqlite3` — két tábla: `snapshots` (egy keresés) + `offers` (a találatok)
- `data/raw/` — nyers JSON keresésenként (parser-csere után újraolvasható)
- `data/reports/` — CSV és ábrák (`python -m farewatch analyze`)
- `data/backups/` — napi SQLite másolat, 14 napot tart

Belénézés:

```powershell
python -m farewatch status
python -m farewatch analyze
```

A `analyze` a `data/reports/` alá írja a horizont és a kitűzött RT CSV-t. A teljes séma:

```
snapshots  egy keresés: collected_on, origin/dest, outbound_date, trip_type (OW|RT), status, source
offers     a keresés találatai: airline, departure_at, price_amount, …  (N sor / snapshot)
```

GUI-hoz: [DB Browser for SQLite](https://sqlitebrowser.org/) — nyisd meg a `data/fares.sqlite3` fájlt. OneDrive alatt a SQLite néha összeakad a szinkronnal; ha hibát látsz, állítsd szünetre a `data/` mappát, vagy tedd a DB-t helyi lemezre.

## Ütemezés (laptop, amíg nincs VPS)

Napi **10:00** kezdet — akkor már be van kapcsolva a gép. A 12:00-es második futás csak a hibás kereséseket kéri újra (a sikerest kihagyja), majd újra HTML + git push.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\install-windows-task.ps1
```

Ez két Task Scheduler feladatot hoz létre, **a bejelentkezett felhasználóként** (kell a git push-hoz):

- `Farewatch-BUD-MAD` — 10:00: collect → dashboard → `docs/` commit + push
- `Farewatch-BUD-MAD-retry` — 12:00: ugyanaz; a sikerest kihagyja, a hibásat újra kéri
- `Farewatch-BUD-MAD-backup` — 12:40: SQLite másolat

Ha 10:00-kor a laptop még alszik / ki van kapcsolva, a `StartWhenAvailable` bekapcsoláskor (bejelentkezés után) elindítja. Alvásból ébresztést a Windows nem mindig tud; a biztos út: 10-re már nyitva legyen a gép, te bejelentkezve.

Kézi futtatás: `.\scripts\collect.ps1`  
Log: `data\collect.log`

**VPS** (később): lásd [`scripts/crontab.example`](scripts/crontab.example). Ugyanaz a `collect.sh` (gyűjtés + dashboard + push).

```bash
chmod +x scripts/collect.sh scripts/backup-db.sh
crontab -e
```

## CLI

| Parancs | Mit csinál |
| --- | --- |
| `python -m farewatch collect` | Napi gyűjtés |
| `python -m farewatch collect --pinned-only` | Csak a 2027-03-12/15 út |
| `python -m farewatch collect --dry-run` | Job lista, hálózat nélkül |
| `python -m farewatch status` | Hány snapshot, kitűzött RT min ár |
| `python -m farewatch dashboard` | HTML a `docs/` mappába |
| `python -m farewatch analyze` | Ár vs. hátralévő napok + RT idősor |
| `python -m farewatch backup` | SQLite másolat |

## Tesztek

```powershell
pytest
```
