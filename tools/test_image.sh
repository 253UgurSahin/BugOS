#!/usr/bin/bash
# shellcheck disable=SC2016,SC2034  # klopt() voert de controle zelf uit (eval): de $ zijn bedoeld
# Test van het gebouwde BugOS-beeld: draait IN het beeld (niet op je eigen computer).
# Kijkt of de bouw (build.sh, system.sh, style.sh) alles goed heeft neergezet: naam, rechten,
# app-pictogrammen, diensten, instellingen, en of elk BugOS-programma en menu echt laadt
# met de Qt, KDE en Python van Fedora zelf.
#
# Gebruik:  podman run --rm -v "$PWD:/repo:ro" <beeld> bash /repo/tools/test_image.sh
set -u
fouten=0
ok() { echo "OK    $1"; }
fout() { echo "FOUT  $1"; fouten=$((fouten + 1)); }
klopt() { if eval "$1"; then ok "$2"; else fout "$2"; fi; }
REPO="${REPO:-/repo}"

# 1. BugOS is een eigen systeem (system.sh)
# shellcheck source=/dev/null
. /usr/lib/os-release
klopt '[ "$ID" = bugos ] && [ "$NAME" = BugOS ] && [[ "$ID_LIKE" == *fedora* ]]' "os-release: ID=bugos, NAME=BugOS, lijkt op fedora ($PRETTY_NAME)"
klopt '[ -n "${VARIANT_ID:-}" ] && [ -n "${VERSION_ID:-}" ]' "os-release: VARIANT_ID=${VARIANT_ID:-} en VERSION_ID=${VERSION_ID:-} gezet"
klopt '[ -s /usr/share/icons/hicolor/scalable/apps/bugos-logo.svg ] && [ -s /usr/share/pixmaps/bugos-logo.svg ]' "logo: bugos-logo staat in hicolor en pixmaps"
klopt 'grep -q "\"image-name\"" /usr/share/ublue-os/image-info.json' "image-info.json: geschreven"

# 1b. Elk bestand uit system_files staat er precies zo in (build.sh, stap 1). Een lokale bouw liet ooit bestanden die
#     al in de fundering stonden half staan: de oude inhoud met nul-bytes erachter. Alleen bestanden die de bouw
#     daarna niet zelf nog aanpast (AANGEPAST: de vooraf vertaalde Python-bestanden).
AANGEPAST='^usr/lib/bugos/python/__pycache__/'
anders=""
if [ -d "$REPO/system_files" ]; then
    while IFS= read -r -d '' f; do
        rel="${f#"$REPO"/system_files/}"
        [[ "$rel" =~ $AANGEPAST ]] && continue
        cmp -s "$f" "/$rel" || anders="$anders /$rel"
    done < <(find "$REPO/system_files" -type f -print0)
fi
klopt '[ -z "$anders" ]' "bestanden: alles uit system_files staat er ongeschonden in${anders:0:300}"

# 1c. Ook wat de bouw zelf schrijft (cat >, printf >, kwriteconfig6) moet heel zijn. In een lokale bouw met
#     fuse-overlayfs bleef van bestanden die al in de fundering stonden alleen de oude inhoud over, aangevuld met
#     nul-bytes tot de nieuwe lengte (/usr/lib/plasmalogin/defaults.conf: inlogscherm met de achtergrond van KDE;
#     /etc/xdg/kcm-about-distrorc: 'Over deze computer'). Zo'n tekstbestand eindigt op nul-bytes: dat mag nergens
#     in /etc of in de mappen waar de bouw schrijft. (/etc/selinux heeft echte binaire bestanden met nullen.)
kapot="$(python3 - <<'EOF'
import os
plekken = ["/etc", "/usr/lib/plasmalogin", "/usr/share/kde-settings", "/usr/share/plasma/look-and-feel",
           "/usr/share/plasma/shells", "/usr/share/sddm", "/usr/share/bugos"]
kapot = []
for plek in plekken:
    for map_, mappen, bestanden in os.walk(plek):
        mappen[:] = [m for m in mappen if os.path.join(map_, m) != "/etc/selinux"]
        for b in bestanden:
            p = os.path.join(map_, b)
            try:
                if os.path.islink(p) or not 0 < os.path.getsize(p) < 2_000_000:
                    continue
                with open(p, "rb") as h:
                    data = h.read()
            except OSError:
                continue
            # Tekst (geen nul-byte in het begin) met nul-bytes aan het eind: de oude inhoud, opgevuld.
            romp = data.rstrip(b"\0")
            if romp != data and romp and b"\0" not in romp:
                kapot.append(p)
print(" ".join(kapot[:10]))
EOF
)"
klopt '[ -z "$kapot" ]' "bestanden: geen tekstbestand dat eindigt op nul-bytes (half geschreven) ${kapot}"

