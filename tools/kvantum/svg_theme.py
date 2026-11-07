"""De Kvantum-SVG (alle elementen van het thema) voor make.py: maak_svg()."""

from __future__ import annotations

from palette import KAART, KNOP, PALETTEN, meng
from svg_parts import Svg, f, icoon, kader_set, lijn_pad, negenvlak, schaduw, spoor, vul


# ---------------------------------------------------------------- het thema

def maak_svg(k: dict) -> str:
    svg = Svg()
    donker = k is PALETTEN["donker"]
    rood = svg.verloop(k["verloop"])                    # links -> rechts
    rood_v = svg.verloop(k["verloop"], 0, 1)            # boven -> onder

    # Knoppen: plat warmgrijs, 12 px rond, geen rand.
    knop = {"normal": (k["knop"], None, 0), "focused": (k["knop_hover"], None, 0),
            "pressed": (k["knop_druk"], None, 0), "toggled": (k["selectie"], k["accent_lijn"], 1),
            "disabled": (k["knop"] + "80", None, 0)}
    kader_set(svg, "btn", "button", knop, 3, KNOP, KNOP)
    svg.element("button-default-indicator", 8, 8, lambda x, y: "")
    # Toetsenbordfocus: een rode ring van 2 px langs de rand, zoals QPushButton:focus in bugos_ui.
    # Kvantum tekent btn-focus over de knop heen; in QML (KDE Instellingen) krijgt een
    # "highlighted" knop zo ook de ring.
    negenvlak(svg, "btn", "focus", 3, 3, None, k["accent"], 2, binnen=False)
    negenvlak(svg, "button", "focus", KNOP, KNOP, None, k["accent"], 2, binnen=False)
    # De standaardknop (Open, Opslaan): in de apps rood met witte tekst, maar Kvantum kent geen eigen
    # tekstkleur voor die knop. Dus een zachte rode tint over de knop (geen ring: die betekent focus).
    # Half doorzichtig, zodat wijzen en indrukken eronder zichtbaar blijven.
    negenvlak(svg, "btn", "default", 3, 3, k["standaard_tint"])
    negenvlak(svg, "button", "default", KNOP, KNOP, k["standaard_tint"])
    for staat in ("focus", "default"):
        svg.element(f"expand-button-{staat}", 4, 4,
                    lambda x, y: f'<rect x="{f(x)}" y="{f(y)}" width="4" height="4" fill="#000000"/>')

    # Knoppen op een werkbalk: zonder vlak tot je erop wijst.
    tknop = {"normal": (None, None, 0), "focused": (k["knop_hover"], None, 0),
             "pressed": (k["knop_druk"], None, 0), "toggled": (k["selectie"], None, 0),
             "disabled": (None, None, 0)}
    kader_set(svg, "tbtn", "tbutton", tknop, 3, KNOP, KNOP)

    # Invoervelden: kaartkleur, haarlijn, 12 px; met focus een rode ring van 2 px.
    veld = {"normal": (k["vlak"], k["rand_sterk"] if donker else k["rand_sterk"], 1),
            "focused": (k["vlak"], k["accent"], 2), "pressed": (k["vlak"], k["accent"], 2),
            "toggled": (k["vlak"], k["accent"], 2),
            "disabled": (meng(k["vlak"], k["achter"], 0.6), k["rand"], 1)}
    kader_set(svg, "le", "lineedit", veld, 3, KNOP, KNOP)

    # Keuzelijst (combobox): als een veld, wijzen = iets donkerdere rand.
    combo = {"normal": (k["vlak"], k["rand_sterk"], 1), "focused": (k["vlak_hover"], k["tekst3"], 1),
             "pressed": (k["vlak"], k["accent"], 2), "toggled": (k["vlak"], k["accent"], 2),
             "disabled": (meng(k["vlak"], k["achter"], 0.6), k["rand"], 1)}
    kader_set(svg, "cb", "combo", combo, 3, KNOP, KNOP)

    # Lijsten: wijzen = rustige tint, gekozen = zachte rode tint (12 px).
    rij = {"normal": (None, None, 0), "focused": (k["knop"], None, 0),
           "pressed": (k["selectie"], None, 0), "toggled": (k["selectie"], None, 0),
           "disabled": (None, None, 0)}
    kader_set(svg, "itemview", "ritemview", rij, 2, KNOP, KNOP)

    # Menu: kaart met haarlijn en 12 px hoeken; regels met 8 px wijs-tint.
    menu = {"normal": (k["vlak"], k["rand"] if not donker else k["rand_sterk"], 1)}
    kader_set(svg, "menu", "rmenu", menu, 6, KNOP, KNOP)
    mregel = {"normal": (None, None, 0), "focused": (k["knop"] if not donker else k["knop"], None, 0),
              "pressed": (k["knop"], None, 0), "toggled": (k["knop"], None, 0), "disabled": (None, None, 0)}
    kader_set(svg, "menuitem", "rmenuitem", mregel, 3, 8, 8)
    kader_set(svg, "menubaritem", "rmenubaritem", mregel, 3, 8, 8)
    negenvlak(svg, "menubar", "normal", 2, 0, k["achter"])
    schaduw(svg, "menu", 8, k["schaduw_alpha"])
    # Scheidingslijn in een menu (Kvantum rekt menuitem-separator uit over de hele regel van 9 px):
    # een haarlijn in de randkleur, met aan beide kanten wat ruimte (zoals QMenu::separator in bugos_ui).
    svg.element("menuitem-separator", 120, 9,
                lambda x, y: f'<rect x="{f(x + 6)}" y="{f(y + 4)}" width="108" height="1" {vul(k["rand"])}/>')
    # Afscheurrand van een menu (zelden): een stippellijn, Kvantum herhaalt dit stukje om de 20 px.
    for st, kl in (("normal", k["rand_sterk"]), ("focused", k["tekst3"])):
        svg.element(f"menuitem-tearoff-{st}", 20, 8,
                    lambda x, y, kl=kl: f'<rect x="{f(x + 4)}" y="{f(y + 3.5)}" width="12" height="1" {vul(kl)}/>')

    # Tooltip: inkt met lichte tekst (donker: omgekeerd), 12 px.
    tip = {"normal": (k["tip"], None, 0)}
    kader_set(svg, "tooltip", "rtooltip", tip, 4, KNOP, KNOP)
    schaduw(svg, "tooltip", 6, k["schaduw_alpha"])

    # Kaders (lijsten, scrollvlakken) en groepen: kaart met haarlijn.
    kader = {"normal": (k["vlak"], k["rand"] if not donker else k["rand"], 1),
             "focused": (k["vlak"], k["rand"] if not donker else k["rand"], 1)}
    kader_set(svg, "common", "rcommon", kader, 4, KNOP, KNOP, binnen=False)
    groep = {"normal": (k["vlak"], k["rand"], 1)}
    kader_set(svg, "group", "rgroup", groep, 4, KAART, KAART)
    tabvlak = {"normal": (k["vlak"], k["rand"], 1)}
    kader_set(svg, "tabframe", "rtabframe", tabvlak, 4, KNOP, KNOP, binnen=False)

    # Tabbladen: rustig; gekozen = zachte rode tint.
    tab = {"normal": (None, None, 0), "focused": (k["knop_hover"], None, 0), "pressed": (k["selectie"], None, 0),
           "toggled": (k["selectie"], None, 0), "disabled": (None, None, 0)}
    kader_set(svg, "tab", "rtab", tab, 3, KNOP, KNOP)
    # Kvantum tekent "tab-tear" als er tabbladen buiten beeld zijn; leeg, anders komt het standaardthema.
    svg.element("tab-tear", 8, 8, lambda x, y: "")

    # Kopjes van tabellen: kaartkleur met een lijntje eronder.
    for st, kl in {"normal": k["vlak"], "focused": k["vlak_hover"], "pressed": k["knop"], "toggled": k["vlak"],
                   "disabled": k["vlak"]}.items():
        negenvlak(svg, "header", st, 2, 0, kl, k["rand"], 1, alleen_onder=True)

    # Werkbalk, venster, dock: plat in de vensterkleur.
    negenvlak(svg, "toolbar", "normal", 2, 0, k["achter"])
    # Scheiding tussen knoppengroepen op een werkbalk: een staande haarlijn.
    svg.element("toolbar-separator", 8, 24,
                lambda x, y: f'<rect x="{f(x + 3.5)}" y="{f(y + 4)}" width="1" height="16" {vul(k["rand_sterk"])}/>')
    svg.element("window-normal", 8, 8, lambda x, y: f'<rect x="{f(x)}" y="{f(y)}" width="8" height="8" {vul(k["achter"])}/>')
    negenvlak(svg, "dock", "normal", 2, 0, k["achter"])
    negenvlak(svg, "dock", "focused", 2, 0, k["achter"])
    negenvlak(svg, "titlebar", "normal", 2, 0, k["zijbalk"])
    negenvlak(svg, "titlebar", "focused", 2, 0, k["zijbalk"])

    # Schuif: spoor van 8 px, gevuld deel koraal -> rood; bolletje van 22 px.
    for st, kl in {"normal": k["spoor"], "disabled": k["spoor"] + "80"}.items():
        negenvlak(svg, "slider", st, 4, 4, kl)
    spoor(svg, "slider", "toggled", 4, k["verloop"][0], k["verloop"][1], rood_v, "y")
    negenvlak(svg, "slider", "focused", 4, 4, k["spoor"])
    negenvlak(svg, "slider", "pressed", 4, 4, k["spoor"])
    # Toetsenbordfocus op een schuif: een dun rood randje om het spoor (focusFrame=true in [Slider]);
    # een streepje eronder zou Kvantum hier gedraaid tekenen.
    negenvlak(svg, "slider", "focus", 4, 4, None, k["accent"], 1, binnen=False)
    for naam in ("slidercursor", "slidercursor-tickless"):
        for st in ("normal", "focused", "pressed", "disabled"):
            rand = k["bol_rand"] if st != "focused" else k["tekst3"]
            vulk = k["bol"] if st != "disabled" else meng(k["bol"], k["achter"], 0.5)
            ring = rand if not rand.endswith("00") else None

            def bol(x, y, vulk=vulk, ring=ring, st=st):
                m = 11
                uit = (f'<circle cx="{f(x + m)}" cy="{f(y + m + 0.8)}" r="10.2" fill="#000000" '
                       f'fill-opacity="{0.10 if not donker else 0.40}"/>')
                if ring:
                    uit += f'<circle cx="{f(x + m)}" cy="{f(y + m)}" r="10" {vul(ring)}/>'
                    uit += f'<circle cx="{f(x + m)}" cy="{f(y + m)}" r="9" {vul(vulk)}/>'
                else:
                    uit += f'<circle cx="{f(x + m)}" cy="{f(y + m)}" r="10" {vul(vulk)}/>'
                if st == "pressed":
                    uit += f'<circle cx="{f(x + m)}" cy="{f(y + m)}" r="4" {vul(k["accent"])}/>'
                return uit
            svg.element(f"{naam}-{st}", 22, 22, bol)
    svg.element("slider-tick-normal", 2, 8,
                lambda x, y: f'<rect x="{f(x)}" y="{f(y)}" width="2" height="8" {vul(k["rand_sterk"])}/>')

    # Voortgang: spoor zoals de schuif, gevuld met het rode verloop.
    negenvlak(svg, "progress", "normal", 4, 4, k["spoor"])
    negenvlak(svg, "progress", "disabled", 4, 4, k["spoor"] + "80")
    spoor(svg, "progress-pattern", "normal", 4, k["verloop"][0], k["verloop"][1], rood, "x")
    spoor(svg, "progress-pattern", "focused", 4, k["verloop"][0], k["verloop"][1], rood, "x")
    negenvlak(svg, "progress-pattern", "disabled", 4, 4, k["tekst3"] + "80")

    # Schuifbalk: dun rond staafje, geen pijltjes.
    for st, (kl, w) in {"normal": (k["balk"], 6), "focused": (k["balk_hover"], 8), "pressed": (k["balk_hover"], 8),
                        "disabled": (k["balk"] + "60", 6)}.items():
        s = 6
        rr = w / 2
        off = (12 - w) / 2

        def stuk(deel, kl=kl, w=w, rr=rr, off=off):
            def teken(x, y):
                # alles in een staande balk van 12 breed: twee helften (left/right) van elk 6
                if deel in ("left", "right"):
                    if deel == "left":
                        return f'<rect x="{f(x + off)}" y="{f(y)}" width="{f(6 - off)}" height="8" {vul(kl)}/>'
                    return f'<rect x="{f(x)}" y="{f(y)}" width="{f(6 - off)}" height="8" {vul(kl)}/>'
                # hoeken: kwart van een cirkel met straal rr, tegen de binnenkant
                links = deel.endswith("left")
                boven = deel.startswith("top")
                cx = x + 6 if links else x
                cy = y + 6 if boven else y
                # halve dop (breedte 6-off, hoogte rr) aan de binnenkant
                bx = x + off if links else x
                d = (f"M{f(cx)} {f(cy)} L{f(bx if links else cx + (6 - off))} {f(cy)} "
                     f"A{f(rr)} {f(rr)} 0 0 {1 if links == boven else 0} {f(cx)} {f(cy - rr if boven else cy + rr)} Z")
                return f'<path d="{d}" {vul(kl)}/>'
            return teken
        for deel in ("topleft", "topright", "bottomleft", "bottomright"):
            svg.element(f"scrollbarslider-{st}-{deel}", s, s, stuk(deel))
        for deel in ("left", "right"):
            svg.element(f"scrollbarslider-{st}-{deel}", s, 8, stuk(deel))
        for deel in ("top", "bottom"):
            svg.element(f"scrollbarslider-{st}-{deel}", 8, s, lambda x, y: "")
        svg.element(f"scrollbarslider-{st}", 8, 8, lambda x, y: "")

    # Vinkjes en rondjes: 18 px, rond 6; aan = rood met wit.
    def vakje(st: str, aan: str):
        def teken(x, y):
            m = 18
            if aan == "nee":
                rand = {"normal": k["rand_sterk"], "focused": k["tekst3"], "pressed": k["accent"],
                        "disabled": k["rand"]}[st]
                binnenk = k["vlak"] if st != "disabled" else meng(k["vlak"], k["achter"], 0.6)
                return (f'<rect x="{f(x + 0.75)}" y="{f(y + 0.75)}" width="{f(m - 1.5)}" height="{f(m - 1.5)}" rx="5.25" '
                        f'{vul(binnenk)} stroke="{rand}" stroke-width="1.5"/>')
            vlak = {"normal": k["accent"], "focused": k["accent_hover"], "pressed": k["accent_hover"],
                    "disabled": k["tekst3"] + "80"}[st]
            uit = f'<rect x="{f(x)}" y="{f(y)}" width="{m}" height="{m}" rx="6" {vul(vlak)}/>'
            if aan == "ja":
                d = "M5 9.4 7.9 12.3 13.2 6.4"
            else:
                d = "M5.5 9h7"
            uit += (f'<path transform="translate({f(x)} {f(y)})" d="{d}" fill="none" stroke="#FFFFFF" stroke-width="2" '
                    'stroke-linecap="round" stroke-linejoin="round"/>')
            return uit
        return teken

    def rondje(st: str, aan: bool):
        def teken(x, y):
            c = 9
            if not aan:
                rand = {"normal": k["rand_sterk"], "focused": k["tekst3"], "pressed": k["accent"],
                        "disabled": k["rand"]}[st]
                binnenk = k["vlak"] if st != "disabled" else meng(k["vlak"], k["achter"], 0.6)
                return f'<circle cx="{f(x + c)}" cy="{f(y + c)}" r="8.25" {vul(binnenk)} stroke="{rand}" stroke-width="1.5"/>'
            vlak = {"normal": k["accent"], "focused": k["accent_hover"], "pressed": k["accent_hover"],
                    "disabled": k["tekst3"] + "80"}[st]
            return (f'<circle cx="{f(x + c)}" cy="{f(y + c)}" r="9" {vul(vlak)}/>'
                    f'<circle cx="{f(x + c)}" cy="{f(y + c)}" r="3.5" fill="#FFFFFF"/>')
        return teken

    for st in ("normal", "focused", "pressed", "disabled"):
        svg.element(f"checkbox-{st}", 18, 18, vakje(st, "nee"))
        svg.element(f"checkbox-checked-{st}", 18, 18, vakje(st, "ja"))
        svg.element(f"checkbox-tristate-{st}", 18, 18, vakje(st, "half"))
        svg.element(f"radio-{st}", 18, 18, rondje(st, False))
        svg.element(f"radio-checked-{st}", 18, 18, rondje(st, True))
    # In menu's: alleen een vinkje (of stip) als het aan staat, zoals in de BugOS-apps.
    for st in ("normal", "focused"):
        svg.element(f"menu-checkbox-{st}", 18, 18, lambda x, y: "")
        icoon(svg, f"menu-checkbox-checked-{st}", lijn_pad("vink"), k["tekst"], 18, 2)
        icoon(svg, f"menu-checkbox-tristate-{st}", "M7 12h10", k["tekst"], 18, 2)
        svg.element(f"menu-radio-{st}", 18, 18, lambda x, y: "")
        svg.element(f"menu-radio-checked-{st}", 18, 18,
                    lambda x, y: f'<circle cx="{f(x + 9)}" cy="{f(y + 9)}" r="3.5" {vul(k["tekst"])}/>')

    # Pijltjes: BugOS-lijn (chevron), in de tweede tekstkleur.
    chevron = lijn_pad("rechts")
    pijlkleur = {"normal": k["tekst2"], "focused": k["tekst"], "pressed": k["tekst"], "toggled": k["selectie_tekst"],
                 "disabled": k["tekst3"] + "90"}
    for richting, draai in {"right": 0, "down": 90, "left": 180, "up": 270}.items():
        for st, kl in pijlkleur.items():
            icoon(svg, f"arrow-{richting}-{st}", chevron, kl, 16, 2, draai)
            if st != "toggled":
                icoon(svg, f"iarrow-{richting}-{st}", chevron, kl, 16, 2, draai)
    for st, kl in pijlkleur.items():
        if st == "toggled":
            continue
        icoon(svg, f"arrow-plus-{st}", "M12 6v12M6 12h12", kl, 16, 2)
        icoon(svg, f"arrow-minus-{st}", "M6 12h12", kl, 16, 2)
        icoon(svg, f"iarrow-plus-{st}", "M12 6v12M6 12h12", kl, 16, 2)
        icoon(svg, f"iarrow-minus-{st}", "M6 12h12", kl, 16, 2)
    # Boom: pijltje naar rechts (dicht) of naar onder (open).
    for st, kl in (("normal", k["tekst2"]), ("focused", k["tekst"]), ("pressed", k["tekst"]),
                   ("disabled", k["tekst3"] + "90")):
        icoon(svg, f"tree-plus-{st}", chevron, kl, 16, 2)
        icoon(svg, f"tree-minus-{st}", chevron, kl, 16, 2, 90)
    # Sluitkruisje op tabbladen.
    kruis = lijn_pad("kruis")
    for st, kl in (("normal", k["tekst2"]), ("focused", k["tekst"]), ("pressed", k["accent"]),
                   ("disabled", k["tekst3"] + "90"), ("toggled", k["selectie_tekst"])):
        icoon(svg, f"tab-close-{st}", kruis, kl, 16, 2)
    # Vensterknopjes in programma's met deelvensters (MDI); zelden gezien.
    for st, kl in (("normal", k["tekst2"]), ("focused", k["tekst"]), ("pressed", k["accent"]),
                   ("disabled", k["tekst3"] + "90")):
        icoon(svg, f"mdi-close-{st}", kruis, kl, 16, 2)
        icoon(svg, f"mdi-minimize-{st}", "M6 12h12", kl, 16, 2)
        icoon(svg, f"mdi-maximize-{st}", "M6.5 6.5h11v11h-11z", kl, 16, 2)
        icoon(svg, f"mdi-restore-{st}", "M8.5 8.5h9v9h-9zM6.5 15.5v-9h9", kl, 16, 2)
        icoon(svg, f"mdi-shade-{st}", "m7 14 5-5 5 5", kl, 16, 2)
    icoon(svg, "mdi-menu-normal", "M6 8h12M6 12h12M6 16h12", k["tekst2"], 16, 2)

    # Grepen: rustige stipjes.
    def stipjes(kl):
        def teken(x, y):
            return "".join(f'<circle cx="{f(x + 4)}" cy="{f(y + cy)}" r="1" {vul(kl)}/>' for cy in (8, 12, 16))
        return teken
    for st, kl in (("normal", k["rand_sterk"]), ("focused", k["tekst3"]), ("pressed", k["accent"])):
        svg.element(f"splitter-grip-{st}", 8, 24, stipjes(kl))
    svg.element("toolbar-handle", 8, 24, stipjes(k["rand_sterk"]))
    svg.element("resize-grip-normal", 12, 12,
                lambda x, y: "".join(f'<circle cx="{f(x + a)}" cy="{f(y + b)}" r="1" {vul(k["tekst3"])}/>'
                                     for a, b in ((10, 10), (6, 10), (10, 6))))
    # Draaiknop (QDial), zelden gebruikt.
    svg.element("dial", 40, 40, lambda x, y: f'<circle cx="{f(x + 20)}" cy="{f(y + 20)}" r="19" {vul(k["knop"])} '
                f'stroke="{k["rand_sterk"]}" stroke-width="1"/>')
    svg.element("dial-handle", 8, 8, lambda x, y: f'<circle cx="{f(x + 4)}" cy="{f(y + 4)}" r="4" {vul(k["accent"])}/>')
    svg.element("dial-notches", 40, 40, lambda x, y: "")

    # Focus op een label of rij (PE_FrameFocusRect: vinkjes, rondjes, tabbladen, schuif, de huidige rij
    # in lijsten en in Dolphin): Kvantum zoekt "focus-top" enz. zonder toestand, op hoogstens 2 px.
    # Ontbreken ze, dan tekent Kvantum de stippelrand van zijn eigen standaardthema. BugOS: een rustig
    # grijs streepje van 2 px onderaan (een rij met focus blijft grijs, zoals in de BugOS-apps).
    for deel, (w, h) in {"top": (8, 2), "bottom": (8, 2), "left": (2, 8), "right": (2, 8), "topleft": (2, 2),
                         "topright": (2, 2), "bottomleft": (2, 2), "bottomright": (2, 2)}.items():
        onder = deel.startswith("bottom")
        svg.element(f"focus-{deel}", w, h,
                    lambda x, y, w=w, h=h, onder=onder:
                    f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" {vul(k["focus_streep"])}/>'
                    if onder else "")
    return svg.tekst()
