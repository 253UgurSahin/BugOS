#!/usr/bin/env python3
"""Test van de taakbalk en het bureaublad zonder KDE-bewerkmodus (pakket shell).

Wat er getest wordt, zonder Plasma en zonder node:
  A. de JavaScript van bugos-panel in een nagebootst Plasma (PySide6 QJSEngine): het slot, eerlijk vervang(),
     het bureaubladmenu, het systeemvak;
  B. bugos-panel zelf (bash) met nep-programma's (gdbus, qdbus6, notify-send): wat hij naar Plasma stuurt;
  C. de functie bureaubladmenu uit build_files/style.sh op nagemaakte KDE-bestanden;
  D. style.sh: de kiosk-sleutel, het bestand voor nieuwe gebruikers;
  E. de QML: de eigen regels in de rechtermuismenu's (bureaublad, klok, snelmenu);
  F. de indeling voor nieuwe gebruikers (look-and-feel) in een nagebootst Plasma.
Er verandert niets aan je computer: alles gebeurt in een tijdelijke map.

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_native_shell.py
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication  # noqa: E402
from PySide6.QtQml import QJSEngine  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PANEEL = ROOT / "system_files/usr/bin/bugos-panel"
STYLE = ROOT / "build_files/style.sh"
INDELING = ROOT / "system_files/usr/share/plasma/look-and-feel/org.bugos.desktop/contents/layouts/org.kde.plasma.desktop-layout.js"
PLASMOIDS = ROOT / "system_files/usr/share/plasma/plasmoids"
APP = QGuiApplication(sys.argv)
fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


def lees(pad: Path) -> str:
    # In een Windows-kopie staan er CRLF-regeleinden in; git en het beeld hebben LF.
    return pad.read_text(encoding="utf-8").replace("\r\n", "\n")


PANEEL_TEKST = lees(PANEEL)
STYLE_TEKST = lees(STYLE)


def js_blok() -> str:
    """De JavaScript van bugos-panel: alles tussen de regel die met JS=' begint en de regel die alleen ' is."""
    regels = PANEEL_TEKST.split("\n")
    begin = next(i for i, r in enumerate(regels) if r.startswith("JS='"))
    eind = next(i for i in range(begin + 1, len(regels)) if regels[i] == "'")
    return "\n".join([regels[begin][4:]] + regels[begin + 1:eind]) + "\n"


JS = js_blok()


def wijzig(code: str, na: str = "true") -> str:
    """Wat plasma_wijzig() in bugos-panel naar Plasma stuurt (zonder $JS), uit de bash-functie zelf gehaald."""
    m = re.search(r'^plasma_wijzig\(\) \{ plasma_script "\$JS (.*)"; \}$', PANEEL_TEKST, re.M)
    if not m:
        return "GEEN plasma_wijzig()"
    return m.group(1).replace("$1", code).replace("$(slot_na)", na)


# Een nagebootst Plasma, zoals tools/panel-sim.js, maar met het slot erbij. addWidget() geeft niets terug als het
# geheel (__AppInterface.locked) of het paneel zelf op slot staat, net als Plasma.
SIM = r"""
var gedrukt = [];
function print(x) { gedrukt.push(String(x)); }
var gridUnit = 16;
__AppInterface = { locked: false };
var bestanden = {};
function ConfigFile(ouder, groep) {
    var pad = (typeof ouder == "string" ? ouder : ouder.pad) + "/" + groep;
    return { pad: pad,
        writeEntry: function (k, v) { if (!bestanden[pad]) bestanden[pad] = {}; bestanden[pad][k] = v; },
        readEntry: function (k, d) { return bestanden[pad] && (k in bestanden[pad]) ? bestanden[pad][k] : d; } };
}
var volgnummer = 1;
function opSlot(c) { return (typeof __AppInterface != "undefined" && __AppInterface.locked) || c.locked; }
function maakContainment(soorten, cfgs) {
    var c = { locked: false, lijst: [], floating: true, height: 0, currentConfigGroup: [] };
    c.maak = function (type) {
        var cfg = (cfgs && cfgs[type]) ? JSON.parse(JSON.stringify(cfgs[type])) : {};
        var w = { id: volgnummer++, type: type, cfg: cfg, locked: false, currentConfigGroup: [], herladen: 0,
            writeConfig: function (k, v) { cfg[k] = v; },
            readConfig: function (k, s) { return (k in cfg) ? cfg[k] : s; },
            reloadConfig: function () { w.herladen++; },
            remove: function () { c.lijst.splice(c.lijst.indexOf(w), 1); } };
        Object.defineProperty(w, "index", {
            get: function () { return c.lijst.indexOf(w); },
            set: function (n) { c.lijst.splice(c.lijst.indexOf(w), 1); c.lijst.splice(n, 0, w); } });
        return w;
    };
    c.widgets = function () { return c.lijst.slice(); };
    c.addWidget = function (type) { if (opSlot(c)) return undefined; var w = c.maak(type); c.lijst.push(w); return w; };
    c.readConfig = function (k, s) { return s; };
    c.writeConfig = function () {};
    c.reloadConfig = function () {};
    for (var i = 0; i < soorten.length; i++) c.lijst.push(c.maak(soorten[i]));
    return c;
}
function soorten(c) { return c.lijst.map(function (w) { return w.type; }); }
function vak(c) { for (var i = 0; i < c.lijst.length; i++) if (c.lijst[i].type == "org.kde.plasma.systemtray") return c.lijst[i]; return null; }
"""

TAAKBALK = ["org.bugos.startmenu", "org.kde.plasma.icontasks", "org.bugos.taskbar", "org.kde.plasma.systemtray",
            "org.bugos.clock"]


def draai_js(code: str, uitkomst: str, begin: list[str] | None = None, cfgs: dict | None = None,
             vooraf: str = "") -> dict:
    """Draai het JS-blok van bugos-panel plus 'code' in het nagebootste Plasma; geef 'uitkomst' (een JS-uitdrukking)
    terug als Python-waarde, met 'gedrukt' (alles wat print() kreeg) en 'fout' (een uitzondering uit 'code')."""
    opzet = (f"var paneel = maakContainment({json.dumps(begin if begin is not None else TAAKBALK)}, {json.dumps(cfgs or {})});"
             "var bureau = maakContainment([]);"
             "function panels() { return [paneel]; } function desktops() { return [bureau]; }" + vooraf)
    e = QJSEngine()
    r = e.evaluate(SIM + opzet + "\n" + JS + "\nvar __fout = null; try {\n" + code + "\n} catch (x) { __fout = String(x); }\n"
                   "JSON.stringify({u: (" + uitkomst + "), gedrukt: gedrukt, fout: __fout})")
    if r.isError():
        return {"u": None, "gedrukt": [], "fout": "JS: " + r.toString()}
    return json.loads(r.toString())


# --- A. De JavaScript van bugos-panel -----------------------------------------------------------------------------
klopt("\\" not in JS, "A1: het JS-blok van bugos-panel heeft geen backslash (via gdbus wordt dat een SyntaxError)")
klopt("'" not in JS, "A1: het JS-blok heeft geen enkel aanhalingsteken (het staat tussen '...' in bash)")

r = draai_js('__AppInterface.locked = true; vervang("", "org.bugos.quickmenu", "org.kde.plasma.systemtray");',
             "soorten(paneel)")
klopt(r["gedrukt"] == ["0"] and "org.bugos.quickmenu" not in (r["u"] or []),
      f"A2: op slot voegt Plasma niets toe: vervang() zegt 0 en er komt niets bij ({r})")

r = draai_js("__AppInterface.locked = true; " + wijzig('vervang("", "org.bugos.quickmenu", "org.kde.plasma.systemtray");'),
             "{s: soorten(paneel), slot: __AppInterface.locked}")
s = (r["u"] or {}).get("s", [])
klopt(r["gedrukt"] == ["1"] and "org.bugos.quickmenu" in s
      and s.index("org.bugos.quickmenu") + 1 == s.index("org.kde.plasma.systemtray") and r["u"]["slot"] is True,
      f"A3: slot eraf, snelmenu erbij (vlak voor het systeemvak), slot er weer op ({r})")

r = draai_js("delete __AppInterface; slot(true); var a = [paneel.locked, bureau.locked].concat(paneel.lijst.map(function (w) { return w.locked; }));"
             "slot(false); var b = [paneel.locked, bureau.locked].concat(paneel.lijst.map(function (w) { return w.locked; }));",
             "{a: a, b: b}")
u = r["u"] or {}
klopt(u.get("a") and all(u["a"]) and not any(u["b"]) and r["fout"] is None,
      f"A4: zonder __AppInterface (reserveweg): slot(true) zet paneel, bureaublad en elk onderdeel vast, slot(false) maakt ze los ({r})")
r = draai_js("delete __AppInterface; paneel.locked = true; " + wijzig('vervang("", "org.bugos.quickmenu", "org.kde.plasma.systemtray");'),
             "{s: soorten(paneel), slot: paneel.locked, w: paneel.lijst.every(function (w) { return w.locked; })}")
klopt(r["gedrukt"] == ["1"] and "org.bugos.quickmenu" in r["u"]["s"] and r["u"]["slot"] and r["u"]["w"],
      f"A4: reserveweg: met het paneel op slot voegt bugos-panel het snelmenu toch toe, en alles staat weer vast ({r})")

r = draai_js("paneel.locked = true; slot(false);", "[paneel.locked, __AppInterface.locked]")
klopt(r["u"] == [False, False], f"A5: slot(false) haalt ook een los slot op het paneel eraf ({r})")

r = draai_js(wijzig("bestaat_niet();"), "__AppInterface.locked")
klopt(r["fout"] is not None and r["u"] is True,
      f"A9: gaat de verandering mis (een fout in het script), dan staat het slot er toch weer op ({r})")
r = draai_js(wijzig("weg(\"org.bugos.clock\");", na="false"), "__AppInterface.locked")
klopt(r["u"] is False, "A9: met 'bewerken aan' (slot_na = false) blijft het slot eraf")

BUREAUBLAD_UIT = ["_add panel", "_display_settings", "_lock_screen", "_logout", "_open_terminal", "_run_command",
                  "_wallpaper", "add widgets", "configure", "configure shortcuts", "desktop edit mode", "edit mode",
                  "manage activities", "remove"]
r = draai_js("__AppInterface.locked = true; bureaubladmenu();", "bestanden")
_b = r["u"] or {}
_groep0 = _b.get("plasma-org.kde.plasma.desktop-appletsrc/ActionPlugins/0", {})
_menu0 = _b.get("plasma-org.kde.plasma.desktop-appletsrc/ActionPlugins/0/RightButton;NoModifier", {})
klopt(r["gedrukt"] == ["14"] and _groep0 == {"RightButton;NoModifier": "org.kde.contextmenu"}
      and _menu0 == {k: False for k in BUREAUBLAD_UIT},
      f"A6: bureaubladmenu() zet de 14 KDE-regels van het bureaublad uit, en houdt het menu zelf aan ({r['gedrukt']}, {sorted(_menu0)})")
klopt(not any("/ActionPlugins/1" in k for k in _b) and set(_b) <= {
      "plasma-org.kde.plasma.desktop-appletsrc/ActionPlugins/0",
      "plasma-org.kde.plasma.desktop-appletsrc/ActionPlugins/0/RightButton;NoModifier"},
      f"A6: bureaubladmenu() schrijft NIETS in groep 1 (het paneel: dan verdwijnt het hele taakbalkmenu) ({sorted(_b)})")

r = draai_js("slot(false); slot(true);", "1")
klopt(r["gedrukt"] == [], f"A8: slot() print niets (anders klopt de 0/1 van vervang niet meer) ({r['gedrukt']})")


# --- B. bugos-panel (bash) met nep-programma's ------------------------------------------------------------------
NEP = r'''#!/usr/bin/env python3
# Nep-gdbus / nep-qdbus6 / nep-notify-send voor tools/test_native_shell.py: schrijft elke aanroep op, en geeft het
# antwoord uit antwoorden.json. Het script naar Plasma begint altijd met het hele JS-blok (met 'function heeft');
# alleen het stuk na de laatste regel '}' zegt wat er gebeurt.
import json, os, sys
d = os.environ["NEP_MAP"]
naam = os.path.basename(sys.argv[0])
args = sys.argv[1:]
logmap = os.path.join(d, "log")
n = len(os.listdir(logmap))
with open(os.path.join(logmap, "%04d.json" % n), "w", encoding="utf-8") as f:
    json.dump([naam] + args, f)
if naam not in ("gdbus", "qdbus6"):
    sys.exit(0)
with open(os.path.join(d, "antwoorden.json"), encoding="utf-8") as f:
    a = json.load(f)
methode = args[args.index("--method") + 1] if "--method" in args else (args[2] if len(args) > 2 else "")
if methode.endswith("NameHasOwner"):
    print("(true,)" if a.get("bureaublad", True) else "(false,)")
    sys.exit(0)
if methode.endswith("KGlobalAccel.shortcut"):
    print(a.get("sneltoets", "([268435537],)"))
    sys.exit(0)
if methode.endswith("setForeignShortcut"):
    print("()")
    sys.exit(0)
if methode.endswith("evaluateScript"):
    if not a.get("plasma", True):
        sys.exit(1)
    oproep = args[-1].rsplit("\n}\n", 1)[-1]
    uit = "aan" if "heeft(" in oproep else "1"
    for stuk, antwoord in a.get("regels", []):
        if stuk in oproep:
            uit = antwoord
            break
    print("('%s',)" % uit if naam == "gdbus" else uit)
    sys.exit(0)
sys.exit(0)
'''


class Paneel:
    """bugos-panel in een tijdelijke map, met nep-programma's op PATH."""

    def __init__(self, tmp: Path, qdbus6: bool = True):
        self.tmp = tmp
        self.bin = tmp / "bin"
        self.bin.mkdir()
        (tmp / "log").mkdir()
        self.thuis = tmp / "thuis"
        self.config = self.thuis / ".config"
        self.merk = self.config / "bugos"
        self.merk.mkdir(parents=True)
        tekst = PANEEL_TEKST.replace("/usr/share/bugos", str(ROOT / "system_files/usr/share/bugos"))
        self.script = tmp / "paneel"
        self.script.write_text(tekst, encoding="utf-8", newline="\n")
        for naam in ("gdbus", "notify-send") + (("qdbus6",) if qdbus6 else ()):
            p = self.bin / naam
            p.write_text(NEP, encoding="utf-8", newline="\n")
            p.chmod(p.stat().st_mode | stat.S_IEXEC)
        for naam in ("kdialog", "sleep"):
            p = self.bin / naam
            p.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8", newline="\n")
            p.chmod(p.stat().st_mode | stat.S_IEXEC)
        self.antwoorden({})

    def antwoorden(self, a: dict) -> None:
        (self.tmp / "antwoorden.json").write_text(json.dumps(a), encoding="utf-8")

    def draai(self, *args: str) -> subprocess.CompletedProcess:
        for f in (self.tmp / "log").iterdir():
            f.unlink()
        env = dict(os.environ, HOME=str(self.thuis), XDG_CONFIG_HOME=str(self.config), NEP_MAP=str(self.tmp),
                   PATH=f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}", LANG="nl_NL.UTF-8", LC_ALL="nl_NL.UTF-8", LANGUAGE="")
        return subprocess.run(["bash", str(self.script), *args], env=env, capture_output=True, text=True, timeout=60)

    def log(self) -> list[list[str]]:
        return [json.loads(f.read_text(encoding="utf-8")) for f in sorted((self.tmp / "log").iterdir())]

    def scripts(self) -> list[str]:
        """Het stuk na het JS-blok van elk script dat naar Plasma ging."""
        uit = []
        for a in self.log():
            if a[0] in ("gdbus", "qdbus6") and any(x.endswith("evaluateScript") for x in a):
                uit.append(a[-1][len(JS):] if a[-1].startswith(JS) else "GEEN JS-BLOK: " + a[-1][:80])
        return uit

    def meldingen(self) -> list[str]:
        return [" ".join(a[1:]) for a in self.log() if a[0] == "notify-send"]


