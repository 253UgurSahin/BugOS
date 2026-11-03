#!/usr/bin/env python3
"""Bouw website/index.html uit tools/website/pagina.html.

Vult de plekken in met het echte BugOS-logo (zodat de website altijd hetzelfde
beestje laat zien als BugOS zelf):
  {{MERK:naam}}  -> het beestje; het kopje volgt licht/donker (CSS-variabelen)
  {{OPBOUW}}     -> de opbouwtekening van het logo met hulplijnen en nummers
Gebruik: python3 tools/website/bouw.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
ROOT = HIER.parent.parent
sys.path.insert(0, str(ROOT / "tools" / "merk"))
from merk import CX, CY, HR, HX, HY, R, RAND, STIPPEN, merkteken  # noqa: E402


def merk_variabel(uid: str) -> str:
    """Het merkteken waarvan de kop en de kopvlekjes CSS-variabelen volgen."""
    m = merkteken(uid)
    m = m.replace(f'fill="#16171C" mask="url(#{uid}-kop)"', f'style="fill:var(--merk-kop)" mask="url(#{uid}-kop)"', 1)
    m = m.replace(f'<g fill="#FFFFFF" mask="url(#{uid}-kop)">', f'<g style="fill:var(--merk-oog)" mask="url(#{uid}-kop)">', 1)
    assert "var(--merk-kop)" in m and "var(--merk-oog)" in m
    return m


def merk_svg(uid: str) -> str:
    if uid == "winmerk":  # Windows-titelbalk is altijd licht
        return f'<svg class="m" viewBox="0 0 256 256" aria-hidden="true">{merkteken(uid)}</svg>'
    return f'<svg viewBox="0 0 256 256" aria-hidden="true">{merk_variabel(uid)}</svg>'


def opbouw() -> str:
    """Opbouwtekening: het beestje met de cirkels waarmee het getekend is."""
    hulp = (
        f'<g class="hulp" fill="none" stroke="currentColor" stroke-width=".7">'
        f'<circle cx="{CX}" cy="{CY}" r="{R}" stroke-dasharray="3 3"/>'
        f'<circle cx="{CX}" cy="{CY}" r="{R + RAND}" stroke-dasharray="1 3"/>'
        f'<circle cx="{HX}" cy="{HY}" r="{HR}" stroke-dasharray="3 3"/>'
        f'<path d="M{CX} -18V270" stroke-dasharray="2 4"/>'
        f'<path d="M-28 {CY}H284M60 {HY}H196" stroke-dasharray="1 4"/>'
        f'<path d="M{CX - 5} {CY}h10M{CX} {CY - 5}v10M{HX - 5} {HY}h10M{HX} {HY - 5}v10"/>'
    )
    for x, y, r in STIPPEN:  # hulpcirkels om de stippen
        for sx in (x, 256 - x):
            hulp += f'<circle cx="{sx}" cy="{y}" r="{r + 5}" stroke-dasharray="1 2.5"/>'
    hulp += "</g>"
    maten = (
        '<g class="hulp" fill="currentColor" font-family="JetBrains Mono, monospace" font-size="7.5">'
        f'<text x="{CX + R + 10}" y="{CY - 4}">r 94</text>'
        f'<text x="{HX + HR + 6}" y="{HY - 3}">r 44</text>'
        '</g>'
    )

    def merker(n: int, x: float, y: float, x1: float, y1: float, x2: float, y2: float) -> str:
        return (f'<path d="M{x1} {y1}L{x2} {y2}" stroke="var(--rood)" stroke-width="1" fill="none"/>'
                f'<circle cx="{x}" cy="{y}" r="9.5" fill="var(--rood)"/>'
                f'<text x="{x}" y="{y + 3.4}" text-anchor="middle" font-family="JetBrains Mono, monospace" '
                f'font-size="10" font-weight="600" fill="#fff">{n}</text>')

    merkers = (merker(1, 240, 236, 204, 209, 232, 230)
               + merker(2, 12, 80, 77, 108, 20, 85)
               + merker(3, 210, 0, 160, 28, 202, 5))
    label = ("Opbouwtekening van het BugOS-logo: twee vleugels (1), vier stippen (2) en een kop met twee "
             "witte vlekjes (3), getekend met cirkels en één rechte lijn.")
    return (f'<svg class="tekening" viewBox="-36 -26 328 312" role="img" aria-label="{label}">'
            f'{merk_variabel("opbouw")}{hulp}{maten}{merkers}</svg>')


def main() -> int:
    bron = (HIER / "pagina.html").read_text(encoding="utf-8")
    uit = re.sub(r"\{\{MERK:([a-z]+)\}\}", lambda m: merk_svg(m.group(1)), bron)
    uit = uit.replace("{{OPBOUW}}", opbouw())
    assert "{{" not in uit, "er staat nog een lege plek in de pagina"
    (ROOT / "website" / "index.html").write_text(uit, encoding="utf-8")
    print("website/index.html gebouwd")
    return 0


if __name__ == "__main__":
    sys.exit(main())
