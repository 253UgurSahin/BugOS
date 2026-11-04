#!/usr/bin/bash
# Start de verkenner (BugOS Bestanden, of Dolphin) of een ander BugOS-programma voor een foto.
# Net als in een echte BugOS-sessie (KDE), zodat de BugOS-kleuren en -letters gelden.
# Draait in het echte BugOS-beeld; de bouwstraat maakt dan een schermfoto.
#
# Gebruik: bash tools/fotos/verkenner.sh <licht|donker> [map] [programma]
#   map: welke map open moet staan, bijvoorbeeld Documenten (leeg = de thuismap).
#        Een bestand mag ook: dan opent zijn map en is dat bestand gekozen.
#        "computer:" opent de pagina Deze computer; een pad met / ervoor mag ook.
#   programma: bugos-bestanden (standaard) of dolphin
# Met BUGOS_LSBLK=<lijstje.json> ziet de verkenner nep-schijven (zie tools/fotos/schijven.json),
# met BUGOS_RUIMTE=totaal,vrij,afbeeldingen,videos,documenten,muziek,downloads voorbeeldgetallen.
set -euo pipefail

THEMA="${1:-licht}"
MAP="${2:-}"
PROGRAMMA="${3:-bugos-bestanden}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"

# Een gebruiker "bugie" met de gewone Nederlandse mappen.
mkdir -p /var/home
id bugie >/dev/null 2>&1 || useradd -m -d /var/home/bugie -s /bin/bash bugie
THUIS=/var/home/bugie
cd "$THUIS"
mkdir -p Bureaublad Documenten Downloads Afbeeldingen Muziek "Video's" Sjablonen Openbaar .config
cat > .config/user-dirs.dirs <<'MAPPEN'
XDG_DESKTOP_DIR="$HOME/Bureaublad"
XDG_DOCUMENTS_DIR="$HOME/Documenten"
XDG_DOWNLOAD_DIR="$HOME/Downloads"
XDG_MUSIC_DIR="$HOME/Muziek"
XDG_PICTURES_DIR="$HOME/Afbeeldingen"
XDG_PUBLICSHARE_DIR="$HOME/Openbaar"
XDG_TEMPLATES_DIR="$HOME/Sjablonen"
XDG_VIDEOS_DIR="$HOME/Video's"
MAPPEN
echo "nl_NL" > .config/user-dirs.locale

# Voorbeeldbestanden
cp "$REPO"/tools/fotos/demo/* Documenten/
mkdir -p "Afbeeldingen/Vakantie Texel" "Afbeeldingen/Kleinkinderen"
cp /usr/share/wallpapers/bugos/contents/images/3840x2160.jpg "Afbeeldingen/Achtergrond Stip.jpg"
cp /usr/share/wallpapers/bugos/contents/images_dark/3840x2160.jpg "Afbeeldingen/Achtergrond Stip donker.jpg"
cp "$REPO/website/assets/bureaublad-licht.webp" "Afbeeldingen/Bureaublad licht.webp"
cp "$REPO/website/assets/bureaublad-donker.webp" "Afbeeldingen/Bureaublad donker.webp"
cp "$REPO/website/assets/winkel-licht.webp" "Afbeeldingen/BugOS Winkel.webp"
cp "$REPO/website/assets/welkom-licht.webp" "Afbeeldingen/BugOS Welkom.webp"
cp "$REPO/tools/fotos/demo/Brief gemeente.pdf" Downloads/
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
schema = lees("/usr/share/color-schemes/BugOSDonker.colors")
eigen = lees(doel)
for groep in schema.sections():
    if not eigen.has_section(groep):
        eigen.add_section(groep)
    for sleutel, waarde in schema.items(groep):
        eigen.set(groep, sleutel, waarde)
eigen.set("General", "ColorScheme", "BugOSDonker")
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
    STICK="/run/media/bugie/Stick van Bugie"
    if [ -d "$STICK" ]; then
        mkdir -p "$STICK/Foto's van de kleinkinderen"
        cp "Afbeeldingen/Achtergrond Stip.jpg" "$STICK/Verjaardag Daan.jpg"
        cp "Afbeeldingen/BugOS Welkom.webp" "$STICK/Kerst.webp"
        cp "$REPO/tools/fotos/demo/Recepten Bugie.odt" "$STICK/"
    fi
    if [ -d /run/media/bugie/Fotoschijf ]; then
        mkdir -p /run/media/bugie/Fotoschijf/{2019,2020,2021,2022}
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
    LANG=nl_NL.UTF-8 LANGUAGE=nl QT_SCALE_FACTOR=2 \
    XDG_CURRENT_DESKTOP=KDE KDE_FULL_SESSION=true KDE_SESSION_VERSION=6 "${BUGOS_ENV[@]}" \
    dbus-run-session -- "$PROGRAMMA" -qwindowgeometry 1180x740+0+0 "$DOEL"
