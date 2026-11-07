"""De tekens voor status.py: geluid, netwerk, batterij, scherm, meldingen, media, sessie en berichten."""

from __future__ import annotations

import math

from base import LIJN
from status_draw import ROOD, R, Stuk, _boog, _g, _lijnkleur, _p, _stip, _vaag, _vol, lijn


# ================================================================ tekens ===

# ---- geluid ----

def _luidspreker_maten(r: R) -> dict:
    if r.eigen16:
        return {"lijf": "M1.5 6.5H3.5L6.5 3.5V12.5L3.5 9.5H1.5Z", "c": (6.5, 8),
                "bogen": [(3, 40), (5.5, 42), (8, 38)], "kruis": "M9.5 6 13.5 10M13.5 6 9.5 10"}
    return {"lijf": "M2 9.5H5.5L10 5.5V18.5L5.5 14.5H2Z", "c": (10, 12),
            "bogen": [(4.5, 40), (8, 42), (11.5, 38)], "kruis": "M14 9 20 15M20 9 14 15"}


def geluid(r: R, vol: int = 3, *, stil: bool = False, golven: int = 3, buitenste: str = "") -> Stuk:
    """Luidspreker met golfjes: vol = hoeveel er vol zijn; stil = een kruisje; buitenste = kleurklasse."""
    m = _luidspreker_maten(r)
    s = _p(m["lijf"])
    if stil:
        s += _p(m["kruis"])
    else:
        for i, (rad, hoek) in enumerate(m["bogen"][:golven]):
            extra = "" if i < vol else _vaag()
            if i == 2 and buitenste:
                extra = _lijnkleur(buitenste)
            s += _p(_boog(*m["c"], rad, hoek), extra)
    return Stuk(s)


def microfoon(r: R, niveau: int | None = None) -> Stuk:
    """Microfoon; niveau 1-3 vult het kopje (gevoeligheid)."""
    if r.eigen16:
        s = ('<rect x="5.5" y="1.5" width="5" height="8" rx="2.5"/>' +
             _p("M3.5 7.5A4.5 4.5 0 0 0 12.5 7.5") + _p("M8 12V14.5"))
        boven = {1: 6.5, 2: 5, 3: 3}
        if niveau:
            s += f'<rect x="7" y="{_g(boven[niveau])}" width="2" height="{_g(8 - boven[niveau])}" rx="1"{_vol()}/>'
        return Stuk(s)
    s = ('<rect x="9" y="3" width="6" height="11" rx="3"/>' +
         _p("M5.5 11A6.5 6.5 0 0 0 18.5 11") + _p("M12 17.5V21"))
    boven = {1: 9.5, 2: 7.25, 3: 5}
    if niveau:
        s += f'<rect x="11" y="{_g(boven[niveau])}" width="2" height="{_g(12 - boven[niveau])}" rx="1"{_vol()}/>'
    return Stuk(s)


# ---- netwerk ----

def _niveau(pct: int) -> int:
    """Signaal in procenten -> hoeveel delen vol (0-4), zoals plasma-nm afrondt."""
    return 0 if pct == 0 else 1 if pct <= 25 else 2 if pct <= 50 else 3 if pct <= 75 else 4


def wifi(r: R, vol: int = 4) -> Stuk:
    """De wifi-waaier van LIJN: stip + drie boogjes; vol = hoeveel delen vol zijn."""
    delen = [_stip(12, 19.4, 1.45, _vol() + "{v}"),
             _p("M8.9 16A4.6 4.6 0 0 1 15.1 16", "{v}"),
             _p("M5.8 12.6A9 9 0 0 1 18.2 12.6", "{v}"),
             _p("M2.8 9.2A13.5 13.5 0 0 1 21.2 9.2", "{v}")]
    return Stuk("".join(d.replace("{v}", "" if i < vol else _vaag()) for i, d in enumerate(delen)))


def kabel(r: R, verbonden: bool = False) -> Stuk:
    """Netwerkaansluiting (RJ45) van voren; verbonden = de opening is vol."""
    poort = _p("M8 9.5H16V14H14V16H10V14H8Z", ' fill="currentColor"' if verbonden else "")
    return Stuk('<rect x="3.5" y="5" width="17" height="14" rx="2.5"/>' + poort)


def mobiel(r: R, vol: int = 4) -> Stuk:
    """Vier streepjes die hoger worden (mobiel netwerk); vol = hoeveel er vol zijn."""
    if r.eigen16:
        stokken = [(3.5, 11.5), (6.5, 9.5), (9.5, 7), (12.5, 3.5)]
        onder = 13.5
    else:
        stokken = [(5, 16.5), (9.5, 13), (14, 9.5), (18.5, 5)]
        onder = 19.5
    return Stuk("".join(_p(f"M{_g(x)} {_g(onder)}V{_g(top)}", "" if i < vol else _vaag())
                        for i, (x, top) in enumerate(stokken)))


