"""Programma's van het bureaublad (.desktop-bestanden): hun naam en icoon, en wat er vanzelf meestart.

Hoort bij bugos_tasks (BugOS Taakbeheer): haal het daar uit (import bugos_tasks as bt; bt.opstart_lijst()).
"""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path


# ================================================================ apps ===

def app_mappen() -> list[Path]:
    thuis = Path.home()
    data = [Path(os.environ.get("XDG_DATA_HOME", thuis / ".local" / "share"))]
    data += [Path(p) for p in os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":") if p]
    data += [thuis / ".local/share/flatpak/exports/share", Path("/var/lib/flatpak/exports/share")]
    return [d / "applications" for d in data]


_APPS: dict[str, tuple[str, str] | None] = {}


def lees_bureaublad(pad: Path) -> configparser.RawConfigParser | None:
    c = configparser.RawConfigParser(strict=False, interpolation=None)
    c.optionxform = str
    try:
        c.read(pad, encoding="utf-8")
    except (configparser.Error, UnicodeDecodeError):
        return None
    return c if c.has_section("Desktop Entry") else None


def vertaald(sectie: configparser.SectionProxy, sleutel: str) -> str:
    """Name[nl_NL], dan Name[nl], dan Name: in de taal van de gebruiker als dat er is."""
    taal = os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or ""
    code = taal.split(".")[0].split("@")[0]
    kandidaten = [f"{sleutel}[{code}]", f"{sleutel}[{code.split('_')[0]}]"] if code else []
    for k in kandidaten + [sleutel]:
        if k in sectie:
            return sectie.get(k, "")
    return ""


def app_info(app_id: str) -> tuple[str, str] | None:
    """(naam, icoon) van een programma, uit zijn .desktop-bestand."""
    if app_id in _APPS:
        return _APPS[app_id]
    gevonden = None
    for naam in (app_id, app_id.lower()):
        for map_ in app_mappen():
            pad = map_ / f"{naam}.desktop"
            if pad.is_file():
                c = lees_bureaublad(pad)
                if c is not None:
                    s = c["Desktop Entry"]
                    gevonden = (vertaald(s, "Name") or app_id, s.get("Icon", ""))
                    break
        if gevonden:
            break
    _APPS[app_id] = gevonden
    return gevonden


def mooie_naam(app_id: str) -> str:
    """Geen .desktop gevonden? Dan 'org.example.Notities' -> 'Notities'."""
    kort = app_id.rsplit(".", 1)[-1] if "." in app_id else app_id
    return kort[:1].upper() + kort[1:]


# ============================================================== opstarten ===

@dataclass
class Opstart:
    bestand: str        # bv. discord.desktop
    naam: str
    icoon: str
    aan: bool
    van_systeem: bool   # staat in /etc/xdg/autostart (anders alleen bij jou)


def config_thuis() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def systeem_autostart() -> list[Path]:
    return [Path(p) / "autostart" for p in os.environ.get("XDG_CONFIG_DIRS", "/etc/xdg").split(":") if p]


def opstart_lijst() -> list[Opstart]:
    """Programma's die vanzelf starten als je inlogt (zoals 'Opstarten' in Taakbeheer van Windows)."""
    systeem: dict[str, Path] = {}
    for map_ in reversed(systeem_autostart()):
        for pad in sorted(map_.glob("*.desktop")):
            systeem[pad.name] = pad
    eigen = {p.name: p for p in sorted((config_thuis() / "autostart").glob("*.desktop"))}
    lijst = []
    for bestand in sorted(set(systeem) | set(eigen)):
        basis = lees_bureaublad(systeem[bestand]) if bestand in systeem else None
        eigen_c = lees_bureaublad(eigen[bestand]) if bestand in eigen else None
        c = eigen_c if eigen_c is not None and eigen_c["Desktop Entry"].get("Name") else (basis or eigen_c)
        if c is None:
            continue
        s = c["Desktop Entry"]
        bron = basis["Desktop Entry"] if basis is not None else s
        if bron.get("NoDisplay", "false").lower() == "true":
            continue  # onderdelen van het systeem zelf
        alleen = [x for x in bron.get("OnlyShowIn", "").split(";") if x]
        niet = [x for x in bron.get("NotShowIn", "").split(";") if x]
        if (alleen and "KDE" not in alleen) or "KDE" in niet:
            continue
        verborgen = eigen_c is not None and eigen_c["Desktop Entry"].get("Hidden", "false").lower() == "true"
        if basis is not None and basis["Desktop Entry"].get("Hidden", "false").lower() == "true" and eigen_c is None:
            verborgen = True
        lijst.append(Opstart(bestand, vertaald(s, "Name") or vertaald(bron, "Name") or bestand.removesuffix(".desktop"),
                             s.get("Icon", "") or bron.get("Icon", ""), not verborgen, bestand in systeem))
    return sorted(lijst, key=lambda x: x.naam.lower())


ALLEEN_UIT = "[Desktop Entry]\nHidden=true\n"  # wat wij neerzetten om een systeem-programma uit te zetten


def met_hidden(tekst: str, waarde: str) -> str:
    """Zet alleen de regel Hidden= in [Desktop Entry]; de rest (ook commentaar en eigen Exec) blijft precies zo."""
    regels = tekst.splitlines()
    groep, invoeg = "", None
    for i, regel in enumerate(regels):
        kaal = regel.strip()
        if kaal.startswith("[") and kaal.endswith("]"):
            groep = kaal
            if groep == "[Desktop Entry]":
                invoeg = i + 1
            continue
        if groep == "[Desktop Entry]" and kaal.split("=", 1)[0].strip() == "Hidden":
            regels[i] = f"Hidden={waarde}"
            return "\n".join(regels) + "\n"
    if invoeg is None:
        return f"[Desktop Entry]\nHidden={waarde}\n" + tekst
    regels.insert(invoeg, f"Hidden={waarde}")
    return "\n".join(regels) + "\n"


def schrijf_veilig(pad: Path, tekst: str) -> None:
    """Eerst naar een tijdelijk bestand, dan in één keer op zijn plek: nooit een half bestand."""
    tijdelijk = pad.with_name(f".{pad.name}.bugos-nieuw")
    tijdelijk.write_text(tekst, encoding="utf-8")
    os.replace(tijdelijk, pad)


def zet_opstart(item: Opstart, aan: bool) -> None:
    """Aan of uit, alleen voor jou (in ~/.config/autostart). Het origineel blijft heel, en een eigen
    aangepaste versie (andere opdracht, extra opties) ook: we veranderen alleen 'Hidden'."""
    map_ = config_thuis() / "autostart"
    map_.mkdir(parents=True, exist_ok=True)
    pad = map_ / item.bestand
    try:
        eigen = pad.read_text(encoding="utf-8")
    except OSError:
        eigen = None
    if item.van_systeem and eigen is None:
        if not aan:
            schrijf_veilig(pad, ALLEEN_UIT)
        return
    if item.van_systeem and aan and eigen.strip() == ALLEEN_UIT.strip():
        pad.unlink(missing_ok=True)  # alleen ons eigen 'uit'-briefje: weg ermee, dan geldt het origineel weer
        return
    if eigen is None:
        return
    schrijf_veilig(pad, met_hidden(eigen, "false" if aan else "true"))
