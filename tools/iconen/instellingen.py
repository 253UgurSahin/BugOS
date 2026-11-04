"""KDE Instellingen en Info Center: eenkleurige BugOS-lijnpictogrammen.

Net als de zijbalk van BugOS Instellingen: één lijnicoon per onderwerp, in de
tekstkleur (KDE kleurt ColorScheme-Text mee met licht, donker en het gekozen
item). Hetzelfde onderwerp krijgt hetzelfde teken als in BugOS Instellingen:
wifi, bluetooth, printer, geluid, scherm, energie, uiterlijk, muis,
makkelijker zien, tijd, taal, inloggen, standaardprogramma's, updates en
'over deze computer'.

Namen: elke Icon= van de modules en categorieën van KDE Instellingen en van het
Info Center (ref/kcms.tsv, ref/systemsettings-categorieen.tsv,
/usr/share/kinfocenter/categories), behalve de namen van status.py,
plaatsen.py en apps.py. Elke naam komt ook als -symbolic, en met een eigen
16-pixelversie (lijn 1,5 op het 24-raster = 1 pixel).

Plus een paar langere namen die KDE echt vraagt (vergrendelscherm, systeemvak,
instellingen van het bureaublad, 'Tekst voorlezen'). KDE haalt bij een
onbekende naam eerst stukjes van achteren af BINNEN BugOS, en pas daarna kijkt
het in Breeze: zonder eigen tekening zou input-keyboard-virtual-show hier het
teken van input-keyboard-virtual krijgen (pijl omlaag, dus 'verbergen') en
preferences-desktop-filter het bureaublad.

Nieuwe tekens staan in EIGEN; ze volgen LIJN: raster 24, lijn 2, ronde
uiteinden, grote vormen tussen ongeveer 3 en 21, cirkels met straal 8,5.
"""

from __future__ import annotations

import math

import basis
from basis import klein, lijn, symbolisch


def _g(x: float) -> str:
    """Getal kort opschrijven (12.0 -> 12, 3.456 -> 3.46)."""
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return "0" if s == "-0" else s


def _tandwiel(cx: float = 12, cy: float = 12, r_top: float = 8.6, r_voet: float = 6.3, tanden: int = 8,
              top: float = 1.3, voet: float = 2.0, gat: float | None = 2.6) -> str:
    """Tandwiel: tanden met een ronde kop en voet (top/voet = halve breedte in rasterpunten)."""
    def p(r: float, a: float) -> str:
        return f"{_g(cx + r * math.cos(a))} {_g(cy + r * math.sin(a))}"
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
        volgende = a + stap
        d.append(f"A{_g(r_voet)} {_g(r_voet)} 0 0 1 {p(r_voet, volgende - av)}")
    uit = f'<path d="{"".join(d)}z"/>'
    if gat:
        uit += f'<circle cx="{_g(cx)}" cy="{_g(cy)}" r="{_g(gat)}"/>'
    return uit


def _ster4(cx: float, cy: float, r: float, k: float = 0.16) -> str:
    """Vierpuntige fonkelster met holle zijden."""
    c = k * r
    return (f'<path d="M{_g(cx)} {_g(cy - r)}Q{_g(cx + c)} {_g(cy - c)} {_g(cx + r)} {_g(cy)}'
            f'Q{_g(cx + c)} {_g(cy + c)} {_g(cx)} {_g(cy + r)}Q{_g(cx - c)} {_g(cy + c)} {_g(cx - r)} {_g(cy)}'
            f'Q{_g(cx - c)} {_g(cy - c)} {_g(cx)} {_g(cy - r)}z"/>')


def _stip(x: float, y: float, r: float = 1.1) -> str:
    """Gevuld rondje (voor kleine stippen die bij lijn 2 anders dichtlopen)."""
    return f'<circle cx="{_g(x)}" cy="{_g(y)}" r="{_g(r)}" fill="currentColor" stroke="none"/>'