def vliegtuig(r: R) -> Stuk:
    return Stuk(_p("M12 2.5C13 2.5 13.5 3.5 13.5 5V9.5L20.5 13.5V15.5L13.5 13.5V18L15.5 19.5V21L12 20L8.5 21"
                   "V19.5L10.5 18V13.5L3.5 15.5V13.5L10.5 9.5V5C10.5 3.5 11 2.5 12 2.5Z"))


def hotspot(r: R) -> Stuk:
    return Stuk(_stip(12, 12, 1.7) +
                _p("M8.82 8.82A4.5 4.5 0 0 0 8.82 15.18") + _p("M15.18 8.82A4.5 4.5 0 0 1 15.18 15.18") +
                _p("M6.34 6.34A8 8 0 0 0 6.34 17.66") + _p("M17.66 6.34A8 8 0 0 1 17.66 17.66"))


def schild(r: R) -> Stuk:
    """VPN: een schild met een sleutelgat."""
    return Stuk(_p("M12 3.5L19 6.5V11.5C19 15.8 16 19.2 12 20.5C8 19.2 5 15.8 5 11.5V6.5Z") +
                '<circle cx="12" cy="10.5" r="1.8"/>' + _p("M12 12.3V15"))


def bluetooth(r: R, verbonden: bool = False) -> Stuk:
    s = LIJN["bluetooth"]
    if verbonden:
        s += _stip(3.8, 12, 1.45) + _stip(20.2, 12, 1.45)
    return Stuk(s)


def schakel(r: R) -> Stuk:
    """Twee schakels van een ketting: verbinden."""
    return Stuk(_p("M10 14A4.2 4.2 0 0 0 15.9 14L18.8 11.1A4.2 4.2 0 0 0 12.9 5.2L11.4 6.7") +
                _p("M14 10A4.2 4.2 0 0 0 8.1 10L5.2 12.9A4.2 4.2 0 0 0 11.1 18.8L12.6 17.3"))


# ---- batterij ----

def _bliksem(cx: float, cy: float, h: float, breed: float | None = None) -> str:
    """Bliksem rond (cx, cy): h = halve hoogte, breed = halve breedte (standaard 0,6 h)."""
    pt = [(0.35, -1), (-0.6, 0.15), (-0.05, 0.15), (-0.35, 1), (0.6, -0.15), (0.05, -0.15)]
    fx = (breed / 0.6) if breed else h
    return "M" + "L".join(f"{_g(cx + a * fx)} {_g(cy + b * h)}" for a, b in pt) + "Z"


def batterij(r: R, pct: int | None, laden: bool = False, *, leeg_teken: str = "") -> Stuk:
    """Liggende batterij (als LIJN 'batterij') met een gevulde balk.

    Laden: het lijf wordt iets korter en het nokje rechts wordt een bliksem. Zo blijft
    de balk (het niveau) ook tijdens het laden helemaal zichtbaar.
    pct None: geen balk. Onder 20 % is de balk rood; op 0 % (zonder laden) ook de rand.
    Alles valt op hele eenheden, zodat het lijf op 16 en 22 px scherp is."""
    rood = pct is not None and pct < 20 and not laden
    rand = _lijnkleur("ColorScheme-NegativeText") if rood and pct == 0 else ""
    if r.eigen16:
        if laden:
            lijf = '<rect x="1.5" y="4.5" width="9" height="7" rx="1.5"/>'
            bx, by, bb, bh, brx = 3, 6, 6, 4, 0.75
            flits, fd = _bliksem(13.75, 8, 3.6, 1.5), 0.5     # 12..15,5: 1 px ruimte naast het lijf
        else:
            lijf = f'<rect x="1.5" y="4.5" width="11" height="7" rx="1.5"{rand}/>' + _p("M14.5 6.5V9.5", rand)
            bx, by, bb, bh, brx = 3, 6, 8, 4, 0.75
    else:
        if laden:
            lijf = '<rect x="2" y="7" width="13" height="10" rx="2.2"/>'
            bx, by, bb, bh, brx = 4, 9, 9, 6, 1
            flits, fd = _bliksem(20.2, 12, 5, 2.3), 1         # 17,4..23: past ook in de 22-viewBox
        else:
            lijf = f'<rect x="3" y="7" width="16" height="10" rx="2.2"{rand}/>' + _p("M21.5 10.5V13.5", rand)
            bx, by, bb, bh, brx = 5, 9, 12, 6, 1
    stuk = Stuk(lijf)
    if pct:
        w = max(bb * pct / 100, 1.5 if not r.eigen16 else 1)
        kleur = _vol("ColorScheme-NegativeText") if pct < 20 else _vol()
        stuk.erop(f'<rect x="{_g(bx)}" y="{_g(by)}" width="{_g(w)}" height="{_g(bh)}" rx="{_g(brx)}"{kleur}/>')
    if laden:
        stuk.erop(_p(flits, f' fill="currentColor" stroke-width="{_g(fd)}"'))
    if leeg_teken:
        stuk.erop(leeg_teken)
    return stuk


