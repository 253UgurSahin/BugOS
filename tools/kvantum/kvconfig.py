"""Het Kvantum-instellingenbestand (.kvconfig) voor make.py: maak_kvconfig()."""

from __future__ import annotations

from palette import KAART, KNOP, THEMAS, meng
from tokens import MATEN


def maak_kvconfig(thema: str, k: dict) -> str:
    donker = thema == "donker"
    naam = THEMAS[thema][0]
    st = k["selectie_tekst"]
    e_knop = KNOP * 2     # frame.expansion: hoeken van 12 px
    e_kaart = KAART * 2   # hoeken van 16 px
    e_regel = 16          # hoeken van 8 px (menu-regels)
    tekst = k["tekst"]
    t2 = k["tekst2"]

    def sectie(titel: str, **sleutels) -> str:
        # Knoppen met een vlak zijn halfvet (zoals QPushButton in bugos_ui: font-weight 600). Alles wat
        # verder van PanelButtonCommand erft (vinkjes, lijsten, tabbladen, werkbalkknoppen) blijft gewoon.
        if "inherits" in sleutels and "text__bold" not in sleutels and titel != "PanelButtonTool":
            sleutels["text__bold"] = False
        regels = [f"[{titel}]"]
        for s, v in sleutels.items():
            s = s.replace("__", ".")
            if isinstance(v, bool):
                v = "true" if v else "false"
            regels.append(f"{s}={v}")
        return "\n".join(regels) + "\n"

    def kader(element, groot, rand, expansie, **extra):
        d = dict(frame=True, frame__element=element, frame__expandedElement=groot,
                 frame__top=rand, frame__bottom=rand, frame__left=rand, frame__right=rand,
                 frame__expansion=expansie)
        d.update(extra)
        return d

    delen = [f"""# BugOS-programmastijl voor Kvantum ({"donker" if donker else "licht"}).
# Gemaakt door tools/kvantum/make.py uit tools/design/tokens.py; niet met de hand bewerken.
"""]
    delen.append(sectie(
        "%General",
        author="BugOS", comment=f"The BugOS style for KDE and Qt apps ({'dark' if donker else 'light'})",
        x11drag="menubar_and_primary_toolbar", alt_mnemonic=True, respect_DE=True, click_behavior=0,
        composite=True, translucent_windows=False, blurring=False, popup_blurring=False,
        reduce_window_opacity=0, reduce_menu_opacity=0, no_window_pattern=False, no_inactiveness=True,
        menu_shadow_depth=8, tooltip_shadow_depth=6, menu_blur_radius=0, tooltip_blur_radius=0,
        shadowless_popup=False, animate_states=True,
        layout_spacing=6, layout_margin=12, small_icon_size=16, large_icon_size=32, button_icon_size=16,
        toolbar_icon_size=22, toolbutton_style=0,
        # transient_groove=false: geen half doorzichtige baan met een streep ernaast, alleen het staafje
        # (zoals in de BugOS-apps).
        scroll_width=12, scroll_min_extent=36, scroll_arrows=False, transient_scrollbar=True,
        transient_groove=False, scrollbar_in_view=True,
        slider_width=MATEN["schuif_spoor"], slider_handle_width=MATEN["schuif_knop"],
        slider_handle_length=MATEN["schuif_knop"], tickless_slider_handle_size=MATEN["schuif_knop"],
        check_size=18, progressbar_thickness=MATEN["schuif_spoor"], textless_progressbar=False, spread_progressbar=True,
        combo_as_lineedit=False, square_combo_button=False, combo_menu=True, hide_combo_checkboxes=True,
        combo_focus_rect=False, inline_spin_indicators=True, vertical_spin_indicators=False,
        inline_spin_separator=False, spin_button_width=24,
        groupbox_top_label=True, spread_menuitems=True, spread_header=True, menu_separator_height=9,
        scrollable_menu=True, submenu_overlap=0, submenu_delay=250, tooltip_delay=-1,
        merge_menubar_with_toolbar=True, menubar_mouse_tracking=True,
        left_tabs=False, attach_active_tab=False, embedded_tabs=False, mirror_doc_tabs=True,
        joined_inactive_tabs=False, bold_active_tab=False, no_active_tab_separator=True,
        group_toolbar_buttons=False, toolbar_item_spacing=2, toolbar_interior_spacing=4,
        center_toolbar_handle=True, slim_toolbars=False, fill_rubberband=False, tree_branch_line=False,
        splitter_width=7, drag_from_buttons=False, contrast="1.00", intensity="1.00", saturation="1.00",
    ))
    delen.append(sectie(
        "GeneralColors",
        window__color=k["achter"], inactive__window__color=k["achter"],
        base__color=k["vlak"], inactive__base__color=k["vlak"],
        alt__base__color=meng(k["vlak"], k["achter"], 0.55 if not donker else 0.0) if not donker else k["vlak_hover"],
        inactive__alt__base__color=meng(k["vlak"], k["achter"], 0.55) if not donker else k["vlak_hover"],
        button__color=k["knop"],
        light__color=k["vlak"] if not donker else k["rand_sterk"],
        mid__light__color=k["achter"] if not donker else k["knop_hover"],
        mid__color=k["rand"], dark__color=k["rand_sterk"] if not donker else "#0B0C0F",
        highlight__color=k["selectie"], inactive__highlight__color=k["selectie"],
        text__color=tekst, inactive__text__color=tekst, window__text__color=tekst,
        inactive__window__text__color=tekst, button__text__color=tekst, inactive__button__text__color=tekst,
        disabled__text__color=k["tekst3"],
        tooltip__base__color=k["tip"], tooltip__text__color=k["tip_tekst"],
        highlight__text__color=st, inactive__highlight__text__color=st,
        link__color=k["link"], link__visited__color="#8B3FA8" if not donker else "#C08CE0",
        progress__indicator__text__color=tekst, progress__inactive__indicator__text__color=tekst,
    ))
    delen.append(sectie(
        "Hacks",
        transparent_ktitle_label=True, transparent_dolphin_view=False, transparent_pcmanfm_sidepane=True,
        transparent_pcmanfm_view=False, blur_translucent=False, transparent_menutitle=True,
        respect_darkness=False, force_size_grip=False, iconless_pushbutton=False, iconless_menu=False,
        disabled_icon_opacity=50, normal_default_pushbutton=True, single_top_toolbar=True,
        tint_on_mouseover=0, no_selection_tint=True, transparent_arrow_button=True,
        middle_click_scroll=False, kinetic_scrolling=False, centered_forms=False, lxqtmainmenu_iconsize=0,
        style_vertical_toolbars=False,
    ))
    knoptekst = dict(text__normal__color=tekst, text__focus__color=tekst, text__press__color=tekst,
                     text__toggle__color=st, text__shadow=False, text__bold=True, text__boldness=2)
    delen.append(sectie(
        "PanelButtonCommand",
        **kader("btn", "button", 3, e_knop), interior=True, interior__element="button", focusFrame=True,
        indicator__element="arrow", indicator__size=12, text__margin=1, text__iconspacing=6,
        text__margin__top=5, text__margin__bottom=5, text__margin__left=9, text__margin__right=9,
        min_width="+0.3font", **knoptekst))
    # Losse gereedschapsknoppen: dezelfde ronde knop (de sleutels hier nog eens, anders blijven de hoeken klein).
    delen.append(sectie("PanelButtonTool", inherits="PanelButtonCommand", **kader("btn", "button", 3, e_knop),
                        interior=True, interior__element="button"))
    delen.append(sectie(
        "ToolbarButton", inherits="PanelButtonCommand", **kader("tbtn", "tbutton", 3, e_knop),
        interior__element="tbutton", text__margin__top=4, text__margin__bottom=4, text__margin__left=5,
        text__margin__right=5, min_width=0, focusFrame=False))
    delen.append(sectie("Dock", inherits="PanelButtonCommand", frame=False, interior=False,
                        text__normal__color=tekst))
    delen.append(sectie("DockTitle", inherits="PanelButtonCommand", frame=False, interior=False,
                        text__normal__color=t2, text__focus__color=tekst, text__bold=False,
                        text__margin__top=4, text__margin__bottom=4))
    delen.append(sectie("IndicatorSpinBox", inherits="PanelButtonCommand", frame=False, interior=False,
                        indicator__element="iarrow", indicator__size=12, text__normal__color=tekst))
    delen.append(sectie("RadioButton", inherits="PanelButtonCommand", frame=False, interior=True,
                        interior__element="radio", text__margin__top=2, text__margin__bottom=2,
                        text__margin__left=2, text__margin__right=2, text__focus__color=tekst,
                        text__toggle__color=tekst, focusFrame=False))
    delen.append(sectie("CheckBox", inherits="PanelButtonCommand", frame=False, interior=True,
                        interior__element="checkbox", text__margin__top=2, text__margin__bottom=2,
                        text__margin__left=2, text__margin__right=2, text__focus__color=tekst,
                        text__toggle__color=tekst, focusFrame=False))
    # Kvantum tekent dit kader altijd zonder ronde hoeken en hoogstens 2 px dik (zie focus-* in de SVG).
    delen.append(sectie("Focus", inherits="PanelButtonCommand", interior=False, frame=True, frame__element="focus",
                        frame__top=2, frame__bottom=2, frame__left=2, frame__right=2, frame__expansion=0))
    delen.append(sectie("GenericFrame", inherits="PanelButtonCommand", interior=False,
                        **kader("common", "rcommon", 4, e_knop), interior__element="common", focusFrame=False))
    delen.append(sectie(
        "LineEdit", inherits="PanelButtonCommand", **kader("le", "lineedit", 3, e_knop),
        interior=True, interior__element="lineedit", text__margin__top=4, text__margin__bottom=4,
        text__margin__left=7, text__margin__right=7, focusFrame=False))
    delen.append(sectie("ToolbarLineEdit", inherits="LineEdit"))
    delen.append(sectie("DropDownButton", inherits="PanelButtonCommand", indicator__element="arrow-down",
                        indicator__size=12))
    delen.append(sectie("IndicatorArrow", indicator__element="arrow", indicator__size=12))
    delen.append(sectie("ToolboxTab", inherits="PanelButtonCommand", text__normal__color=tekst,
                        text__press__color=tekst, text__focus__color=tekst))
    delen.append(sectie(
        "Tab", inherits="PanelButtonCommand", **kader("tab", "rtab", 3, e_knop), interior=True,
        interior__element="tab", indicator__element="tab", indicator__size=16, focusFrame=False,
        text__margin__top=4, text__margin__bottom=4, text__margin__left=10, text__margin__right=10,
        text__normal__color=t2, text__focus__color=tekst, text__press__color=st, text__toggle__color=st,
        min_width="4font"))
    delen.append(sectie("TabFrame", inherits="PanelButtonCommand", interior=False,
                        **kader("tabframe", "rtabframe", 4, e_knop), focusFrame=False))
    delen.append(sectie("TabBarFrame", inherits="GenericFrame", frame=False, interior=False))
    delen.append(sectie("TreeExpander", inherits="PanelButtonCommand", frame=False, interior=False,
                        indicator__element="tree", indicator__size=14))
    delen.append(sectie(
        "HeaderSection", inherits="PanelButtonCommand", frame=True, frame__element="header",
        frame__top=2, frame__bottom=2, frame__left=2, frame__right=2, frame__expansion=0,
        frame__expandedElement="header", interior=True, interior__element="header",
        text__margin__top=4, text__margin__bottom=4, text__margin__left=6, text__margin__right=6,
        text__normal__color=t2, text__focus__color=tekst, text__press__color=tekst, text__toggle__color=tekst,
        text__bold=False, focusFrame=False))
    delen.append(sectie("SizeGrip", indicator__element="resize-grip"))
    delen.append(sectie("Toolbar", inherits="PanelButtonCommand", frame=True, frame__element="toolbar",
                        frame__top=2, frame__bottom=2, frame__left=2, frame__right=2, frame__expansion=0,
                        interior=True, interior__element="toolbar", indicator__element="toolbar",
                        indicator__size=8, text__margin=0, text__normal__color=tekst, focusFrame=False))
    delen.append(sectie("Slider", inherits="PanelButtonCommand", frame=True, frame__element="slider",
                        frame__expandedElement="slider", frame__top=4, frame__bottom=4, frame__left=4,
                        frame__right=4, frame__expansion=0, interior=True, interior__element="slider",
                        focusFrame=True))
    delen.append(sectie("SliderCursor", inherits="PanelButtonCommand", frame=False, interior=True,
                        interior__element="slidercursor", focusFrame=False))
    delen.append(sectie("Progressbar", inherits="PanelButtonCommand", frame=True, frame__element="progress",
                        frame__expandedElement="progress", frame__top=4, frame__bottom=4, frame__left=4,
                        frame__right=4, frame__expansion=0, interior=True, interior__element="progress",
                        text__margin=0, text__normal__color=tekst, text__focus__color=tekst,
                        text__press__color=tekst, text__toggle__color=tekst, text__bold=False, focusFrame=False))
    delen.append(sectie("ProgressbarContents", inherits="PanelButtonCommand", frame=True,
                        frame__element="progress-pattern", frame__expandedElement="progress-pattern",
                        frame__top=4, frame__bottom=4, frame__left=4, frame__right=4, frame__expansion=0,
                        interior=True, interior__element="progress-pattern", focusFrame=False))
    delen.append(sectie(
        "ItemView", inherits="PanelButtonCommand", **kader("itemview", "ritemview", 2, e_knop),
        interior=True, interior__element="itemview", text__margin=0, text__margin__top=3,
        text__margin__bottom=3, text__margin__left=6, text__margin__right=6, text__normal__color=tekst,
        text__focus__color=tekst, text__press__color=st, text__toggle__color=st, min_width=0, min_height=0,
        focusFrame=False))
    delen.append(sectie("Splitter", indicator__size=24))
    delen.append(sectie("Scrollbar", inherits="PanelButtonCommand", frame=False, interior=False,
                        indicator__element="arrow", indicator__size=10))
    delen.append(sectie("ScrollbarSlider", inherits="PanelButtonCommand", frame=True,
                        frame__element="scrollbarslider", frame__expandedElement="scrollbarslider",
                        frame__top=6, frame__bottom=6, frame__left=6, frame__right=6, frame__expansion=0,
                        interior=False, indicator__element="grip", indicator__size=0, focusFrame=False))
    delen.append(sectie("ScrollbarGroove", inherits="PanelButtonCommand", frame=False, interior=False))
    delen.append(sectie(
        "MenuItem", inherits="PanelButtonCommand", **kader("menuitem", "rmenuitem", 3, e_regel),
        interior=True, interior__element="menuitem", indicator__element="menuitem", indicator__size=12,
        # Zelfde ruimte als QMenu::item in bugos_ui (Instellingen, Bestanden): 9 px boven en onder,
        # 12 px links. Het kader neemt er al 3 van; de tekstmarge doet de rest.
        text__margin__top=6, text__margin__bottom=6, text__margin__left=9, text__margin__right=12,
        text__normal__color=tekst, text__focus__color=tekst, text__press__color=tekst,
        text__toggle__color=tekst, min_width=0, min_height=0, focusFrame=False))
    delen.append(sectie("MenuBar", inherits="PanelButtonCommand", frame=False, interior=True,
                        interior__element="menubar", frame__element="menubar"))
    delen.append(sectie(
        "MenuBarItem", inherits="PanelButtonCommand", **kader("menubaritem", "rmenubaritem", 3, e_regel),
        interior=True, interior__element="menubaritem", text__margin__top=3, text__margin__bottom=3,
        text__margin__left=6, text__margin__right=6, text__normal__color=tekst, text__focus__color=tekst,
        text__press__color=tekst, text__toggle__color=tekst, min_width=0, min_height=0, focusFrame=False))
    delen.append(sectie("TitleBar", inherits="PanelButtonCommand", frame=False, interior=True,
                        interior__element="titlebar", indicator__element="mdi", indicator__size=16,
                        text__normal__color=t2, text__focus__color=tekst, text__bold=True, text__italic=False))
    delen.append(sectie("ComboBox", inherits="PanelButtonCommand", **kader("cb", "combo", 3, e_knop),
                        interior=True, interior__element="combo", text__margin__left=7, text__margin__right=7,
                        indicator__element="arrow", indicator__size=12, text__toggle__color=tekst))
    delen.append(sectie("ToolbarComboBox", inherits="ComboBox"))
    delen.append(sectie("Menu", inherits="PanelButtonCommand", **kader("menu", "rmenu", 6, e_knop),
                        interior=True, interior__element="menu", text__normal__color=tekst, focusFrame=False))
    delen.append(sectie("GroupBox", inherits="GenericFrame", **kader("group", "rgroup", 4, e_kaart),
                        interior=True, interior__element="group", text__margin=0, text__margin__top=0,
                        text__margin__bottom=4, text__margin__left=2, text__margin__right=2,
                        # Kopje boven een kaart zoals in de BugOS-apps ("sectie"): tweede tekstkleur, halfvet.
                        text__normal__color=t2, text__press__color=tekst, text__focus__color=tekst,
                        text__bold=True, text__boldness=2, focusFrame=False))
    delen.append(sectie("ToolTip", inherits="GenericFrame", **kader("tooltip", "rtooltip", 4, e_knop),
                        interior=True, interior__element="tooltip", text__margin__top=4, text__margin__bottom=4,
                        text__margin__left=6, text__margin__right=6, text__normal__color=k["tip_tekst"],
                        text__focus__color=k["tip_tekst"], text__shadow=False))
    delen.append(sectie("StatusBar", inherits="GenericFrame", frame=False, interior=False))
    delen.append(sectie("Window", interior=True, interior__element="window", frame=False))
    delen.append(sectie("Dialog", inherits="Window"))
    return "\n".join(delen)
