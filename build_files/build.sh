#!/usr/bin/bash
# BugOS - bouwscript
# ==================
# Dit script draait één keer tijdens het bouwen van BugOS (niet op de pc van
# de gebruiker). Het legt onze bestanden neer, installeert extra programma's
# en zet de BugOS-naam en -stijl goed.

set -ouex pipefail

BUGOS_VARIANT="${BUGOS_VARIANT:-main}"
BUGOS_VERSION="${BUGOS_VERSION:-dev}"

# 1. Onze eigen bestanden (scripts, stijl, logo, instellingen) neerleggen.
cp -avf /ctx/system_files/. /
chmod 0755 /usr/bin/bugos-*

# 2. Extra programma's installeren.
#    --skip-unavailable: als een pakket (even) niet bestaat, gaat de bouw
#    gewoon door in plaats van te stoppen.
mapfile -t PAKKETTEN < <(grep -vE '^\s*(#|$)' /ctx/packages.txt)
dnf5 install -y --skip-unavailable "${PAKKETTEN[@]}"

# Steam als echt systeemprogramma (beste voor controllers en game-modus).
# Lukt dat niet, dan zet bugos-eerste-start.service Steam later als Flatpak neer.
dnf5 install -y --skip-unavailable steam || true

# 3. De naam "BugOS" in het systeem zetten (bij "Over dit systeem" e.d.).
#    ID blijft "fedora", anders snappen sommige programma's het niet meer.
sed -i \
    -e "s|^NAME=.*|NAME=\"BugOS\"|" \
    -e "s|^PRETTY_NAME=.*|PRETTY_NAME=\"BugOS ${BUGOS_VERSION}\"|" \
    -e "s|^HOME_URL=.*|HOME_URL=\"https://github.com/253UgurSahin/BugOS\"|" \
    -e "s|^DOCUMENTATION_URL=.*|DOCUMENTATION_URL=\"https://github.com/253UgurSahin/BugOS/tree/main/docs\"|" \
    -e "s|^SUPPORT_URL=.*|SUPPORT_URL=\"https://github.com/253UgurSahin/BugOS/issues\"|" \
    -e "s|^BUG_REPORT_URL=.*|BUG_REPORT_URL=\"https://github.com/253UgurSahin/BugOS/issues\"|" \
    -e "s|^LOGO=.*|LOGO=bugos-logo|" \
    -e "s|^DEFAULT_HOSTNAME=.*|DEFAULT_HOSTNAME=\"bugos\"|" \
    /usr/lib/os-release
grep -q '^BUGOS_VARIANT=' /usr/lib/os-release ||
    echo "BUGOS_VARIANT=\"${BUGOS_VARIANT}\"" >>/usr/lib/os-release

mkdir -p /usr/share/bugos
cat >/usr/share/bugos/image-info.json <<EOF
{
  "naam": "BugOS",
  "variant": "${BUGOS_VARIANT}",
  "versie": "${BUGOS_VERSION}"
}
EOF

# Logo ook beschikbaar maken als gewoon pictogram.
install -Dm0644 /usr/share/bugos/logo.svg /usr/share/icons/hicolor/scalable/apps/bugos-logo.svg
install -Dm0644 /usr/share/bugos/logo.svg /usr/share/pixmaps/bugos-logo.svg

# 4. BugOS-stijl als standaard voor nieuwe gebruikers.
kwriteconfig6 --file /etc/xdg/kdeglobals --group KDE --key LookAndFeelPackage org.bugos.desktop
kwriteconfig6 --file /etc/xdg/kdeglobals --group General --key ColorScheme BugOSLicht
# Dubbelklik om te openen, net als in Windows.
kwriteconfig6 --file /etc/xdg/kdeglobals --group KDE --key SingleClick false

# Lettertypes: Inter voor alles, JetBrains Mono voor code (meegeleverd in /usr/share/fonts/bugos).
fc-cache -f /usr/share/fonts/bugos || true
LETTER="Inter,10,-1,5,400,0,0,0,0,0,0,0,0,0,0,1"
for sleutel in font menuFont toolBarFont; do
    kwriteconfig6 --file /etc/xdg/kdeglobals --group General --key "$sleutel" "$LETTER"
done
kwriteconfig6 --file /etc/xdg/kdeglobals --group General --key smallestReadableFont "Inter,8,-1,5,400,0,0,0,0,0,0,0,0,0,0,1"
kwriteconfig6 --file /etc/xdg/kdeglobals --group General --key fixed "JetBrains Mono,10,-1,5,400,0,0,0,0,0,0,0,0,0,0,1"
kwriteconfig6 --file /etc/xdg/kdeglobals --group WM --key activeFont "Inter,10,-1,5,600,0,0,0,0,0,0,0,0,0,0,1"
# Accentkleur: lieveheersbeestjesrood
kwriteconfig6 --file /etc/xdg/kdeglobals --group General --key AccentColor "222,47,62"

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


schema = lees("/usr/share/color-schemes/BugOSLicht.colors")
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
UITZET=/usr/share/bugos/uitzetscherm/Logout.qml
UITZET_SHELL=/usr/share/plasma/shells/org.kde.plasma.desktop/contents/logout
if [ -d "$UITZET_SHELL" ]; then
    if [ -f "$UITZET_SHELL/Logout.qml" ] && [ ! -f "$UITZET_SHELL/Logout.qml.kde" ]; then
        cp -a "$UITZET_SHELL/Logout.qml" "$UITZET_SHELL/Logout.qml.kde"
    fi
    install -m0644 "$UITZET" "$UITZET_SHELL/Logout.qml"
fi
mkdir -p /usr/share/plasma/look-and-feel/org.bugos.desktop/contents/logout
install -m0644 "$UITZET" /usr/share/plasma/look-and-feel/org.bugos.desktop/contents/logout/Logout.qml

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

# 5. Bestandstypes koppelen: .exe -> bugos-exe, .rpm/.deb -> bugos-pakket.
update-desktop-database /usr/share/applications || true

# 6. Diensten aanzetten.
systemctl enable bugos-eerste-start.service
systemctl enable podman.socket || true
# Elke gebruiker: dagelijks kijken of er een update is (doet alleen iets bij "zelf updaten").
systemctl --global enable bugos-updatecheck.timer

# 7. Standaard: updates automatisch (de gebruiker kan dit omzetten).
mkdir -p /etc/bugos
echo "UPDATES=auto" >/etc/bugos/updates.conf

# Opruimen zodat er geen extra softwarebronnen aan blijven staan.
dnf5 clean all
rm -rf /var/lib/dnf /run/dnf
