"""Systeemvak, schermmeldingen (OSD), Plasma-pop-ups en knoppen: eenkleurige BugOS-lijniconen.

Voor: geluid en microfoon, netwerk (wifi, kabel, mobiel, vpn, vliegtuigstand),
bluetooth, batterij en energieprofielen, helderheid en nachtlicht, meldingen,
media, aan/uit en sessie, toetsenbordlampjes, camera, de berichtpictogrammen
(dialog-*), de gewone knoppen (go-, edit-, view-, window-, ...) en emblemen.

Namen: precies zoals Plasma 6.8 ze vraagt (uit de QML van de applets in het
BugOS-image en uit breeze-icons). KDE zoekt eerst de hele naam en haalt er daarna
stukjes van achteren af (battery-050-charging-profile-performance-symbolic ->
battery-050-charging-symbolic); daarom staat elk niveau er met zijn eigen naam in.

Huisstijl (docs/BRAND.md): 24-raster, lijn 2, ronde uiteinden, in de
tekstkleur (ColorScheme-Text met currentColor, KDE kleurt mee met licht en
donker). Niveaus lees je af aan wat vol is: geluid 0-3 golfjes, wifi 0-3
boogjes, mobiel 0-4 streepjes (de rest op 35 %), batterij en microfoon een
gevulde balk (batterij onder 20 % rood). Bij laden wordt het nokje van de
batterij een bliksem, zodat je het niveau blijft zien. Uit = een schuine streep
met ruimte eromheen. Kleur alleen waar iets aandacht vraagt (een nieuwe melding,
een probleem).

Elk pictogram komt in <soort>/scalable (elke maat vanaf 17 behalve precies 22),
<soort>/22 en <soort>/16.
22 is de maat van het systeemvak en van werkbalken: daar staat dezelfde 24-tekening
met een viewBox van 22 eenheden (1 eenheid = 1 pixel), zodat de lijnen op hele
pixels vallen in plaats van wazig verkleind te worden. De families met niveaus en
de mediaknoppen hebben voor 16 een eigen tekening op een 16-raster (lijn 1 op halve
pixels: scherp); de rest is de 24-tekening met lijn 1,5.

Let op, QtSvg (zo tekent KDE): een element met een eigen ColorScheme-klasse krijgt
die kleur alleen als het zelf ook stroke/fill="currentColor" heeft; clipPath werkt
niet, mask wel (Qt 6.11). En ColorScheme-Highlight is in BugOS de zachte
selectietint (#FDE9E9 / #3A1C22): voor een rode stip dus ColorScheme-NegativeText.
"""

from __future__ import annotations

import math

import basis
from basis import LIJN, STIJLBLAD

VAAG = 0.35          # niet-gevulde niveaus (boogjes, golfjes, streepjes)
NIVEAUS = (0, 20, 40, 60, 80, 100)
ROOD = "ColorScheme-NegativeText"   # rode stip (melding, update, camera aan)

# Eigen 22-mappen (systeemvak, werkbalken). Ze staan in index.theme vóór */scalable,
# dus KDE kiest ze op precies 22 px; op 24 en groter blijft het */scalable.
basis.map_erbij("status/22", Size=22, Context="Status", Type="Fixed")
basis.map_erbij("actions/22", Size=22, Context="Actions", Type="Fixed")


# ================================================================ tekenen ===

def _g(x: float) -> str:
    """Getal kort opschrijven (12.0 -> 12, 3.456 -> 3.46)."""
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


class R:
    """Hoe er getekend wordt: raster van de coördinaten, lijndikte en bestandsmaat."""

    def __init__(self, raster: int, dikte: float, maat: int):
        self.raster, self.dikte, self.maat = raster, dikte, maat
        self.f = raster / 24                    # 24-maten omrekenen naar dit raster
        self.gat = 1.5 if raster == 24 else 1   # ruimte rond een streep of badge

    @property
    def eigen16(self) -> bool:
        return self.raster == 16


GROOT = R(24, 2, 24)       # <soort>/scalable
KLEIN24 = R(24, 1.5, 16)   # <soort>/16, dezelfde tekening (1,5 op 24 = 1 pixel)
KLEIN16 = R(16, 1, 16)     # <soort>/16, eigen tekening op het 16-raster


class Stuk:
    """Een tekening in lagen. Elke laag kan uitsparingen hebben (een SVG-mask)."""

    def __init__(self, inhoud: str = ""):
        self.lagen: list[list[str]] = [[inhoud, ""]]

    def snij(self, gaten: str) -> "Stuk":
        """Snijd uit alles wat er al staat (zwarte vormen; ze krijgen zelf hun maten mee)."""
        for laag in self.lagen:
            laag[1] += gaten
        return self

    def erop(self, inhoud: str, gaten: str = "") -> "Stuk":
        self.lagen.append([inhoud, gaten])
        return self


def svg(stuk: Stuk, r: R) -> str:
    n = r.raster
    defs, lijf = [], []
    for i, (inhoud, gaten) in enumerate(stuk.lagen):
        if not inhoud:
            continue
        if gaten:
            defs.append(f'<mask id="m{i}" maskUnits="userSpaceOnUse" x="0" y="0" width="{n}" height="{n}">'
                        f'<rect width="{n}" height="{n}" fill="#fff"/>{gaten}</mask>')
            lijf.append(f'<g mask="url(#m{i})">{inhoud}</g>')
        else:
            lijf.append(inhoud)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{r.maat}" height="{r.maat}" viewBox="0 0 {n} {n}">'
            f'{STIJLBLAD}' + (f'<defs>{"".join(defs)}</defs>' if defs else "") +
            f'<g class="ColorScheme-Text" fill="none" stroke="currentColor" stroke-width="{_g(r.dikte)}" '
            f'stroke-linecap="round" stroke-linejoin="round">{"".join(lijf)}</g></svg>')


# ---- kleine bouwstenen (op het 24-raster, tenzij r.eigen16) ----

def _p(d: str, extra: str = "") -> str:
    return f'<path d="{d}"{extra}/>'


def _vol(klasse: str = "") -> str:
    """Gevuld vlak; met klasse in een eigen kleur."""
    k = f' class="{klasse}"' if klasse else ""
    return f'{k} fill="currentColor" stroke="none"'