ALLE_MERKEN = ["paneel-hernoemd-1", "paneel-standaard-1", "paneel-systeemvak-1", "paneel-taakbalkruimte-1",
               "paneel-verhouding-1", "paneel-bureaubladmenu-1"]

if shutil.which("bash"):
    # Het echte BugOS heeft geen qdbus6 (alleen qdbus-qt6): dan praat bugos-panel via gdbus. Allebei proberen.
    for _met in ((True, False) if not shutil.which("qdbus6") else (True,)):
        with tempfile.TemporaryDirectory() as t:
            p = Paneel(Path(t), qdbus6=_met)
            uit = p.draai("snelmenu", "aan")
            sc = [s for s in p.scripts() if "vervang(" in s]
            via = "qdbus6" if _met else "gdbus"
            klopt(uit.returncode == 0 and len(sc) == 1 and sc[0].strip().startswith("slot(false);")
                  and sc[0].index("slot(false);") < sc[0].index("vervang(") and sc[0].rstrip().endswith("finally { slot(true); }")
                  and any(a[0] == via and any(x.endswith("evaluateScript") for x in a) for a in p.log()),
                  f"B1 ({via}): snelmenu aan: slot eraf, vervang, en (ook bij een fout) slot erop, in één script ({sc})")
    with tempfile.TemporaryDirectory() as t:
        p = Paneel(Path(t))
        klopt(all(s.startswith(" ") or s == "" for s in p.scripts()), "B1: elk script begint met het hele JS-blok")
        (p.merk / "paneel-bewerken").touch()
        p.draai("snelmenu", "aan")
        sc = [s for s in p.scripts() if "vervang(" in s]
        klopt(len(sc) == 1 and sc[0].rstrip().endswith("finally { slot(false); }"),
              f"B2: na 'bugos-panel bewerken aan' blijft het slot eraf ({sc})")
        (p.merk / "paneel-bewerken").unlink()

        for m in ALLE_MERKEN:
            (p.merk / m).touch()
        p.draai("standaard")
        sc = p.scripts()
        klopt(sc == [" slot(true);"],
              f"B4: standaard met alle stappen al gedaan: toch elke keer het slot erop, en verder niets ({sc})")
        for m in ALLE_MERKEN:
            (p.merk / m).unlink()
        p.antwoorden({"regels": [["bureaubladmenu();", "14"]]})
        p.draai("standaard")
        sc = p.scripts()
        _bm = [x for x in sc if "bureaubladmenu();" in x]
        klopt((p.merk / "paneel-bureaubladmenu-1").exists() and len(_bm) == 1 and "slot(false);" in _bm[0]
              and sc[-1] == " slot(true);",
              f"B5: standaard (nieuwe gebruiker): het bureaubladmenu wordt één keer aangepast en onthouden ({_bm})")
        (p.merk / "paneel-bureaubladmenu-1").unlink()
        p.antwoorden({"regels": [["bureaubladmenu();", "0"]]})
        p.draai("standaard")
        klopt(not (p.merk / "paneel-bureaubladmenu-1").exists(),
              "B7: lukt het bureaubladmenu niet (Plasma geeft 0), dan de volgende keer opnieuw (geen merkteken)")
        p.antwoorden({"plasma": False})
        uit = p.draai("standaard")
        klopt(uit.returncode == 0, f"B4: antwoordt Plasma niet, dan stopt standaard netjes (code {uit.returncode})")
        p.antwoorden({})


