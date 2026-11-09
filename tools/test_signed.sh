#!/usr/bin/bash
# shellcheck disable=SC2016  # de $ in de nep-programma's en controles is bedoeld (wordt later uitgevoerd)
# Test van bugos-ondertekend: een computer zonder controle stapt één keer over op ondertekende updates;
# een computer die al goed staat, of een ander beeld draait, blijft met rust. Met een nep-rpm-ostree.
#
# Gebruik:  bash tools/test_signed.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/var"
fouten=0
klopt() { if eval "$1"; then echo "OK    $2"; else echo "FOUT  $2"; fouten=$((fouten + 1)); fi; }
nep() { printf '#!/usr/bin/bash\n%s\n' "$2" >"$TMP/bin/$1"; chmod +x "$TMP/bin/$1"; }

echo "nep-sleutel" >"$TMP/bugos.pub"
sed -e "s|/etc/pki/containers/bugos.pub|$TMP/bugos.pub|" -e "s|/var/lib/bugos|$TMP/var|g" \
    "$ROOT/system_files/usr/bin/bugos-ondertekend" >"$TMP/ondertekend"
nep nm-online 'exit 0'
nep rpm-ostree 'case "$1" in status) cat "'"$TMP"'/status.json";; rebase) echo "$2" >>"'"$TMP"'/rebase";; esac'
draai() { rm -f "$TMP/var/ondertekend" "$TMP/rebase"; printf '{"deployments":[{"booted":true,"container-image-reference":"%s"}]}' "$1" >"$TMP/status.json"; PATH="$TMP/bin:$PATH" bash "$TMP/ondertekend" >/dev/null 2>&1; }

draai "ostree-unverified-registry:ghcr.io/253ugursahin/bugos:latest"
klopt '[ "$(cat "$TMP/rebase")" = "ostree-image-signed:docker://ghcr.io/253ugursahin/bugos:latest" ] && [ -e "$TMP/var/ondertekend" ]' \
    "zonder controle: overstappen op ostree-image-signed (zelfde beeld en tag), en onthouden"
draai "ostree-image-signed:docker://ghcr.io/253ugursahin/bugos-nvidia:latest"
klopt '[ ! -e "$TMP/rebase" ] && [ -e "$TMP/var/ondertekend" ]' "staat al goed: niets doen"
draai "ostree-unverified-registry:ghcr.io/iemand-anders/eigen:latest"
klopt '[ ! -e "$TMP/rebase" ]' "een ander beeld (zelf gekozen): met rust laten"
rm "$TMP/bugos.pub"
draai "ostree-unverified-registry:ghcr.io/253ugursahin/bugos:latest"
klopt '[ ! -e "$TMP/rebase" ] && [ ! -e "$TMP/var/ondertekend" ]' "nog geen sleutel in BugOS: niets doen (later opnieuw)"
nep rpm-ostree 'case "$1" in status) cat "'"$TMP"'/status.json";; rebase) exit 1;; esac'
echo "nep-sleutel" >"$TMP/bugos.pub"
draai "ostree-unverified-registry:ghcr.io/253ugursahin/bugos:latest"
klopt '[ ! -e "$TMP/var/ondertekend" ]' "overstappen mislukt (geen internet): niet onthouden, volgende keer opnieuw"

# U303: al eens overgestapt (merkteken in /var), maar 'terug' naar een versie zonder controle: opnieuw overstappen.
nep rpm-ostree 'case "$1" in status) cat "'"$TMP"'/status.json";; rebase) echo "$2" >>"'"$TMP"'/rebase";; esac'
printf '{"deployments":[{"booted":true,"container-image-reference":"ostree-unverified-registry:ghcr.io/253ugursahin/bugos:latest"}]}' >"$TMP/status.json"
rm -f "$TMP/rebase"; touch "$TMP/var/ondertekend"
PATH="$TMP/bin:$PATH" bash "$TMP/ondertekend" >/dev/null 2>&1
klopt '[ -e "$TMP/rebase" ]' "U303: na 'terug' naar een versie zonder controle stapt hij opnieuw over"
# ... maar niet als de overstap al klaarstaat voor de volgende keer opstarten.
printf '{"deployments":[{"booted":false,"container-image-reference":"ostree-image-signed:docker://ghcr.io/253ugursahin/bugos:latest"},{"booted":true,"container-image-reference":"ostree-unverified-registry:ghcr.io/253ugursahin/bugos:latest"}]}' >"$TMP/status.json"
rm -f "$TMP/rebase"
PATH="$TMP/bin:$PATH" bash "$TMP/ondertekend" >/dev/null 2>&1
klopt '[ ! -e "$TMP/rebase" ]' "U303: staat de overstap al klaar, dan niet nog een keer"
# U307: bewust 'terug' van een ondertekende (nieuwere) naar de oude versie zonder controle: niet meteen weer overstappen.
printf '{"deployments":[{"booted":true,"timestamp":1000,"container-image-reference":"ostree-unverified-registry:ghcr.io/253ugursahin/bugos:latest"},{"booted":false,"timestamp":2000,"container-image-reference":"ostree-image-signed:docker://ghcr.io/253ugursahin/bugos:latest"}]}' >"$TMP/status.json"
rm -f "$TMP/rebase"
PATH="$TMP/bin:$PATH" bash "$TMP/ondertekend" >/dev/null 2>&1
klopt '[ ! -e "$TMP/rebase" ]' "U307: na een bewuste 'terug' zet hij de nieuwere versie niet stiekem terug"
echo "$fouten fout(en)."
[ "$fouten" -eq 0 ]