def ups(r: R) -> Stuk:
    return Stuk('<rect x="5" y="3.5" width="14" height="17" rx="2.5"/>' +
                _p(_bliksem(12, 12, 4.2), ' fill="currentColor" stroke-width="1"'))


def meter(r: R, wijzer: str = "M12 13L15.3 8.6") -> Stuk:
    """Snelheidsmeter (energieprofiel 'gebalanceerd', of geen batterij)."""
    return Stuk(_p("M4.64 17.25A8.5 8.5 0 1 1 19.36 17.25") + _p(wijzer) + _stip(12, 13, 1.5))


def blad(r: R) -> Stuk:
    """Blaadje: energie besparen."""
    return Stuk(_p("M5.5 18.5C5.5 10 10.5 5 19 5C19 13.5 14 18.5 5.5 18.5Z") + _p("M5.5 18.5L13 11"))


# ---- helderheid, nachtlicht, meldingen ----

def zon_zacht(r: R) -> Stuk:
    """Lage helderheid: het zonnetje met puntjes in plaats van stralen."""
    s = '<circle cx="12" cy="12" r="3.8"/>'
    for i in range(8):
        a = math.radians(i * 45 - 90)
        s += _stip(12 + 7.6 * math.cos(a), 12 + 7.6 * math.sin(a), 1.15)
    return Stuk(s)


def toetsenbordlicht(r: R) -> Stuk:
    return Stuk('<rect x="3" y="13" width="18" height="7.5" rx="2"/>' + _p("M8.5 17H15.5") +
                _p("M8.5 9.5A3.5 3.5 0 0 1 15.5 9.5") +
                _p("M12 3V4.5M6.6 5.2L7.6 6.2M17.4 5.2L16.4 6.2M4.5 9.5H5.5M18.5 9.5H19.5"))


def contrast(r: R) -> Stuk:
    return Stuk('<circle cx="12" cy="12" r="8.5"/>' + _p("M12 3.5A8.5 8.5 0 0 1 12 20.5Z", _vol()))


def bel(r: R) -> Stuk:
    return lijn("bel")


def ring(r: R) -> Stuk:
    """Lege ring: Plasma tekent hierover de voortgang van taken, met het aantal erin."""
    return Stuk(f'<circle cx="12" cy="12" r="8.5"{_vaag()}/>')


# ---- media ----

def media(r: R, wat: str) -> Stuk:
    k = r.eigen16
    d = {
        "start": "M5.5 3.5V12.5L12.5 8Z" if k else "M8 5.5V18.5L18.5 12Z",
        "pause": "M5.5 4V12M10.5 4V12" if k else "M9 6V18M15 6V18",
        "volgende": "M4.5 4.5V11.5L9.5 8ZM11.5 4V12" if k else "M6.5 6.5V17.5L14.5 12ZM17.5 6V18",
        "vorige": "M11.5 4.5V11.5L6.5 8ZM4.5 4V12" if k else "M17.5 6.5V17.5L9.5 12ZM6.5 6V18",
        "vooruit": "M2.5 4.5V11.5L7.5 8ZM8.5 4.5V11.5L13.5 8Z" if k else "M3.5 7V17L11.5 12ZM12.5 7V17L20.5 12Z",
        "terug": "M13.5 4.5V11.5L8.5 8ZM7.5 4.5V11.5L2.5 8Z" if k else "M20.5 7V17L12.5 12ZM11.5 7V17L3.5 12Z",
    }
    if wat == "stop":
        return Stuk('<rect x="4.5" y="4.5" width="7" height="7" rx="1.5"/>' if k else
                    '<rect x="6.5" y="6.5" width="11" height="11" rx="2"/>')
    if wat == "opnemen":
        return Stuk(_stip(8, 8, 4.5) if k else _stip(12, 12, 6.5))
    return Stuk(_p(d[wat]))


