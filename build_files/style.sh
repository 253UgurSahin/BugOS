#!/usr/bin/bash
# BugOS - bouwscript, stap 4: de BugOS-stijl als standaard voor nieuwe gebruikers
# ===============================================================================
# Wordt ingelezen door build.sh (". /ctx/style.sh"), niet los gedraaid: het
# draait dan met dezelfde instellingen (set -ouex pipefail).

# 4. BugOS-stijl als standaard voor nieuwe gebruikers.
kwriteconfig6 --file /etc/xdg/kdeglobals --group KDE --key LookAndFeelPackage org.bugos.desktop
kwriteconfig6 --file /etc/xdg/kdeglobals --group General --key ColorScheme BugOSLight
# Dubbelklik om te openen, net als in Windows.
kwriteconfig6 --file /etc/xdg/kdeglobals --group KDE --key SingleClick false

# De vensterbalk (titelbalk) in BugOS-stijl. We gebruiken de Breeze-rand van
# KDE (goede schaduwen en ronde hoeken, volgt vanzelf licht en donker) met:
#  - de kleur van de bovenkant van het venster (BugOS-kleurenschema), zonder
#    streep eronder: balk en venster lopen in elkaar over;
#  - grote ronde knoppen, en een rood rondje bij "sluiten";
#  - de titel links, zoals in de BugOS-apps; geen extra knoppen links.
kwriteconfig6 --file /etc/xdg/kwinrc --group org.kde.kdecoration2 --key library org.kde.breeze
kwriteconfig6 --file /etc/xdg/kwinrc --group org.kde.kdecoration2 --key theme Breeze
kwriteconfig6 --file /etc/xdg/kwinrc --group org.kde.kdecoration2 --key ButtonsOnLeft ""
kwriteconfig6 --file /etc/xdg/kwinrc --group org.kde.kdecoration2 --key ButtonsOnRight IAX
kwriteconfig6 --file /etc/xdg/kwinrc --group org.kde.kdecoration2 --key BorderSize None
kwriteconfig6 --file /etc/xdg/kwinrc --group org.kde.kdecoration2 --key BorderSizeAuto false
kwriteconfig6 --file /etc/xdg/breezerc --group Common --key OutlineCloseButton true
kwriteconfig6 --file /etc/xdg/breezerc --group Common --key ShadowSize ShadowLarge
kwriteconfig6 --file /etc/xdg/breezerc --group Windeco --key ButtonSize ButtonLarge
kwriteconfig6 --file /etc/xdg/breezerc --group Windeco --key DrawTitleBarSeparator false
kwriteconfig6 --file /etc/xdg/breezerc --group Windeco --key DrawBackgroundGradient false
kwriteconfig6 --file /etc/xdg/breezerc --group Windeco --key TitleAlignment AlignLeft

# Eén ontwerptaal voor het hele systeem (zie tools/design/README.md). De eigen
# BugOS-apps tekenen zichzelf; al het andere krijgt dezelfde stijl van:
#  - KDE-programma's (ook KDE Instellingen, Dolphin, Schijfbeheer): de
#    programmastijl Kvantum "BugOS" (licht) of "BugOSDark" (donker);
#  - pictogrammen: het thema "BugOS" (de rest komt van Breeze);
#  - taakbalk, pop-ups en tooltips: de Plasma-stijl "bugos".
# Licht/donker omzetten doet bugos-theme; die zet ook Kvantum om.
kwriteconfig6 --file /etc/xdg/kdeglobals --group KDE --key widgetStyle kvantum
kwriteconfig6 --file /etc/xdg/kdeglobals --group Icons --key Theme BugOS
kwriteconfig6 --file /etc/xdg/plasmarc --group Theme --key name bugos
# Kvantum leest zijn keuze uit ~/.config/Kvantum: nieuwe gebruikers krijgen hem
# via /etc/skel, bestaande via "bugos-theme eerste-keer" bij het inloggen.
for kv in /etc/skel/.config/Kvantum /etc/xdg/Kvantum; do
    mkdir -p "$kv"
    printf '[General]\ntheme=BugOS\n' >"$kv/kvantum.kvconfig"
done
# GTK-programma's (zoals Firefox) zoeken pictogrammen via deze index.
gtk-update-icon-cache -f -t /usr/share/icons/BugOS || true

