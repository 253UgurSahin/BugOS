"""Systeemvak, schermmeldingen (OSD), Plasma-pop-ups en knoppen: eenkleurige BugOS-lijniconen.

Voor: geluid en microfoon, netwerk (wifi, kabel, mobiel, vpn, vliegtuigstand),
bluetooth, batterij en energieprofielen, helderheid en nachtlicht, meldingen,
media, aan/uit en sessie, toetsenbordlampjes, camera, de berichtpictogrammen
(dialog-*), de gewone knoppen (go-, edit-, view-, window-, ...) en emblemen.

Namen: precies zoals Plasma 6.8 ze vraagt (uit de QML van de applets in het
BugOS-image en uit breeze-icons). KDE zoekt eerst de hele naam en haalt er daarna
stukjes van achteren af (battery-050-charging-profile-performance-symbolic ->
battery-050-charging-symbolic); daarom staat elk niveau er met zijn eigen naam in.

Huisstijl (docs/BRAND.md): 24-raster, lijn 2, ronde uiteinden, in de
tekstkleur (ColorScheme-Text met currentColor, KDE kleurt mee met licht en
donker). Niveaus lees je af aan wat vol is: geluid 0-3 golfjes, wifi 0-3
boogjes, mobiel 0-4 streepjes (de rest op 35 %), batterij en microfoon een
gevulde balk (batterij onder 20 % rood). Bij laden wordt het nokje van de
batterij een bliksem, zodat je het niveau blijft zien. Uit = een schuine streep
met ruimte eromheen. Kleur alleen waar iets aandacht vraagt (een nieuwe melding,
een probleem).

Elk pictogram komt in <soort>/scalable (elke maat vanaf 17 behalve precies 22),
<soort>/22 en <soort>/16.
22 is de maat van het systeemvak en van werkbalken: daar staat dezelfde 24-tekening
met een viewBox van 22 eenheden (1 eenheid = 1 pixel), zodat de lijnen op hele
pixels vallen in plaats van wazig verkleind te worden. De families met niveaus en
de mediaknoppen hebben voor 16 een eigen tekening op een 16-raster (lijn 1 op halve
pixels: scherp); de rest is de 24-tekening met lijn 1,5.

Let op, QtSvg (zo tekent KDE): een element met een eigen ColorScheme-klasse krijgt
die kleur alleen als het zelf ook stroke/fill="currentColor" heeft; clipPath werkt
niet, mask wel (Qt 6.11). En ColorScheme-Highlight is in BugOS de zachte
selectietint (#FDE9E9 / #3A1C22): voor een rode stip dus ColorScheme-NegativeText.
"""

from __future__ import annotations

import base as basis
from base import LIJN
from status_buttons import knop, l, tandwiel
from status_draw import (GROOT, KLEIN16, KLEIN24, NIVEAUS, R, Stuk, _gat_lijn, _gat_rond, _p, _stip, _vol, lijn,
                         met_klok, met_kruis, met_let_op, met_punt, met_slot, svg, uit)
from status_signs import (_info, _niveau, _vraag, batterij, bel, blad, bluetooth, camera, cijfers, cirkel,
                          door_elkaar, gekleurd, geluid, herhaal, hoofdletters, hotspot, kabel, media, meter,
                          microfoon, mobiel, ring, schakel, schild, sleutel, sneeuw, thermometer, toetsenbordlicht,
                          twee_personen, ups, vliegtuig, wifi, zon_zacht)


# Eigen 22-mappen (systeemvak, werkbalken). Ze staan in index.theme vóór */scalable,
# dus KDE kiest ze op precies 22 px; op 24 en groter blijft het */scalable.
basis.map_erbij("status/22", Size=22, Context="Status", Type="Fixed")
basis.map_erbij("actions/22", Size=22, Context="Actions", Type="Fixed")


# ================================================================ namen ===

def op22(tekst: str, boven: int = 1) -> str:
    """De 24-tekening voor precies 22 px: een viewBox van 22 eenheden, 1 eenheid = 1 pixel.

    Lijnen op hele eenheden vallen zo op hele pixels (scherp); verkleind naar 22 worden
    ze 1,83 px breed en wazig. Wat buiten 1..23 komt, valt weg; boven = 2 schuift het
    venster een eenheid omlaag voor tekeningen die tot 23,5 reiken (de bel)."""
    oud = 'width="24" height="24" viewBox="0 0 24 24"'
    if oud not in tekst:
        raise ValueError("op22 verwacht een 24-tekening")
    return tekst.replace(oud, f'width="22" height="22" viewBox="1 {boven} 22 22"', 1)


