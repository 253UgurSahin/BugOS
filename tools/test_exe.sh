#!/usr/bin/bash
# shellcheck disable=SC2016,SC2034  # de $ in de nep-programma's en controles is bedoeld (wordt later uitgevoerd)
# Test van bugos-exe: een rare bestandsnaam staat goed in de melding, en een mislukte Wine-start
# laat geen halve Windows-map achter. Met nep-programma's (wine, kdialog): er wordt niets geïnstalleerd.
#
# Gebruik:  bash tools/test_exe.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/thuis"
fouten=0
klopt() { if eval "$1"; then echo "OK    $2"; else echo "FOUT  $2"; fouten=$((fouten + 1)); fi; }
nep() { printf '#!/usr/bin/bash\n%s\n' "$2" >"$TMP/bin/$1"; chmod +x "$TMP/bin/$1"; }

sed "s|/usr/share/bugos|$ROOT/system_files/usr/share/bugos|g" "$ROOT/system_files/usr/bin/bugos-exe" >"$TMP/exe"
nep kdialog 'printf "%s\n" "$@" >>"'"$TMP"'/dialogen"'
nep notify-send 'exit 0'
nep bugos-theme 'echo licht'
nep wine 'exit 1'                                   # het programma stopt meteen met een fout
nep wineboot 'mkdir -p "$WINEPREFIX/half"; exit 1'  # klaarzetten mislukt halverwege
nep winepath 'echo "$2"'
nep wineserver 'exit 0'                             # de Wine-achtergronddienst: niets om op te wachten
draai() { HOME="$TMP/thuis" PATH="$TMP/bin:$PATH" LANG=nl_NL.UTF-8 bash "$TMP/exe" "$1" >/dev/null 2>&1; echo $?; }

RAAR="$TMP/spel\\nieuw.exe"   # een echte backslash in de naam
touch "$RAAR"
code="$(draai "$RAAR")"
klopt '[ "$code" = 1 ] && [ ! -e "$TMP/thuis/.local/share/bugos/windows" ]' \
    "Wine klaarzetten mislukt: duidelijke melding, geen halve Windows-map"
klopt 'grep -q "Klaarzetten voor Windows" "$TMP/dialogen"' "Wine klaarzetten mislukt: de melding zegt wat er is"

nep wineboot 'mkdir -p "$WINEPREFIX"; exit 0'
: >"$TMP/dialogen"
draai "$RAAR" >/dev/null
klopt 'grep -qF "spel\\nieuw.exe" "$TMP/dialogen"' "rare naam (met \\n erin): staat precies zo in de melding, geen nieuwe regel"

# U251: een naam met opmaak (<b>, <img>) wordt niet als opmaak gelezen.
OPMAAK="$TMP/<h1>Gratis.exe"
touch "$OPMAAK"
: >"$TMP/dialogen"
draai "$OPMAAK" >/dev/null
klopt '! grep -q "<h1>" "$TMP/dialogen" && grep -q "‹h1›Gratis.exe" "$TMP/dialogen"' "U251: een naam met <opmaak> staat er als gewone tekst"

# U082: Annuleren in een installatie is geen "werkt niet op BugOS".
touch "$TMP/setup.msi" "$TMP/MijnSpel-setup.exe" "$TMP/spel.exe"
nep wine 'exit 1602'
: >"$TMP/dialogen"
code="$(draai "$TMP/setup.msi")"
klopt '[ "$code" = 0 ] && ! grep -q "werkt niet" "$TMP/dialogen"' "U082: msiexec Annuleren (1602): geen foutmelding"
nep wine 'exit 2'
: >"$TMP/dialogen"
draai "$TMP/MijnSpel-setup.exe" >/dev/null
klopt 'grep -q "Annuleren" "$TMP/dialogen" && ! grep -q "werkt niet op BugOS" "$TMP/dialogen"' \
    "U082: installatie stopt meteen met 2: vraagt of je op Annuleren klikte"
