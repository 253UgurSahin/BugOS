"""App-pictogrammen voor het BugOS-thema: een lijnicoon op een rustig grijs tegeltje.

docs/BRAND.md ("Shapes"): "a line icon on a calm gray tile". Eén tegel voor de
hele familie (tegel()), daarop een glyph op het 24-raster: lijn 2, ronde uiteinden,
in inkt. BugOS' eigen apps krijgen hooguit één klein rood accent (zoals de stip van
het lieveheersbeestje); KDE-programma's en hulpjes blijven helemaal inkt.

De tegel kleurt mee met licht en donker, net als de neutrale IcoonChip in bugos_ui en
de twee merktegels (branding/logo/bugos-icon-light.svg en bugos-icon.svg). KDE vult
ColorScheme-Background (vensterkleur) en ColorScheme-Text (tekstkleur) in: licht geeft
een lichtgrijze tegel met inkt, donker een donkere tegel met een lichte lijn. Daarover
liggen een vaste zachte tint en een vaste glans en schaduw. Die geven in beide thema's
een rustig verloop. De haarlijn is de tekstkleur op 10 % (het merk: inkt 8 %, wit 9 %).
In een gekozen rij maakt KDE er vanzelf de zachte rode tint met een rode lijn van.
Programma's die het stijlblad niet invullen (GTK) krijgen de lichte tegel.
Rood is vast: ColorScheme-Highlight en -Accent zijn in BugOS de lichtroze selectietint.

Plaatshouders in een glyph: {i} lijnkleur (vlak), {r} rood (lijn), {rv} rood verloop (vlak);
gum() zet {t0} {t1} {t2} neer voor een gat in de tegelkleur.
"""

from __future__ import annotations

import math

import basis
from basis import KLEUREN, LIJN, ROOD_VERLOOP, STIJLBLAD

MAP = "apps/scalable"

_L = KLEUREN["licht"]
INKT = _L["tekst"]                      # #16171C (alleen de schaduw onder de tegel)
ACCENT = _L["accent"]                   # #DE2F3E: vast, ook op de donkere tegel goed te zien
TINT = _L["accent_zacht"]               # #FDE9E9: maakt de tegel warm (licht) en tilt hem op (donker)
TINT_DEKKING = 0.08
GLANS, SCHADUW = 0.035, 0.06            # wit bovenaan, zwart onderaan (vast, voor licht en donker)
RAND_DEKKING = 0.14                     # haarlijn in de tekstkleur (0.1 viel weg op de grijze taakbalk en het startmenu)

# De tegel op het 48-doek: 44 x 44 op (2, 2), hoek ~23 % (net als branding/logo/bugos-icon.svg).
T_XY, T_W, T_R = 2, 44, 10
SCHAAL = 1.5           # 24-raster -> 36 px: de glyph beslaat ruim 60 % van de tegel.
                       # Was 1.25 (de helft): naast volle pictogrammen als Firefox en Steam
                       # leken de BugOS-apps daardoor klein en leeg, in het startmenu en op de taakbalk.
DIKTE = 2.25           # lijndikte in px op het 48-doek (ruim 1 px bij 22 px)


def _n(x: float) -> str:
    s = f"{x:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _d(x: float) -> str:
    """Dekking (drie decimalen)."""
    return f"{x:.3f}".rstrip("0").rstrip(".")


def _verloop(id_: str, y1: float, y2: float) -> str:
    return (f'<linearGradient id="{id_}" x1="0" y1="{_n(y1)}" x2="0" y2="{_n(y2)}" gradientUnits="userSpaceOnUse">'
            f'<stop offset="0" stop-color="#FFFFFF" stop-opacity="{_d(GLANS)}"/>'
            f'<stop offset="1" stop-color="#000000" stop-opacity="{_d(SCHADUW)}"/></linearGradient>')


# De drie lagen van de tegelkleur: vensterkleur, warme tint, glans en schaduw.
_LAAG_BASIS = 'class="ColorScheme-Background" fill="currentColor"'
_LAAG_TINT = f'fill="{TINT}" fill-opacity="{_d(TINT_DEKKING)}"'