def _lijnkleur(klasse: str) -> str:
    return f' class="{klasse}" stroke="currentColor"'


def _vaag() -> str:
    return f' opacity="{VAAG}"'


def _stip(x: float, y: float, rad: float, extra: str = "") -> str:
    return f'<circle cx="{_g(x)}" cy="{_g(y)}" r="{_g(rad)}"{extra or _vol()}/>'


def _gat_lijn(d: str, breedte: float) -> str:
    return f'<path d="{d}" fill="none" stroke="#000" stroke-width="{_g(breedte)}" stroke-linecap="round" stroke-linejoin="round"/>'


def _gat_rond(x: float, y: float, rad: float) -> str:
    return f'<circle cx="{_g(x)}" cy="{_g(y)}" r="{_g(rad)}" fill="#000"/>'


def _boog(cx: float, cy: float, rad: float, hoek: float) -> str:
    """Boogje rechts van (cx, cy), van boven naar onder, hoek graden boven en onder de horizon."""
    a = math.radians(hoek)
    x = cx + rad * math.cos(a)
    return f"M{_g(x)} {_g(cy - rad * math.sin(a))}A{_g(rad)} {_g(rad)} 0 0 1 {_g(x)} {_g(cy + rad * math.sin(a))}"


def lijn(naam: str) -> Stuk:
    return Stuk(LIJN[naam])


# ---- toevoegingen: uit-streep en badges ----

def uit(stuk: Stuk, r: R) -> Stuk:
    """Schuine streep van linksboven naar rechtsonder, met ruimte eromheen."""
    a, b = (3.5, 20.5) if not r.eigen16 else (2.5, 13.5)
    d = f"M{_g(a)} {_g(a)}L{_g(b)} {_g(b)}"
    return stuk.snij(_gat_lijn(d, r.dikte + 2 * r.gat)).erop(_p(d))


def met_slot(stuk: Stuk, r: R) -> Stuk:
    """Slotje rechtsonder (beveiligd netwerk of vpn aan)."""
    f = r.f
    body = (f'<rect x="{_g(15.5 * f)}" y="{_g(17.75 * f)}" width="{_g(6 * f)}" height="{_g(4.5 * f)}" '
            f'rx="{_g(1.2 * f)}"{_vol()}/>')
    beugel = _p(f"M{_g(16.75 * f)} {_g(17.75 * f)}V{_g(16.6 * f)}A{_g(1.75 * f)} {_g(1.75 * f)} 0 0 1 "
                f"{_g(20.25 * f)} {_g(16.6 * f)}V{_g(17.75 * f)}")
    return stuk.snij(_gat_rond(18.5 * f, 18.4 * f, 4.4 * f + r.gat)).erop(body + beugel)


def met_let_op(stuk: Stuk, r: R) -> Stuk:
    """Oranje stip met een uitroepteken erin, rechtsonder (wel verbonden, geen internet)."""
    f = r.f
    cx, cy, rad = 18.5 * f, 18.5 * f, 3.9 * f
    teken = (_gat_lijn(f"M{_g(cx)} {_g(cy - 1.9 * f)}V{_g(cy + 0.2 * f)}", max(1.6 * f, 1)) +
             _gat_rond(cx, cy + 1.9 * f, max(0.85 * f, 0.6)))
    return stuk.snij(_gat_rond(cx, cy, rad + r.gat)).erop(_stip(cx, cy, rad, _vol("ColorScheme-NeutralText")), teken)


def met_punt(stuk: Stuk, r: R, klasse: str = ROOD) -> Stuk:
    """Rode stip rechtsboven: er is iets nieuws (melding, update)."""
    f = r.f
    cx, cy, rad = 19 * f, 5 * f, 2.7 * f
    return stuk.snij(_gat_rond(cx, cy, rad + r.gat)).erop(_stip(cx, cy, rad, _vol(klasse)))


def met_kruis(stuk: Stuk, r: R) -> Stuk:
    """Stip met een kruisje erin, rechtsonder: niet verbonden."""
    f = r.f
    cx, cy, rad, k = 18.5 * f, 18.5 * f, 3.9 * f, 1.5 * f
    teken = _gat_lijn(f"M{_g(cx - k)} {_g(cy - k)}L{_g(cx + k)} {_g(cy + k)}M{_g(cx + k)} {_g(cy - k)}L{_g(cx - k)} {_g(cy + k)}",
                      max(1.5 * f, 1))
    return stuk.snij(_gat_rond(cx, cy, rad + r.gat)).erop(_stip(cx, cy, rad), teken)


def met_klok(stuk: Stuk, r: R) -> Stuk:
    """Klokje rechtsonder: bezig met verbinden."""
    f = r.f
    cx, cy, rad = 18.5 * f, 18.5 * f, 3.4 * f
    klok = (f'<circle cx="{_g(cx)}" cy="{_g(cy)}" r="{_g(rad)}"/>' +
            _p(f"M{_g(cx)} {_g(cy - 1.7 * f)}V{_g(cy)}L{_g(cx + 1.2 * f)} {_g(cy + 0.9 * f)}"))
    return stuk.snij(_gat_rond(cx, cy, rad + r.dikte / 2 + r.gat)).erop(klok)


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


# ---- knoppen ----

def tandwiel(r: R) -> Stuk:
    """Tandwiel (zelfde maten als in settings.py)."""
    cx = cy = 12
    r_top, r_voet, tanden, top, voet = 8.6, 6.3, 8, 1.3, 2.0

    def p(rad: float, a: float) -> str:
        return f"{_g(cx + rad * math.cos(a))} {_g(cy + rad * math.sin(a))}"
    d = []
    stap = 2 * math.pi / tanden
    for i in range(tanden):
        a = -math.pi / 2 + i * stap
        at, av = top / r_top, voet / r_voet
        if i == 0:
            d.append(f"M{p(r_voet, a - av)}")
        d.append(f"L{p(r_top, a - at)}")
        d.append(f"A{_g(r_top)} {_g(r_top)} 0 0 1 {p(r_top, a + at)}")
        d.append(f"L{p(r_voet, a + av)}")
        d.append(f"A{_g(r_voet)} {_g(r_voet)} 0 0 1 {p(r_voet, a + stap - av)}")
    return Stuk(_p("".join(d) + "Z") + '<circle cx="12" cy="12" r="2.6"/>')