def herhaal(r: R, een: bool = False) -> Stuk:
    s = (_p("M17 3.5L20 6.5L17 9.5") + _p("M20 6.5H8A4 4 0 0 0 4 10.5V11.5") +
         _p("M7 20.5L4 17.5L7 14.5") + _p("M4 17.5H16A4 4 0 0 0 20 13.5V12.5"))
    if een:
        s += _p("M11 10.5L12.5 9.5V14.5")
    return Stuk(s)


def door_elkaar(r: R) -> Stuk:
    return Stuk(_p("M16.5 3.5L20 7L16.5 10.5") + _p("M16.5 13.5L20 17L16.5 20.5") +
                _p("M4 7H7.5C10.5 7 12 9 12 12S13.5 17 16.5 17H20") +
                _p("M4 17H7.5C8.8 17 9.8 16.6 10.5 15.9") + _p("M13.5 8.1C14.2 7.4 15.2 7 16.5 7H20"))


# ---- aan/uit en sessie ----

def deur(r: R) -> Stuk:
    """Uitloggen: een deur met een pijl naar buiten."""
    return Stuk(_p("M9.5 20.5H6A1.5 1.5 0 0 1 4.5 19V5A1.5 1.5 0 0 1 6 3.5H9.5") +
                _p("M15.5 16.5L20 12L15.5 7.5") + _p("M20 12H9.5"))


def sneeuw(r: R) -> Stuk:
    """Slaapstand naar schijf (winterslaap): een sneeuwvlok."""
    s = ""
    for i in range(6):
        a = math.radians(i * 60 - 90)
        ux, uy = math.cos(a), math.sin(a)
        s += _p(f"M12 12L{_g(12 + 8.5 * ux)} {_g(12 + 8.5 * uy)}")
        bx, by = 12 + 5.6 * ux, 12 + 5.6 * uy
        for t in (-1, 1):
            b = a + t * math.radians(50)
            s += _p(f"M{_g(bx)} {_g(by)}L{_g(bx + 2.6 * math.cos(b))} {_g(by + 2.6 * math.sin(b))}")
    return Stuk(s)


def twee_personen(r: R) -> Stuk:
    return Stuk('<circle cx="9" cy="8" r="3.5"/>' + _p("M2.5 20A6.5 6.5 0 0 1 15.5 20") +
                _p("M15.5 4.7A3.5 3.5 0 0 1 15.5 11.3") + _p("M18 14.2A6.5 6.5 0 0 1 21.5 20"))


# ---- toetsenbord, camera, temperatuur ----

def hoofdletters(r: R) -> Stuk:
    return Stuk(_p("M12 4.5L4.5 12H8.5V16H15.5V12H19.5Z") + _p("M8.5 19.5H15.5"))


def cijfers(r: R) -> Stuk:
    return Stuk('<rect x="4" y="4" width="16" height="16" rx="3"/>' + _p("M10.5 9L12.5 7.5V16.5"))


def camera(r: R, aan: bool = False) -> Stuk:
    s = '<rect x="3" y="6.5" width="12.5" height="11" rx="2.5"/>' + _p("M15.5 10.5L20.5 7.5V16.5L15.5 13.5")
    if aan:
        s += _stip(9.25, 12, 2.1, _vol(ROOD))
    return Stuk(s)


def thermometer(r: R, top: float) -> Stuk:
    return Stuk(_p("M10 13.5V5.5A2 2 0 0 1 14 5.5V13.5A4 4 0 1 1 10 13.5Z") +
                _p(f"M12 16.5V{_g(top)}") + _stip(12, 17, 1.6))


# ---- berichten (dialog-*) ----

def cirkel(binnen: str) -> Stuk:
    return Stuk('<circle cx="12" cy="12" r="8.5"/>' + binnen)


def _vraag() -> str:
    return _p("M9.6 9.6A2.5 2.5 0 1 1 13 11.9C12.4 12.2 12 12.8 12 13.5V13.8") + _stip(12, 16.7, 1.15)


def _info() -> str:
    return _p("M12 11V16.5") + _stip(12, 7.9, 1.15)


def gekleurd(stuk: Stuk, klasse: str) -> Stuk:
    """Hele tekening in één kleurklasse (waarschuwing, fout, goed)."""
    for laag in stuk.lagen:
        laag[0] = f'<g class="{klasse}" stroke="currentColor">' + laag[0].replace(_vol(), _vol(klasse)) + "</g>"
    return stuk


def sleutel(r: R) -> Stuk:
    return Stuk('<circle cx="8" cy="16" r="4"/>' + _p("M10.9 13.1L19.5 4.5") + _p("M16.5 7.5L19 10") +
                _p("M14.3 9.7L16.3 11.7"))
