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
# Hoe het werkt: KWin draait met een virtueel scherm (geen X of grafische kaart nodig) en daarbinnen
# plasmashell, net als op een echte pc. Het startmenu gaat open zoals de Windows-toets dat doet,
# het uitzetscherm via dezelfde D-Bus-vraag als 'Uitzetten' in het startmenu (in proefstand, zonder
# logind: PLASMA_SESSION_GUI_TEST). De foto maakt KWin zelf (Spectacle, of schermfoto.py via D-Bus)
# en komt in /var/home/oma/foto.png; de bouwstraat kopieert hem uit de container.
# Zonder ~/.config/plasma-org.kde.plasma.desktop-appletsrc bouwt plasmashell de taakbalk uit het
# look-and-feel-pakket in kdeglobals (org.bugos.desktop). Alle BUGOS_-instellingen gaan mee.
set -euo pipefail

stap() {  # een regel in het logboek, met de tijd ervoor
    echo "[$(date +%H:%M:%S)] $*"
}

fout() {  # hiermee kan er geen goede foto komen; de bouwstraat zoekt in het logboek naar 'FOUT:'
    echo "FOUT: $*" >&2
    exit 1
}

# ---- Deel 3: met KWin erbij (Wayland), als oma: plasmashell en de gevraagde scene ----
# Plasma 6.8 is Wayland-only: op een kaal X-scherm crasht plasmashell. Daarom draait KWin zelf in
# een venster op het virtuele scherm (--x11-display) en daarbinnen plasmashell, net als op een echte pc.
# KWin is er dan ook écht, dus het startmenu klapt gewoon op de taakbalk open (activateLauncherMenu)
# en het uitzetscherm komt schermvullend, via dezelfde D-Bus-vraag als 'Uitzetten' in het startmenu.
in_kwin() {  # scene
    local scene="$1" plasma_pid gewacht=0 antwoordt=nee
    export QT_QPA_PLATFORM=wayland WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-foto}" XDG_SESSION_TYPE=wayland
    export QT_QUICK_BACKEND=software PLASMA_SESSION_GUI_TEST=1
    unset QT_SCALE_FACTOR  # KWin zelf geeft de schaal (2) door aan alle programma's
    # Programma's die D-Bus later start (greeter, kglobalaccel) krijgen dezelfde omgeving.
    dbus-update-activation-environment --all 2>/dev/null || true
    stap "In KWin (Wayland-scherm '$WAYLAND_DISPLAY'): plasmashell starten"
    plasmashell --no-respawn &
    plasma_pid=$!
    while [ "$gewacht" -lt 90 ]; do
        if gdbus call --session --dest org.kde.plasmashell --object-path /PlasmaShell \
                --method org.freedesktop.DBus.Peer.Ping >/dev/null 2>&1; then
            antwoordt=ja
            break
        fi
        sleep 2
        gewacht=$((gewacht + 2))
    done
    if [ "$antwoordt" = ja ]; then
        stap "plasmashell antwoordt (na ongeveer $gewacht s); 10 s wachten tot de taakbalk er staat"
    else
        stap "Let op: plasmashell antwoordt na 90 s nog niet; we proberen het toch"
    fi
    sleep 10
    kill -0 "$plasma_pid" 2>/dev/null || stap "Let op: plasmashell is gestopt (zie de regels hierboven)"
    pgrep -x kwin_wayland >/dev/null 2>&1 || stap "Let op: KWin draait niet meer (zie de regels hierboven)"
    case "$scene" in
        taakbalk)
            stap "Alleen de taakbalk; er gaat verder niets open" ;;
        startmenu)
            stap "Startmenu openen zoals de Windows-toets dat doet (activateLauncherMenu)"
            gdbus call --session --dest org.kde.plasmashell --object-path /PlasmaShell \
                --method org.kde.PlasmaShell.activateLauncherMenu >/dev/null 2>&1 || stap "Let op: activateLauncherMenu gaf een fout" ;;
        snelmenu)
            stap "Snelmenu openen als los venster (plasmawindowed org.bugos.snelmenu)"
            plasmawindowed org.bugos.snelmenu & ;;
        uitzetten)
            # De greeter zelf alvast starten (in proefstand); daarna dezelfde D-Bus-vraag als het startmenu.
            stap "Uitzetscherm openen zoals 'Uitzetten' in het startmenu (org.kde.LogoutPrompt, proefstand)"
            if [ -x /usr/libexec/ksmserver-logout-greeter ]; then
                /usr/libexec/ksmserver-logout-greeter &
                sleep 4
            fi
            gdbus call --session --dest org.kde.LogoutPrompt --object-path /LogoutPrompt \
                --method org.kde.LogoutPrompt.promptAll >/dev/null 2>&1 || stap "Let op: promptAll gaf een fout" ;;
    esac
    sleep 8
    schermfoto "$HOME/foto.png"
    stap "Klaar; alles blijft staan tot de bouwstraat de container weghaalt"
    sleep infinity
}

