#!/usr/bin/bash
# shellcheck disable=SC2016  # de $ in de nep-programma's en controles is bedoeld (wordt later uitgevoerd)
# Test van bugos-spelmodus: twee keer 'aan' en dan 'uit' moet alles terugzetten zoals het was.
# Met nep-programma's (powerprofilesctl, systemctl, meldingen): er verandert niets aan je computer.
#
# Gebruik:  bash tools/test_spelmodus.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/thuis"
fouten=0
klopt() { if eval "$1"; then echo "OK    $2"; else echo "FOUT  $2"; fouten=$((fouten + 1)); fi; }
nep() { printf '#!/usr/bin/bash\n%s\n' "$2" >"$TMP/bin/$1"; chmod +x "$TMP/bin/$1"; }

sed "s|/usr/share/bugos|$ROOT/system_files/usr/share/bugos|g" "$ROOT/system_files/usr/bin/bugos-spelmodus" >"$TMP/spelmodus"
# Nep-stroomprofiel: onthoudt de stand in een bestand.
echo balanced >"$TMP/profiel"
nep powerprofilesctl 'case "$1" in get) cat "'"$TMP"'/profiel";; set) echo "$2" >"'"$TMP"'/profiel";; esac'
for p in systemctl notify-send kdialog qdbus qdbus6 gdbus busctl dbus-send; do nep "$p" 'exit 0'; done

draai() { HOME="$TMP/thuis" XDG_CONFIG_HOME="$TMP/thuis/.config" PATH="$TMP/bin:$PATH" bash "$TMP/spelmodus" "$1" >/dev/null 2>&1; }
draai aan
draai aan
draai uit
klopt '[ "$(cat "$TMP/profiel")" = balanced ]' "twee keer aan, dan uit: stroomprofiel weer zoals het was (balanced)"
klopt '[ "$(HOME="$TMP/thuis" XDG_CONFIG_HOME="$TMP/thuis/.config" PATH="$TMP/bin:$PATH" bash "$TMP/spelmodus" status)" = uit ]' "daarna staat game-modus uit"

# B001: zoals op Fedora 44 (tuned-ppd): geen powerprofilesctl, wel de dienst op D-Bus (busctl).
rm -f "$TMP/bin/powerprofilesctl"
echo power-saver >"$TMP/profiel"
nep busctl 'case "$2" in get-property) echo "s \"$(cat "'"$TMP"'/profiel")\"";; set-property) echo "$8" >"'"$TMP"'/profiel";; esac'
if command -v powerprofilesctl >/dev/null 2>&1; then
    echo "OK    (overgeslagen: deze computer heeft zelf powerprofilesctl)"
else
    draai aan
    klopt '[ "$(cat "$TMP/profiel")" = performance ]' "zonder powerprofilesctl: game-modus aan zet via D-Bus volle kracht"
    draai uit
    klopt '[ "$(cat "$TMP/profiel")" = power-saver ]' "zonder powerprofilesctl: uit zet het profiel van daarvoor terug (power-saver)"
fi

echo "$fouten fout(en)."
[ "$fouten" -eq 0 ]
