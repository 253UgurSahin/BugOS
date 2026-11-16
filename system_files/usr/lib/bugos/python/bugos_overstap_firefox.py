"""Haal alles van je oude pc: bladwijzers en het Firefox-profiel van Windows in Firefox op BugOS zetten.

Bladwijzers (vanzelf, zonder 'Importeren' te zoeken)
    Firefox kan bij het starten één keer een HTML-bladwijzerbestand inlezen: de voorkeur
    browser.places.importBookmarksHTML = true met browser.bookmarks.file = <ons bestand>. Firefox zet de voorkeur daarna
    zelf weer op false (PlacesBrowserStartup.sys.mjs). Let op: dat inlezen VERVANGT alle bladwijzers
    (importFromURL met replace: true -> eraseEverything). Daarom zetten we eerst de bladwijzers die er al zijn
    (uit places.sqlite, met hun tags en sleutelwoorden) in hetzelfde bestand, en de nieuwe van Windows erbij in één map
    'Van Windows' op de bladwijzerbalk. Kunnen we places.sqlite niet lezen, dan doen we NIETS (anders zou je je
    bladwijzers kwijtraken) en zeggen we hoe het met de hand gaat.
    De voorkeuren schrijven we in prefs.js (niet in user.js: die geldt bij elke start opnieuw, dan zou Firefox je
    bladwijzers elke keer vervangen). Dat mag alleen als Firefox dicht is: een draaiende Firefox schrijft prefs.js bij
    het afsluiten weer over.

Het profiel van Windows (als firefox_profiel op de stick staat)
    We kopiëren de map naar ~/.mozilla/firefox (of ~/.config/mozilla/firefox, waar Firefox zijn profielen houdt) als
    een nieuw profiel 'Van Windows' en maken dat het standaardprofiel. Je huidige BugOS-profiel blijft staan als
    reserve (about:profiles). Wat er nooit mee gaat, ook als het op de stick staat: wachtwoorden (logins.json,
    key4.db ...) en cookies. Bestanden met Windows-paden die Firefox zelf opnieuw maakt (compatibility.ini,
    extensions.json, pkcs11.txt ...) laten we weg: anders weigert Firefox een profiel van een nieuwere versie, of
    zoekt hij naar C:\\Program Files.

Alles wat van de stick komt, is van een andere computer: we lezen het voorzichtig (grootte, soort, paden).
"""

from __future__ import annotations

import configparser
import html
import json
import os
import re
import secrets
import shutil
import sqlite3
import struct
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import bugos_config as bi
import bugos_overstap_toepassen as ot
from bugos_base import t

GOED, NIET, ZELF = ot.GOED, ot.NIET, ot.ZELF

# Nooit meenemen in een profiel: wachtwoorden en cookies (de keuze van de eigenaar), ook niet als Windows ze per
# ongeluk toch op de stick zette. sessionstore heeft de cookies van open tabbladen.
NOOIT_MEE = {"logins.json", "logins-backup.json", "logins.db", "logins.db-wal", "logins.db-shm", "key3.db", "key4.db", "signons.sqlite", "signons3.txt",
             "cookies.sqlite", "cookies.sqlite-wal", "cookies.sqlite-shm", "cookies.sqlite-journal",
             "sessionstore.jsonlz4", "sessionstore-backups", "sessionCheckpoints.json"}
# Maakt Firefox zelf opnieuw; van Windows kloppen ze niet (paden naar C:\, de versie van Windows, een slot).
NIET_NODIG = {"compatibility.ini", "extensions.json", "extensions.ini", "addonStartup.json.lz4", "pkcs11.txt",
              "lock", ".parentlock", "parent.lock", "startupCache", "cache2", "shader-cache", "minidumps",
              "crashes", "datareporting", "saved-telemetry-pings", "times.json"}
GROOTSTE_JSON = 64 * 1024 * 1024      # een bladwijzerbestand groter dan dit is geen bladwijzerbestand
EIGEN_BESTAND = "bugos-overstap-bladwijzers.html"


# ========================================================== bladwijzers lezen ===
# Een bladwijzer in ons eigen, simpele formaat (zodat Chrome, Edge en Firefox er hetzelfde uitzien):
#   map:        {"titel": ..., "kinderen": [...]}
#   link:       {"titel": ..., "url": ..., "datum": seconden, "tags": "a,b", "sleutel": "zoek"}
#   scheiding:  {"scheiding": True}

@dataclass
class Bron:
    """Bladwijzers van één browserprofiel op de stick."""
    naam: str                 # 'Chrome (Persoon 1)', zoals je hem in Firefox ziet
    soort: str                # 'chrome' (ook Edge en Brave) of 'firefox'
    pad: Path
    knopen: list = field(default_factory=list)