def tegel(glyph: str, *, schaal: float = 1.0, dx: float = 0, dy: float = 0) -> str:
    """Het app-pictogram: de BugOS-tegel met een glyph (24-raster) in het midden.

    schaal: optische correctie per glyph (1 = standaard); de lijn blijft even dik.
    dx, dy: optisch verschuiven, in px op het 48-doek."""
    s = SCHAAL * schaal
    w = DIKTE / s
    x, b, r = T_XY, T_W, T_R
    gat = "{t0}" in glyph
    binnen = glyph.format(i="currentColor", r=ACCENT, rv="url(#bugos-rood)",
                          t0=_LAAG_BASIS + ' stroke="none"', t1=_LAAG_TINT + ' stroke="none"',
                          t2='fill="url(#bugos-tegel-g)" stroke="none"')
    vorm = f'<rect x="{x}" y="{x}" width="{b}" height="{b}" rx="{r}" '
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 48 48">'
        f"{STIJLBLAD}<defs>"
        + _verloop("bugos-tegel", x, x + b)
        # hetzelfde verloop in de maten van de glyph, voor een gat (gum)
        + (_verloop("bugos-tegel-g", (x - 24 - dy) / s + 12, (x + b - 24 - dy) / s + 12) if gat else "")
        + '<linearGradient id="bugos-rood" x1="0" y1="0" x2="0.4" y2="1">'
        f'<stop offset="0" stop-color="{ROOD_VERLOOP[0]}"/><stop offset="1" stop-color="{ROOD_VERLOOP[1]}"/></linearGradient>'
        "</defs>"
        # smalle schaduw onder de tegel (op licht zichtbaar, op donker valt hij weg)
        f'<rect x="{x}" y="{x + 1}" width="{b}" height="{b}" rx="{r}" fill="{INKT}" fill-opacity=".12"/>'
        f"{vorm}{_LAAG_BASIS}/>{vorm}{_LAAG_TINT}/>{vorm}fill=\"url(#bugos-tegel)\"/>"
        f'<rect x="{x + .5}" y="{x + .5}" width="{b - 1}" height="{b - 1}" rx="{r - .5}" class="ColorScheme-Text" '
        f'fill="none" stroke="currentColor" stroke-opacity="{_d(RAND_DEKKING)}"/>'
        f'<g class="ColorScheme-Text" transform="translate({_n(24 + dx)} {_n(24 + dy)}) scale({_n(s)}) translate(-12 -12)" '
        f'fill="none" stroke="currentColor" stroke-width="{_n(w)}" stroke-linecap="round" stroke-linejoin="round">'
        f"{binnen}</g></svg>"
    )


def symbool(glyph: str, *, schaal: float = 1.0, dx: float = 0, dy: float = 0) -> str:
    """Eenkleurige versie (naam-symbolic): alleen de glyph, kleurt mee met het kleurenschema.

    dx, dy: dezelfde optische verschuiving als op de tegel (omgerekend naar het 24-raster);
    schaal doet hier niet mee, zodat de lijn overal 2 blijft."""
    leeg = 'fill="none" stroke="none"'
    binnen = glyph.format(i="currentColor", r="currentColor", rv="currentColor", t0=leeg, t1=leeg, t2=leeg)
    if dx or dy:
        binnen = f'<g transform="translate({_n(dx / SCHAAL)} {_n(dy / SCHAAL)})">{binnen}</g>'
    return basis.symbolisch(binnen)


# ------------------------------------------------------------- bouwstenen ---

def _p(cx: float, cy: float, r: float, hoek: float) -> str:
    a = math.radians(hoek)
    return f"{_n(cx + r * math.cos(a))} {_n(cy + r * math.sin(a))}"


def tandwiel(cx: float, cy: float, ro: float, ri: float, tanden: int = 8, tip: float = 20, voet: float = 32) -> str:
    """Een tandwiel als één lijn: tanden van ri naar ro (tip/voet: breedte in graden)."""
    stap = 360 / tanden
    d = []
    for i in range(tanden):
        a = -90 + i * stap
        d.append(("M" if i == 0 else f"A{_n(ri)} {_n(ri)} 0 0 1 ") + _p(cx, cy, ri, a - voet / 2))
        d.append("L" + _p(cx, cy, ro, a - tip / 2))
        d.append(f"A{_n(ro)} {_n(ro)} 0 0 1 " + _p(cx, cy, ro, a + tip / 2))
        d.append("L" + _p(cx, cy, ri, a + voet / 2))
    d.append(f"A{_n(ri)} {_n(ri)} 0 0 1 " + _p(cx, cy, ri, -90 - voet / 2) + "Z")
    return f'<path d="{"".join(d)}"/>'


