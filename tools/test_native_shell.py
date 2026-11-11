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

# Het systeemvak zoals in de test-VM (Plasma 6.8.2, [General] extraItems: 19 onderdelen), plus een eigen app.
VM_EXTRA = ["org.kde.kdeconnect", "org.kde.plasma.vault", "org.kde.kscreen", "org.kde.plasma.battery",
            "org.kde.plasma.bluetooth", "org.kde.plasma.brightness", "org.kde.plasma.cameraindicator",
            "org.kde.plasma.clipboard", "org.kde.plasma.devicenotifier", "org.kde.plasma.dwellclicker",
            "org.kde.plasma.keyboardindicator", "org.kde.plasma.keyboardlayout", "org.kde.plasma.manage-inputmethod",
            "org.kde.plasma.mediacontroller", "org.kde.plasma.networkmanagement", "org.kde.plasma.notifications",
            "org.kde.plasma.printmanager", "org.kde.plasma.volume", "org.kde.plasma.weather"]
UIT = ["org.kde.plasma.volume", "org.kde.plasma.networkmanagement", "org.kde.plasma.bluetooth",
       "org.kde.plasma.battery", "org.kde.plasma.brightness", "org.kde.plasma.manage-inputmethod",
       "org.kde.kdeconnect", "org.kde.plasma.weather", "org.kde.plasma.vault", "org.kde.kscreen"]
BLIJFT = ["org.kde.plasma.clipboard", "org.kde.plasma.notifications", "org.kde.plasma.devicenotifier",
          "org.kde.plasma.printmanager", "org.kde.plasma.keyboardlayout", "org.kde.plasma.keyboardindicator",
          "org.kde.plasma.cameraindicator", "org.kde.plasma.mediacontroller", "org.kde.plasma.dwellclicker", "mijn.app"]
klopt(sorted(UIT + BLIJFT) == sorted(VM_EXTRA + ["mijn.app"]),
      "A7: over elk onderdeel van het systeemvak in de VM is besloten: uit of blijft")
_vak = {"org.kde.plasma.systemtray": {"extraItems": VM_EXTRA + ["mijn.app"], "hiddenItems": ["mijn.app"]}}
r = draai_js("var v = vak(paneel); " + wijzig("systeemvak(true);") + " var a = {extra: v.cfg.extraItems, uit: v.cfg.bugosOff,"
             " verborgen: v.cfg.hiddenItems, herladen: v.herladen}; " + wijzig("systeemvak(false);")
             + " var b = {extra: v.cfg.extraItems, uit: v.cfg.bugosOff};", "{a: a, b: b, js: UIT}", cfgs=_vak)
u = r["u"] or {}
a, b = u.get("a", {}), u.get("b", {})
klopt(u.get("js") == UIT, f"A7: de UIT-lijst van bugos-panel is de lijst uit het ontwerp ({u.get('js')})")
klopt(r["gedrukt"] == ["1", "1"] and sorted(a.get("extra", [])) == sorted(BLIJFT) and sorted(a.get("uit", [])) == sorted(UIT)
      and a.get("herladen") == 1,
      f"A7: snelmenu aan: de KDE-onderdelen die het snelmenu vervangt staan UIT (niet alleen verborgen) en zijn onthouden ({r})")
klopt(sorted(b.get("extra", [])) == sorted(VM_EXTRA + ["mijn.app"]) and b.get("uit") == [""],
      f"A7: snelmenu uit: precies die komen terug ({b})")
klopt("org.kde.plasma.keyboardlayout" not in a.get("verborgen", []) and "org.kde.plasma.keyboardlayout" in a.get("extra", []),
      "A7: de toetsenbordindeling blijft aan en zichtbaar (zoals Windows 11, met twee of meer indelingen)")
_zonder = [x for x in VM_EXTRA if x != "org.kde.plasma.weather"]
r = draai_js(wijzig("systeemvak(true);") + wijzig("systeemvak(false);"), "vak(paneel).cfg.extraItems",
             cfgs={"org.kde.plasma.systemtray": {"extraItems": _zonder}})