def p(*paden: str) -> callable:
    """Een teken van alleen lijnen (24-raster)."""
    return lambda r: Stuk("".join(x if x.startswith("<") else _p(x) for x in paden))


def l(naam: str, *extra: str) -> callable:
    """LIJN-teken, eventueel met extra lijnen erbij."""
    return lambda r: Stuk(LIJN[naam] + "".join(x if x.startswith("<") else _p(x) for x in extra))


def _doc_rand() -> str:
    return _p("M7 3.5H13.5L18 8V19.5A1 1 0 0 1 17 20.5H7A1 1 0 0 1 6 19.5V4.5A1 1 0 0 1 7 3.5Z") + _p("M13.5 3.5V8H18")


def _meer(r: R, staand: bool = False) -> Stuk:
    """De drie puntjes van LIJN 'meer' (ring 1,2 met lijn 2 = een stip van 2,2), net als in de BugOS-apps."""
    rad = 1.2 + r.dikte / 2
    return Stuk("".join(_stip(12, c, rad) if staand else _stip(c, 12, rad) for c in (5.5, 12, 18.5)))


HOEKEN = ("M4 8V5.5A1.5 1.5 0 0 1 5.5 4H8M16 4H18.5A1.5 1.5 0 0 1 20 5.5V8"
          "M20 16V18.5A1.5 1.5 0 0 1 18.5 20H16M8 20H5.5A1.5 1.5 0 0 1 4 18.5V16")

