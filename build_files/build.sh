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
hernoem org.kde.dolphin.desktop "Bestanden" "Files"
hernoem systemsettings.desktop "Alle instellingen" "All settings"
hernoem org.kde.partitionmanager.desktop "Schijven" "Disks"
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
