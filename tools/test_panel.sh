#!/usr/bin/bash
# shellcheck disable=SC2016,SC2034  # de $ in de nep-programma's en controles is bedoeld (wordt later uitgevoerd)
# Test van 'bugos-panel standaard': lukt het bureaublad niet, dan mag hij het niet als "klaar" onthouden.
# Met nep-programma's (gdbus, qdbus6): er verandert niets aan je computer.
#
# Gebruik:  bash tools/test_panel.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/thuis"
fouten=0
klopt() { if eval "$1"; then echo "OK    $2"; else echo "FOUT  $2"; fouten=$((fouten + 1)); fi; }
nep() { printf '#!/usr/bin/bash\n%s\n' "$2" >"$TMP/bin/$1"; chmod +x "$TMP/bin/$1"; }

sed "s|/usr/share/bugos|$ROOT/system_files/usr/share/bugos|g" "$ROOT/system_files/usr/bin/bugos-panel" >"$TMP/paneel"
nep gdbus 'echo "(true,)"'            # het bureaublad is er
nep qdbus6 'exit 1'                   # ... maar antwoordt (nog) niet
for p in notify-send kdialog sleep; do nep "$p" 'exit 0'; done
MERK="$TMP/thuis/.config/bugos"
draai() { HOME="$TMP/thuis" XDG_CONFIG_HOME="$TMP/thuis/.config" PATH="$TMP/bin:$PATH" bash "$TMP/paneel" standaard >/dev/null 2>&1; }

draai
klopt '[ ! -e "$MERK/paneel-standaard-1" ] && [ ! -e "$MERK/paneel-taakbalkruimte-1" ]' \
    "bureaublad antwoordt niet: niets als klaar onthouden (volgende keer opnieuw)"
nep qdbus6 'echo aan'                 # nu lukt het wel
draai
klopt '[ -e "$MERK/paneel-standaard-1" ] && [ -e "$MERK/paneel-systeemvak-1" ] && [ -e "$MERK/paneel-taakbalkruimte-1" ]' \
    "bureaublad antwoordt: alle stappen klaar en onthouden"

# U073: geen KDE-startknop of systeemvak (Plasma geeft 0): niet "staat aan" melden.
nep notify-send 'echo "$*" >>"'"$TMP"'/meldingen"'
nep qdbus6 'echo 0'
HOME="$TMP/thuis" XDG_CONFIG_HOME="$TMP/thuis/.config" PATH="$TMP/bin:$PATH" bash "$TMP/paneel" startmenu aan >/dev/null 2>&1
code=$?
klopt '[ $code -ne 0 ] && ! grep -q "staat aan\|is on" "$TMP/meldingen" && grep -q "start button\|startknop" "$TMP/meldingen"' \
    "U073: startmenu aan zonder KDE-startknop: zegt dat het niet lukte (code $code)"
: >"$TMP/meldingen"
printf '#!/usr/bin/bash\nprintf "0\\n3\\n"\n' >"$TMP/bin/qdbus6"
HOME="$TMP/thuis" XDG_CONFIG_HOME="$TMP/thuis/.config" PATH="$TMP/bin:$PATH" bash "$TMP/paneel" snelmenu aan >/dev/null 2>&1
code=$?
klopt '[ $code -ne 0 ] && grep -q "system tray\|systeemvak" "$TMP/meldingen"' "U073: snelmenu aan zonder systeemvak: zegt dat het niet lukte"
nep qdbus6 'echo 1'
: >"$TMP/meldingen"
HOME="$TMP/thuis" XDG_CONFIG_HOME="$TMP/thuis/.config" PATH="$TMP/bin:$PATH" bash "$TMP/paneel" startmenu aan >/dev/null 2>&1
code=$?
klopt '[ $code -eq 0 ] && grep -q "staat aan\|is on" "$TMP/meldingen"' "U073: startmenu aan met een startknop: staat aan"

echo "$fouten fout(en)."
[ "$fouten" -eq 0 ]
