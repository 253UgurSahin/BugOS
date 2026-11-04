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
# Lukt dat niet, dan zet bugos-eerste-start.service Steam later als Flatpak neer.
dnf5 install -y --skip-unavailable steam || true

# 3. BugOS is een eigen systeem, net als Bazzite.
#    De fundering is kaal Fedora Kinoite van Universal Blue (zie Containerfile);
#    alles wat daar "Fedora" of "Kinoite" heet, wordt hier BugOS. Ook de ID:
#    ID=bugos, met ID_LIKE=fedora zodat programma's weten dat BugOS op Fedora
#    lijkt (dnf, fwupd en het installatieprogramma kijken daarnaar).
#    VERSION_ID (bijv. 44) blijft het Fedora-nummer: dnf en Flatpak hebben dat nodig.

# Bij Fedora is /usr/lib/os-release een verwijzing naar een bestand van het
# pakket fedora-release. Eerst een echt eigen bestand maken, anders passen we
# straks het bestand van Fedora aan in plaats van dat van BugOS.
if [ -L /usr/lib/os-release ]; then
    cp --remove-destination "$(readlink -f /usr/lib/os-release)" /usr/lib/os-release
fi

if [ "$BUGOS_VARIANT" = nvidia ]; then
    BEELD_ID=bugos-nvidia
else
    BEELD_ID=bugos
fi

# os_zet SLEUTEL WAARDE: zet een regel in os-release (vervangen of erbij).
os_zet() {
    if grep -q "^$1=" /usr/lib/os-release; then
        sed -i "s|^$1=.*|$1=$2|" /usr/lib/os-release
    else
        echo "$1=$2" >>/usr/lib/os-release
    fi
}
# De velden die programma's laten zien ("Over dit systeem", hostnamectl,
# fastfetch, lsb_release) en de namen waarop andere programma's het systeem
# herkennen.
os_zet NAME '"BugOS"'
os_zet ID bugos
os_zet ID_LIKE '"fedora"'
os_zet PRETTY_NAME "\"BugOS ${BUGOS_VERSION}\""
os_zet VERSION "\"${BUGOS_VERSION}\""
os_zet VARIANT '"BugOS"'
os_zet VARIANT_ID "${BEELD_ID}"
os_zet VERSION_CODENAME '""'
os_zet CPE_NAME "\"cpe:/o:bugos:bugos:${BUGOS_VERSION}\""
os_zet HOME_URL '"https://github.com/253UgurSahin/BugOS"'
os_zet DOCUMENTATION_URL '"https://github.com/253UgurSahin/BugOS/tree/main/docs"'
os_zet SUPPORT_URL '"https://github.com/253UgurSahin/BugOS/issues"'
os_zet BUG_REPORT_URL '"https://github.com/253UgurSahin/BugOS/issues"'
os_zet LOGO bugos-logo
os_zet DEFAULT_HOSTNAME '"bugos"'
os_zet IMAGE_ID "\"${BEELD_ID}\""
os_zet IMAGE_VERSION "\"${BUGOS_VERSION}\""
os_zet OSTREE_VERSION "'${BUGOS_VERSION}'"
os_zet BUILD_ID "\"${BUGOS_VERSION}\""
os_zet ANSI_COLOR '"0;38;2;222;47;62"'
os_zet BUGOS_VARIANT "\"${BUGOS_VARIANT}\""
# Fedora's einddatum en Red Hat-meldplekken horen niet bij BugOS. (PLATFORM_ID
# blijft: dnf heeft die nodig.)
sed -i -e '/^SUPPORT_END=/d' -e '/^REDHAT_/d' /usr/lib/os-release
cat /usr/lib/os-release

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

# 3b. Wat de gebruiker verder nog als Fedora, Kinoite of Universal Blue zou
#     zien, wordt BugOS.

# /etc/system-release was een verwijzing naar "Fedora release 44". Het
# opstartprogramma (bootupd) noemt de opstartkeuze in het BIOS/UEFI-menu
# daarnaar, dus daar stond "Fedora". Nu een eigen bestand: "BugOS release 44".
# (/etc/fedora-release blijft Fedora, voor programma's die dat nodig hebben.)
rm -f /etc/system-release
printf 'BugOS release %s\n' "$(. /usr/lib/os-release && echo "${VERSION_ID}")" >/etc/system-release

