#!/usr/bin/bash
# shellcheck disable=SC2016  # de $ in de nep-programma's en controles is bedoeld (wordt later uitgevoerd)
# Test van bugos-light-mode: 'uit' zet terug wat de gebruiker zelf had ingesteld (niet zomaar de standaard).
# Met nep-programma's (kwriteconfig6, kreadconfig6, balooctl6): er verandert niets aan je computer.
#
# Gebruik:  bash tools/test_light_mode.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/thuis" "$TMP/kde"
fouten=0
klopt() { if eval "$1"; then echo "OK    $2"; else echo "FOUT  $2"; fouten=$((fouten + 1)); fi; }
nep() { printf '#!/usr/bin/bash\n%s\n' "$2" >"$TMP/bin/$1"; chmod +x "$TMP/bin/$1"; }

sed "s|/usr/share/bugos|$ROOT/system_files/usr/share/bugos|g" "$ROOT/system_files/usr/bin/bugos-light-mode" >"$TMP/lichte-stand"
# Nep-KDE-instellingen: één bestand per bestand/groep/sleutel.
K="$TMP/kde"
nep kreadconfig6 'f="'"$K"'/$2.$4.$6"; [ -f "$f" ] && cat "$f"; exit 0'
nep kwriteconfig6 'f="'"$K"'/$2.$4.$6"; if [[ " $* " == *" --delete "* ]]; then rm -f "$f"; else printf "%s" "${!#}" >"$f"; fi'
# Nep-zoeker: de gebruiker had hem zelf uitgezet.
# Zoals de echte balooctl6: 'status' zegt "uit" op stderr (vertaald) met code 1; de keuze staat in baloofilerc.
mkdir -p "$K"
printf false >"$K/baloofilerc.Basic Settings.Indexing-Enabled"
nep balooctl6 'f="'"$K"'/baloofilerc.Basic Settings.Indexing-Enabled"; case "$1" in
status) if [ "$(cat "$f" 2>/dev/null)" = false ]; then echo "Baloo is momenteel uitgeschakeld." >&2; exit 1; fi; echo "Baloo File Indexer is running";;
enable) printf true >"$f";; disable) printf false >"$f";; esac'
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
klopt '[ "$(cat "$K/baloofilerc.Basic Settings.Indexing-Enabled")" = false ]' "uit: de zoeker blijft uit, want die had je zelf uitgezet (U056)"
# En stond hij aan, dan komt hij na 'uit' weer aan.
printf true >"$K/baloofilerc.Basic Settings.Indexing-Enabled"
draai aan
draai uit
klopt '[ "$(cat "$K/baloofilerc.Basic Settings.Indexing-Enabled")" = true ]' "uit: stond de zoeker aan, dan komt hij weer aan"

# U127: uit terwijl hij al uit stond: niets aan jouw instellingen veranderen.
printf "0.5" >"$K/kdeglobals.KDE.AnimationDurationFactor"
draai uit
klopt '[ "$(cat "$K/kdeglobals.KDE.AnimationDurationFactor" 2>/dev/null)" = 0.5 ]' \
    "U127: lichte stand uit terwijl hij al uit stond: je eigen animatie-instelling blijft"

echo "$fouten fout(en)."
[ "$fouten" -eq 0 ]
