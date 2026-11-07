"""De knoppen voor status.py: KNOPPEN (naam -> teken) voor go-, edit-, view-, window-, ..."""

from __future__ import annotations

import math

from base import LIJN
from status_draw import R, Stuk, _g, _p, _stip
from status_signs import _info, _vraag, cirkel, contrast, deur, meter, schakel


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