# De "eerste keer opstarten"-assistent van KDE (plasma-setup) maakt zelf een
# gebruiker en zet het thema van Fedora neer. Bij BugOS maakt het
# installatieprogramma de gebruiker al, en BugOS Welkom doet de rest.
# Dit bestand betekent voor plasma-setup: "al gedaan".
touch /etc/plasma-setup-done

# Het "Welcome Center" van KDE (met "Welcome to Fedora" en het Fedora-logo)
# verschijnt bij de eerste keer inloggen. BugOS heeft een eigen welkomstapp
# (bugos-welkom), dus deze gaat er helemaal uit. Geen ander pakket heeft hem
# nodig (alleen plasma-workspace "raadt hem aan").
# rpm -e in plaats van dnf remove: dan gaan er niet stilletjes andere
# pakketten mee die toevallig alleen hierdoor waren binnengekomen.
if rpm -q plasma-welcome >/dev/null 2>&1; then
    rpm -e plasma-welcome
fi
rm -rf /usr/share/plasma/plasma-welcome

# fastfetch kiest zijn logo op ID; bugos kent hij niet. Dus geven we hem zelf
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
# Daar stond kinoite-main; dan zou bijvoorbeeld "ujust rebase-helper" de
# computer naar kaal Kinoite kunnen omzetten.
mkdir -p /usr/share/ublue-os
cat >/usr/share/ublue-os/image-info.json <<EOF
{
  "image-name": "${BEELD_ID}",
  "image-flavor": "${BUGOS_VARIANT}",
  "image-vendor": "253ugursahin",
  "image-ref": "ostree-unverified-registry:ghcr.io/253ugursahin/${BEELD_ID}",
  "image-tag": "latest",
  "base-image-name": "kinoite",
  "fedora-version": "$(. /usr/lib/os-release && echo "${VERSION_ID}")"
}
EOF

# Universal Blue's eigen update-dienst (uupd) en Fedora's rpm-ostree-
# updatemeldingen: BugOS regelt updates zelf (stap 6). Twee dingen die
# tegelijk updaten, zitten elkaar in de weg.
for eenheid in uupd.timer ublue-update.timer; do
    if [ -e "/usr/lib/systemd/system/$eenheid" ]; then
        systemctl mask "$eenheid"
    fi
done

# De zoekbalk (KRunner): Fedora zet hier zijn eigen keuzes neer. Zonder dat
# bestand gelden de gewone KDE-instellingen.
rm -f /usr/share/kde-settings/kde-profile/default/xdg/krunnerrc

# Firefox: begint niet meer op de Fedora-startpagina, en heet "for BugOS".
FF=/usr/lib64/firefox
if [ -d "$FF" ]; then
    sed -i -e 's|https://start.fedoraproject.org/|about:home|' -e '/browser.newtabpage.pinned/d' \
        "$FF/browser/defaults/preferences/firefox-redhat-default-prefs.js" || true
    mkdir -p "$FF/distribution"
    cat >"$FF/distribution/distribution.ini" <<'EOF'
[Global]
id=bugos
version=1.0
about=Mozilla Firefox for BugOS

[Preferences]
app.distributor="bugos"
app.distributor.channel="bugos"
EOF
fi

# Logo's: veel programma's gebruiken vaste bestandsnamen voor "het logo van
# dit systeem" (Over dit systeem, het installatieprogramma, sommige menu's).
# Daar staat het Fedora-logo. Wij leggen er het lieveheersbeestje neer.
MERK=/usr/share/bugos/merk
for png in system-logo.png fedora-logo-sprite.png fedora-logo.png fedora_logo_med.png fedora-logo-small.png; do
    install -Dm0644 "$MERK/merk-256.png" "/usr/share/pixmaps/$png"
