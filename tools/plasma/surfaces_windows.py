"""Vensterachtergronden voor surfaces.py: pop-ups, taakbalk, tooltips, kaarten en de kop van een pop-up."""

from __future__ import annotations

from dataclasses import dataclass

from surfaces_frames import kader, marges, masker_kader, schaduw_inhoud, schaduw_kader, vlak
from surfaces_shapes import (A_DOORZICHTIG, A_RAND, I_POPUP, M_BALK, M_BALK_DIK, M_KAART, M_POPUP, M_TIP, NEGEN,
                             NUL, R_BALK, R_KAART, R_POPUP, R_TIP, RR, S_BALK, S_DOORZICHTIG, S_KAART, S_POPUP,
                             S_TIP, Blad, Laag, Schaduw, pad, verf)


# --------------------------------------------------------- vensterachtergronden ---

@dataclass(frozen=True)
class Venster:
    """Een vensterachtergrond: pop-up, taakbalk of tooltip."""
    r: float
    marge: tuple[float, float, float, float]   # boven, rechts, onder, links
    schaduw: Schaduw
    inzet: float = NUL                         # hint-*-inset (zie I_POPUP)


POPUP = Venster(R_POPUP, (M_POPUP,) * 4, S_POPUP, inzet=I_POPUP)
BALK = Venster(R_BALK, (M_BALK,) * 4, S_BALK)
TIP = Venster(R_TIP, (M_TIP,) * 4, S_TIP)
KAART_VENSTER = Venster(R_KAART, (M_KAART,) * 4, S_POPUP)


def vensterachtergrond(titel: str, v: Venster, *, alfa: float, schaduw: bool = True, dik: bool = False,
                       inset: bool = True, basis: bool = False, prive_schaduw: bool = False) -> Blad:
    """dialogs/background, widgets/panel-background en widgets/tooltip (en hun varianten)."""
    blad = Blad(titel)
    blad.hint("hint-tile-center", 0, 0, 5, 5, "#ff6600")
    if prive_schaduw:
        blad.hint("private-hint-use-shadow", 6, 0, 5, 5, "#ff6600")
    oy = 10
    if basis:
        blad.voeg('  <g id="base">')
        blad.ids.add("base")
    W, H = kader(blad, "", 2, oy, v.r, v.r, v.r, v.r, vlak(v.r, alfa))
    if basis:
        blad.voeg("  </g>")
    b, rr, o, l = v.marge
    marges(blad, "", 2, oy, W, H, b, rr, o, l)
    if inset:
        # de schaduw valt buiten het venster (KWin tekent hem); de inspringing zegt alleen
        # hoe ver ingeklapte inhoud van de rand blijft (pop-ups: I_POPUP, de rest 0)
        i = v.inzet
        marges(blad, "", 2, oy, W, H, i, i, i, i, soort="inset", kleur="#00ff00")
    if dik:
        # "thick": de marges rechts van de margescheiding (systeemvak, klok)
        blad.groep("thick-center", [], (2 + v.r, oy + H + 10, 2 + v.r + 32, oy + H + 42))
        tx, ty = 2, oy + H + 6
        blad.hint("thick-hint-top-margin", tx + W / 2 + 4, ty, 2, M_BALK_DIK, "#800080")
        blad.hint("thick-hint-bottom-margin", tx + W / 2 + 4, ty + 40, 2, M_BALK_DIK, "#800080")
        blad.hint("thick-hint-left-margin", tx, ty + 20, M_BALK_DIK, 2, "#800080")
        blad.hint("thick-hint-right-margin", tx + W - M_BALK_DIK, ty + 20, M_BALK_DIK, 2, "#800080")
    mx = 2 + W + 12
    masker_kader(blad, "", mx, oy, v.r)
    if schaduw:
        schaduw_kader(blad, mx + W + 12, 0, v.r, v.schaduw)
    return blad


# ----------------------------------------------------- widgets op het bureaublad ---

def kaart_lagen(ins: float, r: float, alfa: float, rand: bool = True):
    """Een kaart, ingesprongen voor de schaduw binnen het kader (zie kaart_schaduw)."""
    def lagen(W, H):
        vorm = RR(ins, ins, W - ins, H - ins, r)
        uit = [Laag(vorm, "Background", alfa)]
        if rand:
            uit.append(Laag(vorm, "Text", A_RAND, ring=1))
        return uit
    return lagen


def kaart_schaduw(blad: Blad, voor: str, ox: float, oy: float, ins: float, r: float, sch: Schaduw,
                  cw: float = 32, ch: float = 32) -> dict:
    """extra-functies voor kader(): de schaduw in de randtegels, onder de kaart."""
    L = ins + r
    W, H = 2 * L + cw, 2 * L + ch
    venster = RR(ox + ins, oy + ins, ox + W - ins, oy + H - ins, r)
    kol = [(0, L), (L, L + cw), (L + cw, W)]
    rij = [(0, L), (L, L + ch), (L + ch, H)]
    tegels = {NEGEN[j][i]: (ox + kol[i][0], oy + rij[j][0], ox + kol[i][1], oy + rij[j][1])
              for j in range(3) for i in range(3)}
    inhoud = schaduw_inhoud(blad, venster, tegels, sch, voor)
    return {naam: (lambda _t, s=inhoud[naam]: s) for naam in inhoud}