def _maak_beide(b: basis.Bouwer, soort: str, namen, teken, *, eigen16: bool = False, symbolic: bool = True,
                boven22: int = 1) -> None:
    """Schrijf teken(r) als <soort>/scalable, <soort>/22 en <soort>/16 onder alle namen."""
    if isinstance(namen, str):
        namen = [namen]
    groot = svg(teken(GROOT), GROOT)
    midden = op22(groot, boven22)
    r16 = KLEIN16 if eigen16 else KLEIN24
    klein = svg(teken(r16), r16)
    for naam in namen:
        b.schrijf(f"{soort}/scalable", naam, groot, symbolic_ook=symbolic)
        b.schrijf(f"{soort}/22", naam, midden, symbolic_ook=symbolic)
        b.schrijf(f"{soort}/16", naam, klein, symbolic_ook=symbolic)


def _geluid(b: basis.Bouwer) -> None:
    S = "status"
    _maak_beide(b, S, ["audio-volume-muted", "audio-off"], lambda r: geluid(r, stil=True), eigen16=True)
    _maak_beide(b, S, "audio-volume-low", lambda r: geluid(r, 1), eigen16=True)
    _maak_beide(b, S, "audio-volume-medium", lambda r: geluid(r, 2), eigen16=True)
    _maak_beide(b, S, ["audio-volume-high", "audio-on"], lambda r: geluid(r, 3), eigen16=True)
    _maak_beide(b, S, ["audio-volume-high-warning", "audio-volume-overamplified"],
                lambda r: geluid(r, 3, buitenste="ColorScheme-NeutralText"), eigen16=True)
    _maak_beide(b, S, "audio-volume-high-danger", lambda r: geluid(r, 3, buitenste="ColorScheme-NegativeText"), eigen16=True)
    _maak_beide(b, S, "audio-ready", lambda r: geluid(r, golven=0), eigen16=True)
    # microfoon: gevoeligheid = hoe vol het kopje is
    _maak_beide(b, S, ["microphone-sensitivity-muted", "audio-input-microphone-muted", "microphone-disabled"],
                lambda r: uit(microfoon(r), r), eigen16=True)
    _maak_beide(b, S, ["microphone-sensitivity-low", "audio-input-microphone-low"], lambda r: microfoon(r, 1), eigen16=True)
    _maak_beide(b, S, ["microphone-sensitivity-medium", "audio-input-microphone-medium"], lambda r: microfoon(r, 2), eigen16=True)
    _maak_beide(b, S, ["microphone-sensitivity-high", "audio-input-microphone-high"], lambda r: microfoon(r, 3), eigen16=True)
    _maak_beide(b, S, "audio-input-microphone", lambda r: microfoon(r), eigen16=True)


