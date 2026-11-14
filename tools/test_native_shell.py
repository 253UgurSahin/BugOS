#!/usr/bin/env python3
"""Test van de taakbalk en het bureaublad zonder KDE-bewerkmodus (pakket shell).

Wat er getest wordt, zonder Plasma en zonder node:
  A. de JavaScript van bugos-panel in een nagebootst Plasma (PySide6 QJSEngine): het slot, eerlijk vervang(),
     het bureaubladmenu, het systeemvak (KDE-onderdelen alleen uit naast het snelmenu, en nooit wat je in KDE
     "Always shown" gaf);
  B. bugos-panel zelf (bash) met nep-programma's (gdbus, qdbus6, notify-send): wat hij naar Plasma stuurt, en
     welke eenmalige stappen hij onthoudt (merktekens);
  C. de functie bureaubladmenu uit build_files/style.sh op nagemaakte KDE-bestanden;
  D. style.sh: de kiosk-sleutel, het bestand voor nieuwe gebruikers, het menu op bestanden (kservicemenurc en het
     Filelight-servicemenu), Discover en Filelight uit het startmenu (met en zonder Discover in het beeld);
  E. de QML: de eigen regels in de rechtermuismenu's (bureaublad, klok, snelmenu);
  F. de indeling voor nieuwe gebruikers (look-and-feel) in een nagebootst Plasma;
  G. systeemvakNaUpdate(), de eenmalige stap 6 voor wie al een taakbalk had: wat hij doet, dat twee keer hetzelfde
     is als één keer, dat hij wacht als Plasma het systeemvak nog niet had ingevuld, dat wat je zelf zichtbaar
     wilde ("Always shown", of weer laten zien) aan blijft, en dat geen enkele combinatie van instellingen het
     systeemvak kapotmaakt.
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
# Dezelfde taakbalk met het snelmenu erop (vlak voor het systeemvak), zoals na "snelmenu aan" en bij een nieuwe
# gebruiker. Alleen dan zet systeemvak(true) de KDE-onderdelen die het snelmenu vervangt ook echt uit (A10).
TAAKBALK_SNEL = TAAKBALK[:3] + ["org.bugos.quickmenu"] + TAAKBALK[3:]


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
             + " var b = {extra: v.cfg.extraItems, uit: v.cfg.bugosOff};", "{a: a, b: b, js: UIT}", begin=TAAKBALK_SNEL,
             cfgs=_vak)
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
             begin=TAAKBALK_SNEL, cfgs={"org.kde.plasma.systemtray": {"extraItems": _zonder}})
klopt(r["u"] is not None and "org.kde.plasma.weather" not in r["u"] and sorted(r["u"]) == sorted(_zonder),
      f"A7: wat je zelf uitzette (Weer) komt niet terug als het snelmenu uit gaat ({r['u']})")
r = draai_js(wijzig("systeemvak(true);"), "vak(paneel).cfg", begin=TAAKBALK_SNEL, cfgs={"org.kde.plasma.systemtray": {}})
klopt(r["u"] is not None and "extraItems" not in r["u"] and r["u"].get("bugosOff") == [""],
      f"A7: een systeemvak zonder extraItems: er wordt niets uitgezet en niets verzonnen ({r['u']})")
r = draai_js(wijzig("systeemvak(true);") + wijzig("systeemvak(true);"), "vak(paneel).cfg", begin=TAAKBALK_SNEL,
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

# A10 (review): zonder snelmenu op de taakbalk (bijv. "bugos-panel systeemvak rustig" met het snelmenu uit) verbergt
# systeemvak(true) alleen, zoals de vorige BugOS: er gaat niets uit, dus geluid, netwerk en batterij blijven achter
# het pijltje te zien. Wat BugOS eerder uitzette (het snelmenu ging op een andere manier weg), komt terug.
r = draai_js(wijzig("systeemvak(true);"), "{cfg: vak(paneel).cfg, rustig: RUSTIG}",
             cfgs={"org.kde.plasma.systemtray": {"extraItems": VM_EXTRA + ["mijn.app"]}})
u = r["u"] or {}
c = u.get("cfg") or {}
klopt(r["gedrukt"] == ["1"] and "org.bugos.quickmenu" not in TAAKBALK
      and sorted(c.get("extraItems", [])) == sorted(VM_EXTRA + ["mijn.app"]) and c.get("bugosOff") == [""]
      and c.get("hiddenItems") == u.get("rustig"),
      f"A10: zonder snelmenu: systeemvak rustig verbergt de BugOS-lijst, maar zet niets uit ({c})")
_al_uit = [x for x in VM_EXTRA if x not in UIT]
r = draai_js(wijzig("systeemvak(true);"), "vak(paneel).cfg",
             cfgs={"org.kde.plasma.systemtray": {"extraItems": list(_al_uit), "bugosOff": list(UIT)}})
c = r["u"] or {}
klopt(sorted(c.get("extraItems", [])) == sorted(_al_uit + UIT) and c.get("bugosOff") == [""],
      f"A10: zonder snelmenu komt terug wat BugOS eerder uitzette (anders zie je nergens netwerk of geluid) ({c})")
r = draai_js(wijzig("systeemvak(true);"), "vak(paneel).cfg", begin=TAAKBALK_SNEL,
             cfgs={"org.kde.plasma.systemtray": {"extraItems": list(VM_EXTRA)}})
klopt(r["u"] is not None and not set(UIT) & set(r["u"].get("extraItems", [])),
      "A10: ter vergelijking: staat het snelmenu er wel, dan gaan ze echt uit")

# A11 (review): systeemvak(true) zet nooit uit wat je in KDE "Always shown" gaf (shownItems: dat schrijft alleen
# KDE, als jij het kiest). Uitzetten haalt het pictogram helemaal weg, en op slot kun je het niet terugzetten. Staat
# zo een onderdeel nog in bugosOff (BugOS zette het ooit uit, jij zette het weer aan), dan gaat het daar uit, zodat
# "snelmenu uit" niets terugzet wat je later misschien zelf uitzet. Ook als Plasma shownItems als tekst geeft.
BAT, NET = "org.kde.plasma.battery", "org.kde.plasma.networkmanagement"
for _getoond in ([BAT], BAT, [BAT, "mijn.app"]):
    r = draai_js(wijzig("systeemvak(true);") + " var a = JSON.parse(JSON.stringify(vak(paneel).cfg));"
                 + wijzig("systeemvak(false);"), "{a: a, b: vak(paneel).cfg}", begin=TAAKBALK_SNEL,
                 cfgs={"org.kde.plasma.systemtray": {"extraItems": list(VM_EXTRA), "shownItems": _getoond,
                                                     "bugosOff": [BAT, "org.kde.plasma.vault"]}})
    u = r["u"] or {}
    a, b = u.get("a") or {}, u.get("b") or {}
    klopt(r["fout"] is None and BAT in a.get("extraItems", []) and BAT not in a.get("bugosOff", [])
          and sorted(a.get("bugosOff", [])) == sorted(x for x in UIT if x != BAT) and a.get("shownItems") == _getoond
          and sorted(b.get("extraItems", [])) == sorted(VM_EXTRA) and b.get("bugosOff") == [""],
          f"A11: snelmenu aan laat aan wat je 'Always shown' gaf (shownItems {_getoond!r}), haalt het uit bugosOff, en "
          f"snelmenu uit zet de rest terug ({a.get('bugosOff')}, {b.get('extraItems')})")

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
    # "fout": Plasma geeft een D-Bus-fout (bijv. een fout in het script) op elk script met dat stuk erin.
    if any(stuk in oproep for stuk in a.get("fout", [])):
        sys.exit(1)
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
        # Een nieuwe gebruiker: Plasma zegt "klaar" op stap 6 (het systeemvak is bijgewerkt).
        p.antwoorden({"regels": [["bureaubladmenu();", "14"], ["systeemvakNaUpdate();", "klaar"]]})
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
        # Stap 2 verbergt de BugOS-lijst (systeemvak(true)); stap 6 is systeemvakNaUpdate(), juist NIET nog eens
        # systeemvak(true): die zou bij wie al een taakbalk had alles weer verbergen wat hij zelf zichtbaar maakte.
        _vak = [x for x in sc if "systeemvak(true);" in x]
        _na = [x for x in sc if "systeemvakNaUpdate();" in x]
        klopt((p.merk / "paneel-systeemvak-2").exists() and len(_vak) == 1 and len(_na) == 1
              and sc.index(_vak[0]) < sc.index(_na[0])
              and _na[0].strip() == "slot(false); try { systeemvakNaUpdate(); } finally { slot(true); }",
              f"B5: standaard (nieuwe gebruiker): stap 2 is systeemvak(true), stap 6 is systeemvakNaUpdate() met het slot eraf "
              f"en er weer op, en stap 6 is onthouden ({_vak}, {_na})")
        (p.merk / "paneel-systeemvak-2").unlink()
        p.antwoorden({"regels": [['heeft("org.bugos.quickmenu")', "uit"]]})
        p.draai("standaard")
        klopt((p.merk / "paneel-systeemvak-2").exists()
              and not [x for x in p.scripts() if "systeemvak(" in x or "systeemvakNaUpdate(" in x],
              "B5: staat het snelmenu uit, dan blijft het systeemvak zoals het is (en is stap 6 klaar)")

        # B9: stap 6 draait één keer, en alleen een merkteken als het echt lukte. De andere stappen zijn al gedaan.
        for m in ALLE_MERKEN:
            (p.merk / m).touch()

        def stap6(antwoorden: dict) -> tuple[list[str], bool]:
            """standaard met alleen stap 6 nog open (als het merkteken weg is): de scripts met systeemvakNaUpdate()
            en of het merkteken er daarna staat."""
            p.antwoorden(antwoorden)
            p.draai("standaard")
            return [x for x in p.scripts() if "systeemvakNaUpdate();" in x], (p.merk / "paneel-systeemvak-2").exists()

        (p.merk / "paneel-systeemvak-2").unlink()
        _s, _m = stap6({"regels": [["systeemvakNaUpdate();", "later"]]})
        klopt(len(_s) == 1 and not _m and p.scripts()[-1] == " slot(true);",
              f"B9: Plasma had de onderdelen van het systeemvak nog niet ('later'): geen merkteken, wel het slot erop ({_s})")
        _s, _m = stap6({"regels": [["systeemvakNaUpdate();", "later"]]})
        klopt(len(_s) == 1 and not _m, "B9: ... dus bij het volgende inloggen probeert stap 6 het opnieuw")
        _s, _m = stap6({"regels": [["systeemvakNaUpdate();", "1"]]})
        klopt(len(_s) == 1 and not _m, "B9: een onverwacht antwoord (bijv. '1' van een oudere bugos-panel) telt niet als klaar")
        _s, _m = stap6({"fout": ["systeemvakNaUpdate();"]})
        klopt(len(_s) == 1 and not _m, "B9: een fout van Plasma in stap 6: geen merkteken")
        _s, _m = stap6({"fout": ['heeft("org.bugos.quickmenu")']})
        klopt(not _s and not _m,
              "B9: geen antwoord op de vraag of het snelmenu er staat: niets doen en niets onthouden (niet als 'uit' tellen)")
        _s, _m = stap6({"regels": [["systeemvakNaUpdate();", "klaar"]]})
        klopt(len(_s) == 1 and _m, f"B9: 'klaar': stap 6 is onthouden ({_s})")
        _s, _m = stap6({"regels": [["systeemvakNaUpdate();", "klaar"]]})
        klopt(not _s and _m and p.scripts() == [" slot(true);"],
              f"B9: daarna draait stap 6 nooit meer (eenmalig); alleen het slot gaat er weer op ({p.scripts()})")

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
# A-16: het vergrendelscherm gebruikt de donkere Stip, zodat de witte klok en datum ook in lichte modus leesbaar
# zijn (op de lichte Stip stonden ze op bijna wit). Het bestand moet ook echt bestaan.
_slot = re.search(r"kscreenlockerrc .*?--key Image \"file://([^\"]+)\"", STYLE_TEKST, re.S)
klopt(bool(_slot) and "images_dark" in _slot.group(1)
      and (ROOT / "system_files" / _slot.group(1).lstrip("/")).is_file(),
      "D2b (A-16): het vergrendelscherm gebruikt de donkere Stip (bestaand bestand), niet de lichte")


_skel = re.search(r"cat >/etc/skel/\.config/plasma-org\.kde\.plasma\.desktop-appletsrc <<'EOF'\n(.*?)\nEOF\n", STYLE_TEKST, re.S)
_regels = _skel.group(1).split("\n") if _skel else []
klopt(bool(_skel) and _regels[:2] == ["[ActionPlugins][0]", "RightButton;NoModifier=org.kde.contextmenu"]
      and "[ActionPlugins][0][RightButton;NoModifier]" in _regels
      and sorted(r for r in _regels if r.endswith("=false")) == sorted(f"{k}=false" for k in BUREAUBLAD_UIT)
      and not any("[ActionPlugins][1]" in r for r in _regels),
      "D3: nieuwe gebruikers krijgen het bureaubladmenu zonder de 14 KDE-regels (/etc/skel), en niets voor het paneel")
klopt(bool(_skel) and STYLE_TEKST.index("mkdir -p /etc/skel/.config") < _skel.start(),
      "D3: style.sh maakt /etc/skel/.config eerst")
# D5: Discover en Filelight staan niet in het startmenu. Het pakket store haalt Discover uit het beeld (build.sh); dit
# pakket moet werken met én zonder Discover: zolang de basis hem meebrengt is hij verborgen, is hij weg dan doet
# verberg niets. En nergens een "Meer apps"-naam die gebruikers naar Discover stuurt.
_lussen = [m.group(0) for m in re.finditer(r"^for app in .*?\ndone\n", STYLE_TEKST, re.S | re.M)]
_kde_lus = next((l for l in _lussen if "org.kde.dolphin.desktop" in l and 'verberg "$app"' in l), "")
_namen = _kde_lus.split(";", 1)[0].replace("\\\n", " ").split()[3:]
klopt("org.kde.discover.desktop" in _namen and "org.kde.filelight.desktop" in _namen,
      f"D5: style.sh verbergt Discover (zolang de basis hem meebrengt) en Filelight (Bestanden laat zelf de grootste mappen zien) ({_namen[:4]}...)")
_style_code = [r for r in STYLE_TEKST.split("\n") if not r.lstrip().startswith("#")]
klopt(not any("discover" in r.lower() and "hernoem" in r for r in _style_code)
      and not any("Meer apps" in r or "More apps" in r for r in _style_code),
      "D5: style.sh geeft Discover geen BugOS-naam meer ('Meer apps'): niets wijst nog naar Discover")
klopt("Schijfbeheer\" in Bestanden" not in STYLE_TEKST and "\"Meer apps\" in de Winkel" not in STYLE_TEKST,
      "D5: het commentaar in style.sh belooft geen Schijfbeheer in Bestanden en geen 'Meer apps' meer")
# De echte hulpjes en de echte lus uit style.sh draaien, met set -euo pipefail zoals build.sh (set -ouex pipefail):
# één keer met Discover (zoals in Kinoite 44: NoDisplay=false) en Filelight erin, één keer zonder.
_hulp = {n: re.search(rf"^{n}\(\) \{{\n.*?\n\}}\n", STYLE_TEKST, re.S | re.M) for n in ("verberg", "hernoem")}
DISCOVER = ("[Desktop Entry]\nName=Discover\nExec=plasma-discover %F\nIcon=plasmadiscover\nType=Application\n"
            "NoDisplay=false\nCategories=Qt;KDE;System;\n\n[Desktop Action Updates]\nName=Updates\n"
            "Exec=plasma-discover --mode update\n")
FILELIGHT = "[Desktop Entry]\nName=Filelight\nExec=filelight %u\nIcon=filelight\nType=Application\n"
ANDER = "[Desktop Entry]\nName=Gwenview\nExec=gwenview %U\nType=Application\n"


def draai_verberg(apps: dict[str, str], extra: str = "") -> tuple[subprocess.CompletedProcess, dict[str, str]]:
    """verberg/hernoem en de KDE-lus uit style.sh op een eigen map met .desktop-bestanden; geeft de uitkomst en de
    bestanden erna terug."""
    with tempfile.TemporaryDirectory() as d:
        for naam, tekst in apps.items():
            (Path(d) / naam).write_text(tekst, encoding="utf-8", newline="\n")
        code = "set -euo pipefail\n" + "".join(h.group(0) for h in _hulp.values() if h) + _kde_lus + extra
        code = code.replace("/usr/share/applications/", d + "/")
        uit = subprocess.run(["bash", "-c", code], capture_output=True, text=True, timeout=30)
        return uit, {f.name: f.read_text(encoding="utf-8") for f in Path(d).iterdir()}


if all(_hulp.values()) and _kde_lus and shutil.which("bash"):
    _u, _na = draai_verberg({"org.kde.discover.desktop": DISCOVER, "org.kde.filelight.desktop": FILELIGHT,
                             "org.kde.gwenview.desktop": ANDER})
    _disc = _na.get("org.kde.discover.desktop", "").split("\n")
    klopt(_u.returncode == 0 and "NoDisplay=true" in _disc and "NoDisplay=false" not in _disc
          and _na.get("org.kde.filelight.desktop", "").startswith("[Desktop Entry]\nNoDisplay=true\n")
          and _na.get("org.kde.gwenview.desktop") == ANDER,
          f"D5: met Discover in het beeld: Discover en Filelight krijgen NoDisplay=true, de rest blijft ({_u.returncode}, {_u.stderr.strip()[:200]})")
    _u, _na = draai_verberg({"org.kde.gwenview.desktop": ANDER}, 'hernoem bestaat-niet.desktop "Naam" "Name"\n')
    klopt(_u.returncode == 0 and set(_na) == {"org.kde.gwenview.desktop"} and _na["org.kde.gwenview.desktop"] == ANDER,
          f"D5: zonder Discover en Filelight (pakket store, of een andere basis): geen fout, en er komt niets bij ({_u.returncode}, {sorted(_na)})")
else:
    klopt(False, "D5: style.sh heeft de hulpjes verberg en hernoem en de KDE-lus (met Dolphin)")
klopt(re.search(r"^bureaubladmenu /usr/share/plasma/plasmoids/org\.kde\.desktopcontainment/contents/ui \\\n"
                r" +/usr/share/plasma/plasmoids/org\.bugos\.taskbar/contents/ui/BureaubladActies\.qml$", STYLE_TEKST, re.M)
      is not None, "D4: style.sh past de mapweergave van KDE aan (org.kde.desktopcontainment) met BureaubladActies.qml")

# D6 (review 1): het menu op een bestand of map op het bureaublad zonder "Activiteiten >", tags, KDE Connect, de
# kluis en "Openen als beheerder" (kio-admin: Dolphin als beheerder, een KDE-venster). De lus echt draaien met een
# nagemaakte kwriteconfig6 die opschrijft wat hij krijgt. (Nagekeken in Kinoite 44: alle vijf .so-bestanden
# bestaan, en hun metadata heeft geen eigen Id, dus KIO leest kservicemenurc met de bestandsnaam.)
BESTANDMENU_UIT = ["kactivitymanagerd_fileitem_linking_plugin", "tagsfileitemaction", "kdeconnectfileitemaction",
                   "plasmavaultfileitemaction", "kio-admin"]
_lus = re.search(r"^for plugin in (.*?); do\n    kwriteconfig6 (.*?)\ndone\n", STYLE_TEKST, re.S | re.M)
_gekregen: list[list[str]] = []
if _lus:
    with tempfile.TemporaryDirectory() as _d:
        _nep = Path(_d) / "kwriteconfig6"
        _nep.write_text('#!/bin/bash\nprintf "%s|" "$@" >>"$NEP_LOG"; echo >>"$NEP_LOG"\n', encoding="utf-8", newline="\n")
        _nep.chmod(0o755)
        _log = Path(_d) / "log"
        subprocess.run(["bash", "-c", "set -euo pipefail\n" + _lus.group(0)], check=False, capture_output=True,
                       env={**os.environ, "PATH": f"{_d}:{os.environ.get('PATH', '')}", "NEP_LOG": str(_log)})
        if _log.exists():
            _gekregen = [r.rstrip("|").split("|") for r in _log.read_text(encoding="utf-8").splitlines() if r]
klopt(_gekregen == [["--file", "/etc/xdg/kservicemenurc", "--group", "Show", "--key", p, "false"] for p in BESTANDMENU_UIT],
      f"D6: style.sh zet in /etc/xdg/kservicemenurc [Show] precies de vijf KDE-onderdelen van het bestandsmenu uit ({_gekregen})")
klopt(not any(p in STYLE_TEKST for p in ("sharefileitemaction", "compressfileitemaction", "extractfileitemaction",
                                         "wallpaperfileitemaction")),
      "D6: Delen, Inpakken, Uitpakken en 'Als achtergrond instellen' blijven in het bestandsmenu")
# De controle in het gebouwde beeld (tools/test_image.sh) moet dezelfde vijf nakijken, anders gaat er bij een
# wijziging aan één kant iets stil mis.
TEST_IMAGE_TEKST = lees(ROOT / "tools/test_image.sh")
_beeld = re.search(r"for p in ([a-z0-9_ -]+); do \[ -f /usr/lib64/qt6/plugins/kf6/kfileitemaction/\$p\.so \]", TEST_IMAGE_TEKST)
klopt(_beeld is not None and _beeld.group(1).split() == BESTANDMENU_UIT,
      f"D6: tools/test_image.sh kijkt in het beeld dezelfde vijf plug-ins na ({_beeld.group(1).split() if _beeld else None})")

# D7: de Filelight-regel op mappen ("schijfgebruik bekijken") is een los servicemenu-bestand van het pakket filelight
# (rpm -ql filelight in Kinoite 44: /usr/share/kio/servicemenus/filelight.desktop). style.sh haalt het weg; dat mag
# nooit de bouw breken, ook niet als het bestand er niet is. De echte regel uit style.sh draaien, op een eigen map.
_rm = re.search(r"^rm -f /usr/share/kio/servicemenus/filelight\.desktop$", STYLE_TEKST, re.M)
klopt(_rm is not None, "D7: style.sh haalt het Filelight-servicemenu weg (rm -f, het pad uit het pakket filelight)")
if _rm and shutil.which("bash"):
    for _er in (True, False):
        with tempfile.TemporaryDirectory() as _d:
            _menu = Path(_d) / "filelight.desktop"
            _ander = Path(_d) / "installfont.desktop"   # een ander servicemenu van KDE: moet blijven
            _ander.write_text("[Desktop Entry]\n", encoding="utf-8")
            if _er:
                _menu.write_text("[Desktop Entry]\nActions=filelight\n", encoding="utf-8")
            _u = subprocess.run(["bash", "-c", "set -euo pipefail\n"
                                 + _rm.group(0).replace("/usr/share/kio/servicemenus/", _d + "/") + "\n"],
                                capture_output=True, text=True, timeout=30)
            klopt(_u.returncode == 0 and not _menu.exists() and _ander.exists(),
                  f"D7: {'met' if _er else 'zonder'} het Filelight-servicemenu: weg (of er al niet), geen fout, de rest blijft")
klopt("[ ! -e /usr/share/kio/servicemenus/filelight.desktop ]" in TEST_IMAGE_TEKST,
      "D7: tools/test_image.sh kijkt in het beeld na dat het Filelight-servicemenu weg is")
klopt('grep -qx "NoDisplay=true" /usr/share/applications/org.kde.discover.desktop' in TEST_IMAGE_TEKST
      and 'grep -qx "NoDisplay=true" /usr/share/applications/org.kde.filelight.desktop' in TEST_IMAGE_TEKST,
      "D7: tools/test_image.sh kijkt in het beeld na dat Discover en Filelight weg of verborgen zijn")

# D8: niets in de shell (taakbalk, startmenu, snelmenu, klok, bureaubladmenu, indeling, bugos-panel) stuurt je naar
# KDE Discover: de Winkel doet alle apps (pakket store).
_shell = [PANEEL, INDELING] + sorted(PLASMOIDS.rglob("*.qml")) + sorted(PLASMOIDS.rglob("*.js")) + sorted(PLASMOIDS.rglob("*.json"))
_naar_discover = [str(f.relative_to(ROOT)) for f in _shell if "discover" in lees(f).lower()]
klopt(len(_shell) > 5 and not _naar_discover, f"D8: niets in de shell wijst naar Discover ({_naar_discover})")


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


def bureaubladregel_in_qml(regel: str, taal: str) -> dict:
    """E5: de regel die style.sh in KDE's FolderViewLayer.qml zet (C1), echt draaien in de QML van Qt 6, niet alleen
    als losse JavaScript: met BugosBureaubladActies.qml ernaast (zoals de bouw hem neerzet), een item met dezelfde
    id als KDE (folderViewLayerComponent) en een nagemaakt Plasmoid (isContainment, contextualActions). Zo is ook
    nagekeken dat 'for (const a of bugosO.acties)' over een list<QtObject> loopt en dat Qt.createComponent het
    bestand naast de mapweergave vindt."""
    from PySide6.QtCore import QLocale, QUrl
    from PySide6.QtQml import QQmlComponent, QQmlEngine, QQmlExpression
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
        (t / "BugosBureaubladActies.qml").write_text(lees(BRON), encoding="utf-8", newline="\n")
        # Een Plasmoid als bureaublad (isContainment) en een als losse "Mapweergave" op een paneel (geen BugOS-regels).
        (t / "Laag.qml").write_text(
            "import QtQuick\nItem {\n    id: folderViewLayerComponent\n    property var gevonden: []\n"
            "    property int inPaneel: -1\n    function draai(Plasmoid) {\n" + regel + "\n    }\n"
            "    Component.onCompleted: {\n"
            "        var p = { isContainment: true, contextualActions: [\"KDE\"] };\n        draai(p);\n"
            "        gevonden = p.contextualActions.map(function (a) { return typeof a == \"string\" ? a : a.text; });\n"
            "        var q = { isContainment: false, contextualActions: [] };\n        draai(q);\n"
            "        inPaneel = q.contextualActions.length;\n    }\n}\n", encoding="utf-8", newline="\n")
        QLocale.setDefault(QLocale(taal))
        engine = QQmlEngine()
        engine.addImportPath(str(t))
        comp = QQmlComponent(engine, QUrl.fromLocalFile(str(t / "Laag.qml")))
        obj = comp.create()
        if obj is None:
            return {"fout": "; ".join(e.toString() for e in comp.errors())}
        uit = QQmlExpression(engine.rootContext(), obj, "JSON.stringify({g: gevonden, p: inPaneel})").evaluate()
        obj.deleteLater()
        return json.loads(uit[0] if isinstance(uit, tuple) else uit)


_regel = globals().get("ingevoegd", "")
_q = bureaubladregel_in_qml(_regel, "en_US") if _regel else {"fout": "geen ingevoegde regel uit C1"}
klopt(_q.get("g") == ["KDE", "Display settings", "Change background"] and _q.get("p") == 0,
      f"E5: de regel in KDE's mapweergave werkt echt in QML: na KDE's eigen regels komen 'Display settings' en "
      f"'Change background', en niets in een losse mapweergave op een paneel ({_q})")

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


# --- G. systeemvakNaUpdate(): de eenmalige stap 6 ----------------------------------------------------------------
# Voor wie al een taakbalk had, en voor een nieuwe gebruiker bij wie Plasma de onderdelen pas na het inloggen
# invult. Wat de functie moet doen: de KDE-onderdelen die het snelmenu vervangt uitzetten (en onthouden), de
# toetsenbordindeling weer laten zien als BugOS die verborg, en verder van hiddenItems afblijven. Wat ze nooit mag:
# een systeemvak slopen (iets kwijtraken, iets verbergen, knownItems of shownItems aanraken, iets uitzetten wat je
# zelf zichtbaar wilde), vastlopen op een rare instelling, of een tweede keer iets anders doen dan de eerste keer.
KL = "org.kde.plasma.keyboardlayout"
_e = QJSEngine()
_e.evaluate(JS)
RUSTIG_JS, VROEGER_JS = json.loads(_e.evaluate("JSON.stringify([RUSTIG, RUSTIG_VROEGER])").toString())
klopt(sorted(VROEGER_JS) == sorted(_vroeger) and set(VROEGER_JS) - set(RUSTIG_JS) == {KL} and KL not in RUSTIG_JS,
      "G0: RUSTIG_VROEGER is de lijst van de vorige BugOS (13, met de toetsenbordindeling), RUSTIG dezelfde zonder")
# knownItems van een echt systeemvak: alles wat Plasma kent, ook wat uit staat (Kinoite 44: 22 onderdelen).
VM_KNOWN = VM_EXTRA + ["org.kde.plasma.addons.katesessions", "org.kde.plasma.diskquota", "org.kde.plasma.trash"]
NA_UPDATE = wijzig("systeemvakNaUpdate();")


def na_update(cfg: dict, code: str = NA_UPDATE, vooraf: str = "") -> dict:
    """Stap 6 zoals bugos-panel hem naar Plasma stuurt (slot eraf, try, finally slot erop), op een taakbalk die op
    slot staat, met één systeemvak met deze instellingen. Geeft de instellingen erna, alles wat geprint is, hoe vaak
    het systeemvak herladen werd, het slot en een eventuele fout."""
    r = draai_js("__AppInterface.locked = true; var v = vak(paneel);" + code,
                 "{cfg: v.cfg, herladen: v.herladen, slot: __AppInterface.locked}",
                 cfgs={"org.kde.plasma.systemtray": cfg}, vooraf=vooraf)
    u = r["u"] or {}
    return {"cfg": u.get("cfg") or {}, "herladen": u.get("herladen"), "slot": u.get("slot"), "gedrukt": r["gedrukt"],
            "fout": r["fout"]}


# G1: de gewone bestaande gebruiker (de vorige BugOS verborg 13 onderdelen, met de toetsenbordindeling).
_wie = {"hiddenItems": list(_vroeger), "bugosHidden": list(_vroeger), "extraItems": VM_EXTRA + ["mijn.app"],
        "knownItems": VM_KNOWN + ["mijn.app"], "shownItems": ["mijn.app"]}
r = na_update(_wie)
c = r["cfg"]
klopt(r["fout"] is None and r["gedrukt"] == ["klaar"] and r["slot"] is True and r["herladen"] == 1,
      f"G1: bestaande gebruiker: één woord 'klaar', één keer herladen, het slot weer erop ({r['gedrukt']}, {r['fout']})")
klopt(c.get("hiddenItems") == [x for x in _vroeger if x != KL],
      f"G1: de toetsenbordindeling is weer te zien (BugOS verborg hem); de rest blijft verborgen, in dezelfde volgorde ({c.get('hiddenItems')})")
klopt(sorted(c.get("bugosHidden", [])) == sorted(RUSTIG_JS),
      "G1: bugosHidden onthoudt wat BugOS nog verbergt (zonder de toetsenbordindeling), voor 'snelmenu uit'")
klopt(sorted(c.get("extraItems", [])) == sorted(BLIJFT) and sorted(c.get("bugosOff", [])) == sorted(UIT),
      f"G1: de KDE-onderdelen die het snelmenu vervangt staan uit en zijn onthouden; de rest (ook je eigen app) blijft aan ({c.get('extraItems')})")
klopt(c.get("knownItems") == _wie["knownItems"] and c.get("shownItems") == ["mijn.app"],
      "G1: knownItems en shownItems blijven precies zoals ze waren (anders zet Plasma onderdelen zelf weer aan)")

# G2: wie het klembord en de printers zelf weer zichtbaar maakte, houdt ze zichtbaar.
_zelf = [x for x in _vroeger if x not in ("org.kde.plasma.clipboard", "org.kde.plasma.printmanager")]
_cfg2 = {"hiddenItems": _zelf, "bugosHidden": list(_vroeger), "extraItems": list(VM_EXTRA)}
r = na_update(_cfg2)
klopt(r["gedrukt"] == ["klaar"] and r["cfg"].get("hiddenItems") == [x for x in _zelf if x != KL],
      f"G2: wat je zelf weer zichtbaar maakte (klembord, printers), verbergt de update niet opnieuw ({r['cfg'].get('hiddenItems')})")
r = na_update(_cfg2, wijzig("systeemvak(true);"))
klopt("org.kde.plasma.clipboard" in r["cfg"].get("hiddenItems", []),
      "G2: (ter vergelijking: systeemvak(true) verbergt het klembord wél weer; daarom is stap 6 systeemvakNaUpdate)")

# G3: wat je zelf verborg, blijft verborgen.
r = na_update({"hiddenItems": _vroeger + ["mijn.app"], "bugosHidden": list(_vroeger), "extraItems": list(VM_EXTRA)})
klopt(r["cfg"].get("hiddenItems") == [x for x in _vroeger if x != KL] + ["mijn.app"],
      f"G3: je eigen verborgen app blijft verborgen ({r['cfg'].get('hiddenItems')})")

# G4: een oudere BugOS, van voor bugosHidden: de hele lijst staat verborgen, maar er is niets onthouden.
r = na_update({"hiddenItems": ["mijn.app"] + _vroeger, "extraItems": list(VM_EXTRA)})
c = r["cfg"]
klopt(r["gedrukt"] == ["klaar"] and c.get("hiddenItems") == ["mijn.app"] + [x for x in _vroeger if x != KL]
      and sorted(c.get("bugosHidden", [])) == sorted(RUSTIG_JS) and sorted(c.get("bugosOff", [])) == sorted(UIT),
      f"G4: oudere BugOS zonder bugosHidden: de toetsenbordindeling weer te zien, de lijst van BugOS onthouden, UIT uit ({c})")

# G5: nooit iets onthouden en wat verborgen staat is niet de lijst van BugOS: dan is het van jou en blijft het.
r = na_update({"hiddenItems": ["mijn.app", KL], "extraItems": list(VM_EXTRA)})
c = r["cfg"]
klopt(r["gedrukt"] == ["klaar"] and c.get("hiddenItems") == ["mijn.app", KL] and "bugosHidden" not in c
      and sorted(c.get("bugosOff", [])) == sorted(UIT),
      f"G5: jouw eigen verborgen lijst (ook de toetsenbordindeling) blijft, er wordt niets 'van BugOS' verzonnen ({c})")

# G6: je koos zelf 'bugos-panel systeemvak alles' (BugOS verbergt niets): dan blijven de KDE-onderdelen aan.
for _leeg in ([""], "", []):
    _cfg6 = {"hiddenItems": ["mijn.app"], "bugosHidden": _leeg, "extraItems": list(VM_EXTRA), "knownItems": VM_KNOWN}
    r = na_update(_cfg6)
    klopt(r["gedrukt"] == ["klaar"] and r["cfg"] == _cfg6 and r["herladen"] == 0 and r["slot"] is True,
          f"G6: 'systeemvak alles' gekozen (bugosHidden {_leeg!r}): niets verandert, de KDE-onderdelen blijven aan ({r['cfg'] if r['cfg'] != _cfg6 else 'gelijk'})")

# G7: Plasma heeft de onderdelen nog niet ingevuld: niets aanraken (ook geen bugosOff), 'later'.
for _extra in ("weg", [], [""], "", None):
    _cfg7 = {"hiddenItems": list(_vroeger), "bugosHidden": list(_vroeger), "knownItems": VM_KNOWN}
    if _extra != "weg":
        _cfg7["extraItems"] = _extra
    r = na_update(_cfg7)
    klopt(r["gedrukt"] == ["later"] and r["cfg"] == _cfg7 and r["herladen"] == 0 and r["slot"] is True and r["fout"] is None,
          f"G7: extraItems {_extra!r}: 'later', en er is niets veranderd (de volgende keer begint schoon) ({r})")

# G8: twee keer draaien geeft precies hetzelfde als één keer (en zegt allebei 'klaar').
for _naam, _cfg in (("G1", _wie), ("G2", _cfg2), ("G4", {"hiddenItems": ["mijn.app"] + _vroeger, "extraItems": list(VM_EXTRA)})):
    r1, r2 = na_update(_cfg), na_update(_cfg, NA_UPDATE * 2)
    klopt(r2["cfg"] == r1["cfg"] and r2["gedrukt"] == ["klaar", "klaar"],
          f"G8: {_naam} twee keer: hetzelfde als één keer")

# G9: een taakbalk zonder systeemvak: niets te doen, dus 'klaar' (anders bij elk inloggen opnieuw).
r = draai_js(NA_UPDATE, "soorten(paneel)", begin=["org.bugos.startmenu", "org.kde.plasma.icontasks", "org.bugos.quickmenu"])
klopt(r["gedrukt"] == ["klaar"] and r["fout"] is None, f"G9: geen systeemvak: 'klaar' en geen fout ({r['gedrukt']}, {r['fout']})")

# G10: twee taakbalken met elk een systeemvak; één is nog niet ingevuld. Die wacht ('later'), de andere is al bij.
_klaar_vak = {"hiddenItems": list(_vroeger), "bugosHidden": list(_vroeger), "extraItems": list(VM_EXTRA)}
_twee = ("var paneel2 = maakContainment(" + json.dumps(TAAKBALK) + ", " + json.dumps({"org.kde.plasma.systemtray": _klaar_vak})
         + "); function panels() { return [paneel, paneel2]; }")
r = draai_js(NA_UPDATE + " var a = JSON.parse(JSON.stringify([vak(paneel).cfg, vak(paneel2).cfg]));"
             " vak(paneel).cfg.extraItems = " + json.dumps(VM_EXTRA) + ";" + NA_UPDATE
             + " var b = JSON.parse(JSON.stringify([vak(paneel).cfg, vak(paneel2).cfg]));",
             "{a: a, b: b}", cfgs={"org.kde.plasma.systemtray": {"hiddenItems": list(_vroeger), "bugosHidden": list(_vroeger)}},
             vooraf=_twee)
u = r["u"] or {}
a, b = u.get("a") or [{}, {}], u.get("b") or [{}, {}]
klopt(r["gedrukt"] == ["later", "klaar"] and "bugosOff" not in a[0] and sorted(a[1].get("bugosOff", [])) == sorted(UIT)
      and sorted(b[0].get("bugosOff", [])) == sorted(UIT) and b[1] == a[1],
      f"G10: twee systeemvakken: wat al kan gebeurt meteen, het andere bij de volgende keer; het eerste verandert dan niet meer ({r['gedrukt']})")

# G11: rare instellingen (lijsten als tekst, dubbel, leeg, null, een getal, een los object): geen fout, iets zinnigs.
r = na_update({"hiddenItems": "org.kde.plasma.volume,,org.kde.plasma.keyboardlayout,org.kde.plasma.volume",
               "bugosHidden": "org.kde.plasma.keyboardlayout,org.kde.plasma.volume",
               "extraItems": ",".join(VM_EXTRA) + ",", "bugosOff": None, "knownItems": VM_KNOWN})
c = r["cfg"]
klopt(r["fout"] is None and r["gedrukt"] == ["klaar"] and c.get("hiddenItems") == ["org.kde.plasma.volume"]
      and c.get("bugosHidden") == ["org.kde.plasma.volume"]
      and sorted(c.get("extraItems", [])) == sorted(x for x in VM_EXTRA if x not in UIT)
      and sorted(c.get("bugosOff", [])) == sorted(UIT) and c.get("knownItems") == VM_KNOWN,
      f"G11: lijsten als tekst met dubbele en lege namen, bugosOff null: gewoon goed bijgewerkt ({c})")
for _raar in ({"hiddenItems": 5, "extraItems": list(VM_EXTRA)},
              {"hiddenItems": list(_vroeger), "bugosHidden": {"x": 1}, "extraItems": list(VM_EXTRA)},
              {"hiddenItems": list(_vroeger), "bugosHidden": list(_vroeger), "extraItems": 7},
              {"hiddenItems": None, "bugosHidden": None, "extraItems": None, "bugosOff": 3}):
    r = na_update(_raar)
    klopt(r["fout"] is None and len(r["gedrukt"]) == 1 and r["gedrukt"][0] in ("klaar", "later") and r["slot"] is True,
          f"G11: een rare instelling ({json.dumps(_raar)[:90]}): geen fout, één antwoord, het slot erop ({r['gedrukt']}, {r['fout']})")

# G12: het systeemvak kan niet stuk. Alle combinaties van hiddenItems, bugosHidden, extraItems en bugosOff (ook
# ontbrekend, leeg, als tekst, null) in één keer. Per combinatie: één keer, nog een keer, en daarna 'snelmenu uit'.
WEG = object()   # de sleutel ontbreekt helemaal


def norm(x) -> list[str]:
    """Zoals lijst() in bugos-panel: tekst splitsen op komma's, lege en dubbele namen weg; geen lijst = leeg."""
    if isinstance(x, str):
        x = x.split(",")
    if not isinstance(x, list):
        return []
    uit: list[str] = []
    for y in x:
        if y is not None and str(y) and str(y) not in uit:
            uit.append(str(y))
    return uit


