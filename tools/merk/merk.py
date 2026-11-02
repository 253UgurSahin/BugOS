"""Het BugOS-merkteken: een geometrisch lieveheersbeestje.

Opbouw (alles in een vlak van 256 x 256):
  - schild: cirkel (128,146) straal 94, in twee helften gesneden (spleet 7)
  - kop: cirkel (128,60) straal 44; rond het schild is een randje uitgespaard
  - kopvlekjes: twee witte vlekjes op de kop (zoals bij een echt
    lieveheersbeestje); ze lijken op vriendelijke oogjes
  - stippen: twee per vleugel, boven groot en onder iets kleiner

Dit bestand maakt alleen SVG-tekst. tools/merk/maak.py schrijft de bestanden.
"""

from __future__ import annotations

INKT = "#16171C"
KOP_DONKER = "#F4F2F2"  # kop op een donkere achtergrond (warm wit)
ROOD = {
    "l1": "#FF5C50",  # linkervleugel, boven
    "l2": "#E52F3E",  # linkervleugel, onder
    "r1": "#EE3F49",  # rechtervleugel, boven
    "r2": "#C41D3A",  # rechtervleugel, onder (iets donkerder: geeft diepte)
}

CX, CY, R = 128, 146, 94  # schild
HX, HY, HR = 128, 60, 44  # kop
SPLEET = 7
RAND = 6
STIPPEN = [(90, 120, 18), (88, 186, 14)]
VLEKJES = [(-23, -21, -28), (23, -21, 28)]  # (dx, dy, draaiing) t.o.v. kop


def _vlekje(dx: float, dy: float, hoek: float, extra: str = "") -> str:
    x, y = HX + dx, HY + dy
    return f'<ellipse cx="{x}" cy="{y}" rx="8.5" ry="6.5" transform="rotate({hoek} {x} {y})"{extra}/>'


def merkteken(uid: str = "bug", stijl: str = "kleur", mono: str | None = None) -> str:
    """De binnenkant van een SVG (zonder <svg>-tag).

    stijl:
      "kleur"     - rode vleugels, inktzwarte kop en stippen, witte kopvlekjes
      "systeem"   - zoals kleur, maar kop volgt de tekstkleur van het thema en
                    de kopvlekjes de achtergrondkleur (KDE kleurt dit vanzelf)
      "donker"    - voor een donkere achtergrond: lichte kop met inktkleurige
                    kopvlekjes (zoals "systeem" in een donker thema)
      "mono"      - alles in één kleur (mono=...), vlekjes en spleet uitgespaard
    """
    kleuren = dict(ROOD)
    if stijl == "mono":
        kleur = mono or INKT
        kleuren = {k: kleur for k in kleuren}
    stip_kleur = (mono or INKT) if stijl == "mono" else INKT

    if stijl == "systeem":
        kop_attr = 'class="ColorScheme-Text" fill="currentColor"'
        vlek_attr = 'class="ColorScheme-Background" fill="currentColor"'
    elif stijl == "donker":
        kop_attr = f'fill="{KOP_DONKER}"'
        vlek_attr = f'fill="{INKT}"'
    else:
        kop_attr = f'fill="{(mono or INKT) if stijl == "mono" else INKT}"'
        vlek_attr = 'fill="#FFFFFF"'

    stippen = "".join(
        f'<circle cx="{x}" cy="{y}" r="{r}"/><circle cx="{256 - x}" cy="{y}" r="{r}"/>' for x, y, r in STIPPEN)

    if stijl == "mono":
        uitsparing = "".join(_vlekje(dx, dy, h, ' fill="#000"') for dx, dy, h in VLEKJES)
        vlekjes = ""
    else:
        uitsparing = ""
        vlekjes = f'<g {vlek_attr} mask="url(#{uid}-kop)">' + "".join(_vlekje(*v) for v in VLEKJES) + "</g>"

    return f'''<defs>
<linearGradient id="{uid}-l" x1="0" y1="0" x2="0.7" y2="1"><stop offset="0" stop-color="{kleuren['l1']}"/><stop offset="1" stop-color="{kleuren['l2']}"/></linearGradient>
<linearGradient id="{uid}-r" x1="0.3" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{kleuren['r1']}"/><stop offset="1" stop-color="{kleuren['r2']}"/></linearGradient>
<mask id="{uid}-kop" maskUnits="userSpaceOnUse" x="0" y="0" width="256" height="256"><rect width="256" height="256" fill="#fff"/><circle cx="{CX}" cy="{CY}" r="{R + RAND}" fill="#000"/>{uitsparing}</mask>
<mask id="{uid}-schild" maskUnits="userSpaceOnUse" x="0" y="0" width="256" height="256"><rect width="256" height="256" fill="#fff"/><rect x="{CX - SPLEET / 2}" y="0" width="{SPLEET}" height="256" fill="#000"/></mask>
<clipPath id="{uid}-links"><rect x="0" y="0" width="{CX}" height="256"/></clipPath>
<clipPath id="{uid}-rechts"><rect x="{CX}" y="0" width="{256 - CX}" height="256"/></clipPath>
</defs>
<circle cx="{HX}" cy="{HY}" r="{HR}" {kop_attr} mask="url(#{uid}-kop)"/>{vlekjes}
<g mask="url(#{uid}-schild)">
<circle cx="{CX}" cy="{CY}" r="{R}" fill="url(#{uid}-l)" clip-path="url(#{uid}-links)"/>
<circle cx="{CX}" cy="{CY}" r="{R}" fill="url(#{uid}-r)" clip-path="url(#{uid}-rechts)"/>
<g fill="{stip_kleur}">{stippen}</g>
</g>'''