def _netwerk(b: basis.Bouwer) -> None:
    S = "status"
    for pct in NIVEAUS:
        n = _niveau(pct)
        _maak_beide(b, S, f"network-wireless-{pct}", lambda r, n=n: wifi(r, n))
        _maak_beide(b, S, f"network-wireless-{pct}-locked", lambda r, n=n: met_slot(wifi(r, n), r))
        _maak_beide(b, S, f"network-wireless-{pct}-limited", lambda r, n=n: met_let_op(wifi(r, n), r))
    for pct in (0, 20, 25, 40, 50, 60, 75, 80, 100):
        n = _niveau(pct)
        _maak_beide(b, S, f"network-wireless-connected-{pct:02d}", lambda r, n=n: wifi(r, n))
    for naam, pct in (("none", 0), ("weak", 20), ("ok", 40), ("good", 60), ("excellent", 100)):
        n = _niveau(pct)
        _maak_beide(b, S, f"network-wireless-signal-{naam}", lambda r, n=n: wifi(r, n))
    _maak_beide(b, S, ["network-wireless", "network-wireless-on", "network-wireless-connected"], lambda r: wifi(r))
    _maak_beide(b, S, ["network-wireless-off", "network-wireless-disabled"], lambda r: uit(wifi(r), r))
    _maak_beide(b, S, "network-wireless-disconnected", lambda r: met_kruis(wifi(r, 0), r))
    _maak_beide(b, S, ["network-wireless-available", "network-wireless-no-route"], lambda r: wifi(r, 0))
    _maak_beide(b, S, "network-wireless-acquiring", lambda r: met_klok(wifi(r, 0), r))
    _maak_beide(b, S, "network-wireless-hotspot", hotspot)
    # kabel
    _maak_beide(b, S, ["network-wired", "network-wired-available"], lambda r: kabel(r))
    _maak_beide(b, S, "network-wired-activated", lambda r: kabel(r, True))
    _maak_beide(b, S, "network-wired-activated-limited", lambda r: met_let_op(kabel(r, True), r))
    _maak_beide(b, S, "network-wired-activated-locked", lambda r: met_slot(kabel(r, True), r))
    _maak_beide(b, S, "network-wired-acquiring", lambda r: met_klok(kabel(r), r))
    _maak_beide(b, S, ["network-wired-disconnected", "network-wired-unavailable", "network-wired-no-route"],
                lambda r: met_kruis(kabel(r), r))
    # geen netwerk / geen internet: de wereldbol
    _maak_beide(b, S, ["network-offline", "network-unavailable", "network-error"], lambda r: met_kruis(lijn("wereld"), r))
    _maak_beide(b, S, "network-limited", lambda r: met_let_op(lijn("wereld"), r))
    _maak_beide(b, S, "network-vpn", schild)
    # mobiel
    for pct in NIVEAUS:
        n = _niveau(pct)
        _maak_beide(b, S, f"network-mobile-{pct}", lambda r, n=n: mobiel(r, n), eigen16=True)
        _maak_beide(b, S, f"network-mobile-{pct}-locked", lambda r, n=n: met_slot(mobiel(r, n), r), eigen16=True)
    _maak_beide(b, S, "network-mobile-on", lambda r: mobiel(r), eigen16=True)
    _maak_beide(b, S, "network-mobile-available", lambda r: mobiel(r, 0), eigen16=True)
    _maak_beide(b, S, "network-mobile-off", lambda r: uit(mobiel(r), r), eigen16=True)
    # vliegtuigstand (KDE en GNOME-namen)
    _maak_beide(b, S, ["network-flightmode-on", "airplane-mode"], vliegtuig)
    _maak_beide(b, S, ["network-flightmode-off", "airplane-mode-disabled"], lambda r: uit(vliegtuig(r), r))
    # bluetooth
    _maak_beide(b, S, ["network-bluetooth", "bluetooth", "bluetooth-active"], lambda r: bluetooth(r))
    _maak_beide(b, S, ["network-bluetooth-activated", "network-wireless-bluetooth", "bluetooth-paired"],
                lambda r: bluetooth(r, True))
    _maak_beide(b, S, "network-bluetooth-activated-locked", lambda r: met_slot(bluetooth(r, True), r))
    _maak_beide(b, S, ["network-bluetooth-inactive", "bluetooth-disabled"], lambda r: uit(bluetooth(r), r))


def _batterij(b: basis.Bouwer) -> None:
    S = "status"
    for pct in range(0, 101, 10):
        for laden in (False, True):
            naam = f"battery-{pct:03d}" + ("-charging" if laden else "")
            namen = [naam] + [f"{naam}-profile-{p}" for p in ("powersave", "balanced", "performance")]
            _maak_beide(b, S, namen, lambda r, pct=pct, laden=laden: batterij(r, pct, laden), eigen16=True)
            # GNOME-namen (alleen -symbolic)
            g = f"battery-level-{pct}" + ("-charging" if laden else "") + "-symbolic"
            _maak_beide(b, S, g, lambda r, pct=pct, laden=laden: batterij(r, pct, laden), eigen16=True, symbolic=False)
    for naam, pct in (("full", 100), ("good", 60), ("low", 20), ("caution", 10), ("empty", 0)):
        _maak_beide(b, S, f"battery-{naam}", lambda r, pct=pct: batterij(r, pct), eigen16=True)
        _maak_beide(b, S, f"battery-{naam}-charging", lambda r, pct=pct: batterij(r, pct, True), eigen16=True)
    _maak_beide(b, S, ["battery-full-charged", "battery-level-100-charged"], lambda r: batterij(r, 100, True), eigen16=True)
    _maak_beide(b, S, "battery-charging", lambda r: batterij(r, None, True), eigen16=True)
    kruisje = {16: _p("M5.5 6.5L8.5 9.5M8.5 6.5L5.5 9.5"), 24: _p("M8.5 9.5L13.5 14.5M13.5 9.5L8.5 14.5")}
    _maak_beide(b, S, "battery-missing", lambda r: batterij(r, None, leeg_teken=kruisje[r.raster]), eigen16=True)
    _maak_beide(b, S, "battery", l("batterij"))
    _maak_beide(b, S, "battery-ups", ups)
    _maak_beide(b, S, ["battery-profile-powersave", "power-profile-power-saver"], blad)
    _maak_beide(b, S, ["battery-profile-balanced", "power-profile-balanced"], lambda r: meter(r))
    _maak_beide(b, S, ["battery-profile-performance", "power-profile-performance"],
                lambda r: meter(r, "M12 13L17.4 11.2"))


