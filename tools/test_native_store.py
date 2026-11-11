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
             "BUGOS_WINKEL_GEEN_VERVERS"):
    os.environ.pop(_weg, None)

NEP = TMP / "nep-bin"
NEP.mkdir()
LOG = TMP / "flatpak.log"
LOG.write_text("")


def nep_programma(naam: str, inhoud: str) -> None:
    (NEP / naam).write_text("#!/usr/bin/bash\n" + inhoud)
    (NEP / naam).chmod(0o755)


# Een nep-flatpak: schrijft elke opdracht in flatpak.log en antwoordt zoals de echte (TAB tussen de kolommen).
nep_programma("flatpak", f'''echo "$*" >> "{LOG}"
case "$1 $2 $3" in
  "list --app --columns=application") printf 'org.voorbeeld.Oud\\n'; exit 0 ;;
  "list --app --columns=application,name,origin") printf 'org.voorbeeld.Oud\\tOud\\tflathub\\n'; exit 0 ;;
  "list --runtime --columns=ref") printf 'org.gnome.Platform/x86_64/49\\n'; exit 0 ;;
esac
if [ "$1" = remote-ls ]; then
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
  [ -n "$BUGOS_TEST_VERVERS_SLAAP" ] && /usr/bin/sleep "$BUGOS_TEST_VERVERS_SLAAP"
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
klopt("Niets gevonden voor \"qqqzzz\"" in w.melding.tekst.text(),
      "1: niets gevonden: een gewone zin met een voorbeeld, geen verwijzing naar een ander programma")
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

print()
print("Fouten:", fouten)
sys.exit(1 if fouten else 0)
