#!/usr/bin/bash
# shellcheck disable=SC2016  # de $ in de nep-programma's en controles is bedoeld (wordt later uitgevoerd)
# Test van de systeem-scripts (updates, ontwikkelaarsmodus, hulp, lichte stand, game-modus, taal).
# Met nep-programma's (rpm-ostree, flatpak, distrobox, nmcli, ...): er verandert niets aan je computer.
#
# Gebruik:  bash tools/test_os_system.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$ROOT/system_files/usr/bin"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/thuis"
fouten=0
klopt() { if eval "$1"; then echo "OK    $2"; else echo "FOUT  $2"; fouten=$((fouten + 1)); fi; }
nep() { printf '#!/usr/bin/bash\n%s\n' "$2" >"$TMP/bin/$1"; chmod +x "$TMP/bin/$1"; }
# Een script met lib.sh uit deze map (niet die van de computer).
kopie() { sed "s|/usr/share/bugos|$ROOT/system_files/usr/share/bugos|g" "$BIN/$1" >"$TMP/$1"; }
# Draai een gekopieerd script met de nep-programma's, in het Engels (C.UTF-8: die taal is er altijd); geeft de afsluitcode.
draai() {
    local naam="$1"
    shift
    HOME="$TMP/thuis" XDG_CONFIG_HOME="$TMP/thuis/.config" PATH="$TMP/bin:$PATH" LC_ALL=C.UTF-8 \
        bash "$TMP/$naam" "$@" >"$TMP/uit" 2>&1
    code=$?
}
# shellcheck disable=SC2034  # code wordt gelezen in de controles (via eval)
code=0
for p in notify-send kdialog pkexec systemctl; do nep "$p" 'exit 0'; done
nep id 'echo 0'   # doe alsof we beheerder zijn, dan vraagt bugos-updates geen wachtwoord

# U005: "Nu updaten" mag niet "klaar" zeggen als de systeem-update mislukt.
kopie bugos-updates
nep flatpak 'exit 0'
nep rpm-ostree 'exit 1'
draai bugos-updates nu
klopt '[ $code -ne 0 ]' "updates nu: rpm-ostree mislukt -> afsluitcode niet 0"
nep flatpak 'echo flatpak >"'"$TMP"'/flatpak-gedaan"'
draai bugos-updates nu
klopt '[ -f "$TMP/flatpak-gedaan" ]' "updates nu: de apps worden ook dan nog bijgewerkt"
nep rpm-ostree 'exit 0'
nep flatpak 'exit 1'
draai bugos-updates nu
klopt '[ $code -eq 0 ]' "updates nu: rpm-ostree gelukt -> afsluitcode 0 (ook als een app niet lukt)"
nep rpm-ostree 'exit 1'
draai bugos-updates terug
klopt '[ $code -ne 0 ] && ! grep -q Done "$TMP/uit"' "updates terug: rollback mislukt -> afsluitcode niet 0, geen 'Done'"
nep rpm-ostree 'exit 0'
draai bugos-updates terug
klopt '[ $code -eq 0 ] && grep -q Done "$TMP/uit"' "updates terug: rollback gelukt -> 'Done'"

# U033/U034: "terug" zet automatische updates uit (anders komt de nieuwe versie terug), en twee keer
# "terug" gaat niet weer vooruit.
sed -e "s|/usr/share/bugos|$ROOT/system_files/usr/share/bugos|g" -e "s|/etc/bugos|$TMP/etc-bugos|g" \
    "$BIN/bugos-updates" >"$TMP/bugos-updates"
mkdir -p "$TMP/etc-bugos"
echo UPDATES=auto >"$TMP/etc-bugos/updates.conf"
nep systemctl 'echo "$*" >>"'"$TMP"'/systemctl"'
nep rpm-ostree 'case "$1" in status) cat "'"$TMP"'/status.json";; rollback) echo rollback >>"'"$TMP"'/rollback";; esac'
printf '{"deployments":[{"booted":true,"timestamp":2000},{"booted":false,"timestamp":1000}]}' >"$TMP/status.json"
rm -f "$TMP/systemctl" "$TMP/rollback"
draai bugos-updates terug
klopt '[ $code -eq 0 ] && [ -f "$TMP/rollback" ] && grep -qx UPDATES=hand "$TMP/etc-bugos/updates.conf" && grep -q "disable --now rpm-ostreed-automatic.timer" "$TMP/systemctl"' \
    "updates terug (vanzelf): teruggezet, en updates gaan niet meer vanzelf"
