"""De zachte map, prullenbak en server, de lijnversies en de map- en apparatentabellen (voor places.py)."""

from __future__ import annotations

from base import klein, symbolisch
from places_colors import LAGEN, _afgerond, _hex
from places_svg import EIGEN, MAP_LIJN, _g, _rrect, _svg, _veelhoek, pad
from tokens import LIJN, ROOD, TINTEN


# --------------------------------------------------------------------- de zachte map ---
# Verhoudingen uit teken_map() in bugos-files (daar 84 x 66 beeldpunten).
ML, MT, MW, MH = 3.0, 8.0, 42.0, 33.0     # links, boven, breedte, hoogte op het 48-raster
MR = MW * 0.085                           # hoekstraal
VOOR_Y = MT + MH * 0.24                   # bovenkant van de voorkant


def _stapel(d: str, laag: tuple, tint: str | None = None) -> str:
    """Een vlak dat meekleurt: vensterkleur, dan vast grijs, dan het BugOS-rood (of een andere tint)."""
    g, og, oh = _afgerond(laag)
    grijs = _hex((g, g, g))
    return (f'<path class="ColorScheme-Background" fill="currentColor" d="{d}"/>'
            f'<path fill="{grijs}" fill-opacity="{_g(og)}" d="{d}"/>'
            f'<path fill="{tint or ROOD}" fill-opacity="{_g(oh)}" d="{d}"/>')


def _streep(d: str, laag: tuple, tint: str | None, breedte: float, transform: str = "") -> str:
    """Een lijntekening in de kleur van het tekentje (wit, dan rood, dan tekstkleur)."""
    ow, oh, ot = _afgerond(laag)
    t = f' transform="{transform}"' if transform else ""
    gemeen = f'fill="none" stroke-width="{_g(breedte)}" stroke-linecap="round" stroke-linejoin="round" d="{d}"'
    return (f"<g{t}>"
            f'<path stroke="#FFFFFF" stroke-opacity="{_g(ow)}" {gemeen}/>'
            f'<path stroke="{tint or ROOD}" stroke-opacity="{_g(oh)}" {gemeen}/>'
            f'<path class="ColorScheme-Text" stroke="currentColor" stroke-opacity="{_g(ot)}" {gemeen}/>'
            "</g>")


def _papier_vlak(d: str, rand: float = 0.16, licht: float = 0.05) -> str:
    """Papier in de kleur van een kaart: vensterkleur, iets opgelicht, met een haarlijn.

    licht: hoeveel wit erover. 0.05 geeft in donker de kaartkleur van Bestanden; in een open map
    is meer nodig, anders leest het velletje in donker als een zwarte gleuf."""
    return (f'<path class="ColorScheme-Background" fill="currentColor" d="{d}"/>'
            f'<path fill="#FFFFFF" fill-opacity="{_g(licht)}" d="{d}"/>'
            f'<path class="ColorScheme-Text" fill="none" stroke="currentColor" stroke-opacity="{_g(rand)}" '
            f'stroke-width="0.75" stroke-linejoin="round" d="{d}"/>')


def _glyph_op_map(teken: str, tint: str | None, cy: float | None = None) -> str:
    m = MH * 0.38
    cx = ML + MW / 2
    if cy is None:
        cy = (VOOR_Y + MT + MH) / 2 + MH * 0.02
    s = m / 24
    return _streep(pad(teken), LAGEN["teken"], tint, 2.2,
                   f"translate({_g(cx - m / 2)} {_g(cy - m / 2)}) scale({_g(s)})")


