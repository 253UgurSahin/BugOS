"""BugOS Instellingen: makkelijker zien (letters, aanwijzer, vergrootglas, kaccess) en muis en touchpad
(KWin via busctl).

Hoort bij bugos_config (importeer het via daar). draai, VOORBEELD, _VB en de KDE-hulpjes komen via
bugos_config (_c.draai), zodat een test die bi.draai of bi.VOORBEELD vervangt dat ook hier ziet.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass

import bugos_config as _c


# ======================================================== makkelijker zien ===

GEWONE_LETTERS = 10
GROTE_LETTERS = 12


def letter(familie: str, punten: int, dikte: int = 400) -> str:
    """Een lettertype zoals KDE het opschrijft in kdeglobals."""
    return f"{familie},{punten},-1,5,{dikte},0,0,0,0,0,0,0,0,0,0,1"


def lees_letter(tekst: str) -> tuple[str, int]:
    """'Inter,10,-1,5,400,...' -> ('Inter', 10)."""
    delen = tekst.split(",")
    try:
        return (delen[0].strip() or "Inter"), int(float(delen[1]))
    except (IndexError, ValueError):
        return "Inter", GEWONE_LETTERS


def grote_tekst() -> bool:
    if _c.VOORBEELD:
        return _c._VB["grote_tekst"]
    return lees_letter(_c.kde_lees("kdeglobals", "General", "font", ""))[1] >= GROTE_LETTERS


def zet_grote_tekst(aan: bool) -> None:
    """Grotere letters overal: menu's, knoppen, vensters. De lettersoort blijft wat hij was."""
    if _c.VOORBEELD:
        _c._VB["grote_tekst"] = aan
        return
    familie, _p = lees_letter(_c.kde_lees("kdeglobals", "General", "font", ""))
    punten = GROTE_LETTERS if aan else GEWONE_LETTERS
    for sleutel in ("font", "menuFont", "toolBarFont"):
        _c.kde_schrijf("kdeglobals", "General", sleutel, letter(familie, punten))
    _c.kde_schrijf("kdeglobals", "General", "smallestReadableFont", letter(familie, punten - 2))
    _c.kde_schrijf("kdeglobals", "WM", "activeFont", letter(familie, punten, 600))
    _c.draai("gdbus", "emit", "--session", "--object-path", "/KDEPlatformTheme", "--signal",
          "org.kde.KDEPlatformTheme.refreshFonts", timeout=5)
    _c.kwin_herlees()


GEWONE_AANWIJZER = 24
GROTE_AANWIJZER = 48


def grote_aanwijzer() -> bool:
    if _c.VOORBEELD:
        return _c._VB["grote_aanwijzer"]
    try:
        return int(_c.kde_lees("kcminputrc", "Mouse", "cursorSize", str(GEWONE_AANWIJZER))) >= GROTE_AANWIJZER
    except ValueError:
        return False


def zet_grote_aanwijzer(aan: bool) -> None:
    if _c.VOORBEELD:
        _c._VB["grote_aanwijzer"] = aan
        return
    # Altijd zelf schrijven: plasma-apply-cursortheme doet niets (en zegt "gelukt") als het thema al het
    # huidige is, en kijkt in Plasma 6.8 niet meer naar --size (U065). Daarna het signaal dat KDE's eigen
    # instellingenscherm ook stuurt (CursorChanged = 5), zodat KWin en de open programma's het meteen zien.
    _c.kde_schrijf("kcminputrc", "Mouse", "cursorSize", str(GROTE_AANWIJZER if aan else GEWONE_AANWIJZER))
    _c.draai("gdbus", "emit", "--session", "--object-path", "/KGlobalSettings", "--signal",
             "org.kde.KGlobalSettings.notifyChange", "5", "0", timeout=5)
    _c.kwin_herlees()


def schud_aanwijzer() -> bool:
    """Schud je de muis, dan wordt de aanwijzer even groot zodat je hem terugvindt."""
    if _c.VOORBEELD:
        return _c._VB["schud"]
    return _c.kde_lees("kwinrc", "Plugins", "shakecursorEnabled", "true") == "true"