def gum(cx: float, cy: float, r: float) -> str:
    """Een rond gat in de tegelkleur (dezelfde drie lagen als de tegel), zodat een voorgrondvorm vrij staat.

    Alleen vlakken, geen lijn: dan valt een doorzichtige laag nergens dubbel."""
    c = f'<circle cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r)}" '
    return c + "{t0}/>" + c + "{t1}/>" + c + "{t2}/>"


def stip(cx: float, cy: float, r: float = 1.6, kleur: str = "{rv}") -> str:
    return f'<circle cx="{_n(cx)}" cy="{_n(cy)}" r="{_n(r)}" fill="{kleur}" stroke="none"/>'


MAP_LIJN = LIJN["map"]
CIRKEL = '<circle cx="12" cy="12" r="8.5"/>'
VENSTER = '<rect x="3" y="4.5" width="18" height="15" rx="2.5"/>'           # kader van een programmavenster
SCHERM = LIJN["computer"]                                                   # beeldscherm met voet
RUITEN = '<rect x="4" y="4" width="16" height="16" rx="2.5"/><path d="M12 4v16M4 12h16"/>'  # venster in vier ruiten

# Een kever (geen lieveheersbeestje: langwerpig, met pootjes en voelsprieten).
_KEVER = ('<rect x="7.5" y="8.5" width="9" height="12" rx="4.5"/>'
          '<path d="M9.6 8.6v-.4a2.4 2.4 0 0 1 4.8 0v.4M10.3 5.6 8.8 4.1M13.7 5.6l1.5-1.5'
          'M7.5 12.5H4.5M16.5 12.5h3M7.6 16.2 5 17.8M16.4 16.2l2.6 1.6M8 10 5.6 8.6M16 10l2.4-1.4"/>')

# Potlood schuin rechtsonder (voor tekst en menu's), en een open blad waar hij in past.
_POTLOOD = '<path d="M19.1 10.9a1.9 1.9 0 0 1 2.7 2.7l-7.1 7.1-3.6.9.9-3.6z"/><path d="m17.4 12.6 2.7 2.7"/>'
_BLAD_OPEN = '<path d="M10 20.5H6.5a2 2 0 0 1-2-2v-13a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2V9"/>'

# Ladybug in lijn, voor Welkom: ronde schildjes, kopje, middenlijn, vier stippen.
_LIEVEHEERSBEESTJE = (
    '<circle cx="12" cy="13.5" r="7"/>'
    '<path d="M8.74 7.31a3.3 3.3 0 1 1 6.52 0M12 6.5v14"/>'
    + stip(9.2, 11.6, 1.25) + stip(14.8, 11.6, 1.25) + stip(9.4, 16.3, 1.25) + stip(14.6, 16.3, 1.25)
)

# Reddingsboei voor "Er werkt iets niet" (BugOS Hulp): twee rode banden.
_BOEI = (
    '<path d="M5.99 5.99A8.5 8.5 0 0 1 18.01 5.99L14.55 9.45A3.6 3.6 0 0 0 9.45 9.45z" fill="{rv}" stroke="none"/>'
    '<path d="M18.01 18.01A8.5 8.5 0 0 1 5.99 18.01L9.45 14.55A3.6 3.6 0 0 0 14.55 14.55z" fill="{rv}" stroke="none"/>'
    + CIRKEL + '<circle cx="12" cy="12" r="3.6"/>'
    '<path d="M9.45 9.45 5.99 5.99M14.55 9.45l3.46-3.46M14.55 14.55l3.46 3.46M9.45 14.55l-3.46 3.46"/>'
)


# -------------------------------------------------------------- de apps ---
# naam -> (glyph, opties voor tegel())