# 2. Rechten (build.sh): programma's uitvoerbaar, de rest niet, geen wereld-schrijfbare bestanden
slecht="$(find /usr/bin -maxdepth 1 -name 'bugos-*' ! -perm 0755 | head -5)"
klopt '[ -z "$slecht" ]' "rechten: elk /usr/bin/bugos-* is 0755 ${slecht}"
slecht="$(find /usr/lib/bugos /usr/share/bugos /usr/lib/systemd/system/bugos-* /usr/lib/systemd/user/bugos-* -perm -o+w 2>/dev/null | head -5)"
klopt '[ -z "$slecht" ]' "rechten: niets van BugOS is door iedereen te veranderen ${slecht}"

# 3. App-starters en hun pictogrammen
for d in /usr/share/applications/bugos-*.desktop; do
    uit="$(desktop-file-validate "$d" 2>&1 | grep -v -i 'hint:' || true)"
    klopt '[ -z "$uit" ]' "starter: $(basename "$d") is geldig ${uit:+($uit)}"
    icoon="$(sed -n 's/^Icon=//p' "$d" | head -1)"
    gevonden="$(find /usr/share/icons/BugOS /usr/share/icons/hicolor -name "$icoon.svg" -o -name "$icoon.png" 2>/dev/null | head -1)"
    klopt '[ -n "$gevonden" ]' "pictogram: $icoon (uit $(basename "$d")) bestaat"
done

# 4. Diensten en updates (build.sh stap 6 en 7)
for u in bugos-first-boot.service rpm-ostreed-automatic.timer bugos-update-apps.timer; do
    klopt '[ "$(systemctl is-enabled "$u" 2>/dev/null)" = enabled ]' "dienst: $u staat aan"
done
klopt '[ ! -e /usr/lib/systemd/user/flatpak-user-update.timer ] || [ "$(systemctl --global is-enabled flatpak-user-update.timer 2>/dev/null)" != masked ]' \
    "dienst: flatpak-user-update.timer (apps per gebruiker) staat standaard aan, zoals 'Updates vanzelf' (U117)"
# U087: alleen BugOS werkt de apps bij (anders gaat het door, ook als je 'Updates zelf doen' kiest).
for u in flatpak-system-update.timer uupd.timer rpm-ostree-countme.timer; do
    [ -e "/usr/lib/systemd/system/$u" ] || continue
    klopt '[ "$(systemctl is-enabled "$u" 2>/dev/null)" = masked ]' "dienst: $u van de basis staat uit (masked)"
done
klopt '[ "$(systemctl --global is-enabled bugos-updatecheck.timer 2>/dev/null)" = enabled ]' "dienst: bugos-updatecheck.timer staat aan voor elke gebruiker"
klopt 'grep -qx "UPDATES=auto" /etc/bugos/updates.conf' "updates: standaard automatisch"
klopt 'grep -q "^AutomaticUpdatePolicy=stage" /etc/rpm-ostreed.conf' "updates: rpm-ostree zet updates klaar (stage)"
# IPv6, connect, not running: meldingen van de bouwcontainer zelf, geen fouten in de diensten.
uit="$(systemd-analyze verify /usr/lib/systemd/system/bugos-*.service /usr/lib/systemd/system/bugos-*.timer 2>&1 | grep -v -E 'Failed to (connect|open)|Cannot|not running|IPv6' || true)"
klopt '[ -z "$uit" ]' "diensten: systemd-analyze verify vindt geen fouten ${uit:+($uit)}"
# systemd-remount-fs mislukte na elke start (composefs-wortel); onze aanvulling laat die ene mislukking niet als fout
# tellen. Het programma moet op de plek staan die de aanvulling noemt, anders start de dienst helemaal niet meer.
klopt 'grep -qx "ExecStart=-/usr/lib/systemd/systemd-remount-fs" /usr/lib/systemd/system/systemd-remount-fs.service.d/50-bugos-composefs.conf && [ -x /usr/lib/systemd/systemd-remount-fs ] && grep -q "^enabled *= *yes" /usr/lib/ostree/prepare-root.conf' \
    "dienst: systemd-remount-fs telt het niet-opnieuw-koppelen van de composefs-wortel niet als fout"
for p in /usr/share/polkit-1/actions/org.bugos.*.policy; do
    klopt 'python3 -c "import sys, xml.etree.ElementTree as E; E.parse(sys.argv[1])" "$p"' "polkit: $(basename "$p") is geldige XML"
done

# 5. De BugOS-stijl voor nieuwe gebruikers (style.sh)
klopt 'grep -q "LookAndFeelPackage=org.bugos.desktop" /etc/xdg/kdeglobals' "stijl: look-and-feel org.bugos.desktop"
klopt 'grep -A3 "^\[Icons\]" /etc/xdg/kdeglobals | grep -q "Theme=BugOS"' "stijl: pictogramthema BugOS"
klopt 'grep -q "widgetStyle=kvantum" /etc/xdg/kdeglobals && [ -d /usr/share/Kvantum/BugOS ] && [ -d /usr/share/Kvantum/BugOSDark ] && grep -q "^theme=BugOS$" /etc/xdg/Kvantum/kvantum.kvconfig' "stijl: Kvantum met BugOS licht en donker"
klopt '[ -f /usr/share/color-schemes/BugOSLight.colors ] && [ -f /usr/share/color-schemes/BugOSDark.colors ]' "stijl: kleurschema's licht en donker"
klopt '[ -f /usr/share/bugos/wine/licht.reg ] && [ -f /usr/share/bugos/wine/donker.reg ]' "Windows-programma's: licht.reg en donker.reg"
klopt '[ -f /usr/share/plasma/shells/org.kde.plasma.desktop/contents/logout/bugos-aftellen.js ] && [ -f /usr/share/plasma/look-and-feel/org.bugos.desktop/contents/logout/bugos-aftellen.js ]' "uitzetscherm: bugos-aftellen.js staat naast Logout.qml (U088)"
klopt 'fc-list | grep -q "Inter" && fc-list | grep -q "JetBrains Mono"' "letters: Inter en JetBrains Mono geïnstalleerd"