klopt 'grep -q "no longer automatic" "$TMP/uit"' "updates terug (vanzelf): zegt dat updates nu uit staan"
printf '{"deployments":[{"booted":false,"timestamp":1000},{"booted":true,"timestamp":2000}]}' >"$TMP/status.json"
rm -f "$TMP/rollback"
draai bugos-updates terug
klopt '[ $code -eq 0 ] && [ ! -f "$TMP/rollback" ] && grep -q "already set" "$TMP/uit"' \
    "updates terug, tweede keer: niet weer vooruit, zegt dat het al klaarstaat"
printf '{"deployments":[{"booted":true,"timestamp":2000},{"booted":false,"timestamp":1000}]}' >"$TMP/status.json"
echo UPDATES=hand >"$TMP/etc-bugos/updates.conf"
rm -f "$TMP/systemctl"
draai bugos-updates terug
klopt '[ ! -f "$TMP/systemctl" ] && ! grep -q "no longer automatic" "$TMP/uit"' "updates terug (zelf updaten): verder niets aangepast"
# U041: geen vorige versie -> zeggen (code 3), niet "mislukt"; "nu" met een al klaarstaande update -> doorgeven.
printf '{"deployments":[{"booted":true,"timestamp":2000}]}' >"$TMP/status.json"
rm -f "$TMP/rollback"
draai bugos-updates terug
klopt '[ $code -eq 3 ] && [ ! -f "$TMP/rollback" ] && grep -q "no older version" "$TMP/uit"' "U041: terug zonder vorige versie: zegt dat (code 3)"
# U044: al teruggegaan en opnieuw opgestart (de oudere draait, de nieuwere staat erna): niet weer vooruit.
printf '{"deployments":[{"booted":true,"timestamp":1000},{"booted":false,"timestamp":2000}]}' >"$TMP/status.json"
rm -f "$TMP/rollback"
draai bugos-updates terug
klopt '[ $code -eq 3 ] && [ ! -f "$TMP/rollback" ] && grep -q "no older version" "$TMP/uit"' \
    "U044: terug terwijl de oudste al draait: niet vooruit naar de nieuwere, zegt dat er geen oudere is"
# U043: er staat een update klaar (staged) voor de volgende keer opstarten: eerst weghalen, dan pas terug.
nep rpm-ostree 'case "$1" in status) cat "'"$TMP"'/status.json";; cleanup) echo "cleanup $*" >>"'"$TMP"'/rollback";;
rollback) grep -q cleanup "'"$TMP"'/rollback" 2>/dev/null || { echo "error: Staged deployment" >&2; exit 1; }; echo rollback >>"'"$TMP"'/rollback";; esac'
printf '{"deployments":[{"booted":false,"staged":true,"timestamp":3000},{"booted":true,"timestamp":2000},{"booted":false,"timestamp":1000}]}' >"$TMP/status.json"
rm -f "$TMP/rollback"
draai bugos-updates terug
klopt '[ $code -eq 0 ] && grep -q "cleanup -p" "$TMP/rollback" && grep -qx rollback "$TMP/rollback"' \
    "U043: terug terwijl er een update op een herstart wacht: die eerst weg, dan wel terug (niet 'mislukt')"
