# BugOS - het bouwrecept
# ======================
# Jip-en-Janneke: dit bestand zegt "pak deze fundering, doe er onze
# BugOS-spullen in, en maak er een nieuw systeem van".
#
# BASE_IMAGE kiest de fundering:
#   - ghcr.io/ublue-os/kinoite-main:44    -> gewone pc's (Intel/AMD)
#   - ghcr.io/ublue-os/kinoite-nvidia:44  -> pc's met een Nvidia-kaart
# Dat is kaal Fedora Kinoite (Fedora Atomic met KDE) van Universal Blue, met
# alleen codecs en drivers erbij. Geen ander systeem eronder (zoals Aurora):
# BugOS is een eigen systeem, net als Bazzite, dat op dezelfde basis bouwt.
#
# Het Fedora-nummer (44) staat vast, ook in .github/workflows/build.yml en
# tools/iso-lokaal.sh: een nieuwe Fedora komt er nooit 's nachts vanzelf in.
# Overstappen (bijv. naar 45): verander het nummer op die drie plekken, bouw
# een test-ISO en kijk of thema en menu's nog kloppen (build.sh zegt "LET OP"
# als een aanpassing niet meer past). Fedora 44 krijgt updates tot 2 juni 2027.

ARG BASE_IMAGE=ghcr.io/ublue-os/kinoite-main:44

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
