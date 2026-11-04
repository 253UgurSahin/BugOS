# BugOS - het bouwrecept
# ======================
# Jip-en-Janneke: dit bestand zegt "pak deze fundering, doe er onze
# BugOS-spullen in, en maak er een nieuw systeem van".
#
# BASE_IMAGE kiest de fundering:
#   - ghcr.io/ublue-os/kinoite-main:latest    -> gewone pc's (Intel/AMD)
#   - ghcr.io/ublue-os/kinoite-nvidia:latest  -> pc's met een Nvidia-kaart
# Dat is kaal Fedora Kinoite (Fedora Atomic met KDE) van Universal Blue, met
# alleen codecs en drivers erbij. Geen ander systeem eronder (zoals Aurora):
# BugOS is een eigen systeem, net als Bazzite, dat op dezelfde basis bouwt.

ARG BASE_IMAGE=ghcr.io/ublue-os/kinoite-main:latest

# Deze tussenstap houdt de bouwscripts buiten het eindresultaat.
FROM scratch AS ctx
COPY build_files /
COPY system_files /system_files

FROM ${BASE_IMAGE}

ARG BUGOS_VARIANT=main
ARG BUGOS_VERSION=dev

RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/log \
    --mount=type=tmpfs,dst=/tmp \
    BUGOS_VARIANT="${BUGOS_VARIANT}" BUGOS_VERSION="${BUGOS_VERSION}" /ctx/build.sh

# Laatste controle: is het een geldig opstartbaar systeem?
RUN bootc container lint