nep rpm-ostree 'case "$1" in status) cat "'"$TMP"'/status.json";; upgrade) echo "No upgrade available.";; esac'
printf '{"deployments":[{"booted":false,"timestamp":3000},{"booted":true,"timestamp":2000}]}' >"$TMP/status.json"
draai bugos-updates nu
klopt '[ $code -eq 0 ] && grep -qx bugos-update-klaar "$TMP/uit"' "U041: nu, terwijl er al een nieuwere versie klaarstaat: dat wordt doorgegeven"
printf '{"deployments":[{"booted":true,"timestamp":2000},{"booted":false,"timestamp":1000}]}' >"$TMP/status.json"
draai bugos-updates nu
klopt '! grep -q bugos-update-klaar "$TMP/uit"' "U041: nu, niets klaar: niets doorgegeven"
# U050: 'terug' gekozen, nog niet opnieuw opgestart, dan toch 'Nu updaten': dat 'terug' wordt eerst ongedaan gemaakt.
nep rpm-ostree 'case "$1" in status) cat "'"$TMP"'/status.json";; rollback) echo rollback >>"'"$TMP"'/rollback";;
upgrade) echo "No upgrade available.";; esac'
printf '{"deployments":[{"booted":false,"timestamp":1000},{"booted":true,"timestamp":2000}]}' >"$TMP/status.json"
rm -f "$TMP/rollback"
draai bugos-updates nu
klopt '[ $code -eq 0 ] && grep -qx rollback "$TMP/rollback"' "U050: Nu updaten na een nog wachtend 'terug': het terug wordt ongedaan gemaakt"
printf '{"deployments":[{"booted":true,"timestamp":2000},{"booted":false,"timestamp":1000}]}' >"$TMP/status.json"
rm -f "$TMP/rollback"
draai bugos-updates nu
klopt '[ ! -f "$TMP/rollback" ]' "U050: gewoon Nu updaten: geen rollback"
# U055: zonder internet (de update lukt niet) blijft het wachtende 'terug' staan.
nep rpm-ostree 'case "$1" in status) cat "'"$TMP"'/status.json";; rollback) echo rollback >>"'"$TMP"'/rollback";;
upgrade) echo "error: no network" >&2; exit 1;; esac'
printf '{"deployments":[{"booted":false,"timestamp":1000},{"booted":true,"timestamp":2000}]}' >"$TMP/status.json"
rm -f "$TMP/rollback"
draai bugos-updates nu
klopt '[ $code -ne 0 ] && [ ! -f "$TMP/rollback" ]' "U055: Nu updaten mislukt (geen internet): het wachtende 'terug' blijft staan"
nep rpm-ostree 'case "$1" in status) cat "'"$TMP"'/status.json";; rollback) echo rollback >>"'"$TMP"'/rollback";;
upgrade) echo "No upgrade available.";; esac'
# Een gewone update die nu pas binnenkomt, is geen "stond al klaar".
nep rpm-ostree 'case "$1" in status) cat "'"$TMP"'/status.json";; upgrade)
printf "{\"deployments\":[{\"booted\":false,\"staged\":true,\"timestamp\":3000},{\"booted\":true,\"timestamp\":2000}]}" >"'"$TMP"'/status.json";; esac'
printf '{"deployments":[{"booted":true,"timestamp":2000}]}' >"$TMP/status.json"
draai bugos-updates nu
klopt '[ $code -eq 0 ] && ! grep -q bugos-update-klaar "$TMP/uit"' "U041: nu, een update die nu pas binnenkomt: gewoon 'klaar', niet 'stond al klaar'"
nep systemctl 'exit 0'
kopie bugos-updates

# U024: na "terug naar de vorige versie" staat de oude versie bovenaan; dat is geen nieuwe update.
kopie bugos-updatecheck
nep bugos-updates 'echo hand'
nep skopeo 'exit 1'
nep notify-send 'echo "$*" >>"'"$TMP"'/meldingen"'
status_json() {  # $1 = tijd van de bovenste versie, $2 = tijd van de versie die nu draait
    printf '{"deployments":[{"booted":false,"timestamp":%s},{"booted":true,"timestamp":%s}]}' "$1" "$2" >"$TMP/status.json"
}
nep rpm-ostree 'cat "'"$TMP"'/status.json"'
status_json 1000 2000   # bovenaan staat de oudere versie (na terug)
rm -f "$TMP/meldingen"
draai bugos-updatecheck
klopt '! grep -q "Update is ready" "$TMP/meldingen" 2>/dev/null' "updatecheck: na terugzetten geen 'Update is ready'"
status_json 3000 2000   # bovenaan staat een nieuwere versie
rm -f "$TMP/meldingen"
draai bugos-updatecheck
klopt 'grep -q "Update is ready" "$TMP/meldingen" 2>/dev/null' "updatecheck: nieuwere versie klaar -> 'Update is ready'"
nep notify-send 'exit 0'
# U178: nog geen internet: niet 'niets aan de hand' (0), maar een fout, zodat systemd het later opnieuw probeert.
printf '{"deployments":[{"booted":true,"timestamp":2000,"container-image-reference":"ostree-image-signed:docker://ghcr.io/x/bugos:latest","container-image-reference-digest":"sha256:aa"}]}' >"$TMP/status.json"
nep skopeo 'exit 1'
draai bugos-updatecheck
klopt '[ "$code" -ne 0 ] && grep -q "^Restart=on-failure" "$ROOT/system_files/usr/lib/systemd/user/bugos-updatecheck.service"' \
    "U178: updatecheck zonder internet: later opnieuw proberen (code $code), niet pas morgen"