# De foto van het virtuele scherm: met Spectacle als dat er is, anders via KWin's D-Bus (schermfoto.py).
schermfoto() {  # uit.png
    local uit="$1"
    rm -f "$uit"
    if command -v spectacle >/dev/null 2>&1; then
        stap "Schermfoto met Spectacle"
        timeout 40 spectacle --background --nonotify --fullscreen --output "$uit" 2>&1 | head -20 || true
    fi
    if [ ! -s "$uit" ]; then
        stap "Schermfoto via KWin's D-Bus (schermfoto.py)"
        timeout 60 python3 "$(dirname "$ZELF")/schermfoto.py" "$uit" 2>&1 | head -20 || true
    fi
    if [ -s "$uit" ]; then
        stap "Schermfoto staat klaar: $uit ($(stat -c %s "$uit") bytes)"
    else
        fout "Geen schermfoto kunnen maken (geen Spectacle en geen schermfoto via D-Bus)."
    fi
}

# ---- Deel 2: draait als oma, binnen één dbus-run-session (gestart onderaan dit bestand) ----
bureaublad_tonen() {  # scene
    local scene="$1" kam plasma_pid kwin_pid kwin_code gewacht=0 antwoordt=nee greeter hulp kies=()
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

    if command -v kwin_wayland >/dev/null 2>&1; then
        # De echte weg: KWin in een venster op het virtuele scherm (2560x1600, schaal 2 = net als
        # de andere foto's), met zachte (software) tekening; daarbinnen plasmashell (in_kwin).
        stap "$(kwin_wayland --version 2>/dev/null | head -1 || true)"
        stap "D-Bus-sessie: ${DBUS_SESSION_BUS_ADDRESS:-(geen adres)}; namen op de bus: $(gdbus call --session \
            --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus --method org.freedesktop.DBus.ListNames 2>/dev/null | tr ',' '\n' | wc -l)"
        # Virtueel scherm van 2560x1600 op schaal 2 (net als de andere foto's). De bouwcomputer heeft geen
        # grafische kaart: KWIN_DRM_DEVICES wijst naar iets dat geen kaart is, en dan neemt KWin zijn
        # software-tekenaar (llvmpipe) — zo draaien KDE's eigen tests ook.
        # KWIN_WAYLAND_NO_PERMISSION_CHECKS: zodat ook ons eigen fotoscriptje een schermfoto mag vragen.
        stap "KWin starten met een virtueel scherm van 2560x1600 op schaal 2 (tekenen met de processor)"
        export LIBGL_ALWAYS_SOFTWARE=1 QT_QUICK_BACKEND=software KWIN_DRM_DEVICES=/dev/null KWIN_WAYLAND_NO_PERMISSION_CHECKS=1
        kwin_wayland --virtual --width 2560 --height 1600 --scale 2 \
            --no-lockscreen --no-global-shortcuts --socket wayland-foto &
        kwin_pid=$!
        # Pas als KWin zich op D-Bus meldt (org.kde.KWin) is hij echt klaar; het socket-bestand is er eerder.
        gewacht=0
        while [ "$gewacht" -lt 60 ]; do
            if [ "$(gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus \
                    --method org.freedesktop.DBus.NameHasOwner org.kde.KWin 2>/dev/null)" = "(true,)" ]; then
                break
            fi
            kill -0 "$kwin_pid" 2>/dev/null || break
            sleep 2
            gewacht=$((gewacht + 2))
        done
        if kill -0 "$kwin_pid" 2>/dev/null && [ -S "${XDG_RUNTIME_DIR:-/tmp}/wayland-foto" ]; then
            stap "KWin is er (Wayland-scherm 'wayland-foto', na ongeveer $gewacht s)"
            in_kwin "$scene"
            return
        fi
        kwin_code=0
        wait "$kwin_pid" || kwin_code=$?
        stap "Let op: KWin kwam niet op (stopte met code $kwin_code); we proberen plasmashell rechtstreeks op het X-scherm"
    fi

    # Zonder KWin (oudere beelden): plasmashell rechtstreeks op het X-scherm.
    stap "Geen kwin_wayland; plasmashell rechtstreeks op het X-scherm proberen"
    export QT_QPA_PLATFORM=xcb QT_QUICK_BACKEND=software QT_SCALE_FACTOR=2
    stap "plasmashell starten"
    plasmashell --no-respawn &
    plasma_pid=$!
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
            # Maten zijn in punten; met QT_SCALE_FACTOR=2 is het venster op de foto twee keer zo groot.
            stap "Startmenu openen (plasmawindowed org.bugos.startmenu)"
            plasmawindowed org.bugos.startmenu -qwindowgeometry 660x640+30+60 & ;;
        snelmenu)
            stap "Snelmenu openen (plasmawindowed org.bugos.snelmenu)"
            plasmawindowed org.bugos.snelmenu -qwindowgeometry 410x380+750+250 & ;;
        uitzetten)
            # In proefstand toont de greeter alle knoppen zonder logind; --windowed slaat de focusbewaker
            # over (die sluit het venster anders na 3 s). Met --choose vraagt hij "Wat wil je doen?".
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