# GTK-programma's (Firefox, GNOME-apps, GTK-Flatpaks): het Breeze-GTK-thema. KDE
# zet daar zelf de BugOS-kleuren in (colors.css); bugos-theme zet er bij het
# inloggen de BugOS-laag bovenop (/usr/share/bugos/gtk, gemaakt door
# tools/gtk/make.py: alleen hoeken, schuifjes, schakelaars en het rood).
# We houden Breeze als naam: alleen dan geeft KDE GTK-vensters dezelfde
# vensterknoppen als alle andere vensters.
if [ ! -f /usr/share/themes/Breeze/gtk-3.0/gtk.css ] || [ ! -f /usr/share/themes/Breeze/gtk-4.0/gtk.css ]; then
    dnf5 install -y --setopt=install_weak_deps=False breeze-gtk-gtk3 breeze-gtk-gtk4 ||
        echo "LET OP: Breeze-GTK ontbreekt; GTK-programma's krijgen dan Adwaita met de BugOS-laag."
fi
for v in 3.0 4.0; do
    mkdir -p "/etc/xdg/gtk-$v"
    cat >"/etc/xdg/gtk-$v/settings.ini" <<'EOF'
[Settings]
gtk-theme-name=Breeze
gtk-icon-theme-name=BugOS
gtk-font-name=Inter 10
gtk-cursor-theme-name=breeze_cursors
gtk-application-prefer-dark-theme=false
EOF
done

# Terminal (Konsole): het BugOS-profiel (kleuren uit tools/konsole/make.py,
# JetBrains Mono). bugos-theme wisselt licht/donker.
kwriteconfig6 --file /etc/xdg/konsolerc --group "Desktop Entry" --key DefaultProfile BugOS.profile

# Lettertypes: Inter voor alles, JetBrains Mono voor code (meegeleverd in /usr/share/fonts/bugos).
fc-cache -f /usr/share/fonts/bugos || true
LETTER="Inter,10,-1,5,400,0,0,0,0,0,0,0,0,0,0,1"
for sleutel in font menuFont toolBarFont; do
    kwriteconfig6 --file /etc/xdg/kdeglobals --group General --key "$sleutel" "$LETTER"
done
kwriteconfig6 --file /etc/xdg/kdeglobals --group General --key smallestReadableFont "Inter,8,-1,5,400,0,0,0,0,0,0,0,0,0,0,1"
kwriteconfig6 --file /etc/xdg/kdeglobals --group General --key fixed "JetBrains Mono,10,-1,5,400,0,0,0,0,0,0,0,0,0,0,1"
kwriteconfig6 --file /etc/xdg/kdeglobals --group WM --key activeFont "Inter,10,-1,5,600,0,0,0,0,0,0,0,0,0,0,1"
# Geen aparte KDE-accentkleur: die zou de zachte BugOS-selectie bij elke wissel van
# licht/donker weer fel maken. Het rood zit al in het kleurenschema (DecorationFocus).

# KDE's schakelaar (QQC2 Switch, o.a. in KDE Instellingen) kleurt "aan" met de selectiekleur,
# en die is in BugOS zacht rood. Laat hem net als in de BugOS-apps fel rood zijn met een wit bolletje.
SCHAKEL=/usr/lib64/qt6/qml/org/kde/desktop/private
if [ -f "$SCHAKEL/SwitchIndicator.qml" ]; then
    sed -i         -e 's/indicator.control.checked ? Kirigami.Theme.highlightColor : handleBorderColor/indicator.control.checked ? Kirigami.Theme.focusColor : handleBorderColor/'         -e 's/color: Qt.alpha(Kirigami.Theme.highlightColor, 0.5)/color: Kirigami.Theme.focusColor/'         -e 's/readonly property color handleColor: Kirigami.Theme.backgroundColor/readonly property color handleColor: "#ffffff"/'         "$SCHAKEL/SwitchIndicator.qml"
    # Zonder "prefer" laadt Qt de QML van schijf in plaats van de ingebouwde kopie.
    sed -i '/^prefer :\/qt\/qml\/org\/kde\/desktop\/private\/$/d' "$SCHAKEL/qmldir"
    grep -q focusColor "$SCHAKEL/SwitchIndicator.qml" || echo "LET OP: schakelaar-aanpassing paste niet (nieuwe KDE-versie?)"
fi

# De kleuren van "BugOS Licht" ook echt in de standaardinstellingen zetten.
# Alleen de naam van het schema is niet genoeg: programma's zoals de verkenner
# lezen de kleuren zelf uit kdeglobals. Zo is alles meteen in BugOS-kleuren.
python3 - <<'PY'
import configparser


