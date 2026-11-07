#!/usr/bin/env python3
"""BugOS-laag voor GTK-programma's (Firefox, GIMP, Flatpak-apps met GTK), licht en donker.

Schrijft:
  system_files/usr/share/bugos/gtk/gtk-3.0.css   (GTK 3)
  system_files/usr/share/bugos/gtk/gtk-4.0.css   (GTK 4, ook libadwaita-apps)

Jip-en-Janneke: GTK-programma's krijgen in BugOS het gewone Breeze-GTK-thema.
KDE zet daar zelf al de kleuren van het BugOS-kleurenschema in (colors.css in
~/.config/gtk-3.0 en gtk-4.0). Wat Breeze anders doet dan BugOS, zijn de
vormen: kleine hoekjes, een dun schuifje en een roze schakelaar. Deze laag
verandert alleen dat, en verder niets ("niet overschilderen"):
  - hoeken uit MATEN (knoppen, velden, pop-ups en menu's 12; de vensterrand zelf blijft van KWin);
  - het schuifje: spoor van 8 px, gevuld deel koraal -> rood, wit bolletje van 22 px;
  - een schakelaar die aan staat: het rode verloop, net als in Kvantum en de eigen apps.
Kleuren komen uit het kleurenschema (de @..._breeze-namen van KDE), zodat licht
en donker vanzelf kloppen; alleen het koraal van het verloop staat hier vast.

bugos-theme zet dit bestand bij het inloggen in ~/.config/gtk-3.0/bugos.css en
zet "@import 'bugos.css';" in gtk.css. KDE laat dat staan (het voegt alleen
zijn eigen colors.css toe), en Flatpak-apps zien het ook.

Eén bron: maten en kleuren komen uit tools/design/tokens.py (dus uit bugos_ui.py).

Gebruik:  python3 tools/gtk/make.py
"""

from __future__ import annotations

import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER.parent / "ontwerp"))

from tokens import KLEUREN, MATEN, REPO, ROOD_VERLOOP  # noqa: E402

UIT = REPO / "system_files" / "usr" / "share" / "bugos" / "gtk"

KNOP = MATEN["knop"]
SPOOR = MATEN["schuif_spoor"]
BOL = MATEN["schuif_knop"]
KORAAL = ROOD_VERLOOP[0]

KOP = f"""/* BugOS-laag voor GTK {{versie}}. Gemaakt door tools/gtk/make.py: niet met de hand aanpassen.
 *
 * Alleen vormen (hoeken, schuifje, schakelaar). De kleuren komen van KDE
 * (colors.css, uit het BugOS-kleurenschema); hieronder staan alleen
 * reservekleuren voor als die er niet is (bijv. in een Flatpak zonder toegang).
 * Weg ermee? Haal de regel "@import 'bugos.css';" uit ~/.config/gtk-{{versie}}/gtk.css. */

/* Reservekleuren (BugOS Licht). KDE's colors.css komt na dit bestand en wint dus. */
@define-color theme_button_decoration_focus_breeze {KLEUREN['licht']['accent']};
@define-color theme_bg_color_breeze {KLEUREN['licht']['achter']};
@define-color theme_button_foreground_normal_breeze {KLEUREN['licht']['tekst']};
@define-color borders_breeze {KLEUREN['licht']['rand_sterk']};
@define-color bugos_koraal {KORAAL};
"""


def verloop() -> str:
    return f"linear-gradient(to right, @bugos_koraal, @theme_button_decoration_focus_breeze)"


