#!/usr/bin/env python3
"""Test van de BugOS Winkel zonder KDE Discover (pakket 'store'): alle apps van Flathub in de Winkel zelf.

De lijst van Flathub (appstream), flatpak, busctl en de rest zijn nep: alles gebeurt in een tijdelijke map, zonder
internet en zonder je echte apps aan te raken.
Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_native_store.py
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"
BRON = ROOT / "system_files" / "usr" / "bin" / "bugos-store"
sys.path.insert(0, str(PY))
sys.dont_write_bytecode = True
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

TMP = Path(tempfile.mkdtemp(prefix="bugos-store-test-"))
THUIS = TMP / "thuis"
(THUIS / ".config").mkdir(parents=True)
os.environ["HOME"] = str(THUIS)
os.environ["XDG_DATA_HOME"] = str(THUIS / ".local" / "share")
os.environ["XDG_CONFIG_HOME"] = str(THUIS / ".config")
os.environ["XDG_CACHE_HOME"] = str(TMP / "cache")
os.environ["BUGOS_APPSTREAM"] = str(TMP / "appstream")
os.environ["LC_ALL"] = "nl_NL.UTF-8"   # de test kijkt naar de Nederlandse teksten
os.environ["BUGOS_MEERDERE"] = "1"
for _weg in ("LANGUAGE", "BUGOS_GEINSTALLEERD", "BUGOS_INSTELLINGEN_VOORBEELD", "BUGOS_WINKEL_VOORBEELD",
             "BUGOS_WINKEL_GEEN_VERVERS", "BUGOS_TEST_GEEN_CACHE", "BUGOS_TEST_GEEN_NET", "BUGOS_TEST_VERVERS_HANGT",
             "BUGOS_TEST_LIJST_NAAR", "BUGOS_TEST_LIJST_XML"):
    os.environ.pop(_weg, None)

NEP = TMP / "nep-bin"
NEP.mkdir()
LOG = TMP / "flatpak.log"
LOG.write_text("")


def nep_programma(naam: str, inhoud: str) -> None:
    (NEP / naam).write_text("#!/usr/bin/bash\n" + inhoud)
    (NEP / naam).chmod(0o755)


# Een nep-flatpak: schrijft elke opdracht in flatpak.log en antwoordt zoals de echte (TAB tussen de kolommen).
# (Het script springt in met 4 spaties per stap, zoals alle code in BugOS.)
nep_programma("flatpak", f'''echo "$*" >> "{LOG}"
case "$1 $2 $3" in
    "list --app --columns=application") printf 'org.voorbeeld.Oud\\n'; exit 0 ;;
    "list --app --columns=application,name,origin") printf 'org.voorbeeld.Oud\\tOud\\tflathub\\n'; exit 0 ;;
    "list --runtime --columns=ref") printf 'org.gnome.Platform/x86_64/49\\n'; exit 0 ;;
esac
if [ "$1" = remote-ls ]; then
    # Zo zegt de echte flatpak het (nagegaan op Kinoite 44): een gewone gebruiker zonder eigen cache krijgt bij
    # --cached 'No cached summary'; zonder --cached haalt hij de samenvatting op, en zonder internet faalt dat.
    if [ "$2" = --cached ] && [ -n "$BUGOS_TEST_GEEN_CACHE" ]; then
        echo "error: Unable to load summary from remote flathub: No cached summary for remote 'flathub'" >&2; exit 1
    fi
    if [ "$2" != --cached ] && [ -n "$BUGOS_TEST_GEEN_NET" ]; then
        echo "error: Unable to load summary from remote flathub: [6] Could not resolve hostname" >&2; exit 1
    fi
    printf 'app/org.voorbeeld.Radio/x86_64/stable\\t5.5\\302\\240MB\\t12.3\\302\\240MB\\torg.gnome.Platform/x86_64/49\\n'
    printf 'app/org.voorbeeld.Groot/x86_64/stable\\t50.0\\302\\240MB\\t120.4\\302\\240MB\\torg.freedesktop.Platform/x86_64/25.08\\n'
    printf 'app/org.voorbeeld.Oud/x86_64/stable\\t309.7\\302\\240MB\\t15.9\\302\\240MB\\torg.freedesktop.Platform/x86_64/25.08\\n'
    printf 'runtime/org.freedesktop.Platform/x86_64/25.08\\t260.1\\302\\240MB\\t670.7\\302\\240MB\\t\\n'
    printf 'runtime/org.gnome.Platform/x86_64/49\\t418.8\\302\\240MB\\t1.1\\302\\240GB\\t\\n'
    exit 0
fi
if [ "$1" = install ]; then
    /usr/bin/sleep 0.3
    [ "${{BUGOS_TEST_FLATPAK:-0}}" = 9 ] && echo "error: Not authorized" && exit 1
    [ "${{BUGOS_TEST_FLATPAK:-0}}" = 8 ] && echo "error: No space left on device" && exit 1
    [ "${{BUGOS_TEST_FLATPAK:-0}}" = 7 ] && echo "error: Nothing matches $4 in remote flathub" && exit 1
    exit "${{BUGOS_TEST_FLATPAK:-0}}"
fi
if [ "$1" = update ]; then
    # Een verbinding die blijft haperen: flatpak komt niet terug. Met exec, zodat de kill van de Winkel (na 2
    # minuten, in de test korter) precies dit proces raakt, zoals bij de echte flatpak.
    [ -n "$BUGOS_TEST_VERVERS_HANGT" ] && exec /usr/bin/sleep 30
    [ -n "$BUGOS_TEST_VERVERS_SLAAP" ] && /usr/bin/sleep "$BUGOS_TEST_VERVERS_SLAAP"
    # Gelukt en een lijst gevraagd (test 16): zet hem neer zoals flatpak dat doet, in een map met een controlegetal
    # als naam, 'active' wijst ernaar, en .timestamp wordt nu.
    if [ "${{BUGOS_TEST_VERVERS:-0}}" = 0 ] && [ -n "$BUGOS_TEST_LIJST_XML" ]; then
        /usr/bin/mkdir -p "$BUGOS_TEST_LIJST_NAAR/{"c" * 64}"
        /usr/bin/cp "$BUGOS_TEST_LIJST_XML" "$BUGOS_TEST_LIJST_NAAR/{"c" * 64}/appstream.xml"
        /usr/bin/ln -sfn "{"c" * 64}" "$BUGOS_TEST_LIJST_NAAR/active"
        /usr/bin/touch "$BUGOS_TEST_LIJST_NAAR/.timestamp"
    fi
    exit "${{BUGOS_TEST_VERVERS:-0}}"
fi
exit 0
''')
nep_programma("plasma-discover", f'touch "{TMP}/discover-gestart"\n')
nep_programma("busctl", '''case "$*" in
  *NetworkManager*Metered*) echo "u ${BUGOS_TEST_METERED:-4}" ;;
  *login1*Active*) echo "b ${BUGOS_TEST_ACTIEF:-true}" ;;
  *) exit 1 ;;
esac
''')
nep_programma("kioclient", f'echo "kioclient $*" >> "{LOG}"\n')
nep_programma("xdg-open", f'echo "xdg-open $*" >> "{LOG}"\n')
os.environ["PATH"] = f"{NEP}:/usr/bin:/bin"

fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


def laad(naam: str):
    lader = importlib.machinery.SourceFileLoader(naam, str(BRON))
    spec = importlib.util.spec_from_loader(naam, lader)
    m = importlib.util.module_from_spec(spec)
    sys.modules[naam] = m
    lader.exec_module(m)
    return m


BRONTEKST = BRON.read_text(encoding="utf-8")

# ============================================================== 11. geen KDE Discover meer in de Winkel ===
klopt("plasma-discover" not in BRONTEKST and "Discover" not in BRONTEKST,
      "11: de Winkel start nergens KDE Discover (en noemt het niet)")

winkel = laad("bugos_winkel_test")
import bugos_ui  # noqa: E402
from PySide6.QtCore import QElapsedTimer, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication.instance() or bugos_ui.maak_app("bugos-test", "bugos-test", ["test"])
gestart: list = []
winkel.start = lambda *a: gestart.append(a) or True
APPS = TMP / "applications"
APPS.mkdir()
winkel.APP_MAPPEN = [APPS]
CAT = winkel.lees_catalogus(ROOT / "system_files" / "usr" / "share" / "bugos" / "store.json")


def wacht(voorwaarde, ms: int = 8000) -> bool:
    klok = QElapsedTimer()
    klok.start()
    while not voorwaarde() and klok.elapsed() < ms:
        app.processEvents()
    return bool(voorwaarde())


def even(ms: int) -> None:
    wacht(lambda: False, ms)


# ============================================================== 1. geen sprong meer, alles in de Winkel ===
os.environ["BUGOS_WINKEL_GEEN_VERVERS"] = "1"   # het verversen van de lijst komt bij 9
w = winkel.Winkel(CAT)
wacht(lambda: w.flathub is not None)
w.resize(1180, 760)
w.show()
w.activateWindow()
from PySide6.QtTest import QTest  # noqa: E402

QTest.qWaitForWindowActive(w, 2000)
w.tweede_start(["appstream://org.mozilla.firefox"])
klopt(w.stapel.currentIndex() == 0 and w.zoek.text() == "Firefox",
      f"1: een app uit de BugOS-selectie: de lijst met die app ({w.zoek.text()!r})")
w.tweede_start(["appstream://org.example.NietBijOns"])
klopt(w.stapel.currentIndex() == 1 and w.pagina_id == "org.example.NietBijOns" and gestart == [],
      f"1: een onbekende app: een eigen pagina in de Winkel, geen ander programma ({w.pagina_id}, {gestart})")
w.tweede_start(["appstream:org.videolan.vlc"])
klopt(w.stapel.currentIndex() == 0 and w.zoek.text() == "VLC",
      "1: daarna een app uit de selectie (kleine letters, zonder //): terug naar de lijst met VLC (U330)")
w.tweede_start(["appstream://-rf.x.y"])
klopt(w.stapel.currentIndex() == 0 and gestart == [], "1: een id met '-' vooraan wordt nooit iets (geen optie)")
w.zoek.setText("radio")
w.toon_app("org.example.NietBijOns")
w.terug()
klopt(w.stapel.currentIndex() == 0 and w.zoek.text() == "radio" and w.pagina_id is None,
      "1: Terug: de lijst weer, met dezelfde zoektekst")
w.toon_app("org.example.NietBijOns")
w.pagina.terug.setFocus()
QTest.keyClick(w.pagina.terug, Qt.Key.Key_Escape)
klopt(w.stapel.currentIndex() == 0, "1: Esc op de app-pagina = terug naar de lijst")
w.toon_app("org.example.NietBijOns")
w.lijst.setCurrentRow(1)
klopt(w.stapel.currentIndex() == 0, "1: een onderwerp in de zijbalk kiezen terwijl een app-pagina open is: de lijst")
w.zoek.setText("")
w.meer_apps()
klopt(gestart == [] and w.focusWidget() is w.zoek and "Typ hierboven" in w.opdracht_melding.tekst.text(),
      f"1: 'Alle apps doorzoeken' start niets, maar zet je in het zoekveld ({w.opdracht_melding.tekst.text()!r})")
w.zoek.setText("qqqzzz")
w.zoek_meer()
klopt("is er nog niet" in w.meer_status.text() and w.meer_knop_ophalen.isVisibleTo(w) and "Niets gevonden" not in
      w.melding.tekst.text(),
      "1: nog geen lijst van Flathub: dat zegt de Winkel (met 'Nu ophalen'), niet 'niets gevonden'")
w.close()
klopt(not (TMP / "discover-gestart").exists(), "1: KDE Discover is nooit gestart")

# ============================================================== de nep-lijst van Flathub (appstream) ===
SOM1, SOM2 = "a" * 64, "b" * 64
OUD_ID = "org.voorbeeld.Oud"


def component(app_id: str, naam: str, kort: str = "Een app", soort: str = "desktop-application", extra: str = "",
              met_bundel: bool = True, maker: str = "Iemand", id_tekst: str | None = None) -> str:
    bundel = f'<bundle type="flatpak">app/{app_id}/x86_64/stable</bundle>' if met_bundel else ""
    id_el = f"<id>{id_tekst if id_tekst is not None else app_id}</id>" if id_tekst != "" else ""
    return (f'<component type="{soort}">{id_el}<name>{naam}</name><summary>{kort}</summary>'
            f'<developer><name>{maker}</name></developer>{extra}{bundel}</component>')


RADIO = component(
    "org.voorbeeld.Radio", "Radio", "Luister naar de radio over internet",
    extra=('<name xml:lang="nl">Radio NL</name><summary xml:lang="nl">Radio luisteren</summary>'
           '<developer><name xml:lang="be">Кто-то</name></developer>'
           '<icon type="cached" height="64">org.voorbeeld.Radio.png</icon>'
           '<icon type="cached" height="128">org.voorbeeld.Radio.png</icon>'
           '<url type="homepage">https://radio.example.org/</url>'
           '<custom><value key="flathub::verification::verified">true</value>'
           '<value key="flathub::verification::website">radio.example.org</value></custom>'
           '<content_rating type="oars-1.1"><content_attribute id="social-chat">intense</content_attribute>'
           '<content_attribute id="money-purchasing">mild</content_attribute></content_rating>'
           '<keywords><keyword>stream</keyword></keywords><keywords xml:lang="de"><keyword>rundfunk</keyword></keywords>'
           '<description xml:lang="be"><p>Беларуская</p></description>'
           '<description><p>Radio is a  radio\nplayer.</p><ul><li>Many stations</li><li>Small</li></ul></description>'),
    maker="Radiomakers")
GIMPACHTIG = component(
    "org.voorbeeld.Teken", "Teken", "Tekenen en foto's bewerken",
    extra=('<description xml:lang="be"><p>Першы</p></description><description xml:lang="be"><p>Другі</p></description>'
           '<description><p>' + "Lang verhaal " * 80 + '</p></description>'
           '<content_rating type="oars-1.1"/>'))
APPS_XML = [
    RADIO, GIMPACHTIG,
    component(OUD_ID, "Oud", id_tekst=OUD_ID + ".desktop"),   # oude stijl: het id eindigt op .desktop
    component("org.videolan.VLC", "VLC", "Video"),   # een app uit de BugOS-selectie
    component("org.voorbeeld.Radio.Plugin", "Radio plug-in", soort="addon",
              extra="<extends>org.voorbeeld.Radio</extends>"),
    component("org.voorbeeld.Platform", "Voorbeeld Platform", soort="runtime"),
    component("org.voorbeeld.Klok", "klok-cli", soort="console-application"),
    component("org.voorbeeld.Zonder", "Zonder id", id_tekst="", met_bundel=False),
    component("-x.y.z", "Slecht"),
    component("org.voorbeeld.Radio", "Dubbel"),   # zelfde id nog eens: de eerste telt
    component("org.voorbeeld.Cafe", "Café Müzik", "Muziek uit Istanbul", extra='<content_rating type="oars-1.1"/>'),
    component("org.kde.dolphin", "Dolphin", "File manager"),   # zit in BugOS zelf (I1)
    component("org.kde.skanpage", "Skanpage", "Scan documents"),
    component("org.voorbeeld.Groot", "Groot", "Een grote app", extra='<content_rating type="oars-1.1"/>'),
    component("org.voorbeeld.Niet", "Niet", "Niet gecontroleerd", maker=""),
] + [component(f"org.voorbeeld.Muziek{i}", f"Muziekspeler {i}", "Speelt muziek af") for i in range(25)]


def maak_appstream(som: str, apps: list[str], gz: bool = False) -> Path:
    bron = TMP / "appstream"
    (bron / som / "icons" / "128x128").mkdir(parents=True, exist_ok=True)
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<components version="0.8" origin="flathub">' + "".join(apps) + \
          "</components>\n"
    if gz:
        import gzip
        (bron / som / "appstream.xml.gz").write_bytes(gzip.compress(xml.encode()))
        (bron / som / "appstream.xml").unlink(missing_ok=True)
    else:
        (bron / som / "appstream.xml").write_text(xml, encoding="utf-8")
    actief = bron / "active"
    if actief.is_symlink() or actief.exists():
        actief.unlink()
    actief.symlink_to(som)
    (bron / ".timestamp").touch()
    return bron


BRONMAP = maak_appstream(SOM1, APPS_XML)

# ============================================================== 1. de lijst lezen ===
_extra: dict = {}
apps = winkel.lees_appstream(BRONMAP / "active", _extra)
_ids = [a["id"] for a in apps]
klopt("org.voorbeeld.Radio" in _ids and OUD_ID in _ids and "org.videolan.VLC" in _ids
      and not {"org.voorbeeld.Radio.Plugin", "org.voorbeeld.Platform", "org.voorbeeld.Klok", "-x.y.z"} & set(_ids)
      and _ids.count("org.voorbeeld.Radio") == 1,
      f"F1: alleen apps met een venster, met een goed id, elk één keer ({len(_ids)} apps)")
radio = next(a for a in apps if a["id"] == "org.voorbeeld.Radio")
klopt(set(radio) == {"id", "naam", "naam_nl", "kort", "kort_nl", "uitleg", "uitleg_nl", "maker", "icoon", "echt",
                     "echt_site", "oars", "woorden", "site"}, "F1: elke app heeft precies de afgesproken velden")
klopt(radio["naam"] == "Radio" and radio["naam_nl"] == "Radio NL" and radio["kort_nl"] == "Radio luisteren"
      and radio["maker"] == "Radiomakers", f"F1: namen per taal, en de maker zonder taal (niet het Cyrillisch): {radio['maker']!r}")
klopt(radio["uitleg"] == "Radio is a radio player.\n• Many stations\n• Small" and radio["uitleg_nl"] == "",
      f"F1: de gewone beschrijving (niet de Wit-Russische), lijstjes met '• ': {radio['uitleg']!r}")
_teken = next(a for a in apps if a["id"] == "org.voorbeeld.Teken")
klopt(len(_teken["uitleg"]) <= 701 and _teken["uitleg"].endswith("…") and "Перш" not in _teken["uitleg"],
      f"F1: een lange beschrijving wordt netjes afgekapt ({len(_teken['uitleg'])} tekens)")
klopt(radio["woorden"] == "stream" and radio["echt"] and radio["echt_site"] == "radio.example.org"
      and radio["oars"] == {"social-chat": "intense", "money-purchasing": "mild"} and radio["icoon"] == "org.voorbeeld.Radio.png"
      and radio["site"] == "https://radio.example.org/",
      "F1: trefwoorden zonder Duits, gecontroleerde maker met site, leeftijdsgegevens, pictogram, website")
klopt(next(a for a in apps if a["id"] == OUD_ID)["oars"] is None and _teken["oars"] == {},
      "F1: geen leeftijdsgegevens = None, leeg = voor iedereen")
klopt(_extra["hoort_bij"] == {"org.voorbeeld.Radio.Plugin": "org.voorbeeld.Radio"}
      and _extra["geen_app"].get("org.voorbeeld.Platform", [""])[1] == "onderdeel"
      and _extra["geen_app"].get("org.voorbeeld.Klok", [""])[1] == "terminal",
      f"I3: uitbreidingen en onderdelen worden onthouden ({_extra['hoort_bij']}, {sorted(_extra['geen_app'])})")

# 2. alleen het .gz-bestand
_gz = TMP / "gz"
_gz.mkdir()
import gzip  # noqa: E402

(_gz / "appstream.xml.gz").write_bytes(gzip.compress((BRONMAP / "active" / "appstream.xml").read_bytes()))
klopt([a["id"] for a in winkel.lees_appstream(_gz)] == _ids, "F1: ook als er alleen appstream.xml.gz is")

# 3. de index en de cache
CACHE = TMP / "cache" / "bugos"
idx = winkel.flathub_index(BRONMAP, CACHE)
klopt(len(idx["apps"]) == len(_ids) and (CACHE / f"store-flathub-{SOM1}.json").is_file(),
      "F1: de index wordt gemaakt en bewaard in je eigen cache")
_echt_lees = winkel.lees_appstream


def _kapot(*a, **k):
    raise RuntimeError("niet opnieuw lezen")


winkel.lees_appstream = _kapot
klopt(len(winkel.flathub_index(BRONMAP, CACHE)["apps"]) == len(_ids), "F1: de tweede keer uit de cache (niet opnieuw lezen)")
winkel.lees_appstream = _echt_lees
maak_appstream(SOM2, APPS_XML[:3])
idx2 = winkel.flathub_index(BRONMAP, CACHE)
klopt(len(idx2["apps"]) == 3 and (CACHE / f"store-flathub-{SOM2}.json").is_file()
      and not (CACHE / f"store-flathub-{SOM1}.json").exists(),
      "F1: een nieuwe lijst van Flathub: een nieuwe index, de oude cache weg")
(CACHE / f"store-flathub-{SOM2}.json").write_text("{kapot")
klopt(len(winkel.flathub_index(BRONMAP, CACHE)["apps"]) == 3, "F1: een kapotte cache wordt opnieuw gemaakt")
(BRONMAP / SOM2 / "appstream.xml").write_text("<components><component")
(CACHE / f"store-flathub-{SOM2}.json").unlink()
klopt(winkel.flathub_index(BRONMAP, CACHE)["apps"] == [], "F1: een kapotte lijst geeft gewoon geen apps (geen fout)")
klopt(winkel.flathub_index(TMP / "bestaat-niet", CACHE)["apps"] == [], "F1: geen lijst op de computer: geen apps")
maak_appstream(SOM1, APPS_XML)
for _f in CACHE.glob("*.json"):
    _f.unlink()
klopt(winkel.maak_index_apart(BRONMAP, CACHE) and (CACHE / f"store-flathub-{SOM1}.json").is_file(),
      "I11: de index kan in een eigen proces gemaakt worden (dan hapert het typen niet)")
klopt(winkel.index_sleutel(BRONMAP) == SOM1, "I10: de sleutel is de map waar 'active' echt naar wijst")

# 4. zoeken
idx = winkel.flathub_index(BRONMAP, CACHE)
_pick_ids = {a["id"].lower() for a in CAT["apps"]}


def zoek(tekst: str, uit: set | None = None) -> list[str]:
    return [e["id"] for e in winkel.zoek_flathub(idx["apps"], tekst, _pick_ids if uit is None else uit)]


klopt(zoek("radio")[:1] == ["org.voorbeeld.Radio"], f"F2: 'radio' vindt Radio als eerste ({zoek('radio')[:3]})")
klopt(zoek("Radio NL")[:1] == ["org.voorbeeld.Radio"] and zoek("stream") == ["org.voorbeeld.Radio"],
      "F2: ook op de Nederlandse naam en op trefwoorden")
klopt(zoek("radio xyz") == [] and zoek("r") == [], "F2: elk woord moet passen (U268), en één letter zoekt niets")
klopt(zoek("cafe muzik") == ["org.voorbeeld.Cafe"] and zoek("CAFÉ") == ["org.voorbeeld.Cafe"],
      "F2: zonder accenten en hoofdletters (U268)")
klopt("org.videolan.VLC" not in zoek("vlc") and "org.videolan.VLC" in zoek("vlc", set()),
      "F2: een app uit de BugOS-selectie staat niet nog eens bij Flathub")
_gelijk = [{"id": "a.b.Een", "naam": "Speler", "echt": False}, {"id": "a.b.Twee", "naam": "Speler", "echt": True}]
klopt([e["id"] for e in winkel.zoek_flathub(_gelijk, "speler", set())] == ["a.b.Twee", "a.b.Een"],
      "F2: bij gelijke namen eerst de gecontroleerde maker")
klopt(zoek("skanpage") == ["org.kde.skanpage"], "I12: 'skanpage' (niet in de BugOS-selectie) vindt hij bij Flathub")

# 5. leeftijd
klopt(winkel.leeftijd(None) is None and winkel.leeftijd({}) == 0 and winkel.leeftijd(radio["oars"]) == 13
      and winkel.leeftijd({"violence-worship": "mild"}) == 13 and winkel.leeftijd({"onbekend": "intense", "sex-themes": "raar"}) == 0,
      "F3: de leeftijd zoals libappstream hem rekent (en onbekende dingen tellen niet)")
klopt(winkel.leeftijd_redenen(radio["oars"]) == ["contact met anderen online"]
      and winkel.leeftijd_redenen({"social-audio": "intense", "money-purchasing": "intense"}) ==
      ["geld uitgeven of gokken", "contact met anderen online"],
      "F3: waarom die leeftijd, in gewone woorden en in een vaste volgorde")

# 6. groottes
klopt(winkel.grootte_bytes("309.7 MB") == 309_700_000 and winkel.grootte_bytes("747.7 kB") == 747_700
      and winkel.grootte_bytes("1.2 GB") == 1_200_000_000 and winkel.grootte_bytes("12 bytes") == 12
      and winkel.grootte_bytes("veel") is None and winkel.grootte_bytes("") is None,
      "F3: groottes van flatpak (met harde spatie, 1000 per stap)")
_g = winkel.lees_groottes("app/x.y.Z/x86_64/stable\t5.5 MB\t12.3 MB\torg.gnome.Platform/x86_64/49\n"
                          "runtime/org.gnome.Platform/x86_64/49\t418.8 MB\t1.1 GB\t\nrommel\n")
klopt(_g == {"app/x.y.Z/x86_64/stable": (5_500_000, 12_300_000, "org.gnome.Platform/x86_64/49"),
             "runtime/org.gnome.Platform/x86_64/49": (418_800_000, 1_100_000_000, "")},
      f"F3: remote-ls lezen, ook het gedeelde onderdeel ({_g})")
klopt(winkel.grootte_tekst(1_200_000_000) == "1,2 GB" and winkel.grootte_tekst(12_300_000) == "12 MB"
      and winkel.grootte_tekst(300_000) == "1 MB", "F3: groottes in het Nederlands met een komma (U237)")

# ============================================================== 7. links en bestanden ===
o = winkel.opdracht_uit
D = TMP / "downloads met spatie"
D.mkdir()
ZOOM = ("[Flatpak Ref]\nName=us.zoom.Zoom\nBranch=stable\nTitle=us.zoom.Zoom from flathub\nIsRuntime=false\n"
        "Url=https://dl.flathub.org/repo/\nSuggestRemoteName=flathub\nGPGKey=mQINBFlD2sABEADsiUZUOYBg1UdDaWkEdJYkTSZD\n"
        "RuntimeRepo=https://dl.flathub.org/repo/flathub.flatpakrepo\n")


def bestand(naam: str, inhoud: str | bytes) -> str:
    (D / naam).write_bytes(inhoud if isinstance(inhoud, bytes) else inhoud.encode())
    return str(D / naam)


klopt(o(["--zoek", "foto", "bewerken"]) == ("foto bewerken", "", "") and o(["appstream://org.voorbeeld.Radio"]) ==
      ("", "org.voorbeeld.Radio", "") and o(["appstream:org.voorbeeld.radio.desktop"]) == ("", "org.voorbeeld.radio", ""),
      "7: --zoek en appstream-links (ook zonder // en met .desktop)")
klopt(o(["flatpak+https://dl.flathub.org/repo/appstream/org.voorbeeld.Radio.flatpakref"]) == ("", "org.voorbeeld.Radio", "")
      and o(["https://dl.flathub.org/repo/appstream/org.voorbeeld.Radio.flatpakref"]) == ("", "org.voorbeeld.Radio", "")
      and o(["flatpak+https://dl.flathub.org/repo/elders/org.voorbeeld.Radio.flatpakref"])[2] == "andere_bron"
      and o(["https://evil.example/repo/appstream/x.y.z.flatpakref"])[2] == "andere_bron"
      and o(["flatpak+https://dl.flathub.org/repo/appstream/-rf.y.z.flatpakref"])[2] == "andere_bron",
      "7: een Flathub-link geeft de app (zonder iets te downloaden); elke andere link wordt geweigerd")
klopt(o(["https://dl.flathub.org/beta-repo/appstream/org.voorbeeld.Radio.flatpakref"]) == ("Radio", "", "test_versie"),
      "7/I10: een link naar Flathub Beta: 'testversie', niet 'een andere appwinkel'")
klopt(o([bestand("us.zoom.Zoom.flatpakref", ZOOM)]) == ("", "us.zoom.Zoom", ""),
      "7: het echte .flatpakref-bestand van Zoom (de knop 'Install' op flathub.org) geeft Zoom")
klopt(o([bestand("ander.flatpakref", ZOOM.replace("https://dl.flathub.org/repo/", "https://example.org/repo/"))])
      == ("Zoom", "", "andere_bron")
      and o([bestand("beta.flatpakref", ZOOM.replace("/repo/", "/beta-repo/"))]) == ("Zoom", "", "test_versie")
      and o([bestand("rt.flatpakref", ZOOM.replace("IsRuntime=false", "IsRuntime=true"))])[2] == "onderdeel"
      and o([bestand("rf.flatpakref", ZOOM.replace("Name=us.zoom.Zoom", "Name=-rf"))])[2] == "kapot",
      "7: een ander adres: geweigerd met een zoektekst; Beta: testversie; een onderdeel; een rare naam: kapot")
_pad = bestand("Zoom installeren.flatpakref", ZOOM)
klopt(o(["file://" + _pad.replace(" ", "%20")]) == ("", "us.zoom.Zoom", ""), "7: een file://-adres met %20 erin")
klopt(o([bestand("flathub.flatpakrepo", "[Flatpak Repo]\nUrl=https://dl.flathub.org/repo/\n")])[2] == "flathub_al"
      and o([bestand("x.flatpakrepo", "[Flatpak Repo]\nUrl=https://apps.example.org/repo/\n")])[2] == "andere_winkel"
      and o([bestand("Mijn_app-1.2.flatpak", b"\x00\x01")]) == ("Mijn app 1.2", "", "bundel"),
      "7: een andere appwinkel toevoegen en losse app-bestanden: geweigerd, met uitleg")
klopt(o([bestand("leeg.flatpakref", "")])[2] == "kapot" and o([bestand("bin.flatpakref", bytes(range(256)) * 4)])[2] == "kapot"
      and o([str(D / "weg.flatpakref")])[2] == "kapot" and o([bestand("halve.flatpakrepo", "[Flatpak")])[2] == "kapot",
      "7: leeg, binair, half of weg: 'kan dit bestand niet lezen'")
os.mkfifo(D / "pijp.flatpakref")
klopt(o([str(D / "pijp.flatpakref")])[2] == "kapot", "7/I10: een pijp met die naam laat de Winkel niet hangen")
klopt(o(["--onbekend"]) == ("", "", "") and o([]) == ("", "", "") and o(["foto.png"]) == ("", "", ""),
      "7: iets anders: gewoon de Winkel")
_cwd = os.getcwd()
os.chdir(D)
klopt(winkel.absolute_args(["us.zoom.Zoom.flatpakref"]) == [str(D / "us.zoom.Zoom.flatpakref")]
      and winkel.absolute_args(["appstream://a.b.C"]) == ["appstream://a.b.C"]
      and winkel.absolute_args(["--zoek", "x"]) == ["--zoek", "x"]
      and winkel.absolute_args(["flatpak+https://x/y"]) == ["flatpak+https://x/y"],
      "7/I10: een bestand wordt een volledig pad voordat de opdracht naar een open Winkel gaat")
os.chdir(_cwd)
for _code in ("andere_bron", "test_versie", "andere_winkel", "flathub_al", "bundel", "onderdeel", "terminal", "kapot"):
    _tekst, _soort = winkel.weiger_tekst(_code)
    klopt(_tekst and _soort in ("info", "let_op", "fout") and "Discover" not in _tekst, f"7: uitleg voor '{_code}'")

# ============================================================== 8. het venster: zoeken en de app-pagina ===
from PySide6.QtWidgets import QLabel  # noqa: E402

(APPS / "org.kde.dolphin.desktop").write_text("[Desktop Entry]\nName=Dolphin\nName[nl]=Dolphin\nNoDisplay=true\n"
                                              "Exec=dolphin\n")
(APPS / "org.kde.kclock.desktop").write_text("[Desktop Entry]\nName=KClock\nExec=kclock\n")
for _f in CACHE.glob("*.json"):
    _f.unlink()
LOG.write_text("")


def teksten(widget) -> str:
    return " | ".join(lab.text() for lab in widget.findChildren(QLabel) if lab.isVisibleTo(widget))


def zichtbaar(widget) -> bool:
    return widget.isVisibleTo(w)


w = winkel.Winkel(CAT)
w.resize(1180, 760)
w.show()
w.activateWindow()
klopt(wacht(lambda: w.flathub is not None and len(w.flathub["apps"]) > 30),
      "8: de index komt binnen (in een eigen proces gemaakt) zonder dat het venster vastloopt")
w.zoek.setText("muziek")
_picks = [k.app["id"] for k in w.kaarten]
wacht(lambda: zichtbaar(w.meer_blok) and w.meer_kaarten, 3000)
_meer = [k.app["id"] for k in w.meer_kaarten]
klopt("org.videolan.VLC" in _picks and zichtbaar(w.meer_blok) and len(_meer) == 20
      and not set(_meer) & {a["id"] for a in CAT["apps"]},
      f"F2: 'muziek': eerst de BugOS-apps ({len(_picks)}), dan 20 van Flathub, zonder dubbele ({len(_meer)})")
klopt(zichtbaar(w.meer_toon_meer) and "(6)" in w.meer_toon_meer.text() and zichtbaar(w.meer_hint)
      and "26" in w.meer_hint.text() and not zichtbaar(w.onder),
      f"F2/I9: 'Meer laten zien (6)', en bovenaan dat er nog {w.meer_hint.text()!r}")
w.toon_meer()
even(50)   # nieuwe kaarten worden pas getoond als Qt even tijd krijgt
klopt(len(w.meer_kaarten) == 26 and not zichtbaar(w.meer_toon_meer), "F2: 'Meer laten zien' zet de rest erbij")
_k = w.meer_kaarten[0]
klopt(isinstance(_k, winkel.FlathubKaart) and _k.knop.text() == "Bekijken" and _k.knop.accessibleDescription()
      and _k.accessibleName(), "F2: een app van Flathub heeft 'Bekijken' (geen installeren met één klik), met namen voor de schermlezer")
_k.knop.click()
klopt(w.stapel.currentIndex() == 1 and "install" not in LOG.read_text(),
      "F2: 'Bekijken' opent de pagina van de app en installeert niets")
w.terug()
klopt(w.stapel.currentIndex() == 0 and w.zoek.text() == "muziek" and w.focusWidget() is _k.knop,
      f"F3: Terug: dezelfde zoektekst, en de focus weer op die kaart ({w.focusWidget()!r}, {w._terug_naar!r}, {_k.knop!r})")
from PySide6.QtCore import QPoint  # noqa: E402

QTest.mouseClick(_k, Qt.MouseButton.LeftButton, pos=QPoint(20, 100))   # onder het pictogram: geen knop
klopt(w.stapel.currentIndex() == 1, "F2: een klik op de kaart zelf opent ook de pagina")
w.terug()
w.zoek.setText("dolphin")
even(400)
klopt(not any(k.app["id"] == "org.kde.dolphin" for k in w.meer_kaarten),
      "I1: Dolphin zit in BugOS zelf: niet nog eens als app van Flathub")

# de app-pagina
w.tweede_start(["appstream://org.voorbeeld.Radio"])
p = w.pagina
klopt(w.stapel.currentIndex() == 1 and w.pagina_id == "org.voorbeeld.Radio" and p.soort == "flathub",
      "F3: appstream://<id> van Flathub opent de pagina van die app")
_t = teksten(p)
klopt("niet getest" in p.veilig.tekst.text() and "Radio NL" in _t and "Door Radiomakers" in _t
      and "Geverifieerde maker" in _t and "Flathub heeft gecontroleerd dat de app echt van radio.example.org komt" in _t,
      "F3: de pagina zegt dat BugOS hem niet testte, en wie hem maakt (gecontroleerd)")
klopt("Vanaf 13 jaar (contact met anderen online)" in _t and "Radio is a radio player." in _t,
      "F3: voor welke leeftijd, en waarom; en wat de app doet")
klopt(wacht(lambda: "Ongeveer 12 MB" in p.grootte.text(), 4000) and p.grootte_rij.isVisibleTo(p),
      f"F3: de grootte (uit flatpak, zonder internet): {p.grootte.text()!r}")
klopt(any(isinstance(k, winkel.Knop) and k.text() == "radio.example.org" for k in p.findChildren(winkel.Knop)),
      "F3: de website als knop met alleen de naam van de site")
klopt(w.pagina_scroll.horizontalScrollBar().maximum() == 0, "12: de app-pagina schuift niet opzij")
w.toon_app("org.voorbeeld.Groot")
klopt(wacht(lambda: "gedeeld onderdeel" in w.pagina.grootte.text(), 3000),
      f"F3: een app die een gedeeld onderdeel nodig heeft zegt dat erbij ({w.pagina.grootte.text()!r})")
w.toon_app("org.voorbeeld.Niet")
_t = teksten(w.pagina)
klopt("Maker onbekend" in _t and "niet gecontroleerd" in _t and "Door " not in _t,
      "I10: geen maker bekend: 'Maker onbekend', nooit 'Door ' of '. Flathub...'")
w.tweede_start(["appstream://org.voorbeeld.Radio.Plugin"])
klopt(w.pagina_id == "org.voorbeeld.Radio", f"I3: een uitbreiding opent de app die hij uitbreidt ({w.pagina_id})")
w.tweede_start(["appstream://org.voorbeeld.Platform"])
klopt(w.stapel.currentIndex() == 0 and "onderdeel voor andere apps" in w.opdracht_melding.tekst.text()
      and w.zoek.text() == "Voorbeeld Platform",
      "I3: een onderdeel (runtime) is geen 'niet op Flathub': uitleg, en zoeken op zijn naam")
w.tweede_start(["appstream://org.voorbeeld.Klok"])
klopt("opdrachtregel" in w.opdracht_melding.tekst.text(), "I3: een programma voor de terminal: dat zegt de Winkel")
w.tweede_start(["appstream://org.kde.dolphin"])
klopt(w.pagina.soort == "systeem" and "hoort bij BugOS" in w.pagina.melding.tekst.text()
      and not w.pagina.installeer_knop.isVisibleTo(w.pagina) and not w.pagina.open_knop.isVisibleTo(w.pagina),
      "I1: Dolphin (via KRunner): 'hoort bij BugOS', geen Installeren, en geen Openen (BugOS verbergt hem)")
w.tweede_start(["appstream://org.kde.kclock.desktop"])
klopt(w.pagina.soort == "systeem" and w.pagina.open_knop.isVisibleTo(w.pagina),
      "I1: een gewoon programma van BugOS heeft wel 'Openen'")
gestart.clear()
w.pagina.open_knop.click()
klopt(gestart and gestart[0][-1].endswith("org.kde.kclock.desktop"), f"I1: ... en dat opent zijn eigen .desktop ({gestart})")
w.tweede_start(["appstream://org.example.NietBijOns"])
klopt(w.pagina.soort == "niet_gevonden", "F3: een id dat nergens is: 'staat niet in Flathub', met zoeken")
w.tweede_start([bestand("radio.flatpakref", ZOOM.replace("us.zoom.Zoom", "org.voorbeeld.Radio"))])
klopt(w.stapel.currentIndex() == 1 and w.pagina_id == "org.voorbeeld.Radio",
      "F6: een .flatpakref van Flathub opent de pagina van die app in de Winkel")
w.tweede_start([str(D / "x.flatpakrepo")])
klopt(w.stapel.currentIndex() == 0 and "andere appwinkel toevoegen" in w.opdracht_melding.tekst.text(),
      "F6: een .flatpakrepo van een andere appwinkel: de lijst, met uitleg waarom niet")
w.tweede_start([str(D / "ander.flatpakref")])
klopt(w.zoek.text() == "Zoom" and "andere appwinkel dan Flathub" in w.opdracht_melding.tekst.text(),
      "F6: een app uit een andere appwinkel: uitleg, en zoeken op zijn naam")
w.zoek.clear()

# installeren, verwijderen vanaf de pagina
w.toon_app("org.voorbeeld.Radio")
LOG.write_text("")
w.pagina.installeer_knop.click()
klopt(w.pagina.installeer_knop.text() == "Bezig…", "F4: tijdens het installeren: 'Bezig…'")
wacht(lambda: w.bezig_met is None and w.proces.state() == w.proces.ProcessState.NotRunning)
_log = LOG.read_text()
klopt("install -y flathub org.voorbeeld.Radio" in _log and "--noninteractive" not in _log,
      f"F4/U059: installeren met flatpak, zonder --noninteractive ({_log.strip().splitlines()[-1:]})")
klopt(w.pagina.open_knop.isVisibleTo(w.pagina) and w.pagina.weg_knop.isVisibleTo(w.pagina)
      and not w.pagina.installeer_knop.isVisibleTo(w.pagina)
      and w.pagina.melding.tekst.text().startswith("✅") and w.melding.tekst.text().startswith("✅"),
      f"F4: daarna Openen en Verwijderen, en de melding op de pagina en in de lijst ({w.pagina.melding.tekst.text()!r})")
for _code, _woord in (("9", "beheerder"), ("8", "vol"), ("7", "niet (meer) te krijgen")):
    os.environ["BUGOS_TEST_FLATPAK"] = _code
    w.toon_app("org.voorbeeld.Groot")
    w.pagina.installeer_knop.click()
    wacht(lambda: w.bezig_met is None and w.proces.state() == w.proces.ProcessState.NotRunning)
    klopt(_woord in w.pagina.melding.tekst.text() and "internet" not in w.pagina.melding.tekst.text(),
          f"F4: mislukt ({_code}): {w.pagina.melding.tekst.text()!r}")
os.environ.pop("BUGOS_TEST_FLATPAK", None)
import bugos_shell  # noqa: E402

_gevraagd: list = []
_echt_exec = bugos_shell.VraagDialoog.exec


def _ja(self):
    _gevraagd.append((self.kop.text(), self.standaard, getattr(self, "vinkje", None) is not None))
    return bugos_shell.QDialog.DialogCode.Accepted


bugos_shell.VraagDialoog.exec = _ja
w.toon_app("org.voorbeeld.Radio")
LOG.write_text("")
w.pagina.weg_knop.click()
wacht(lambda: w.bezig_met is None and w.proces.state() == w.proces.ProcessState.NotRunning)
bugos_shell.VraagDialoog.exec = _echt_exec
klopt(_gevraagd == [("Verwijderen?", "Annuleren", True)] and "uninstall -y org.voorbeeld.Radio" in LOG.read_text()
      and "--delete-data" not in LOG.read_text(),
      f"F4/D11: verwijderen vraagt het eerst met de BugOS-vraag (Enter = Annuleren, met het vinkje) ({_gevraagd})")

# terug naar de lijst; leeg zoeken; niets gevonden
w.terug()
w.zoek.setText("qqqzzz")
wacht(lambda: "Niets gevonden" in w.melding.tekst.text(), 2000)
klopt("Niets gevonden voor \"qqqzzz\"" in w.melding.tekst.text() and not zichtbaar(w.meer_blok),
      "F2: echt niets (ook niet bij Flathub): een gewone zin met een voorbeeld")
w.bezig_met = "org.mozilla.firefox"
w.zoek.setText("")
klopt(not zichtbaar(w.meer_blok) and zichtbaar(w.onder) and "geïnstalleerd" in w.melding.tekst.text(),
      "F2/U333: weer leeg: de Flathub-apps weg, de onderste kaart terug, en 'wordt geïnstalleerd' staat er weer")
w.bezig_met = None
# F7: 'Mijn apps' laat elke geïnstalleerde app zien, ook een van buiten de BugOS-selectie, met Verwijderen.
_rij_mijn = next((i for i in range(w.lijst.count()) if w.lijst.sleutel(i) == "_mijn"), -1)
w.lijst.setCurrentRow(_rij_mijn)
even(50)
_oud = next((k for k in w.kaarten if k.app["id"] == OUD_ID), None)
klopt(_rij_mijn >= 0 and isinstance(_oud, winkel.FlathubKaart) and _oud.weg.isVisibleTo(w)
      and _oud.knop.text() == "Openen" and w.naam_van(OUD_ID) == "Oud",
      f"F7: 'Mijn apps' heeft ook {OUD_ID} (niet uit de selectie), met Openen en Verwijderen")
gestart.clear()
_oud.knop.click()
klopt(gestart == [("flatpak", "run", OUD_ID)], f"F7: ... en Openen start die app ({gestart})")
w.lijst.setCurrentRow(0)
# 12. de kaarten van Flathub zijn niet breder dan die van BugOS
w.zoek.setText("muziek")
wacht(lambda: bool(w.meer_kaarten), 2000)
klopt(max(k.minimumSizeHint().width() for k in w.meer_kaarten) <= max(k.minimumSizeHint().width() for k in w.kaarten),
      "12: een kaart van Flathub is niet breder dan een kaart van BugOS (de rasters lopen gelijk)")
w.close()

# ============================================================== 9. de lijst van Flathub vers houden ===
import time  # noqa: E402

_ts = BRONMAP / ".timestamp"
os.utime(_ts, (time.time() - 25 * 3600,) * 2)
_oud25 = winkel.lijst_oud(BRONMAP)
os.utime(_ts, (time.time() - 3600,) * 2)
_oud1 = winkel.lijst_oud(BRONMAP)
_ts.unlink()
klopt(_oud25 and not _oud1 and winkel.lijst_oud(BRONMAP) and winkel.lijst_oud(TMP / "bestaat-niet"),
      "9: de lijst is oud na een dag, of als hij (of zijn tijdstempel) er niet is")
os.environ["BUGOS_TEST_METERED"] = "1"
_m1 = winkel.gemeten()
os.environ["BUGOS_TEST_METERED"] = "3"
_m3 = winkel.gemeten()
os.environ["BUGOS_TEST_METERED"] = "4"
os.environ["BUGOS_TEST_ACTIEF"] = "false"
_a0 = winkel.sessie_actief()
os.environ.pop("BUGOS_TEST_ACTIEF")
klopt(_m1 and _m3 and not winkel.gemeten() and not _a0 and winkel.sessie_actief(),
      "9/I7: een hotspot (1 of 3) telt als 'kost per MB'; een sessie die niet actief is, ververst niet")
os.environ.pop("BUGOS_WINKEL_GEEN_VERVERS", None)


def winkel_start(**omgeving) -> "winkel.Winkel":
    for k, v in omgeving.items():
        os.environ[k] = v
    LOG.write_text("")
    v = winkel.Winkel(CAT)
    wacht(lambda: v.flathub is not None)
    return v


def ververst() -> bool:
    return "update --appstream --noninteractive flathub" in LOG.read_text()


w = winkel_start(BUGOS_TEST_METERED="4")
klopt(wacht(ververst, 4000) and wacht(lambda: not w.lijst_bezig(), 3000),
      "9: oude lijst, gewone verbinding: de Winkel ververst hem zelf (flatpak update --appstream)")
w.close()
w = winkel_start(BUGOS_TEST_METERED="1")
even(2200)
klopt(not ververst(), "9: op een telefoon-hotspot niet vanzelf (dat kost geld)")
w.close()
w = winkel_start(BUGOS_TEST_METERED="4", BUGOS_TEST_ACTIEF="false")
even(2200)
klopt(not ververst(), "9/I7: niet als je sessie niet de actieve is (dan zou Flatpak om een wachtwoord vragen)")
os.environ.pop("BUGOS_TEST_ACTIEF")
w.close()
w = winkel_start(BUGOS_TEST_METERED="4", BUGOS_TEST_VERVERS="1")
wacht(ververst, 4000)
wacht(lambda: not w.lijst_bezig(), 3000)
w.zoek.setText("radio")
w.zoek_meer()
klopt(not w.lijst_mislukt and "lukte niet" not in w.meer_status.text() and w.meer_kaarten,
      "9: mislukt het stille verversen terwijl er al een lijst is: geen melding, zoeken werkt gewoon")
w.close()
# I13: installeren wacht tot het verversen klaar is (dezelfde map op de computer), en andersom.
w = winkel_start(BUGOS_TEST_VERVERS="0", BUGOS_TEST_VERVERS_SLAAP="1", BUGOS_WINKEL_GEEN_VERVERS="1")
LOG.write_text("")
w.haal_lijst()
_tijdens = w.lijst_bezig()
w.installeer(winkel.entry_naar_app(w.op_id["org.voorbeeld.radio"]))
_wacht13 = w.proces.state() == w.proces.ProcessState.NotRunning and w._wachtend is not None
wacht(lambda: w.bezig_met is None and not w.lijst_bezig() and w.proces.state() == w.proces.ProcessState.NotRunning)
_regels = [r for r in LOG.read_text().splitlines() if r.startswith(("update", "install"))]
klopt(_tijdens and _wacht13 and _regels[:2] == ["update --appstream --noninteractive flathub",
                                                "install -y flathub org.voorbeeld.Radio"],
      f"9/I13: installeren start pas als het verversen klaar is ({_regels})")
_klaar13 = w.start_lijst(handmatig=False)   # er loopt niets meer: dat mag weer
wacht(lambda: not w.lijst_bezig(), 3000)
w.proces.start("/usr/bin/sleep", ["1"])
klopt(_klaar13 and not w.start_lijst(handmatig=False), "9/I13: tijdens het installeren start het verversen niet")
w.proces.waitForFinished(3000)
w.close()
os.environ.pop("BUGOS_TEST_VERVERS_SLAAP")
# Geen lijst op de computer (vers geïnstalleerd, nooit online): 'Nu ophalen'; mislukt -> een gewone zin.
_leeg = TMP / "geen-appstream"
_echt_bron = winkel.APPSTREAM
winkel.APPSTREAM = _leeg
w = winkel_start(BUGOS_TEST_VERVERS="1", BUGOS_WINKEL_GEEN_VERVERS="1")
w.zoek.setText("radio")
w.zoek_meer()
_status0 = (w.meer_status.text(), w.meer_knop_ophalen.isVisibleTo(w))
os.environ["BUGOS_TEST_VERVERS_SLAAP"] = "0.5"
w.meer_knop_ophalen.click()
_status1 = (w.meer_status.text(), w.meer_knop_ophalen.isVisibleTo(w))
wacht(lambda: not w.lijst_bezig(), 3000)
even(50)
klopt("is er nog niet" in _status0[0] and _status0[1] and "wordt opgehaald" in _status1[0] and not _status1[1]
      and "Ophalen lukte niet" in w.meer_status.text() and ververst(),
      f"9/I6: geen lijst: 'Nu ophalen'; tijdens het ophalen geen knop; mislukt: een gewone zin ({w.meer_status.text()!r})")
os.environ["BUGOS_TEST_VERVERS"] = "0"   # gelukt, maar de lijst blijft leeg (kapot): ook 'lukte niet', geen lus
w.meer_knop_ophalen.click()
klopt(wacht(lambda: not w.lijst_bezig() and not w._index_bezig and "Ophalen lukte niet" in w.meer_status.text(), 5000),
      f"9/I6: gelukt maar nog steeds geen lijst: 'lukte niet' ({w.meer_status.text()!r})")
w.close()
winkel.APPSTREAM = _echt_bron
os.environ.pop("BUGOS_TEST_VERVERS_SLAAP")
os.environ["BUGOS_WINKEL_GEEN_VERVERS"] = "1"
# Blijft flatpak hangen (een haperende verbinding), dan stopt de Winkel hem na 2 minuten (kill). Hier de echte weg:
# een flatpak die niet terugkomt, en de wachttijd ingekort tot 0,3 s. Qt geeft na kill() code 9 en CrashExit
# (nagegaan met PySide6): mislukt, dus geen nieuwe index, en 'lukte niet' omdat je er zelf om vroeg.
w = winkel_start(BUGOS_TEST_VERVERS="0", BUGOS_TEST_VERVERS_HANGT="1")
w._lijst_wacht.setInterval(300)   # in plaats van 120_000 ms
_klok9 = time.monotonic()
w.haal_lijst()
_bezig9 = w.lijst_bezig()
wacht(lambda: not w.lijst_bezig(), 5000)
_duur9 = time.monotonic() - _klok9
even(50)
klopt(_bezig9 and _duur9 < 3 and w.lijst_mislukt and not w._index_bezig and not w._lijst_wacht.isActive(),
      f"9: flatpak blijft hangen: na de wachttijd gestopt ({_duur9:.1f} s, niet 30), geen nieuwe index, 'lukte niet'")
os.environ.pop("BUGOS_TEST_VERVERS_HANGT")
w.close()

# ============================================================== 10. de voorbeeldstand (foto's) ===
LOG.write_text("")
_code10 = f'''
import sys, importlib.machinery as m, importlib.util as u
sys.path.insert(0, {str(PY)!r})
from PySide6.QtWidgets import QApplication
app = QApplication([])
l = m.SourceFileLoader("w10", {str(BRON)!r}); w = u.module_from_spec(u.spec_from_loader(l.name, l)); l.exec_module(w)
v = w.Winkel(w.lees_catalogus(w.Path({str(ROOT / "system_files/usr/share/bugos/store.json")!r})))
v.zoek.setText("muziek")
v.zoek_meer()
print("KAARTEN", ",".join(k.app["id"] for k in v.meer_kaarten))
v.toon_app("io.bassi.Amberol")
print("GROOTTE", v.pagina.grootte.text())
'''
_r = subprocess.run([sys.executable, "-c", _code10], env={**os.environ, "BUGOS_WINKEL_VOORBEELD": "1"},
                    capture_output=True, text=True, timeout=60)
klopt("io.bassi.Amberol" in _r.stdout and "GROOTTE Ongeveer 12 MB" in _r.stdout
      and "update" not in LOG.read_text() and "remote-ls" not in LOG.read_text(),
      f"10: voorbeeldstand: echte voorbeelden, geen flatpak ({_r.stdout.strip()[-120:]!r} {_r.stderr.strip()[-200:]!r})")

# ============================================================== 13. groottes, ook zonder eigen cache van flatpak ===
# Nagegaan op Kinoite 44: 'flatpak remote-ls --cached' faalt voor een gewone gebruiker zolang zijn eigen cache leeg
# is ('No cached summary'), ook als de computer zelf (root) Flathub al had. Zonder meer kwam de grootte dan bijna
# nooit. Nu: één keer zonder --cached (niet op een hotspot); zonder internet gewoon geen grootte.
_ls = "--columns=ref,download-size,installed-size,runtime flathub"
os.environ["BUGOS_TEST_GEEN_CACHE"] = "1"
os.environ["BUGOS_TEST_METERED"] = "4"
LOG.write_text("")
_g13, _r13 = winkel.alle_groottes()
_ls13 = [r for r in LOG.read_text().splitlines() if r.startswith("remote-ls")]
klopt(len(_g13) == 5 and _ls13 == [f"remote-ls --cached {_ls}", f"remote-ls {_ls}"] and _r13,
      f"13: geen eigen cache: één keer zonder --cached, en dan zijn de groottes er toch ({len(_g13)}, {_ls13})")
os.environ["BUGOS_TEST_METERED"] = "1"
LOG.write_text("")
_g13m, _ = winkel.alle_groottes()
klopt(_g13m == {} and [r for r in LOG.read_text().splitlines() if r.startswith("remote-ls")] == [f"remote-ls --cached {_ls}"],
      "13: op een telefoon-hotspot niet zelf ophalen (dat kost geld): dan gewoon geen grootte")
os.environ["BUGOS_TEST_METERED"] = "4"
os.environ["BUGOS_TEST_GEEN_NET"] = "1"
w = winkel_start()
w.resize(1180, 760)
w.show()
w.toon_app("org.voorbeeld.Radio")
klopt(wacht(lambda: not w._groottes_bezig and w.groottes is not None, 4000) and w.groottes == {}
      and not w.pagina.grootte_rij.isVisibleTo(w.pagina) and w.stapel.currentIndex() == 1
      and not w.pagina.melding.tekst.text(),
      "13: zonder internet en zonder cache: geen grootte en geen melding; de pagina werkt gewoon")
os.environ.pop("BUGOS_TEST_GEEN_NET")
LOG.write_text("")
w.toon_app("org.voorbeeld.Groot")
_meteen = w._groottes_bezig or "remote-ls" in LOG.read_text()
w._groottes_om -= 61   # een minuut later
w.toon_app("org.voorbeeld.Radio")
klopt(not _meteen and wacht(lambda: "Ongeveer 12 MB" in w.pagina.grootte.text(), 4000),
      f"13: niet bij elke pagina opnieuw, wel na een minuut: dan staat de grootte er alsnog ({w.pagina.grootte.text()!r})")
os.environ.pop("BUGOS_TEST_GEEN_CACHE")
w.close()

# ============================================================== 14. naam en chip, op een kaart en op de pagina ===
# Een gewone afbrekende QLabel brak 'Strawberry Music Player' al af bij ongeveer 20 tekens, ook op een brede kaart
# (zo stond het in de WIP-versie: de naam zonder stretch, met chip en rek erachter). Nu staat de chip direct naast de
# naam, breekt een lange naam pas af als de kaart echt te smal is, en wordt de kaart er niet breder van.
from PySide6.QtWidgets import QVBoxLayout, QWidget  # noqa: E402


def in_houder(breed: int, widget: QWidget) -> QWidget:
    """Zet een kaart of pagina in een eigen venster van deze breedte (minstens zijn minimum)."""
    houder = QWidget()
    lay = QVBoxLayout(houder)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(widget)
    houder.resize(breed, 300)
    houder.show()
    even(60)
    return houder


def regels(lab) -> int:
    return round(lab.height() / lab.fontMetrics().lineSpacing())


def gat(links, rechts) -> int:
    """Ruimte tussen het eind van 'links' en het begin van 'rechts' (zelfde ouder)."""
    return rechts.geometry().left() - links.geometry().right() - 1


w = winkel_start()
_lang = {"id": OUD_ID, "naam": "Strawberry Music Player", "kort": "Speelt muziek af", "maker": "Iemand", "echt": True}
_k14 = winkel.FlathubKaart(dict(_lang), w)   # OUD_ID is geïnstalleerd: de chip 'Geïnstalleerd' staat er
_h14 = in_houder(620, _k14)
klopt(regels(_k14.naam_label) == 1 and _k14.chip.isVisibleTo(_k14) and 6 <= gat(_k14.naam_label, _k14.chip) <= 10,
      f"14: brede kaart: 'Strawberry Music Player' op één regel, de chip er direct naast "
      f"({regels(_k14.naam_label)} regel(s), {gat(_k14.naam_label, _k14.chip)} px)")
_k14s = winkel.FlathubKaart(dict(_lang), w)
_h14s = in_houder(300, _k14s)
klopt(regels(_k14s.naam_label) >= 2 and gat(_k14s.naam_label, _k14s.chip) >= 6
      and _k14s.chip.geometry().right() <= _k14s.width(),
      f"14: smalle kaart: de naam breekt af en de chip staat er nog naast ({regels(_k14s.naam_label)} regels)")
_k14k = winkel.FlathubKaart(dict(_lang, naam="Oud"), w)
klopt(_k14s.minimumSizeHint().width() == _k14k.minimumSizeHint().width(),
      f"14: een lange naam maakt de kaart niet breder ({_k14s.minimumSizeHint().width()} = "
      f"{_k14k.minimumSizeHint().width()} px), dus de rasters blijven gelijk lopen")
_p14 = winkel.AppPagina(w, "flathub", "org.voorbeeld.Lang",
                        entry=dict(w.entry_van(OUD_ID), id="org.voorbeeld.Lang", maker="Rick van Lieshout", echt=True))
_hp14 = in_houder(900, _p14)
_chip14 = next(c for c in _p14.findChildren(winkel.Chip) if c.text() == "Geverifieerde maker")
klopt(_p14.maker.text() == "Door Rick van Lieshout" and regels(_p14.maker) == 1 and 6 <= gat(_p14.maker, _chip14) <= 10,
      f"14: de pagina: 'Door Rick van Lieshout' op één regel, met 'Geverifieerde maker' ernaast ({regels(_p14.maker)})")
for _h in (_h14, _h14s, _hp14):
    _h.close()
w.close()

# ============================================================== 15. geen KDE Discover meer in het beeld ===
# Zonder Discover is de Winkel de enige die een .flatpakref (de knop 'Install' op flathub.org), een flatpak+https://-
# en een appstream://-link opent. build.sh haalt Discover (en KDE Partition Manager) weg met rpm -e zonder --nodeps:
# hangt er ooit iets van af, dan stopt de bouw luid. (Of het in het gebouwde beeld klopt: tools/test_image.sh, 5c.)
import re  # noqa: E402

SOORTEN = ["x-scheme-handler/appstream", "x-scheme-handler/flatpak+https", "application/vnd.flatpak.ref",
           "application/vnd.flatpak.repo", "application/vnd.flatpak"]
_desktop = (ROOT / "system_files/usr/share/applications/bugos-store.desktop").read_text(encoding="utf-8")
_mime = next((r.split("=", 1)[1] for r in _desktop.splitlines() if r.startswith("MimeType=")), "")
klopt(set(SOORTEN) <= set(filter(None, _mime.split(";"))) and "Exec=bugos-store %U" in _desktop,
      f"15: bugos-store.desktop kent .flatpakref, .flatpakrepo, .flatpak, flatpak+https:// en appstream:// ({_mime})")
_lijst = (ROOT / "system_files/etc/xdg/kde-mimeapps.list").read_text(encoding="utf-8")
_standaard = dict(r.split("=", 1) for r in _lijst.split("[Added Associations]")[0].splitlines()
                  if "=" in r and not r.startswith("#"))
klopt(all(_standaard.get(s) == "bugos-store.desktop" for s in SOORTEN),
      "15: kde-mimeapps.list: die vijf openen standaard de Winkel (ook voor Firefox: gio leest kde-mimeapps.list)")
_bouw = (ROOT / "build_files/build.sh").read_text(encoding="utf-8")
_stap2 = _bouw.split("# Geen KDE Discover")[1].split("# Steam als echt")[0]
_rpm_e = [r.strip() for r in _stap2.splitlines() if r.strip().startswith("rpm -e")]
klopt(all(p in _stap2 for p in ("plasma-discover-libs", "plasma-discover-kns", "plasma-discover-flatpak",
                                "plasma-discover-notifier", "kde-partitionmanager", "kpmcore"))
      and len(_rpm_e) == 2 and not any("--nodeps" in r for r in _rpm_e) and "dnf5 install" not in _stap2,
      f"15: build.sh haalt Discover en Partition Manager weg, met rpm -e zonder --nodeps ({_rpm_e})")
_pakketten = (ROOT / "build_files/packages.txt").read_text(encoding="utf-8")
klopt(not re.search(r"^\s*(plasma-discover|kde-partitionmanager|kpmcore)", _pakketten, re.M),
      "15: packages.txt installeert Discover en Partition Manager niet (meer)")

# ============================================================== 16. een link terwijl de lijst er nog niet is ===
# Een vers geïnstalleerde BugOS heeft Flathub's lijst nog niet: bugos-first-boot installeert alleen apps (dat zet geen
# lijst neer, nagegaan op Kinoite 44) en de dagelijkse update draait pas 's nachts. Juist dan klik je op 'Install' op
# flathub.org (een .flatpakref) of op een appstream://-link. De Winkel haalt de lijst dan zelf (1,5 s na het openen).
# Eerst zei de pagina 'staat niet (meer) in Flathub' en bleef dat zeggen, zonder Installeren, ook toen de lijst er was.
# Nu: zeggen wat de Winkel doet, en zodra de lijst er is de app zelf. Alles nep (flatpak, busctl), zoals hierboven.
import shutil  # noqa: E402

VERS = TMP / "verse-computer"   # waar Flathub's lijst zou staan (/var/lib/flatpak/appstream/flathub/x86_64)
LIJST16 = TMP / "lijst16.xml"   # wat de nep-flatpak bij 'update --appstream' neerzet: Radio en Teken
LIJST16.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<components version="0.8" origin="flathub">' + RADIO
                   + GIMPACHTIG + "</components>\n", encoding="utf-8")
winkel.APPSTREAM = VERS
os.environ.pop("BUGOS_WINKEL_GEEN_VERVERS", None)   # nu juist wel zelf verversen, zoals op een echte computer
os.environ.update(BUGOS_TEST_METERED="4", BUGOS_TEST_VERVERS="0", BUGOS_TEST_VERVERS_SLAAP="0.5",
                  BUGOS_TEST_LIJST_NAAR=str(VERS), BUGOS_TEST_LIJST_XML=str(LIJST16))
os.environ.pop("BUGOS_TEST_ACTIEF", None)
RADIO_REF = bestand("radio16.flatpakref", ZOOM.replace("us.zoom.Zoom", "org.voorbeeld.Radio"))


def vers_begin(oude_lijst: list[str] | None = None, dagen: float = 0) -> None:
    """Weer een computer zonder lijst en zonder index, zoals net geïnstalleerd. Met oude_lijst: wel een lijst (met
    die apps), van 'dagen' geleden."""
    shutil.rmtree(VERS, ignore_errors=True)
    for f in CACHE.glob("*.json"):
        f.unlink()
    if oude_lijst is not None:
        som = "d" * 64
        (VERS / som).mkdir(parents=True)
        (VERS / som / "appstream.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<components version="0.8" '
                                                  'origin="flathub">' + "".join(oude_lijst) + "</components>\n",
                                                  encoding="utf-8")
        (VERS / "active").symlink_to(som)
        (VERS / ".timestamp").touch()
        os.utime(VERS / ".timestamp", (time.time() - dagen * 86400,) * 2)
    LOG.write_text("")


def open16(opdracht: list[str]) -> "winkel.Winkel":
    """De Winkel zoals main() hem opent: met de opdracht (de link of het bestand) meteen erbij."""
    v = winkel.Winkel(CAT, opdracht=opdracht)
    v.resize(1180, 760)
    v.show()
    return v


def staat16(v) -> tuple[str, str, list[str]]:
    """(soort pagina, de melding op de pagina, de knoppen die je ziet) van de open app-pagina."""
    p = v.pagina
    if p is None or v.stapel.currentIndex() != 1:
        return "", "", []
    return p.soort, p.melding.tekst.text(), [k.text() for k in p.findChildren(winkel.Knop) if k.isVisibleTo(p)]


def nu_ophalen(v) -> None:
    next(k for k in v.pagina.findChildren(winkel.Knop) if k.text() == "Nu ophalen").click()


def onthoud16(v, gezien: set[str]) -> None:
    """Onthoud de melding die de pagina nu laat zien (goedkoop: dit draait bij elke ronde van wacht())."""
    if v.pagina is not None:
        gezien.add(v.pagina.melding.tekst.text())


# 16a. de link en het .flatpakref-bestand op een verse computer met internet: eerst 'worden geladen', dan 'wordt
#      opgehaald', en dan de app met Installeren. Nooit 'staat niet in Flathub'.
for _opdracht in (["appstream://org.voorbeeld.Radio"], [RADIO_REF]):
    vers_begin()
    v = open16(_opdracht)
    _gezien: set[str] = set()   # elke melding die de pagina onderweg liet zien
    _meteen = staat16(v)
    wacht(lambda: v.flathub is not None, 3000)
    _na_index = staat16(v)
    wacht(lambda: onthoud16(v, _gezien) or v.lijst_bezig(), 4000)
    _tijdens = staat16(v)
    wacht(lambda: onthoud16(v, _gezien) or (v.pagina is not None and v.pagina.soort == "flathub"), 8000)
    _eind = staat16(v)
    _soort = "link" if _opdracht[0].startswith("appstream") else ".flatpakref"
    klopt(_meteen[0] == "laden" and "worden geladen" in _meteen[1] and _na_index[0] == "laden"
          and "worden geladen" in _na_index[1] and "Nu ophalen" not in _na_index[2],
          f"16a ({_soort}): geen lijst, de Winkel kijkt nog: 'worden geladen…', geen 'Nu ophalen' ({_na_index})")
    klopt(_tijdens[0] == "laden" and "wordt opgehaald" in _tijdens[1] and "Nu ophalen" not in _tijdens[2],
          f"16a ({_soort}): tijdens het verversen: 'De lijst … wordt opgehaald…' ({_tijdens[1]!r})")
    klopt(_eind[0] == "flathub" and v.pagina_id == "org.voorbeeld.Radio" and "Installeren" in _eind[2] and ververst()
          and not any("staat niet" in m for m in _gezien | {_meteen[1], _na_index[1], _eind[1]}),
          f"16a ({_soort}): zodra de lijst er is: de pagina van de app, met Installeren; nooit 'staat niet' "
          f"({_eind[0]}, {_eind[2]})")
    v.close()

# 16b. geen internet: het stille verversen mislukt. Rustig 'de lijst is er nog niet' met 'Nu ophalen' (geen fout);
#      zelf ophalen zonder internet: 'lukte niet'; weer online en nog eens: de app.
vers_begin()
os.environ["BUGOS_TEST_VERVERS"] = "1"
v = open16(["appstream://org.voorbeeld.Radio"])
wacht(lambda: v.lijst_bezig(), 4000)
wacht(lambda: not v.lijst_onderweg(), 4000)
even(50)
_stil = staat16(v)
klopt(_stil[0] == "laden" and "is er nog niet" in _stil[1] and "Nu ophalen" in _stil[2] and "lukte niet" not in _stil[1]
      and "staat niet" not in _stil[1],
      f"16b: offline, stil mislukt: 'De lijst met alle apps is er nog niet' met 'Nu ophalen' ({_stil[1]!r}, {_stil[2]})")
nu_ophalen(v)
_zelf = staat16(v)
wacht(lambda: not v.lijst_onderweg(), 4000)
even(50)
_mis = staat16(v)
klopt("wordt opgehaald" in _zelf[1] and "Nu ophalen" not in _zelf[2] and "Ophalen lukte niet" in _mis[1]
      and "Nu ophalen" in _mis[2] and _mis[0] == "laden",
      f"16b: 'Nu ophalen' zonder internet: eerst 'wordt opgehaald', dan 'Ophalen lukte niet' met de knop ({_mis[1]!r})")
os.environ["BUGOS_TEST_VERVERS"] = "0"
nu_ophalen(v)
klopt(wacht(lambda: staat16(v)[0] == "flathub", 8000) and "Installeren" in staat16(v)[2],
      f"16b: weer online, 'Nu ophalen': de pagina van de app, met Installeren ({staat16(v)[0]})")
v.close()

# 16c. een telefoon-hotspot: de Winkel ververst niet vanzelf (dat kost geld), maar zegt het en laat je kiezen.
vers_begin()
os.environ["BUGOS_TEST_METERED"] = "1"
v = open16(["appstream://org.voorbeeld.Radio"])
wacht(lambda: not v._lijst_straks, 4000)
even(50)
_hotspot = staat16(v)
klopt(not ververst() and _hotspot[0] == "laden" and "is er nog niet" in _hotspot[1] and "Nu ophalen" in _hotspot[2],
      f"16c: hotspot: niet vanzelf ophalen; 'is er nog niet' met 'Nu ophalen' ({_hotspot[1]!r})")
nu_ophalen(v)
klopt(wacht(lambda: staat16(v)[0] == "flathub", 8000) and ververst(),
      "16c: ... en 'Nu ophalen' (je vraagt het zelf) haalt hem toch, en dan de app")
v.close()
os.environ["BUGOS_TEST_METERED"] = "4"

# 16d. terug naar de lijst terwijl de pagina wacht: als de lijst er is, springt de Winkel niet terug naar die pagina.
vers_begin()
v = open16(["appstream://org.voorbeeld.Radio"])
wacht(lambda: v.flathub is not None, 3000)
v.terug()
wacht(lambda: ververst() and not v.lijst_onderweg(), 8000)
even(50)
v.zoek.setText("radio")
v.zoek_meer()
klopt(v.stapel.currentIndex() == 0 and v._wacht_app is None and any(k.app["id"] == "org.voorbeeld.Radio"
                                                                   for k in v.meer_kaarten),
      "16d: terug naar de lijst tijdens het wachten: geen sprong terug, en de app staat wel in de zoekresultaten")
v.close()

# 16e. wel een lijst, maar van twee dagen geleden en zonder deze app (vandaag op Flathub gekomen): eerst de nieuwe
#      lijst, dan de app. En een lijst van vandaag zonder de app: dan staat hij er echt niet in.
vers_begin([GIMPACHTIG], dagen=2)
v = open16(["appstream://org.voorbeeld.Radio"])
wacht(lambda: v.flathub is not None, 3000)
_oud16 = staat16(v)
klopt(_oud16[0] == "laden" and wacht(lambda: staat16(v)[0] == "flathub", 8000) and ververst(),
      f"16e: een oude lijst zonder de app: wachten op de nieuwe lijst, dan de app ({_oud16[0]}, {staat16(v)[0]})")
v.close()
vers_begin([GIMPACHTIG], dagen=0)
v = open16(["appstream://org.voorbeeld.Radio"])
wacht(lambda: not v._lijst_straks, 4000)
even(50)
_echt_niet = staat16(v)
klopt(not ververst() and _echt_niet[0] == "niet_gevonden" and "staat niet (meer) in de lijst van Flathub" in _echt_niet[1]
      and "Zoek een andere app" in _echt_niet[2],
      f"16e: een verse lijst zonder de app: 'staat niet (meer) in de lijst van Flathub', met zoeken ({_echt_niet[1]!r})")
v.close()

# 16f. zonder het stille verversen (zoals bij foto's en tests): meteen 'is er nog niet' met 'Nu ophalen'.
vers_begin()
os.environ["BUGOS_WINKEL_GEEN_VERVERS"] = "1"
v = open16(["appstream://org.voorbeeld.Radio"])
wacht(lambda: v.flathub is not None, 3000)
even(50)
_zonder = staat16(v)
klopt(_zonder[0] == "laden" and "is er nog niet" in _zonder[1] and "Nu ophalen" in _zonder[2] and not ververst(),
      f"16f: niet vanzelf verversen: meteen 'is er nog niet' met 'Nu ophalen' ({_zonder[1]!r})")
v.close()
for _weg in ("BUGOS_TEST_LIJST_NAAR", "BUGOS_TEST_LIJST_XML", "BUGOS_TEST_VERVERS_SLAAP"):
    os.environ.pop(_weg, None)

print()
print("Fouten:", fouten)
sys.exit(1 if fouten else 0)
