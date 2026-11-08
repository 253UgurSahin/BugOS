#!/usr/bin/bash
# shellcheck disable=SC2016  # de $ in de nep-programma's en controles is bedoeld (wordt later uitgevoerd)
# Test van de systeem-scripts (updates, ontwikkelaarsmodus, hulp, lichte stand, game-modus, taal).
# Met nep-programma's (rpm-ostree, flatpak, distrobox, nmcli, ...): er verandert niets aan je computer.
#
# Gebruik:  bash tools/test_os_system.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$ROOT/system_files/usr/bin"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/thuis"
fouten=0
klopt() { if eval "$1"; then echo "OK    $2"; else echo "FOUT  $2"; fouten=$((fouten + 1)); fi; }
nep() { printf '#!/usr/bin/bash\n%s\n' "$2" >"$TMP/bin/$1"; chmod +x "$TMP/bin/$1"; }
# Een script met lib.sh uit deze map (niet die van de computer).
kopie() { sed "s|/usr/share/bugos|$ROOT/system_files/usr/share/bugos|g" "$BIN/$1" >"$TMP/$1"; }
# Draai een gekopieerd script met de nep-programma's, in het Engels (C.UTF-8: die taal is er altijd); geeft de afsluitcode.
draai() {
    local naam="$1"
    shift
    HOME="$TMP/thuis" XDG_CONFIG_HOME="$TMP/thuis/.config" PATH="$TMP/bin:$PATH" LC_ALL=C.UTF-8 \
        bash "$TMP/$naam" "$@" >"$TMP/uit" 2>&1
    code=$?
}
# shellcheck disable=SC2034  # code wordt gelezen in de controles (via eval)
code=0
for p in notify-send kdialog pkexec systemctl; do nep "$p" 'exit 0'; done
nep id 'echo 0'   # doe alsof we beheerder zijn, dan vraagt bugos-updates geen wachtwoord

# U005: "Nu updaten" mag niet "klaar" zeggen als de systeem-update mislukt.
kopie bugos-updates
nep flatpak 'exit 0'
nep rpm-ostree 'exit 1'
draai bugos-updates nu
klopt '[ $code -ne 0 ]' "updates nu: rpm-ostree mislukt -> afsluitcode niet 0"
nep flatpak 'echo flatpak >"'"$TMP"'/flatpak-gedaan"'
draai bugos-updates nu
klopt '[ -f "$TMP/flatpak-gedaan" ]' "updates nu: de apps worden ook dan nog bijgewerkt"
nep rpm-ostree 'exit 0'
nep flatpak 'exit 1'
draai bugos-updates nu
klopt '[ $code -eq 0 ]' "updates nu: rpm-ostree gelukt -> afsluitcode 0 (ook als een app niet lukt)"
nep rpm-ostree 'exit 1'
draai bugos-updates terug
klopt '[ $code -ne 0 ] && ! grep -q Done "$TMP/uit"' "updates terug: rollback mislukt -> afsluitcode niet 0, geen 'Done'"
nep rpm-ostree 'exit 0'
draai bugos-updates terug
klopt '[ $code -eq 0 ] && grep -q Done "$TMP/uit"' "updates terug: rollback gelukt -> 'Done'"

# U024: na "terug naar de vorige versie" staat de oude versie bovenaan; dat is geen nieuwe update.
kopie bugos-updatecheck
nep bugos-updates 'echo hand'
nep skopeo 'exit 1'
nep notify-send 'echo "$*" >>"'"$TMP"'/meldingen"'
status_json() {  # $1 = tijd van de bovenste versie, $2 = tijd van de versie die nu draait
    printf '{"deployments":[{"booted":false,"timestamp":%s},{"booted":true,"timestamp":%s}]}' "$1" "$2" >"$TMP/status.json"
}
nep rpm-ostree 'cat "'"$TMP"'/status.json"'
status_json 1000 2000   # bovenaan staat de oudere versie (na terug)
rm -f "$TMP/meldingen"
draai bugos-updatecheck
klopt '! grep -q "Update is ready" "$TMP/meldingen" 2>/dev/null' "updatecheck: na terugzetten geen 'Update is ready'"
status_json 3000 2000   # bovenaan staat een nieuwere versie
rm -f "$TMP/meldingen"
draai bugos-updatecheck
klopt 'grep -q "Update is ready" "$TMP/meldingen" 2>/dev/null' "updatecheck: nieuwere versie klaar -> 'Update is ready'"
nep notify-send 'exit 0'

# Hulp (bugos-help, Python): één controle draaien met de nep-programma's; print stand en tekst.
hulp() {
    HOME="$TMP/thuis" PATH="$TMP/bin:$PATH" LC_ALL=C.UTF-8 QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 \
        python3 - "$ROOT" "$1" <<'PY' 2>&1
import importlib.machinery, importlib.util, sys
root, naam = sys.argv[1], sys.argv[2]
sys.path.insert(0, root + "/system_files/usr/lib/bugos/python")
lader = importlib.machinery.SourceFileLoader("bugos_help", root + "/system_files/usr/bin/bugos-help")
bh = importlib.util.module_from_spec(importlib.util.spec_from_loader("bugos_help", lader))
lader.exec_module(bh)
u = getattr(bh, naam)()
print(u.stand, u.tekst)
PY
}
status_json 1000 2000
klopt '[[ "$(hulp controle_updates)" == ok* ]]' "hulp: na terugzetten staat er geen update klaar"
status_json 3000 2000
klopt '[[ "$(hulp controle_updates)" == let_op* ]]' "hulp: nieuwere versie klaar -> 'An update is ready'"

echo "$fouten fout(en)."
[ "$fouten" -eq 0 ]