def _scherm_en_meldingen(b: basis.Bouwer) -> None:
    S = "status"
    _maak_beide(b, S, ["brightness-high", "display-brightness", "display-brightness-high", "video-display-brightness",
                       "redshift-status-day"], l("zon"))
    _maak_beide(b, S, ["brightness-low", "display-brightness-low"], zon_zacht)
    _maak_beide(b, S, "input-keyboard-brightness", toetsenbordlicht)
    _maak_beide(b, S, ["redshift-status-on", "night-light"], l("maan"))
    _maak_beide(b, S, ["redshift-status-off", "night-light-disabled"], lambda r: uit(lijn("maan"), r))
    # meldingen (de bel reikt tot 23,5: op 22 px een eenheid hoger in beeld)
    _maak_beide(b, S, ["notification-inactive", "notifications", "notification-empty", "preferences-desktop-notification",
                       "preferences-desktop-notification-bell"], bel, boven22=2)
    _maak_beide(b, S, ["notification-active", "notification-new"], lambda r: met_punt(bel(r), r), boven22=2)
    _maak_beide(b, S, ["notifications-disabled", "notification-disabled"], lambda r: uit(bel(r), r), boven22=2)
    _maak_beide(b, S, ["notification-progress-inactive", "notification-progress-active"], ring)
    # toetsenbordlampjes, camera, temperatuur, klembord
    _maak_beide(b, S, ["input-caps-on", "input-combo-on"], hoofdletters)
    _maak_beide(b, S, "input-num-on", cijfers)
    _maak_beide(b, S, "camera-ready", lambda r: camera(r))
    _maak_beide(b, S, "camera-on", lambda r: camera(r, True))
    _maak_beide(b, S, ["camera-off", "camera-disabled"], lambda r: uit(camera(r), r))
    _maak_beide(b, S, "temperature-cold", lambda r: thermometer(r, 15))
    _maak_beide(b, S, "temperature-normal", lambda r: thermometer(r, 11.5))
    _maak_beide(b, S, "temperature-warm", lambda r: thermometer(r, 8))
    _maak_beide(b, S, "klipper-symbolic", l("plak"), symbolic=False)
    # vastgezette regels in het klembord (ster aan / uit)
    _maak_beide(b, S, "starred", lambda r: Stuk(LIJN["ster"].replace("<path ", '<path fill="currentColor" ')))
    _maak_beide(b, S, "non-starred", l("ster"))
    # berichten
    # (data-*: dezelfde berichten in Kirigami-dialogen, de schijvencontrole en het klembord)
    _maak_beide(b, S, ["dialog-information", "data-information"], lambda r: cirkel(_info()))
    _maak_beide(b, S, "dialog-question", lambda r: cirkel(_vraag()))
    _maak_beide(b, S, ["dialog-warning", "data-warning"], lambda r: gekleurd(Stuk(LIJN["uitroep"].replace(
        "M12 9.5v4.5M12 16.8v.3", "M12 9.5v4") + _stip(12, 16.6, 1.15)), "ColorScheme-NeutralText"))
    _maak_beide(b, S, ["dialog-error", "data-error"],
                lambda r: gekleurd(cirkel(_p("M9 9L15 15M15 9L9 15")), "ColorScheme-NegativeText"))
    _maak_beide(b, S, ["dialog-positive", "data-success"],
                lambda r: gekleurd(cirkel(_p("M8 12.5L10.8 15.2L16 9.5")), "ColorScheme-PositiveText"))
    _maak_beide(b, S, "dialog-password", sleutel)
    # media als toestand
    _maak_beide(b, S, "media-playback-playing", lambda r: media(r, "start"), eigen16=True)
    _maak_beide(b, S, "media-playback-paused", lambda r: media(r, "pause"), eigen16=True)
    _maak_beide(b, S, "media-playback-stopped", lambda r: media(r, "stop"), eigen16=True)
    # slaapstand tegengehouden of niet
    _maak_beide(b, S, "system-suspend-inhibited", lambda r: uit(lijn("maan"), r))
    _maak_beide(b, S, "system-suspend-uninhibited", l("maan"))