def widgets_background(titel: str, *, vervaagd: bool) -> Blad:
    """widgets/background: kaart op het bureaublad (en Popup/Dialog/Drawer van PlasmaComponents)."""
    blad = Blad(titel)
    ins, r = 8, R_KAART
    L = ins + r
    m = ins + M_KAART
    blad.hint("hint-stretch-borders", 0, 0, 5, 5, "#ff6600")
    blad.voeg('  <g id="base">')
    blad.ids.add("base")
    oy = 8
    extra = kaart_schaduw(blad, "", 2, oy, ins, r, S_KAART)
    W, H = kader(blad, "", 2, oy, L, L, L, L, kaart_lagen(ins, r, 1.0), extra=extra)
    blad.voeg("  </g>")
    # oud element van Breeze: alleen het midden
    blad.groep("toolbutton-pressed-center", [f'<path d="{pad(2 + L, oy + H + 8, 2 + L + 32, oy + H + 40)}" '
                                             f'{verf("Background")}/>'], (2 + L, oy + H + 8, 2 + L + 32, oy + H + 40))
    marges(blad, "", 2, oy, W, H, m, m, m, m)
    marges(blad, "", 2, oy, W, H, ins, ins, ins, ins, soort="inset", kleur="#00ff00")
    # shadow-*: alleen de schaduw, als kader
    sx = 2 + W + 12
    extra = kaart_schaduw(blad, "shadow-", sx, oy, ins, r, S_KAART)
    kader(blad, "shadow-", sx, oy, L, L, L, L, lambda W_, H_: [], extra=extra)
    marges(blad, "shadow-", sx, oy, W, H, m, m, m, m)
    marges(blad, "shadow-", sx, oy, W, H, ins, ins, ins, ins, soort="inset", kleur="#00ff00")
    if vervaagd:
        # blurred-*: Plasma vervaagt de achtergrond zelf (blurred-mask) en legt dit erover
        by = oy + H + 50
        extra = kaart_schaduw(blad, "blurred-", 2, by, ins, r, S_KAART)
        kader(blad, "blurred-", 2, by, L, L, L, L, kaart_lagen(ins, r, A_DOORZICHTIG - 0.03),
              extra=extra)
        marges(blad, "blurred-", 2, by, W, H, m, m, m, m)
        marges(blad, "blurred-", 2, by, W, H, ins, ins, ins, ins, soort="inset", kleur="#00ff00")
        kader(blad, "blurred-mask-", sx, by, L, L, L, L,
              lambda W_, H_: [Laag(RR(ins, ins, W_ - ins, H_ - ins, r), None)])
    return blad


def translucentbackground() -> Blad:
    """widgets/translucentbackground: een doorschijnende kaart (applets die daarom vragen)."""
    blad = Blad("doorschijnende kaart")
    r = R_KAART
    blad.hint("hint-tile-center", 0, 0, 5, 5, "#ff6600")
    blad.voeg('  <g id="base">')
    blad.ids.add("base")
    oy = 10
    W, H = kader(blad, "", 2, oy, r, r, r, r, vlak(r, 0.80))
    blad.voeg("  </g>")
    marges(blad, "", 2, oy, W, H, M_KAART, M_KAART, M_KAART, M_KAART)
    marges(blad, "", 2, oy, W, H, NUL, NUL, NUL, NUL, soort="inset", kleur="#00ff00")
    schaduw_kader(blad, 2 + W + 12, 0, r, S_DOORZICHTIG, breeze_namen=False)
    return blad


# ------------------------------------------------------------ kop van een pop-up ---

def plasmoidheading() -> Blad:
    """widgets/plasmoidheading: geen aparte balk, alleen een haarlijn tussen kop en inhoud."""
    blad = Blad("kop en voet van een pop-up")
    blad.hint("hint-stretch-borders", 0, 0, 5, 5, "#ff6600")
    zij, dik = 12, 12

    def kop(W, H):  # lijn onderaan, alleen tussen de hoeken: springt 12 px in, net als de inhoud
        return [Laag(RR(zij, H - 1, W - zij, H, 0), "Text", A_RAND)]

    def voet(W, H):
        return [Laag(RR(zij, 0, W - zij, 1, 0), "Text", A_RAND)]

    W, H = kader(blad, "header-", 2, 8, zij, dik, zij, 1, kop)
    kader(blad, "footer-", 2 + W + 12, 8, zij, 1, zij, dik, voet)
    # Breeze heeft ook kale hint-*-margin (voor het voorvoegsel ""): zelfde maat als de kop
    marges(blad, "", 2, 8, W, H, 8, 8, 8, 8)
    return blad