KNOPPEN: dict[str, callable] = {
    # richting
    "links": l("links"), "rechts": l("rechts"), "onder": l("onder"), "boven": p("M6.5 14.5L12 9L17.5 14.5"),
    "eerste": p("M16.5 6L10.5 12L16.5 18", "M7.5 6V18"), "laatste": p("M7.5 6L13.5 12L7.5 18", "M16.5 6V18"),
    "top": p("M6 17L12 11L18 17", "M6 6.5H18"), "bodem": p("M6 7L12 13L18 7", "M6 17.5H18"),
    "pijl-links": p("M19.5 12H5", "M10.5 6L4.5 12L10.5 18"), "pijl-rechts": p("M4.5 12H19", "M13.5 6L19.5 12L13.5 18"),
    "pijl-op": p("M12 19.5V5", "M6 10.5L12 4.5L18 10.5"), "pijl-neer": p("M12 4.5V19", "M6 13.5L12 19.5L18 13.5"),
    "huis": l("huis"),
    # vensters
    "kruis": l("kruis"), "streep": p("M6.5 12H17.5"), "vierkant": p('<rect x="6" y="6" width="12" height="12" rx="2"/>'),
    "terugzetten": p('<rect x="5" y="9" width="10" height="10" rx="2"/>', "M9 5.5H16.5A2 2 0 0 1 18.5 7.5V15"),
    "nieuw-venster": p('<rect x="3.5" y="5" width="17" height="14" rx="2.5"/>', "M12 9V15M9 12H15"),
    "speld": p("M8.5 3.5H15.5", "M9.5 3.5V9L6.5 13V14.5H17.5V13L14.5 9V3.5", "M12 14.5V20.5"),
    # bewerken
    "kopieer": l("kopieer"), "knip": l("schaar"), "plak": l("plak"), "weg": l("prullenbak"), "zoek": l("zoek"),
    "potlood": l("potlood"), "vink": l("vink"), "meer": l("meer"), "verversen": l("verversen"),
    "ongedaan": p("M9 14L4 9L9 4", "M4 9H14.5A5.5 5.5 0 0 1 14.5 20H11"),
    "opnieuw": p("M15 14L20 9L15 4", "M20 9H9.5A5.5 5.5 0 0 0 9.5 20H13"),
    "herstel": p("M4.5 12A7.5 7.5 0 1 0 6.7 6.7", "M4.5 4V8.5H9"),
    "wis-veld": lambda r: cirkel(_p("M9 9L15 15M15 9L9 15")),
    "backspace": p("M8.5 5.5H19A2 2 0 0 1 21 7.5V16.5A2 2 0 0 1 19 18.5H8.5L2.5 12Z", "M11.5 9.5L16.5 14.5M16.5 9.5L11.5 14.5"),
    "backspace-r": p("M15.5 5.5H5A2 2 0 0 0 3 7.5V16.5A2 2 0 0 0 5 18.5H15.5L21.5 12Z", "M7.5 9.5L12.5 14.5M12.5 9.5L7.5 14.5"),
    "gum": p("M9.6 20.4L3.6 14.4L13.4 4.6L19.4 10.6Z", "M7.5 10.5L13.5 16.5", "M9.6 20.4H20.5"),
    "hernoem": p("M4 9.5H11M4 14.5H9", "M16.5 5V19M14 5H19M14 19H19"),
    "alles": p(HOEKEN, "M8.5 12L11 14.5L15.5 9.5"), "niets": p(HOEKEN),
    "geen": lambda r: cirkel(_p("M6 6L18 18")),
    "plus": p("M12 5V19M5 12H19"), "min": p("M5 12H19"),
    # weergave
    "menu": p("M4 7H20M4 12H20M4 17H20"),
    "meer-staand": lambda r: _meer(r, True),
    "meer-liggend": lambda r: _meer(r),
    "lijst": p("M9 6.5H20M9 12H20M9 17.5H20", _stip(4.75, 6.5, 1.3), _stip(4.75, 12, 1.3), _stip(4.75, 17.5, 1.3)),
    "tegels": l("apps"), "tekstlijst": p("M4 6.5H20M4 12H20M4 17.5H14"),
    "boom": p("M4 5.5H14", "M5.5 5.5V18H8.5M5.5 12H8.5", "M11 12H20M11 18H20"),
    "oog": l("oog"), "trechter": p("M4 5H20L14 12.5V19L10 17V12.5Z"),
    "sorteer-op": p("M4 6.5H11M4 12H9M4 17.5H7", "M17 19V5", "M13.5 8.5L17 5L20.5 8.5"),
    "sorteer-neer": p("M4 6.5H11M4 12H9M4 17.5H7", "M17 5V19", "M13.5 15.5L17 19L20.5 15.5"),
    "qr": p('<rect x="4" y="4" width="6" height="6" rx="1.5"/>', '<rect x="14" y="4" width="6" height="6" rx="1.5"/>',
            '<rect x="4" y="14" width="6" height="6" rx="1.5"/>', "M14 14H16.5V16.5H14ZM19.5 14V14.01M14 19.5H14.01M17.5 17.5H20V20H17.5Z"),
    "groot": p("M14.5 4.5H19.5V9.5", "M19.5 4.5L14 10", "M9.5 19.5H4.5V14.5", "M4.5 19.5L10 14"),
    "klein": p("M9.5 4.5V9.5H4.5", "M4 4L9.5 9.5", "M14.5 19.5V14.5H19.5", "M20 20L14.5 14.5"),
    "geschiedenis": p("M3.5 12A8.5 8.5 0 1 0 6.2 5.8L3.5 8.5", "M3.5 4V8.5H8", "M12 7.5V12L15 14"),
    "inzoomen": l("zoek", "M8 11H14M11 8V14"), "uitzoomen": l("zoek", "M8 11H14"),
    # documenten
    "open": p("M3.5 18.5V6.5A1.5 1.5 0 0 1 5 5H9.5L11.5 7H17A1.5 1.5 0 0 1 18.5 8.5V10.5",
              "M3.5 18.5L6.2 12A1.5 1.5 0 0 1 7.6 11H20.2A1 1 0 0 1 21.1 12.4L18.6 18.1A1.5 1.5 0 0 1 17.2 19H4A.5.5 0 0 1 3.5 18.5Z"),
    "bewaar": p("M5.5 3.5H15.5L20.5 8.5V18.5A2 2 0 0 1 18.5 20.5H5.5A2 2 0 0 1 3.5 18.5V5.5A2 2 0 0 1 5.5 3.5Z",
                "M7.5 3.5V8H14.5V3.5", "M7.5 20.5V14.5H16.5V20.5"),
    "nieuw": lambda r: Stuk(_doc_rand() + _p("M12 11.5V17.5M9 14.5H15")),
    "document": l("document"),
    "versturen": p("M21 3L10.5 13.5", "M21 3L14.5 21L10.5 13.5L3 9.5Z"),
    "delen": p('<circle cx="17.5" cy="5.5" r="2.5"/>', '<circle cx="6.5" cy="12" r="2.5"/>',
               '<circle cx="17.5" cy="18.5" r="2.5"/>', "M8.7 10.7L15.3 6.8M8.7 13.3L15.3 17.2"),
    "printer": l("printer"),
    # overig
    "stop": p("M8.5 3.5H15.5L20.5 8.5V15.5L15.5 20.5H8.5L3.5 15.5V8.5Z", "M9.5 9.5L14.5 14.5M14.5 9.5L9.5 14.5"),
    "vraag": lambda r: cirkel(_vraag()), "info": lambda r: cirkel(_info()),
    "tandwiel": tandwiel, "plak-bord": l("plak"), "uitwerpen": l("uitwerpen"), "muziek": l("muziek"),
    "deur": deur, "aan": l("aan"), "maan": l("maan"), "slot": l("slot"), "zon": l("zon"),
    "contrast": contrast, "meter": meter, "schakel": schakel,
    # KDE Instellingen (Importeren, Standaard), KDE-dialogen en het KWin-venstermenu
    "importeer": l("download"), "exporteer": p("M12 15V4", "M7.5 8.5L12 4L16.5 8.5", "M5 19.5H19"),
    "voorbeeld": l("foto"),
    "boven-houden": p('<rect x="4" y="11" width="16" height="9.5" rx="2"/>', "M8 7.5L12 3.5L16 7.5"),
    "onder-houden": p('<rect x="4" y="3.5" width="16" height="9.5" rx="2"/>', "M8 16.5L12 20.5L16 16.5"),
    "verplaats": p("M12 3.5V20.5M3.5 12H20.5", "M9.5 6L12 3.5L14.5 6M9.5 18L12 20.5L14.5 18",
                   "M6 9.5L3.5 12L6 14.5M18 9.5L20.5 12L18 14.5"),
    "schaal": p("M13.5 4.5H19.5V10.5", "M10.5 19.5H4.5V13.5", "M19.5 4.5L4.5 19.5"),
    "sneltoetsen": l("toetsenbord"),
    "sluit-document": lambda r: Stuk(_doc_rand() + _p("M9.5 12.5L14.5 17.5M14.5 12.5L9.5 17.5")),
    "spring": p("M4.5 18.5C4.5 12 8.5 8 15 8H19.5", "M16 4.5L19.5 8L16 11.5"),
    "dubbel-links": p("M11.5 6L5.5 12L11.5 18", "M18.5 6L12.5 12L18.5 18"),
    "dubbel-rechts": p("M12.5 6L18.5 12L12.5 18", "M5.5 6L11.5 12L5.5 18"),
}


def knop(naam: str) -> callable:
    return KNOPPEN[naam]


# ================================================================ namen ===

def op22(tekst: str, boven: int = 1) -> str:
    """De 24-tekening voor precies 22 px: een viewBox van 22 eenheden, 1 eenheid = 1 pixel.

    Lijnen op hele eenheden vallen zo op hele pixels (scherp); verkleind naar 22 worden
    ze 1,83 px breed en wazig. Wat buiten 1..23 komt, valt weg; boven = 2 schuift het
    venster een eenheid omlaag voor tekeningen die tot 23,5 reiken (de bel)."""
    oud = 'width="24" height="24" viewBox="0 0 24 24"'
    if oud not in tekst:
        raise ValueError("op22 verwacht een 24-tekening")
    return tekst.replace(oud, f'width="22" height="22" viewBox="1 {boven} 22 22"', 1)


