#!/usr/bin/bash
# Start de verkenner (Dolphin, in BugOS "Bestanden") voor een foto.
# Draait in het echte BugOS-beeld; de bouwstraat maakt dan een schermfoto.
#
# Gebruik: bash tools/fotos/verkenner.sh <licht|donker> [map]
#   map: welke map open moet staan, bijvoorbeeld Documenten (leeg = de thuismap)
set -euo pipefail

THEMA="${1:-licht}"
MAP="${2:-}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"

# Een gebruiker "oma" met de gewone Nederlandse mappen.
mkdir -p /var/home
id oma >/dev/null 2>&1 || useradd -m -d /var/home/oma -s /bin/bash oma
THUIS=/var/home/oma
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

chown -R oma:oma "$THUIS"
mkdir -p /tmp/run-oma && chown oma:oma /tmp/run-oma && chmod 700 /tmp/run-oma

exec runuser -u oma -- env HOME="$THUIS" USER=oma XDG_RUNTIME_DIR=/tmp/run-oma DISPLAY="${DISPLAY:-:99}" \
    LANG=nl_NL.UTF-8 LANGUAGE=nl QT_SCALE_FACTOR=2 \
    dbus-run-session -- dolphin -qwindowgeometry 1180x740+0+0 "$THUIS/$MAP"
