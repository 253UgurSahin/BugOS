#!/usr/bin/bash
# BugOS-stick (live ISO) helemaal lokaal bouwen, zonder GitHub.
# ===============================================================
# Waarom: via GitHub duurt het lang (bouwen, en dan ~6 GB downloaden). Lokaal
# halen we alleen de fundering (Fedora Kinoite van Universal Blue, ~3 GB) en de extra pakketten op, en
# bouwen we de rest zelf. Het doet precies wat build.yml + iso.yml doen:
#   1. BugOS bouwen uit deze map (Containerfile)            -> localhost/bugos:lokaal
#   2. Een eigen registry op localhost:5000 (de stick-bouw "haalt" BugOS
#      daar op, zoals hij in iso.yml van GitHub Packages haalt)
#   3. De live-omgeving bouwen, met BugOS erin               -> localhost/bugos-live:lokaal
#   4. De ISO maken met hetzelfde script als Titanoboa (vaste versie)
#
# Draait als root, met podman, op Linux. Op Windows/macOS via Docker:
#   docker run --rm -it --privileged \
#       -v bugos-podman:/var/lib/containers \
#       -v <map-met-deze-repo>:/repo:ro -v <uitvoermap>:/uit \
#       quay.io/podman/stable bash /repo/tools/iso-lokaal.sh /repo /uit
# Let op: op Windows moet de repo-map LF-regeleinden hebben (bijv. uitgepakt
# met "git -c core.autocrlf=false archive HEAD"), anders struikelt bash over \r.
#
# Gebruik:  iso-lokaal.sh <repo-map> <uitvoermap> [variant main|nvidia]

set -euo pipefail

REPO="${1:?geef de map van de BugOS-repo}"
UIT="${2:?geef de uitvoermap voor de ISO}"
VARIANT="${3:-main}"

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

stap() { printf '\n==> %s\n' "$*"; }

mkdir -p "$UIT"
# In een container is /proc/sys soms alleen-lezen; podman-in-podman wil erin schrijven.
mount -o remount,rw /proc/sys 2>/dev/null || true

stap "1. BugOS bouwen (fundering: $BASIS)"
podman build \
    --build-arg BASE_IMAGE="$BASIS" \
    --build-arg BUGOS_VARIANT="$VARIANT" \
    --build-arg BUGOS_VERSION="$VERSIE" \
    --label containers.bootc=1 \
    -t "localhost/${NAAM}:lokaal" "$REPO"

stap "2. Eigen registry op localhost:5000"
podman rm -f bugos-registry >/dev/null 2>&1 || true
podman run -d --rm --name bugos-registry --network host docker.io/library/registry:2
# Wachten tot hij antwoordt.
for _ in $(seq 1 30); do
    curl -fs http://localhost:5000/v2/ >/dev/null && break
    sleep 1
done
# --digestfile: de precieze versie zoals hij in de registry staat (die geven
# we door, net als iso.yml dat met de versie van GitHub Packages doet).
DIGESTBESTAND="$(mktemp)"
podman push --tls-verify=false --digestfile "$DIGESTBESTAND" \
    "localhost/${NAAM}:lokaal" "localhost:5000/${NAAM}:lokaal"
DIGEST="$(cat "$DIGESTBESTAND")"
rm -f "$DIGESTBESTAND"
echo "digest: $DIGEST"

stap "3. Live-omgeving bouwen, met BugOS erin"
# Leeg inlogbestand: de lokale registry heeft geen wachtwoord nodig.
LEEG="$(mktemp)"
podman build --network host \
    --cap-add sys_admin --security-opt label=disable --squash \
    --secret id=ghcr,src="$LEEG" \
    --build-arg BASE_IMAGE="localhost/${NAAM}:lokaal" \
    --build-arg IMAGE_REF="$IMAGE_REF" \
    --build-arg IMAGE_DIGEST="$DIGEST" \
    --build-arg IMAGE_SOURCE="localhost:5000/${NAAM}" \
    --build-arg IMAGE_SOURCE_TLS=false \
    --build-arg BUGOS_VARIANT="$VARIANT" \
    -t localhost/bugos-live:lokaal "$REPO/iso_live"
rm -f "$LEEG"
podman rm -f bugos-registry >/dev/null 2>&1 || true

stap "4. ISO maken (Titanoboa $TITANOBOA)"
WERK="$(mktemp -d)"
curl -fsSL -o "$WERK/build_iso.sh" \
    "https://raw.githubusercontent.com/ublue-os/titanoboa/${TITANOBOA}/build_iso.sh"
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
