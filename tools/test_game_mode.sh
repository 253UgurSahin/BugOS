#!/usr/bin/bash
# shellcheck disable=SC2016  # de $ in de nep-programma's en controles is bedoeld (wordt later uitgevoerd)
# Test van bugos-game-mode: twee keer 'aan' en dan 'uit' moet alles terugzetten zoals het was.
# Met nep-programma's (powerprofilesctl, systemctl, meldingen): er verandert niets aan je computer.
#
# Gebruik:  bash tools/test_game_mode.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/thuis"
fouten=0
klopt() { if eval "$1"; then echo "OK    $2"; else echo "FOUT  $2"; fouten=$((fouten + 1)); fi; }
nep() { printf '#!/usr/bin/bash\n%s\n' "$2" >"$TMP/bin/$1"; chmod +x "$TMP/bin/$1"; }

sed "s|/usr/share/bugos|$ROOT/system_files/usr/share/bugos|g" "$ROOT/system_files/usr/bin/bugos-game-mode" >"$TMP/spelmodus"
mkdir -p "$TMP/shm"
export BUGOS_GAMER_MAP="$TMP/shm"
# Nep-stroomprofiel: onthoudt de stand in een bestand.
echo balanced >"$TMP/profiel"
nep powerprofilesctl 'case "$1" in get) cat "'"$TMP"'/profiel";; set) echo "$2" >"'"$TMP"'/profiel";; esac'
for p in systemctl notify-send kdialog qdbus qdbus6 gdbus busctl dbus-send; do nep "$p" 'exit 0'; done

draai() { HOME="$TMP/thuis" XDG_CONFIG_HOME="$TMP/thuis/.config" PATH="$TMP/bin:$PATH" bash "$TMP/spelmodus" "$1" >/dev/null 2>&1; }
draai aan
draai aan
draai uit
klopt '[ "$(cat "$TMP/profiel")" = balanced ]' "twee keer aan, dan uit: stroomprofiel weer zoals het was (balanced)"
klopt '[ "$(HOME="$TMP/thuis" XDG_CONFIG_HOME="$TMP/thuis/.config" PATH="$TMP/bin:$PATH" bash "$TMP/spelmodus" status)" = uit ]' "daarna staat game-modus uit"

# B001: zoals op Fedora 44 (tuned-ppd): geen powerprofilesctl, wel de dienst op D-Bus (busctl).
rm -f "$TMP/bin/powerprofilesctl"
echo power-saver >"$TMP/profiel"
nep busctl 'case "$2" in get-property) echo "s \"$(cat "'"$TMP"'/profiel")\"";; set-property) echo "$8" >"'"$TMP"'/profiel";; esac'
if command -v powerprofilesctl >/dev/null 2>&1; then
    echo "OK    (overgeslagen: deze computer heeft zelf powerprofilesctl)"
else
    draai aan
    klopt '[ "$(cat "$TMP/profiel")" = performance ]' "zonder powerprofilesctl: game-modus aan zet via D-Bus volle kracht"
    draai uit
    klopt '[ "$(cat "$TMP/profiel")" = power-saver ]' "zonder powerprofilesctl: uit zet het profiel van daarvoor terug (power-saver)"
fi

# U124: 'niet storen' voor 1 uur, dan game-modus aan en uit: weer 'tot over een uur', niet 'voor altijd'.
# U127: game-modus uit terwijl hij al uit stond: niets veranderen.
nep kreadconfig6 'cat "'"$TMP"'/until" 2>/dev/null'
nep kwriteconfig6 'if [[ " $* " == *" --delete "* ]]; then rm -f "'"$TMP"'/until"; else echo "${!#}" >"'"$TMP"'/until"; fi'
nep powerprofilesctl 'case "$1" in get) cat "'"$TMP"'/profiel";; set) echo "$2" >"'"$TMP"'/profiel";; esac'
straks="$(date -d "+1 hour" +%Y,%-m,%-d,%-H,%-M,0)"
echo "$straks" >"$TMP/until"
echo balanced >"$TMP/profiel"
draai aan
klopt '[ "$(cat "$TMP/until")" = "2999,12,31,0,0,0" ]' "U124: tijdens game-modus: niet storen 'voor altijd'"
draai uit
klopt '[ "$(cat "$TMP/until")" = "$straks" ]' "U124: na game-modus: weer 'niet storen tot over een uur' ($(cat "$TMP/until"))"
# U143: tijdens de game-modus zette je 'niet storen' zelf uit: dan komt het na de game-modus niet terug.
echo "$straks" >"$TMP/until"
draai aan
rm -f "$TMP/until"
draai uit
klopt '[ ! -e "$TMP/until" ]' "U143: 'niet storen' tijdens de game-modus zelf uitgezet: blijft uit na de game-modus"
echo power-saver >"$TMP/profiel"
echo "$straks" >"$TMP/until"
draai uit
klopt '[ "$(cat "$TMP/profiel")" = power-saver ] && [ "$(cat "$TMP/until")" = "$straks" ]' \
    "U127: game-modus uit terwijl hij al uit stond: stroomprofiel en 'niet storen' blijven van jou"