# Knoppen: naam(en) -> teken uit KNOPPEN.
ACTIES: list[tuple[list[str], str]] = [
    (["go-previous", "go-previous-view", "pan-start"], "links"),
    (["go-next", "go-next-view", "pan-end"], "rechts"),
    (["go-up", "pan-up", "collapse"], "boven"),
    (["go-down", "pan-down", "expand"], "onder"),
    (["go-first", "go-first-view"], "eerste"), (["go-last", "go-last-view"], "laatste"),
    (["go-top"], "top"), (["go-bottom"], "bodem"), (["go-home"], "huis"),
    # arrow-* is bij KDE (Breeze) een hoekje, geen pijl: het pijltje van het systeemvak, schuifbalken en sorteren.
    # Een hoekje, net als Windows 11 (^ naast de klok); de echte pijlen heten go-*.
    (["arrow-left"], "links"), (["arrow-right"], "rechts"), (["arrow-up"], "boven"), (["arrow-down"], "onder"),
    (["window-close", "dialog-close", "tab-close"], "kruis"), (["window-minimize"], "streep"),
    (["window-maximize"], "vierkant"), (["window-restore"], "terugzetten"),
    (["window-new"], "nieuw-venster"), (["window-pin"], "speld"),
    (["edit-copy"], "kopieer"), (["edit-cut"], "knip"), (["edit-paste"], "plak"),
    (["edit-delete", "edit-delete-remove", "entry-delete"], "weg"),
    (["edit-find", "edit-find-replace", "search", "system-search"], "zoek"),
    (["edit-undo"], "ongedaan"), (["edit-redo"], "opnieuw"),
    (["edit-reset", "document-revert"], "herstel"),   # document-revert: de knop Standaard in elke KDE-instelling
    (["edit-rename"], "hernoem"), (["edit-entry", "entry-edit", "document-edit"], "potlood"),
    (["edit-select-all"], "alles"), (["edit-select-none"], "niets"),
    (["edit-clear"], "wis-veld"),
    (["edit-clear-locationbar-rtl"], "backspace"), (["edit-clear-locationbar-ltr"], "backspace-r"),
    (["edit-clear-all", "edit-clear-history"], "gum"),
    (["edit-none", "dialog-cancel"], "geen"),
    (["list-add"], "plus"), (["list-remove"], "min"),
    (["dialog-ok", "dialog-ok-apply", "dialog-apply", "object-select", "checkmark"], "vink"),
    (["view-refresh", "system-reboot"], "verversen"),
    (["view-more", "view-more-horizontal"], "meer-liggend"),
    (["overflow-menu", "overflow-menu-left", "overflow-menu-right"], "meer-staand"),
    (["application-menu", "open-menu", "show-menu"], "menu"),
    (["view-list-details"], "lijst"), (["view-list-icons", "view-grid"], "tegels"),
    (["view-list-text"], "tekstlijst"), (["view-list-tree"], "boom"),
    (["view-visible"], "oog"), (["view-filter"], "trechter"),
    (["view-sort-ascending", "view-sort"], "sorteer-op"), (["view-sort-descending"], "sorteer-neer"),
    (["view-barcode-qr"], "qr"), (["view-fullscreen", "zoom-fit-best"], "groot"), (["view-restore"], "klein"),
    (["view-history", "document-open-recent"], "geschiedenis"),
    (["zoom-in"], "inzoomen"), (["zoom-out"], "uitzoomen"), (["zoom-original"], "zoek"),
    (["document-open", "document-open-folder"], "open"), (["document-save", "document-save-as"], "bewaar"),
    (["document-new"], "nieuw"), (["document-properties"], "document"), (["document-send"], "versturen"),
    (["document-share"], "delen"), (["document-print"], "printer"),
    (["process-stop"], "stop"),
    (["help-contents", "help-contextual", "help-faq"], "vraag"), (["help-about", "help-hint"], "info"),
    (["configure", "settings-configure"], "tandwiel"),
    (["media-eject"], "uitwerpen"), (["media-album-cover"], "muziek"),
    (["system-shutdown"], "aan"), (["system-log-out", "application-exit"], "deur"),
    (["system-suspend"], "maan"), (["system-lock-screen"], "slot"),
    (["contrast"], "contrast"), (["speedometer"], "meter"),
    (["network-connect"], "schakel"),
    # gevraagd door KDE Instellingen, KDE-dialogen (KStandardGuiItem/KStandardAction) en het KWin-venstermenu
    (["document-import"], "importeer"), (["document-export"], "exporteer"), (["view-preview"], "voorbeeld"),
    (["window-keep-above"], "boven-houden"), (["window-keep-below"], "onder-houden"),
    (["transform-move"], "verplaats"), (["transform-scale"], "schaal"),
    (["configure-shortcuts"], "sneltoetsen"), (["document-close"], "sluit-document"), (["go-jump"], "spring"),
    (["arrow-left-double"], "dubbel-links"), (["arrow-right-double"], "dubbel-rechts"),
]


