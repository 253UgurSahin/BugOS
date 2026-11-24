#!/usr/bin/bash
# shellcheck disable=SC2016  # het blok voor dbus-run-session staat bewust tussen enkele aanhalingstekens
# Test van bugos-shell (het echte C++-programma) op een eigen, tijdelijke D-Bus (dbus-run-session):
#  - de meldingendienst (org.freedesktop.Notifications): servergegevens, een melding, sluiten, en 'niet storen';
#  - de Meta-toets: KWin roept org.kde.plasmashell /PlasmaShell activateLauncherMenu aan, en dat lukt.
# Er verandert niets aan je computer: een eigen sessiebus, een eigen tijdelijke configuratiemap.
#
#  - het systeemvak (fase 2): systeemvak-test naast bugos-shell (cmake -DBUGOS_TESTS=ON) speelt twee apps met een
#    pictogram en een menu na, op dezelfde soort eigen bus.
#
# Gebruik:  bash tools/test_shell_dbus.sh <pad naar bugos-shell>
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BIN="$(realpath "${1:?pad naar bugos-shell}")"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
export ROOT BIN TMP

dbus-run-session -- bash -c '
fouten=0
klopt() { if eval "$1"; then echo "OK    $2"; else echo "FOUT  $2"; fouten=$((fouten + 1)); fi; }
mkdir -p "$TMP/config"
export XDG_CONFIG_HOME="$TMP/config" QT_QPA_PLATFORM=offscreen
export BUGOS_ACHTERGROND_PAKKET="$ROOT/system_files/usr/share/wallpapers/bugos"
"$BIN" --qml "$ROOT/system_files/usr/share/bugos/shell/Shell.qml" --stop-na 8000 >"$TMP/uit" 2>"$TMP/fout" &
pid=$!
for _ in $(seq 100); do
    gdbus call --session --dest org.freedesktop.DBus --object-path /org/freedesktop/DBus \
        --method org.freedesktop.DBus.NameHasOwner org.kde.plasmashell 2>/dev/null | grep -q true && break
    sleep 0.05
done
N="gdbus call --session --dest org.freedesktop.Notifications --object-path /org/freedesktop/Notifications"
klopt "$N --method org.freedesktop.Notifications.GetServerInformation | grep -q BugOS" "meldingen: de dienst is van bugos-shell"
klopt "$N --method org.freedesktop.Notifications.GetCapabilities | grep -q actions" "meldingen: knoppen op een melding kunnen"
gdbus monitor --session --dest org.freedesktop.Notifications >"$TMP/monitor" 2>&1 &
mon=$!
sleep 0.3
id="$($N --method org.freedesktop.Notifications.Notify test 0 "" Kop Tekst "[]" "{}" 5000 | sed -n "s/.*uint32 \([0-9]*\).*/\1/p")"
klopt "[ \"\$id\" -ge 1 ]" "meldingen: Notify geeft een nummer ($id)"
id2="$($N --method org.freedesktop.Notifications.Notify test "$id" "" Kop2 Tekst "[]" "{}" 5000 | sed -n "s/.*uint32 \([0-9]*\).*/\1/p")"
klopt "[ \"\$id2\" = \"\$id\" ]" "meldingen: replaces_id vervangt dezelfde melding"
$N --method org.freedesktop.Notifications.CloseNotification "$id" >/dev/null
# Niet storen (snelmenu): geen kaartje, de app hoort meteen dat de melding vervallen is.
printf "[DoNotDisturb]\nUntil=2999,12,31,0,0,0\n" >"$XDG_CONFIG_HOME/plasmanotifyrc"
id3="$($N --method org.freedesktop.Notifications.Notify test 0 "" Stil Tekst "[]" "{}" 5000 | sed -n "s/.*uint32 \([0-9]*\).*/\1/p")"
sleep 0.5
kill "$mon" 2>/dev/null
klopt "grep -q \"NotificationClosed (uint32 \$id, uint32 3)\" \"\$TMP/monitor\"" "meldingen: CloseNotification sluit hem (reden 3)"
klopt "grep -q \"NotificationClosed (uint32 \$id3, uint32 1)\" \"\$TMP/monitor\"" "meldingen: niet storen: geen kaartje, meteen vervallen"
klopt "gdbus call --session --dest org.kde.plasmashell --object-path /PlasmaShell --method org.kde.PlasmaShell.activateLauncherMenu >/dev/null" \
    "de Meta-toets: activateLauncherMenu werkt"
wait "$pid"
code=$?
klopt "[ $code -eq 0 ] && grep -q \"bugos-shell: OK\" \"\$TMP/uit\"" "bugos-shell liep en stopte netjes (code $code)"
if [ "$fouten" -ne 0 ]; then
    echo "--- stderr van bugos-shell:"
    grep -v "image://icon\|Takenlijst.qml\|taskmanager" "$TMP/fout" | head -20
fi
echo "$fouten fout(en)."
[ "$fouten" -eq 0 ]
'

VAK="$(dirname "$BIN")/systeemvak-test"
if [ -x "$VAK" ]; then
    echo "--- het systeemvak (systeemvak-test)"
    dbus-run-session -- "$VAK" 2>&1 | grep -v "fd limit\|XDG_RUNTIME_DIR"
    [ "${PIPESTATUS[0]}" -eq 0 ] || exit 1
else
    echo "(geen systeemvak-test naast bugos-shell: bouw met cmake -DBUGOS_TESTS=ON)"
fi