_keuzes = {
    # Ook een systeemvak waarin je zelf het klembord (geen UIT-onderdeel) of het geluid (wel een UIT-onderdeel) weer
    # liet zien ("Shown when relevant").
    "hiddenItems": [WEG, [], list(_vroeger), _vroeger + ["mijn.app"], [x for x in _vroeger if x != "org.kde.plasma.clipboard"],
                    [x for x in _vroeger if x != "org.kde.plasma.volume"], ["mijn.app", KL], ",".join(_vroeger), None],
    "bugosHidden": [WEG, [""], list(_vroeger), [KL, "org.kde.plasma.volume"], KL + ",org.kde.plasma.volume", None],
    "extraItems": [WEG, [], VM_EXTRA + ["mijn.app"], ",".join(VM_EXTRA), [x for x in VM_EXTRA if x not in UIT],
                   VM_EXTRA + [""] + VM_EXTRA[:3]],
    "bugosOff": [WEG, list(UIT), [""]],
    # "Always shown" in KDE: alleen je eigen app, ook de batterij, of batterij en netwerk als tekst.
    "shownItems": [["mijn.app"], ["mijn.app", BAT], BAT + "," + NET],
}
_scenarios = [{}]
for _sleutel, _waarden in _keuzes.items():
    _scenarios = [{**s, _sleutel: w} if w is not WEG else dict(s) for s in _scenarios for w in _waarden]
