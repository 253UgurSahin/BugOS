# BugOS - gedeelde hulpjes voor alle bugos-* scripts.
# shellcheck shell=bash

# Taal van de gebruiker als twee letters, bijv. nl, en, de, tr.
bugos_taal() {
    local lang="${LC_ALL:-${LC_MESSAGES:-${LANG:-en}}}" eerste
    # De taal die je in KDE kiest staat in LANGUAGE (bijv. "nl:en_US"): die gaat voor, net als bij
    # alle andere programma's. Behalve bij taal C: dan wil iemand bewust Engels.
    eerste="${LANGUAGE#:}"
    eerste="${eerste%%:*}"
    case "$lang" in
    C | C.* | POSIX) ;;
    *) [ -n "$eerste" ] && lang="$eerste" ;;
    esac
    lang="${lang%%.*}"
    lang="${lang%%_*}"
    echo "${lang,,}"
}

# t "Nederlandse tekst" "English text"  -> geeft de juiste taal terug.
# Andere talen komen uit /usr/share/bugos/translations/<taal>.json (Engels -> vertaling).
t() {
    local taal bestand vertaald
    taal="$(bugos_taal)"
    if [ "$taal" = nl ]; then
        echo "$1"
        return
    fi
    bestand="/usr/share/bugos/translations/$taal.json"
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
    # Met een desktop-entry: anders zet KDE het onder 'overig', en dat komt niet in de meldingengeschiedenis (U323).
    notify-send --app-name=BugOS --icon=bugos-logo --hint=string:desktop-entry:bugos-settings "$1" "${2:-}" 2>/dev/null ||
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

# Stroomprofiel (power-saver, balanced, performance). Fedora 44 heeft tuned-ppd: dezelfde dienst
# op D-Bus (net.hadess.PowerProfiles), maar zonder het programma powerprofilesctl. Dus: dat als het
# er is, anders rechtstreeks via D-Bus. Mag zonder wachtwoord voor wie achter de computer zit.
STROOM=(net.hadess.PowerProfiles /net/hadess/PowerProfiles net.hadess.PowerProfiles)
stroomprofiel_get() {
    if command -v powerprofilesctl >/dev/null 2>&1; then
        powerprofilesctl get 2>/dev/null
        return
    fi
    local uit
    uit="$(busctl --system get-property "${STROOM[@]}" ActiveProfile 2>/dev/null)" || return 1
    uit="${uit#s \"}"
    printf '%s\n' "${uit%\"}"
}
stroomprofiel_zet() {
    if command -v powerprofilesctl >/dev/null 2>&1; then
        powerprofilesctl set "$1" 2>/dev/null
        return
    fi
    busctl --system set-property "${STROOM[@]}" ActiveProfile s "$1" 2>/dev/null
}

# Niet storen (geen berichtjes in beeld). Eén plek voor alle scripts;
# Instellingen (bugos_config.py) schrijft precies dezelfde waarde.
NIET_STOREN_TOT="2999,12,31,0,0,0"
niet_storen_aan() {
    kwriteconfig6 --file plasmanotifyrc --group DoNotDisturb --key Until --notify "$NIET_STOREN_TOT" 2>/dev/null
}
niet_storen_uit() {
    kwriteconfig6 --file plasmanotifyrc --group DoNotDisturb --key Until --notify --delete 2>/dev/null
}
# Print "aan" als niet storen aanstaat (er staat een tot-tijd die nog niet voorbij is), anders "uit".
niet_storen_status() {
    # De hele tijd vergelijken, niet alleen de dag: "1 uur niet storen" van vanochtend is vanavond voorbij (U071).
    # KDE schrijft "j,m,d,u,min,sec[.ms][,tijdzone]" of een ISO-tijd.
    niet_storen_tot_status "$(kreadconfig6 --file plasmanotifyrc --group DoNotDisturb --key Until 2>/dev/null)"
}
# Zelfde, voor een 'tot'-waarde die je al hebt (bijv. bewaard door de game-modus).
niet_storen_tot_status() {
    local tot="$1" tot_s nu_s j m d u mi s zone
    if [ -z "$tot" ]; then
        echo uit
        return
    fi
    case "$tot" in
    *,*)
        IFS=, read -r j m d u mi s zone _ <<<"$tot"
        s="${s%%.*}"
        tot="$(printf '%04d-%02d-%02d %02d:%02d:%02d' "$j" "$m" "$d" "${u:-0}" "${mi:-0}" "${s:-0}" 2>/dev/null)" || tot=""
        # Een lege TZ betekent UTC: alleen zetten als KDE er een tijdzone bij schreef.
        if [ -z "$tot" ]; then
            tot_s=""
        elif [ -n "$zone" ]; then
            tot_s="$(TZ="$zone" date -d "$tot" +%s 2>/dev/null)"
        else
            tot_s="$(date -d "$tot" +%s 2>/dev/null)"
        fi
        ;;
    *)
        tot_s="$(date -d "$tot" +%s 2>/dev/null)"
        ;;
    esac
    nu_s="$(date +%s)"
    if [ -n "$tot_s" ] && [ "$tot_s" -gt "$nu_s" ] 2>/dev/null; then echo aan; else echo uit; fi
}

# Plek waar BugOS onthoudt wat de gebruiker heeft gekozen.
# shellcheck disable=SC2034 # wordt gebruikt door de scripts die dit inladen
BUGOS_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/bugos"