# Hulp (bugos-help, Python): één controle draaien met de nep-programma's; print stand en tekst.
# hulp <controle> repareer  -> druk daarna ook op de knop.
hulp() {
    HOME="$TMP/thuis" PATH="$TMP/bin:$PATH" LC_ALL="${HULP_LC_ALL-C.UTF-8}" LANG="${HULP_LANG-}" \
        QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 \
        python3 - "$ROOT" "$@" <<'PY' 2>&1
import importlib.machinery, importlib.util, sys, time
root, naam = sys.argv[1], sys.argv[2]
sys.path.insert(0, root + "/system_files/usr/lib/bugos/python")
lader = importlib.machinery.SourceFileLoader("bugos_help", root + "/system_files/usr/bin/bugos-help")
bh = importlib.util.module_from_spec(importlib.util.spec_from_loader("bugos_help", lader))
lader.exec_module(bh)
u = getattr(bh, naam)()
print(u.stand, u.tekst)
if "repareer" in sys.argv[3:] and u.repareer:  # en druk op de knop
    u.repareer()
    time.sleep(1)
PY
}
status_json 1000 2000
klopt '[[ "$(hulp controle_updates)" == ok* ]]' "hulp: na terugzetten staat er geen update klaar"
status_json 3000 2000
klopt '[[ "$(hulp controle_updates)" == let_op* ]]' "hulp: nieuwere versie klaar -> 'An update is ready'"

# U007: ontwikkelaarsmodus mag niet AAN zeggen als het klaarzetten mislukt (bijv. geen internet).
kopie bugos-developer
nep flatpak 'exit 1'
nep distrobox 'case "$1" in list) exit 0;; *) exit 1;; esac'
nep kdialog 'echo "$*" >>"'"$TMP"'/vensters"'
draai bugos-developer aan
klopt '[ $code -ne 0 ] && [ "$(HOME="$TMP/thuis" XDG_CONFIG_HOME="$TMP/thuis/.config" bash "$TMP/bugos-developer" status)" = uit ]' \
    "ontwikkelaar: alles mislukt -> afsluitcode niet 0 en status uit"
klopt 'grep -qi "online" "$TMP/vensters" 2>/dev/null' "ontwikkelaar: mislukt -> uitleg 'Are you online?'"
nep flatpak 'exit 0'
draai bugos-developer aan
klopt '[ $code -ne 0 ] && [ ! -e "$TMP/thuis/.config/bugos/ontwikkelaar-aan" ]' "ontwikkelaar: dev-doosje mislukt -> niet aan"
nep distrobox 'case "$1" in list) exit 0;; enter) exit 1;; *) exit 0;; esac'
draai bugos-developer aan
klopt '[ $code -ne 0 ] && [ ! -e "$TMP/thuis/.config/bugos/ontwikkelaar-aan" ]' "ontwikkelaar: doosje binnengaan mislukt -> niet aan"
nep distrobox 'exit 0'
draai bugos-developer aan
klopt '[ $code -eq 0 ] && [ -e "$TMP/thuis/.config/bugos/ontwikkelaar-aan" ]' "ontwikkelaar: alles gelukt -> aan"
nep kdialog 'exit 0'

# U018: qdbus6 bestaat niet op Fedora 44. Herstarten (Hulp) en KWin herladen (lichte stand) gaan via gdbus.
nep gdbus 'echo "$*" >>"'"$TMP"'/dbus"'
rm -f "$TMP/dbus"
status_json 3000 2000
hulp controle_updates repareer >/dev/null
klopt 'grep -q "org.kde.LogoutPrompt.promptReboot" "$TMP/dbus" 2>/dev/null' "hulp: 'Nu herstarten' vraagt echt om te herstarten (gdbus)"
kopie bugos-light-mode
for p in kreadconfig6 kwriteconfig6 balooctl6; do nep "$p" 'exit 0'; done
rm -f "$TMP/dbus"
draai bugos-light-mode aan
klopt '[ "$(grep -c "org.kde.KWin.reconfigure" "$TMP/dbus" 2>/dev/null)" = 1 ]' "lichte stand aan: KWin wordt herladen (gdbus)"
rm -f "$TMP/dbus"
draai bugos-light-mode uit
klopt '[ "$(grep -c "org.kde.KWin.reconfigure" "$TMP/dbus" 2>/dev/null)" = 1 ]' "lichte stand uit: KWin wordt herladen (gdbus)"

# U008: Hulp leest wat nmcli zegt; in het Nederlands zegt nmcli "ingeschakeld" i.p.v. "enabled".
# Nep-nmcli praat Nederlands, behalve als LC_ALL=C (zoals echte programma's).
nep nmcli 'nl() { [ "${LC_ALL:-}" != C ]; }
case "$*" in
"-t -f TYPE device") echo wifi ;;
"radio wifi") if nl; then echo ingeschakeld; else echo enabled; fi ;;
"-t -f WIFI radio") if nl; then echo ingeschakeld; else echo enabled; fi ;;
esac'
klopt '[[ "$(HULP_LC_ALL="" HULP_LANG=nl_NL.UTF-8 hulp controle_wifi)" == ok* ]]' "hulp in het Nederlands: wifi die aan staat heet 'aan'"