# U385: twee gebruikers (snel wisselen): A aan, B aan, A uit, B uit -> de pc mag niet op volle kracht blijven staan.
if [ -e "$TMP/bin/powerprofilesctl" ] || nep powerprofilesctl 'case "$1" in get) cat "'"$TMP"'/profiel";; set) echo "$2" >"'"$TMP"'/profiel";; esac'; then
    echo balanced >"$TMP/profiel"
    nep id 'if [ "$1" = -u ]; then echo "${NEP_UID:-1000}"; else /usr/bin/id "$@"; fi'
    nep getent 'case "$2" in 1999) exit 2;; *) exit 0;; esac'   # 1999: een account dat niet meer bestaat
    # In de test is alles van root: stat zegt het nummer uit de naam, behalve voor het merkje 'nep' (U435).
    nep stat 'f="${@: -1}"; case "$f" in *bugos-spelmodus-1888) echo 1001;; *bugos-spelmodus-*) echo "${f##*-}";; *) /usr/bin/stat "$@";; esac'
    # shellcheck disable=SC2086  # $2 kan "fps status" zijn (twee woorden)
    gebruiker() { NEP_UID="$3" HOME="$TMP/$1" XDG_CONFIG_HOME="$TMP/$1/.config" PATH="$TMP/bin:$PATH" bash "$TMP/spelmodus" $2 >/dev/null 2>&1; }
    gebruiker anna aan 1001
    gebruiker bram aan 1002
    gebruiker anna uit 1001
    klopt '[ "$(cat "$TMP/profiel")" = performance ]' "U394: anna stopt terwijl bram nog gamet: volle kracht blijft"
    gebruiker bram uit 1002
    klopt '[ "$(cat "$TMP/profiel")" = balanced ]' "U385: twee mensen met game-modus: daarna staat de pc niet voor altijd op volle kracht ($(cat "$TMP/profiel"))"
    # U394: zelf al op volle kracht, dan game-modus aan en uit: jouw volle kracht blijft.
    echo performance >"$TMP/profiel"
    gebruiker carla aan 1003
    gebruiker carla uit 1003
    klopt '[ "$(cat "$TMP/profiel")" = performance ]' "U394: wie zelf 'volle kracht' koos, houdt dat na game-modus uit"    # U404: anna gamet, logt uit (of de pc start opnieuw op): haar merkje blijft, net als haar 'game-modus aan'.
    # Dan is volle kracht niet van dolf, en na zijn game-modus mag het niet voor altijd op volle kracht blijven.
    echo balanced >"$TMP/profiel"
    gebruiker anna aan 1001
    klopt 'grep -q "^GAMER_MAP=\"\${BUGOS_GAMER_MAP:-/var/tmp/bugos-spel}\"" "$TMP/spelmodus" && grep -qx "d /var/tmp/bugos-spel 1777 root root -" "$ROOT/system_files/usr/lib/tmpfiles.d/bugos.conf"' \
        "U404: de merkjes staan niet in /dev/shm (dat wist uitloggen en opnieuw opstarten)"
    rm -f "$BUGOS_GAMER_MAP"/bugos-spelmodus-1001   # oude BugOS: merkje weg, game-modus nog aan
    gebruiker anna "fps status" 1001
    klopt '[ -e "$BUGOS_GAMER_MAP/bugos-spelmodus-1001" ]' "U404: game-modus staat aan maar het merkje is weg: het komt terug"
    gebruiker dolf aan 1004
    gebruiker dolf uit 1004
    gebruiker anna uit 1001
    klopt '[ "$(cat "$TMP/profiel")" = balanced ]' "U404: na anna en dolf staat de pc niet op volle kracht ($(cat "$TMP/profiel"))"
    # U420: een merkje van een gewist account, of van iemand wiens instellingen weg zijn, houdt de pc niet op volle kracht.
    touch "$BUGOS_GAMER_MAP/bugos-spelmodus-1999"
    gebruiker emma aan 1005
    rm -rf "$TMP/emma/.config/bugos"            # emma's instellingen gewist terwijl game-modus aan stond
    gebruiker emma "fps status" 1005
    klopt '[ ! -e "$BUGOS_GAMER_MAP/bugos-spelmodus-1005" ]' "U420: zonder 'game-modus aan' verdwijnt je merkje"
    echo balanced >"$TMP/profiel"
    # U432: 'status' (het snelmenu kijkt steeds) neemt geen merkje weg: dat kan van een 'aan' zijn die nog bezig is.
    touch "$BUGOS_GAMER_MAP/bugos-spelmodus-1007"
    gebruiker gijs status 1007
    klopt '[ -e "$BUGOS_GAMER_MAP/bugos-spelmodus-1007" ]' "U432: 'status' laat het merkje van een 'aan' in uitvoering staan"
    rm -f "$BUGOS_GAMER_MAP/bugos-spelmodus-1007"
    # U435: een nep-merkje (nummer 0, of een bestand dat niet van dat account is) telt niet.
    touch "$BUGOS_GAMER_MAP/bugos-spelmodus-0" "$BUGOS_GAMER_MAP/bugos-spelmodus-1888"
    gebruiker frits aan 1006
    gebruiker frits uit 1006
    klopt '[ "$(cat "$TMP/profiel")" = balanced ]' "U420/U435: merkjes van gewiste accounts, van root of nagemaakt houden de pc niet op volle kracht ($(cat "$TMP/profiel"))"
    rm -f "$BUGOS_GAMER_MAP/bugos-spelmodus-0" "$BUGOS_GAMER_MAP/bugos-spelmodus-1888"
fi
echo "$fouten fout(en)."
[ "$fouten" -eq 0 ]