klopt(r["u"] is not None and "org.kde.plasma.weather" not in r["u"] and sorted(r["u"]) == sorted(_zonder),
      f"A7: wat je zelf uitzette (Weer) komt niet terug als het snelmenu uit gaat ({r['u']})")
r = draai_js(wijzig("systeemvak(true);"), "vak(paneel).cfg", cfgs={"org.kde.plasma.systemtray": {}})
klopt(r["u"] is not None and "extraItems" not in r["u"] and r["u"].get("bugosOff") == [""],
      f"A7: een systeemvak zonder extraItems: er wordt niets uitgezet en niets verzonnen ({r['u']})")
r = draai_js(wijzig("systeemvak(true);") + wijzig("systeemvak(true);"), "vak(paneel).cfg",
             cfgs={"org.kde.plasma.systemtray": {"extraItems": ",".join(VM_EXTRA)}})
klopt(r["u"] is not None and sorted(r["u"].get("bugosOff", [])) == sorted(UIT)
      and not set(UIT) & set(r["u"].get("extraItems", [])),
      f"A7: twee keer aan (en een lijst als tekst, zoals Plasma soms geeft): bugosOff blijft compleet ({r['u']})")
# U456 (zoals tools/test_panel.sh, maar zonder node): wat je zelf verborg, blijft verborgen.
r = draai_js(wijzig("systeemvak(true);") * 2 + wijzig("systeemvak(false);"), "vak(paneel).cfg.hiddenItems",
             cfgs={"org.kde.plasma.systemtray": {"hiddenItems": ["org.kde.kdeconnect", "mijn.app"]}})
klopt(r["u"] == ["org.kde.kdeconnect", "mijn.app"], f"A7/U456: snelmenu aan en uit: wat je zelf verborg, blijft verborgen ({r['u']})")
_vroeger = ["org.kde.plasma.volume", "org.kde.plasma.networkmanagement", "org.kde.plasma.bluetooth", "org.kde.plasma.battery",
            "org.kde.plasma.brightness", "org.kde.kscreen", "org.kde.plasma.clipboard", "org.kde.plasma.keyboardlayout",
            "org.kde.plasma.keyboardindicator", "org.kde.plasma.manage-inputmethod", "org.kde.plasma.printmanager",
            "org.kde.kdeconnect", "org.kde.plasma.weather"]
r = draai_js(wijzig("systeemvak(false);"), "vak(paneel).cfg.hiddenItems",
             cfgs={"org.kde.plasma.systemtray": {"hiddenItems": ["mijn.app"] + _vroeger}})
klopt(r["u"] == ["mijn.app"], f"A7/U456: na een oudere BugOS (ook met de toetsenbordindeling): snelmenu uit laat ze weer zien ({r['u']})")
r = draai_js(wijzig("systeemvak(true);"), "vak(paneel).cfg.hiddenItems", cfgs={"org.kde.plasma.systemtray": {"hiddenItems": ["mijn.app"]}})
klopt((r["u"] or [])[:2] == ["mijn.app", "org.kde.plasma.volume"] and "org.kde.plasma.keyboardlayout" not in r["u"],
      f"A7/U456: snelmenu aan verbergt de BugOS-lijst erbij, zonder de toetsenbordindeling ({r['u']})")
r = draai_js(wijzig("systeemvak(true);"), "vak(paneel).cfg.hiddenItems",
             cfgs={"org.kde.plasma.systemtray": {"hiddenItems": ["org.kde.plasma.keyboardlayout"],
                                                 "bugosHidden": ["org.kde.plasma.keyboardlayout", "org.kde.plasma.volume"]}})