# U022: KDE zet de gekozen taal in LANGUAGE (bijv. "nl:en_US"); BugOS moet die volgen (bash en Python).
taal_sh() { env -i PATH="$PATH" "$@" bash -c '. "$1/system_files/usr/share/bugos/lib.sh"; bugos_taal' _ "$ROOT"; }
taal_py() {
    env -i PATH="$PATH" PYTHONDONTWRITEBYTECODE=1 "$@" python3 -c \
        'import sys; sys.path.insert(0, sys.argv[1]); import bugos_base; print(bugos_base.TAAL)' \
        "$ROOT/system_files/usr/lib/bugos/python"
}
for soort in sh py; do
    klopt '[ "$(taal_$soort LANGUAGE=nl:en_US LANG=en_US.UTF-8)" = nl ]' "taal ($soort): KDE in het Nederlands (LANGUAGE=nl:en_US) -> nl"
    klopt '[ "$(taal_$soort LANGUAGE=en_US LANG=nl_NL.UTF-8)" = en ]' "taal ($soort): KDE in het Engels op een Nederlandse computer -> en"
    klopt '[ "$(taal_$soort LANG=nl_NL.UTF-8)" = nl ]' "taal ($soort): zonder LANGUAGE geldt LANG"
    klopt '[ "$(taal_$soort LANGUAGE=nl LC_ALL=C)" != nl ]' "taal ($soort): LC_ALL=C blijft Engels (zoals bij gettext)"
done

# U023: een gewone pc met 6 GB (Linux ziet daar zo'n 5,6-5,8 GB van) is niet "oud of traag".
kopie bugos-light-mode
sed -i "s|/proc/meminfo|$TMP/meminfo|" "$TMP/bugos-light-mode"
nep nproc 'echo 4'
licht_auto() {  # $1 = MemTotal in kB; print aan/uit
    printf 'MemTotal:       %s kB\n' "$1" >"$TMP/meminfo"
    rm -rf "$TMP/thuis/.config/bugos"
    draai bugos-light-mode auto
    draai bugos-light-mode status
    cat "$TMP/uit"
}
klopt '[ "$(licht_auto 5800000)" = uit ]' "lichte stand: 6 GB-pc (5,8 GB zichtbaar) -> niet vanzelf aan"
klopt '[ "$(licht_auto 7600000)" = uit ]' "lichte stand: 8 GB-pc -> niet vanzelf aan"
klopt '[ "$(licht_auto 3800000)" = aan ]' "lichte stand: 4 GB-pc -> wel vanzelf aan"
rm -f "$TMP/bin/nproc"

# U017: de FPS-teller (MANGOHUD=1) komt pas in games na opnieuw inloggen; game-modus moet dat eerlijk zeggen.
kopie bugos-game-mode
nep powerprofilesctl 'echo balanced'
nep notify-send 'echo "$*" >>"'"$TMP"'/meldingen"'
rm -rf "$TMP/thuis/.config/bugos" "$TMP/meldingen"
draai bugos-game-mode aan
klopt 'grep -q "log in again" "$TMP/meldingen"' "game-modus aan: zegt dat de FPS-teller na opnieuw inloggen komt"
rm -f "$TMP/meldingen"
MANGOHUD=1 draai bugos-game-mode uit
klopt 'grep -q "log in again" "$TMP/meldingen"' "game-modus uit: zegt dat de FPS-teller na opnieuw inloggen weggaat"
rm -f "$TMP/meldingen"
MANGOHUD=1 draai bugos-game-mode aan
klopt '! grep -q "log in again" "$TMP/meldingen"' "game-modus aan terwijl MangoHud al meedraait: niets over inloggen"
rm -f "$TMP/meldingen"
draai bugos-game-mode uit
klopt '! grep -q "log in again" "$TMP/meldingen"' "game-modus uit zonder FPS-teller in deze sessie: niets over inloggen"

# FPS-teller meteen klaar (instelbaar): MangoHud altijd klaar met ons eigen bestand; game-modus zet hem zichtbaar/verborgen.
CF="$TMP/thuis/.config"
MHC="$CF/bugos/mangohud.conf"
rm -rf "$CF/bugos" "$CF/environment.d" "$TMP/meldingen"
draai bugos-game-mode fps status
klopt 'grep -qx uit "$TMP/uit"' "fps meteen: staat standaard uit"
draai bugos-game-mode fps aan
klopt 'grep -qx "MANGOHUD=1" "$CF/environment.d/80-bugos-mangohud.conf" && grep -qx "MANGOHUD_CONFIGFILE=$MHC" "$CF/environment.d/80-bugos-mangohud.conf"' \
    "fps meteen aan: MangoHud altijd klaar, met het BugOS-bestand"
