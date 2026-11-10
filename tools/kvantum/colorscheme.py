"""De sleutels in de KDE-kleurenschema's die bij deze stijl horen, voor make.py."""

from __future__ import annotations

import re
from pathlib import Path

from palette import rgb


# ---------------------------------------------------------------- KDE-kleurenschema

def _drie(h: str) -> str:
    return ",".join(str(v) for v in rgb(h))


def schema_kleuren(thema: str, k: dict) -> dict[str, dict[str, str]]:
    """De sleutels in het kleurenschema die bij deze stijl horen (de rest blijft zoals hij is)."""
    donker = thema == "donker"
    sel = {
        # Zachte selectie: rode tint met rode tekst die AA haalt (nooit een volle rode balk).
        "BackgroundNormal": _drie(k["selectie"]),
        "BackgroundAlternate": _drie(k["selectie_alt"]),
        "ForegroundNormal": _drie(k["selectie_tekst"]),
        "ForegroundActive": _drie(k["selectie_tekst"]),
        "ForegroundInactive": _drie(k["tekst2"]),
        "ForegroundLink": _drie(k["selectie_tekst"]),
        "ForegroundVisited": "139,63,168" if not donker else "192,140,224",
        "ForegroundNegative": _drie(k["fout"]),
        "ForegroundNeutral": _drie(k["let_op"]),
        "ForegroundPositive": _drie(k["goed"]),
        # Focus en accent blijven het BugOS-rood.
        "DecorationFocus": _drie(k["accent"]),
    }
    uit = {"Colors:Selection": sel}
    if donker:
        # Donker: pagina = achtergrond, lijsten en kaarten iets lichter (zoals de BugOS-apps).
        uit["Colors:Window"] = {"BackgroundNormal": _drie(k["achter"]), "BackgroundAlternate": _drie(k["zijbalk"])}
        uit["Colors:View"] = {"BackgroundNormal": _drie(k["vlak"]), "BackgroundAlternate": _drie(k["vlak_hover"])}
        uit["Colors:Button"] = {"BackgroundNormal": _drie(k["knop"]), "BackgroundAlternate": _drie(k["knop_hover"])}
        uit["ColorEffects:Disabled"] = {"Color": _drie(k["achter"])}
        uit["ColorEffects:Inactive"] = {"Color": _drie(k["achter"])}
    else:
        uit["Colors:Window"] = {"BackgroundNormal": _drie(k["achter"]), "BackgroundAlternate": _drie(k["zijbalk"])}
        uit["Colors:View"] = {"BackgroundNormal": _drie(k["vlak"])}
        uit["Colors:Button"] = {"BackgroundNormal": _drie(k["knop"]), "BackgroundAlternate": _drie(k["knop_hover"])}
    # Eén vlak per venster, zoals Windows 11 en macOS: de vensterbalk (WM), de kop- en
    # werkbalken (Header) en de zijbalk hebben precies de vensterkleur. Zo loopt de titelbalk
    # naadloos over in het venster, bij de eigen apps en bij KDE-programma's.
    for groep in ("Colors:Header", "Colors:Header][Inactive"):
        uit[groep] = {"BackgroundNormal": _drie(k["achter"]), "BackgroundAlternate": _drie(k["achter"])}
    uit["WM"] = {"activeBackground": _drie(k["achter"]), "inactiveBackground": _drie(k["achter"])}
    # ForegroundActive is in KDE de kleur van een gewone mededeling (Kirigami InlineMessage en Badge
    # "Information"): een rand in die kleur en een vlak met 20% ervan. Rood maakte van elke mededeling
    # in KDE Instellingen een foutmelding; BugOS houdt een mededeling rustig grijs ("alleen wat aandacht
    # nodig heeft krijgt kleur", Melding in bugos_ui = knopgrijs). tekst3 geeft een licht vlak met een
    # zachte rand (tekst2 werd een zwaar grijs blok). Rood blijft voor focus (DecorationFocus), de
    # selectie en fouten (ForegroundNegative).
    for groep in ("Colors:Window", "Colors:View", "Colors:Button", "Colors:Header", "Colors:Header][Inactive"):
        uit.setdefault(groep, {})["ForegroundActive"] = _drie(k["tekst3"])
    return uit


def schema_bijwerken(pad: Path, wijzig: dict[str, dict[str, str]]) -> str:
    """Zet alleen de gegeven sleutels; volgorde, andere groepen en [WM] blijven precies zoals ze zijn."""
    regels = pad.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    groep = None
    gezien: dict[str, set[str]] = {}
    uit = []
    for r in regels:
        m = re.match(r"^\[(.+)\]$", r)
        if m:
            groep = m.group(1)
            gezien.setdefault(groep, set())
        elif groep in wijzig and "=" in r:
            sleutel = r.split("=", 1)[0]
            if sleutel in wijzig[groep]:
                r = f"{sleutel}={wijzig[groep][sleutel]}"
                gezien[groep].add(sleutel)
        uit.append(r)
    ontbreekt = [(g, s) for g, d in wijzig.items() for s in d if s not in gezien.get(g, set())]
    if ontbreekt:
        raise SystemExit(f"{pad.name}: sleutels niet gevonden: {ontbreekt}")
    tekst = "\n".join(uit)
    return tekst if tekst.endswith("\n") else tekst + "\n"
