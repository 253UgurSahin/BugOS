#!/usr/bin/env python3
"""Maak alle BugOS-logobestanden opnieuw aan.

Gebruik:  python3 tools/merk/maak.py
Schrijft naar branding/logo/ en zet het systeempictogram klaar voor BugOS zelf.
Het woordmerk wordt omgezet naar lijnen (paden), zodat er geen lettertype nodig is.
"""

from __future__ import annotations

import sys
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))
from merk import INKT, merkteken, svg, tegel  # noqa: E402

ROOT = HIER.parent.parent
LOGO = ROOT / "branding" / "logo"
LETTER = ROOT / "branding" / "lettertypes" / "FunnelDisplay[wght].ttf"
SYSTEEM_ICOON = ROOT / "system_files" / "usr" / "share" / "bugos" / "logo.svg"

GEWICHT = 650
SPATIERING = -0.03  # em, iets strakker dan normaal


def woordmerk_pad(tekst: str = "BugOS", grootte: float = 100.0) -> tuple[str, float, float, float]:
    """Geeft (svg-pad, breedte, hoofdletterhoogte, onderkant) voor het woordmerk."""
    font = TTFont(LETTER)
    font = instancer.instantiateVariableFont(font, {"wght": GEWICHT})
    upm = font["head"].unitsPerEm
    schaal = grootte / upm
    glyphs = font.getGlyphSet()
    cap = getattr(font["OS/2"], "sCapHeight", 0) or int(upm * 0.7)
    desc = -font["hhea"].descent

    blob = hb.Blob.from_file_path(str(LETTER))
    face = hb.Face(blob)
    hbfont = hb.Font(face)
    hbfont.set_variations({"wght": GEWICHT})
    buf = hb.Buffer()
    buf.add_str(tekst)
    buf.guess_segment_properties()
    hb.shape(hbfont, buf, {"kern": True, "liga": True})
    namen = font.getGlyphOrder()

    pen = SVGPathPen(glyphs)
    x = 0.0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        naam = namen[info.codepoint]
        # lettertype-eenheden -> onze eenheden; y omdraaien (SVG gaat naar beneden)
        tp = TransformPen(pen, (schaal, 0, 0, -schaal, (x + pos.x_offset) * schaal, cap * schaal))
        glyphs[naam].draw(tp)
        x += pos.x_advance + SPATIERING * upm
    x -= SPATIERING * upm
    return pen.getCommands(), x * schaal, cap * schaal, (cap + desc) * schaal


def schrijf(naam: str, inhoud: str) -> None:
    pad = LOGO / naam
    pad.write_text(inhoud, encoding="utf-8")
    print(f"  {pad.relative_to(ROOT)}")


def main() -> int:
    LOGO.mkdir(parents=True, exist_ok=True)
    print("Merkteken:")
    schrijf("bugos-merk.svg", svg(merkteken("merk")))
    schrijf("bugos-merk-systeem.svg", svg(merkteken("merk", stijl="systeem"), stylesheet=True))
    schrijf("bugos-merk-inkt.svg", svg(merkteken("merk", stijl="mono", mono=INKT)))
    schrijf("bugos-merk-wit.svg", svg(merkteken("merk", stijl="mono", mono="#FFFFFF")))
    schrijf("bugos-merk-rood.svg", svg(merkteken("merk", stijl="mono", mono="#E52F3E")))
    print("App-icoon:")
    schrijf("bugos-icoon.svg", svg(tegel("icoon", "inkt")))
    schrijf("bugos-icoon-licht.svg", svg(tegel("icoon", "licht")))

    print("Woordmerk en logo:")
    pad, breedte, cap, onder = woordmerk_pad()
    schrijf("bugos-woordmerk.svg", svg(f'<path d="{pad}" fill="{INKT}"/>', breedte, onder, "BugOS"))
    schrijf("bugos-woordmerk-wit.svg", svg(f'<path d="{pad}" fill="#FFFFFF"/>', breedte, onder, "BugOS"))

    # Liggend logo: merkteken links, woordmerk rechts.
    mh = 256.0                     # hoogte merkteken
    tekst_schaal = (mh * 0.56) / cap   # hoofdletters ~56% van het merkteken
    tussen = mh * 0.22
    tw = breedte * tekst_schaal
    # midden van de hoofdletters op het midden van het schild (y=146)
    ty = 146 - (cap * tekst_schaal) / 2
    totaal_b = mh + tussen + tw
    totaal_h = max(256.0, ty + onder * tekst_schaal + 2)  # ruimte voor de staart van de g
    for kleur, achtervoegsel in ((INKT, ""), ("#FFFFFF", "-wit")):
        binnen = (merkteken(f"logo{achtervoegsel}") +
                  f'<path d="{pad}" fill="{kleur}" transform="translate({mh + tussen:.2f} {ty:.2f}) scale({tekst_schaal:.5f})"/>')
        schrijf(f"bugos-logo{achtervoegsel}.svg", svg(binnen, round(totaal_b, 2), round(totaal_h, 2)))

    # Het systeempictogram dat in BugOS wordt geïnstalleerd (kleurt mee met het thema).
    SYSTEEM_ICOON.write_text(svg(merkteken("bugos", stijl="systeem"), stylesheet=True), encoding="utf-8")
    print(f"  {SYSTEEM_ICOON.relative_to(ROOT)} (systeempictogram)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