for s in _scenarios:
    s["knownItems"] = VM_KNOWN + ["mijn.app"]


def zelf_zichtbaar(voor: dict) -> set[str]:
    """Wat je zelf zichtbaar wilde, zoals systeemvakNaUpdate() het hoort te zien: wat je "Always shown" gaf
    (shownItems), en wat BugOS verborg (bugosHidden; nooit bewaard: de hele oude lijst als die er nog staat) en nu niet
    meer verborgen staat."""
    h0 = norm(voor.get("hiddenItems"))
    if "bugosHidden" in voor:
        van_ons = norm(voor["bugosHidden"])
    else:
        van_ons = VROEGER_JS if all(x in h0 for x in RUSTIG_JS) else []
    return set(norm(voor.get("shownItems"))) | (set(van_ons) - set(h0))


_HARNAS = ("var uitslagen = [];"
           "for (var s = 0; s < SCENARIOS.length; s++) {"
           " paneel = maakContainment(" + json.dumps(TAAKBALK) + ", {\"org.kde.plasma.systemtray\": SCENARIOS[s]});"
           " __AppInterface.locked = true; var v = vak(paneel); var r = {fout: null};"
           " gedrukt = []; try { " + NA_UPDATE + " } catch (x) { r.fout = String(x); }"
           " r.na1 = JSON.parse(JSON.stringify(v.cfg)); r.gedrukt1 = gedrukt.slice(); r.slot1 = __AppInterface.locked;"
           " gedrukt = []; try { " + NA_UPDATE + " } catch (x) { r.fout = String(x); }"
           " r.na2 = JSON.parse(JSON.stringify(v.cfg)); r.gedrukt2 = gedrukt.slice();"
           " gedrukt = []; try { " + wijzig("systeemvak(false);") + " } catch (x) { r.fout = String(x); }"
           " r.uit = JSON.parse(JSON.stringify(v.cfg)); uitslagen.push(r);"
           "}")