: >"$TMP/dialogen"
draai "$TMP/spel.exe" >/dev/null
klopt 'grep -q "werkt niet op BugOS" "$TMP/dialogen"' "U082: een gewoon programma dat meteen stopt: zoals eerst"

# U190: 'ChatGPTSetup.exe' is geen Telegram; 'tsetup-x64.5.1.exe' wel.
sed -n '/^zoek_alternatief()/,/^}/p' "$ROOT/system_files/usr/bin/bugos-exe" >"$TMP/zoek.sh"
zoek() { NAAM="$1" ALTERNATIEVEN="$ROOT/system_files/usr/share/bugos/alternatives.txt" bash -c '. "$1"; zoek_alternatief' _ "$TMP/zoek.sh"; }
klopt '[ "$(zoek tsetup-x64.5.1.exe)" = "Telegram|org.telegram.desktop" ] && [ -z "$(zoek ChatGPTSetup.exe)" ] && [ -z "$(zoek MinecraftSetup.exe)" ]' \
    "U190: Telegram herkennen aan het begin van de naam, niet in ChatGPTSetup of MinecraftSetup"

# D-04: veelgebruikte Windows-installaties krijgen ook een BugOS-versie aangeboden (op de echte bestandsnamen).
klopt '[ "$(zoek npp.8.7.1.Installer.x64.exe)" = "KWrite (Teksteditor)|org.kde.kwrite|KWrite (Text editor)" ] && [ "$(zoek Audacity-3.7.1-64bit.exe)" = "Audacity|org.audacityteam.Audacity" ] && [ "$(zoek paint.net.5.1.2.install.x64.exe)" = "Pinta|com.github.PintaProject.Pinta" ] && [ "$(zoek 7z2408-x64.exe)" = "Ark|org.kde.ark" ] && [ "$(zoek OBS-Studio-31.0.0-Windows-Installer.exe)" = "OBS Studio|com.obsproject.Studio" ] && [ "$(zoek LibreOffice_25.2.0_Win_x86-64.msi)" = "LibreOffice|org.libreoffice.LibreOffice" ]' \
    "D-04: Notepad++, Audacity, Paint.NET, 7-Zip, OBS en LibreOffice: eerst de BugOS-versie aangeboden"
klopt '[ -z "$(zoek happynpp.exe)" ] && [ -z "$(zoek spel.exe)" ]' "D-04: 'npp.' alleen aan het begin van de naam (niet in happynpp.exe)"

# D-04: staat de BugOS-versie al op de computer (KWrite voor Notepad++), dan meteen die openen, niet de Winkel.
mkdir -p "$TMP/thuis/.local/share/applications"
printf '[Desktop Entry]\nType=Application\nName=KWrite\nExec=kwrite %%U\n' >"$TMP/thuis/.local/share/applications/org.kde.kwrite.desktop"
nep gio 'echo "$*" >"'"$TMP"'/gio"'
nep bugos-store 'echo "$*" >"'"$TMP"'/winkel"'
nep wine 'echo gestart >"'"$TMP"'/wine-gestart"; exit 0'
touch "$TMP/npp.8.7.1.Installer.x64.exe"
: >"$TMP/dialogen"
rm -f "$TMP/gio" "$TMP/winkel" "$TMP/wine-gestart"
XDG_DATA_HOME="$TMP/thuis/.local/share" draai "$TMP/npp.8.7.1.Installer.x64.exe" >/dev/null
klopt 'grep -q "BugOS heeft al KWrite" "$TMP/dialogen" && grep -q "launch .*org.kde.kwrite.desktop" "$TMP/gio" 2>/dev/null && [ ! -e "$TMP/winkel" ] && [ ! -e "$TMP/wine-gestart" ]' \
    "D-04: Notepad++ met KWrite al op de computer: KWrite openen aangeboden (niet de Winkel, niet Wine)"
# VM-test 2026-11-23: in het Engels stond er "BugOS already has KWrite (Teksteditor)". Nu de Engelse naam uit het
# vierde veld van alternatives.txt, en in het Nederlands nog steeds de Nederlandse.
: >"$TMP/dialogen"
XDG_DATA_HOME="$TMP/thuis/.local/share" HOME="$TMP/thuis" PATH="$TMP/bin:$PATH" LANG=en_US.UTF-8 \
    bash "$TMP/exe" "$TMP/npp.8.7.1.Installer.x64.exe" >/dev/null 2>&1