klopt '! grep -qE "^(TEMPLATES|PUBLICSHARE)=" /etc/xdg/user-dirs.defaults && grep -q "^DOCUMENTS=" /etc/xdg/user-dirs.defaults'     "thuismap: een nieuwe gebruiker krijgt geen lege mappen Templates en Public (zoals Windows)"

# 5b. Het startmenu toont alleen programma's met een gewone naam (style.sh: hernoemen en verbergen).
#     Geen KDE-namen (KFind, Krfb, KCharSelect...), geen hulpjes voor gevorderden.
apps="$(LANG=en_US.UTF-8 /usr/bin/bugos-start-data 2>/dev/null | python3 -c 'import json, sys
for a in json.load(sys.stdin)["apps"]:
    if a.get("soort") == "app":
        print(a["naam"])' 2>/dev/null)"
klopt '[ -n "$apps" ]' "startmenu: bugos-start-data geeft de apps"
raar="$(echo "$apps" | grep -E '^K[A-Z]|^K[a-z]+[A-Z]|^Krfb|Kvantum|DOSBox|Firewall|KDE|Dolphin|Discover|Info Center|System Monitor|Menu Editor' | paste -sd, - || true)"
klopt '[ -z "$raar" ]' "startmenu: geen KDE-namen of hulpjes voor gevorderden tussen de apps ${raar:+($raar)}"

# 6. Alles laadt met de Qt, KDE en Python van het beeld zelf
HOME="$(mktemp -d)"
export QT_QPA_PLATFORM=offscreen PYTHONDONTWRITEBYTECODE=1 HOME
uit="$(python3 - <<'EOF' 2>&1
import importlib, importlib.machinery, importlib.util, sys
from pathlib import Path
sys.path.insert(0, "/usr/lib/bugos/python")
import bugos_ui, bugos_config, bugos_tasks  # noqa: F401  eerst de ouders
fout = []
for p in sorted(Path("/usr/lib/bugos/python").glob("*.py")):
    try:
        importlib.import_module(p.stem)
    except Exception as e:
        fout.append(f"{p.name}: {type(e).__name__}: {e}")
for p in sorted(Path("/usr/bin").glob("bugos-*")):
    if not p.read_text(errors="replace").startswith("#!/usr/bin/python3"):
        continue
    naam = "p_" + p.name.replace("-", "_")
    lader = importlib.machinery.SourceFileLoader(naam, str(p))
    mod = importlib.util.module_from_spec(importlib.util.spec_from_loader(naam, lader))
    sys.modules[naam] = mod
    try:
        lader.exec_module(mod)
    except SystemExit:
        pass
    except Exception as e:
        fout.append(f"{p.name}: {type(e).__name__}: {e}")
print("\n".join(fout))
EOF
)"
klopt '[ -z "$uit" ]' "laden: elk BugOS-programma en onderdeel laadt ${uit:+($uit)}"
for s in /usr/bin/bugos-*; do
    head -1 "$s" | grep -q bash || continue
    klopt 'bash -n "$s"' "shell: $(basename "$s") heeft geen tikfouten"
done

# 7. De tests uit de repo, maar nu met de echte programma's van Fedora (rsync, udisks, Qt, Plasma-QML)
if [ -d "$REPO/tools" ]; then
    T="$(mktemp -d)"
    cp -a "$REPO/." "$T/"
    for t in qml-test test_files test_task_manager test_settings test_start_data test_help test_backup test_logout test_edges test_os_settings test_os_apps test_menus; do
        if (cd "$T" && timeout 300 python3 "tools/$t.py" >"$T/$t.log" 2>&1); then ok "repo-test: $t"; else fout "repo-test: $t ($(grep -E '^FOUT|Error' "$T/$t.log" | head -3 | tr '\n' ' '))"; fi
    done
    for t in test_package test_game_mode test_light_mode test_panel test_exe test_signed test_windows_start test_os_system; do
        if (cd "$T" && timeout 300 bash "tools/$t.sh" >"$T/$t.log" 2>&1); then ok "repo-test: $t"; else fout "repo-test: $t ($(grep -E '^FOUT' "$T/$t.log" | head -3 | tr '\n' ' '))"; fi
    done
fi

echo "$fouten fout(en)."
[ "$fouten" -eq 0 ]
