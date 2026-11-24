#!/usr/bin/bash
# shellcheck disable=SC2016  # de $ in de nep-programma's en controles is bedoeld (wordt later uitgevoerd)
# Test van bugos-theme licht/donker: snel zichtbaar, het trage deel daarna op de achtergrond, en bij snel
# licht-donker-licht wint de laatste keuze.
# Met nep-programma's (plasma-apply-colorscheme, kreadconfig6, kwriteconfig6, gdbus, wine): er verandert niets aan
# je computer. De nep-programma's schrijven elk wat ze doen, met de tijd, in één logboek.
#
# Gebruik:  bash tools/test_theme.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/thuis/.config" "$TMP/kde" "$TMP/thuis/.local/share/bugos/windows" "$TMP/konsole"
fouten=0
klopt() { if eval "$1"; then echo "OK    $2"; else echo "FOUT  $2"; fouten=$((fouten + 1)); fi; }
nep() { printf '#!/usr/bin/bash\n%s\n' "$2" >"$TMP/bin/$1"; chmod +x "$TMP/bin/$1"; }
K="$TMP/kde"
LOG="$TMP/log"
# Konsole-profielen en Wine-kleuren uit deze map (niet die van de computer).
cp "$ROOT/system_files/usr/share/konsole/BugOS.profile" "$ROOT/system_files/usr/share/konsole/BugOSDark.profile" "$TMP/konsole/"
sed -e "s|/usr/share/bugos|$ROOT/system_files/usr/share/bugos|g" -e "s|/usr/share/konsole|$TMP/konsole|g" \
    "$ROOT/system_files/usr/bin/bugos-theme" >"$TMP/bugos-theme"

# Nep-KDE-instellingen: één bestand per bestand/groep/sleutel.
# (Een volledig pad als bestand, zoals ~/.config/Kvantum/kvantum.kvconfig: de / wordt een _.)
nep kreadconfig6 'f="'"$K"'/${2//\//_}.$4.$6"; [ -f "$f" ] && cat "$f"; exit 0'
nep kwriteconfig6 'echo "$EPOCHREALTIME kwriteconfig6 $*" >>"'"$LOG"'"; f="'"$K"'/${2//\//_}.$4.$6"
if [[ " $* " == *" --delete "* ]]; then rm -f "$f"; else printf "%s" "${!#}" >"$f"; fi'
# Het kleurenschema: op een oudere laptop duurt dit even (NEP_SCHEMA_TIJD).
# NEP_DONKER_TRAAG: donker duurt nog langer (dan zou een oudere keuze voor donker als laatste klaar zijn).
nep plasma-apply-colorscheme 'echo "$EPOCHREALTIME schema-begin $1" >>"'"$LOG"'"; sleep "${NEP_SCHEMA_TIJD:-0}"
[ "$1" = BugOSDark ] && sleep "${NEP_DONKER_TRAAG:-0}"
printf "%s" "$1" >"'"$K"'/kdeglobals.General.ColorScheme"; echo "$EPOCHREALTIME schema-klaar $1" >>"'"$LOG"'"'
nep plasma-apply-desktoptheme 'echo "$EPOCHREALTIME desktoptheme $*" >>"'"$LOG"'"'
nep gdbus 'echo "$EPOCHREALTIME gdbus $*" >>"'"$LOG"'"'
# Wine is traag om op te starten (een paar seconden op een oudere laptop).
nep wine 'echo "$EPOCHREALTIME wine-begin $*" >>"'"$LOG"'"; sleep "${NEP_WINE_TIJD:-0}"; echo "$EPOCHREALTIME wine-klaar" >>"'"$LOG"'"'
nep winepath 'echo "Z:$2"'
printf bugos >"$K/plasmarc.Theme.name"   # al de BugOS-Plasma-stijl: plasma-apply-desktoptheme hoeft niet
printf kvantum >"$K/kdeglobals.KDE.widgetStyle"
printf BugOSLight >"$K/kdeglobals.General.ColorScheme"

# Zoals Instellingen het doet (subprocess.run met capture_output): de uitvoer via een pijp, en wachten tot die dicht is.
# Geeft de afsluitcode in $code en de duur in $duur (seconden).
draai() {
    local begin=$EPOCHREALTIME
    HOME="$TMP/thuis" XDG_CONFIG_HOME="$TMP/thuis/.config" PATH="$TMP/bin:$PATH" LC_ALL=C.UTF-8 \
        bash "$TMP/bugos-theme" "$@" 2>&1 | cat >"$TMP/uit"
    code=${PIPESTATUS[0]}
    duur=$(awk -v a="$begin" -v b="$EPOCHREALTIME" 'BEGIN { printf "%.2f", b - a }')
}
# Los starten (zoals Welkom en het snelmenu): niet wachten.
los() {
    HOME="$TMP/thuis" XDG_CONFIG_HOME="$TMP/thuis/.config" PATH="$TMP/bin:$PATH" LC_ALL=C.UTF-8 \
        bash "$TMP/bugos-theme" "$1" >"$TMP/uit-$2" 2>&1 &
    eval "pid_$2=$!"
}
# Wacht tot er niets meer van bugos-theme loopt (ook niet op de achtergrond), hooguit 10 s.
rustig() {
    local i
    for ((i = 0; i < 100; i++)); do
        pgrep -f "$TMP/bugos-theme" >/dev/null 2>&1 || pgrep -f "$TMP/bin/wine" >/dev/null 2>&1 || return 0
        sleep 0.1
    done
}
tijd() { grep " $1" "$LOG" | head -1 | cut -d" " -f1; }
na() { awk -v a="$(tijd "$1")" -v b="$(tijd "$2")" 'BEGIN { exit !(a != "" && b != "" && b + 0 >= a + 0) }'; }
schema() { cat "$K/kdeglobals.General.ColorScheme"; }
profiel() { cat "$K/konsolerc.Desktop Entry.DefaultProfile" 2>/dev/null; }