klopt 'grep -qx no_display "$MHC"' "fps meteen aan, game-modus uit: de teller is verborgen"
klopt 'grep -q "Log in again once" "$TMP/meldingen"' "fps meteen aan: zegt dat het na één keer opnieuw inloggen werkt"
draai bugos-game-mode fps status
klopt 'grep -qx aan "$TMP/uit"' "fps meteen: status aan"
rm -f "$TMP/meldingen"
MANGOHUD=1 MANGOHUD_CONFIGFILE="$MHC" draai bugos-game-mode aan
klopt '! grep -q no_display "$MHC" && [ ! -f "$CF/environment.d/90-bugos-game-mode.conf" ]' "fps meteen + game-modus aan: de teller is meteen zichtbaar"
klopt '! grep -q "log in again" "$TMP/meldingen"' "fps meteen + game-modus aan: niets over opnieuw inloggen"
rm -f "$TMP/meldingen"
MANGOHUD=1 MANGOHUD_CONFIGFILE="$MHC" draai bugos-game-mode uit
klopt 'grep -qx no_display "$MHC" && grep -qx MANGOHUD=1 "$CF/environment.d/80-bugos-mangohud.conf"' \
    "fps meteen + game-modus uit: meteen verborgen, MangoHud blijft klaar"
klopt '! grep -q "log in again" "$TMP/meldingen"' "fps meteen + game-modus uit: niets over opnieuw inloggen"
# U032: de keuze uitzetten terwijl deze sessie ons bestand nog gebruikt: niet weggooien (anders de volle teller).
MANGOHUD=1 MANGOHUD_CONFIGFILE="$MHC" draai bugos-game-mode fps uit
klopt 'grep -qx no_display "$MHC" && [ ! -f "$CF/environment.d/80-bugos-mangohud.conf" ]' \
    "U032: fps meteen uit in een sessie die het gebruikt: teller blijft verborgen tot opnieuw inloggen"
# U049: in diezelfde sessie (leest ons bestand nog) game-modus aan en uit: de teller gaat echt aan en weer uit.
rm -f "$TMP/meldingen"
MANGOHUD=1 MANGOHUD_CONFIGFILE="$MHC" draai bugos-game-mode aan
klopt '! grep -q no_display "$MHC"' "U049: keuze net uit, zelfde sessie, game-modus aan: de teller is echt zichtbaar"
MANGOHUD=1 MANGOHUD_CONFIGFILE="$MHC" draai bugos-game-mode uit
klopt 'grep -qx no_display "$MHC"' "U049: ... en game-modus uit: meteen weer verborgen"
# U054: ingelogd met game-modus aan (MANGOHUD=1, maar niet ons bestand), dan de keuze aan, dan game-modus uit:
# dat de teller pas na opnieuw inloggen weggaat, moet erbij staan.
draai bugos-game-mode fps aan
MANGOHUD=1 draai bugos-game-mode aan
rm -f "$TMP/meldingen"
MANGOHUD=1 draai bugos-game-mode uit
klopt 'grep -q "goes away after you log in again" "$TMP/meldingen" && grep -qx no_display "$MHC"' \
    "U054: game-modus uit in een sessie zonder ons bestand: zegt 'na opnieuw inloggen', bestand klaar voor de volgende keer"
draai bugos-game-mode fps uit
# U035: je eigen MangoHud.conf (indeling) gaat mee in ons bestand.
mkdir -p "$CF/MangoHud"
printf 'fps_only\nposition=top-right\n' >"$CF/MangoHud/MangoHud.conf"
draai bugos-game-mode fps aan
klopt 'grep -qx fps_only "$MHC" && grep -qx "position=top-right" "$MHC" && grep -qx no_display "$MHC"' \
    "U035: fps meteen: je eigen MangoHud-indeling gaat mee (en verborgen als game-modus uit staat)"
MANGOHUD=1 MANGOHUD_CONFIGFILE="$MHC" draai bugos-game-mode aan
klopt 'grep -qx fps_only "$MHC" && ! grep -q no_display "$MHC"' "U035: game-modus aan: je eigen indeling, zichtbaar"
MANGOHUD=1 MANGOHUD_CONFIGFILE="$MHC" draai bugos-game-mode uit
rm -rf "$CF/MangoHud"
draai bugos-game-mode aan
draai bugos-game-mode fps uit
klopt '[ ! -f "$MHC" ] && [ ! -f "$CF/environment.d/80-bugos-mangohud.conf" ] && grep -qx MANGOHUD=1 "$CF/environment.d/90-bugos-game-mode.conf"' \
    "fps meteen uit terwijl game-modus aan staat: terug naar de gewone manier (na opnieuw inloggen)"
