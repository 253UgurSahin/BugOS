"""Tekenen voor status.py: raster (R), tekening in lagen (Stuk), svg(), bouwstenen en badges."""

from __future__ import annotations

import math

from base import LIJN, STIJLBLAD


VAAG = 0.35          # niet-gevulde niveaus (boogjes, golfjes, streepjes)
NIVEAUS = (0, 20, 40, 60, 80, 100)
ROOD = "ColorScheme-NegativeText"   # rode stip (melding, update, camera aan)


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
