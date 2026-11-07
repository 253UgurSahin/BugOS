#!/usr/bin/env python3
"""BugOS-kleuren voor de Terminal (Konsole), licht en donker.

Schrijft:
  system_files/usr/share/konsole/BugOS.colorscheme         (licht)
  system_files/usr/share/konsole/BugOSDark.colorscheme   (donker)
  system_files/usr/share/konsole/BugOS.profile             (licht: kleuren, JetBrains Mono, wat ruimte)
  system_files/usr/share/konsole/BugOSDark.profile       (donker)

Jip-en-Janneke: Konsole gebruikt niet het kleurenschema van KDE, maar een eigen
lijstje van 8 (x3) kleuren. Die maken we hier uit dezelfde BugOS-kleuren als de rest:
rood = het BugOS-rood, groen = "goed", geel = "let op", enzovoort. Elke kleur
wordt bijgeschoven tot hij goed leesbaar is (contrast 4,5 op de achtergrond).
bugos-theme licht|donker kiest het passende profiel, als je zelf geen ander koos.

Eén bron: tools/design/tokens.py (dus bugos_ui.py).

Gebruik:  python3 tools/konsole/make.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER.parent / "design"))

from tokens import KLEUREN, LETTERS, REPO, TINTEN, rgb  # noqa: E402

UIT = REPO / "system_files" / "usr" / "share" / "konsole"
#: thema -> (naam van het kleurenschema en profiel, beschrijving)
THEMAS = {"licht": ("BugOS", "BugOS Light"), "donker": ("BugOSDark", "BugOS Dark")}


def hexk(c) -> str:
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(v))) for v in c)


def meng(a: str, b: str, t: float) -> str:
    ra, rb = rgb(a), rgb(b)
    return hexk(tuple(x + (y - x) * t for x, y in zip(ra, rb)))


def lum(h: str) -> float:
    def kanaal(v: int) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb(h)
    return 0.2126 * kanaal(r) + 0.7152 * kanaal(g) + 0.0722 * kanaal(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def leesbaar(kleur: str, achter: str, naar: str, doel: float = 4.5) -> str:
    """Schuif `kleur` stapje voor stapje richting `naar` tot hij `doel` haalt op `achter`."""
    for stap in range(21):
        k = meng(kleur, naar, stap * 0.05)
        if contrast(k, achter) >= doel:
            return k
    return meng(kleur, naar, 1.0)


def palet(thema: str) -> dict[str, str]:
    k = KLEUREN[thema]
    donker = thema == "donker"
    achter = k["achter"] if donker else k["vlak"]
    tekst = k["tekst"]
    naar = "#FFFFFF" if donker else "#000000"
    basis = {
        "rood": k["fout"], "groen": k["goed"], "geel": k["let_op"], "blauw": TINTEN["blauw"],
        "paars": TINTEN["paars"], "cyaan": TINTEN["turkoois"],
    }
    p = {n: leesbaar(c, achter, naar) for n, c in basis.items()}
    p["zwart"] = k["rand_sterk"] if donker else tekst
    p["wit"] = k["tekst2"] if donker else k["rand_sterk"]
    return {"achter": achter, "tekst": tekst, **p}


VOLGORDE = ("zwart", "rood", "groen", "geel", "blauw", "paars", "cyaan", "wit")


def kleurenschema(thema: str) -> str:
    naam, beschrijving = THEMAS[thema]
    p = palet(thema)
    donker = thema == "donker"
    fel = "#FFFFFF" if donker else "#000000"

    def regel(groep: str, kleur: str) -> str:
        return f"[{groep}]\nColor={','.join(str(v) for v in rgb(kleur))}\n\n"

    uit = [f"# BugOS-kleuren voor de Terminal. Gemaakt door tools/konsole/make.py: niet met de hand aanpassen.\n\n"]
    uit.append(regel("Background", p["achter"]))
    uit.append(regel("BackgroundIntense", p["achter"]))
    uit.append(regel("BackgroundFaint", p["achter"]))
    for i, n in enumerate(VOLGORDE):
        uit.append(regel(f"Color{i}", p[n]))
        # Fel: iets sterker (dichter bij zwart/wit); zwak: halverwege naar de achtergrond.
        fel_kleur = KLEUREN[thema]["tekst3"] if n == "zwart" else (
            KLEUREN[thema]["tekst"] if n == "wit" else meng(p[n], fel, 0.2))
        uit.append(regel(f"Color{i}Intense", fel_kleur))
        uit.append(regel(f"Color{i}Faint", meng(p[n], p["achter"], 0.4)))
    uit.append(regel("Foreground", p["tekst"]))
    uit.append(regel("ForegroundIntense", p["tekst"]))
    uit.append(regel("ForegroundFaint", meng(p["tekst"], p["achter"], 0.4)))
    uit.append(f"[General]\nAnchor=0.5,0.5\nBlur=false\nColorRandomization=false\n"
               f"Description={beschrijving}\nFillStyle=Tile\nOpacity=1\nWallpaper=\nWallpaperFlipType=NoFlip\n"
               f"WallpaperOpacity=1\n")
    return "".join(uit)


def profiel(thema: str) -> str:
    naam, beschrijving = THEMAS[thema]
    return (
        "# BugOS-profiel voor de Terminal. Gemaakt door tools/konsole/make.py: niet met de hand aanpassen.\n\n"
        "[Appearance]\n"
        f"ColorScheme={naam}\n"
        f"Font={LETTERS['code']},11,-1,5,400,0,0,0,0,0,0,0,0,0,0,1\n"
        "\n[Cursor Options]\nCursorShape=1\n"
        "\n[General]\n"
        f"Name={beschrijving}\n"
        "Parent=FALLBACK/\n"
        "TerminalMargin=12\n"
        "\n[Scrolling]\nHistoryMode=2\n"
    )


def schrijf(pad: Path, tekst: str) -> None:
    if not pad.exists() or pad.read_text(encoding="utf-8") != tekst:
        pad.write_text(tekst, encoding="utf-8")
        print("geschreven:", pad.relative_to(REPO))


def main() -> None:
    UIT.mkdir(parents=True, exist_ok=True)
    for thema, (naam, _) in THEMAS.items():
        schrijf(UIT / f"{naam}.colorscheme", kleurenschema(thema))
        schrijf(UIT / f"{naam}.profile", profiel(thema))
        p = palet(thema)
        laag = [n for n in VOLGORDE[1:7] if contrast(p[n], p["achter"]) < 4.5]
        if laag:
            raise SystemExit(f"{thema}: te weinig contrast voor {', '.join(laag)}")


if __name__ == "__main__":
    main()