# --- D. style.sh -------------------------------------------------------------------------------------------------
klopt('--group "KDE Action Restrictions" --key plasma/allow_configure_when_locked false' in STYLE_TEKST,
      "D1: style.sh zet de kiosk-sleutel plasma/allow_configure_when_locked=false")
_code = "\n".join(r for r in STYLE_TEKST.split("\n") if not r.lstrip().startswith("#"))
klopt("unlockedDesktop" not in _code, "D2: style.sh gebruikt plasma/plasmashell/unlockedDesktop niet (breekt bugos-panel)")
_code = "\n".join(r for r in PANEEL_TEKST.split("\n") if not r.lstrip().startswith("#"))
klopt("unlockedDesktop" not in _code, "D2: bugos-panel gebruikt unlockedDesktop niet")


_skel = re.search(r"cat >/etc/skel/\.config/plasma-org\.kde\.plasma\.desktop-appletsrc <<'EOF'\n(.*?)\nEOF\n", STYLE_TEKST, re.S)
_regels = _skel.group(1).split("\n") if _skel else []
klopt(bool(_skel) and _regels[:2] == ["[ActionPlugins][0]", "RightButton;NoModifier=org.kde.contextmenu"]
      and "[ActionPlugins][0][RightButton;NoModifier]" in _regels
      and sorted(r for r in _regels if r.endswith("=false")) == sorted(f"{k}=false" for k in BUREAUBLAD_UIT)
      and not any("[ActionPlugins][1]" in r for r in _regels),
      "D3: nieuwe gebruikers krijgen het bureaubladmenu zonder de 14 KDE-regels (/etc/skel), en niets voor het paneel")
