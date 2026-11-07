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
# Vaste rechten, wat de bouwmap ook zegt (vanaf Windows is alles 0777, en dan
# klaagt systemd over "world-writable" diensten): bestanden 0644, mappen 0755,
# alleen de programma's in /usr/bin uitvoerbaar.
(cd /ctx/system_files && find . -type f -print0) | while IFS= read -r -d '' f; do chmod 0644 "/${f#./}"; done
(cd /ctx/system_files && find . -mindepth 1 -type d -print0) | while IFS= read -r -d '' d; do chmod 0755 "/${d#./}"; done
chmod 0755 /usr/bin/bugos-*

# 2. Extra programma's installeren.
#    --skip-unavailable: als een pakket (even) niet bestaat, gaat de bouw
#    gewoon door in plaats van te stoppen.
mapfile -t PAKKETTEN < <(grep -vE '^\s*(#|$)' /ctx/packages.txt)
dnf5 install -y --skip-unavailable "${PAKKETTEN[@]}"

# KDE Discover voor "Meer apps zoeken" in de BugOS Winkel: alleen Flatpak-apps.
# Zonder weak deps, anders komt PackageKit mee en toont Discover Fedora-
# pakketten en "updates" die op BugOS (alleen-lezen systeem) niet kunnen.
dnf5 install -y --setopt=install_weak_deps=False plasma-discover plasma-discover-flatpak
# Weg met wat Discover laat zien over het systeem zelf: Fedora-pakketten
# (PackageKit) en systeemupdates (rpm-ostree, dat zit in Kinoite). Updates doet
# BugOS zelf (stap 6). In één keer, omdat ze van elkaar afhangen.
mapfile -t TEVEEL < <(rpm -q --qf '%{NAME}
' plasma-discover-packagekit plasma-discover-offline-updates     plasma-discover-rpm-ostree 2>/dev/null | grep -v 'not installed' || true)
if [ "${#TEVEEL[@]}" -gt 0 ]; then
    rpm -e "${TEVEEL[@]}"
fi

# Steam als echt systeemprogramma (beste voor controllers en game-modus).
# Lukt dat niet, dan zet bugos-first-boot.service Steam later als Flatpak neer.
dnf5 install -y --skip-unavailable steam || true

# 3. BugOS is een eigen systeem, net als Bazzite (naam, logo, ondertekende updates): zie system.sh.
# shellcheck source=build_files/system.sh
. /ctx/system.sh

# 4. BugOS-stijl als standaard voor nieuwe gebruikers: zie style.sh.
# shellcheck source=build_files/style.sh
. /ctx/style.sh

# 5. Bestandstypes koppelen: .exe -> bugos-exe, .rpm/.deb -> bugos-package.
update-desktop-database /usr/share/applications || true

# 6. Diensten aanzetten.
systemctl enable bugos-first-boot.service
# Updates: BugOS regelt dit zelf (geen uupd van Universal Blue).
#  - het systeem: rpm-ostree haalt de nieuwe BugOS op de achtergrond op en zet
#    hem klaar ("stage"); hij wordt actief bij de volgende keer opstarten.
#  - de apps (Flatpak): bugos-update-apps.timer, elke dag.
#  bugos-updates auto|hand zet ze allebei aan of uit.
if grep -q '^#\?AutomaticUpdatePolicy=' /etc/rpm-ostreed.conf 2>/dev/null; then
    sed -i 's|^#\?AutomaticUpdatePolicy=.*|AutomaticUpdatePolicy=stage|' /etc/rpm-ostreed.conf
else
    printf '[Daemon]\nAutomaticUpdatePolicy=stage\n' >>/etc/rpm-ostreed.conf
fi
systemctl enable rpm-ostreed-automatic.timer bugos-update-apps.timer
systemctl enable podman.socket || true
# Elke gebruiker: dagelijks kijken of er een update is (doet alleen iets bij "zelf updaten").
systemctl --global enable bugos-updatecheck.timer

# 7. Standaard: updates automatisch (de gebruiker kan dit omzetten).
mkdir -p /etc/bugos
echo "UPDATES=auto" >/etc/bugos/updates.conf

# Opruimen zodat er geen extra softwarebronnen aan blijven staan.
dnf5 clean all
rm -rf /var/lib/dnf /run/dnf