def zet_schud_aanwijzer(aan: bool) -> None:
    if _c.VOORBEELD:
        _c._VB["schud"] = aan
        return
    _c.kde_schrijf("kwinrc", "Plugins", "shakecursorEnabled", "true" if aan else "false")
    _c.kwin_herlees()


def vergrootglas(stap: int) -> bool:
    """stap +1 = inzoomen, -1 = uitzoomen, 0 = gewone grootte (het vergrootglas van KWin)."""
    if not _c.VOORBEELD and _c.kde_lees("kwinrc", "Plugins", "zoomEnabled", "true") != "true":
        _c.kde_schrijf("kwinrc", "Plugins", "zoomEnabled", "true")
        _c.kwin_herlees()
    return _c.kwin_sneltoets("view_zoom_in" if stap > 0 else "view_zoom_out" if stap < 0 else "view_actual_size")


TOETSHULP = {"plaktoetsen": ("Keyboard", "StickyKeys"), "langzame_toetsen": ("Keyboard", "SlowKeys"),
             "schermlezer": ("ScreenReader", "Enabled")}


# Sinds Plasma 6.8 start de kded-module "screenreader" Orca (als orca.service), niet kaccess meer; die kijkt
# dan niet meer naar Enabled in kaccessrc. Dus via D-Bus, zoals KDE's eigen instellingenscherm (U066).
_SCHERMLEZER = ("--session", "--dest", "org.kde.kded6", "--object-path", "/modules/screenreader", "--method")


def _schermlezer_dbus(*methode: str) -> tuple[int, str]:
    return _c.draai("gdbus", "call", *_SCHERMLEZER, *methode, timeout=10)


def toetshulp(naam: str) -> bool:
    if _c.VOORBEELD:
        return _c._VB[naam]
    if naam == "schermlezer":
        code, uit = _schermlezer_dbus("org.kde.screenreader.enabled")
        if code == 0 and uit.strip():
            return "true" in uit
    groep, sleutel = TOETSHULP[naam]
    return _c.kde_lees("kaccessrc", groep, sleutel, "false") == "true"


