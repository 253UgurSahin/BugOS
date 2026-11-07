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

echo "$fouten fout(en)."
[ "$fouten" -eq 0 ]
