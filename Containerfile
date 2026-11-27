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
# tools/iso-local.sh: een nieuwe Fedora komt er nooit 's nachts vanzelf in.
# Overstappen (bijv. naar 45): verander het nummer op die drie plekken, bouw
# een test-ISO en kijk of thema en menu's nog kloppen (build.sh zegt "LET OP"
# als een aanpassing niet meer past). Fedora 44 krijgt updates tot 2 juni 2027.

ARG BASE_IMAGE=ghcr.io/ublue-os/kinoite-main:44

# Deze tussenstap houdt de bouwscripts buiten het eindresultaat.
FROM scratch AS ctx
COPY build_files /
COPY system_files /system_files

# De eigen BugOS-schil (bugos-shell, docs/STANDALONE.md) bouwen, in een eigen tussenstap: de compiler en de
# -devel-pakketten komen zo nooit in BugOS zelf. Tegen precies dezelfde Qt- en layer-shell-qt-versie als in de
# fundering (niet de nieuwste uit 'updates'), anders zou het programma bibliotheken verwachten die BugOS niet heeft.
# Lukt het bouwen niet, dan gaat de bouw van BugOS gewoon door, zonder bugos-shell: de proefsessie staat dan niet op het
# inlogscherm (TryExec), en de gewone sessie merkt er niets van.
FROM ${BASE_IMAGE} AS schil
COPY shell /shell
RUN mkdir -p /uit && \
    v() { rpm -q --qf '%{VERSION}-%{RELEASE}' "$1"; } && \
    if dnf5 install -y --setopt=install_weak_deps=False cmake gcc-c++ \
            "qt6-qtbase-devel-$(v qt6-qtbase)" "qt6-qtdeclarative-devel-$(v qt6-qtdeclarative)" \
            "layer-shell-qt-devel-$(v layer-shell-qt)" && \
        cmake -S /shell -B /bouw -DCMAKE_BUILD_TYPE=Release -DBUGOS_LAYERSHELL_VERPLICHT=ON && \
        cmake --build /bouw -j"$(nproc)"; then \
        install -Dm755 /bouw/bugos-shell /uit/bugos-shell; \
    else \
        echo "LET OP: bugos-shell kon niet gebouwd worden; BugOS komt er zonder (alleen de proefsessie ontbreekt)." >&2; \
    fi

FROM ${BASE_IMAGE}

# bugos-shell (als het bouwen lukte; anders is /uit leeg en komt er niets bij).
COPY --from=schil /uit/ /usr/bin/

ARG BUGOS_VARIANT=main
ARG BUGOS_VERSION=dev

RUN --mount=type=bind,from=ctx,source=/,target=/ctx \
    --mount=type=cache,dst=/var/cache \
    --mount=type=cache,dst=/var/log \
    --mount=type=tmpfs,dst=/tmp \
    BUGOS_VARIANT="${BUGOS_VARIANT}" BUGOS_VERSION="${BUGOS_VERSION}" /ctx/build.sh

# Laatste controle: is het een geldig opstartbaar systeem?
RUN bootc container lint