# Adressen die alleen in de browser van Windows werken (instellingen, de nieuwe-tabpagina): niet meenemen.
_EIGEN_PAGINA = re.compile(r"^(chrome|edge|brave|opera|vivaldi|about|chrome-extension|edge-extension|file):", re.I)


def _goede_url(url: str) -> bool:
    return bool(url) and len(url) <= 8000 and not _EIGEN_PAGINA.match(url) and url.isprintable()


def _chrome_datum(waarde) -> int:
    """Chrome telt microseconden sinds 1601; Firefox wil seconden sinds 1970."""
    try:
        s = int(waarde) // 1_000_000 - 11_644_473_600
    except (TypeError, ValueError):
        return 0
    return s if s > 0 else 0


def _chrome_knopen(knoop: dict, diepte: int = 0) -> list:
    uit = []
    if diepte > 40:   # een kapot of kwaadaardig bestand met eindeloos diepe mappen
        return uit
    for kind in ot._lijst(knoop.get("children")):
        kind = ot._dict(kind)
        titel = ot._tekst(kind.get("name"), 500)
        if kind.get("type") == "folder":
            uit.append({"titel": titel, "kinderen": _chrome_knopen(kind, diepte + 1)})
        elif kind.get("type") == "url":
            url = str(kind.get("url", "")).strip()
            if _goede_url(url):
                uit.append({"titel": titel or url, "url": url, "datum": _chrome_datum(kind.get("date_added"))})
    return uit


def chrome_bladwijzers(data: dict) -> list:
    """Chrome/Edge/Brave 'Bookmarks' -> eigen knopen: de balk eerst (die zie je ook in Chrome het meest), dan de
    'Andere bladwijzers' en die van je telefoon, elk als eigen map."""
    wortels = ot._dict(ot._dict(data).get("roots"))
    uit = _chrome_knopen(ot._dict(wortels.get("bookmark_bar")))
    namen = {"other": ("Andere bladwijzers", "Other bookmarks"), "synced": ("Mobiele bladwijzers", "Mobile bookmarks")}
    # Eerst 'other' en 'synced', dan wat een andere browser (of een oudere versie) nog meer als wortel heeft: die
    # met hun eigen naam, zodat er niets verloren gaat.
    for sleutel in ["other", "synced"] + [s for s in wortels if s not in ("bookmark_bar", "other", "synced")]:
        wortel = ot._dict(wortels.get(sleutel))
        kinderen = _chrome_knopen(wortel)
        if kinderen:
            titel = t(*namen[sleutel]) if sleutel in namen else (ot._tekst(wortel.get("name"), 200) or sleutel)
            uit.append({"titel": titel, "kinderen": kinderen})
    return uit


def lz4_blok(data: bytes, grootte: int) -> bytes:
    """Pak één LZ4-blok uit (het formaat van Firefox' .jsonlz4, zonder frame). Een eigen versie, want lz4 zit niet in
    de standaard van Python. Gooit ValueError bij iets wat geen geldig blok is of groter wordt dan 'grootte'."""
    uit = bytearray()
    i, n = 0, len(data)
    while i < n:
        token = data[i]
        i += 1
        lengte = token >> 4
        if lengte == 15:
            while True:
                if i >= n:
                    raise ValueError("lz4: kapot")
                b = data[i]
                i += 1
                lengte += b
                if b != 255:
                    break
        if i + lengte > n:
            raise ValueError("lz4: kapot")
        uit += data[i:i + lengte]
        i += lengte
        if i >= n:
            break   # het laatste stuk heeft alleen letterlijke bytes
        if i + 2 > n:
            raise ValueError("lz4: kapot")
        afstand = data[i] | (data[i + 1] << 8)
        i += 2
        if afstand == 0 or afstand > len(uit):
            raise ValueError("lz4: kapot")
        lengte = token & 15
        if lengte == 15:
            while True:
                if i >= n:
                    raise ValueError("lz4: kapot")
                b = data[i]
                i += 1
                lengte += b
                if b != 255:
                    break
        lengte += 4
        if len(uit) + lengte > grootte:
            raise ValueError("lz4: te groot")
        begin = len(uit) - afstand
        if afstand >= lengte:
            uit += uit[begin:begin + lengte]
        else:   # de kopie overlapt zichzelf (bijv. 'aaaa...'): byte voor byte
            for k in range(lengte):
                uit.append(uit[begin + k])
        if len(uit) > grootte:
            raise ValueError("lz4: te groot")
    return bytes(uit)


def lees_mozlz4(pad: Path) -> dict:
    """Een .jsonlz4 van Firefox (bladwijzer-reservekopie): 'mozLz40\\0', de grootte (4 bytes), dan één LZ4-blok."""
    data = pad.read_bytes()
    if not data.startswith(b"mozLz40\0") or len(data) < 12:
        raise ValueError("geen mozlz4")
    grootte = struct.unpack("<I", data[8:12])[0]
    if grootte > GROOTSTE_JSON:
        raise ValueError("te groot")
    tekst = lz4_blok(data[12:], grootte)
    uit = json.loads(tekst.decode("utf-8"))
    return uit if isinstance(uit, dict) else {}


