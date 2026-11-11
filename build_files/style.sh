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

# Zo min mogelijk KDE zien (een echt BugOS-gevoel). Kiosk-regels van KDE voor iedereen:
#  - geen "Over KDE", "Fout melden bij KDE", "Doneren" en "Taal van dit programma" in de Help-menu's;
#  - geen KRunner (Alt+spatie, Alt+F2): het BugOS-startmenu zoekt apps, bestanden en instellingen al.
for actie in help_about_kde help_report_bug help_donate switch_application_language run_command; do
    kwriteconfig6 --file /etc/xdg/kdeglobals --group "KDE Action Restrictions" --key "action/$actie" false
done
#  - geen "Configureren..." in de rechtermuismenu's van taakbalk, startknop en apps zolang ze op slot staan
#    (bugos-panel zet taakbalk en bureaublad op slot). Zonder slot doet deze regel niets. NOOIT de sleutel
#    plasma/plasmashell/unlockedDesktop gebruiken: dan weigert Plasma de scripts van bugos-panel.
kwriteconfig6 --file /etc/xdg/kdeglobals --group "KDE Action Restrictions" --key plasma/allow_configure_when_locked false
# Het rechtermuismenu van het bureaublad voor nieuwe gebruikers: zonder "Bewerkmodus", "Terminal openen",
# "Scherm vergrendelen", KDE's "Bureaublad en achtergrond" enz. (bestaande gebruikers: bugos-panel standaard).
# Plasma leest dit bestand niet uit /etc/xdg, dus via /etc/skel. Alleen groep 0 (bureaublad), NOOIT groep 1
# (paneel): dan verdwijnt het hele taakbalkmenu. De regel "RightButton;NoModifier=org.kde.contextmenu" moet erin,
# anders heeft het bureaublad helemaal geen menu.
mkdir -p /etc/skel/.config
cat >/etc/skel/.config/plasma-org.kde.plasma.desktop-appletsrc <<'EOF'
[ActionPlugins][0]
RightButton;NoModifier=org.kde.contextmenu

[ActionPlugins][0][RightButton;NoModifier]
_add panel=false
_display_settings=false
_lock_screen=false
_logout=false
_open_terminal=false
_run_command=false
_wallpaper=false
add widgets=false
configure=false
configure shortcuts=false
desktop edit mode=false
edit mode=false
manage activities=false
remove=false
EOF
# Geen Overzicht van KDE als je per ongeluk de muis linksboven in de hoek duwt (net als Windows: daar gebeurt niets).
kwriteconfig6 --file /etc/xdg/kwinrc --group Effect-overview --key BorderActivate 9
# KDE Connect (koppelen met je telefoon) start niet vanzelf: het gaf meldingen met "KDE Connect" die niemand vroeg.
# (Starten met de hand kan nog: kdeconnectd.)
if [ -f /etc/xdg/autostart/org.kde.kdeconnect.daemon.desktop ]; then
    printf '%s\n' '[Desktop Entry]' 'Hidden=true' >/etc/xdg/autostart/org.kde.kdeconnect.daemon.desktop
fi

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
# Ook hicolor: daar kwamen na de laatste dnf-stap het BugOS-logo en distributor-logo bij (U425).
gtk-update-icon-cache -f -t /usr/share/icons/hicolor || true

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

