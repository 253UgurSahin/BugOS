"""Taal en programma's starten: het deel van bugos_ui dat geen Qt nodig heeft.

Apps halen dit gewoon uit bugos_ui (from bugos_ui import t, start, draai ...).
"""

from __future__ import annotations

import json
import locale
import os
import shutil
import subprocess
from pathlib import Path


# =================================================================== taal ===

VERTALINGEN = Path("/usr/share/bugos/translations")


def _taal() -> str:
    """Twee-letter taalcode van de gebruiker, bijv. "nl", "en", "de", "tr"."""
    lang = os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or ""
    if not lang:
        lang = locale.getlocale()[0] or ""
    # De taal die je in KDE kiest staat in LANGUAGE (bijv. "nl:en_US"): die gaat voor, net als bij
    # alle andere programma's. Behalve bij taal C: dan wil iemand bewust Engels.
    eerste = next((x for x in os.environ.get("LANGUAGE", "").split(":") if x), "")
    if eerste and lang.split(".")[0] not in ("C", "POSIX"):
        lang = eerste
    code = lang.split(".")[0].split("_")[0].lower()
    return code if code.isalpha() and len(code) in (2, 3) else "en"


def _catalogus(taal: str) -> dict[str, str]:
    """Vertalingen van de community: Engelse tekst -> tekst in deze taal."""
    if taal in ("nl", "en"):
        return {}
    try:
        data = json.loads((VERTALINGEN / f"{taal}.json").read_text(encoding="utf-8"))
        return {k: v for k, v in data.items() if isinstance(v, str) and v}
    except (OSError, ValueError, AttributeError):   # ook een kapot bestand (geen object) laat geen app vallen
        return {}


TAAL = _taal()
_CATALOGUS = _catalogus(TAAL)


def t(nl: str, en: str) -> str:
    """Geef de tekst in de taal van de gebruiker.

    Nederlands en Engels staan in de code zelf. Andere talen komen uit
    /usr/share/bugos/translations/<taal>.json (zie docs/TRANSLATING.md).
    Ontbreekt een vertaling, dan valt BugOS terug op Engels."""
    if TAAL == "nl":
        return nl
    return _CATALOGUS.get(en, en)


# ===================================================== programma's starten ===

def bestaat(programma: str) -> bool:
    return shutil.which(programma) is not None


def eigen_plek(cmd: tuple | list) -> list[str]:
    """Start een programma (met een .desktop-bestand) in zijn eigen systemd-scope, zoals KDE dat doet: dan ziet
    Taakbeheer het als dat programma (niet als deel van wie het startte) en kun je het daar sluiten (U125).
    Zonder systemd voor de gebruiker (of een opdracht zonder .desktop): gewoon zoals het was."""
    naam = os.path.basename(cmd[0]) if cmd else ""
    runtime = os.environ.get("XDG_RUNTIME_DIR", "")
    # Alleen namen die systemd in een eenheid toestaat; anders zou systemd-run weigeren en start er niets (U146).
    if not naam or not runtime or not os.path.exists(os.path.join(runtime, "systemd", "private")) or \
            not shutil.which("systemd-run") or not all(c.isascii() and (c.isalnum() or c in "-_.:") for c in naam):
        return list(cmd)
    mappen = [os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))] + \
        os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")
    if not any(os.path.exists(os.path.join(m, "applications", f"{naam}.desktop")) for m in mappen if m):
        return list(cmd)
    eenheid = "app-" + naam.replace("\\", "\\x5c").replace("-", "\\x2d") + f"-{os.getpid():x}{os.urandom(3).hex()}.scope"
    return ["systemd-run", "--user", "--scope", "--quiet", "--collect", f"--unit={eenheid}", "--", *cmd]


def start(*cmd: str) -> bool:
    """Start een programma los op de achtergrond. Geeft False als het niet kon."""
    try:
        subprocess.Popen(eigen_plek(cmd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except OSError:
        return False


def draai(*cmd: str, timeout: int = 20) -> tuple[int, str]:
    """Draai een programma en wacht op het antwoord. Geeft (code, tekst)."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except (OSError, subprocess.SubprocessError) as e:
        return 127, str(e)


def kde_instelling(module: str) -> None:
    """Open één onderdeel van de (grote) KDE-instellingen."""
    if bestaat("systemsettings"):
        start("systemsettings", module)
    else:
        start("kcmshell6", module)


def zoeksleutel(tekst: str) -> str:
    """Tekst om in te zoeken: kleine letters zonder accenten, zodat 'izleyici' 'İzleyici' vindt (Turks), 'istanbul'
    'İstanbul tatil.jpg' en 'cafe' 'café' (ook als de é uit twee tekens bestaat, zoals op een Mac) (U268)."""
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", str(tekst).casefold()) if not unicodedata.combining(c))