r = draai_js(_HARNAS, "uitslagen", vooraf="var SCENARIOS = " + json.dumps(_scenarios) + ";")
_uitslagen = r["u"] or []
klopt(len(_uitslagen) == len(_scenarios) == 2916 and r["fout"] is None,
      f"G12: {len(_uitslagen)} van de {len(_scenarios)} combinaties gedraaid ({r['fout']})")
_mis: dict[str, list[int]] = {}


def mis(regel: str, i: int, goed: bool) -> None:
    if not goed:
        _mis.setdefault(regel, []).append(i)


for i, (voor, u) in enumerate(zip(_scenarios, _uitslagen)):
    na1, na2, uit_ = u["na1"], u["na2"], u["uit"]
    alles = "bugosHidden" in voor and norm(voor["bugosHidden"]) == []
    wacht = not alles and norm(voor.get("extraItems")) == []
    mis("geen fout, één woord, het slot erop", i, u["fout"] is None and u["slot1"] is True
        and u["gedrukt1"] in (["klaar"], ["later"]) and u["gedrukt2"] == u["gedrukt1"])
    mis("'later' precies als Plasma de onderdelen nog niet had", i, (u["gedrukt1"] == ["later"]) == wacht)
    mis("'later' en 'systeemvak alles': niets veranderd", i, na1 == voor if (wacht or alles) else True)
    mis("knownItems en shownItems blijven", i, all(na1.get(k) == voor.get(k) for k in ("knownItems", "shownItems")))
    _h0, _h1 = set(norm(voor.get("hiddenItems"))), set(norm(na1.get("hiddenItems")))
    mis("niets nieuws verborgen; alleen de toetsenbordindeling mag zichtbaar worden", i, _h1 <= _h0 and _h0 - _h1 <= {KL})
    _e0, _e1 = set(norm(voor.get("extraItems"))), set(norm(na1.get("extraItems")))
    _zelf = zelf_zichtbaar(voor) & set(UIT)
    _uit1 = set(norm(na1.get("bugosOff")))
    mis("alleen UIT-onderdelen gaan uit", i, _e1 <= _e0 and _e0 - _e1 <= set(UIT))
    mis("wat uitging staat in bugosOff", i, (_e0 - _e1) <= _uit1)
    # Review: de vorige BugOS verborg alleen, dus wat je "Always shown" gaf of weer liet zien, zag je nog.
    mis("wat je zelf zichtbaar wilde, blijft aan", i, wacht or alles or (_e0 & _zelf) <= _e1)
    mis("met het snelmenu aan staat geen ander UIT-onderdeel meer aan", i, wacht or alles or (_e1 & set(UIT)) <= _zelf)
    mis("wat aan staat, staat niet in bugosOff", i, wacht or alles or not (_e1 & _uit1))
    # Wat BugOS eerder uitzette en nog uit staat, mag het niet vergeten: anders zet "snelmenu uit" het nooit meer aan.
    _uit0 = set(norm(voor.get("bugosOff")))
    mis("wat uit staat en BugOS onthield, blijft onthouden", i, (_uit0 - _e1) <= _uit1)
    mis("twee keer = één keer", i, na2 == na1)
    mis("'snelmenu uit' daarna: alles is terug", i, (_e0 | _uit0) <= set(norm(uit_.get("extraItems"))))
