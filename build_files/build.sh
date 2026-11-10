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
chmod 0755 /usr/bin/bugos-* /usr/libexec/bugos-user-check
# De Python-onderdelen van BugOS vooraf vertalen: /usr is straks alleen-lezen, dus anders doet elke app dat bij
# elke start opnieuw. Met een controlegetal (checked-hash): ostree zet de tijden van bestanden gelijk, en een
# veranderd bestand (usr-overlay bij het zoeken naar een fout) wordt dan toch opnieuw gelezen (U313, U319).
find /usr/lib/bugos/python -name __pycache__ -prune -exec rm -rf {} +
python3 -m compileall -q --invalidation-mode checked-hash /usr/lib/bugos/python

# De pictogrammen van de apps in de BugOS Winkel meeleveren. Anders zie je op een vers systeem (de catalogus
# van Flathub is dan nog niet opgehaald) en zonder internet bij Firefox, LibreOffice, Spotify en Steam alleen een
# grijs bestandje. Lukt het ophalen niet (geen internet tijdens het bouwen), dan gaat de bouw gewoon door.
python3 - <<'EOF' || true
import json, pathlib, urllib.request
uit = pathlib.Path("/usr/share/bugos/store-icons")
uit.mkdir(parents=True, exist_ok=True)
apps = [a["id"] for a in json.load(open("/usr/share/bugos/store.json", encoding="utf-8"))["apps"]]
def haal(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "bugos-build"}), timeout=20).read()
for app_id in apps:
    try:
        icoon = json.loads(haal(f"https://flathub.org/api/v2/appstream/{app_id}")).get("icon") or ""
        if icoon.startswith("https://dl.flathub.org/"):
            (uit / f"{app_id}.png").write_bytes(haal(icoon))
    except Exception as e:  # noqa: BLE001
        print("BugOS Winkel: geen pictogram voor", app_id, e)
print(len(list(uit.glob("*.png"))), "van", len(apps), "Winkel-pictogrammen")
EOF
chmod 0644 /usr/share/bugos/store-icons/* 2>/dev/null || true

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
# Ook de updatemelder van KDE: die werkte Flatpak-apps stilletjes bij, ook bij 'Ik kies zelf wanneer' (U321).
mapfile -t TEVEEL < <(rpm -q --qf '%{NAME}
' plasma-discover-packagekit plasma-discover-offline-updates     plasma-discover-rpm-ostree plasma-discover-notifier 2>/dev/null | grep -v 'not installed' || true)
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
# Geen gebruiker na het installeren? Dan alsnog KDE's assistent om er een te maken.
systemctl enable bugos-user-check.service
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
# Programma's uit een .rpm/.deb (in hun doosje) ook bijwerken, bij "Updates vanzelf" (U465).
systemctl --global enable bugos-update-doosjes.timer

# 7. Standaard: updates automatisch (de gebruiker kan dit omzetten).
mkdir -p /etc/bugos
echo "UPDATES=auto" >/etc/bugos/updates.conf

# Opruimen zodat er geen extra softwarebronnen aan blijven staan.
dnf5 clean all
rm -rf /var/lib/dnf /run/dnf