def _uit(binnen: str, dikte: float, maat: int | None = None) -> str:
    """'Uit': een schuine streep met ruimte eromheen, net als in status.py (Uit = een
    schuine streep). De ruimte is een mask: QtSvg kent mask wel, clipPath niet."""
    d = "M3.5 3.5 20.5 20.5"
    m = maat or 24
    masker = ('<defs><mask id="uit" maskUnits="userSpaceOnUse" x="0" y="0" width="24" height="24">'
              '<rect width="24" height="24" fill="#fff"/>'
              f'<path d="{d}" fill="none" stroke="#000" stroke-width="{_g(dikte + 3)}" stroke-linecap="round"/>'
              '</mask></defs>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{m}" height="{m}" viewBox="0 0 24 24">'
            f'{basis.STIJLBLAD}{masker}'
            f'<g class="ColorScheme-Text" fill="none" stroke="currentColor" stroke-width="{_g(dikte)}" '
            f'stroke-linecap="round" stroke-linejoin="round"><g mask="url(#uit)">{binnen}</g>'
            f'<path d="{d}"/></g></svg>')


# Het scherm (met voet) uit LIJN, als basis voor andere tekens.
_SCHERM = lijn("computer")

# ---------------------------------------------------------------- tekens ---
# Nieuwe BugOS-lijntekens voor onderwerpen die LIJN (nog) niet heeft.
EIGEN: dict[str, str] = {
    # Systeem: een tandwiel.
    "tandwiel": _tandwiel(),
    # Achtergronddiensten: een groot en een klein tandwiel, los van elkaar (in elkaar grijpend
    # liepen ze bij 16 en 22 px dicht tot één vlek), met zes grove tanden.
    "tandwielen": (_tandwiel(9, 14, 6, 4.35, 6, 1.2, 1.5, 2.1)
                   + _tandwiel(18.25, 6.25, 3.3, 2.2, 6, 0.85, 0.9, None)),
    # Beveiliging, privacy, rechten: een schild.
    "schild": '<path d="M12 3.5c2.4 1.5 4.8 2.4 7.5 2.7v5.3c0 4.4-3.1 7.9-7.5 9.5-4.4-1.6-7.5-5.1-7.5-9.5V6.2'
              'C7.2 5.9 9.6 5 12 3.5z"/>',
    # Alle apps: negen stippen.
    "raster": "".join(f'<circle cx="{x}" cy="{y}" r="1.2"/>' for y in (5.5, 12, 18.5) for x in (5.5, 12, 18.5)),
    # Kleuren: een druppel met een glimlijntje.
    "druppel": '<path d="M12 3.5c3.6 4 6.5 7.7 6.5 11a6.5 6.5 0 0 1-13 0c0-3.3 2.9-7 6.5-11z"/>'
               '<path d="M9 14.8a3 3 0 0 0 2.7 2.9"/>',
    # Aanwijzers: de muispijl.
    "aanwijzer": '<path d="M6 3.5v15.5l4-3.7 2.7 6 2.8-1.3-2.7-5.8H18z"/>',
    # Pictogrammen: drie vormen (driehoek boven, rondje en vierkant onder). Niet rondje boven
    # driehoek of vierkant boven plus: dat leest bij 16 en 22 px als een wc-bordje of het teken voor 'vrouw'.
    "vormen": '<path d="M12 3.5 16.5 10.5h-9z"/><circle cx="7" cy="17" r="3.5"/>'
              '<rect x="13.5" y="13.5" width="7" height="7" rx="1.5"/>',
    # Lettertypen beheren: een A met een plusje.
    "letter-plus": '<path d="M3.5 19 8.5 6.5l5 12.5M5.3 14.5h6.4"/><path d="M18 3.5v6M15 6.5h6"/>',
    # Spelling: een A met een golflijntje eronder.
    "spelling": '<path d="M6 15.5 12 3.5l6 12M8.1 11.3h7.8"/>'
                '<path d="M4 20c1.33-1.33 2.67-1.33 4 0s2.67 1.33 4 0 2.67-1.33 4 0 2.67 1.33 4 0"/>',
    # Sneltoetsen: een toets met een bliksem (snel).
    "sneltoets": '<rect x="3.5" y="3.5" width="17" height="17" rx="3.5"/><path d="M13 6.5 9 12.5h3.5l-1 5 4-6.5H12z"/>',
    # Toetsenbord op het scherm: toetsenbord met een pijltje eronder.
    "toetsenbord-scherm": '<rect x="2.5" y="4" width="19" height="11" rx="2"/>'
                          '<path d="M6 7.5h.01M9.5 7.5h.01M13 7.5h.01M16.5 7.5h.01M6 11h.01M9.5 11h3.5M16.5 11h.01"/>'
                          '<path d="M9.5 18 12 20.5 14.5 18"/>',
    # Toetsenbord op het scherm tonen: pijltje omhoog boven het toetsenbord.
    "toetsenbord-tonen": '<rect x="2.5" y="9" width="19" height="11" rx="2"/>'
                         '<path d="M6 12.5h.01M9.5 12.5h.01M13 12.5h.01M16.5 12.5h.01M6 16h.01M9.5 16h3.5M16.5 16h.01"/>'
                         '<path d="M9.5 6 12 3.5 14.5 6"/>',
    # Filter (instellingen van het bureaublad): een trechter.
    "trechter": '<path d="M3.5 4.5h17L14 12v6.5l-4 2V12z"/>',
    # Tekst voorlezen: een spraakwolkje met geluidsgolfjes.
    "voorlezen": '<path d="M5 5h7a2 2 0 0 1 2 2v6.5a2 2 0 0 1-2 2H9l-3 2.75V15.5H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z"/>'
                 '<path d="M17 7.75a3.5 3.5 0 0 1 0 5M19.5 5.25a7.5 7.5 0 0 1 0 10"/>',
    # Scherm uit / schermbeveiliging: een scherm met een maantje (de maan uit LIJN, kleiner, gevuld).
    "scherm-slaap": _SCHERM + '<path d="M15 11.54A3.2 3.2 0 1 1 10.96 7.5a2.56 2.56 0 0 0 4.04 4.04z" '
                              'fill="currentColor" stroke-width="1"/>',
    # Contextmenu bewerken: een menu met het gekozen regeltje gevuld.
    "menu": '<rect x="4.5" y="3.5" width="15" height="17" rx="2.5"/><path d="M8 7.5h8M8 16.5h8"/>'
            '<rect x="7.5" y="10.75" width="9" height="2.5" rx="1.25" fill="currentColor" stroke-width="1"/>',
    # Touchpad: een vlak met twee knoppen.
    "touchpad": '<rect x="3" y="4.5" width="18" height="15" rx="2.5"/><path d="M3 14.5h18M12 14.5v5"/>',
    # Tekentablet: een liggend tablet met een pen ernaast.
    "tekentablet": '<rect x="2.5" y="7" width="13" height="12" rx="2"/><path d="M5.5 16.5h7"/>'
                   '<path d="M19 3.5h.5a1.5 1.5 0 0 1 1.5 1.5v10l-1.75 3.5L17.5 15V5A1.5 1.5 0 0 1 19 3.5z"/>',
    # Aanraakscherm: een wijzende hand.
    "hand": '<path d="M9 15.5V5.25a1.75 1.75 0 0 1 3.5 0v6.25"/><path d="M12.5 11a1.75 1.75 0 0 1 3.5 0v1"/>'
            '<path d="M16 11.75a1.75 1.75 0 0 1 3.5 0v3.25a6 6 0 0 1-6 6h-1.6a5.4 5.4 0 0 1-3.9-1.7l-3.3-3.4'
            'a1.6 1.6 0 0 1 2.3-2.3L9 15.5"/>',
    # Aanraakgebaren: een kleinere hand die veegt (pijl heen en weer).
    "vegen": '<path d="M10 16.5v-6a1.5 1.5 0 0 1 3 0v3"/><path d="M13 12.5a1.5 1.5 0 0 1 3 0v.5"/>'
             '<path d="M16 13a1.5 1.5 0 0 1 3 0v2.5a5 5 0 0 1-5 5h-1.3a4.5 4.5 0 0 1-3.2-1.4l-2.7-2.8a1.4 1.4 0 0 1 2-2L10 16.5"/>'
             '<path d="M4 4h9M6 2 4 4l2 2M11 2l2 2-2 2"/>',
    # Schermranden: een scherm met een actieve hoek.
    "schermrand": _SCHERM + '<path d="M3 9.5v-3a2 2 0 0 1 2-2h3A5 5 0 0 1 3 9.5z" fill="currentColor"/>',
    # Effecten: fonkelsterren.
    "effecten": _ster4(10, 13.5, 7) + _ster4(18, 5.5, 3),
    # Animaties: een bal in beweging.
    "beweging": '<circle cx="15.5" cy="12" r="5"/><path d="M4.5 8h2.5M3 12h4M4.5 16h2.5"/>',
    # Activiteiten: lagen.
    "lagen": '<path d="M12 3.5 3.5 8 12 12.5 20.5 8z"/><path d="M3.5 12 12 16.5 20.5 12"/>'
             '<path d="M3.5 16 12 20.5 20.5 16"/>',
    # Vensterbeheer (en KWin): twee vensters.
    "vensters": '<rect x="3" y="9" width="13" height="11" rx="2"/><path d="M3 12.5h13"/>'
                '<path d="M8 9V5.5a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-3"/>',
    # Vensterdecoraties: een venster met titelbalk en knopjes.
    "titelbalk": '<rect x="3" y="4.5" width="18" height="15" rx="2.5"/><path d="M3 9.5h18"/>'
                 '<path d="M11.5 7h.01M15 7h.01M18.5 7h.01"/>',
    # Vensters wisselen (Alt+Tab): een kaart met buren.
    "wisselaar": '<rect x="7" y="5.5" width="10" height="13" rx="2"/><path d="M3.5 8v8M20.5 8v8"/>',
    # Venstergedrag, -regels en -scripts: een venster met schuifjes (knopjes vrij van de randen,
    # anders lopen ze bij 16 px dicht).
    "venster-instellen": '<rect x="3" y="3.5" width="18" height="17" rx="2.5"/><path d="M3 8h18"/>'
                         '<path d="M7 12h10M7 16.5h10"/>' + _stip(10, 12, 1.5) + _stip(14, 16.5, 1.5),
    # Werkruimte: een bureaublad met een venster en een taakbalk (zonder startstipje: dat
    # liep bij 16 px dicht met de taakbalk; even groot als 'computer' in LIJN).
    "bureaublad": '<rect x="3" y="4.5" width="18" height="15" rx="2.5"/><path d="M3 15.5h18"/>'
                  '<rect x="9" y="7.5" width="8.5" height="5" rx="1.25"/>',
    # Verbonden apparaten: een scherm met een telefoon ervoor.
    "apparaten": '<path d="M12 14H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v1.5"/><path d="M6.5 18h4M8.5 14v4"/>'
                 '<rect x="14" y="9.5" width="7" height="11" rx="1.5"/><path d="M17.5 17.5h.01"/>',
    # Plasma-stijl: de kwast van 'Programmastijl' (2/3 zo groot) boven de taakbalk: de stijl van
    # het paneel. Een pop-up boven een paneel las als een laptop of een poppetje aan een bureau.
    "paneel": '<path d="M12.38 9.13 16.8 4.7a1.25 1.25 0 0 0-1.78-1.78l-4.42 4.42"/>'
              '<path d="M10.46 7.67a2.05 2.05 0 0 1 2.05 2.05c0 1.72-1.39 2.97-3.1 2.97H6.24c.79-.66.92-1.39.92-2.18'
              'a2.77 2.77 0 0 1 3.3-2.84z"/><rect x="2.5" y="16.5" width="19" height="4.5" rx="2.25"/>',
    # Programmastijl: een kwast.
    "kwast": '<path d="M13.3 13.6 20 6.9a1.9 1.9 0 0 0-2.7-2.7l-6.7 6.7"/>'
             '<path d="M10.4 11.4a3.1 3.1 0 0 1 3.1 3.1c0 2.6-2.1 4.5-4.7 4.5H4c1.2-1 1.4-2.1 1.4-3.3a4.2 4.2 0 0 1 5-4.3z"/>',
    # Opstartscherm: een scherm met een draaiend rondje.
    "opstartscherm": _SCHERM + '<path d="M14.5 10.5a2.5 2.5 0 1 1-2.5-2.5"/>',
    # Bestanden zoeken: een blad met een vergrootglas.
    "blad-zoek": '<path d="M10 20.5H6a1 1 0 0 1-1-1v-15a1 1 0 0 1 1-1h6.5l4.5 4.5V10"/><path d="M12.5 3.5V8H17"/>'
                 '<circle cx="16" cy="16" r="3.2"/><path d="m18.4 18.4 2.6 2.6"/>',
    # Zoeken in Plasma (en KRunner): een zoekveld met een vergrootglas en een regel tekst
    # (met een tekstcursor las het bij 16 en 22 px als 'QI').
    "zoekbalk": '<rect x="2.5" y="6.5" width="19" height="11" rx="3"/><circle cx="8.25" cy="11.75" r="2.25"/>'
                '<path d="m9.9 13.4 1.35 1.35"/><path d="M14 12h4"/>',
    # Zoekwoorden voor het web: een wereldbol als vergrootglas.
    "web-zoek": '<circle cx="10.5" cy="10.5" r="7"/><path d="M3.5 10.5h14"/>'
                '<path d="M10.5 3.5c-1.9 2-2.9 4.4-2.9 7s1 5 2.9 7c1.9-2 2.9-4.4 2.9-7s-1-5-2.9-7z"/>'
                '<path d="m15.5 15.5 5 5"/>',
    # Inlogscherm: een pijl naar binnen.
    "inloggen": '<path d="M14 4h3.5a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H14"/><path d="M4.5 12h9.5M10.5 8.5 14 12l-3.5 3.5"/>',
    # Gebruikers: twee personen.
    "personen": '<circle cx="9.5" cy="8" r="3.5"/><path d="M3 20a6.5 6.5 0 0 1 13 0"/>'
                '<path d="M16.7 4.7a3.5 3.5 0 0 1 0 6.6M18.3 14.1a6.5 6.5 0 0 1 2.7 5.9"/>',
    # Online-accounts: een wolk met een persoon.
    "wolk-persoon": '<path d="M7 18.5a4.2 4.2 0 0 1-.6-8.4 6 6 0 0 1 11.4.4 4 4 0 0 1-.3 8z"/>'
                    '<circle cx="12" cy="12.3" r="1.7"/><path d="M8.9 18.5a3.1 3.1 0 0 1 6.2 0"/>',
    # Proxy: het verkeer gaat door een tussenstation.
    "tussenstation": '<rect x="8.5" y="8.5" width="7" height="7" rx="2"/><path d="M3 12h5.5M15.5 12H21M18.5 9.5 21 12l-2.5 2.5"/>',
    # Delen (Samba): drie verbonden punten.
    "delen": '<circle cx="6" cy="12" r="2.5"/><circle cx="17.5" cy="5.5" r="2.5"/><circle cx="17.5" cy="18.5" r="2.5"/>'
             '<path d="m8.2 10.8 7.1-4.1M8.2 13.2l7.1 4.1"/>',
    # Netwerk (verbindingen): een kastje met twee kastjes eronder.
    "netwerk": '<rect x="9" y="3.5" width="6" height="5.5" rx="1.5"/><rect x="3.5" y="15" width="6" height="5.5" rx="1.5"/>'
               '<rect x="14.5" y="15" width="6" height="5.5" rx="1.5"/><path d="M12 9v3M6.5 15v-3h11v3"/>',
    # Bureaublad op afstand: een scherm met een pijl eruit.
    "op-afstand": _SCHERM + '<path d="m9.5 13 5-5M10.5 8h4v4"/>',
    # Thunderbolt: een bliksemschicht.
    "bliksem": '<path d="M13.5 3 5.5 13.5h6l-1 7.5 8-10.5h-6z"/>',
    # Automatisch starten, apparaatacties: een startknop.
    "starten": '<circle cx="12" cy="12" r="8.5"/><path d="M10 8.5v7l6-3.5z"/>',
    # SMART: een schijf met een hartslag.
    "schijf-hartslag": '<rect x="3" y="5" width="18" height="14" rx="2.5"/><path d="M6.5 12h2.5l1.5-3 3 6 1.5-3h2.5"/>',
    # Bestandskoppelingen: een blad met een pijl naar een programma.
    "blad-pijl": '<path d="M14 11V8l-4.5-4.5H5.5A1.5 1.5 0 0 0 4 5v14a1.5 1.5 0 0 0 1.5 1.5h7A1.5 1.5 0 0 0 14 19v-2"/>'
                 '<path d="M9.5 3.5V8H14"/><path d="M9 14h11.5M17.5 11l3 3-3 3"/>',
    # Dag-en-nachtritme (wanneer dag en nacht beginnen): een zon half boven de horizon.
    # Alleen lijnen, zoals LIJN: de half gevulde cirkel was het zwaarste teken in de zijbalk.
    "dag-nacht": '<path d="M7.5 15.5a4.5 4.5 0 0 1 9 0"/><path d="M3 19.5h18"/>'
                 '<path d="M12 6v2.5M5.4 8.9l1.75 1.75M18.6 8.9l-1.75 1.75"/>',
    # X11: een letter X (smaller dan het kruisje 'sluiten'), één streep onderbroken zoals in het X-logo.
    "x11": '<path d="M6.5 4 17.5 20"/><path d="M17.5 4 13.76 9.44M10.24 14.56 6.5 20"/>',
    # Wayland: een ronde W.
    "wayland": '<path d="M3.5 7.5c1 3.7 2.2 7 3.6 9.6.5.9 1.6.9 2.1 0L12 12l2.8 5.1c.5.9 1.6.9 2.1 0 1.4-2.6 2.6-5.9 3.6-9.6"/>',
    # Hardware-informatie (PCI in het Info Center): een insteekkaart met een chip en een
    # kamstekker. Geen losse chip: dat is cpu (plaatsen.py), en die staat er vlak boven (CPU, Interrupts).
    "insteekkaart": '<rect x="2.5" y="5" width="19" height="10.5" rx="2"/><rect x="6" y="8.25" width="5" height="4" rx="1"/>'
                    '<path d="M14.5 8.5h3.5M14.5 12h3.5"/><path d="M6.5 15.5v3h6v-3M15 15.5v3h3.5v-3"/>',
    # Graphics (Info Center): een kubus.
    "kubus": '<path d="M12 3 20 7.5v9L12 21l-8-4.5v-9z"/><path d="M4 7.5l8 4.5 8-4.5M12 12v9"/>',
    # KDE Portefeuille (wachtwoorden): een portemonnee.
    "portemonnee": '<rect x="3" y="6" width="18" height="14" rx="2.5"/><path d="M21 10.5h-4a2 2 0 0 0 0 4h4"/>'
                   '<path d="M17 12.5h.01"/><path d="M6 6l9-2.6a1.5 1.5 0 0 1 1.9 1.1L17.3 6"/>',
    # Virtuele bureaubladen: vier schermpjes, het huidige gevuld. Tussenruimte 3, zoals 'apps' in LIJN
    # (bij 2 raken de lijnen elkaar bij 22 px).
    "bureaubladen": '<rect x="3" y="5" width="7.5" height="5.5" rx="1.5" fill="currentColor"/>'
                    '<rect x="13.5" y="5" width="7.5" height="5.5" rx="1.5"/>'
                    '<rect x="3" y="13.5" width="7.5" height="5.5" rx="1.5"/>'
                    '<rect x="13.5" y="13.5" width="7.5" height="5.5" rx="1.5"/>',
}


