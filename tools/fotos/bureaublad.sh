#!/usr/bin/bash
# Zet het hele BugOS-bureaublad op het scherm voor een foto: plasmashell met de BugOS-taakbalk
# (startknop, vastgezette programma's, snelmenu, systeemvak en klok) en daarbij op verzoek het
# startmenu, het snelmenu of het uitzetscherm. Net als in een echte BugOS-sessie (KDE), zodat de
# BugOS-kleuren, -letters en -indeling gelden.
# Draait in het echte BugOS-beeld op een virtueel scherm (Xvfb); de bouwstraat maakt dan een
# schermfoto (zie .github/workflows/fotos.yml, taak "bureaublad").
#
# Gebruik: bash tools/fotos/bureaublad.sh <licht|donker> <taakbalk|startmenu|snelmenu|uitzetten>
#   taakbalk:  het bureaublad met de taakbalk, verder niets
#   startmenu: daarbij het BugOS-startmenu open
#   snelmenu:  daarbij het BugOS-snelmenu open
#   uitzetten: daarbij het uitzetscherm (zoals na "Uitzetten" in het startmenu)
#
# Hoe het werkt: zonder vensterbeheerder (KWin) kan plasmashell een menu niet zelf openklappen.
# Daarom tonen we de menu's met plasmawindowed (dat laat een applet als gewoon venster zien) en
# het uitzetscherm met de echte ksmserver-logout-greeter in proefstand (PLASMA_SESSION_GUI_TEST).
# Zonder ~/.config/plasma-org.kde.plasma.desktop-appletsrc bouwt plasmashell de taakbalk uit het
# look-and-feel-pakket in kdeglobals; BugOS zet dat in /etc/xdg/kdeglobals (org.bugos.desktop).
# Alle BUGOS_-instellingen in de omgeving gaan mee naar de programma's.
set -euo pipefail

stap() {  # een regel in het logboek, met de tijd ervoor
    echo "[$(date +%H:%M:%S)] $*"
}

fout() {  # hiermee kan er geen goede foto komen; de bouwstraat zoekt in het logboek naar 'FOUT:'
    echo "FOUT: $*" >&2
    exit 1
}

# ---- Deel 2: draait als oma, binnen één dbus-run-session (gestart onderaan dit bestand) ----
bureaublad_tonen() {  # scene
    local scene="$1" kam plasma_pid gewacht=0 antwoordt=nee greeter hulp kies=()
    export QT_QPA_PLATFORM=xcb QT_QUICK_BACKEND=software QT_SCALE_FACTOR=2
    export LANG=nl_NL.UTF-8 LANGUAGE=nl XDG_CURRENT_DESKTOP=KDE KDE_FULL_SESSION=true KDE_SESSION_VERSION=6
    stap "Bureaublad voor de foto: scene '$scene', scherm ${DISPLAY:-?}, als $(id -un)"
    stap "$(plasmashell --version 2>/dev/null | head -1 || true)"

    # plasmashell heeft de activiteitenbeheerder nodig; anders stopt hij meteen. Meestal start D-Bus
    # die zelf (org.kde.ActivityManager.service), maar voor de zekerheid starten we hem alvast.
    kam="$(command -v kactivitymanagerd || true)"
    if [ -z "$kam" ] && [ -x /usr/libexec/kactivitymanagerd ]; then
        kam=/usr/libexec/kactivitymanagerd
    fi
    if [ -n "$kam" ]; then
        stap "Activiteitenbeheerder starten: $kam"
        "$kam" &
    elif [ -e /usr/share/dbus-1/services/org.kde.ActivityManager.service ]; then
        stap "kactivitymanagerd niet gevonden; D-Bus start hem zelf zodra plasmashell erom vraagt"
    else
        stap "Let op: geen kactivitymanagerd en geen D-Bus-dienst ervoor; plasmashell kan daardoor stoppen"
    fi

    stap "plasmashell starten"
    plasmashell --no-respawn &
    plasma_pid=$!

    # Wachten tot plasmashell op D-Bus antwoordt (hoogstens 60 s), daarna nog even voor het tekenen.
    while [ "$gewacht" -lt 60 ]; do
        if gdbus call --session --dest org.kde.plasmashell --object-path /PlasmaShell \
                --method org.freedesktop.DBus.Peer.Ping >/dev/null 2>&1; then
            antwoordt=ja
            break
        fi
        sleep 2
        gewacht=$((gewacht + 2))
    done
    if [ "$antwoordt" = ja ]; then
        stap "plasmashell antwoordt (na ongeveer $gewacht s); 8 s wachten tot de taakbalk er staat"
    else
        stap "Let op: plasmashell antwoordt na 60 s nog niet; we proberen het toch"
    fi
    sleep 8
    kill -0 "$plasma_pid" 2>/dev/null || stap "Let op: plasmashell is gestopt (zie de regels hierboven)"

    case "$scene" in
        taakbalk)
            stap "Alleen de taakbalk; er gaat verder niets open" ;;
        startmenu)
            # Maten zijn in punten; met QT_SCALE_FACTOR=2 is het venster op de foto twee keer zo groot:
            # 660x640 punten (de maat van het startmenu) wordt 1320x1280 beeldpunten, op (60,120).
            stap "Startmenu openen (plasmawindowed org.bugos.startmenu)"
            plasmawindowed org.bugos.startmenu -qwindowgeometry 660x640+30+60 & ;;
        snelmenu)
            # 410x380 punten wordt 820x760 beeldpunten, op (1500,500): rechts, waar het snelmenu zit.
            stap "Snelmenu openen (plasmawindowed org.bugos.snelmenu)"
            plasmawindowed org.bugos.snelmenu -qwindowgeometry 410x380+750+250 & ;;
        uitzetten)
            # In proefstand toont de greeter alle knoppen zonder logind; --windowed slaat de focusbewaker
            # over (die sluit het venster anders na 3 s). Met --choose vraagt hij "Wat wil je doen?" (alle
            # tegels, geen aftelling); zonder toont hij alleen "Afmelden?", of telt hij af en is hij weg
            # voor de foto. We geven --choose alleen mee als deze greeter het kent.
            greeter=/usr/libexec/ksmserver-logout-greeter
            hulp="$("$greeter" --help 2>&1 || true)"
            case "$hulp" in
                *--choose*) kies=(--choose) ;;
                *) stap "Let op: deze greeter kent --choose niet; het scherm toont dan maar één keus" ;;
            esac
            stap "Uitzetscherm openen ($greeter ${kies[*]:-} --windowed, proefstand)"
            PLASMA_SESSION_GUI_TEST=1 "$greeter" "${kies[@]}" --windowed & ;;
    esac
    stap "Klaar voor de foto; alles blijft staan tot de bouwstraat de container weghaalt"
    sleep infinity
}