# ---- 1. Eén keer omzetten: het zichtbare eerst, het trage deel na het afsluiten ---------------------------------
: >"$LOG"
export NEP_SCHEMA_TIJD=0.3 NEP_WINE_TIJD=3
draai donker
klopt '[ "$code" -eq 0 ] && [ "$(schema)" = BugOSDark ]' "donker: gelukt, het kleurenschema is BugOSDark"
klopt 'awk -v d="$duur" "BEGIN { exit !(d < 1.5) }"' \
    "donker: bugos-theme is klaar in $duur s, ook met een trage Wine (3 s) en via een pijp zoals Instellingen"
klopt '! grep -q "wine-begin" "$LOG" && ! grep -q "konsolerc" "$LOG"' \
    "donker: Wine en de Terminal wachten niet vóór het afsluiten (die doen het daarna, los)"
klopt '[ "$(head -1 "$LOG" | cut -d" " -f2)" = schema-begin ] && na schema-klaar "kwriteconfig6 --file kdeglobals"' \
    "donker: het kleurenschema komt eerst; pas daarna wordt de stijl in kdeglobals geschreven"
klopt 'na "kwriteconfig6 --file kdeglobals --group KDE --key widgetStyle" "gdbus emit" && [ "$(cat "$K/kdeglobals.KDE.widgetStyle")" = kvantum-dark ]' \
    "donker: daarna de stijl (kvantum-dark) en StyleChanged voor open KDE-programma's (A-01)"
rustig
klopt '[ "$(profiel)" = BugOSDark.profile ]' "donker: de Terminal krijgt daarna (op de achtergrond) het donkere profiel"
klopt 'grep -q "wine-begin regedit /S Z:.*donker.reg" "$LOG"' "donker: de Windows-programma's krijgen daarna (op de achtergrond) de donkere kleuren"

# ---- 2. Nog eens Donker: niets opnieuw laten opbouwen -------------------------------------------------------------
: >"$LOG"
NEP_WINE_TIJD=0 draai donker
klopt '[ "$code" -eq 0 ] && ! grep -q "gdbus" "$LOG"' \
    "nog eens donker: geen StyleChanged (alle open programma's hun stijl opnieuw laten opbouwen kost seconden)"
rustig

# ---- 3. Snel licht-donker-licht: de laatste keuze wint -------------------------------------------------------------
: >"$LOG"
export NEP_SCHEMA_TIJD=0.6 NEP_WINE_TIJD=0.3 NEP_DONKER_TRAAG=0.8
los licht a
sleep 0.15
los donker b
sleep 0.15
los licht c
sleep 0.15
los donker d
sleep 0.15
los licht e
wait "$pid_a"; code_a=$?
wait "$pid_b"; code_b=$?
wait "$pid_c"; code_c=$?
wait "$pid_d"; code_d=$?
wait "$pid_e"; code_e=$?
rustig
klopt '[ "$(schema)" = BugOSLight ] && [ "$(cat "$K/kdeglobals.KDE.widgetStyle")" = kvantum ]' \
    "licht-donker-licht-donker-licht: het systeem staat op licht, de laatste keuze ($(schema), $(cat "$K/kdeglobals.KDE.widgetStyle"))"
klopt '[ "$code_a$code_b$code_c$code_d$code_e" = 00000 ]' \
    "snel klikken: geen enkele keuze zegt 'Dat lukte niet' ($code_a$code_b$code_c$code_d$code_e)"
klopt '[ "$(grep -c schema-begin "$LOG")" -le 2 ]' \
    "snel klikken: het kleurenschema hooguit twee keer gezet (die al bezig was en de laatste), niet vijf ($(grep -c schema-begin "$LOG"))"
klopt '[ "$(grep -c schema-begin "$LOG")" -eq "$(grep -c schema-klaar "$LOG")" ] && ! awk "\$2 ~ /schema-/ { if (\$2 == \"schema-begin\" && open) bad = 1; open = (\$2 == \"schema-begin\") } END { exit !bad }" "$LOG"' \
    "snel klikken: nooit twee keer tegelijk het kleurenschema zetten"