klopt(bool(_skel) and STYLE_TEKST.index("mkdir -p /etc/skel/.config") < _skel.start(),
      "D3: style.sh maakt /etc/skel/.config eerst")


# --- E. QML: de eigen regels in de rechtermuismenu's ------------------------------------------------------------
SLEUTELS = set()
for _f in (ROOT / "system_files/usr/lib/bugos/python").glob("bugos_settings_*.py"):
    SLEUTELS.update(re.findall(r'sleutel, icoon = "(\w+)"', lees(_f)))
APPS = {f.name for f in (ROOT / "system_files/usr/share/applications").glob("*.desktop")} | {"org.kde.konsole.desktop"}
# Woorden die in het Nederlands en het Engels hetzelfde zijn (dan mag de vertaling gelijk zijn).
ZELFDE = {"Terminal"}


def blok(tekst: str, begin: int) -> str:
    """Van het [ of { op plek 'begin' tot en met het bijbehorende sluitteken."""
    open_, dicht = tekst[begin], {"[": "]", "{": "}"}[tekst[begin]]
    diepte = 0
    for i in range(begin, len(tekst)):
        if tekst[i] == open_:
            diepte += 1
        elif tekst[i] == dicht:
            diepte -= 1
            if diepte == 0:
                return tekst[begin:i + 1]
    return tekst[begin:]


