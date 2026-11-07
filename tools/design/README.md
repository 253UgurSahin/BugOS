# One design language for the whole system

BugOS's own apps get their look from `bugos_ui.py`. Everything else (KDE apps, KDE Settings,
the taskbar and its pop-ups, icons, GTK and Flatpak apps, the terminal and Windows programs) gets the
same look from these parts:

| Part | Where | Made by |
|---|---|---|
| Icon theme "BugOS" | `system_files/usr/share/icons/BugOS` | `python3 tools/icons/make.py` (one module per group: `apps.py`, `status.py`, `places.py`, `settings.py`) |
| Application style (Kvantum) "BugOS" / "BugOSDark" | `system_files/usr/share/Kvantum` | see `tools/kvantum/` |
| Plasma style "bugos" (taskbar, pop-ups, tooltips) | `system_files/usr/share/plasma/desktoptheme/bugos` | SVG files |
| Window title bar | Breeze with BugOS settings | `build_files/build.sh` |
| GTK layer `bugos.css` (GTK 3 and 4, also libadwaita) | `system_files/usr/share/bugos/gtk` | `python3 tools/gtk/make.py`; test: `xvfb-run -a python3 tools/gtk/preview.py` |
| Terminal (Konsole) "BugOS" / "BugOSDark" | `system_files/usr/share/konsole` | `python3 tools/konsole/make.py` |
| Windows programs (Wine system colors) | `system_files/usr/share/bugos/wine` | `python3 tools/wine/make.py` |

### How it reaches programs that are not KDE

- **GTK** (Firefox, GIMP, GNOME apps): the theme stays *Breeze*, because only then does KDE put its colors into
  GTK (`~/.config/gtk-3.0/colors.css`) and give GTK windows the same window buttons. At every login
  `bugos-theme inloggen` copies `bugos.css` next to it and puts `@import 'bugos.css';` at the top of `gtk.css`
  (KDE keeps that line; it only adds its own `colors.css`). The layer only changes corners, sliders, switches and,
  for libadwaita apps, the accent color: KDE passes the *soft* selection color as the accent, and libadwaita would
  turn that into slate blue. Someone who removes the line keeps it removed.
- **Flatpak** apps cannot see `/usr/share`. `bugos-theme` gives them read-only access to `gtk-3.0`, `gtk-4.0`,
  `Kvantum` and `kdeglobals` in `~/.config` (Flatpak binds those into the app's own config folder) and copies the
  Kvantum themes into `~/.config/Kvantum`. Icons work by themselves (Flatpak shows the host's `/usr/share/icons`).
  `bugos-flatpak-style` (after the first start and after the daily app update) installs
  `org.kde.KStyle.Kvantum` for every installed KDE runtime and `org.gtk.Gtk3theme.Breeze`.
- **Terminal:** `bugos-theme licht|donker` picks the profile `BugOS` or `BugOSDark`, unless someone chose another.
- **Wine:** `bugos-exe` writes the BugOS system colors into the Windows folder, again when light/dark changes or
  after an update changes the colors.

All of them take their colours, sizes and line icons from one place: [`tokens.py`](tokens.py), which reads
`KLEUREN` and `LIJN` straight from `bugos_ui.py`. Change a colour there, and everything follows.

## The test bench: see it without building a USB stick

A container with BugOS, Kvantum and an SVG renderer draws sample sheets of all parts, in light and dark.

```bash
# once: build the test bench on top of a locally built BugOS image (localhost/bugos:lokaal)
podman build -t localhost/bugos-testbank -f - . <<'X'
FROM localhost/bugos:lokaal
RUN dnf5 install -y kvantum librsvg2-tools python3-pillow && dnf5 clean all
X

# then, whenever you like (what: iconen | kvantum | plasma | alles; theme: licht | donker | beide)
podman run --rm -v "$PWD:/repo:ro" -v "$PWD/uit:/uit" localhost/bugos-testbank \
    bash -c 'python3 /repo/tools/design/preview.py alles beide'
```

The sheets land in `uit/`: `iconen-*.png` (each BugOS icon at several sizes, with the Breeze icon next to it),
`kvantum-widgets-*.png`, `kvantum-menu-*.png`, `kvantum-kirigami-*.png` (like KDE Settings) and `plasma-*.png`
(taskbar, a pop-up, a tooltip and the Plasma controls). Add `onderdeel=status` after `iconen` to see only one group.
