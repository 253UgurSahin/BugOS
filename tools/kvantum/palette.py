"""Kleuren voor make.py: de thema's, vaste maten, kleurrekenen en het palet (PALETTEN) per thema."""

from __future__ import annotations

from tokens import KLEUREN, MATEN, ROOD_VERLOOP, ROOD_VERLOOP_DONKER


#: thema -> (Kvantum-naam, kleurenschema)
THEMAS = {"licht": ("BugOS", "BugOSLight"), "donker": ("BugOSDark", "BugOSDark")}

STATEN = ("normal", "focused", "pressed", "toggled", "disabled")
KNOP = MATEN["knop"]      # 12: knoppen, velden, menu's, tooltips
KAART = MATEN["kaart"]    # 16: kaarten, groepen


# ---------------------------------------------------------------- kleuren

def rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def hexk(c) -> str:
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(v))) for v in c)


def meng(a: str, b: str, t: float) -> str:
    """t=0 -> a, t=1 -> b."""
    ra, rb = rgb(a), rgb(b)
    return hexk(tuple(x + (y - x) * t for x, y in zip(ra, rb)))


def lum(h: str) -> float:
    def lin(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(v) for v in rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def leesbaar(kleur: str, achter: list[str], naar: str, minimum: float = 4.6) -> str:
    """Schuif kleur stapje voor stapje richting `naar` tot hij op alle achtergronden AA haalt."""
    for i in range(0, 101):
        k = meng(kleur, naar, i / 100)
        if all(contrast(k, a) >= minimum for a in achter):
            return k
    return naar


def palet(thema: str) -> dict:
    """De tokens plus de paar afgeleide kleuren die Kvantum nodig heeft."""
    k = dict(KLEUREN[thema])
    donker = thema == "donker"
    k["verloop"] = ROOD_VERLOOP_DONKER if donker else ROOD_VERLOOP
    k["knop_druk"] = meng(k["knop_hover"], k["tekst"], 0.10 if donker else 0.07)
    # Zachte selectie (zoals in BugOS Instellingen): rode tint, rode tekst die AA haalt.
    k["selectie"] = k["accent_zacht"]
    k["selectie_alt"] = meng(k["accent_zacht"], k["accent_lijn"], 0.35)
    k["selectie_tekst"] = leesbaar(k["accent"], [k["selectie"], k["selectie_alt"], k["vlak"], k["achter"]],
                                   "#FFFFFF" if donker else "#000000")
    k["link"] = leesbaar(k["accent"], [k["vlak"], k["achter"]], "#FFFFFF" if donker else "#000000")
    # Tooltip zoals het kleurenschema: licht thema inkt met lichte tekst, donker thema omgekeerd.
    k["tip"] = "#16171C" if not donker else "#EDEEF1"
    k["tip_tekst"] = "#F6F5F5" if not donker else "#16171C"
    k["tip_rand"] = k["tip"]
    # Schuifbalkje: warm grijs, iets donkerder als je erop wijst (zoals QScrollBar in bugos_ui).
    k["balk"] = k["rand_sterk"]
    k["balk_hover"] = k["tekst3"]
    # Focus op labels en rijen (vinkjes, tabbladen, huidige rij): een rustig grijs streepje eronder.
    k["focus_streep"] = k["tekst3"]
    k["spoor"] = k["rand"] if not donker else k["rand_sterk"]
    k["uit_tekst"] = k["tekst3"]
    k["schaduw_kleur"] = "#000000"
    k["schaduw_alpha"] = 0.35 if donker else 0.10
    # Het bolletje van een schuif is altijd wit, met een haarlijntje (ook in donker, zoals in de apps).
    k["bol"] = "#FFFFFF"
    k["bol_rand"] = k["rand_sterk"] if not donker else "#00000000"
    k["vink_vlak"] = k["accent"]
    # Standaardknop: het accent als dunne laag over de knop (licht #EFD7D9, donker #4D2D35 in rust).
    k["standaard_tint"] = k["accent"] + ("33" if donker else "1F")
    return k


PALETTEN = {t: palet(t) for t in THEMAS}