for _regel in ("geen fout, één woord, het slot erop", "'later' precies als Plasma de onderdelen nog niet had",
               "'later' en 'systeemvak alles': niets veranderd", "knownItems en shownItems blijven",
               "niets nieuws verborgen; alleen de toetsenbordindeling mag zichtbaar worden", "alleen UIT-onderdelen gaan uit",
               "wat uitging staat in bugosOff", "wat je zelf zichtbaar wilde, blijft aan",
               "met het snelmenu aan staat geen ander UIT-onderdeel meer aan", "wat aan staat, staat niet in bugosOff",
               "wat uit staat en BugOS onthield, blijft onthouden", "twee keer = één keer",
               "'snelmenu uit' daarna: alles is terug"):
    _fout_bij = _mis.get(_regel, [])
    klopt(bool(_uitslagen) and not _fout_bij,
          f"G12: {_regel} (alle {len(_uitslagen)} combinaties)"
          + (f" - mis bij {len(_fout_bij)}, bijv. {json.dumps(_scenarios[_fout_bij[0]])[:300]}" if _fout_bij else ""))

# G13: een nieuwe gebruiker bij wie Plasma de onderdelen pas na het eerste inloggen invult. De indeling liet alleen
# hiddenItems achter; stap 2 (systeemvak(true)) en stap 6 bij het eerste inloggen, Plasma vult de lijst, stap 6
# bij het volgende inloggen.
r = draai_js(wijzig("systeemvak(true);") + " var s1 = JSON.parse(JSON.stringify(vak(paneel).cfg));" + NA_UPDATE
             + " var s2 = JSON.parse(JSON.stringify(vak(paneel).cfg)); vak(paneel).cfg.extraItems = " + json.dumps(VM_EXTRA)
             + ";" + NA_UPDATE, "{s1: s1, s2: s2, s3: vak(paneel).cfg}", begin=TAAKBALK_SNEL,
             cfgs={"org.kde.plasma.systemtray": {"hiddenItems": list(RUSTIG_JS)}})
