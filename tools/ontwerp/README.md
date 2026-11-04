# One design language for the whole system

BugOS's own apps get their look from `bugos_ui.py`. Everything else (KDE apps, KDE Settings,
the taskbar and its pop-ups, icons) gets the same look from four parts:

| Part | Where | Made by |
|---|---|---|
| Icon theme "BugOS" | `system_files/usr/share/icons/BugOS` | `python3 tools/iconen/maak.py` (one module per group: `apps.py`, `status.py`, `plaatsen.py`, `instellingen.py`) |
| Application style (Kvantum) "BugOS" / "BugOSDonker" | `system_files/usr/share/Kvantum` | see `tools/kvantum/` |
| Plasma style "bugos" (taskbar, pop-ups, tooltips) | `system_files/usr/share/plasma/desktoptheme/bugos` | SVG files |
| Window title bar | Breeze with BugOS settings | `build_files/build.sh` |

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
    bash -c 'python3 /repo/tools/ontwerp/proef.py alles beide'
```

The sheets land in `uit/`: `iconen-*.png` (each BugOS icon at several sizes, with the Breeze icon next to it),
`kvantum-widgets-*.png`, `kvantum-menu-*.png`, `kvantum-kirigami-*.png` (like KDE Settings) and `plasma-*.png`
(taskbar, a pop-up, a tooltip and the Plasma controls). Add `onderdeel=status` after `iconen` to see only one group.