def lees(pad):
    c = configparser.RawConfigParser(strict=False, interpolation=None)
    c.optionxform = str
    c.read(pad, encoding="utf-8")
    return c


schema = lees("/usr/share/color-schemes/BugOSLight.colors")
glob = lees("/etc/xdg/kdeglobals")
for groep in schema.sections():
    if groep == "General":
        continue
    if not glob.has_section(groep):
        glob.add_section(groep)
    for sleutel, waarde in schema.items(groep):
        glob.set(groep, sleutel, waarde)
with open("/etc/xdg/kdeglobals", "w", encoding="utf-8") as f:
    glob.write(f, space_around_delimiters=False)
PY

# De verkenner (Dolphin, in BugOS "Bestanden"): rustig en duidelijk.
kwriteconfig6 --file /etc/xdg/dolphinrc --group MainWindow --key MenuBar Disabled
kwriteconfig6 --file /etc/xdg/dolphinrc --group General --key ShowZoomSlider false
kwriteconfig6 --file /etc/xdg/dolphinrc --group General --key ShowSpaceInfo true
kwriteconfig6 --file /etc/xdg/dolphinrc --group General --key RememberOpenedTabs false
kwriteconfig6 --file /etc/xdg/dolphinrc --group General --key BrowseThroughArchives false

# Opstartscherm na het inloggen (KSplash) uit ons look-and-feel-pakket
kwriteconfig6 --file /etc/xdg/ksplashrc --group KSplash --key Engine KSplashQML
kwriteconfig6 --file /etc/xdg/ksplashrc --group KSplash --key Theme org.bugos.desktop

# Vergrendelscherm en inlogscherm: de BugOS-achtergrond
kwriteconfig6 --file /etc/xdg/kscreenlockerrc --group Greeter --group Wallpaper --group org.kde.image --group General \
    --key Image "file:///usr/share/wallpapers/bugos/"
kwriteconfig6 --file /etc/xdg/kscreenlockerrc --group Greeter --group Wallpaper --group org.kde.image --group General \
    --key PreviewImage "file:///usr/share/wallpapers/bugos/contents/screenshot.jpg"
# Het inlogscherm. Fedora 44 gebruikt "Plasma Login Manager" (niet meer
# SDDM), met de achtergrond van Fedora. Nu: Stip.
if [ -d /usr/lib/plasmalogin ]; then
    cat >/usr/lib/plasmalogin/defaults.conf <<'EOF'
[Greeter]
WallpaperPlugin=org.kde.image

[Greeter][Wallpaper][org.kde.image][General]
Image=file:///usr/share/wallpapers/bugos/
PreviewImage=file:///usr/share/wallpapers/bugos/contents/screenshot.jpg
EOF
fi
# Oudere systemen met SDDM: daar ook de BugOS-achtergrond.
if [ -d /usr/share/sddm/themes/breeze ]; then
    printf '[General]\nbackground=/usr/share/wallpapers/bugos/contents/images_dark/3840x2160.jpg\ntype=image\n' \
        >/usr/share/sddm/themes/breeze/theme.conf.user
fi

# 4a. Uitzetscherm: het scherm met "Uitzetten", "Opnieuw opstarten" en
#     "Afmelden" dat je ziet als je via het startmenu uitzet. Plasma 6 laadt
#     dat scherm (Logout.qml) uit het SHELL-pakket org.kde.plasma.desktop, niet
#     uit het look-and-feel-pakket; oudere en andere paden kijken juist in het
#     look-and-feel-pakket. Daarom zetten we onze versie op allebei de plekken.
#     Het origineel van KDE blijft ernaast staan als Logout.qml.kde (om terug
#     te kunnen kijken); Plasma gebruikt dat bestand niet.
UITZET=/usr/share/bugos/logout/Logout.qml
UITZET_SHELL=/usr/share/plasma/shells/org.kde.plasma.desktop/contents/logout
if [ -d "$UITZET_SHELL" ]; then
    if [ -f "$UITZET_SHELL/Logout.qml" ] && [ ! -f "$UITZET_SHELL/Logout.qml.kde" ]; then
        cp -a "$UITZET_SHELL/Logout.qml" "$UITZET_SHELL/Logout.qml.kde"
    fi
    install -m0644 "$UITZET" "$UITZET_SHELL/Logout.qml"
    install -m0644 "${UITZET%/*}/bugos-aftellen.js" "$UITZET_SHELL/bugos-aftellen.js"