def _firefox_knopen(knoop: dict, diepte: int = 0) -> list:
    uit = []
    if diepte > 40:
        return uit
    for kind in ot._lijst(knoop.get("children")):
        kind = ot._dict(kind)
        soort = kind.get("typeCode")
        titel = ot._tekst(kind.get("title"), 500)
        if soort == 2:
            uit.append({"titel": titel, "kinderen": _firefox_knopen(kind, diepte + 1)})
        elif soort == 3:
            uit.append({"scheiding": True})
        elif soort == 1:
            url = str(kind.get("uri", "")).strip()
            if _goede_url(url) or url.startswith("place:"):
                try:
                    datum = int(kind.get("dateAdded", 0)) // 1_000_000
                except (TypeError, ValueError):
                    datum = 0
                uit.append({"titel": titel or url, "url": url, "datum": max(0, datum),
                            "tags": ot._tekst(kind.get("tags"), 500), "sleutel": ot._tekst(kind.get("keyword"), 100)})
    return uit


def firefox_bladwijzers(data: dict) -> list:
    """Een bladwijzer-reservekopie van Firefox -> eigen knopen: de balk, het menu en 'Andere', elk in een eigen map."""
    namen = {"toolbar_____": ("Bladwijzerbalk", "Bookmarks toolbar"), "menu________": ("Bladwijzermenu", "Bookmarks menu"),
             "unfiled_____": ("Andere bladwijzers", "Other bookmarks"), "mobile______": ("Mobiele bladwijzers", "Mobile bookmarks")}
    per = {ot._dict(k).get("guid"): ot._dict(k) for k in ot._lijst(ot._dict(data).get("children"))}
    uit = []
    for guid in ("toolbar_____", "menu________", "unfiled_____", "mobile______"):
        kinderen = _firefox_knopen(per.get(guid, {}))
        if kinderen:
            uit.append({"titel": t(*namen[guid]), "kinderen": kinderen})
    return uit


def bladwijzer_bronnen(bron: Path, i: dict) -> list[Bron]:
    """Alle bladwijzerbestanden op de stick. Versie 2 noemt ze in 'browsers' (met de naam van het profiel); versie 1
    (of als die lijst ontbreekt): alles in de map Bladwijzers (Chrome.json, Edge.json, Firefox.jsonlz4)."""
    uit: list[Bron] = []
    gezien: set[Path] = set()
    browsers = [ot._dict(b) for b in ot._lijst(i.get("browsers"))]
    per_browser: dict[str, int] = {}
    for b in browsers:
        per_browser[ot._tekst(b.get("browser"), 40)] = per_browser.get(ot._tekst(b.get("browser"), 40), 0) + 1
    for b in browsers:
        pad = ot.binnen_stick(bron, b.get("bladwijzers"))
        if pad is None or not pad.is_file() or pad in gezien:
            continue
        browser = ot._tekst(b.get("browser"), 40) or pad.stem
        profiel = ot._tekst(b.get("naam"), 60) or ot._tekst(b.get("profiel"), 60)
        # Eén profiel van Chrome: gewoon 'Chrome'. Meer: 'Chrome (Werk)', zodat je ze uit elkaar houdt.
        naam = f"{browser} ({profiel})" if profiel and per_browser.get(browser, 0) > 1 else browser
        uit.append(Bron(naam, "firefox" if pad.suffix == ".jsonlz4" else "chrome", pad))
        gezien.add(pad)
    bw = bron / "Bladwijzers"
    try:
        losse = sorted(bw.iterdir()) if bw.is_dir() else []
    except OSError:
        losse = []
    for pad in losse:
        if pad in gezien or not pad.is_file() or pad.suffix not in (".json", ".jsonlz4"):
            continue
        uit.append(Bron(pad.stem.replace("-", " ").strip() or pad.stem,
                        "firefox" if pad.suffix == ".jsonlz4" else "chrome", pad))
        gezien.add(pad)
    return uit


def lees_bron(b: Bron) -> list:
    """De knopen van één bron, of [] als het bestand kapot is (dan doen de andere gewoon mee)."""
    try:
        if b.pad.stat().st_size > GROOTSTE_JSON:
            return []
        if b.soort == "firefox":
            return firefox_bladwijzers(lees_mozlz4(b.pad))
        return chrome_bladwijzers(json.loads(b.pad.read_text(encoding="utf-8-sig")))
    except (OSError, ValueError, UnicodeDecodeError, RecursionError):
        return []


# ======================================================== bladwijzers schrijven ===

