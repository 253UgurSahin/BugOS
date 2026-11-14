#!/usr/bin/bash
# BugOS (en de stick met BugOS) helemaal lokaal bouwen, zonder GitHub.
# =====================================================================
# Waarom: via GitHub duurt het lang (bouwen, en dan ~6 GB downloaden). Lokaal halen we alleen de fundering
# (Fedora Kinoite van Universal Blue, ~3 GB) en de extra pakketten op, en bouwen we de rest zelf. Het doet wat
# build.yml + iso.yml doen:
#   1. BugOS bouwen uit deze map (Containerfile)                -> localhost/bugos:lokaal
#   2. BugOS als OCI-map neerzetten (die gaat ingepakt op de stick, zoals iso.yml hem uit GitHub Packages haalt)
#   3. De live-omgeving bouwen, met BugOS erin                   -> localhost/bugos-live:lokaal
#   4. De ISO maken met het script van Titanoboa (vaste versie)
#
# Twee manieren van gebruiken:
#   - Alles (stap 1-4): een ISO om te installeren. Nodig als je de stick of het installatieprogramma test.
#   - Alleen het beeld (ALLEEN_BEELD=1, stap 1): voor elke volgende ronde fixes. Een test-VM die al BugOS draait,
#     haalt de nieuwe versie dan zelf op met "bootc switch" (zoals een echte update), zonder nieuwe ISO en zonder
#     opnieuw installeren. Geef REGISTRY=<host:poort> mee, dan zet het script het beeld daar neer.
#     Zie docs/TESTING.md, "Lokaal bouwen en testen".
#
# Draait als root, met podman, op Linux (op het werk: gewoon "sudo tools/iso-local.sh . uit").
# Op Windows/macOS in een container met podman:
#   docker run --rm --privileged \
#       -v bugos-podman:/var/lib/containers \
#       -v <map-met-deze-repo>:/repo:ro -v <uitvoermap>:/uit \
#       quay.io/podman/stable bash /repo/tools/iso-local.sh /repo /uit
# Let op: op Windows moet de repo-map LF-regeleinden hebben (bijv. uitgepakt met
# "git -c core.autocrlf=false archive HEAD"), anders struikelt bash over \r.
#
# Gebruik:  iso-local.sh <repo-map> <uitvoermap> [variant main|nvidia]
# Instellingen (omgevingsvariabelen):
#   ALLEEN_BEELD=1      alleen stap 1 (en eventueel naar REGISTRY), geen ISO
#   REGISTRY=host:poort zet het beeld na stap 1 ook in deze registry (zonder TLS), voor "bootc switch" in een VM
#   ISO_ZSTD=3          zstd-niveau van de stick (standaard 3: snel; GitHub/Titanoboa gebruikt 19: kleiner, veel trager)

set -euo pipefail

REPO="${1:?geef de map van de BugOS-repo}"
UIT="${2:?geef de uitvoermap voor de ISO}"
VARIANT="${3:-main}"
ALLEEN_BEELD="${ALLEEN_BEELD:-}"
REGISTRY="${REGISTRY:-}"
ISO_ZSTD="${ISO_ZSTD:-3}"

if [ "$VARIANT" = nvidia ]; then
    BASIS=ghcr.io/ublue-os/kinoite-nvidia:${FEDORA:-44}
    NAAM=bugos-nvidia
else
    BASIS=ghcr.io/ublue-os/kinoite-main:${FEDORA:-44}
    NAAM=bugos
fi
# De naam die BugOS op de stick en na het installeren krijgt (voor updates).
IMAGE_REF="ghcr.io/253ugursahin/${NAAM}:lokaal"
# Titanoboa: dezelfde vaste versie als in .github/workflows/iso.yml.
TITANOBOA=5c457c3d0518bd17e754be0fd98a60d29d26abb4
VERSIE="$(date -u +%Y.%m.%d)"

# Elke stap met de tijd sinds het begin (minuten:seconden), zodat je in het logboek ziet waar de tijd heen gaat.
stap() { printf '\n==> [%02d:%02d] %s\n' $((SECONDS / 60)) $((SECONDS % 60)) "$*"; }

mkdir -p "$UIT"
# In een container is /proc/sys soms alleen-lezen; podman-in-podman wil erin schrijven.
mount -o remount,rw /proc/sys 2>/dev/null || true

# Opslag van podman: de overlay van de kernel, niet fuse-overlayfs. Het beeld quay.io/podman/stable (waarin deze
# lokale bouw meestal draait) gebruikt standaard fuse-overlayfs. Daarmee kwamen bestanden die de bouw over een
# bestaand bestand uit de fundering schreef, half in het beeld: wel de nieuwe lengte, maar de oude inhoud met
# nul-bytes erachter (gezien in /usr/lib/plasmalogin/defaults.conf, /etc/xdg/kcm-about-distrorc,
# /etc/xdg/user-dirs.defaults en /etc/xdg/PlasmaDiscoverUpdates; tools/test_image.sh 1c vangt dat nu). En het was
# traag: één fuse-proces met 20 GB geheugen op één kern, uren lang. De bouw op GitHub gebruikt de overlay van de
# kernel al. Die werkt hier ook: de opslag (/var/lib/containers) staat op een gewone schijf (een Docker-volume).
if grep -q '^mount_program *= *"/usr/bin/fuse-overlayfs"' /etc/containers/storage.conf 2>/dev/null; then
    sed -e 's|^mount_program *=.*|# mount_program: uit (zie tools/iso-local.sh)|' -e 's|^mountopt *=.*|mountopt = "nodev"|' \
        /etc/containers/storage.conf >/tmp/bugos-storage.conf
    export CONTAINERS_STORAGE_CONF=/tmp/bugos-storage.conf