def acties(plasmoid: str) -> list[dict]:
    tekst = re.sub(r"//[^\n]*", "", lees(PLASMOIDS / plasmoid / "contents/ui/main.qml"))
    m = re.search(r"Plasmoid\.contextualActions:\s*\[", tekst)
    if not m:
        return []
    lijst = blok(tekst, m.end() - 1)
    uit = []
    for a in re.finditer(r"PlasmaCore\.Action\s*\{", lijst):
        stuk = blok(lijst, a.end() - 1)
        t_ = re.search(r'text:\s*root\.tr\("([^"]*)",\s*"([^"]*)"\)', stuk)
        doe = re.search(r'onTriggered:\s*root\.(voerUit|startApp)\("([^"]*)"\)', stuk)
        uit.append({"nl": t_.group(1) if t_ else "", "en": t_.group(2) if t_ else "",
                    "soort": doe.group(1) if doe else "", "wat": doe.group(2) if doe else "",
                    "icoon": bool(re.search(r'icon\.name:\s*"[\w-]+"', stuk))})
    return uit


def gaat_goed(a: dict) -> bool:
    if a["soort"] == "startApp":
        return a["wat"] in APPS
    m = re.fullmatch(r"bugos-start-data --start (?:instelling:(\w*)|/usr/share/applications/([\w.-]+\.desktop))", a["wat"])
    if not m:
        return False
    return (m.group(1) == "" or m.group(1) in SLEUTELS) if m.group(2) is None else m.group(2) in APPS