def _html_knopen(knopen: list, diepte: int) -> list[str]:
    """Knopen -> regels van het Netscape-bladwijzerformaat (wat Firefox zelf ook schrijft en leest)."""
    inspring = "    " * diepte
    regels = []
    for k in knopen:
        if k.get("scheiding"):
            regels.append(f"{inspring}<HR>")
        elif "kinderen" in k:
            extra = k.get("_extra", "")
            regels.append(f"{inspring}<DT><H3{extra}>{html.escape(k.get('titel', ''))}</H3>")
            regels.append(f"{inspring}<DL><p>")
            regels.extend(_html_knopen(k["kinderen"], diepte + 1))
            regels.append(f"{inspring}</DL><p>")
        else:
            attr = f' HREF="{html.escape(k["url"], quote=True)}"'
            if k.get("datum"):
                attr += f' ADD_DATE="{int(k["datum"])}"'
            if k.get("tags"):
                attr += f' TAGS="{html.escape(k["tags"], quote=True)}"'
            if k.get("sleutel"):
                attr += f' SHORTCUTURL="{html.escape(k["sleutel"], quote=True)}"'
            regels.append(f"{inspring}<DT><A{attr}>{html.escape(k.get('titel', ''))}</A>")
    return regels


def bladwijzer_html(menu: list, balk: list, andere: list) -> str:
    """Het hele bestand: zoals Firefox exporteert. Wat bovenaan staat, gaat in het bladwijzermenu; de map met
    PERSONAL_TOOLBAR_FOLDER is de balk en UNFILED_BOOKMARKS_FOLDER 'Andere bladwijzers' (bij replace-inlezen)."""
    wortel = list(menu)
    wortel.append({"titel": "Bookmarks Toolbar", "kinderen": balk, "_extra": ' PERSONAL_TOOLBAR_FOLDER="true"'})
    if andere:
        wortel.append({"titel": "Other Bookmarks", "kinderen": andere, "_extra": ' UNFILED_BOOKMARKS_FOLDER="true"'})
    regels = ["<!DOCTYPE NETSCAPE-Bookmark-file-1>",
              "<!-- Gemaakt door BugOS: Haal alles van je oude pc -->",
              '<META HTTP-EQUIV="Content-Type" CONTENT="text/html; charset=UTF-8">',
              "<TITLE>Bookmarks</TITLE>", "<H1>Bookmarks Menu</H1>", "", "<DL><p>"]
    regels.extend(_html_knopen(wortel, 1))
    regels.append("</DL>")
    return "\n".join(regels) + "\n"


def bestaande_bladwijzers(profiel: Path) -> dict[str, list] | None:
    """De bladwijzers die nu in dit Firefox-profiel staan (menu, balk, andere), met tags en sleutelwoorden; {} met
    lege lijsten als er nog geen places.sqlite is. None als het bestand er is maar niet te lezen: dan niets doen.
    We lezen een kopie (met het -wal-bestand erbij, waar de laatste veranderingen in kunnen staan)."""
    leeg = {"menu": [], "balk": [], "andere": []}
    pad = profiel / "places.sqlite"
    if not pad.exists():
        return leeg
    try:
        with tempfile.TemporaryDirectory(prefix="bugos-places-") as tmp:
            kopie = Path(tmp) / "places.sqlite"
            shutil.copyfile(pad, kopie)
            if (profiel / "places.sqlite-wal").exists():
                shutil.copyfile(profiel / "places.sqlite-wal", Path(tmp) / "places.sqlite-wal")
            db = sqlite3.connect(str(kopie))
            try:
                rijen = db.execute("SELECT b.id, b.type, b.parent, b.position, b.title, b.guid, b.dateAdded, b.fk, "
                                   "p.url FROM moz_bookmarks b LEFT JOIN moz_places p ON p.id = b.fk").fetchall()
                try:
                    sleutels = dict(db.execute("SELECT k.place_id, k.keyword FROM moz_keywords k").fetchall())
                except sqlite3.Error:
                    sleutels = {}
            finally:
                db.close()
    except (OSError, sqlite3.Error):
        return None
    per_guid = {r[5]: r for r in rijen}
    kinderen: dict[int, list] = {}
    for r in rijen:
        kinderen.setdefault(r[2], []).append(r)
    for lijst in kinderen.values():
        lijst.sort(key=lambda r: r[3] or 0)
    # Tags: in Firefox zijn dat mappen onder 'tags________', met daarin een bladwijzer naar dezelfde plek (fk).
    tags: dict[int, list[str]] = {}
    tag_wortel = per_guid.get("tags________")
    if tag_wortel:
        for tagmap in kinderen.get(tag_wortel[0], []):
            for item in kinderen.get(tagmap[0], []):
                if item[7] is not None and tagmap[4]:
                    tags.setdefault(item[7], []).append(tagmap[4])

    def boom(ouder_id: int, diepte: int = 0) -> list:
        uit = []
        if diepte > 60:
            return uit
        for r in kinderen.get(ouder_id, []):
            _id, soort, _p, _pos, titel, _guid, datum, fk, url = r
            if soort == 2:
                uit.append({"titel": titel or "", "kinderen": boom(_id, diepte + 1)})
            elif soort == 3:
                uit.append({"scheiding": True})
            elif soort == 1 and url:
                uit.append({"titel": titel or "", "url": url, "datum": (datum or 0) // 1_000_000,
                            "tags": ",".join(tags.get(fk, [])), "sleutel": sleutels.get(fk, "") or ""})
        return uit

    uit = dict(leeg)
    for sleutel, guid in (("menu", "menu________"), ("balk", "toolbar_____"), ("andere", "unfiled_____")):
        if guid in per_guid:
            uit[sleutel] = boom(per_guid[guid][0])
    return uit


