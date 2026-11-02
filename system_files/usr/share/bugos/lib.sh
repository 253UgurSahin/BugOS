# BugOS - gedeelde hulpjes voor alle bugos-* scripts.
# shellcheck shell=bash

# Taal van de gebruiker als twee letters, bijv. nl, en, de, tr.
bugos_taal() {
    local lang="${LC_ALL:-${LC_MESSAGES:-${LANG:-en}}}"
    lang="${lang%%.*}"
    lang="${lang%%_*}"
    echo "${lang,,}"
}

# t "Nederlandse tekst" "English text"  -> geeft de juiste taal terug.
# Andere talen komen uit /usr/share/bugos/vertalingen/<taal>.json (Engels -> vertaling).
t() {
    local taal bestand vertaald
    taal="$(bugos_taal)"
    if [ "$taal" = nl ]; then
        echo "$1"
        return
    fi
    bestand="/usr/share/bugos/vertalingen/$taal.json"
    if [ "$taal" != en ] && [ -f "$bestand" ] && command -v jq >/dev/null 2>&1; then
        vertaald="$(jq -r --arg k "$2" '.[$k] // empty' "$bestand" 2>/dev/null)"
        if [ -n "$vertaald" ]; then
            echo "$vertaald"
            return
        fi
    fi
    echo "$2"
}

# Kleine melding rechtsonder in beeld.
melding() {
    notify-send --app-name=BugOS --icon=bugos-logo "$1" "${2:-}" 2>/dev/null ||
        echo "$1: ${2:-}"
}

# Venster met Ja/Nee. Geeft 0 terug bij Ja.
vraag() {
    kdialog --title BugOS --yesno "$(printf '%b' "$1")" 2>/dev/null
}

# Venster met een uitleg dat iets niet lukte.
fout() {
    kdialog --title BugOS --sorry "$(printf '%b' "$1")" 2>/dev/null || echo "$1" >&2
}

# Venster met een gewone mededeling.
info() {
    kdialog --title BugOS --msgbox "$(printf '%b' "$1")" 2>/dev/null || echo "$1"
}

# Plek waar BugOS onthoudt wat de gebruiker heeft gekozen.
# shellcheck disable=SC2034 # wordt gebruikt door de scripts die dit inladen
BUGOS_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/bugos"