def _knoppen(b: basis.Bouwer) -> None:
    A = "actions"
    for namen, teken in ACTIES:
        _maak_beide(b, A, namen, knop(teken))
    _maak_beide(b, A, ["view-hidden", "view-visible-off"], lambda r: uit(lijn("oog"), r))
    _maak_beide(b, A, "window-unpin", lambda r: uit(knop("speld")(r), r))
    _maak_beide(b, A, "network-disconnect", lambda r: uit(schakel(r), r))
    _maak_beide(b, A, ["system-suspend-hibernate", "system-hibernate"], sneeuw)
    _maak_beide(b, A, "system-switch-user", twee_personen)
    _maak_beide(b, A, "system-reboot-update", lambda r: met_punt(knop("verversen")(r), r))
    _maak_beide(b, A, "system-shutdown-update", lambda r: met_punt(lijn("aan"), r))
    # media
    for namen, wat in ((["media-playback-start"], "start"), (["media-playback-pause"], "pause"),
                       (["media-playback-stop"], "stop"), (["media-skip-forward"], "volgende"),
                       (["media-skip-backward"], "vorige"), (["media-seek-forward"], "vooruit"),
                       (["media-seek-backward"], "terug"), (["media-record"], "opnemen")):
        _maak_beide(b, A, namen, lambda r, wat=wat: media(r, wat), eigen16=True)
    _maak_beide(b, A, "media-playlist-repeat", lambda r: herhaal(r))
    _maak_beide(b, A, "media-playlist-repeat-song", lambda r: herhaal(r, True))
    _maak_beide(b, A, "media-playlist-shuffle", door_elkaar)


# ---- emblemen: een gekleurde stip met een uitgespaard teken (16-raster) ----

EMBLEEM = R(16, 2, 16)


def _embleem(klasse: str, gat: str) -> str:
    stuk = Stuk(f'<circle cx="8" cy="8" r="7"{_vol(klasse)}/>').snij(gat)
    return svg(stuk, EMBLEEM)


