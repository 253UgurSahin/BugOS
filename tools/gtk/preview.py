#!/usr/bin/env python3
"""Proefvel voor de BugOS-laag op GTK: een GTK 3-venster vol knoppen, in licht en donker.

Jip-en-Janneke: dit doet na wat een BugOS-computer doet. Het pakt het Breeze-GTK-thema,
zet er de BugOS-kleuren in (zoals KDE dat doet met colors.css) en daarbovenop
bugos.css uit tools/gtk/make.py. Dan maakt het een plaatje, zonder echt scherm.

Nodig (Ubuntu/Debian): gir1.2-gtk-3.0 python3-gi breeze-gtk-theme xvfb
Gebruik:  xvfb-run -a python3 tools/gtk/preview.py [uitmap]      (standaard: uit/)
          python3 tools/gtk/preview.py --check   alleen nakijken of GTK de css zonder fouten leest

Gooit een fout als GTK iets in bugos.css niet snapt, zodat een tikfout niet ongemerkt
op BugOS-computers belandt.
"""

from __future__ import annotations

import configparser
import os
import shutil
import sys
import tempfile
from pathlib import Path

HIER = Path(__file__).resolve().parent
REPO = HIER.parents[1]
GTK_CSS = REPO / "system_files" / "usr" / "share" / "bugos" / "gtk"
SCHEMAS = REPO / "system_files" / "usr" / "share" / "color-schemes"


def colors_css(schema: Path) -> str:
    """Ongeveer wat KDE (kde-gtk-config) van een kleurenschema maakt: de @..._breeze-namen."""
    c = configparser.ConfigParser(interpolation=None)
    c.optionxform = str
    c.read(schema, encoding="utf-8")

    def k(groep: str, sleutel: str) -> str:
        r, g, b = (int(x) for x in c[f"Colors:{groep}"][sleutel].split(",")[:3])
        return f"#{r:02x}{g:02x}{b:02x}"

    def meng(a: str, b: str, t: float) -> str:
        pa = [int(a[i:i + 2], 16) for i in (1, 3, 5)]
        pb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
        return "#" + "".join(f"{round(x + (y - x) * t):02x}" for x, y in zip(pa, pb))

    w_bg, w_fg = k("Window", "BackgroundNormal"), k("Window", "ForegroundNormal")
    namen = {
        "theme_fg_color_breeze": w_fg, "theme_bg_color_breeze": w_bg,
        "theme_text_color_breeze": k("View", "ForegroundNormal"),
        "theme_base_color_breeze": k("View", "BackgroundNormal"),
        "theme_view_hover_decoration_color_breeze": k("View", "DecorationHover"),
        "theme_hovering_selected_bg_color_breeze": k("Selection", "DecorationHover"),
        "theme_selected_bg_color_breeze": k("Selection", "BackgroundNormal"),
        "theme_selected_fg_color_breeze": k("Selection", "ForegroundNormal"),
        "theme_view_active_decoration_color_breeze": k("View", "DecorationHover"),
        "theme_button_background_normal_breeze": k("Button", "BackgroundNormal"),
        "theme_button_decoration_hover_breeze": k("Button", "DecorationHover"),
        "theme_button_decoration_focus_breeze": k("Button", "DecorationFocus"),
        "theme_button_foreground_normal_breeze": k("Button", "ForegroundNormal"),
        "theme_button_foreground_active_breeze": k("Selection", "ForegroundNormal"),
        "borders_breeze": meng(w_bg, w_fg, 0.25),
        "tooltip_text_breeze": k("Tooltip", "ForegroundNormal"),
        "tooltip_background_breeze": k("Tooltip", "BackgroundNormal"),
        "tooltip_border_breeze": meng(k("Tooltip", "BackgroundNormal"), k("Tooltip", "ForegroundNormal"), 0.25),
    }
    # De "backdrop"- en "insensitive"-varianten: in BugOS gelijk aan de gewone.
    for naam, waarde in list(namen.items()):
        kort = naam.removesuffix("_breeze")
        for extra in ("_backdrop", "_insensitive"):
            namen.setdefault(f"{kort}{extra}_breeze", waarde)
        namen.setdefault(kort.replace("theme_", "theme_unfocused_") + "_breeze", waarde)
    namen.setdefault("unfocused_borders_breeze", namen["borders_breeze"])
    namen.setdefault("insensitive_borders_breeze", namen["borders_breeze"])
    return "".join(f"@define-color {n} {v};\n" for n, v in namen.items())


def zet_config(map_: Path, schema: str, donker: bool) -> None:
    gtk = map_ / "gtk-3.0"
    gtk.mkdir(parents=True)
    (gtk / "settings.ini").write_text(
        "[Settings]\ngtk-theme-name=Breeze\n"
        f"gtk-application-prefer-dark-theme={'true' if donker else 'false'}\n"
        "gtk-font-name=Inter 10\n", encoding="utf-8")
    (gtk / "colors.css").write_text(colors_css(SCHEMAS / f"{schema}.colors"), encoding="utf-8")
    shutil.copy(GTK_CSS / "gtk-3.0.css", gtk / "bugos.css")
    # Zo staat het ook op een BugOS-computer: eerst onze laag, dan KDE's kleuren.
    (gtk / "gtk.css").write_text("@import 'bugos.css';\n@import 'colors.css';\n", encoding="utf-8")


