#!/usr/bin/python3
"""Schermfoto via KWin zelf (org.kde.KWin.ScreenShot2), voor als Spectacle er niet is.

Draait in het BugOS-beeld, binnen een KWin-sessie. KWin schrijft de ruwe beeldpunten in een
pijp; wij maken er een PNG van (zonder extra bibliotheken).

Gebruik:  python3 schermfoto.py <uit.png>
KWin moet gestart zijn met KWIN_WAYLAND_NO_PERMISSION_CHECKS=1, anders mag alleen Spectacle dit.
"""

import os
import struct
import sys
import zlib


def png_schrijven(pad: str, breedte: int, hoogte: int, stride: int, data: bytes) -> None:
    """Ruwe BGRA-beeldpunten (zoals QImage ARGB32 op een gewone pc) -> PNG in RGB."""
    def blok(soort: bytes, inhoud: bytes) -> bytes:
        return struct.pack(">I", len(inhoud)) + soort + inhoud + struct.pack(">I", zlib.crc32(soort + inhoud) & 0xFFFFFFFF)

    rijen = bytearray()
    for y in range(hoogte):
        rij = data[y * stride:y * stride + breedte * 4]
        rijen.append(0)  # filter: geen
        # B,G,R,A -> R,G,B
        rijen += bytes(v for i in range(0, len(rij), 4) for v in (rij[i + 2], rij[i + 1], rij[i]))
    kop = struct.pack(">IIBBBBB", breedte, hoogte, 8, 2, 0, 0, 0)
    with open(pad, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + blok(b"IHDR", kop) + blok(b"IDAT", zlib.compress(bytes(rijen), 6)) + blok(b"IEND", b""))


def main() -> int:
    if len(sys.argv) != 2:
        print("Gebruik: schermfoto.py <uit.png>", file=sys.stderr)
        return 2
    try:
        import gi  # noqa: PLC0415
        gi.require_version("Gio", "2.0")
        from gi.repository import Gio, GLib  # noqa: PLC0415
    except (ImportError, ValueError) as e:
        print(f"FOUT: python3-gobject ontbreekt ({e}); geen schermfoto via D-Bus mogelijk.", file=sys.stderr)
        return 1
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    lees, schrijf = os.pipe()
    fds = Gio.UnixFDList.new()
    idx = fds.append(schrijf)
    os.close(schrijf)
    opties = {"include-cursor": GLib.Variant("b", False)}
    antwoord = None
    for methode, args in (("CaptureActiveScreen", GLib.Variant("(a{sv}h)", (opties, idx))),
                          ("CaptureWorkspace", GLib.Variant("(a{sv}h)", (opties, idx)))):
        try:
            antwoord, _fds = bus.call_with_unix_fd_list_sync(
                "org.kde.KWin", "/org/kde/KWin/ScreenShot2", "org.kde.KWin.ScreenShot2", methode, args,
                GLib.VariantType("(a{sv})"), Gio.DBusCallFlags.NONE, 30000, fds, None)
            break
        except GLib.Error as e:
            print(f"{methode} lukte niet: {e.message}", file=sys.stderr)
    if antwoord is None:
        os.close(lees)
        return 1
    info = antwoord.unpack()[0]
    breedte, hoogte, stride = int(info["width"]), int(info["height"]), int(info["stride"])
    nodig = stride * hoogte
    data = bytearray()
    with os.fdopen(lees, "rb") as pijp:
        while len(data) < nodig:
            stuk = pijp.read(min(1 << 20, nodig - len(data)))
            if not stuk:
                break
            data += stuk
    if len(data) < nodig:
        print(f"FOUT: te weinig beeldgegevens ({len(data)} van {nodig} bytes).", file=sys.stderr)
        return 1
    png_schrijven(sys.argv[1], breedte, hoogte, stride, bytes(data))
    print(f"Schermfoto {breedte}x{hoogte} -> {sys.argv[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