def map_svg(teken: str | None = None, tint: str | None = None, open_: bool = False) -> str:
    """De zachte BugOS-map op het 48-raster (zie teken_map in bugos-files)."""
    tab = _rrect(ML, MT, MW * 0.44, MH * 0.32, MR)
    achter = _rrect(ML, MT + MH * 0.1, MW, MH * 0.9, MR)
    delen = [_stapel(tab, LAGEN["achter"], tint), _stapel(achter, LAGEN["achter"], tint)]
    onder = MT + MH
    if open_:
        delen.append(_papier_vlak(_rrect(ML + 4, MT + MH * 0.2, MW - 8, MH * 0.6, 1.5), 0.2, licht=0.3))
        boven = MT + MH * 0.36
        voor = _veelhoek([(ML + 4.5, boven), (ML + MW + 1.5, boven), (ML + MW, onder), (ML, onder)], MR)
        delen.append(_stapel(voor, LAGEN["voor"], tint))
        lijn_y = boven + 0.5
        delen.append(f'<path d="M{_g(ML + 4.5 + MR)} {_g(lijn_y)}H{_g(ML + MW + 1.5 - MR)}" stroke="#FFFFFF" '
                     f'stroke-opacity="0.35" stroke-width="0.75" stroke-linecap="round"/>')
        if teken:
            delen.append(_glyph_op_map(teken, tint, (boven + onder) / 2 + MH * 0.02))
    else:
        voor = _rrect(ML, VOOR_Y, MW, onder - VOOR_Y, MR)
        delen.append(_stapel(voor, LAGEN["voor"], tint))
        delen.append(f'<path d="M{_g(ML + MR)} {_g(VOOR_Y + 0.5)}H{_g(ML + MW - MR)}" stroke="#FFFFFF" '
                     f'stroke-opacity="0.35" stroke-width="0.75" stroke-linecap="round"/>')
        if teken:
            delen.append(_glyph_op_map(teken, tint))
    return _svg("".join(delen))


def prullenbak_svg(vol: bool = False) -> str:
    """De prullenbak in dezelfde zachte tint als de mappen."""
    delen = []
    if vol:
        for x, y, hoek in ((13.5, 3.5, -8), (23, 2.5, 10)):
            vel = _rrect(x, y, 11, 13, 1.5)
            regels = f"M{_g(x + 2.5)} {_g(y + 4)}h6M{_g(x + 2.5)} {_g(y + 7)}h4.5"
            delen.append(f'<g transform="rotate({hoek} {_g(x + 5.5)} {_g(y + 6.5)})">{_papier_vlak(vel, 0.3)}'
                         f'<path class="ColorScheme-Text" fill="none" stroke="currentColor" stroke-opacity="0.3" '
                         f'stroke-width="1" stroke-linecap="round" d="{regels}"/></g>')
    lid = _stapel(_rrect(19, 6.5, 10, 6, 2), LAGEN["achter"]) + _stapel(_rrect(9, 10, 30, 5, 2.2), LAGEN["achter"])
    if vol:
        lid = f'<g transform="rotate(-14 38 14) translate(0 -2.5)">{lid}</g>'
    lijf = _veelhoek([(11.5, 15), (36.5, 15), (34.5, 42), (13.5, 42)], 3.2)
    delen.append(_stapel(lijf, LAGEN["voor"]))
    delen.append(f'<path d="M{_g(13.5)} {_g(15.5)}H{_g(34.5)}" stroke="#FFFFFF" stroke-opacity="0.35" '
                 f'stroke-width="0.75" stroke-linecap="round"/>')
    delen.append(lid)
    delen.append(_streep("M19 21v14M24 21v14M29 21v14", LAGEN["teken"], None, 1.6))
    return _svg("".join(delen))


def server_svg() -> str:
    """Een server (twee kastjes) in de zachte maptint."""
    delen = []
    for y in (8.5, 25.5):
        delen.append(_stapel(_rrect(7, y, 34, 14, 3.5), LAGEN["voor"]))
        delen.append(f'<path d="M{_g(10.5)} {_g(y + 0.5)}H{_g(37.5)}" stroke="#FFFFFF" stroke-opacity="0.35" '
                     f'stroke-width="0.75" stroke-linecap="round"/>')
        delen.append(_streep(f"M13 {_g(y + 7)}h.01M22 {_g(y + 7)}h13", LAGEN["teken"], None, 2.2))
    return _svg("".join(delen))


# ------------------------------------------------------------------- de lijnversies ---

def _klein_set(binnen: str) -> dict[str, str]:
    """Dezelfde lijntekening voor 16 px, 22 px en schaalbaar (24-raster)."""
    return {"16": klein(binnen), "22": symbolisch(binnen, maat=22), "scalable": symbolisch(binnen)}


BINNEN_LIJN = 1.35   # lijndikte van een klein tekentje in een map of papiertje (24-raster)


