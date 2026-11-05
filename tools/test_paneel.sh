#!/usr/bin/bash
# shellcheck disable=SC2016,SC2034  # de $ in de nep-programma's en controles is bedoeld (wordt later uitgevoerd)
# Test van 'bugos-paneel standaard': lukt het bureaublad niet, dan mag hij het niet als "klaar" onthouden.
# Met nep-programma's (gdbus, qdbus6): er verandert niets aan je computer.
#
# Gebruik:  bash tools/test_paneel.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/thuis"
fouten=0
klopt() { if eval "$1"; then echo "OK    $2"; else echo "FOUT  $2"; fouten=$((fouten + 1)); fi; }
nep() { printf '#!/usr/bin/bash\n%s\n' "$2" >"$TMP/bin/$1"; chmod +x "$TMP/bin/$1"; }

sed "s|/usr/share/bugos|$ROOT/system_files/usr/share/bugos|g" "$ROOT/system_files/usr/bin/bugos-paneel" >"$TMP/paneel"
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

echo "$fouten fout(en)."
[ "$fouten" -eq 0 ]
