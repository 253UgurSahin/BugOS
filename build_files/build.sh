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

# KDE Discover voor "Meer apps zoeken" in de BugOS Winkel: alleen Flatpak-apps.
# Zonder weak deps, anders komt PackageKit mee en toont Discover Fedora-
# pakketten en "updates" die op BugOS (alleen-lezen systeem) niet kunnen.
# Systeemupdates doet BugOS zelf. (Aurora had hier Bazaar; zie stap 3b.)
dnf5 install -y --setopt=install_weak_deps=False plasma-discover plasma-discover-flatpak
# Voor de zekerheid: waren ze er toch, dan samen weg (in één keer, omdat ze
# van elkaar afhangen).
mapfile -t TEVEEL < <(rpm -q --qf '%{NAME}\n' plasma-discover-packagekit plasma-discover-offline-updates 2>/dev/null | grep -v 'not installed' || true)
if [ "${#TEVEEL[@]}" -gt 0 ]; then
    rpm -e "${TEVEEL[@]}"
fi

# Steam als echt systeemprogramma (beste voor controllers en game-modus).
# Lukt dat niet, dan zet bugos-eerste-start.service Steam later als Flatpak neer.
dnf5 install -y --skip-unavailable steam || true

# 3. De naam "BugOS" in het systeem zetten (bij "Over dit systeem" e.d.).
#    ID blijft wat de fundering zegt ("aurora", met ID_LIKE="fedora"): het
#    installatieprogramma (profiel), Cockpit en fwupd zoeken daarop. Zie 3b.
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

# 3b. Alles wat de gebruiker nog als "Aurora" (of Fedora) ziet, wordt BugOS.
#     BugOS is gebouwd op Aurora, maar dat hoeft niemand te zien: de computer
#     heet overal BugOS. ID=aurora, ID_LIKE=fedora en VERSION_ID laten we
#     staan: het installatieprogramma (profiel), Cockpit, fwupd en dnf zoeken
#     daarop. Alleen wat op het scherm komt, passen we aan.

# os-release: de velden die programma's laten zien ("Over dit systeem",
# hostnamectl, fastfetch, lsb_release). Daar stond "(Kinoite)", "Stargazer",
# "OS Image: aurora" en "cpe:/o:universal-blue:aurora".
if [ "$BUGOS_VARIANT" = nvidia ]; then
    BEELD_ID=bugos-nvidia
else
    BEELD_ID=bugos
fi
sed -i \
    -e "s|^VERSION=.*|VERSION=\"${BUGOS_VERSION}\"|" \
    -e "s|^VARIANT=.*|VARIANT=\"BugOS\"|" \
    -e "s|^VERSION_CODENAME=.*|VERSION_CODENAME=\"\"|" \
    -e "s|^CPE_NAME=.*|CPE_NAME=\"cpe:/o:bugos:bugos:${BUGOS_VERSION}\"|" \
    -e "s|^IMAGE_ID=.*|IMAGE_ID=\"${BEELD_ID}\"|" \
    -e "s|^IMAGE_VERSION=.*|IMAGE_VERSION=\"${BUGOS_VERSION}\"|" \
    -e "s|^OSTREE_VERSION=.*|OSTREE_VERSION='${BUGOS_VERSION}'|" \
    -e "s|^BUILD_ID=.*|BUILD_ID=\"${BUGOS_VERSION}\"|" \
    -e "s|^ANSI_COLOR=.*|ANSI_COLOR=\"0;38;2;222;47;62\"|" \
    /usr/lib/os-release

# /etc/system-release was een verwijzing naar "Fedora release 44". Het
# opstartprogramma (bootupd) noemt de opstartkeuze in het BIOS/UEFI-menu
# daarnaar, dus daar stond "Fedora". Nu een eigen bestand: "BugOS release 44".
# (/etc/fedora-release blijft Fedora, voor programma's die dat nodig hebben.)
rm -f /etc/system-release
printf 'BugOS release %s\n' "$(. /usr/lib/os-release && echo "${VERSION_ID}")" >/etc/system-release

# Aurora's "eerste keer opstarten"-assistent van KDE (plasma-setup) maakt
# zelf een gebruiker en zet Aurora's thema neer. Bij BugOS maakt het
# installatieprogramma de gebruiker al, en BugOS Welkom doet de rest.
# Dit bestand betekent voor plasma-setup: "al gedaan".
touch /etc/plasma-setup-done

