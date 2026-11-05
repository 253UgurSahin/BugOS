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
nep bugos-thema 'echo licht'
nep wine 'exit 1'                                   # het programma stopt meteen met een fout
nep wineboot 'mkdir -p "$WINEPREFIX/half"; exit 1'  # klaarzetten mislukt halverwege
nep winepath 'echo "$2"'
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

echo "$fouten fout(en)."
[ "$fouten" -eq 0 ]