def zet_toetshulp(naam: str, aan: bool) -> None:
    """Plaktoetsen, langzame toetsen en de schermlezer: kaccess van KDE regelt het verder."""
    if _c.VOORBEELD:
        _c._VB[naam] = aan
        return
    if naam == "schermlezer" and _schermlezer_dbus("org.kde.screenreader.setEnabled", "true" if aan else "false")[0] == 0:
        return
    groep, sleutel = TOETSHULP[naam]
    _c.kde_schrijf("kaccessrc", groep, sleutel, "true" if aan else "false")
    if shutil.which("kaccess"):
        try:
            subprocess.Popen(["kaccess"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        except OSError:
            pass


def kan_schermlezer() -> bool:
    return _c.VOORBEELD or shutil.which("orca") is not None


# ======================================================== muis en touchpad ===

@dataclass
class Aanwijzer:
    """Een muis of touchpad, zoals KWin hem kent."""
    sysnaam: str
    naam: str
    touchpad: bool
    aan: bool
    linkshandig: bool
    natuurlijk: bool    # scrollen 'zoals op een telefoon'
    snelheid: int       # 0-100
    tikken: bool        # tikken om te klikken (touchpad)
    kan: set[str]       # welke dingen dit apparaat kan: aan, linkshandig, natuurlijk, snelheid, tikken


def lees_busctl(uitvoer: str) -> list:
    """Uit: busctl ... --json=short (één JSON per regel) -> de waarden."""
    waarden = []
    for regel in uitvoer.splitlines():
        regel = regel.strip()
        if not regel.startswith("{"):
            continue
        try:
            d = json.loads(regel)
        except ValueError:
            continue
        waarden.append(d.get("data"))
    return waarden


def _busctl(*args: str) -> list:
    return lees_busctl(_c.draai("busctl", "--user", *args, "--json=short", timeout=5)[1])


def lees_aanwijzer(sysnaam: str, eigenschappen: dict) -> Aanwijzer | None:
    """Uit: de eigenschappen (GetAll) van org.kde.KWin.InputDevice."""
    def w(naam: str, standaard=None):
        v = eigenschappen.get(naam)
        if isinstance(v, dict) and "data" in v:   # busctl schrijft een variant als {"type": "b", "data": true}
            v = v["data"]
        return standaard if v is None else v
    if not w("pointer", False):
        return None
    kan = {naam for naam, sleutel in (("aan", "supportsDisableEvents"), ("linkshandig", "supportsLeftHanded"),
                                      ("natuurlijk", "supportsNaturalScroll"), ("snelheid", "supportsPointerAcceleration"),
                                      ) if w(sleutel, False)}
    # KWin heeft geen 'supportsTapToClick': tikken kan als het touchpad vingers telt (tapFingerCount > 0) (U153).
    try:
        if int(w("tapFingerCount", 0) or 0) > 0:
            kan.add("tikken")
    except (TypeError, ValueError):
        pass
    versnelling = w("pointerAcceleration", 0.0) or 0.0
    return Aanwijzer(sysnaam, str(w("name", sysnaam)), bool(w("touchpad", False)), bool(w("enabled", True)),
                     bool(w("leftHanded", False)), bool(w("naturalScroll", False)),
                     max(0, min(100, round((float(versnelling) + 1) * 50))), bool(w("tapToClick", False)), kan)


def aanwijzers() -> list[Aanwijzer]:
    if _c.VOORBEELD:
        if _c._VB["aanwijzers"] is None:
            _c._VB["aanwijzers"] = [
                Aanwijzer("event5", "Muis van Logitech", False, True, False, False, 50, False,
                          {"linkshandig", "natuurlijk", "snelheid"}),
                Aanwijzer("event7", "Touchpad", True, True, False, True, 55, True,
                          {"aan", "linkshandig", "natuurlijk", "snelheid", "tikken"})]
        return _c._VB["aanwijzers"]
    namen = _busctl("get-property", "org.kde.KWin", "/org/kde/KWin/InputDevice", "org.kde.KWin.InputDeviceManager",
                    "devicesSysNames")
    lijst = []
    for sysnaam in (namen[0] if namen and isinstance(namen[0], list) else []):
        alles = _busctl("call", "org.kde.KWin", f"/org/kde/KWin/InputDevice/{sysnaam}", "org.freedesktop.DBus.Properties",
                        "GetAll", "s", "org.kde.KWin.InputDevice")
        if alles and isinstance(alles[0], list) and alles[0] and isinstance(alles[0][0], dict):
            a = lees_aanwijzer(sysnaam, alles[0][0])
            if a is not None:
                lijst.append(a)
    return sorted(lijst, key=lambda a: (a.touchpad, a.naam.lower()))


EIGENSCHAP = {"aan": ("enabled", "b"), "linkshandig": ("leftHanded", "b"), "natuurlijk": ("naturalScroll", "b"),
              "snelheid": ("pointerAcceleration", "d"), "tikken": ("tapToClick", "b")}


def zet_aanwijzer(sysnaam: str, wat: str, waarde: bool | int) -> bool:
    """Zet iets om op een muis of touchpad; KWin onthoudt het zelf (in kcminputrc)."""
    if _c.VOORBEELD:
        for a in aanwijzers():
            if a.sysnaam == sysnaam:
                setattr(a, wat, waarde)
        return True
    sleutel, soort = EIGENSCHAP[wat]
    tekst = f"{(int(waarde) / 50) - 1:.2f}" if soort == "d" else ("true" if waarde else "false")
    return _c.draai("busctl", "--user", "set-property", "org.kde.KWin", f"/org/kde/KWin/InputDevice/{sysnaam}",
                 "org.kde.KWin.InputDevice", sleutel, soort, tekst, timeout=5)[0] == 0


def dubbelklik() -> bool:
    """Dubbelklikken om te openen (zoals in Windows); anders opent één klik."""
    if _c.VOORBEELD:
        return _c._VB["dubbelklik"]
    return _c.kde_lees("kdeglobals", "KDE", "SingleClick", "false") != "true"


def zet_dubbelklik(aan: bool) -> None:
    if _c.VOORBEELD:
        _c._VB["dubbelklik"] = aan
        return
    _c.kde_schrijf("kdeglobals", "KDE", "SingleClick", "false" if aan else "true")