ALLE_ACTIES = {}
for _p in ("org.bugos.clock", "org.bugos.quickmenu", "org.bugos.taskbar", "org.bugos.startmenu"):
    ALLE_ACTIES[_p] = acties(_p)
    _a = ALLE_ACTIES[_p]
    klopt(bool(_a) and all(x["nl"] and x["en"] and (x["nl"] != x["en"] or x["en"] in ZELFDE) and x["icoon"] for x in _a),
          f"E2: {_p}: elke regel in het rechtermuismenu heeft een Nederlandse en Engelse tekst en een pictogram ({[x['en'] for x in _a]})")
    klopt(all(gaat_goed(x) for x in _a),
          f"E2: {_p}: elke regel opent een bestaande pagina van Instellingen of een bestaande app ({[x['wat'] for x in _a if not gaat_goed(x)]})")
    _t = lees(PLASMOIDS / _p / "contents/ui/main.qml")
    klopt(not re.search(r'internalAction\("configure"\)|setInternalAction|removeInternalAction', _t),
          f"E4: {_p}: geen eigen KDE-instellingenvenster (configure) in main.qml")
klopt([x["wat"] for x in ALLE_ACTIES["org.bugos.clock"]]
      == ["bugos-start-data --start instelling:tijd", "bugos-start-data --start instelling:meldingen"]
      and [x["en"] for x in ALLE_ACTIES["org.bugos.clock"]] == ["Adjust date and time", "Notification settings"],
      "E3: klok: precies 'Datum en tijd aanpassen' en 'Meldingsinstellingen', zoals Windows 11")