klopt '[ "$(grep schema-klaar "$LOG" | tail -1 | cut -d" " -f3)" = BugOSLight ]' "snel klikken: het laatst gezette kleurenschema is dat van de laatste keuze"
klopt '[ "$(profiel)" = BugOS.profile ] && [ "$(grep -c wine-begin "$LOG")" -le 1 ]' \
    "snel klikken: de Terminal volgt de laatste keuze, en Wine start hooguit één keer ($(grep -c wine-begin "$LOG"))"
klopt '[ "$(grep -c "gdbus emit" "$LOG")" -le 2 ]' "snel klikken: StyleChanged hooguit twee keer ($(grep -c "gdbus emit" "$LOG"))"

unset NEP_DONKER_TRAAG

# ---- 4. Een oudere keuze die op het slot wacht, stopt vóór de nieuwste klaar is ------------------------------------
# (Instellingen zet na 'gelukt' zijn eigen kleuren: een oudere die als laatste 'gelukt' zei, gaf het verkeerde thema.)
: >"$LOG"
export NEP_SCHEMA_TIJD=1 NEP_WINE_TIJD=0
los donker f          # bezig (1 s)
sleep 0.2
los licht g           # wacht op f
sleep 0.2
los donker h          # de nieuwste: g is nu overbodig
wait "$pid_g"
g_klaar=$EPOCHREALTIME
wait "$pid_f" "$pid_h"
h_klaar=$EPOCHREALTIME
rustig
klopt 'awk -v g="$g_klaar" -v h="$h_klaar" "BEGIN { exit !(g < h) }" && ! grep -q "schema-begin BugOSLight" "$LOG" && [ "$(schema)" = BugOSDark ]' \
    "een overbodige oudere keuze stopt meteen (zet niets) en is eerder klaar dan de nieuwste"

# ---- 5. Inloggen en een keuze in Welkom tegelijk: de keuze blijft staan ---------------------------------------------
printf BugOSLight >"$K/kdeglobals.General.ColorScheme"
printf kvantum >"$K/kdeglobals.KDE.widgetStyle"
# Een trage eerste keer (plasma-apply-desktoptheme duurt even): intussen kies je Donker in Welkom.
rm -f "$K/plasmarc.Theme.name"
nep plasma-apply-desktoptheme 'echo "$EPOCHREALTIME desktoptheme $*" >>"'"$LOG"'"; sleep 1; printf bugos >"'"$K"'/plasmarc.Theme.name"'
nep flatpak 'exit 0'
: >"$LOG"
export NEP_SCHEMA_TIJD=0.2
los inloggen i
sleep 0.3
los donker j
wait "$pid_i" "$pid_j"
rustig
klopt '[ "$(schema)" = BugOSDark ] && [ "$(cat "$K/kdeglobals.KDE.widgetStyle")" = kvantum-dark ] && [ "$(profiel)" = BugOSDark.profile ]' \
    "inloggen en tegelijk Donker in Welkom: kleuren, stijl en Terminal staan alle drie op donker"

# ---- 6. Lukt het kleurenschema niet, dan zegt bugos-theme dat (U342), en het trage deel blijft weg ------------------
printf BugOSLight >"$K/kdeglobals.General.ColorScheme"
nep plasma-apply-colorscheme 'exit 1'
: >"$LOG"
draai donker
rustig
klopt '[ "$code" -ne 0 ] && ! grep -q wine-begin "$LOG"' "mislukt: afsluitcode niet 0, en geen Wine voor een thema dat er niet is"

# ---- 7. bugos-flatpak-style: wat er al staat, niet nog eens nakijken of installeren --------------------------------
sed "s|/usr/share/bugos|$ROOT/system_files/usr/share/bugos|g" "$ROOT/system_files/usr/bin/bugos-flatpak-style" >"$TMP/fp-stijl"
nep flatpak 'echo "$*" >>"'"$TMP"'/fp-log"; case "$1" in
remotes) echo flathub ;;
list) printf "org.kde.Platform\t6.9\norg.kde.KStyle.Kvantum\t6.9\norg.kde.Platform\t6.8\norg.freedesktop.Platform\t24.08\norg.gtk.Gtk3theme.Breeze\t3.22\n" ;;
esac; exit 0'
: >"$TMP/fp-log"
PATH="$TMP/bin:$PATH" bash "$TMP/fp-stijl" >/dev/null 2>&1
klopt 'grep -q "install .*org.kde.KStyle.Kvantum//6.8" "$TMP/fp-log" && grep -q "install .*VulkanLayer.MangoHud//24.08" "$TMP/fp-log"' \
    "flatpak-stijl: wat nog ontbreekt (Kvantum voor KDE 6.8, MangoHud) wordt geïnstalleerd"
klopt '! grep -q "install .*Kvantum//6.9" "$TMP/fp-log" && ! grep -q "install .*Gtk3theme" "$TMP/fp-log" && ! grep -q "^info" "$TMP/fp-log"' \
    "flatpak-stijl: wat er al staat niet opnieuw, en geen 'flatpak info' per stuk ($(grep -c . "$TMP/fp-log") flatpak-opdrachten)"

echo "$fouten fout(en)."
[ "$fouten" -eq 0 ]