def _map_met_klein(glyph: str, schaal: float = 0.4) -> str:
    """Mapomtrek met een klein tekentje erin (zoals map-plus in LIJN)."""
    return (f"{MAP_LIJN}<g transform=\"translate(12 13.4) scale({_g(schaal)}) translate(-12 -12)\" "
            f"stroke-width=\"{_g(BINNEN_LIJN / schaal)}\"><path d=\"{pad(glyph)}\"/></g>")


def _lijnset(soort: str, glyph: str | None) -> dict[str, str]:
    """soort: 'teken' (alleen het tekentje, zoals de zijbalk van Bestanden), 'map', 'met' of 'open'."""
    if soort == "teken":
        return _klein_set(EIGEN.get(glyph) or LIJN[glyph])
    if soort == "map":
        return _klein_set(MAP_LIJN)
    if soort == "open":
        return _klein_set(EIGEN["map-open"])
    if soort == "met":
        binnen = _map_met_klein(glyph)
        return {"16": klein(binnen), "22": symbolisch(binnen, maat=22), "scalable": symbolisch(binnen)}
    raise ValueError(soort)


# --------------------------------------------------------------------- mappen-tabel ---
# (namen, tekentje op de grote map, kleine versie)
# Klein: 'teken' = alleen het lijnicoon (zoals de zijbalk van Bestanden en zoals Breeze op
# 16 en 22 px), 'met' = mapomtrek met een eenvoudig tekentje erin, 'map' = alleen de
# mapomtrek. Een klein tekentje ín een mapomtrek wordt op 16 px een vlekje; daarom krijgen
# de bijzondere mappen klein alleen hun tekentje. Alleen het uitroepteken (één streepje)
# blijft leesbaar in de map. Openbaar en Sjablonen hebben in Bestanden geen tekentje; hier
# dus ook niet.
MAPPEN = [
    (["folder", "inode-directory", "folder-red", "folder-templates", "folder-publicshare", "folder-public",
      "folder-root"], None, ("map", None)),
    (["folder-open"], None, ("open", None)),
    (["folder-documents", "folder-txt", "folder-text", "folder-log"], "document", ("teken", "document")),
    (["folder-download", "folder-downloads"], "download", ("teken", "download")),
    (["folder-pictures", "folder-images", "folder-image", "folder-picture"], "foto", ("teken", "foto")),
    (["folder-music", "folder-sound", "folder-podcast"], "muziek", ("teken", "muziek")),
    (["folder-videos", "folder-video"], "film", ("teken", "film")),
    (["folder-desktop", "user-desktop"], "computer", ("teken", "computer")),
    (["folder-home", "user-home"], "huis", ("teken", "huis")),
    (["folder-network", "network-workgroup"], "wereld", ("teken", "wereld")),
    (["folder-remote"], "wereld", ("teken", "wereld")),
    # wolkdiensten (kio-gdrive vraagt folder-gdrive in het Netwerk-overzicht van Dolphin)
    (["folder-cloud", "folder-gdrive", "folder-dropbox", "folder-onedrive", "folder-owncloud"], "wolk",
     ("teken", "wolk")),
    (["folder-recent", "folder-open-recent"], "klok", ("teken", "klok")),
    (["folder-favorites", "folder-bookmark"], "ster", ("teken", "ster")),
    (["folder-saved-search"], "zoek", ("teken", "zoek")),
    (["folder-important"], "belangrijk", ("met", "belangrijk")),
    (["folder-temp"], "zandloper", ("teken", "zandloper")),
    (["folder-development", "folder-script", "folder-build", "folder-git", "folder-java", "folder-html"],
     "code", ("teken", "code")),
    (["folder-games", "folder-godot"], "spel", ("teken", "spel")),
    (["folder-locked", "folder-encrypted"], "slot", ("teken", "slot")),
    (["folder-unlocked", "folder-decrypted"], "slot-open", ("teken", "slot-open")),
    (["folder-mail"], "envelop", ("teken", "envelop")),
    (["folder-print"], "printer", ("teken", "printer")),
    (["folder-tar", "folder-appimage", "folder-deb", "folder-rpm", "folder-snap", "folder-flatpak",
      "folder-docker"], "doos", ("teken", "doos")),
    (["folder-trash"], "prullenbak", ("teken", "prullenbak")),
    # KDE Connect vraagt folder-book (de map Boeken op de telefoon)
    (["folder-book", "folder-library"], "boek", ("teken", "boek")),
    (["folder-android"], "telefoon", ("teken", "telefoon")),
    (["folder-windows", "folder-mac"], "computer", ("teken", "computer")),
    (["folder-design", "folder-drawing", "folder-paint", "folder-blender"], "palet", ("teken", "palet")),
    (["folder-notes", "folder-sign"], "potlood", ("teken", "potlood")),
    (["folder-chart", "folder-presentation", "folder-calculate"], "grafiek", ("teken", "grafiek")),
    (["folder-table", "folder-activities", "folder-extension"], "apps", ("teken", "apps")),
    (["folder-comic"], "praten", ("teken", "praten")),
    (["folder-crash"], "uitroep", ("teken", "uitroep")),
    (["folder-database"], "opslag", ("teken", "opslag")),
    (["folder-image-people"], "persoon", ("teken", "persoon")),
    (["folder-language"], "letter", ("teken", "letter")),
]
EIGEN["doos"] = ('<rect x="3.5" y="4.5" width="17" height="4.5" rx="1.5"/>'
                 '<path d="M5 9v9.5A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5V9M10 12.5h4"/>')