fi
stap "Opslag van podman: $(podman info --format '{{.Store.GraphDriverName}} {{.Store.GraphOptions}}' 2>&1 | head -c 300)"

# Werkmap op dezelfde schijf als de opslag (niet in /tmp van de container): de OCI-map (~6 GB) en de ISO (~11 GB)
# passen dan, en verplaatsen is daar een hernoeming in plaats van een kopie.
WERK="${WERKMAP:-/var/lib/containers/bugos-werk}"
rm -rf "$WERK"
mkdir -p "$WERK"

stap "1. BugOS bouwen (fundering: $BASIS)"
podman build \
    --build-arg BASE_IMAGE="$BASIS" \
    --build-arg BUGOS_VARIANT="$VARIANT" \
    --build-arg BUGOS_VERSION="$VERSIE" \
    --label containers.bootc=1 \
    -t "localhost/${NAAM}:lokaal" "$REPO"

if [ -n "$REGISTRY" ]; then
    # Voor een test-VM: die haalt het beeld hier op met "bootc switch" (zoals een echte update). Zonder TLS: het is
    # een registry op je eigen computer. Ingepakt met zstd: veel sneller dan gzip, en bootc leest het.
    stap "1b. Beeld naar de registry $REGISTRY (voor bootc switch in de test-VM)"
    podman push --tls-verify=false --compression-format zstd \
        "localhost/${NAAM}:lokaal" "docker://${REGISTRY}/${NAAM}:lokaal"
fi
if [ -n "$ALLEEN_BEELD" ]; then
    stap "Klaar: localhost/${NAAM}:lokaal (alleen het beeld, geen ISO)"
    exit 0
fi

# Vroeger ging BugOS hier naar een eigen registry op localhost:5000, en haalde de stick-bouw hem daar weer op. Dat
# is twee keer ~6 GB schrijven en lezen over het netwerk. Nu: één keer als OCI-map; stap 3 krijgt die map als
# volume mee (IMAGE_SOURCE=oci:..., zie iso_live/src/build.sh). De lagen gaan ingepakt (gzip, zoals GitHub
# Packages) op de stick: zo leest het installatieprogramma ze (ostreecontainer --transport=oci).
stap "2. BugOS als OCI-map neerzetten (gaat op de stick)"
podman push "localhost/${NAAM}:lokaal" "oci:${WERK}/bron-oci"
du -sh "${WERK}/bron-oci"

stap "3. Live-omgeving bouwen, met BugOS erin"
# Leeg inlogbestand: een lokale OCI-map heeft geen wachtwoord nodig.
LEEG="$(mktemp)"
podman build \
    --cap-add sys_admin --security-opt label=disable --squash \
    --secret id=ghcr,src="$LEEG" \
    --volume "${WERK}/bron-oci:/bron-oci:ro" \
    --build-arg BASE_IMAGE="localhost/${NAAM}:lokaal" \
    --build-arg IMAGE_REF="$IMAGE_REF" \
    --build-arg IMAGE_SOURCE="oci:/bron-oci" \
    --build-arg BUGOS_VARIANT="$VARIANT" \
    -t localhost/bugos-live:lokaal "$REPO/iso_live"
rm -f "$LEEG"
rm -rf "${WERK}/bron-oci"

stap "4. ISO maken (Titanoboa $TITANOBOA, zstd niveau $ISO_ZSTD)"
curl -fsSL -o "$WERK/build_iso.sh" \
    "https://raw.githubusercontent.com/ublue-os/titanoboa/${TITANOBOA}/build_iso.sh"
# Titanoboa pakt de stick in met zstd niveau 19: het kleinst, maar op ~19 GB ook verreweg de traagste stap. Voor een
# test-ISO is niveau 3 vele malen sneller, en de ISO maar iets groter. Wil je precies wat GitHub maakt: ISO_ZSTD=19.
grep -q -- '-Xcompression-level 19' "$WERK/build_iso.sh" || { echo "build_iso.sh is veranderd: geen zstd-niveau 19 gevonden" >&2; exit 1; }
sed -i "s/-Xcompression-level 19/-Xcompression-level ${ISO_ZSTD}/" "$WERK/build_iso.sh"
chmod +x "$WERK/build_iso.sh"
mkdir -p "$WERK/output"
podman run --rm -i \
    --cap-add sys_admin --security-opt label=disable \
    -v "$WERK/build_iso.sh":/src/build_iso.sh:ro \
    --mount type=image,source=localhost/bugos-live:lokaal,dst=/rootfs \
    -v "$WERK/output":/output \
    quay.io/fedora/fedora:latest /src/build_iso.sh
ISO="$(find "$WERK/output" -name '*.iso' | head -1)"
DOEL="$UIT/BugOS-${VARIANT}-lokaal-${VERSIE}.iso"
mv "$ISO" "$DOEL"
(cd "$UIT" && sha256sum "$(basename "$DOEL")" | tee "$(basename "$DOEL").sha256")
rm -rf "$WERK"
stap "Klaar: $DOEL"