draai bugos-game-mode uit
klopt '[ ! -f "$CF/environment.d/90-bugos-game-mode.conf" ]' "daarna game-modus uit: niets van MangoHud blijft staan"
nep notify-send 'exit 0'

# Diensten (systemd). Met systemd-analyze (als dat er is) kijken we of systemd ze kan lezen.
SD="$ROOT/system_files/usr/lib/systemd"
sd_goed() {  # geen klachten behalve "programma bestaat hier niet" (dat komt pas in BugOS zelf)
    command -v systemd-analyze >/dev/null 2>&1 || return 0
    # IPv6, lookup, initialize, connect: meldingen van een container zonder echte systemd, geen fouten in de dienst.
    ! systemd-analyze verify --man=no "$@" 2>&1 |
        grep -v -E "is not executable|IPv6|Failed to (lookup|initialize|connect|open)|not running" | grep -q .
}
# U020: zonder internet mag de eerste start de computer niet in "bezig met opstarten" houden.
klopt '! grep -q "^Type=oneshot" "$SD/system/bugos-first-boot.service"' \
    "eerste start: geen oneshot (het opstarten wacht dan op het downloaden en opnieuw proberen)"
klopt 'grep -q "^Restart=on-failure" "$SD/system/bugos-first-boot.service"' "eerste start: probeert het later opnieuw"
klopt 'sd_goed "$SD/system/bugos-first-boot.service"' "eerste start: systemd kan de dienst lezen"
# U021: elke dag op de klok, ook op laptops die slapen (een dag "na de vorige keer" telt niet door in slaap).
for klok in "$SD/system/bugos-update-apps.timer" "$SD/user/bugos-updatecheck.timer"; do
    naam="$(basename "$klok")"
    klopt 'grep -q "^OnCalendar=daily" "$klok" && grep -q "^Persistent=true" "$klok" &&
        ! grep -qE "^OnUnit(In)?[Aa]ctiveSec=" "$klok"' "$naam: elke dag op de klok, en inhalen als hij gemist is"
    klopt 'sd_goed "$klok" "${klok%.timer}.service"' "$naam: systemd kan hem lezen"
done

# U071: "niet storen" van vanochtend (1 uur) is vanavond voorbij: de hele tijd vergelijken, niet alleen de dag.
# shellcheck source=system_files/usr/share/bugos/lib.sh
. "$ROOT/system_files/usr/share/bugos/lib.sh"
dnd() { nep kreadconfig6 "echo '$1'"; PATH="$TMP/bin:$PATH" niet_storen_status; }
klopt '[ "$(dnd "$(date -d "-10 min" +%Y,%-m,%-d,%-H,%-M,7.913)")" = uit ]' "U071: niet storen dat 10 minuten geleden afliep: uit"
klopt '[ "$(dnd "$(date -d "+10 min" +%Y,%-m,%-d,%-H,%-M,7.913)")" = aan ]' "U071: niet storen tot over 10 minuten: aan"
klopt '[ "$(dnd "$(date -u -d "+2 hour" +%Y,%-m,%-d,%-H,%-M,12),UTC")" = aan ] && [ "$(dnd "$(date -u -d "-2 hour" +%Y,%-m,%-d,%-H,%-M,12),UTC")" = uit ]' \
    "U071: met een tijdzone erachter (zoals KDE dat soms schrijft)"
klopt '[ "$(dnd 2999,12,31,0,0,0)" = aan ] && [ "$(dnd "")" = uit ] && [ "$(dnd onzin)" = uit ] && [ "$(dnd 2999-01-01T00:00:00)" = aan ]' \
    "U071: spelmodus (2999), leeg, onzin en ISO-tijd"
# U089: app-updates niet over een verbinding met een databundel (Metered 1 of 3); anders wel, ook zonder NetworkManager.
# Zoals systemd hem draait: $$ wordt $.
voorwaarde="$(sed -n 's/^ExecCondition=//p' "$ROOT/system_files/usr/lib/systemd/system/bugos-update-apps.service")"
voorwaarde="${voorwaarde//\$\$/\$}"
gemeten() { nep busctl "$1"; PATH="$TMP/bin:$PATH" eval "$voorwaarde"; }
klopt '! gemeten "echo \"u 1\"" && ! gemeten "echo \"u 3\""' "U089: app-updates slaan een hotspot (Metered ja/vermoedelijk ja) over"
klopt 'gemeten "echo \"u 2\"" && gemeten "echo \"u 4\"" && gemeten "echo \"u 0\"" && gemeten "exit 1"' \
    "U089: app-updates gaan door bij wifi/kabel, onbekend, of zonder NetworkManager"
