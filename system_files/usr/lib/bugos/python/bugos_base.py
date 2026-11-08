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
    except (OSError, ValueError):
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


def start(*cmd: str) -> bool:
    """Start een programma los op de achtergrond. Geeft False als het niet kon."""
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
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