klopt 'grep -q "BugOS already has KWrite (Text editor)" "$TMP/dialogen" && ! grep -q "Teksteditor" "$TMP/dialogen"' \
    "Notepad++ in het Engels: 'KWrite (Text editor)', geen Nederlands woord in de Engelse vraag"
klopt '[ "$(zoek Audacity-3.7.1-64bit.exe)" = "Audacity|org.audacityteam.Audacity" ]' \
    "Een regel zonder Engelse naam geeft nog steeds 'naam|id' (geen lege derde kolom)"
rm -f "$TMP/thuis/.local/share/applications/org.kde.kwrite.desktop"

# D-02: Wine maakt alleen de laatste map (zoals de echte wineboot: mkdir zonder -p). Op een nieuwe computer bestaat
# ~/.local/share/bugos nog niet: bugos-exe moet die zelf maken, anders mislukt het klaarzetten altijd.
# D-05: het klaarzetten gebeurt zonder scherm (geen Wine-vensters), het programma zelf daarna wel met scherm.
nep wineboot 'echo "DISPLAY=${DISPLAY-weg} WAYLAND=${WAYLAND_DISPLAY-weg}" >>"'"$TMP"'/wineboot"; mkdir "$WINEPREFIX" || exit 1'
nep wineserver 'exit 0'
nep wine 'echo "DISPLAY=${DISPLAY-weg}" >"'"$TMP"'/wine-gestart"; exit 0'
rm -rf "$TMP/thuis/.local" "$TMP/wineboot" "$TMP/wine-gestart"
: >"$TMP/dialogen"
code="$(DISPLAY=:0 WAYLAND_DISPLAY=wayland-0 draai "$TMP/spel.exe")"
klopt '[ "$code" = 0 ] && [ -d "$TMP/thuis/.local/share/bugos/windows" ] && ! grep -q "lukte niet" "$TMP/dialogen"' \
    "D-02: eerste keer op een nieuwe computer (zonder ~/.local/share/bugos): het klaarzetten lukt ($code)"
klopt '[ "$(cat "$TMP/wineboot" 2>/dev/null)" = "DISPLAY=weg WAYLAND=weg" ] && grep -q "DISPLAY=:0" "$TMP/wine-gestart" 2>/dev/null' \
    "D-05: Windows klaarzetten zonder Wine-vensters, het programma daarna gewoon in beeld ($(cat "$TMP/wineboot" 2>/dev/null))"

# VM-test 2026-11-23: de eerste keer klaarzetten duurde ruim 3 minuten, maar de melding ("een minuutje") verdween na
# een paar seconden. Nu blijft hij staan (--expire-time=0) en wordt hij aan het eind vervangen (zelfde nummer), zodat
# er geen 'Even geduld' blijft hangen. Een nep-notify-send schrijft zijn argumenten op en geeft nummer 42 terug.
nep notify-send 'echo "$*" >>"'"$TMP"'/meldingen"; echo 42'
rm -rf "$TMP/thuis/.local" "$TMP/meldingen"
draai "$TMP/spel.exe" >/dev/null
klopt 'head -1 "$TMP/meldingen" | grep -q -- "--expire-time=0" && head -1 "$TMP/meldingen" | grep -q "paar minuten" && ! grep -q "minuutje" "$TMP/meldingen"' \
    "Eerste keer Windows klaarzetten: de melding blijft staan en zegt eerlijk 'een paar minuten'"
klopt 'tail -1 "$TMP/meldingen" | grep -q -- "--replace-id=42" && tail -1 "$TMP/meldingen" | grep -q "Klaar"' \
    "Eerste keer Windows klaarzetten: aan het eind wordt dezelfde melding vervangen door 'Klaar'"
nep notify-send 'exit 0'