u = r["u"] or {}
klopt(r["gedrukt"] == ["1", "later", "klaar"] and u.get("s2") == u.get("s1")
      and sorted((u.get("s3") or {}).get("bugosOff", [])) == sorted(UIT)
      and sorted((u.get("s3") or {}).get("extraItems", [])) == sorted(x for x in VM_EXTRA if x not in UIT)
      and (u.get("s3") or {}).get("hiddenItems") == RUSTIG_JS,
      f"G13: nieuwe gebruiker, lijst pas later ingevuld: eerst 'later' (niets veranderd), de volgende keer echt uit ({r['gedrukt']})")

# G14 (review): wie op de vorige BugOS zelf de batterij en het netwerk "Always shown" gaf (shownItems, en dus niet
# meer verborgen), houdt ze na de update aan. De vorige BugOS verborg alleen, dus die pictogrammen zag je nog;
# uitzetten zou ze zonder te vragen helemaal weghalen, en op slot is er geen "Configure System Tray..." om ze terug
# te zetten. Daarna snelmenu uit (alles terug) en weer aan (Instellingen): "Always shown" blijft ook dan aan.
_cfg14 = {"hiddenItems": [x for x in _vroeger if x not in (BAT, NET)], "bugosHidden": list(_vroeger),
          "extraItems": list(VM_EXTRA), "shownItems": [BAT, NET], "knownItems": VM_KNOWN}