def _maak_beide(b: basis.Bouwer, soort: str, namen, teken, *, eigen16: bool = False, symbolic: bool = True,
                boven22: int = 1) -> None:
    """Schrijf teken(r) als <soort>/scalable, <soort>/22 en <soort>/16 onder alle namen."""
    if isinstance(namen, str):
        namen = [namen]
    groot = svg(teken(GROOT), GROOT)
    midden = op22(groot, boven22)
    r16 = KLEIN16 if eigen16 else KLEIN24
    klein = svg(teken(r16), r16)
    for naam in namen:
        b.schrijf(f"{soort}/scalable", naam, groot, symbolic_ook=symbolic)
        b.schrijf(f"{soort}/22", naam, midden, symbolic_ook=symbolic)
        b.schrijf(f"{soort}/16", naam, klein, symbolic_ook=symbolic)


def _geluid(b: basis.Bouwer) -> None:
    S = "status"
    _maak_beide(b, S, ["audio-volume-muted", "audio-off"], lambda r: geluid(r, stil=True), eigen16=True)
    _maak_beide(b, S, "audio-volume-low", lambda r: geluid(r, 1), eigen16=True)
    _maak_beide(b, S, "audio-volume-medium", lambda r: geluid(r, 2), eigen16=True)
    _maak_beide(b, S, ["audio-volume-high", "audio-on"], lambda r: geluid(r, 3), eigen16=True)
    _maak_beide(b, S, ["audio-volume-high-warning", "audio-volume-overamplified"],
                lambda r: geluid(r, 3, buitenste="ColorScheme-NeutralText"), eigen16=True)
    _maak_beide(b, S, "audio-volume-high-danger", lambda r: geluid(r, 3, buitenste="ColorScheme-NegativeText"), eigen16=True)
    _maak_beide(b, S, "audio-ready", lambda r: geluid(r, golven=0), eigen16=True)
    # microfoon: gevoeligheid = hoe vol het kopje is
    _maak_beide(b, S, ["microphone-sensitivity-muted", "audio-input-microphone-muted", "microphone-disabled"],
                lambda r: uit(microfoon(r), r), eigen16=True)
    _maak_beide(b, S, ["microphone-sensitivity-low", "audio-input-microphone-low"], lambda r: microfoon(r, 1), eigen16=True)
    _maak_beide(b, S, ["microphone-sensitivity-medium", "audio-input-microphone-medium"], lambda r: microfoon(r, 2), eigen16=True)
    _maak_beide(b, S, ["microphone-sensitivity-high", "audio-input-microphone-high"], lambda r: microfoon(r, 3), eigen16=True)
    _maak_beide(b, S, "audio-input-microphone", lambda r: microfoon(r), eigen16=True)


def _netwerk(b: basis.Bouwer) -> None:
    S = "status"
    for pct in NIVEAUS:
        n = _niveau(pct)
        _maak_beide(b, S, f"network-wireless-{pct}", lambda r, n=n: wifi(r, n))
        _maak_beide(b, S, f"network-wireless-{pct}-locked", lambda r, n=n: met_slot(wifi(r, n), r))
        _maak_beide(b, S, f"network-wireless-{pct}-limited", lambda r, n=n: met_let_op(wifi(r, n), r))
    for pct in (0, 20, 25, 40, 50, 60, 75, 80, 100):
        n = _niveau(pct)
        _maak_beide(b, S, f"network-wireless-connected-{pct:02d}", lambda r, n=n: wifi(r, n))
    for naam, pct in (("none", 0), ("weak", 20), ("ok", 40), ("good", 60), ("excellent", 100)):
        n = _niveau(pct)
        _maak_beide(b, S, f"network-wireless-signal-{naam}", lambda r, n=n: wifi(r, n))
    _maak_beide(b, S, ["network-wireless", "network-wireless-on", "network-wireless-connected"], lambda r: wifi(r))
    _maak_beide(b, S, ["network-wireless-off", "network-wireless-disabled"], lambda r: uit(wifi(r), r))
    _maak_beide(b, S, "network-wireless-disconnected", lambda r: met_kruis(wifi(r, 0), r))
    _maak_beide(b, S, ["network-wireless-available", "network-wireless-no-route"], lambda r: wifi(r, 0))
    _maak_beide(b, S, "network-wireless-acquiring", lambda r: met_klok(wifi(r, 0), r))
    _maak_beide(b, S, "network-wireless-hotspot", hotspot)
    # kabel
    _maak_beide(b, S, ["network-wired", "network-wired-available"], lambda r: kabel(r))
    _maak_beide(b, S, "network-wired-activated", lambda r: kabel(r, True))
    _maak_beide(b, S, "network-wired-activated-limited", lambda r: met_let_op(kabel(r, True), r))
    _maak_beide(b, S, "network-wired-activated-locked", lambda r: met_slot(kabel(r, True), r))
    _maak_beide(b, S, "network-wired-acquiring", lambda r: met_klok(kabel(r), r))
    _maak_beide(b, S, ["network-wired-disconnected", "network-wired-unavailable", "network-wired-no-route"],
                lambda r: met_kruis(kabel(r), r))
    # geen netwerk / geen internet: de wereldbol
    _maak_beide(b, S, ["network-offline", "network-unavailable", "network-error"], lambda r: met_kruis(lijn("wereld"), r))
    _maak_beide(b, S, "network-limited", lambda r: met_let_op(lijn("wereld"), r))
    _maak_beide(b, S, "network-vpn", schild)
    # mobiel
    for pct in NIVEAUS:
        n = _niveau(pct)
        _maak_beide(b, S, f"network-mobile-{pct}", lambda r, n=n: mobiel(r, n), eigen16=True)
        _maak_beide(b, S, f"network-mobile-{pct}-locked", lambda r, n=n: met_slot(mobiel(r, n), r), eigen16=True)
    _maak_beide(b, S, "network-mobile-on", lambda r: mobiel(r), eigen16=True)
    _maak_beide(b, S, "network-mobile-available", lambda r: mobiel(r, 0), eigen16=True)
    _maak_beide(b, S, "network-mobile-off", lambda r: uit(mobiel(r), r), eigen16=True)
    # vliegtuigstand (KDE en GNOME-namen)
    _maak_beide(b, S, ["network-flightmode-on", "airplane-mode"], vliegtuig)
    _maak_beide(b, S, ["network-flightmode-off", "airplane-mode-disabled"], lambda r: uit(vliegtuig(r), r))
    # bluetooth
    _maak_beide(b, S, ["network-bluetooth", "bluetooth", "bluetooth-active"], lambda r: bluetooth(r))
    _maak_beide(b, S, ["network-bluetooth-activated", "network-wireless-bluetooth", "bluetooth-paired"],
                lambda r: bluetooth(r, True))
    _maak_beide(b, S, "network-bluetooth-activated-locked", lambda r: met_slot(bluetooth(r, True), r))
    _maak_beide(b, S, ["network-bluetooth-inactive", "bluetooth-disabled"], lambda r: uit(bluetooth(r), r))