fi
mkdir -p /usr/share/plasma/look-and-feel/org.bugos.desktop/contents/logout
install -m0644 "$UITZET" /usr/share/plasma/look-and-feel/org.bugos.desktop/contents/logout/Logout.qml
install -m0644 "${UITZET%/*}/bugos-aftellen.js" /usr/share/plasma/look-and-feel/org.bugos.desktop/contents/logout/bugos-aftellen.js

# Opstartlogo (Plymouth): het BugOS-logo onderaan het opstartscherm.
if [ -d /usr/share/plymouth/themes/spinner ]; then
    install -m0644 /usr/share/bugos/plymouth-watermark.png /usr/share/plymouth/themes/spinner/watermark.png
    KERNEL="$(find /usr/lib/modules -maxdepth 1 -mindepth 1 -type d -printf '%P\n' | head -1)"
    # Eerst naar een tijdelijk bestand: lukt het niet, dan blijft het oude gewoon staan.
    if dracut --no-hostonly --kver "$KERNEL" --reproducible --zstd --add ostree -f /tmp/initramfs-bugos.img; then
        install -m0600 /tmp/initramfs-bugos.img "/usr/lib/modules/$KERNEL/initramfs.img"
    fi
    rm -f /tmp/initramfs-bugos.img
fi

# 4b. Bekende KDE-programma's een simpele BugOS-naam geven in het startmenu.
#     hernoem <bestand> <Nederlandse naam> <Engelse naam>
hernoem() {
    local f="/usr/share/applications/$1"
    [ -f "$f" ] || return 0
    awk -v nl="$2" -v en="$3" '
        /^\[/ { hoofd = ($0 == "[Desktop Entry]") }
        hoofd && /^Name(\[[^]]*\])?=/ { if (!gedaan) { print "Name=" en; print "Name[nl]=" nl; gedaan = 1 }; next }
        { print }
    ' "$f" >"$f.nieuw" && mv "$f.nieuw" "$f"
}
hernoem org.kde.discover.desktop "Meer apps" "More apps"
hernoem org.kde.dolphin.desktop "Dolphin (voor gevorderden)" "Dolphin (advanced)"
hernoem systemsettings.desktop "Alle instellingen" "All settings"
hernoem org.kde.partitionmanager.desktop "Schijfbeheer (voor gevorderden)" "Disk management (advanced)"
hernoem org.kde.plasma-systemmonitor.desktop "Systeemmonitor (voor gevorderden)" "System Monitor (advanced)"
hernoem org.kde.konsole.desktop "Terminal" "Terminal"

# 4c. Het startmenu rustig houden (de Bugie-test): hulpjes voor gevorderden en
#     losse onderdelen van Wine (Kladblok, Regedit, Mijnenveger...) verbergen.
#     Ze werken gewoon; een .exe openen gaat via bugos-exe. NoDisplay verandert
#     niets aan wat een bestand opent.
verberg() {
    local f="/usr/share/applications/$1"
    [ -f "$f" ] || return 0
    if grep -q '^NoDisplay=' "$f"; then
        sed -i 's/^NoDisplay=.*/NoDisplay=true/' "$f"
    else
        sed -i '0,/^\[Desktop Entry\]/s//[Desktop Entry]\nNoDisplay=true/' "$f"
    fi
}
for f in /usr/share/applications/wine-*.desktop; do
    [ -e "$f" ] && verberg "$(basename "$f")"
done
# "KDE System Settings" is dezelfde als "All settings" (systemsettings.desktop).
for app in kdesystemsettings.desktop htop.desktop nvtop.desktop org.kde.kdebugsettings.desktop \
    org.kde.drkonqi.coredump.gui.desktop org.kde.kjournaldbrowser.desktop; do
    verberg "$app"
done

# 4d. Eigen pictogramnamen voor KDE-programma's waarvan de standaardnaam ook in
#     KDE Instellingen gebruikt wordt (daar is het een lijnicoon, hier een app-tegel).
icoon() {
    local f="/usr/share/applications/$1"
    [ -f "$f" ] && sed -i "0,/^Icon=.*/s//Icon=$2/" "$f"
    return 0
}
icoon systemsettings.desktop systemsettings
icoon org.kde.kinfocenter.desktop org.kde.kinfocenter
icoon org.kde.kwalletmanager.desktop org.kde.kwalletmanager
