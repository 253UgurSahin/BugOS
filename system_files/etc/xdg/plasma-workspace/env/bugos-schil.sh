# shellcheck shell=bash
# Gelezen door startplasma bij het begin van elke sessie (vóór het doorgeven van de omgeving aan systemd).
# Fase 4 van docs/STANDALONE.md: het nieuwe BugOS-bureaublad is de standaard. bugos-schil kies zegt nieuw of klassiek
# (de sessie 'BugOS klassiek', jouw keuze, die van de computer). Nieuw:
#   BUGOS_SCHIL=1                      plasma-plasmashell.service start bugos-shell (bugos-schil-of-plasma)
#   PLASMA_DEFAULT_SHELL=org.bugos.schil  het BugOS-vergrendelscherm (kscreenlocker)
# Klassiek: allebei weg, ook uit systemd (dat kan nog van een vorige sessie zijn als je snel opnieuw inlogt).
if [ "$(/usr/bin/bugos-schil kies 2>/dev/null)" = nieuw ]; then
    export BUGOS_SCHIL=1
    export PLASMA_DEFAULT_SHELL=org.bugos.schil
else
    unset BUGOS_SCHIL PLASMA_DEFAULT_SHELL
    systemctl --user unset-environment BUGOS_SCHIL PLASMA_DEFAULT_SHELL >/dev/null 2>&1 || true
fi