_snel_uit = wijzig('weg("org.bugos.quickmenu"); systeemvak(false);')
_snel_aan = wijzig('vervang("", "org.bugos.quickmenu", "org.kde.plasma.systemtray");') + wijzig("systeemvak(true);")
r = draai_js("__AppInterface.locked = true; var v = vak(paneel);" + NA_UPDATE + " var a = JSON.parse(JSON.stringify(v.cfg));"
             + NA_UPDATE + " var a2 = JSON.parse(JSON.stringify(v.cfg));" + _snel_uit
             + " var b = JSON.parse(JSON.stringify(v.cfg)); var sb = soorten(paneel);" + _snel_aan,
             "{a: a, a2: a2, b: b, sb: sb, c: v.cfg, sc: soorten(paneel), slot: __AppInterface.locked}",
             begin=TAAKBALK_SNEL, cfgs={"org.kde.plasma.systemtray": _cfg14})
u = r["u"] or {}
a, b, c = u.get("a") or {}, u.get("b") or {}, u.get("c") or {}
_rest = sorted(x for x in UIT if x not in (BAT, NET))
klopt(r["fout"] is None and r["gedrukt"][:2] == ["klaar", "klaar"] and {BAT, NET} <= set(a.get("extraItems", []))
      and sorted(a.get("bugosOff", [])) == _rest and a.get("shownItems") == [BAT, NET] and a.get("knownItems") == VM_KNOWN
      and a.get("hiddenItems") == [x for x in _vroeger if x not in (BAT, NET, KL)] and u.get("a2") == a,
      f"G14: 'Always shown' (batterij, netwerk) blijft na de update aan en staat niet in bugosOff; de rest van UIT gaat uit; "
      f"twee keer = één keer ({a.get('extraItems')}, {a.get('bugosOff')}, {r['fout']})")