def gtk3() -> str:
    return KOP.format(versie="3.0") + f"""
/* Hoeken: knoppen en velden {KNOP} px (zoals overal in BugOS) */
button, entry, combobox button, spinbutton:not(.vertical), .linked > entry:only-child {{
  border-radius: {KNOP}px;
}}
/* Rij van knoppen aan elkaar (zoals "Vet | Schuin"): alleen de buitenste hoeken rond */
.linked:not(.vertical) > button:first-child, .linked:not(.vertical) > entry:first-child,
.linked:not(.vertical) > combobox:first-child > box > button.combo {{
  border-radius: {KNOP}px 0 0 {KNOP}px;
}}
.linked:not(.vertical) > button:last-child, .linked:not(.vertical) > entry:last-child,
.linked:not(.vertical) > combobox:last-child > box > button.combo {{
  border-radius: 0 {KNOP}px {KNOP}px 0;
}}
.linked:not(.vertical) > button:only-child, .linked:not(.vertical) > entry:only-child {{
  border-radius: {KNOP}px;
}}
.linked:not(.vertical) > button:not(:first-child):not(:last-child),
.linked:not(.vertical) > entry:not(:first-child):not(:last-child) {{
  border-radius: 0;
}}
button.circular, button.osd.circular {{ border-radius: 9999px; }}

/* Menu's, pop-ups en tooltips: {KNOP} px, net als in KDE (Kvantum) */
menu, .menu, .context-menu, popover, popover.background, tooltip, tooltip.background {{
  border-radius: {KNOP}px;
}}
menu menuitem {{ border-radius: 8px; }}

/* De vensterrand (en zijn hoeken) laten we aan KWin en Breeze: die zijn gelijk aan alle andere vensters. */

/* Schakelaar: aan = het BugOS-rood (verloop), uit blijft rustig grijs */
switch:checked {{
  background-image: {verloop()};
  border-color: transparent;
}}
switch:checked:disabled {{ opacity: 0.5; }}
switch slider {{ background-image: none; background-color: #FFFFFF; }}

/* Schuif: spoor {SPOOR} px, gevuld deel koraal -> rood, wit bolletje van {BOL} px */
scale trough {{
  min-width: {SPOOR}px;
  min-height: {SPOOR}px;
  border-radius: {SPOOR // 2}px;
  border-color: transparent;
}}
scale highlight {{
  border-radius: {SPOOR // 2}px;
  border-color: transparent;
  background-image: {verloop()};
}}
scale highlight:disabled {{ background-image: none; }}
scale slider {{
  min-width: {BOL}px;
  min-height: {BOL}px;
  margin: -{(BOL - SPOOR) // 2 + 1}px;
  background-image: none;
  background-color: #FFFFFF;
  border-color: alpha(@theme_button_foreground_normal_breeze, 0.15);
}}
"""


def gtk4() -> str:
    # GTK 4 en libadwaita: alleen wat Breeze-GTK4 en libadwaita allebei begrijpen,
    # zodat libadwaita-apps (GNOME-apps) hun eigen opbouw houden.
    return KOP.format(versie="4.0") + f"""
/* Accentkleur van GNOME-apps (libadwaita). KDE geeft via de portal de zachte selectiekleur
 * door (lichtroze); libadwaita maakt daar grijsblauw van. Hier: het echte BugOS-rood, uit het
 * kleurenschema (licht en donker), met witte tekst erop. */
@define-color accent_bg_color @theme_button_decoration_focus_breeze;
@define-color accent_fg_color #FFFFFF;
@define-color accent_color @theme_button_decoration_focus_breeze;
:root {{
  --accent-bg-color: @theme_button_decoration_focus_breeze;
  --accent-fg-color: #FFFFFF;
  --accent-color: @theme_button_decoration_focus_breeze;
}}

/* Hoeken: knoppen en velden {KNOP} px. Ronde (.circular) en pil-knoppen (.pill) blijven rond. */
button:not(.circular):not(.pill):not(.osd), entry, spinbutton, dropdown > button, combobox button {{
  border-radius: {KNOP}px;
}}
.linked:not(.vertical) > button:not(:first-child):not(:last-child),
.linked:not(.vertical) > entry:not(:first-child):not(:last-child) {{
  border-radius: 0;
}}
.linked:not(.vertical) > button:first-child:not(:only-child),
.linked:not(.vertical) > entry:first-child:not(:only-child) {{
  border-top-right-radius: 0; border-bottom-right-radius: 0;
}}
.linked:not(.vertical) > button:last-child:not(:only-child),
.linked:not(.vertical) > entry:last-child:not(:only-child) {{
  border-top-left-radius: 0; border-bottom-left-radius: 0;
}}

/* Pop-ups en menu's: {KNOP} px */
popover > contents, popover.menu > contents, tooltip {{ border-radius: {KNOP}px; }}
popover.menu modelbutton {{ border-radius: 8px; }}

/* Schakelaar aan = BugOS-rood */
switch:checked {{
  background-image: {verloop()};
}}
switch > slider {{ background-color: #FFFFFF; }}

/* Schuif: gevuld deel koraal -> rood, wit bolletje */
scale > trough > highlight {{ background-image: {verloop()}; }}
scale > trough > slider {{ background-color: #FFFFFF; }}
"""


def main() -> None:
    UIT.mkdir(parents=True, exist_ok=True)
    for naam, tekst in (("gtk-3.0.css", gtk3()), ("gtk-4.0.css", gtk4())):
        pad = UIT / naam
        oud = pad.read_text(encoding="utf-8") if pad.exists() else None
        if oud != tekst:
            pad.write_text(tekst, encoding="utf-8")
            print("geschreven:", pad.relative_to(REPO))


if __name__ == "__main__":
    main()