done
# De "witte" versie is voor donkere achtergronden: het beestje met lichte kop.
install -Dm0644 "$MERK/merk-donker-256.png" /usr/share/pixmaps/system-logo-white.png
# fedora-logo.svg en fedora_whitelogo.svg zijn (verwijzingen naar) het Fedora-logo.
rm -f /usr/share/pixmaps/fedora-logo.svg /usr/share/pixmaps/fedora_whitelogo.svg
install -Dm0644 "$MERK/logo.svg" /usr/share/pixmaps/fedora-logo.svg
install -Dm0644 "$MERK/logo-wit.svg" /usr/share/pixmaps/fedora_whitelogo.svg
# Het algemene "logo van de distributie" (ook voor het pictogram start-here).
install -Dm0644 "$MERK/merk.svg" /usr/share/icons/hicolor/scalable/distributor-logo.svg
install -Dm0644 "$MERK/merk-inkt.svg" /usr/share/icons/hicolor/scalable/places/distributor-logo-symbolic.svg

# "Over dit systeem" (KDE Info-centrum): onze naam, versie, logo en website.
# Name en Version moeten er expliciet in: anders pakt KDE ze per regel uit
# Fedora's eigen bestand in kde-profile, en staat er "Fedora 44". Dat
# bestand halen we ook weg, zodat er niets van Fedora kan doorschemeren.
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

# Eén ontwerptaal voor het hele systeem (zie tools/ontwerp/README.md). De eigen
# BugOS-apps tekenen zichzelf; al het andere krijgt dezelfde stijl van:
#  - KDE-programma's (ook KDE Instellingen, Dolphin, Schijfbeheer): de
#    programmastijl Kvantum "BugOS" (licht) of "BugOSDonker" (donker);
#  - pictogrammen: het thema "BugOS" (de rest komt van Breeze);
#  - taakbalk, pop-ups en tooltips: de Plasma-stijl "bugos".
# Licht/donker omzetten doet bugos-thema; die zet ook Kvantum om.
kwriteconfig6 --file /etc/xdg/kdeglobals --group KDE --key widgetStyle kvantum
kwriteconfig6 --file /etc/xdg/kdeglobals --group Icons --key Theme BugOS
kwriteconfig6 --file /etc/xdg/plasmarc --group Theme --key name bugos
# Kvantum leest zijn keuze uit ~/.config/Kvantum: nieuwe gebruikers krijgen hem
# via /etc/skel, bestaande via "bugos-thema eerste-keer" bij het inloggen.
for kv in /etc/skel/.config/Kvantum /etc/xdg/Kvantum; do
    mkdir -p "$kv"
    printf '[General]\ntheme=BugOS\n' >"$kv/kvantum.kvconfig"
done
# GTK-programma's (zoals Firefox) zoeken pictogrammen via deze index.
gtk-update-icon-cache -f -t /usr/share/icons/BugOS || true

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

# 5. Bestandstypes koppelen: .exe -> bugos-exe, .rpm/.deb -> bugos-pakket.
update-desktop-database /usr/share/applications || true

# 6. Diensten aanzetten.
systemctl enable bugos-eerste-start.service
# Updates: BugOS regelt dit zelf (geen uupd van Universal Blue).
#  - het systeem: rpm-ostree haalt de nieuwe BugOS op de achtergrond op en zet
#    hem klaar ("stage"); hij wordt actief bij de volgende keer opstarten.
#  - de apps (Flatpak): bugos-apps-bijwerken.timer, elke dag.
#  bugos-updates auto|hand zet ze allebei aan of uit.
if grep -q '^#\?AutomaticUpdatePolicy=' /etc/rpm-ostreed.conf 2>/dev/null; then
    sed -i 's|^#\?AutomaticUpdatePolicy=.*|AutomaticUpdatePolicy=stage|' /etc/rpm-ostreed.conf
else
    printf '[Daemon]\nAutomaticUpdatePolicy=stage\n' >>/etc/rpm-ostreed.conf
fi
systemctl enable rpm-ostreed-automatic.timer bugos-apps-bijwerken.timer
systemctl enable podman.socket || true
# Elke gebruiker: dagelijks kijken of er een update is (doet alleen iets bij "zelf updaten").
systemctl --global enable bugos-updatecheck.timer

# 7. Standaard: updates automatisch (de gebruiker kan dit omzetten).
mkdir -p /etc/bugos
echo "UPDATES=auto" >/etc/bugos/updates.conf

# Opruimen zodat er geen extra softwarebronnen aan blijven staan.
dnf5 clean all
rm -rf /var/lib/dnf /run/dnf