def teken(naam: str) -> str:
    """Binnenkant van een teken: uit EIGEN of uit LIJN."""
    if naam in EIGEN:
        return EIGEN[naam]
    if naam in basis.LIJN:
        return lijn(naam)
    raise KeyError(f"onbekend teken {naam!r}")


# ------------------------------------------------------------ pictogrammen ---
# KDE-naam -> teken. Volgorde: zoals de zijbalk van KDE Instellingen.
VOORKEUREN: dict[str, str] = {
    # Hoofdgroepen en de startpagina
    "preferences-desktop": "bureaublad",              # Werkruimte, Algemeen gedrag, Snelle instellingen
    "preferences-system": "tandwiel",                 # Systeem
    "preferences-security": "schild",                 # Beveiliging en privacy, App-rechten, Firmware
    "preferences-desktop-peripherals": "apparaten",   # Verbonden apparaten
    "preferences-desktop-user": "persoon",            # Persoonlijk (en Gebruiker wisselen)
    # Invoer en uitvoer
    "preferences-desktop-mouse": "muis",              # Muis en touchpad (zoals BugOS Instellingen)
    "preferences-desktop-touchpad": "touchpad",
    "preferences-desktop-keyboard": "toetsenbord",
    "preferences-desktop-keyboard-shortcut": "sneltoets",
    "input-keyboard-virtual": "toetsenbord-scherm",
    "preferences-desktop-touchscreen": "hand",
    "preferences-desktop-gestures-touch": "vegen",
    "preferences-desktop-tablet": "tekentablet",
    "preferences-desktop-gaming": "spel",
    "preferences-desktop-sound": "geluid",            # Geluid
    "preferences-desktop-multimedia": "muziek",
    "preferences-desktop-accessibility": "oog",       # Makkelijker zien
    # Scherm
    "preferences-desktop-display": "computer",        # Scherm
    "preferences-desktop-display-randr": "computer",
    "preferences-desktop-gestures-screenedges": "schermrand",
    # Verbonden apparaten
    "preferences-system-bluetooth": "bluetooth",
    "preferences-devices-printer": "printer",
    "preferences-desktop-thunderbolt": "bliksem",
    "preferences-system-disks": "opslag",
    "preferences-smart-status": "schijf-hartslag",
    # Netwerk
    "preferences-system-network": "wifi",             # Wifi en internet
    "preferences-system-network-connection": "netwerk",
    "preferences-system-network-proxy": "tussenstation",
    "preferences-system-network-sharing": "delen",
    "preferences-system-network-remote": "op-afstand",
    "preferences-online-accounts": "wolk-persoon",
    # Uiterlijk
    "preferences-desktop-theme-global": "palet",      # Uiterlijk
    "preferences-desktop-theme": "palet",
    "preferences-desktop-color": "druppel",
    "preferences-desktop-theme-applications": "kwast",
    "preferences-desktop-plasma-theme": "paneel",
    "preferences-desktop-theme-windowdecorations": "titelbalk",
    "preferences-desktop-icons": "vormen",
    "preferences-desktop-cursors": "aanwijzer",
    "preferences-desktop-wallpaper": "foto",
    "preferences-system-splash": "opstartscherm",
    "preferences-desktop-font": "letter",
    "preferences-desktop-font-installer": "letter-plus",
    "preferences-desktop-animations": "beweging",
    # Apps en vensters
    "preferences-desktop-default-applications": "apps",   # Standaardprogramma's
    "preferences-desktop-filetype-association": "blad-pijl",
    "preferences-desktop-activities": "lagen",
    "preferences-system-windows": "vensters",
    "kwin": "vensters",
    "preferences-system-windows-actions": "venster-instellen",
    "preferences-system-tabbox": "wisselaar",
    "preferences-desktop-virtual": "bureaubladen",
    "preferences-desktop-effects": "effecten",
    # Werkruimte: zoeken en sessie
    "preferences-desktop-search": "zoek",
    "preferences-desktop-baloo": "blad-zoek",
    "plasma-search": "zoekbalk",
    "krunner": "zoekbalk",
    "preferences-web-browser-shortcuts": "web-zoek",
    "preferences-system-login": "inloggen",
    "preferences-system-session-services": "tandwielen",
    "system-run": "starten",
    "system-file-manager": "map",
    # Beveiliging
    "preferences-desktop-user-password": "slot",
    "kwalletmanager": "portemonnee",
    # Taal en tijd
    "preferences-desktop-locale": "wereld",           # Taal
    "preferences-system-time": "klok",                # Tijd
    "lighttable": "dag-nacht",
    "tools-check-spelling": "spelling",
    # Systeem
    "ktip": "laptop",                                 # Over deze computer
    "preferences-system-power-management": "batterij",  # Energie
    "preferences-system-users": "personen",
    "system-software-update": "verversen",            # Updates
    "preferences-desktop-feedback": "praten",
    # Info Center
    "hwinfo": "insteekkaart",
    "xorg": "x11",
    "wayland": "wayland",
    # Langere namen die anders op een korter BugOS-teken terugvallen (zie boven).
    "input-keyboard-virtual-show": "toetsenbord-tonen",   # inlog- en vergrendelscherm, systeemvak
    "input-keyboard-virtual-hide": "toetsenbord-scherm",  # idem, en de toets op het schermtoetsenbord
    "input-keyboard-virtual-on": "toetsenbord",           # vergrendelscherm (aan); uit staat in UIT
    "preferences-desktop-filter": "trechter",             # Bureaublad en achtergrond > Filter
    "preferences-desktop-text-to-speech": "voorlezen",    # 'Tekst voorlezen' in tekstvakken, Toegankelijkheid
    "preferences-desktop-screensaver": "scherm-slaap",    # Energiebeheer: scherm dimmen en uit
    "preferences-desktop-menu-edit": "menu",              # Dolphin: Contextmenu
    "preferences-system-network-share": "delen",          # delen via het netwerk (Samba)
    "preferences-system-network-share-windows": "delen",
}