# >>> bureaubladmenu (getest door tools/test_native_shell.py)
# Het rechtermuismenu van het bureaublad: twee BugOS-regels erbij (Scherminstellingen, Achtergrond wijzigen) en
# Ctrl+Shift+D (opent KDE's "Bureaublad en achtergrond", ook als het bureaublad op slot staat) eraf. De mapweergave
# van KDE staat als QML op schijf. Breekt de bouw nooit (set -e): elke grep staat in een if of achter ||.
bureaubladmenu() {
    local ui="$1" bron="$2"
    local laag="$ui/FolderViewLayer.qml" hoofd="$ui/main.qml"
    # 1. Ctrl+Shift+D eraf, los van stap 2: ook als FolderViewLayer.qml in een nieuwe KDE-versie anders is.
    if [ -f "$hoofd" ]; then
        sed -i '/^[[:space:]]*shortcut: *"Ctrl+Shift+D"[[:space:]]*$/d' "$hoofd"
        if grep -q 'Ctrl+Shift+D' "$hoofd"; then
            echo "LET OP: bureaubladmenu: Ctrl+Shift+D staat nog in main.qml (nieuwe KDE-versie?); dat opent KDE's achtergrondvenster."
        fi
    else
        echo "LET OP: bureaubladmenu: $hoofd ontbreekt (nieuwe KDE-versie?)."
    fi
    # 2. De BugOS-regels: één regel achter het scheidingsstreepje dat KDE na zijn eigen regels zet.
    if [ ! -f "$laag" ] || ! grep -q '^ *Plasmoid\.contextualActions\.push(actionSeparator);$' "$laag"; then
        echo "LET OP: bureaubladmenu: FolderViewLayer.qml is anders dan verwacht (nieuwe KDE-versie?); geen BugOS-regels in het bureaubladmenu."
        return 0
    fi
    install -m0644 "$bron" "$ui/BugosBureaubladActies.qml"
    if ! grep -q 'BugosBureaubladActies.qml' "$laag"; then
        # Plasmoid.isContainment: niet in een losse "Mapweergave" die iemand op een paneel zet.
        sed -i 's|^\( *\)Plasmoid\.contextualActions\.push(actionSeparator);$|&\n\1if (Plasmoid.isContainment) { const bugosC = Qt.createComponent("BugosBureaubladActies.qml"); const bugosO = bugosC.status === Component.Ready ? bugosC.createObject(folderViewLayerComponent) : null; if (bugosO) { for (const a of bugosO.acties) Plasmoid.contextualActions.push(a); } else { console.warn("BugOS bureaubladmenu:", bugosC.errorString()); } } // BugOS|' "$laag"
    fi
    grep -q 'BugosBureaubladActies.qml' "$laag" || echo "LET OP: bureaubladmenu: invoegen in FolderViewLayer.qml lukte niet."
    return 0
}
# <<< bureaubladmenu
bureaubladmenu /usr/share/plasma/plasmoids/org.kde.desktopcontainment/contents/ui \
    /usr/share/plasma/plasmoids/org.bugos.taskbar/contents/ui/BureaubladActies.qml

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
hernoem org.kde.dolphin.desktop "Dolphin (voor gevorderden)" "Dolphin (advanced)"
hernoem systemsettings.desktop "Alle instellingen" "All settings"
hernoem org.kde.partitionmanager.desktop "Schijfbeheer (voor gevorderden)" "Disk management (advanced)"
hernoem org.kde.plasma-systemmonitor.desktop "Systeemmonitor (voor gevorderden)" "System Monitor (advanced)"
hernoem org.kde.konsole.desktop "Terminal" "Terminal"
# Windows+E en Windows+I openen BugOS Bestanden en Instellingen (zoals in Windows), niet Dolphin en de
# KDE-instellingen: hun eigen sneltoetsen eraf (U322).
sed -i 's/^X-KDE-Shortcuts=Meta+E$//' /usr/share/applications/org.kde.dolphin.desktop
sed -i 's/^X-KDE-Shortcuts=Tools,Meta+I$/X-KDE-Shortcuts=Tools/; s/^X-KDE-Shortcuts=Meta+I$//' /usr/share/applications/systemsettings.desktop
# KDE leest de standaard-sneltoets (X-KDE-Shortcuts) van een app alleen uit /usr/share/kglobalaccel/. Zonder die
# koppeling deden Ctrl+Shift+Esc (Taakbeheer), Windows+E (Bestanden) en Windows+I (Instellingen) niets.
mkdir -p /usr/share/kglobalaccel
for app in bugos-task-manager bugos-files bugos-settings; do
    ln -sf "../applications/$app.desktop" "/usr/share/kglobalaccel/$app.desktop"
done

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
# Een echt BugOS-gevoel: de KDE-programma's waar BugOS een eigen app (of knop) voor heeft, staan niet in het
# startmenu. Ze blijven geïnstalleerd en werken gewoon, maar BugOS opent er nog maar één zelf: KDE Instellingen
# ("Geavanceerde instellingen" onder Over deze computer). Bestanden laat zelf zien wat de meeste ruimte inneemt
# (dus geen Filelight) en opent geen Dolphin of Schijfbeheer meer. (Discover zit niet meer in het beeld: de Winkel.)
for app in org.kde.dolphin.desktop systemsettings.desktop org.kde.filelight.desktop \
    org.kde.partitionmanager.desktop org.kde.plasma-systemmonitor.desktop org.kde.kinfocenter.desktop \
    org.kde.kwalletmanager.desktop org.kde.kwalletmanager5.desktop org.kde.kmenuedit.desktop \
    org.kde.kdeconnect.app.desktop org.kde.kdeconnect.sms.desktop org.kde.kdeconnect_open.desktop \
    org.kde.kdeconnect-settings.desktop org.kde.kdeconnect.nonplasma.desktop org.kde.plasma.emojier.desktop \
    winetricks.desktop org.kde.kwrite.desktop org.kde.khelpcenter.desktop org.kde.plasma-welcome.desktop \
    org.freedesktop.MalcontentControl.desktop; do
    verberg "$app"
done
# Gezien in "Alle apps" op een verse installatie (2026-11-10): hulpjes die met een ander pakket meekomen en waar
# Bugie niets mee kan. Ze werken gewoon, maar staan niet in het startmenu: de DOS-emulator van Wine, de firewall
# (staat goed; instellen kan via de geavanceerde instellingen), KDE's zoekvenster (Bestanden zoekt zelf), scherm
# delen via VNC, en het hulpprogramma van de vensterstijl.
for app in org.dosbox-staging.dosbox-staging.desktop firewall-config.desktop org.kde.kfind.desktop     org.kde.krfb.desktop org.kde.krfb.virtualmonitor.desktop kvantummanager.desktop; do
    verberg "$app"
done
hernoem org.kde.spectacle.desktop "Schermafbeelding" "Screenshot"
hernoem org.kde.kate.desktop "Teksteditor" "Text editor"
hernoem org.kde.kcharselect.desktop "Speciale tekens" "Special characters"

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