def nakijken(versie: str) -> int:
    """Laat GTK zelf het bestand lezen. GTK 3 en 4 kunnen niet in één proces: elk apart."""
    if versie == "beide":
        code = 0
        for v in ("3.0", "4.0"):
            code |= os.spawnv(os.P_WAIT, sys.executable, [sys.executable, __file__, "--check", v])
        return code
    import gi
    gi.require_version("Gtk", versie)
    from gi.repository import Gtk

    fouten = []
    p = Gtk.CssProvider()
    if versie == "3.0":
        p.connect("parsing-error", lambda _p, sec, e: fouten.append(f"regel {sec.get_start_line() + 1}: {e.message}"))
    else:
        p.connect("parsing-error", lambda _p, sec, e: fouten.append(
            f"regel {sec.get_start_location().lines + 1}: {e.message}"))
    tekst = (GTK_CSS / f"gtk-{versie}.css").read_text(encoding="utf-8")
    if versie == "4.0" and (Gtk.get_major_version(), Gtk.get_minor_version()) < (4, 16):
        # CSS-variabelen (:root { --accent-bg-color }) kent GTK pas vanaf 4.16 (Fedora 44 heeft 4.20).
        import re
        tekst = re.sub(r":root \{.*?\}\n", "", tekst, flags=re.S)
        print(f"(GTK {Gtk.get_major_version()}.{Gtk.get_minor_version()}: het :root-blok overgeslagen, dat kan pas vanaf 4.16)")
    p.load_from_data(tekst, -1) if versie == "4.0" else p.load_from_data(tekst.encode())
    print("\n".join(f"gtk-{versie}.css {f}" for f in fouten) or f"GTK {versie[0]} leest gtk-{versie}.css zonder fouten.")
    return 1 if fouten else 0


def proefvel(uit: Path, thema: str) -> None:
    import gi
    gi.require_version("Gtk", "3.0")
    from gi.repository import Gtk, GLib

    win = Gtk.OffscreenWindow()
    doos = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12, margin=24)
    win.add(doos)

    rij = Gtk.Box(spacing=8)
    rij.pack_start(Gtk.Button(label="Opslaan"), False, False, 0)
    hoofd = Gtk.Button(label="Kopiëren")
    hoofd.get_style_context().add_class("suggested-action")
    rij.pack_start(hoofd, False, False, 0)
    knop_uit = Gtk.Button(label="Uit")
    knop_uit.set_sensitive(False)
    rij.pack_start(knop_uit, False, False, 0)
    doos.pack_start(rij, False, False, 0)

    gekoppeld = Gtk.Box()
    gekoppeld.get_style_context().add_class("linked")
    for t in ("Vet", "Schuin", "Onder"):
        gekoppeld.pack_start(Gtk.Button(label=t), False, False, 0)
    doos.pack_start(gekoppeld, False, False, 0)

    veld = Gtk.Entry()
    veld.set_placeholder_text("Zoek een bestand")
    doos.pack_start(veld, False, False, 0)

    combo = Gtk.ComboBoxText()
    for t in ("Grote letters", "Normaal"):
        combo.append_text(t)
    combo.set_active(1)
    doos.pack_start(combo, False, False, 0)

    schakels = Gtk.Box(spacing=16)
    for aan in (True, False):
        s = Gtk.Switch()
        s.set_active(aan)
        schakels.pack_start(s, False, False, 0)
    vink = Gtk.CheckButton(label="Onthouden")
    vink.set_active(True)
    schakels.pack_start(vink, False, False, 0)
    schakels.pack_start(Gtk.RadioButton(label="Licht"), False, False, 0)
    doos.pack_start(schakels, False, False, 0)

    schuif = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
    schuif.set_value(60)
    schuif.set_draw_value(False)
    schuif.set_size_request(320, -1)
    doos.pack_start(schuif, False, False, 0)
    balk = Gtk.ProgressBar()
    balk.set_fraction(0.4)
    doos.pack_start(balk, False, False, 0)

    win.set_default_size(420, -1)
    win.show_all()

    def klaar():
        pix = win.get_pixbuf()
        pix.savev(str(uit / f"gtk-{thema}.png"), "png", [], [])
        Gtk.main_quit()
        return False

    GLib.timeout_add(400, klaar)
    Gtk.main()


def main() -> int:
    if "--check" in sys.argv:
        rest = sys.argv[sys.argv.index("--check") + 1:]
        return nakijken(rest[0] if rest else "beide")
    uit = Path(sys.argv[1] if len(sys.argv) > 1 else "uit").resolve()
    uit.mkdir(parents=True, exist_ok=True)
    if "BUGOS_GTK_PROEF" not in os.environ:
        # Elk thema in een eigen proces: GTK leest settings.ini maar één keer.
        code = 0
        for thema, schema in (("licht", "BugOSLight"), ("donker", "BugOSDark")):
            with tempfile.TemporaryDirectory() as tmp:
                zet_config(Path(tmp), schema, thema == "donker")
                env = dict(os.environ, XDG_CONFIG_HOME=tmp, BUGOS_GTK_PROEF=thema, GTK_THEME="")
                env.pop("GTK_THEME")
                code |= os.spawnve(os.P_WAIT, sys.executable, [sys.executable, __file__, str(uit)], env)
        print("Proefvellen in", uit)
        return code
    proefvel(uit, os.environ["BUGOS_GTK_PROEF"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