def _emblemen(b: basis.Bouwer) -> None:
    E = "emblems/scalable"
    G = "ColorScheme-PositiveText"
    N = "ColorScheme-NegativeText"
    T = "ColorScheme-Text"

    def lijn16(d: str, w: float = 2) -> str:
        return _gat_lijn(d, w)
    vink = lijn16("M4.75 8.25L7 10.5L11.25 6")
    kruis = lijn16("M5.5 5.5L10.5 10.5M10.5 5.5L5.5 10.5")
    uitroep = lijn16("M8 4.25V8.25") + _gat_rond(8, 11.1, 1.15)
    info = lijn16("M8 7.25V11.25") + _gat_rond(8, 4.75, 1.15)
    vraag = lijn16("M6 6.2A2 2 0 1 1 8.8 8C8.3 8.3 8 8.7 8 9.3V9.4", 1.7) + _gat_rond(8, 11.5, 1)
    plus = lijn16("M8 4.5V11.5M4.5 8H11.5")
    min_ = lijn16("M4.5 8H11.5")
    pauze = lijn16("M6.25 5V11M9.75 5V11")
    slot = ('<rect x="5" y="7.5" width="6" height="4.5" rx="1" fill="#000"/>' +
            lijn16("M6.25 7.5V6.25A1.75 1.75 0 0 1 9.75 6.25V7.5", 1.5))
    open_slot = ('<rect x="5" y="7.5" width="6" height="4.5" rx="1" fill="#000"/>' +
                 lijn16("M6.25 7.5V5.75A1.75 1.75 0 0 1 9.75 5.75", 1.5))
    koppeling = lijn16("M5 11V9.5A2.5 2.5 0 0 1 7.5 7H11M9 5L11 7L9 9", 1.7)
    streep = lijn16("M4.75 4.75L11.25 11.25")
    persoon = _gat_rond(8, 6, 2) + lijn16("M4.6 12A3.4 3.4 0 0 1 11.4 12", 1.7)
    eject = '<path d="M8 4.25L11.25 8.25H4.75Z" fill="#000"/>' + lijn16("M4.75 11H11.25", 1.7)

    for namen, klasse, gat in (
            (["emblem-ok", "emblem-success", "emblem-checked", "emblem-mounted"], G, vink),
            (["emblem-added", "emblem-new"], G, plus),
            (["emblem-error", "emblem-unreadable"], N, kruis),
            (["emblem-important"], N, uitroep),
            (["emblem-remove"], N, min_),
            (["emblem-information"], T, info), (["emblem-question"], T, vraag),
            (["emblem-pause"], T, pauze),
            (["emblem-locked", "emblem-readonly", "emblem-encrypted-locked"], T, slot),
            (["emblem-unlocked", "emblem-encrypted-unlocked"], T, open_slot),
            (["emblem-symbolic-link"], T, koppeling), (["emblem-unavailable"], T, streep),
            (["emblem-shared"], T, persoon), (["emblem-unmounted"], T, eject)):
        bestand = _embleem(klasse, gat)
        for naam in namen:
            b.schrijf(E, naam, bestand)
    # waarschuwing: oranje driehoek
    driehoek = Stuk('<path d="M8 1.5L15 14H1Z" class="ColorScheme-NeutralText" fill="currentColor" '
                    'stroke="currentColor" stroke-width="1.5"/>').snij(lijn16("M8 6V9.25") + _gat_rond(8, 11.75, 1.1))
    b.schrijf(E, "emblem-warning", svg(driehoek, EMBLEEM))
    # favoriet: gevulde ster (de warme waarschuwingskleur: goud in donker)
    ster = LIJN["ster"].replace("<path ", '<path class="ColorScheme-NeutralText" fill="currentColor" stroke="currentColor" ')
    b.schrijf(E, "emblem-favorite", svg(Stuk(ster), GROOT))
    # -symbolic emblemen zijn bij Breeze gewone lijntekens (ook als pictogram in KDE Instellingen)
    for naam, teken in (("emblem-music-symbolic", "muziek"), ("emblem-photos-symbolic", "foto"),
                        ("emblem-videos-symbolic", "film"), ("emblem-documents-symbolic", "document"),
                        ("emblem-ok-symbolic", "vink"), ("emblem-default-symbolic", "vink"),
                        ("emblem-important-symbolic", "uitroep"), ("emblem-favorite-symbolic", "ster"),
                        ("emblem-synchronizing-symbolic", "verversen")):
        b.schrijf(E, naam, svg(lijn(teken), GROOT))
    b.schrijf(E, "emblem-system-symbolic", svg(tandwiel(GROOT), GROOT))
    b.schrijf(E, "emblem-shared-symbolic", svg(knop("delen")(GROOT), GROOT))


def maak(b: basis.Bouwer) -> None:
    _geluid(b)
    _netwerk(b)
    _batterij(b)
    _scherm_en_meldingen(b)
    _knoppen(b)
    _emblemen(b)
