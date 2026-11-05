#!/usr/bin/bash
# Start de verkenner (BugOS Bestanden, of Dolphin) of een ander BugOS-programma voor een foto.
# Net als in een echte BugOS-sessie (KDE), zodat de BugOS-kleuren en -letters gelden.
# Draait in het echte BugOS-beeld; de bouwstraat maakt dan een schermfoto.
#
# Gebruik: bash tools/screenshots/explorer.sh <licht|donker> [map] [programma]
#   map: welke map open moet staan, bijvoorbeeld Documents (leeg = de thuismap).
#        Een bestand mag ook: dan opent zijn map en is dat bestand gekozen.
#        "computer:" opent de pagina Deze computer; een pad met / ervoor mag ook.
#   programma: bugos-files (standaard) of dolphin
# Met BUGOS_LSBLK=<lijstje.json> ziet de verkenner nep-schijven (zie tools/screenshots/drives.json),
# met BUGOS_RUIMTE=totaal,vrij,afbeeldingen,videos,documenten,muziek,downloads voorbeeldgetallen.
set -euo pipefail

THEMA="${1:-licht}"
MAP="${2:-}"
PROGRAMMA="${3:-bugos-files}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"

# Een gebruiker "bugie" met de gewone Engelse mappen (BugOS is standaard Engels).
mkdir -p /var/home
id bugie >/dev/null 2>&1 || useradd -m -d /var/home/bugie -s /bin/bash bugie
THUIS=/var/home/bugie
cd "$THUIS"
mkdir -p Desktop Documents Downloads Pictures Music Videos Templates Public .config
cat > .config/user-dirs.dirs <<'MAPPEN'
XDG_DESKTOP_DIR="$HOME/Desktop"
XDG_DOCUMENTS_DIR="$HOME/Documents"
XDG_DOWNLOAD_DIR="$HOME/Downloads"
XDG_MUSIC_DIR="$HOME/Music"
XDG_PICTURES_DIR="$HOME/Pictures"
XDG_PUBLICSHARE_DIR="$HOME/Public"
XDG_TEMPLATES_DIR="$HOME/Templates"
XDG_VIDEOS_DIR="$HOME/Videos"
MAPPEN
echo "en_US" > .config/user-dirs.locale

# Voorbeeldbestanden
cp "$REPO"/tools/screenshots/demo/* Documents/
mkdir -p "Pictures/Holiday by the sea" "Pictures/Family"
cp /usr/share/wallpapers/bugos/contents/images/3840x2160.jpg "Pictures/Stip background.jpg"
cp /usr/share/wallpapers/bugos/contents/images_dark/3840x2160.jpg "Pictures/Stip background dark.jpg"
cp "$REPO/website/assets/desktop-light.webp" "Pictures/Desktop light.webp"
cp "$REPO/website/assets/desktop-dark.webp" "Pictures/Desktop dark.webp"
cp "$REPO/website/assets/store-light.webp" "Pictures/BugOS Store.webp"
cp "$REPO/website/assets/welcome-light.webp" "Pictures/BugOS Welcome.webp"
cp "$REPO/tools/screenshots/demo/Letter from the council.pdf" Downloads/
: > Downloads/SpotifySetup.exe

if [ "$THEMA" = donker ]; then
    # Net als "Donker" kiezen in BugOS Welkom: de donkere kleuren in je eigen instellingen.
    python3 - "$THUIS/.config/kdeglobals" <<'PY'
import configparser
import sys

def lees(pad):
    c = configparser.RawConfigParser(strict=False, interpolation=None)
    c.optionxform = str
    c.read(pad, encoding="utf-8")
    return c

doel = sys.argv[1]
schema = lees("/usr/share/color-schemes/BugOSDark.colors")
eigen = lees(doel)
for groep in schema.sections():
    if not eigen.has_section(groep):
        eigen.add_section(groep)
    for sleutel, waarde in schema.items(groep):
        eigen.set(groep, sleutel, waarde)
if not eigen.has_section("General"):
    eigen.add_section("General")
eigen.set("General", "ColorScheme", "BugOSDark")
with open(doel, "w", encoding="utf-8") as f:
    eigen.write(f, space_around_delimiters=False)
PY
fi

if [ -n "${BUGOS_LSBLK:-}" ]; then
    # Nep-schijven voor de foto: maak de mappen waar ze 'open' staan, met wat op de stick.
    python3 - "$BUGOS_LSBLK" <<'PY'
import json
import os
import sys

def alle(a):
    yield a
    for kind in a.get("children") or []:
        yield from alle(kind)

for schijf in json.load(open(sys.argv[1], encoding="utf-8"))["blockdevices"]:
    for a in alle(schijf):
        for plek in a.get("mountpoints") or []:
            if plek and plek.startswith("/run/media/"):
                os.makedirs(plek, exist_ok=True)
PY
    STICK="/run/media/bugie/Bugie's stick"
    if [ -d "$STICK" ]; then
        mkdir -p "$STICK/Foto's van de kleinkinderen"
        cp "Pictures/Stip background.jpg" "$STICK/Daan birthday.jpg"
        cp "Pictures/BugOS Welcome.webp" "$STICK/Christmas.webp"
        cp "$REPO/tools/screenshots/demo/Bugie's recipes.odt" "$STICK/"
    fi
    if [ -d /run/media/bugie/"Photo drive" ]; then
        mkdir -p "/run/media/bugie/Photo drive"/{2019,2020,2021,2022}
    fi
    # Alleen als er nep-schijven 'open' staan (bij een lege lijst bestaat deze map niet).
    if [ -d /run/media/bugie ]; then
        chown -R bugie:bugie /run/media/bugie
    fi
fi

case "$MAP" in
    computer:* | /*) DOEL="$MAP" ;;
    arg:*) DOEL="${MAP#arg:}" ;;  # voor andere programma's: gewoon dit woord (bv. arg:wifi)
    *) DOEL="$THUIS/$MAP" ;;
esac
# Alle BUGOS_-instellingen gaan mee naar het programma (bv. voorbeeldgegevens voor foto's).
mapfile -t BUGOS_ENV < <(env | grep '^BUGOS_' || true)

chown -R bugie:bugie "$THUIS"
mkdir -p /tmp/run-bugie && chown bugie:bugie /tmp/run-bugie && chmod 700 /tmp/run-bugie

exec runuser -u bugie -- env HOME="$THUIS" USER=bugie XDG_RUNTIME_DIR=/tmp/run-bugie DISPLAY="${DISPLAY:-:99}" \
    LANG=en_US.UTF-8 LANGUAGE=en QT_SCALE_FACTOR=2 \
    XDG_CURRENT_DESKTOP=KDE KDE_FULL_SESSION=true KDE_SESSION_VERSION=6 "${BUGOS_ENV[@]}" \
    dbus-run-session -- "$PROGRAMMA" -qwindowgeometry 1180x740+0+0 "$DOEL"