# Het "Welcome Center" van KDE (met "Welcome to Aurora" en het Aurora-logo)
# verscheen bij de eerste keer inloggen en op de USB-stick. BugOS heeft een
# eigen welkomstapp (bugos-welkom), dus deze gaat er helemaal uit. Geen
# ander pakket heeft hem nodig (alleen plasma-workspace "raadt hem aan").
# rpm -e in plaats van dnf remove: dan gaan er niet stilletjes andere
# pakketten mee die toevallig alleen hierdoor waren binnengekomen.
if rpm -q plasma-welcome >/dev/null 2>&1; then
    rpm -e plasma-welcome
fi
# Aurora zet het echte programma onder een andere naam neer en zijn eigen
# welkomsttekst in een losse map; die zijn van geen pakket, dus zelf weghalen.
rm -f /usr/bin/plasma-welcome-original
rm -rf /usr/share/plasma/plasma-welcome

# De terminal begon met "Welcome to Aurora" en links naar Aurora
# (ublue-motd, ook in fish). Weg ermee: een terminal hoort rustig te openen.
rm -f /etc/profile.d/ublue-motd.sh /usr/bin/ublue-motd /usr/share/fish/vendor_conf.d/fish_greeting.fish
rm -rf /usr/share/ublue-os/motd
# fastfetch/neofetch-aliassen wijzen naar Aurora's versie met Aurora-logo
# en "Stargazers"-tellers. Weg; fastfetch krijgt hieronder ons eigen logo.
rm -f /etc/profile.d/ublue-fastfetch.sh /usr/share/fish/vendor_conf.d/ublue-fastfetch.fish \
    /usr/bin/ublue-fastfetch /usr/share/ublue-os/fastfetch.jsonc /usr/share/ublue-os/aurora-ascii-logo.txt
# Gewone fastfetch kiest zijn logo op ID (=aurora), dus geven we hem zelf
# een instelling met het lieveheersbeestje (fastfetch leest /etc/xdg).
mkdir -p /etc/xdg/fastfetch
cat >/usr/share/bugos/fastfetch-logo.txt <<'EOF'
$1      ▄▄▄
$1    ▄█▀ ▀█▄
$2  ▄████$1█$2████▄
$2 ██ ▀▀ $1█$2 ▀▀ ██
$2 ████▄▄$1█$2▄▄████
$2  ▀████$1█$2████▀
$2     ▀▀$1▀$2▀▀
EOF
cat >/etc/xdg/fastfetch/config.jsonc <<'EOF'
{
    "logo": {
        "type": "file",
        "source": "/usr/share/bugos/fastfetch-logo.txt",
        "color": { "1": "white", "2": "red" }
    },
    "modules": [
        "title", "separator",
        { "type": "os", "format": "{pretty-name}" },
        "kernel", "uptime", "packages", "shell", "de", "terminal",
        "cpu", "gpu", "memory", "disk", "break", "colors"
    ]
}
EOF

# Wat ujust en de andere Universal Blue-hulpjes over "dit systeem" lezen.
# Daar stond Aurora (ghcr.io/ublue-os/aurora); dan zou bijvoorbeeld
# "ujust rebase-helper" de computer naar Aurora kunnen omzetten.
cat >/usr/share/ublue-os/image-info.json <<EOF
{
  "image-name": "${BEELD_ID}",
  "image-flavor": "${BUGOS_VARIANT}",
  "image-vendor": "253ugursahin",
  "image-ref": "ostree-unverified-registry:ghcr.io/253ugursahin/${BEELD_ID}",
  "image-tag": "latest",
  "base-image-name": "aurora",
  "fedora-version": "$(. /usr/lib/os-release && echo "${VERSION_ID}")"
}
EOF

# Aurora-apps in het startmenu en de zoekbalk ("Documentation", "Community",
# "Aurora Offline Docs", "System Update") en de instellingenpagina
# "Aurora Preferences" (die kan de computer zelfs naar Aurora omzetten).
for f in dev.getaurora.documentation dev.getaurora.discussions dev.getaurora.offline-docs dev.getaurora.system-update; do
    rm -f "/usr/share/applications/$f.desktop"
done
rm -f /usr/share/kglobalaccel/dev.getaurora.offline-docs.desktop \
    /usr/share/icons/hicolor/scalable/apps/aurora-docs.svg \
    /usr/share/icons/hicolor/scalable/apps/aurora-discussions.svg \
    /usr/share/icons/hicolor/scalable/apps/aurora-update.svg
rm -rf /usr/share/doc/aurora
if rpm -q kcm_ublue >/dev/null 2>&1; then
    rpm -e kcm_ublue
fi