def tegel(uid: str = "tegel", soort: str = "inkt") -> str:
    """App-icoon: afgeronde tegel met het merkteken erin (binnenkant van een SVG)."""
    if soort == "inkt":
        achter = (f'<defs><linearGradient id="{uid}-bg" x1="0" y1="0" x2="0" y2="1">'
                  f'<stop offset="0" stop-color="#2B2D34"/><stop offset="1" stop-color="#121317"/></linearGradient></defs>'
                  f'<rect width="256" height="256" rx="60" fill="url(#{uid}-bg)"/>'
                  f'<rect x="1" y="1" width="254" height="254" rx="59" fill="none" stroke="#fff" stroke-opacity=".09" stroke-width="2"/>')
    else:
        achter = (f'<defs><linearGradient id="{uid}-bg" x1="0" y1="0" x2="0" y2="1">'
                  f'<stop offset="0" stop-color="#FFFFFF"/><stop offset="1" stop-color="#F2EFEF"/></linearGradient></defs>'
                  f'<rect width="256" height="256" rx="60" fill="url(#{uid}-bg)"/>'
                  f'<rect x="1" y="1" width="254" height="254" rx="59" fill="none" stroke="#16171C" stroke-opacity=".08" stroke-width="2"/>')
    return achter + f'<g transform="translate(40 34) scale(0.6875)">{merkteken(uid + "-m")}</g>'


def svg(binnen: str, breedte: float = 256, hoogte: float = 256, titel: str = "BugOS",
        px: int | None = None, stylesheet: bool = False) -> str:
    """Zet de binnenkant in een volledige SVG."""
    maat = f' width="{px}" height="{round(px * hoogte / breedte)}"' if px else ""
    stijl = ""
    if stylesheet:
        # KDE vervangt deze kleuren door die van het actieve thema.
        stijl = ('<style type="text/css" id="current-color-scheme">'
                 '.ColorScheme-Text { color:#16171C; } .ColorScheme-Background { color:#FFFFFF; }</style>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {breedte} {hoogte}"{maat}>'
            f'<title>{titel}</title>{stijl}{binnen}</svg>\n')