# Een half klaargezette Windows-map (zonder kernel32.dll, van een eerste keer die halverwege stopte) wordt opzij gezet
# en opnieuw gemaakt; een complete map blijft gewoon staan (VM-test 2026-11-16: "could not load kernel32.dll").
nep wineboot 'mkdir -p "$WINEPREFIX/drive_c/windows/system32" "$WINEPREFIX/drive_c/windows/syswow64" && touch "$WINEPREFIX/drive_c/windows/system32/kernel32.dll" "$WINEPREFIX/drive_c/windows/syswow64/kernel32.dll" "$WINEPREFIX/system.reg"'
rm -rf "$TMP/thuis/.local"
mkdir -p "$TMP/thuis/.local/share/bugos/windows/drive_c/windows/system32" "$TMP/thuis/.local/share/bugos/windows/drive_c/windows/syswow64"
# half, zoals in de VM: de 64-bits helft en system.reg wel, de 32-bits helft (syswow64) leeg
touch "$TMP/thuis/.local/share/bugos/windows/drive_c/windows/system32/kernel32.dll" "$TMP/thuis/.local/share/bugos/windows/system.reg"
touch "$TMP/thuis/.local/share/bugos/windows/mijn-spul"
code="$(draai "$TMP/spel.exe")"
klopt '[ "$code" = 0 ] && [ -f "$TMP/thuis/.local/share/bugos/windows/drive_c/windows/system32/kernel32.dll" ] && ls -d "$TMP"/thuis/.local/share/bugos/windows-onaf-* >/dev/null 2>&1 && [ -f "$(ls -d "$TMP"/thuis/.local/share/bugos/windows-onaf-* | head -1)/mijn-spul" ]' \
    "Windows-map half af: opzij gezet (niets weggegooid) en opnieuw klaargezet ($code)"
nep wineboot 'echo opnieuw >>"'"$TMP"'/wineboot-twee"; exit 0'
rm -f "$TMP/wineboot-twee"
draai "$TMP/spel.exe" >/dev/null
klopt '[ ! -e "$TMP/wineboot-twee" ] && [ "$(ls -d "$TMP"/thuis/.local/share/bugos/windows-onaf-* | wc -l)" = 1 ]' \
    "Windows-map compleet: blijft staan, niet opnieuw klaarzetten"

# D-02: mislukt het klaarzetten, dan alleen "vol" zeggen als de schijf echt (bijna) vol is.
nep wineboot 'exit 1'
nep df 'echo "Filesystem 1024-blocks Used Available Capacity Mounted on"; echo "/dev/sda3 100000000 20000000 80000000 20% /var"'
rm -rf "$TMP/thuis/.local"
: >"$TMP/dialogen"
draai "$TMP/spel.exe" >/dev/null
klopt 'grep -q "Klaarzetten voor Windows" "$TMP/dialogen" && ! grep -qi "vol\b\|full" "$TMP/dialogen"' \
    "D-02: klaarzetten mislukt met genoeg ruimte: niet 'is je computer vol?'"
nep df 'echo "Filesystem 1024-blocks Used Available Capacity Mounted on"; echo "/dev/sda3 100000000 99800000 200000 100% /var"'
: >"$TMP/dialogen"
draai "$TMP/spel.exe" >/dev/null
klopt 'grep -q "je computer is vol" "$TMP/dialogen"' "D-02: klaarzetten mislukt met een volle schijf: dat wordt gezegd"
rm -f "$TMP/bin/df"

# D-03: de bouw geeft de 32-bits Windows-dll's van wine-wow64 het SELinux-label waarmee Wine ze mag aanpassen.
BOUW="$ROOT/build_files/build.sh"
klopt 'grep -qF "fcontext -a -t textrel_shlib_t" "$BOUW" && grep -qF "/usr/lib/wine-wow64/.+-windows/" "$BOUW" && grep -qF "matchpathcon" "$BOUW"' \
    "D-03: build.sh zet textrel_shlib_t op /usr/lib64/wine-wow64 (en stopt de bouw als het niet klopt)"

echo "$fouten fout(en)."
[ "$fouten" -eq 0 ]