# Hetzelfde teken met de 'uit'-streep erdoor.
UIT: dict[str, str] = {
    "input-keyboard-virtual-off": "toetsenbord",          # vergrendelscherm (uit), systeemvak
    "preferences-system-bluetooth-inactive": "bluetooth",
}

# Categorieën (Context Categories, zoals bij Breeze).
CATEGORIEEN: dict[str, str] = {
    "applications-all": "raster",          # Apps en vensters
    "applications-graphics": "kubus",      # Info Center: Graphics
}


def maak(b: basis.Bouwer) -> None:
    basis.map_erbij("preferences/16", Size=16, Context="Applications", Type="Fixed")
    basis.map_erbij("categories/16", Size=16, Context="Categories", Type="Fixed")
    for soort, tabel in (("preferences", VOORKEUREN), ("categories", CATEGORIEEN)):
        for naam, t in tabel.items():
            binnen = teken(t)
            b.schrijf(f"{soort}/scalable", naam, symbolisch(binnen), symbolic_ook=True)
            b.schrijf(f"{soort}/16", naam, klein(binnen), symbolic_ook=True)
    for naam, t in UIT.items():
        binnen = teken(t)
        b.schrijf("preferences/scalable", naam, _uit(binnen, basis.MATEN["lijn"]), symbolic_ook=True)
        b.schrijf("preferences/16", naam, _uit(binnen, 1.5, 16), symbolic_ook=True)