# Gekleurde mappen (Dolphin: "Mappictogram wijzigen"): dezelfde map in een rustige tint.
KLEURMAPPEN = {
    "folder-blue": TINTEN["blauw"], "folder-green": TINTEN["groen"], "folder-yellow": TINTEN["geel"],
    "folder-orange": TINTEN["oranje"], "folder-brown": TINTEN["oranje"], "folder-violet": TINTEN["paars"],
    "folder-magenta": TINTEN["roze"], "folder-cyan": TINTEN["turkoois"], "folder-grey": TINTEN["grijs"],
    "folder-black": TINTEN["grijs"],
}


# ------------------------------------------------------------------ apparaten-tabel ---
# lijnicoon -> namen (devices/16 en devices/scalable, met -symbolic erbij)
APPARATEN = {
    "computer": ["computer", "video-display"],
    "laptop": ["computer-laptop"],
    "opslag": ["drive-harddisk", "drive-harddisk-solidstate", "drive-harddisk-root", "drive-harddisk-system",
               "drive-harddisk-usb", "drive-harddisk-ieee1394", "drive-harddisk-encrypted", "drive", "drive-partition",
               "drive-multipartition"],
    "schijven": ["drive-multidisk"],
    "usb": ["drive-removable-media", "drive-removable-media-usb", "drive-removable-media-usb-pendrive",
            "media-removable"],
    "cd": ["drive-optical", "media-optical", "media-optical-audio", "media-optical-cd", "media-optical-cd-audio",
           "media-optical-cd-r", "media-optical-dvd", "media-optical-dvd-video", "media-optical-blu-ray",
           "media-optical-bd", "media-optical-data", "media-optical-recordable", "media-optical-mixed-cd",
           "media-optical-video"],
    "kaart": ["media-flash", "media-flash-sd-mmc", "media-flash-memory-stick", "media-flash-smart-media"],
    "diskette": ["media-floppy"],
    # Solid en kio-mtp: een Android-telefoon heet multimedia-player, een iPhone phone-apple-iphone.
    # Het systeemvak vraagt <naam>-symbolic van het laatst aangesloten apparaat.
    "telefoon": ["phone", "smartphone", "multimedia-player", "phone-apple-iphone",
                 "multimedia-player-apple-ipod-touch"],
    "tablet": ["computer-apple-ipad"],
    "printer": ["printer", "printer-network"],
    "toetsenbord": ["input-keyboard"],
    "muis": ["input-mouse"],
    "spel": ["input-gaming", "input-gamepad"],
    "tekentablet": ["input-tablet"],
    "touchpad": ["input-touchpad"],
    "geluidskaart": ["audio-card"],
    "koptelefoon": ["audio-headphones"],
    "headset": ["audio-headset"],
    "luidspreker": ["audio-speakers"],
    "camera": ["camera-photo"],
    "videocamera": ["camera-video"],
    "webcam": ["camera-web"],
    "netwerkkaart": ["network-card"],
    "chip": ["cpu", "preferences-devices-cpu"],
    "geheugen": ["memory"],
    "uitwerpschijf": ["device-notifier"],
}
