# BugOS - gedeelde hulpjes voor alle bugos-* scripts.
# shellcheck shell=bash

# Taal kiezen: Nederlands als het systeem Nederlands is, anders Engels.
bugos_taal() {
    case "${LC_MESSAGES:-${LANG:-}}" in
    nl* | NL*) echo nl ;;
    *) echo en ;;
    esac
}

# t "Nederlandse tekst" "English text"  -> geeft de juiste taal terug.
t() {
    if [ "$(bugos_taal)" = nl ]; then echo "$1"; else echo "$2"; fi
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
