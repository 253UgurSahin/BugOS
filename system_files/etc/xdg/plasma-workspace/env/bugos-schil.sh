# shellcheck shell=bash
# Gelezen door startplasma bij elke sessie. In de gewone sessie BUGOS_SCHIL weghalen uit systemd: blijft de
# systemd-gebruikersdienst na de proefsessie nog even draaien (snel opnieuw inloggen), dan zou de gewone sessie
# anders ook de nieuwe schil krijgen.
if [ "${BUGOS_SCHIL:-}" != 1 ]; then
    systemctl --user unset-environment BUGOS_SCHIL PLASMA_DEFAULT_SHELL >/dev/null 2>&1 || true
    unset PLASMA_DEFAULT_SHELL
fi