def _batterij(b: basis.Bouwer) -> None:
    S = "status"
    for pct in range(0, 101, 10):
        for laden in (False, True):
            naam = f"battery-{pct:03d}" + ("-charging" if laden else "")
            namen = [naam] + [f"{naam}-profile-{p}" for p in ("powersave", "balanced", "performance")]
            _maak_beide(b, S, namen, lambda r, pct=pct, laden=laden: batterij(r, pct, laden), eigen16=True)
            # GNOME-namen (alleen -symbolic)
            g = f"battery-level-{pct}" + ("-charging" if laden else "") + "-symbolic"
            _maak_beide(b, S, g, lambda r, pct=pct, laden=laden: batterij(r, pct, laden), eigen16=True, symbolic=False)
    for naam, pct in (("full", 100), ("good", 60), ("low", 20), ("caution", 10), ("empty", 0)):
        _maak_beide(b, S, f"battery-{naam}", lambda r, pct=pct: batterij(r, pct), eigen16=True)
        _maak_beide(b, S, f"battery-{naam}-charging", lambda r, pct=pct: batterij(r, pct, True), eigen16=True)
    _maak_beide(b, S, ["battery-full-charged", "battery-level-100-charged"], lambda r: batterij(r, 100, True), eigen16=True)
    _maak_beide(b, S, "battery-charging", lambda r: batterij(r, None, True), eigen16=True)
    kruisje = {16: _p("M5.5 6.5L8.5 9.5M8.5 6.5L5.5 9.5"), 24: _p("M8.5 9.5L13.5 14.5M13.5 9.5L8.5 14.5")}
    _maak_beide(b, S, "battery-missing", lambda r: batterij(r, None, leeg_teken=kruisje[r.raster]), eigen16=True)
    _maak_beide(b, S, "battery", l("batterij"))
    _maak_beide(b, S, "battery-ups", ups)
    _maak_beide(b, S, ["battery-profile-powersave", "power-profile-power-saver"], blad)
    _maak_beide(b, S, ["battery-profile-balanced", "power-profile-balanced"], lambda r: meter(r))
    _maak_beide(b, S, ["battery-profile-performance", "power-profile-performance"],
                lambda r: meter(r, "M12 13L17.4 11.2"))


def _scherm_en_meldingen(b: basis.Bouwer) -> None:
    S = "status"
    _maak_beide(b, S, ["brightness-high", "display-brightness", "display-brightness-high", "video-display-brightness",
                       "redshift-status-day"], l("zon"))
    _maak_beide(b, S, ["brightness-low", "display-brightness-low"], zon_zacht)
    _maak_beide(b, S, "input-keyboard-brightness", toetsenbordlicht)
    _maak_beide(b, S, ["redshift-status-on", "night-light"], l("maan"))
    _maak_beide(b, S, ["redshift-status-off", "night-light-disabled"], lambda r: uit(lijn("maan"), r))
    # meldingen (de bel reikt tot 23,5: op 22 px een eenheid hoger in beeld)
    _maak_beide(b, S, ["notification-inactive", "notifications", "notification-empty", "preferences-desktop-notification",
                       "preferences-desktop-notification-bell"], bel, boven22=2)
    _maak_beide(b, S, ["notification-active", "notification-new"], lambda r: met_punt(bel(r), r), boven22=2)
    _maak_beide(b, S, ["notifications-disabled", "notification-disabled"], lambda r: uit(bel(r), r), boven22=2)
    _maak_beide(b, S, ["notification-progress-inactive", "notification-progress-active"], ring)
    # toetsenbordlampjes, camera, temperatuur, klembord
    _maak_beide(b, S, ["input-caps-on", "input-combo-on"], hoofdletters)
    _maak_beide(b, S, "input-num-on", cijfers)
    _maak_beide(b, S, "camera-ready", lambda r: camera(r))
    _maak_beide(b, S, "camera-on", lambda r: camera(r, True))
    _maak_beide(b, S, ["camera-off", "camera-disabled"], lambda r: uit(camera(r), r))
    _maak_beide(b, S, "temperature-cold", lambda r: thermometer(r, 15))
    _maak_beide(b, S, "temperature-normal", lambda r: thermometer(r, 11.5))
    _maak_beide(b, S, "temperature-warm", lambda r: thermometer(r, 8))
    _maak_beide(b, S, "klipper-symbolic", l("plak"), symbolic=False)
    # vastgezette regels in het klembord (ster aan / uit)
    _maak_beide(b, S, "starred", lambda r: Stuk(LIJN["ster"].replace("<path ", '<path fill="currentColor" ')))
    _maak_beide(b, S, "non-starred", l("ster"))
    # berichten
    # (data-*: dezelfde berichten in Kirigami-dialogen, de schijvencontrole en het klembord)
    _maak_beide(b, S, ["dialog-information", "data-information"], lambda r: cirkel(_info()))
    _maak_beide(b, S, "dialog-question", lambda r: cirkel(_vraag()))
    _maak_beide(b, S, ["dialog-warning", "data-warning"], lambda r: gekleurd(Stuk(LIJN["uitroep"].replace(
        "M12 9.5v4.5M12 16.8v.3", "M12 9.5v4") + _stip(12, 16.6, 1.15)), "ColorScheme-NeutralText"))
    _maak_beide(b, S, ["dialog-error", "data-error"],
                lambda r: gekleurd(cirkel(_p("M9 9L15 15M15 9L9 15")), "ColorScheme-NegativeText"))
    _maak_beide(b, S, ["dialog-positive", "data-success"],
                lambda r: gekleurd(cirkel(_p("M8 12.5L10.8 15.2L16 9.5")), "ColorScheme-PositiveText"))
    _maak_beide(b, S, "dialog-password", sleutel)
    # media als toestand
    _maak_beide(b, S, "media-playback-playing", lambda r: media(r, "start"), eigen16=True)
    _maak_beide(b, S, "media-playback-paused", lambda r: media(r, "pause"), eigen16=True)
    _maak_beide(b, S, "media-playback-stopped", lambda r: media(r, "stop"), eigen16=True)
    # slaapstand tegengehouden of niet
    _maak_beide(b, S, "system-suspend-inhibited", lambda r: uit(lijn("maan"), r))
    _maak_beide(b, S, "system-suspend-uninhibited", l("maan"))