# ============================================================ Firefox-profielen ===

# Firefox als Flatpak (org.mozilla.firefox van Flathub): BugOS zet Firefox als losse app klaar, zodat je hem kunt
# verwijderen (keuze van de eigenaar, 2026-11-16). Een Flatpak bewaart zijn profielen in zijn eigen map onder
# ~/.var/app/<id>/, met daarin dezelfde opbouw als de gewone Firefox.
FLATPAK_FIREFOX = "org.mozilla.firefox"


def firefox_mappen() -> list[Path]:
    """Waar Firefox zijn profielen kan hebben: ~/.mozilla/firefox (tot nu toe), ~/.config/mozilla/firefox (nieuwe
    gebruikers sinds Firefox 147), en dezelfde twee in de map van de Flatpak-Firefox. De map met een profiles.ini
    eerst; daarna de Flatpak (die heeft BugOS nu), dan de rest."""
    thuis = Path.home()
    config = Path(os.environ.get("XDG_CONFIG_HOME") or thuis / ".config")
    flatpak = thuis / ".var" / "app" / FLATPAK_FIREFOX
    mappen = [flatpak / ".mozilla" / "firefox", flatpak / "config" / "mozilla" / "firefox",
              thuis / ".mozilla" / "firefox", config / "mozilla" / "firefox"]
    return sorted(mappen, key=lambda m: not (m / "profiles.ini").is_file())


def _ini(pad: Path) -> configparser.RawConfigParser:
    ini = configparser.RawConfigParser(strict=False, interpolation=None)
    ini.optionxform = str   # Firefox schrijft IsRelative en Path met hoofdletters, en leest ze zo
    try:
        ini.read(pad, encoding="utf-8")
    except (OSError, configparser.Error, UnicodeDecodeError):
        pass
    return ini


def _schrijf_ini(ini: configparser.RawConfigParser, pad: Path) -> None:
    """Zoals Firefox: 'Sleutel=waarde' zonder spaties; eerst in een los bestand, dan in één keer op zijn plek."""
    tmp = pad.with_name(pad.name + ".bugos-nieuw")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        ini.write(f, space_around_delimiters=False)
    os.replace(tmp, pad)


def _profiel_pad(map_: Path, sectie) -> Path:
    pad = sectie.get("Path", "")
    return map_ / pad if sectie.get("IsRelative", "1") == "1" else Path(pad)


def standaard_profiel() -> Path | None:
    """Het profiel dat Firefox opent: wat [Install...] in profiles.ini zegt (Firefox 67+), anders het profiel met
    Default=1, anders het eerste. None als er nog geen profiel is (Firefox nooit gestart)."""
    for map_ in firefox_mappen():
        ini = _ini(map_ / "profiles.ini")
        for s in ini.sections():
            if s.startswith("Install") and ini[s].get("Default"):
                pad = map_ / ini[s]["Default"]
                if pad.is_dir():
                    return pad
        profielen = [ini[s] for s in ini.sections() if s.startswith("Profile") and ini[s].get("Path")]
        for p in profielen:
            if p.get("Default") == "1" and _profiel_pad(map_, p).is_dir():
                return _profiel_pad(map_, p)
        for p in profielen:
            if _profiel_pad(map_, p).is_dir():
                return _profiel_pad(map_, p)
    return None


def draait(profiel: Path | None = None) -> bool:
    """Staat Firefox open? Aan het slot in het profiel ('lock' wijst naar 'adres:+pid') en anders aan pgrep."""
    if profiel is not None:
        slot = profiel / "lock"
        try:
            doel = os.readlink(slot)
            pid = int(doel.rsplit("+", 1)[1])
            if Path(f"/proc/{pid}").exists():
                return True
        except (OSError, ValueError, IndexError):
            pass
    if shutil.which("pgrep"):
        for naam in ("firefox", "firefox-bin"):
            try:
                if subprocess.run(["pgrep", "-u", str(os.getuid()), "-x", naam], capture_output=True,
                                  timeout=5).returncode == 0:
                    return True
            except (OSError, subprocess.SubprocessError):
                pass
    return False


