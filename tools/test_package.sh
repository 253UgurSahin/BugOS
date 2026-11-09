#!/usr/bin/bash
# Test van bugos-package: een .rpm met een rare naam installeren mag nooit iets anders uitvoeren.
# Met nep-programma's (distrobox, dnf, kdialog...): er wordt niets echt geïnstalleerd.
#
# Gebruik:  bash tools/test_package.sh
set -u
# shellcheck disable=SC2016  # de $ in de nep-programma's en controles is bedoeld (wordt later uitgevoerd)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/lib"
fouten=0
klopt() { if eval "$1"; then echo "OK    $2"; else echo "FOUT  $2"; fouten=$((fouten + 1)); fi; }

# lib.sh van deze repo, niet die van het systeem.
sed "s|/usr/share/bugos|$ROOT/system_files/usr/share/bugos|g" "$ROOT/system_files/usr/bin/bugos-package" >"$TMP/bugos-package"
nep() { printf '#!/usr/bin/bash\n%s\n' "$2" >"$TMP/bin/$1"; chmod +x "$TMP/bin/$1"; }
nep kdialog 'exit 0'
nep notify-send 'exit 0'
nep flatpak 'exit 0'
nep rpm '[ "$1" = -qp ] && echo voorbeeld; exit 0'
nep sudo 'exec "$@"'
nep dnf 'printf "%s\n" "$@" >"$NEP_UIT"'
nep distrobox 'case "$1" in list) echo " bugos-fedora ";; enter) shift; while [ "$1" != -- ]; do shift; done; shift; exec "$@";; esac'

cd "$TMP" || exit 1
installeer() { rm -f "$TMP/dnf-args"; touch "$1"; PATH="$TMP/bin:$PATH" NEP_UIT="$TMP/dnf-args" bash "$TMP/bugos-package" "$1"; }

RAAR="$TMP/app\$(touch gehackt)\`touch gehackt2\`.rpm"
installeer "$RAAR"
klopt '[ ! -e "$TMP/gehackt" ] && [ ! -e "$TMP/gehackt2" ]' "naam met \$(…) en \`…\`: er wordt niets uitgevoerd"
klopt 'grep -qxF -- "$RAAR" "$TMP/dnf-args" 2>/dev/null' "naam met \$(…) en \`…\`: dnf krijgt precies het bestand"

RAAR2="$TMP/app \"2\" \$HOME.rpm"
installeer "$RAAR2"
klopt 'grep -qxF -- "$RAAR2" "$TMP/dnf-args" 2>/dev/null' "naam met spaties, \" en \$: dnf krijgt precies het bestand"

# U057: in het Nederlands zegt flatpak "Geen overeenkomsten gevonden": dat is geen app, dus niet "staat in de Winkel".
nep flatpak 'if [ "$1" = search ]; then if [ "${LC_ALL:-}" = C ]; then echo "No matches found"; else echo "Geen overeenkomsten gevonden"; fi; fi; exit 0'
nep kdialog 'echo "$*" >>"'"$TMP"'/gevraagd"; exit 0'
nep bugos-store 'echo "$*" >"'"$TMP"'/winkel"; exit 0'
rm -f "$TMP/gevraagd" "$TMP/winkel"
LANG=nl_NL.UTF-8 installeer "$TMP/eigen-app.rpm"
klopt '! grep -qi "winkel\|store" "$TMP/gevraagd" 2>/dev/null && [ ! -f "$TMP/winkel" ]' \
    "U057: geen app in de Winkel (Nederlandse flatpak): niet vragen of het 'ook in de Winkel' staat"
nep flatpak 'if [ "$1" = search ]; then echo "org.voorbeeld.App"; fi; exit 0'
rm -f "$TMP/gevraagd" "$TMP/winkel"
installeer "$TMP/voorbeeld.rpm"
klopt 'grep -q "appstream://org.voorbeeld.App" "$TMP/winkel" 2>/dev/null' "U057: staat het wel in de Winkel, dan gaat het daarheen"

# U195: een pakket zonder programma met een venster: niet 'staat in je startmenu' zeggen.
nep flatpak 'exit 0'
nep notify-send 'echo "$*" >>"'"$TMP"'/meldingen"'
rm -f "$TMP/meldingen"
installeer "$TMP/alleen-terminal.rpm"
klopt 'grep -q "Terminal" "$TMP/meldingen" 2>/dev/null && ! grep -q "staat nu in je startmenu\|is now in your start menu" "$TMP/meldingen"' \
    "U195: zonder plek in het startmenu: zeggen dat je het in de Terminal gebruikt"