# Knoppen: naam(en) -> teken uit KNOPPEN.
ACTIES: list[tuple[list[str], str]] = [
    (["go-previous", "go-previous-view", "pan-start"], "links"),
    (["go-next", "go-next-view", "pan-end"], "rechts"),
    (["go-up", "pan-up", "collapse"], "boven"),
    (["go-down", "pan-down", "expand"], "onder"),
    (["go-first", "go-first-view"], "eerste"), (["go-last", "go-last-view"], "laatste"),
    (["go-top"], "top"), (["go-bottom"], "bodem"), (["go-home"], "huis"),
    (["arrow-left"], "pijl-links"), (["arrow-right"], "pijl-rechts"), (["arrow-up"], "pijl-op"), (["arrow-down"], "pijl-neer"),
    (["window-close", "dialog-close", "tab-close"], "kruis"), (["window-minimize"], "streep"),
    (["window-maximize"], "vierkant"), (["window-restore"], "terugzetten"),
    (["window-new"], "nieuw-venster"), (["window-pin"], "speld"),
    (["edit-copy"], "kopieer"), (["edit-cut"], "knip"), (["edit-paste"], "plak"),
    (["edit-delete", "edit-delete-remove", "entry-delete"], "weg"),
    (["edit-find", "edit-find-replace", "search", "system-search"], "zoek"),
    (["edit-undo"], "ongedaan"), (["edit-redo"], "opnieuw"),
    (["edit-reset", "document-revert"], "herstel"),   # document-revert: de knop Standaard in elke KDE-instelling
    (["edit-rename"], "hernoem"), (["edit-entry", "entry-edit", "document-edit"], "potlood"),
    (["edit-select-all"], "alles"), (["edit-select-none"], "niets"),
    (["edit-clear"], "wis-veld"),
    (["edit-clear-locationbar-rtl"], "backspace"), (["edit-clear-locationbar-ltr"], "backspace-r"),
    (["edit-clear-all", "edit-clear-history"], "gum"),
    (["edit-none", "dialog-cancel"], "geen"),
    (["list-add"], "plus"), (["list-remove"], "min"),
    (["dialog-ok", "dialog-ok-apply", "dialog-apply", "object-select", "checkmark"], "vink"),
    (["view-refresh", "system-reboot"], "verversen"),
    (["view-more", "view-more-horizontal"], "meer-liggend"),
    (["overflow-menu", "overflow-menu-left", "overflow-menu-right"], "meer-staand"),
    (["application-menu", "open-menu", "show-menu"], "menu"),
    (["view-list-details"], "lijst"), (["view-list-icons", "view-grid"], "tegels"),
    (["view-list-text"], "tekstlijst"), (["view-list-tree"], "boom"),
    (["view-visible"], "oog"), (["view-filter"], "trechter"),
    (["view-sort-ascending", "view-sort"], "sorteer-op"), (["view-sort-descending"], "sorteer-neer"),
    (["view-barcode-qr"], "qr"), (["view-fullscreen", "zoom-fit-best"], "groot"), (["view-restore"], "klein"),
    (["view-history", "document-open-recent"], "geschiedenis"),
    (["zoom-in"], "inzoomen"), (["zoom-out"], "uitzoomen"), (["zoom-original"], "zoek"),
    (["document-open", "document-open-folder"], "open"), (["document-save", "document-save-as"], "bewaar"),
    (["document-new"], "nieuw"), (["document-properties"], "document"), (["document-send"], "versturen"),
    (["document-share"], "delen"), (["document-print"], "printer"),
    (["process-stop"], "stop"),
    (["help-contents", "help-contextual", "help-faq"], "vraag"), (["help-about", "help-hint"], "info"),
    (["configure", "settings-configure"], "tandwiel"),
    (["media-eject"], "uitwerpen"), (["media-album-cover"], "muziek"),
    (["system-shutdown"], "aan"), (["system-log-out", "application-exit"], "deur"),
    (["system-suspend"], "maan"), (["system-lock-screen"], "slot"),
    (["contrast"], "contrast"), (["speedometer"], "meter"),
    (["network-connect"], "schakel"),
    # gevraagd door KDE Instellingen, KDE-dialogen (KStandardGuiItem/KStandardAction) en het KWin-venstermenu
    (["document-import"], "importeer"), (["document-export"], "exporteer"), (["view-preview"], "voorbeeld"),
    (["window-keep-above"], "boven-houden"), (["window-keep-below"], "onder-houden"),
    (["transform-move"], "verplaats"), (["transform-scale"], "schaal"),
    (["configure-shortcuts"], "sneltoetsen"), (["document-close"], "sluit-document"), (["go-jump"], "spring"),
    (["arrow-left-double"], "dubbel-links"), (["arrow-right-double"], "dubbel-rechts"),
]