klopt 'grep -q "flatpak-system-update.timer" "$ROOT/build_files/system.sh"' "U087: de bouw zet Universal Blue's eigen app-updates uit"
klopt '! grep -q "^ *systemctl --global mask flatpak-user-update" "$ROOT/build_files/system.sh"' \
    "U117: de bouw zet de app-updates per gebruiker niet voor altijd uit"
# U117: 'Updates vanzelf' aan/uit zet ook de app-updates per gebruiker aan/uit (niet voor altijd uit in de bouw).
mkdir -p "$TMP/user-units"
touch "$TMP/user-units/flatpak-user-update.timer"
kopie bugos-updates
nep systemctl 'echo "$*" >>"'"$TMP"'/systemctl-log"'
: >"$TMP/systemctl-log"
BUGOS_SYSTEMD_USER="$TMP/user-units" draai bugos-updates hand
klopt 'grep -q -- "--global mask flatpak-user-update.timer" "$TMP/systemctl-log"' "U117: zelf updaten: ook de app-updates per gebruiker uit"
: >"$TMP/systemctl-log"
BUGOS_SYSTEMD_USER="$TMP/user-units" draai bugos-updates auto
klopt 'grep -q -- "--global unmask flatpak-user-update.timer" "$TMP/systemctl-log"' "U117: updates vanzelf: de app-updates per gebruiker weer aan"
nep systemctl 'exit 0'
# U132: licht/donker wisselen geeft ook geïnstalleerde Windows-programma's de nieuwe kleuren.
kopie bugos-theme
for p in plasma-apply-desktoptheme kwriteconfig6; do nep "$p" 'exit 0'; done
# Het kleurenschema onthouden, zodat bugos-theme kan zien wat er nu aan staat (U169).
nep plasma-apply-colorscheme 'echo "$1" >"'"$TMP"'/schema"'
nep kreadconfig6 'case "$*" in *ColorScheme*) cat "'"$TMP"'/schema" 2>/dev/null ;; esac'
nep wine 'echo "$*" >>"'"$TMP"'/wine-log"'
nep winepath 'echo "Z:$2"'
mkdir -p "$TMP/thuis/.local/share/bugos/windows"
: >"$TMP/wine-log"
draai bugos-theme donker
for _ in 1 2 3 4 5 6 7 8 9 10; do [ -s "$TMP/thuis/.local/share/bugos/windows/.bugos-kleuren" ] && break; sleep 0.2; done
klopt 'grep -q "regedit /S Z:.*donker.reg" "$TMP/wine-log" && grep -q "^donker " "$TMP/thuis/.local/share/bugos/windows/.bugos-kleuren"' \
    "U132: donker: ook de Windows-programma's krijgen de donkere kleuren ($(cat "$TMP/wine-log" "$TMP/uit" 2>&1 | head -3 | tr "\n" " "))"
# U169: intussen alweer teruggezet (snel licht-donker-licht): de oude keuze zet de Windows-kleuren niet meer.
nep plasma-apply-colorscheme 'echo BugOSLight >"'"$TMP"'/schema"'
: >"$TMP/wine-log"
draai bugos-theme donker
sleep 1
klopt '[ ! -s "$TMP/wine-log" ]' "U169: een oudere licht/donker-keuze zet de Windows-kleuren niet meer"
nep plasma-apply-colorscheme 'echo "$1" >"'"$TMP"'/schema"'
# U148: na een nieuwe Wine-versie (de map is nog niet bijgewerkt) niet bij licht/donker Wine starten (dat toont een venster).
echo 1 >"$TMP/thuis/.local/share/bugos/windows/.update-timestamp"
: >"$TMP/wine-log"
rm -f "$TMP/thuis/.local/share/bugos/windows/.bugos-kleuren"
if [ -f /usr/share/wine/wine.inf ]; then
    draai bugos-theme licht
    sleep 1
    klopt '[ ! -s "$TMP/wine-log" ]' "U148: nieuwe Wine-versie: niet bij licht/donker bijwerken (dat doet het openen van een programma)"
fi
rm -f "$TMP/thuis/.local/share/bugos/windows/.update-timestamp"
nep wine 'exit 0'
echo "$fouten fout(en)."
[ "$fouten" -eq 0 ]