APPS: dict[str, tuple[str, dict]] = {
    # --- BugOS' eigen apps (hooguit één rood accent) ---
    # Bestanden: de BugOS-map.
    "bugos-files": (MAP_LIJN, {}),
    # Instellingen: een tandwiel met een rood asje.
    "bugos-settings": (tandwiel(12, 12, 8.9, 6.7) + '<circle cx="12" cy="12" r="2.6" stroke="{r}"/>', {}),
    # Winkel: een tas met de rode stip.
    "bugos-store": ('<path d="M5 8.5h14l-.9 10.6a1.6 1.6 0 0 1-1.6 1.4H7.5a1.6 1.6 0 0 1-1.6-1.4z"/>'
                     '<path d="M9 8.5V7a3 3 0 0 1 6 0v1.5"/>' + stip(12, 14.5, 1.7), {}),
    # Welkom: het lieveheersbeestje als lijntekening, met rode stippen.
    "bugos-welcome": (_LIEVEHEERSBEESTJE, {}),
    # Er werkt iets niet: reddingsboei.
    "bugos-help": (_BOEI, {}),
    # Back-up: klok met een pijl terug (rode pijlpunt).
    "bugos-backup": ('<path d="M4.5 12a7.5 7.5 0 1 0 2.2-5.3"/><path d="M4.5 4v4.5H9" stroke="{r}"/>'
                     '<path d="M12 8v4l2.8 1.8"/>', {}),
    # Bestanden van Windows: een rode pijl de map in (iets naar rechts: de pijl steekt links uit).
    "bugos-switch": ('<path d="M3.5 10V7a2 2 0 0 1 2-2h4l2 2h7a2 2 0 0 1 2 2v8.5a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2V17"/>'
                       '<path d="M2 13.5h9M8 10.5l3 3-3 3" stroke="{r}"/>', {"dx": .6}),
    # Taakbeheer: hartslaglijn met een rode stip aan het eind (nu).
    "bugos-task-manager": ('<path d="M3 12.5h3.5l2.5-6 4 11.5 2.8-7.5 1.7 2h.6"/>' + stip(20, 12.5, 1.6), {}),
    # Spelmodus: een spelcontroller met één rode knop.
    "bugos-game-mode": ('<path d="M7 8.5h10a4.5 4.5 0 0 1 4.5 4.5v1a2.5 2.5 0 0 1-4.4 1.6L15.5 14h-7l-1.6 1.6'
                        'A2.5 2.5 0 0 1 2.5 14v-1A4.5 4.5 0 0 1 7 8.5z"/><path d="M7.5 10.5v3M6 12h3M15.5 11.5h.01"/>'
                        '<path d="M17.5 12.5h.01" stroke="{r}"/>', {"schaal": 1.06}),
    # Windows-programma: een venster in vier ruiten.
    "bugos-exe": (RUITEN, {}),
    # Pakket installeren: een doos met rode tape (eerst de tape, zodat de rand van de doos heel blijft).
    "bugos-package": ('<path d="m8 5.5 8 4" stroke="{r}"/>'
                     '<path d="M12 3.5 20 7.5v9l-8 4-8-4v-9z"/><path d="M4 7.5l8 4 8-4M12 11.5v9"/>', {}),
    # BugOS installeren: laptop met een rode pijl naar beneden.
    "bugos-install": ('<rect x="4.5" y="5" width="15" height="10.5" rx="1.5"/><path d="M2.5 19h19"/>'
                          '<path d="M12 7.5v5M9.6 10.4 12 12.8l2.4-2.4" stroke="{r}"/>', {}),

    # --- KDE en andere programma's (alleen inkt) ---
    # Alle instellingen (KDE Systeeminstellingen): twee tandwielen.
    "systemsettings": (tandwiel(9.6, 9.6, 6.6, 4.9, 8, 22, 34) + '<circle cx="9.6" cy="9.6" r="1.9"/>'
                       + gum(17.2, 17.2, 6.9) + tandwiel(17.2, 17.2, 4.3, 3.1, 6, 26, 40)
                       + stip(17.2, 17.2, 1.15, "{i}"), {}),
    # Dolphin (voor gevorderden): de map met het teken voor gevorderden.
    "org.kde.dolphin": (MAP_LIJN + '<path d="M9.5 11.5l-2 2 2 2M14.5 11.5l2 2-2 2M12.8 10.9l-1.6 5.2"/>', {}),
    # Terminal: venster met prompt.
    "utilities-terminal": (VENSTER + '<path d="M7 9.5l3 2.5-3 2.5M12.5 15h4.5"/>', {}),
    # Meer apps (Discover): het app-raster met een plusje.
    "plasmadiscover": ('<rect x="4" y="4" width="6.5" height="6.5" rx="1.8"/><rect x="13.5" y="4" width="6.5" height="6.5" rx="1.8"/>'
                       '<rect x="4" y="13.5" width="6.5" height="6.5" rx="1.8"/><path d="M16.75 13.75v6M13.75 16.75h6"/>', {}),
    # Systeemmonitor (voor gevorderden): venster met een hartslaglijn.
    "utilities-system-monitor": (VENSTER + '<path d="M6.5 12.5h2l1.5-3.5 2.5 7 1.8-4.5 1 1h2.2"/>', {}),
    # Schijfbeheer: taartdiagram met één los stuk.
    "partitionmanager": ('<path d="M11 5a8 8 0 1 0 8 8h-8z"/><path d="M13.5 10.5V3a7.5 7.5 0 0 1 7.5 7.5z"/>', {}),
    # Help (KDE Helpcentrum): vraagteken in een cirkel.
    "help-browser": (CIRKEL + '<path d="M9.6 9.6a2.5 2.5 0 0 1 4.85.85c0 1.65-2.45 2.05-2.45 3.8M12 16.9h.01"/>', {}),
    # Informatiecentrum: i in een cirkel.
    "org.kde.kinfocenter": (CIRKEL + '<path d="M12 11v5.5M12 7.9h.01"/>', {}),
    # Wachtwoordkluis: portemonnee.
    "org.kde.kwalletmanager": ('<rect x="3.5" y="7" width="17" height="12.5" rx="2.5"/>'
                               '<path d="M5.5 7 15 4.4a1.5 1.5 0 0 1 1.9 1.45V7M20.5 11h-3.5a2.25 2.25 0 0 0 0 4.5h3.5M17 13.25h.01"/>', {}),
    # Kate (teksteditor voor gevorderden): blad met codehaakjes en een potlood.
    # Het potlood steekt rechtsonder uit: iets naar links en omhoog, zodat het geheel in het midden staat.
    "kate": (_BLAD_OPEN + '<path d="M9.5 7.5 7.5 9.5l2 2M12 7.5l2 2-2 2M8 15h2.5"/>' + _POTLOOD, {"dx": -1.2, "dy": -.5}),
    # KWrite: blad met tekst en een potlood.
    "kwrite": (_BLAD_OPEN + '<path d="M8 8h5M8 11.5h5M8 15h2"/>' + _POTLOOD, {"dx": -1.2, "dy": -.5}),
    # Ark: archiefdoos.
    "ark": ('<rect x="3" y="4.5" width="18" height="5" rx="1.5"/><path d="M4.5 9.5v8.5a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V9.5"/>'
            '<path d="M10 13.5h4"/>', {}),
    # Spectacle (schermafbeelding): zoekerhoeken met een lens.
    "spectacle": ('<path d="M4 8.5V6a2 2 0 0 1 2-2h2.5M15.5 4H18a2 2 0 0 1 2 2v2.5M20 15.5V18a2 2 0 0 1-2 2h-2.5M8.5 20H6a2 2 0 0 1-2-2v-2.5"/>'
                  '<circle cx="12" cy="12" r="3.5"/>', {}),
    # Filelight: ringdiagram met één gevuld stuk (hoeveel ruimte een map inneemt).
    "filelight": ('<path d="M12 3.5A8.5 8.5 0 0 1 19.36 16.25L15.64 14.1A4.2 4.2 0 0 0 12 7.8z" fill="{i}"/>'
                  + CIRKEL + '<circle cx="12" cy="12" r="4.2"/>', {}),
    # KFind: blad met een vergrootglas.
    "kfind": ('<path d="M11 20.5H6.5a2 2 0 0 1-2-2v-13a2 2 0 0 1 2-2h8a2 2 0 0 1 2 2V10"/><path d="M8 8h5M8 11.5h2.5"/>'
              '<circle cx="15" cy="15.5" r="3.5"/><path d="m17.6 18.1 2.9 2.9"/>', {}),
    # Speciale tekens: omega.
    "accessories-character-map": ('<path d="M5 18.7h4.2v-1.6a6.2 6.2 0 1 1 5.6 0v1.6H19"/>', {}),
    # Menu bewerken: lijstje met een potlood (de tekening zit laag en rechts op het raster: terugschuiven).
    "kmenuedit": ('<path d="M4 6.5h.01M7.5 6.5h9M4 11h.01M7.5 11h5M4 15.5h.01M7.5 15.5h2"/>' + _POTLOOD,
                  {"dx": -1.2, "dy": -2.2}),
    # Scherm delen (krfb): beeldscherm met een pijl naar buiten.
    "krfb": (SCHERM + '<path d="M9.5 12.5l4.5-4.5M10.5 8H14v3.5"/>', {}),
    # Firewall: schild met een muurtje.
    "firewall-config": ('<path d="M12 3.5l7 2.8v5.2c0 4.3-2.9 7.6-7 9-4.1-1.4-7-4.7-7-9V6.3z"/>'
                        '<path d="M5.2 11.5h13.6M10 4.6v6.9M14.5 11.5v7.4"/>', {}),
    # htop: venster met staafjes.
    "htop": (VENSTER + '<path d="M8 15.5v-2.5M12 15.5v-6.5M16 15.5v-4.5"/>', {}),
    # nvtop: meter met wijzer.
    "nvtop": ('<path d="M4.8 17a8 8 0 1 1 14.4 0"/><path d="m12 13.5 3.6-3.6"/>' + stip(12, 13.5, 1.5, "{i}"), {"dy": 1}),
    # Journal (logboek): blad met regels en tijdstipjes.
    "org.kde.kjournaldbrowser": ('<rect x="4.5" y="3.5" width="15" height="17" rx="2.2"/>'
                                 '<path d="M8 8h.01M11 8h5M8 12h.01M11 12h3.5M8 16h.01M11 16h5"/>', {}),
    # Fout melden: een kever met een uitroepteken.
    "tools-report-bug": (_KEVER + '<path d="M12 11.8v3.6M12 17.6h.01"/>', {}),
    # Foutzoeken starten: een kever met een afspeelknopje.
    "debug-run": (_KEVER + '<path d="M10.8 12.2v4.6l3.8-2.3z"/>', {}),
    # KDE Connect: laptop en telefoon.
    "kdeconnect": ('<rect x="2.5" y="6" width="10.5" height="8" rx="1.5"/><path d="M1.5 17.5h12.5"/>'
                   '<rect x="15.5" y="6" width="6.5" height="12" rx="1.6"/><path d="M18.75 15.5h.01"/>', {"dx": .3}),
    # Emoji kiezen: smiley.
    "preferences-desktop-emoticons": (CIRKEL + '<path d="M9 9.5v1M15 9.5v1M8.5 14a4 4 0 0 0 7 0"/>', {}),
    # Wine: venster in vier ruiten; Winetricks: idem met een plusje.
    "wine": (RUITEN, {}),
    "winetricks": ('<path d="M12 20H6a2.5 2.5 0 0 1-2.5-2.5V6A2.5 2.5 0 0 1 6 3.5h11.5A2.5 2.5 0 0 1 20 6v6"/>'
                   '<path d="M11.75 3.5V20M3.5 11.75h16.5M18 14.5v6M15 17.5h6"/>', {}),
}

# Zelfde tekening, andere naam (KDE vraagt soms de nieuwe of de oude naam).
ALIASSEN = {
    "utilities-terminal": ["org.kde.konsole"],
    "plasmadiscover": ["org.kde.discover"],
    "ark": ["org.kde.ark"],
    "kfind": ["org.kde.kfind"],
    "kwrite": ["org.kde.kwrite"],
    "org.kde.kwalletmanager": ["org.kde.kwalletmanager5"],
}

# Namen waarvan KDE (ook) een eenkleurige -symbolic-versie vraagt (Breeze heeft ze).
SYMBOLISCH = ["kate", "kdeconnect", "krfb", "utilities-terminal", "wine", "debug-run", "tools-report-bug",
              "preferences-desktop-emoticons"]


def maak(b: basis.Bouwer) -> None:
    for naam, (glyph, opties) in APPS.items():
        b.schrijf(MAP, naam, tegel(glyph, **opties))
    for naam, anderen in ALIASSEN.items():
        b.alias(MAP, naam, *anderen)
    for naam in SYMBOLISCH:
        glyph, opties = APPS[naam]
        b.schrijf(MAP, naam + "-symbolic", symbool(glyph, **opties))