def firefox_opdracht() -> list[str] | None:
    """Hoe je Firefox start: de gewone 'firefox', anders de Flatpak ('flatpak run org.mozilla.firefox'), of None."""
    if shutil.which("firefox"):
        return ["firefox"]
    if shutil.which("flatpak"):
        try:
            if subprocess.run(["flatpak", "info", FLATPAK_FIREFOX], capture_output=True, timeout=15).returncode == 0:
                return ["flatpak", "run", FLATPAK_FIREFOX]
        except (OSError, subprocess.SubprocessError):
            pass
    return None


def maak_profiel() -> Path | None:
    """Nog nooit Firefox gestart: laat Firefox zelf zijn profiel maken (onzichtbaar, --headless met een schermfoto
    van een lege pagina; daarna stopt hij vanzelf). Zo klopt alles wat Firefox erbij zet (installs.ini ...)."""
    opdracht = firefox_opdracht()
    if opdracht is None:
        return None
    with tempfile.TemporaryDirectory(prefix="bugos-firefox-") as tmp:
        try:
            # Een Flatpak mag niet zomaar in /tmp schrijven; de schermfoto zelf hebben we niet nodig (alleen het profiel).
            subprocess.run(opdracht + ["--headless", "--screenshot", str(Path(tmp) / "leeg.png"), "about:blank"],
                           capture_output=True, timeout=120)
        except (OSError, subprocess.SubprocessError):
            return None
    return standaard_profiel()


def _zet_voorkeuren(profiel: Path, voorkeuren: dict[str, object]) -> None:
    """Zet voorkeuren in prefs.js (eerst de oude regels voor dezelfde naam weg). Alleen als Firefox dicht is."""
    pad = profiel / "prefs.js"
    try:
        regels = pad.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        regels = ['// Mozilla User Preferences']
    namen = [json.dumps(n) for n in voorkeuren]
    regels = [r for r in regels if not any(r.startswith(f"user_pref({n},") for n in namen)]
    for naam, waarde in voorkeuren.items():
        regels.append(f"user_pref({json.dumps(naam)}, {json.dumps(waarde, ensure_ascii=False)});")
    tmp = pad.with_name("prefs.js.bugos-nieuw")
    tmp.write_text("\n".join(regels) + "\n", encoding="utf-8")
    os.replace(tmp, pad)


def map_titel(computer: str) -> str:
    """De map op de bladwijzerbalk: 'Van Windows' (met de naam van de oude computer, als die er is)."""
    basis = t("Van Windows", "From Windows")
    computer = ot._tekst(computer, 40)
    return f"{basis} ({computer})" if computer else basis


def bladwijzers_naar_firefox(bronnen: list[Bron], computer: str = "", profiel: Path | None = None) -> ot.Uitslag:
    """Zet de bladwijzers van de stick in Firefox: in één map op de bladwijzerbalk, de rest blijft zoals het was.
    Firefox leest ze de volgende keer dat hij start."""
    lijst = [(b, lees_bron(b)) for b in bronnen]
    lijst = [(b, k) for b, k in lijst if k]
    if not lijst:
        return ot.Uitslag("bladwijzers", NIET, t("De bladwijzers op de stick waren niet te lezen.",
                                                 "The bookmarks on the drive could not be read."))
    titel = map_titel(computer)
    if bi.VOORBEELD:
        return ot.Uitslag("bladwijzers", GOED, t("Ze staan in Firefox, in de map '{m}' op de bladwijzerbalk.",
                                                 "They are in Firefox, in the '{m}' folder on the bookmarks toolbar.").format(m=titel))
    profiel = profiel or standaard_profiel()
    if profiel is None and not draait():
        profiel = maak_profiel()
    hand = t(" Met de hand: Firefox > Bladwijzers beheren > Importeren > HTML, en kies het bestand in Documenten.",
             " By hand: Firefox > Manage bookmarks > Import > HTML, and choose the file in Documents.")
    if profiel is None:
        return ot.Uitslag("bladwijzers", ZELF, t("Open Firefox één keer en druk dan nog eens op Overzetten.",
                                                 "Open Firefox once and then press Transfer again.") + hand)
    if draait(profiel):
        return ot.Uitslag("bladwijzers", ZELF, t("Firefox stond open. Sluit Firefox en druk nog eens op Overzetten "
                                                 "(alleen 'Bladwijzers' aan is genoeg).",
                                                 "Firefox was open. Close Firefox and press Transfer again "
                                                 "(only 'Bookmarks' on is enough)."))
    bestaand = bestaande_bladwijzers(profiel)
    if bestaand is None:
        # Niet te lezen: inlezen zou ze vervangen, dus nu niets doen.
        return ot.Uitslag("bladwijzers", ZELF, t("BugOS kon je huidige Firefox-bladwijzers niet lezen, dus heeft hij niets "
                                                 "veranderd.", "BugOS could not read your current Firefox bookmarks, so it "
                                                 "changed nothing.") + hand)
    if any(k.get("titel") == titel and "kinderen" in k for k in bestaand["balk"]):
        return ot.Uitslag("bladwijzers", GOED, t("Ze stonden al in Firefox (map '{m}').",
                                                 "They were already in Firefox ('{m}' folder).").format(m=titel))
    # Eén bron: alles direct in de map. Meer: een map per browserprofiel.
    if len(lijst) == 1:
        nieuw = lijst[0][1]
    else:
        nieuw = [{"titel": b.naam, "kinderen": k} for b, k in lijst]
    balk = list(bestaand["balk"]) + [{"titel": titel, "kinderen": nieuw}]
    bestand = profiel / EIGEN_BESTAND
    try:
        bestand.write_text(bladwijzer_html(bestaand["menu"], balk, bestaand["andere"]), encoding="utf-8")
        voorkeuren = {"browser.places.importBookmarksHTML": True,
                      "browser.bookmarks.file": str(bestand),
                      "browser.bookmarks.restore_default_bookmarks": False}
        _zet_voorkeuren(profiel, voorkeuren)
        # Voor 'Alles terugdraaien': zolang Firefox ze nog niet inlas, kunnen deze voorkeuren weer weg.
        ot._onthoud("firefox_voorkeuren", profiel=str(profiel), namen=list(voorkeuren), map=titel)
    except OSError:
        return ot.Uitslag("bladwijzers", ZELF, t("Opslaan in Firefox lukte niet.", "Saving into Firefox did not work.") + hand)
    return ot.Uitslag("bladwijzers", GOED, t("Ze staan in Firefox, in de map '{m}' op de bladwijzerbalk (zodra je Firefox "
                                             "opent).", "They are in Firefox, in the '{m}' folder on the bookmarks "
                                             "toolbar (as soon as you open Firefox).").format(m=titel))