klopt(r["u"] is not None and "org.kde.plasma.keyboardlayout" not in r["u"],
      f"A7: wie de vorige BugOS had: de toetsenbordindeling die BugOS verborg, is weer te zien ({r['u']})")

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
                   PATH=f"{self.bin}{os.pathsep}{os.environ.get('PATH', '')}", LANGUAGE="")
        # Nederlands, zoals de andere tests (t() kijkt naar LANG); zonder LC_ALL, want die taal hoeft niet geïnstalleerd te zijn.
        for k in ("LC_ALL", "LC_MESSAGES"):
            env.pop(k, None)
        env["LANG"] = "nl_NL.UTF-8"
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
               "paneel-verhouding-1", "paneel-bureaubladmenu-1", "paneel-systeemvak-2", "paneel-sneltoets-1"]
META_Q_ID = "['plasmashell','manage activities','plasmashell','Show Activity Switcher']"

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
            klopt(p.scripts() and all(s.startswith(" ") for s in p.scripts()), f"B1 ({via}): elk script begint met het hele JS-blok")
    with tempfile.TemporaryDirectory() as t:
        p = Paneel(Path(t))
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
        klopt(sc == [" slot(true);"] and not [a for a in p.log() if "org.kde.KGlobalAccel.shortcut" in a],
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
        _vak = [x for x in sc if "systeemvak(true);" in x]
        klopt((p.merk / "paneel-systeemvak-2").exists() and len(_vak) == 2,
              f"B5: standaard (nieuwe gebruiker): systeemvak(true) voor stap 2 en de nieuwe stap 6, allebei onthouden ({_vak})")
        (p.merk / "paneel-systeemvak-2").unlink()
        p.antwoorden({"regels": [['heeft("org.bugos.quickmenu")', "uit"]]})
        p.draai("standaard")
        klopt((p.merk / "paneel-systeemvak-2").exists() and not [x for x in p.scripts() if "systeemvak(" in x],
              "B5: staat het snelmenu uit, dan blijft het systeemvak zoals het is (en is stap 6 klaar)")

        # Meta+Q (KDE: zijpaneel Activiteiten).
        def sneltoets(antwoord: str) -> list[list[str]]:
            m = p.merk / "paneel-sneltoets-1"
            if m.exists():
                m.unlink()
            p.antwoorden({"sneltoets": antwoord})
            p.draai("standaard")
            return [a for a in p.log() if "org.kde.KGlobalAccel.setForeignShortcut" in a]
        _zet = sneltoets("([268435537],)")
        klopt(len(_zet) == 1 and _zet[0][-2:] == [META_Q_ID, "@ai []"] and (p.merk / "paneel-sneltoets-1").exists(),
              f"B5: Meta+Q (nog de standaard van KDE) gaat uit, één keer, en wordt onthouden ({_zet})")
        _zet = sneltoets("([268435538],)")
        klopt(not _zet and (p.merk / "paneel-sneltoets-1").exists(),
              "B6: zelf een andere toets gekozen: niet aankomen (wel onthouden)")
        _zet = sneltoets("(@ai [],)")
        klopt(not _zet and not (p.merk / "paneel-sneltoets-1").exists(),
              "B6: leeg antwoord (Plasma heeft de sneltoets nog niet aangemeld): niets doen, de volgende keer opnieuw kijken")
        _zet = sneltoets("")
        klopt(not _zet and not (p.merk / "paneel-sneltoets-1").exists(), "B6: geen antwoord van KDE: de volgende keer opnieuw")
        # De deur voor gevorderden.
        p.antwoorden({})
        uit = p.draai("bewerken", "aan")
        klopt(uit.returncode == 0 and (p.merk / "paneel-bewerken").exists() and p.scripts() == [" slot(false);"]
              and any("Taakbalk en bureaublad zijn los" in m and "bugos-panel bewerken uit" in m for m in p.meldingen()),
              f"B3: bewerken aan: slot eraf, onthouden, en een melding hoe je het terugzet ({p.scripts()}, {p.meldingen()})")
        klopt(p.draai("bewerken", "status").stdout.strip() == "aan", "B3: bewerken status: aan")
        p.draai("standaard")
        klopt(p.scripts() and p.scripts()[-1] == " slot(false);" and not any("slot(true)" in s for s in p.scripts()),
              f"B3: na opnieuw inloggen blijft het los ({p.scripts()})")
        uit = p.draai("bewerken", "uit")
        klopt(uit.returncode == 0 and not (p.merk / "paneel-bewerken").exists() and p.scripts() == [" slot(true);"]
              and any("weer vast" in m for m in p.meldingen()),
              f"B3: bewerken uit: slot erop, vergeten, melding ({p.scripts()}, {p.meldingen()})")
        klopt(p.draai("bewerken", "status").stdout.strip() == "uit", "B3: bewerken status: uit")
        p.antwoorden({"plasma": False})
        uit = p.draai("bewerken", "aan")
        klopt(uit.returncode != 0 and not (p.merk / "paneel-bewerken").exists() and "niet bereikbaar" in uit.stderr,
              f"B3: antwoordt Plasma niet: gewone zin, en niets onthouden ({uit.stderr.strip()})")
        uit = p.draai()
        klopt(uit.returncode == 2 and "bewerken aan|uit|status" in uit.stderr, f"B8: de uitleg noemt 'bewerken' ({uit.stderr.strip()})")
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
klopt(re.search(r"^bureaubladmenu /usr/share/plasma/plasmoids/org\.kde\.desktopcontainment/contents/ui \\\n"
                r" +/usr/share/plasma/plasmoids/org\.bugos\.taskbar/contents/ui/BureaubladActies\.qml$", STYLE_TEKST, re.M)
      is not None, "D4: style.sh past de mapweergave van KDE aan (org.kde.desktopcontainment) met BureaubladActies.qml")


# --- C. style.sh: bureaubladmenu op nagemaakte KDE-bestanden ----------------------------------------------------
BRON = PLASMOIDS / "org.bugos.taskbar/contents/ui/BureaubladActies.qml"
_f = re.search(r"^# >>> bureaubladmenu.*?\n(.*?)^# <<< bureaubladmenu", STYLE_TEKST, re.S | re.M)
klopt(_f is not None and "bureaubladmenu() {" in _f.group(1), "C: style.sh heeft de functie bureaubladmenu tussen de merktekens")
LAAG = """import QtQuick
FolderViewDropArea {
    id: folderViewLayerComponent
    Component.onCompleted: {
        Plasmoid.contextualActions.push(nieuw);
        Plasmoid.contextualActions.push(actionSeparator);
        Plasmoid.contextualActions.push(laatste);
    }
}
"""
HOOFD = """PlasmoidItem {
    PlasmaCore.Action {
            id: configAction
            text: "Desktop and Wallpaper"
            shortcut:"Ctrl+Shift+D"
            onTriggered: configureRequested()
    }
}
"""
if _f and shutil.which("bash"):
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        (t / "functie.sh").write_text(_f.group(1), encoding="utf-8", newline="\n")
        (t / "draai.sh").write_text('set -euo pipefail\n. "$(dirname "$0")/functie.sh"\nbureaubladmenu "$1" "$2"\n',
                                    encoding="utf-8", newline="\n")

        def bouw(ui: Path) -> subprocess.CompletedProcess:
            bron = t / "bron.qml"
            bron.write_text(lees(BRON), encoding="utf-8", newline="\n")
            return subprocess.run(["bash", str(t / "draai.sh"), str(ui), str(bron)], capture_output=True, text=True, timeout=30)

        ui = t / "ui"
        ui.mkdir()
        (ui / "FolderViewLayer.qml").write_text(LAAG, encoding="utf-8", newline="\n")
        (ui / "main.qml").write_text(HOOFD, encoding="utf-8", newline="\n")
        u1 = bouw(ui)
        laag = (ui / "FolderViewLayer.qml").read_text(encoding="utf-8").split("\n")
        i = laag.index("        Plasmoid.contextualActions.push(actionSeparator);")
        ingevoegd = laag[i + 1] if i + 1 < len(laag) else ""
        klopt(u1.returncode == 0 and "LET OP" not in u1.stdout
              and (ui / "BugosBureaubladActies.qml").read_text(encoding="utf-8") == lees(BRON)
              and ingevoegd.startswith("        if (Plasmoid.isContainment) {") and "BugosBureaubladActies.qml" in ingevoegd
              and ingevoegd.endswith("// BugOS") and laag[i + 2] == "        Plasmoid.contextualActions.push(laatste);",
              f"C1: de BugOS-regels komen direct na het scheidingsstreepje, even ver ingesprongen ({u1.stdout.strip()[:200]})")
        klopt("Ctrl+Shift+D" not in (ui / "main.qml").read_text(encoding="utf-8")
              and "onTriggered: configureRequested()" in (ui / "main.qml").read_text(encoding="utf-8"),
              "C1: Ctrl+Shift+D (KDE's achtergrondvenster) is weg, de rest van main.qml blijft")
        _js = QJSEngine().evaluate("(function () { " + ingevoegd + " })")
        klopt(not _js.isError(), f"C1: de ingevoegde regel is geldige JavaScript ({_js.toString() if _js.isError() else 'ok'})")
        u2 = bouw(ui)
        klopt(u2.returncode == 0 and (ui / "FolderViewLayer.qml").read_text(encoding="utf-8").count("BugosBureaubladActies.qml") == 1,
              "C2: twee keer bouwen: de regel staat er nog steeds maar één keer")

        ui3 = t / "ui3"
        ui3.mkdir()
        anders = LAAG.replace("Plasmoid.contextualActions.push(actionSeparator);", "Plasmoid.contextualActions.push(streep);")
        (ui3 / "FolderViewLayer.qml").write_text(anders, encoding="utf-8", newline="\n")
        (ui3 / "main.qml").write_text(HOOFD, encoding="utf-8", newline="\n")
        u3 = bouw(ui3)
        klopt(u3.returncode == 0 and "LET OP" in u3.stdout
              and (ui3 / "FolderViewLayer.qml").read_text(encoding="utf-8") == anders
              and not (ui3 / "BugosBureaubladActies.qml").exists(),
              "C3: een nieuwe KDE-versie (FolderViewLayer.qml anders): de bouw gaat door met LET OP, niets half veranderd")
        klopt("Ctrl+Shift+D" not in (ui3 / "main.qml").read_text(encoding="utf-8"),
              "C3: ... en Ctrl+Shift+D is toch weg (los van FolderViewLayer.qml)")
        u4 = bouw(t / "bestaat-niet")
        klopt(u4.returncode == 0 and "LET OP" in u4.stdout, "C4: de mapweergave ontbreekt helemaal: de bouw gaat door met LET OP")


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
STUB_ACTION = """import QtQuick
QtObject { property string text; property Icon icon: Icon {}; signal triggered(); function trigger() { triggered() } }
"""
STUB_DATASOURCE = """import QtQuick
QtObject { property string engine; property var connectedSources: []; property var log: []
    signal newData(string bron, var data)
    function connectSource(s) { log = log.concat([s]) }
    function disconnectSource(s) {} }
"""


def bureaublad_acties(taal: str) -> dict:
    """Laad BureaubladActies.qml met nagemaakte Plasma-modules; klik op elke regel. Geeft teksten, pictogrammen en
    de opdrachten terug."""
    from PySide6.QtCore import QLocale, QMetaObject, QUrl
    from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression, QQmlListReference
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        core = t / "org/kde/plasma/core"
        p5 = t / "org/kde/plasma/plasma5support"
        core.mkdir(parents=True)
        p5.mkdir(parents=True)
        (core / "qmldir").write_text("module org.kde.plasma.core\nAction 1.0 Action.qml\nIcon 1.0 Icon.qml\n", encoding="utf-8")
        (core / "Icon.qml").write_text("import QtQuick\nQtObject { property string name }\n", encoding="utf-8")
        (core / "Action.qml").write_text(STUB_ACTION, encoding="utf-8")
        (p5 / "qmldir").write_text("module org.kde.plasma.plasma5support\nDataSource 1.0 DataSource.qml\n", encoding="utf-8")
        (p5 / "DataSource.qml").write_text(STUB_DATASOURCE, encoding="utf-8")
        QLocale.setDefault(QLocale(taal))
        engine = QQmlEngine()
        engine.addImportPath(str(t))
        comp = QQmlComponent(engine, QUrl.fromLocalFile(str(BRON)))
        obj = comp.create()
        if obj is None:
            return {"fout": "; ".join(e.toString() for e in comp.errors())}
        lijst = QQmlListReference(obj, "acties")
        uit = {"teksten": [], "iconen": []}
        for i in range(lijst.count()):
            a = lijst.at(i)
            uit["teksten"].append(a.property("text"))
            ic = QQmlExpression(engine.rootContext(), a, "icon.name").evaluate()
            uit["iconen"].append(ic[0] if isinstance(ic, tuple) else ic)
            QMetaObject.invokeMethod(a, "trigger")
        log = QQmlExpression(engine.rootContext(), obj, "JSON.stringify(opdracht.log)").evaluate()
        uit["log"] = json.loads(log[0] if isinstance(log, tuple) else log)
        obj.deleteLater()
        return uit


_en = bureaublad_acties("en_US")
_nl = bureaublad_acties("nl_NL")
klopt(_en.get("teksten") == ["Display settings", "Change background"]
      and _nl.get("teksten") == ["Scherminstellingen", "Achtergrond wijzigen"],
      f"E1: bureaublad: 'Scherminstellingen' en 'Achtergrond wijzigen' in het Nederlands en Engels ({_en}, {_nl.get('teksten')})")
klopt(_en.get("log") == ["bugos-start-data --start instelling:scherm", "bugos-start-data --start instelling:uiterlijk"]
      and {"scherm", "uiterlijk"} <= SLEUTELS,
      f"E1: bureaublad: de regels openen Instellingen > Scherm en > Uiterlijk ({_en.get('log')})")
klopt(_en.get("iconen") == ["preferences-desktop-display", "preferences-desktop-wallpaper"],
      f"E1: bureaublad: met de pictogrammen van scherm en achtergrond ({_en.get('iconen')})")

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
klopt(r.get("vak") is not None and "extraItems" not in r["vak"] and "bugosOff" not in r["vak"],
      f"F: heeft Plasma extraItems nog niet ingevuld, dan laat de indeling die met rust (bugos-panel doet het later) ({r.get('vak')})")
r = draai_indeling({"org.kde.plasma.systemtray": {"extraItems": VM_EXTRA}})
_v = r.get("vak") or {}
klopt(sorted(_v.get("extraItems", [])) == sorted(x for x in VM_EXTRA if x not in UIT)
      and sorted(_v.get("bugosOff", [])) == sorted(UIT),
      f"F: nieuwe gebruiker: de KDE-onderdelen die het snelmenu vervangt staan meteen uit, en zijn onthouden ({_v})")
_e = QJSEngine()
_e.evaluate(JS)
_paneel_lijsten = json.loads(_e.evaluate("JSON.stringify([RUSTIG, UIT])").toString())
klopt(_v.get("hiddenItems") == _paneel_lijsten[0], "F: de indeling verbergt dezelfde lijst als bugos-panel (RUSTIG)")
klopt(sorted(_v.get("bugosOff", [])) == sorted(_paneel_lijsten[1]), "F: de indeling zet dezelfde lijst uit als bugos-panel (UIT)")
klopt("org.kde.plasma.keyboardlayout" not in _v.get("hiddenItems", ["org.kde.plasma.keyboardlayout"]),
      "F: de toetsenbordindeling is niet verborgen (met twee of meer indelingen naast de klok)")


print(f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