def _knoppen(b: basis.Bouwer) -> None:
    A = "actions"
    for namen, teken in ACTIES:
        _maak_beide(b, A, namen, knop(teken))
    _maak_beide(b, A, ["view-hidden", "view-visible-off"], lambda r: uit(lijn("oog"), r))
    _maak_beide(b, A, "window-unpin", lambda r: uit(knop("speld")(r), r))
    _maak_beide(b, A, "network-disconnect", lambda r: uit(schakel(r), r))
    _maak_beide(b, A, ["system-suspend-hibernate", "system-hibernate"], sneeuw)
    _maak_beide(b, A, "system-switch-user", twee_personen)
    _maak_beide(b, A, "system-reboot-update", lambda r: met_punt(knop("verversen")(r), r))
    _maak_beide(b, A, "system-shutdown-update", lambda r: met_punt(lijn("aan"), r))
    # media
    for namen, wat in ((["media-playback-start"], "start"), (["media-playback-pause"], "pause"),
                       (["media-playback-stop"], "stop"), (["media-skip-forward"], "volgende"),
                       (["media-skip-backward"], "vorige"), (["media-seek-forward"], "vooruit"),
                       (["media-seek-backward"], "terug"), (["media-record"], "opnemen")):
        _maak_beide(b, A, namen, lambda r, wat=wat: media(r, wat), eigen16=True)
    _maak_beide(b, A, "media-playlist-repeat", lambda r: herhaal(r))
    _maak_beide(b, A, "media-playlist-repeat-song", lambda r: herhaal(r, True))
    _maak_beide(b, A, "media-playlist-shuffle", door_elkaar)


# ---- emblemen: een gekleurde stip met een uitgespaard teken (16-raster) ----

EMBLEEM = R(16, 2, 16)


def _embleem(klasse: str, gat: str) -> str:
    stuk = Stuk(f'<circle cx="8" cy="8" r="7"{_vol(klasse)}/>').snij(gat)
    return svg(stuk, EMBLEEM)


def _emblemen(b: basis.Bouwer) -> None:
    E = "emblems/scalable"
    G = "ColorScheme-PositiveText"
    N = "ColorScheme-NegativeText"
    T = "ColorScheme-Text"

    def lijn16(d: str, w: float = 2) -> str:
        return _gat_lijn(d, w)
    vink = lijn16("M4.75 8.25L7 10.5L11.25 6")
    kruis = lijn16("M5.5 5.5L10.5 10.5M10.5 5.5L5.5 10.5")
    uitroep = lijn16("M8 4.25V8.25") + _gat_rond(8, 11.1, 1.15)
    info = lijn16("M8 7.25V11.25") + _gat_rond(8, 4.75, 1.15)
    vraag = lijn16("M6 6.2A2 2 0 1 1 8.8 8C8.3 8.3 8 8.7 8 9.3V9.4", 1.7) + _gat_rond(8, 11.5, 1)
    plus = lijn16("M8 4.5V11.5M4.5 8H11.5")
    min_ = lijn16("M4.5 8H11.5")
    pauze = lijn16("M6.25 5V11M9.75 5V11")
    slot = ('<rect x="5" y="7.5" width="6" height="4.5" rx="1" fill="#000"/>' +
            lijn16("M6.25 7.5V6.25A1.75 1.75 0 0 1 9.75 6.25V7.5", 1.5))
    open_slot = ('<rect x="5" y="7.5" width="6" height="4.5" rx="1" fill="#000"/>' +
                 lijn16("M6.25 7.5V5.75A1.75 1.75 0 0 1 9.75 5.75", 1.5))
    koppeling = lijn16("M5 11V9.5A2.5 2.5 0 0 1 7.5 7H11M9 5L11 7L9 9", 1.7)
    streep = lijn16("M4.75 4.75L11.25 11.25")
    persoon = _gat_rond(8, 6, 2) + lijn16("M4.6 12A3.4 3.4 0 0 1 11.4 12", 1.7)
    eject = '<path d="M8 4.25L11.25 8.25H4.75Z" fill="#000"/>' + lijn16("M4.75 11H11.25", 1.7)

    for namen, klasse, gat in (
            (["emblem-ok", "emblem-success", "emblem-checked", "emblem-mounted"], G, vink),
            (["emblem-added", "emblem-new"], G, plus),
            (["emblem-error", "emblem-unreadable"], N, kruis),
            (["emblem-important"], N, uitroep),
            (["emblem-remove"], N, min_),
            (["emblem-information"], T, info), (["emblem-question"], T, vraag),
            (["emblem-pause"], T, pauze),
            (["emblem-locked", "emblem-readonly", "emblem-encrypted-locked"], T, slot),
            (["emblem-unlocked", "emblem-encrypted-unlocked"], T, open_slot),
            (["emblem-symbolic-link"], T, koppeling), (["emblem-unavailable"], T, streep),
            (["emblem-shared"], T, persoon), (["emblem-unmounted"], T, eject)):
        bestand = _embleem(klasse, gat)
        for naam in namen:
            b.schrijf(E, naam, bestand)
    # waarschuwing: oranje driehoek
    driehoek = Stuk('<path d="M8 1.5L15 14H1Z" class="ColorScheme-NeutralText" fill="currentColor" '
                    'stroke="currentColor" stroke-width="1.5"/>').snij(lijn16("M8 6V9.25") + _gat_rond(8, 11.75, 1.1))
    b.schrijf(E, "emblem-warning", svg(driehoek, EMBLEEM))
    # favoriet: gevulde ster (de warme waarschuwingskleur: goud in donker)
    ster = LIJN["ster"].replace("<path ", '<path class="ColorScheme-NeutralText" fill="currentColor" stroke="currentColor" ')
    b.schrijf(E, "emblem-favorite", svg(Stuk(ster), GROOT))
    # -symbolic emblemen zijn bij Breeze gewone lijntekens (ook als pictogram in KDE Instellingen)
    for naam, teken in (("emblem-music-symbolic", "muziek"), ("emblem-photos-symbolic", "foto"),
                        ("emblem-videos-symbolic", "film"), ("emblem-documents-symbolic", "document"),
                        ("emblem-ok-symbolic", "vink"), ("emblem-default-symbolic", "vink"),
                        ("emblem-important-symbolic", "uitroep"), ("emblem-favorite-symbolic", "ster"),
                        ("emblem-synchronizing-symbolic", "verversen")):
        b.schrijf(E, naam, svg(lijn(teken), GROOT))
    b.schrijf(E, "emblem-system-symbolic", svg(tandwiel(GROOT), GROOT))
    b.schrijf(E, "emblem-shared-symbolic", svg(knop("delen")(GROOT), GROOT))


def maak(b: basis.Bouwer) -> None:
    _geluid(b)
    _netwerk(b)
    _batterij(b)
    _scherm_en_meldingen(b)
    _knoppen(b)
    _emblemen(b)