klopt([x["wat"] for x in ALLE_ACTIES["org.bugos.quickmenu"]]
      == ["bugos-start-data --start instelling:wifi", "bugos-start-data --start instelling:geluid",
          "bugos-start-data --start instelling:"]
      and "All settings" not in [x["en"] for x in ALLE_ACTIES["org.bugos.quickmenu"]],
      "E3: snelmenu: precies 'Wifi en internet', 'Geluidsinstellingen' en 'Instellingen openen' (niet 'Alle instellingen': dat is KDE)")
klopt("import org.kde.plasma.plasma5support as P5Support" in lees(PLASMOIDS / "org.bugos.clock/contents/ui/main.qml")
      and "id: opdracht" in lees(PLASMOIDS / "org.bugos.clock/contents/ui/main.qml"),
      "E3: de klok kan een opdracht starten (P5Support.DataSource)")


# --- F. De indeling voor nieuwe gebruikers -----------------------------------------------------------------------
INDELING_TEKST = lees(INDELING)
_regels = [r.strip() for r in INDELING_TEKST.split("\n") if r.strip() and not r.strip().startswith("//")]
klopt(_regels[-1] == 'if (typeof __AppInterface != "undefined") __AppInterface.locked = true;'
      and INDELING_TEKST.index("__AppInterface.locked = true") > INDELING_TEKST.index('d.writeConfig("Image"'),
      "F: de indeling zet als laatste het slot erop (na de achtergrond; op slot weigert Plasma addWidget)")


def draai_indeling(cfgs: dict | None = None) -> dict:
    e = QJSEngine()
    opzet = (f"var CFGS = {json.dumps(cfgs or {})}; var gemaakt = [];"
             "function Panel() { var p = maakContainment([], CFGS); gemaakt.push(p); return p; }"
             "var bureau = maakContainment([]); bureau.wallpaperPlugin = '';"
             "function desktopsForActivity(a) { return [bureau]; } function currentActivity() { return 'x'; }")
    r = e.evaluate(SIM + opzet + "\n" + INDELING_TEKST + "\nJSON.stringify({slot: __AppInterface.locked, "
                   "s: soorten(gemaakt[0]), vak: vak(gemaakt[0]) ? vak(gemaakt[0]).cfg : null})")
    return {"fout": r.toString()} if r.isError() else json.loads(r.toString())


r = draai_indeling()
klopt(r.get("slot") is True and (r.get("s") or [""])[0] == "org.bugos.startmenu"
      and "org.bugos.quickmenu" in r.get("s", []),
      f"F: de indeling draait in een nagebootst Plasma: startmenu eerst, snelmenu erbij, slot erop ({r.get('s') or r})")


print(f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
