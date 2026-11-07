#!/usr/bin/bash
# shellcheck disable=SC2016  # de $ in de nep-programma's en controles is bedoeld (wordt later uitgevoerd)
# Test van bugos-lichte-stand: 'uit' zet terug wat de gebruiker zelf had ingesteld (niet zomaar de standaard).
# Met nep-programma's (kwriteconfig6, kreadconfig6, balooctl6): er verandert niets aan je computer.
#
# Gebruik:  bash tools/test_lichte_stand.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/thuis" "$TMP/kde"
fouten=0
klopt() { if eval "$1"; then echo "OK    $2"; else echo "FOUT  $2"; fouten=$((fouten + 1)); fi; }
nep() { printf '#!/usr/bin/bash\n%s\n' "$2" >"$TMP/bin/$1"; chmod +x "$TMP/bin/$1"; }

sed "s|/usr/share/bugos|$ROOT/system_files/usr/share/bugos|g" "$ROOT/system_files/usr/bin/bugos-lichte-stand" >"$TMP/lichte-stand"
# Nep-KDE-instellingen: één bestand per bestand/groep/sleutel.
K="$TMP/kde"
nep kreadconfig6 'f="'"$K"'/$2.$4.$6"; [ -f "$f" ] && cat "$f"; exit 0'
nep kwriteconfig6 'f="'"$K"'/$2.$4.$6"; if [ "$7" = --delete ]; then rm -f "$f"; else printf "%s" "$7" >"$f"; fi'
# Nep-zoeker: de gebruiker had hem zelf uitgezet.
echo disabled >"$TMP/baloo"
nep balooctl6 'case "$1" in status) echo "Baloo is currently $(cat "'"$TMP"'/baloo")";; enable) echo enabled >"'"$TMP"'/baloo";; disable) echo disabled >"'"$TMP"'/baloo";; esac'
for p in qdbus6 notify-send kdialog; do nep "$p" 'exit 0'; done

printf true >"$K/kwinrc.Plugins.blurEnabled"   # zelf ingesteld: wazige effecten aan
draai() { HOME="$TMP/thuis" XDG_CONFIG_HOME="$TMP/thuis/.config" PATH="$TMP/bin:$PATH" bash "$TMP/lichte-stand" "$1" >/dev/null 2>&1; }
draai aan
klopt '[ "$(cat "$K/kwinrc.Plugins.blurEnabled")" = false ] && [ "$(cat "$K/kdeglobals.KDE.AnimationDurationFactor")" = 0 ]' \
    "aan: wazig en animaties uit"
draai aan   # nog een keer aan mag niets kapot maken
draai uit
klopt '[ "$(cat "$K/kwinrc.Plugins.blurEnabled" 2>/dev/null)" = true ]' "uit: je eigen instelling (wazig aan) komt terug"
klopt '[ ! -e "$K/kdeglobals.KDE.AnimationDurationFactor" ]' "uit: wat niet ingesteld was, is weer niet ingesteld"
klopt '[ "$(cat "$TMP/baloo")" = disabled ]' "uit: de zoeker blijft uit, want die had je zelf uitgezet"

echo "$fouten fout(en)."
[ "$fouten" -eq 0 ]