# ============================================================ profiel overnemen ===

def profiel_op_stick(bron: Path, i: dict) -> Path | None:
    """De map van het Firefox-profiel op de stick (firefox_profiel), alleen als het echt een profiel is."""
    pad = ot.binnen_stick(bron, i.get("firefox_profiel"))
    try:
        if pad is None or not pad.is_dir() or not ((pad / "prefs.js").is_file() or (pad / "places.sqlite").is_file()):
            return None
    except OSError:
        return None
    return pad


_WINDOWS_PAD = re.compile(r'"[A-Za-z]:\\\\|"\\\\\\\\')   # "C:\\... of "\\\\server in prefs.js


def _niet_kopieren(map_: str, namen: list[str]) -> set[str]:
    """Voor copytree: wachtwoorden, cookies, wat Firefox zelf opnieuw maakt, en links (een stick heeft die niet, en
    een link kan overal heen wijzen)."""
    return {n for n in namen if n in NOOIT_MEE or n in NIET_NODIG or os.path.islink(os.path.join(map_, n))}


def profiel_erbij(map_: Path, bron_profiel: Path, naam: str, achtervoegsel: str,
                  ook_niet: frozenset[str] = frozenset()) -> str:
    """Kopieer een profiel van de stick naar map_ (de map met profiles.ini) als nieuw profiel 'naam', en maak het het
    standaardprofiel. Voor Firefox én Thunderbird (zelfde opbouw). ook_niet: mappen die ook thuisblijven
    (Thunderbird: ImapMail). Het profiel dat er al was, blijft staan (als reserve).

    Alles komt in het logboek (profielmap, profiles.ini en installs.ini zoals ze waren), zodat 'Alles terugdraaien'
    het nieuwe profiel naar de prullenbak kan zetten en het oude weer standaard maakt.
    Geeft '' (gelukt), 'kopie' (kopiëren lukte niet) of 'ini' (het profiel staat er, maar kiezen lukte niet)."""
    ini_pad = map_ / "profiles.ini"
    installs_pad = map_ / "installs.ini"
    ini = _ini(ini_pad)
    profielen = [s for s in ini.sections() if s.startswith("Profile")]
    doel = map_ / f"{secrets.token_hex(4)}.{achtervoegsel}"

    def niet(m: str, namen: list[str]) -> set[str]:
        return _niet_kopieren(m, namen) | {n for n in namen if n in ook_niet}

    try:
        import bugos_overstap_logboek as lb
        lb.maak_map(map_)   # een nieuwe map (Thunderbird nog nooit gestart) ook onthouden, voor terugdraaien
        shutil.copytree(bron_profiel, doel, ignore=niet, symlinks=True)
        prefs = doel / "prefs.js"
        if prefs.is_file():
            regels = prefs.read_text(encoding="utf-8", errors="replace").splitlines()
            # Een map op C:\ (downloads, de laatste map, een mailmap) bestaat hier niet: weg ermee, dan neemt het
            # programma zijn eigen (Thunderbird valt dan terug op de '-rel'-variant, bijv. [ProfD]Mail/...).
            prefs.write_text("\n".join(r for r in regels if not _WINDOWS_PAD.search(r)) + "\n", encoding="utf-8")
    except (OSError, shutil.Error):
        shutil.rmtree(doel, ignore_errors=True)
        return "kopie"
    ot._onthoud("profielmap", pad=str(doel))
    # Hoe profiles.ini en installs.ini nu zijn (None: er was er nog geen), vóór we ze veranderen.
    for p in (ini_pad, installs_pad):
        try:
            ot._onthoud("ini", pad=str(p), inhoud=p.read_text(encoding="utf-8") if p.is_file() else None)
        except OSError:
            pass
    nummer = 0
    while f"Profile{nummer}" in ini.sections():
        nummer += 1
    ini[f"Profile{nummer}"] = {"Name": naam, "IsRelative": "1", "Path": doel.name}
    installaties = [s for s in ini.sections() if s.startswith("Install")]
    if installaties:
        # Firefox/Thunderbird 67+: elke installatie heeft zijn eigen standaard. Die wordt het nieuwe profiel.
        for s in installaties:
            ini[s]["Default"] = doel.name
            ini[s]["Locked"] = "1"
    else:
        # Nog geen installatie bekend (bijvoorbeeld Thunderbird nog nooit gestart): het profiel met Default=1. Bij de
        # eerste start neemt het programma dat standaardprofiel over.
        for s in profielen:
            ini[s].pop("Default", None)
        ini[f"Profile{nummer}"]["Default"] = "1"
    if not ini.has_section("General"):
        ini["General"] = {"StartWithLastProfile": "1", "Version": "2"}
    ini["General"]["StartWithLastProfile"] = "1"
    try:
        _schrijf_ini(ini, ini_pad)
        if installs_pad.is_file():
            installs = _ini(installs_pad)
            for s in installs.sections():
                installs[s]["Default"] = doel.name
                installs[s]["Locked"] = "1"
            _schrijf_ini(installs, installs_pad)
    except OSError:
        return "ini"
    return ""