# kwin_wayland heeft in het beeld extra rechten op het bestand zelf (cap_sys_nice). In een container
# mag een gewone gebruiker zo'n bestand niet starten ("Actie is niet toegestaan"). Voor een foto zijn
# die rechten niet nodig, dus halen we ze hier (alleen in deze wegwerpcontainer) van het bestand af.
KWIN="$(command -v kwin_wayland || true)"
if [ -n "$KWIN" ] && command -v setcap >/dev/null 2>&1; then
    # Een echte if in plaats van "A && B || true": zo meldt shellcheck (SC2015)
    # niets, en lukt het afhalen niet, dan gaat het script gewoon door.
    if setcap -r "$KWIN" 2>/dev/null; then
        stap "Extra rechten van $KWIN afgehaald (niet nodig voor een foto)"
    fi
fi

# Nu als oma, binnen één D-Bus-sessie (plasmashell, de activiteitenbeheerder en de menu's moeten
# elkaar daarop kunnen vinden). Dit script roept zichzelf opnieuw aan voor deel 2 hierboven.
stap "Klaargezet (thema $THEMA, scene $SCENE); nu als oma het bureaublad starten"
# QT_FORCE_STDERR_LOGGING=1: KDE-programma's schrijven hun meldingen anders naar journald, en dat is er hier niet.
exec runuser -u oma -- env HOME="$THUIS" USER=oma LOGNAME=oma XDG_RUNTIME_DIR=/tmp/run-oma DISPLAY="${DISPLAY:-:99}" \
    LANG=nl_NL.UTF-8 QT_FORCE_STDERR_LOGGING=1 ZELF="$ZELF" "${BUGOS_ENV[@]}" dbus-run-session -- bash "$ZELF" --als-oma "$SCENE"
