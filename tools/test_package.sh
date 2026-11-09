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

echo "$fouten fout(en)."
[ "$fouten" -eq 0 ]