def profiel_overnemen(bron_profiel: Path, computer: str = "") -> ot.Uitslag:
    """Kopieer het Firefox-profiel van Windows naar BugOS en maak het het profiel dat Firefox opent. Het profiel dat
    er al was, blijft (als reserve)."""
    naam = map_titel(computer)
    if bi.VOORBEELD:
        return ot.Uitslag("firefox", GOED, t("Firefox opent nu met je profiel van Windows.",
                                             "Firefox now opens with your profile from Windows."))
    oud = standaard_profiel()
    if oud is None and not draait():
        oud = maak_profiel()
    if oud is None:
        return ot.Uitslag("firefox", ZELF, t("Open Firefox één keer en druk dan nog eens op Overzetten.",
                                             "Open Firefox once and then press Transfer again."))
    if draait(oud):
        return ot.Uitslag("firefox", ZELF, t("Firefox stond open. Sluit Firefox en druk nog eens op Overzetten.",
                                             "Firefox was open. Close Firefox and press Transfer again."))
    map_ = oud.parent
    if any(_ini(map_ / "profiles.ini")[s].get("Name") == naam for s in _ini(map_ / "profiles.ini").sections()
           if s.startswith("Profile")):
        return ot.Uitslag("firefox", GOED, t("Je profiel van Windows stond er al ('{n}').",
                                             "Your profile from Windows was already there ('{n}').").format(n=naam))
    fout = profiel_erbij(map_, bron_profiel, naam, "van-windows")
    if fout == "kopie":
        return ot.Uitslag("firefox", ZELF, t("Kopiëren lukte niet (is je computer vol, of is de stick eruit?). Probeer het "
                                             "opnieuw.", "Copying did not work (is your computer full, or was the drive "
                                             "unplugged?). Try again."))
    if fout == "ini":
        return ot.Uitslag("firefox", ZELF, t("Het profiel staat er, maar Firefox kiezen lukte niet. Open about:profiles in "
                                             "Firefox en kies '{n}'.", "The profile is there, but choosing it did not "
                                             "work. Open about:profiles in Firefox and choose '{n}'.").format(n=naam))
    return ot.Uitslag("firefox", GOED, t("Firefox opent nu met je profiel van Windows (zonder wachtwoorden: log opnieuw in "
                                         "op je sites). Je vorige BugOS-Firefox staat er nog, in about:profiles.",
                                         "Firefox now opens with your profile from Windows (without passwords: sign in to "
                                         "your sites again). Your previous BugOS Firefox is still there, in about:profiles."))