klopt(sorted(b.get("extraItems", [])) == sorted(VM_EXTRA) and b.get("bugosOff") == [""] and "org.bugos.quickmenu" not in u.get("sb", []),
      f"G14: daarna snelmenu uit: alle KDE-onderdelen zijn terug ({b.get('extraItems')})")
klopt({BAT, NET} <= set(c.get("extraItems", [])) and sorted(c.get("bugosOff", [])) == _rest
      and "org.bugos.quickmenu" in u.get("sc", []) and u.get("slot") is True,
      f"G14: en snelmenu weer aan: 'Always shown' blijft aan, de rest van UIT gaat weer uit ({c.get('bugosOff')})")

# G15 (review): wie de batterij op de vorige BugOS weer liet zien ("Shown when relevant": niet meer verborgen, niet in
# shownItems), houdt hem na de update ook aan. Wat BugOS nooit verborg (de kluis staat niet in RUSTIG), liet je niet
# zelf zien: dat gaat gewoon uit. Zet je later zelf het snelmenu weer aan (Instellingen), dan maakt dat het systeemvak
# rustig zoals bij een nieuwe gebruiker (net als het klembord in G2): de batterij verborgen en uit. Alleen "Always
# shown" blijft dan (G14).
_cfg15 = {"hiddenItems": [x for x in _vroeger if x != BAT], "bugosHidden": list(_vroeger), "extraItems": list(VM_EXTRA)}
r1, r2 = na_update(_cfg15), na_update(_cfg15, NA_UPDATE * 2)
c = r1["cfg"]
klopt(r1["gedrukt"] == ["klaar"] and BAT in c.get("extraItems", []) and BAT not in c.get("bugosOff", [])
      and "org.kde.plasma.vault" not in c.get("extraItems", [])
      and sorted(c.get("bugosOff", [])) == sorted(x for x in UIT if x != BAT) and r2["cfg"] == c,
      f"G15: wat BugOS verborg en jij weer liet zien (batterij) blijft na de update aan; de kluis gaat uit; twee keer = "
      f"één keer ({c.get('bugosOff')})")
r = draai_js(NA_UPDATE + _snel_uit + _snel_aan, "vak(paneel).cfg", begin=TAAKBALK_SNEL,
             cfgs={"org.kde.plasma.systemtray": _cfg15})
c = r["u"] or {}
klopt(BAT in c.get("hiddenItems", []) and BAT not in c.get("extraItems", []) and BAT in c.get("bugosOff", []),
      f"G15: snelmenu later zelf uit en weer aan: dan is de batterij weer verborgen en uit, zoals bij een nieuwe gebruiker ({c})")


print(f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