# U198: mislukt de installatie (bijv. geen internet), dan niet 'Klaar' zeggen, ook niet zonder plek in het startmenu.
nep dnf 'exit 1'
nep kdialog 'echo "$*" >>"'"$TMP"'/fouten"; exit 0'
rm -f "$TMP/meldingen" "$TMP/fouten"
installeer "$TMP/kapot.rpm"
klopt '! grep -q "Klaar\|Done" "$TMP/meldingen" 2>/dev/null && grep -q "niet gelukt\|did not work" "$TMP/fouten" 2>/dev/null' \
    "U198: een mislukte installatie zegt dat het niet lukte (niet 'Klaar')"
# U351: een kapot .rpm-bestand: meteen zeggen, niet eerst een doosje maken.
nep rpm 'exit 1'
nep distrobox 'echo "$*" >>"'"$TMP"'/doos-log"; exit 0'
rm -f "$TMP/fouten" "$TMP/doos-log"
installeer "$TMP/half.rpm"
klopt 'grep -q "kapot\|broken" "$TMP/fouten" 2>/dev/null && [ ! -s "$TMP/doos-log" ]' "U351: een kapot .rpm-bestand: meteen een uitleg, geen doosje maken"
nep rpm '[ "$1" = -qp ] && echo voorbeeld; exit 0'
klopt 'grep -q "Het kan wel bij je eigen bestanden" "$ROOT/system_files/usr/bin/bugos-package" && ! grep -q "veilig doosje" "$ROOT/system_files/usr/bin/bugos-package"' \
    "U245: installeren zegt eerlijk dat het programma bij je bestanden kan (geen 'veilig doosje')"
# U424: het doosje maken mislukt omdat de computer vol is: dat zeggen, niet 'heb je internet?'.
nep distrobox 'case "$1" in list) exit 0;; create) echo "Error: writing blob: No space left on device" >&2; exit 1;; esac; exit 0'
rm -f "$TMP/fouten"
installeer "$TMP/half.rpm"
klopt 'grep -qi "vol\|full" "$TMP/fouten" 2>/dev/null && ! grep -qi "internet\|online" "$TMP/fouten"' "U424: doosje maken met een volle computer: dat wordt gezegd"
# U465: programma's uit een .rpm/.deb worden bijgewerkt (elke dag, bij 'Updates vanzelf').
nep distrobox 'case "$1" in list) echo " bugos-ubuntu ";; upgrade) echo "$2" >>"'"$TMP"'/bijgewerkt";; esac; exit 0'
rm -f "$TMP/bijgewerkt"
mkdir -p "$TMP/thuis/.local/share/containers"
HOME="$TMP/thuis" PATH="$TMP/bin:$PATH" bash "$TMP/bugos-package" --bijwerken >/dev/null 2>&1
SDU="$ROOT/system_files/usr/lib/systemd/user"
klopt '[ "$(cat "$TMP/bijgewerkt" 2>/dev/null)" = bugos-ubuntu ] && grep -qx "ExecCondition=/usr/bin/bugos-updates mag-vanzelf" "$SDU/bugos-update-doosjes.service" && grep -qx "OnCalendar=daily" "$SDU/bugos-update-doosjes.timer" && grep -q "enable bugos-update-doosjes.timer" "$ROOT/build_files/build.sh"' \
    "U465: programma's uit een .rpm/.deb krijgen ook updates (hun doosje, elke dag bij 'Updates vanzelf')"
# U473: niet via een hotspot, opnieuw proberen als het mislukte, en niets doen voor een account zonder doosjes.
nep distrobox 'case "$1" in list) echo " bugos-ubuntu ";; upgrade) echo "$2" >>"'"$TMP"'/bijgewerkt"; exit 1;; esac; exit 0'
HOME="$TMP/thuis" PATH="$TMP/bin:$PATH" bash "$TMP/bugos-package" --bijwerken >/dev/null 2>&1; c1=$?
rm -f "$TMP/bijgewerkt"
HOME="$TMP/leeg" PATH="$TMP/bin:$PATH" bash "$TMP/bugos-package" --bijwerken >/dev/null 2>&1; c2=$?
klopt '[ "$c1" -ne 0 ] && [ "$c2" -eq 0 ] && [ ! -e "$TMP/bijgewerkt" ] && grep -q "Metered" "$SDU/bugos-update-doosjes.service" && grep -qx "Restart=on-failure" "$SDU/bugos-update-doosjes.service"' \
    "U473: doosjes bijwerken: niet via een hotspot, later opnieuw als het mislukte, niets zonder doosjes ($c1, $c2)"
echo "$fouten fout(en)."
[ "$fouten" -eq 0 ]