if [ "${1:-}" = --als-oma ]; then
    bureaublad_tonen "${2:-taakbalk}"
    exit 0
fi

# ---- Deel 1: draait als root in de container en zet alles klaar ----
THEMA="${1:-licht}"
SCENE="${2:-taakbalk}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
ZELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"  # dit script zelf, met volledig pad

case "$SCENE" in
    taakbalk | startmenu | snelmenu | uitzetten) ;;
    *) fout "Onbekende scene '$SCENE'. Kies taakbalk, startmenu, snelmenu of uitzetten." ;;
esac

# Eerst kijken of alles er is; dan weet je het meteen, en niet pas na een zwarte foto.
for p in plasmashell gdbus dbus-run-session runuser; do
    command -v "$p" >/dev/null || fout "$p ontbreekt in dit BugOS-beeld."
done
case "$SCENE" in
    startmenu | snelmenu)
        command -v plasmawindowed >/dev/null || fout "plasmawindowed ontbreekt in dit BugOS-beeld."
        [ -d "/usr/share/plasma/plasmoids/org.bugos.$SCENE" ] || fout "Het applet org.bugos.$SCENE zit niet in dit BugOS-beeld." ;;
    uitzetten)
        [ -x /usr/libexec/ksmserver-logout-greeter ] || fout "/usr/libexec/ksmserver-logout-greeter ontbreekt in dit BugOS-beeld." ;;
esac

# Een gebruiker "oma" met de gewone Nederlandse mappen (net als in tools/fotos/verkenner.sh).
mkdir -p /var/home
id oma >/dev/null 2>&1 || useradd -m -d /var/home/oma -s /bin/bash -c Oma oma
THUIS=/var/home/oma
cd "$THUIS"
mkdir -p Bureaublad Documenten Downloads Afbeeldingen Muziek "Video's" Sjablonen Openbaar .config .local/share
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

# Pas geopende bestanden, zodat het startmenu bij "Recent geopend" iets laat zien
# (bugos-start-data leest ~/.local/share/recently-used.xbel; alleen bestanden die bestaan tellen).
cat > .local/share/recently-used.xbel <<RECENT
<?xml version="1.0" encoding="UTF-8"?>
<xbel version="1.0" xmlns:bookmark="http://www.freedesktop.org/standards/desktop-bookmarks" xmlns:mime="http://www.freedesktop.org/standards/shared-mime-info">
  <bookmark href="file://$THUIS/Documenten/Recepten%20oma.odt" added="2026-10-30T09:12:00Z" modified="2026-11-02T15:40:00Z" visited="2026-11-02T15:40:00Z"/>
  <bookmark href="file://$THUIS/Downloads/Brief%20gemeente.pdf" added="2026-10-31T10:00:00Z" modified="2026-11-02T11:05:00Z" visited="2026-11-02T11:05:00Z"/>
  <bookmark href="file://$THUIS/Documenten/Boodschappenlijst.odt" added="2026-10-29T08:00:00Z" modified="2026-11-01T17:30:00Z" visited="2026-11-01T17:30:00Z"/>
  <bookmark href="file://$THUIS/Afbeeldingen/Achtergrond%20Stip.jpg" added="2026-10-28T14:00:00Z" modified="2026-10-31T19:20:00Z" visited="2026-10-31T19:20:00Z"/>
  <bookmark href="file://$THUIS/Documenten/Verjaardagen.ods" added="2026-10-20T12:00:00Z" modified="2026-10-30T12:00:00Z" visited="2026-10-30T12:00:00Z"/>
</xbel>
RECENT

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

# Alle BUGOS_-instellingen gaan mee naar de programma's (bv. voorbeeldgegevens voor foto's).
mapfile -t BUGOS_ENV < <(env | grep '^BUGOS_' || true)

chown -R oma:oma "$THUIS"
mkdir -p /tmp/run-oma && chown oma:oma /tmp/run-oma && chmod 700 /tmp/run-oma

# Nu als oma, binnen één D-Bus-sessie (plasmashell, de activiteitenbeheerder en de menu's moeten
# elkaar daarop kunnen vinden). Dit script roept zichzelf opnieuw aan voor deel 2 hierboven.
stap "Klaargezet (thema $THEMA, scene $SCENE); nu als oma het bureaublad starten"
exec runuser -u oma -- env HOME="$THUIS" USER=oma LOGNAME=oma XDG_RUNTIME_DIR=/tmp/run-oma DISPLAY="${DISPLAY:-:99}" \
    "${BUGOS_ENV[@]}" dbus-run-session -- bash "$ZELF" --als-oma "$SCENE"