# Aurora's winkel "Bazaar" (voorpagina "Aurora Recommends", met Aurora-
# plaatjes) werd bij de eerste start vanzelf geïnstalleerd. BugOS heeft één
# winkel: de BugOS Winkel, met "Meer apps zoeken" in KDE Discover (zie
# packages.txt). Twee of drie winkels is verwarrend.
rm -f /usr/share/flatpak/preinstall.d/bazaar.preinstall /usr/lib/tmpfiles.d/bazaar-flatpak.conf \
    /usr/share/factory/var/lib/flatpak/overrides/io.github.kolunmi.Bazaar
rm -rf /etc/bazaar
if rpm -q krunner-bazaar >/dev/null 2>&1; then
    rpm -e krunner-bazaar
fi
# Aurora zette in de zoekbalk (KRunner) de Discover-resultaten uit en Bazaar
# aan. Zonder dat bestand gelden de gewone KDE-instellingen weer.
rm -f /usr/share/kde-settings/kde-profile/default/xdg/krunnerrc

# Firefox: begint niet meer op de Fedora-startpagina, en heet "voor BugOS".
FF=/usr/lib64/firefox
if [ -d "$FF" ]; then
    sed -i -e 's|https://start.fedoraproject.org/|about:home|' -e '/browser.newtabpage.pinned/d' \
        "$FF/browser/defaults/preferences/firefox-redhat-default-prefs.js" || true
    mkdir -p "$FF/distribution"
    cat >"$FF/distribution/distribution.ini" <<'EOF'
[Global]
id=bugos
version=1.0
about=Mozilla Firefox voor BugOS

[Preferences]
app.distributor="bugos"
app.distributor.channel="bugos"
EOF
fi

# Aurora-meldingen ("Aurora IWD/ZFS deprecation") horen niet bij BugOS.
# mask in plaats van disable: anders zet de "preset" bij de eerste start
# ze misschien weer aan.
for eenheid in aurora-iwd-deprecation-notifier.timer aurora-iwd-deprecation-notifier.service \
    aurora-zfs-deprecation-notifier.timer aurora-zfs-deprecation-notifier.service; do
    if [ -e "/usr/lib/systemd/system/$eenheid" ]; then
        systemctl mask "$eenheid"
    fi
done

# Logo's: veel programma's gebruiken vaste bestandsnamen voor "het logo van
# dit systeem" (Over dit systeem, het installatieprogramma, sommige menu's).
# Bij Aurora staat daar de Aurora-"A". Wij leggen er het lieveheersbeestje neer.
MERK=/usr/share/bugos/merk
for png in system-logo.png fedora-logo-sprite.png fedora-logo.png fedora_logo_med.png fedora-logo-small.png; do
    install -Dm0644 "$MERK/merk-256.png" "/usr/share/pixmaps/$png"
done
# De "witte" versie is voor donkere achtergronden: het beestje met lichte kop.
install -Dm0644 "$MERK/merk-donker-256.png" /usr/share/pixmaps/system-logo-white.png
# fedora-logo.svg en fedora_whitelogo.svg waren verwijzingen naar de Aurora-banner.
rm -f /usr/share/pixmaps/fedora-logo.svg /usr/share/pixmaps/fedora_whitelogo.svg /usr/share/pixmaps/aurora-banner.svg
install -Dm0644 "$MERK/logo.svg" /usr/share/pixmaps/fedora-logo.svg
install -Dm0644 "$MERK/logo-wit.svg" /usr/share/pixmaps/fedora_whitelogo.svg
# Het algemene "logo van de distributie" (ook voor het pictogram start-here).
install -Dm0644 "$MERK/merk.svg" /usr/share/icons/hicolor/scalable/distributor-logo.svg
install -Dm0644 "$MERK/merk-inkt.svg" /usr/share/icons/hicolor/scalable/places/distributor-logo-symbolic.svg

# "Over dit systeem" (KDE Info-centrum): onze naam, versie, logo en website.
# Name en Version moeten er expliciet in: anders pakt KDE ze per regel uit
# Aurora's eigen bestand in kde-profile, en stond er "Aurora 44". Dat
# bestand halen we ook weg, zodat er niets van Aurora kan doorschemeren.
rm -f /usr/share/kde-settings/kde-profile/default/xdg/kcm-about-distrorc
cat >/etc/xdg/kcm-about-distrorc <<EOF
[General]
Name=BugOS
Version=${BUGOS_VERSION}
LogoPath=/usr/share/pixmaps/system-logo.png
Website=https://github.com/253UgurSahin/BugOS
Variant=
EOF

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
# Het inlogscherm. Fedora 44 gebruikt "Plasma Login Manager" (niet meer
# SDDM); bij Aurora stond daar de zeilboot met "SS AURORA". Nu: Stip.
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
