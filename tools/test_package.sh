#!/usr/bin/bash
# Test van bugos-package: een .rpm met een rare naam installeren mag nooit iets anders uitvoeren.
# Met nep-programma's (distrobox, dnf, kdialog...): er wordt niets echt geïnstalleerd.
#
# Gebruik:  bash tools/test_package.sh
set -u
# shellcheck disable=SC2016  # de $ in de nep-programma's en controles is bedoeld (wordt later uitgevoerd)
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/bin" "$TMP/lib"
fouten=0
klopt() { if eval "$1"; then echo "OK    $2"; else echo "FOUT  $2"; fouten=$((fouten + 1)); fi; }

# lib.sh van deze repo, niet die van het systeem.
sed "s|/usr/share/bugos|$ROOT/system_files/usr/share/bugos|g" "$ROOT/system_files/usr/bin/bugos-package" >"$TMP/bugos-package"
nep() { printf '#!/usr/bin/bash\n%s\n' "$2" >"$TMP/bin/$1"; chmod +x "$TMP/bin/$1"; }
nep kdialog 'exit 0'
nep notify-send 'exit 0'
nep flatpak 'exit 0'
nep rpm '[ "$1" = -qp ] && echo voorbeeld; exit 0'
nep sudo 'exec "$@"'
nep dnf 'printf "%s\n" "$@" >"$NEP_UIT"'
nep distrobox 'case "$1" in list) echo " bugos-fedora ";; enter) shift; while [ "$1" != -- ]; do shift; done; shift; exec "$@";; esac'
# Het beeld van het doosje is er al (geen download), en skopeo komt niet op internet: de tests downloaden nooit iets.
nep podman 'exit 0'
nep skopeo 'exit 1'

cd "$TMP" || exit 1
installeer() { rm -f "$TMP/dnf-args"; touch "$1"; PATH="$TMP/bin:$PATH" NEP_UIT="$TMP/dnf-args" bash "$TMP/bugos-package" "$1"; }

RAAR="$TMP/app\$(touch gehackt)\`touch gehackt2\`.rpm"
installeer "$RAAR"
klopt '[ ! -e "$TMP/gehackt" ] && [ ! -e "$TMP/gehackt2" ]' "naam met \$(…) en \`…\`: er wordt niets uitgevoerd"
klopt 'grep -qxF -- "$RAAR" "$TMP/dnf-args" 2>/dev/null' "naam met \$(…) en \`…\`: dnf krijgt precies het bestand"

RAAR2="$TMP/app \"2\" \$HOME.rpm"
installeer "$RAAR2"
klopt 'grep -qxF -- "$RAAR2" "$TMP/dnf-args" 2>/dev/null' "naam met spaties, \" en \$: dnf krijgt precies het bestand"

# U057: in het Nederlands zegt flatpak "Geen overeenkomsten gevonden": dat is geen app, dus niet "staat in de Winkel".
nep flatpak 'if [ "$1" = search ]; then if [ "${LC_ALL:-}" = C ]; then echo "No matches found"; else echo "Geen overeenkomsten gevonden"; fi; fi; exit 0'
nep kdialog 'echo "$*" >>"'"$TMP"'/gevraagd"; exit 0'
nep bugos-store 'echo "$*" >"'"$TMP"'/winkel"; exit 0'
rm -f "$TMP/gevraagd" "$TMP/winkel"
LANG=nl_NL.UTF-8 installeer "$TMP/eigen-app.rpm"
klopt '! grep -qi "winkel\|store" "$TMP/gevraagd" 2>/dev/null && [ ! -f "$TMP/winkel" ]' \
    "U057: geen app in de Winkel (Nederlandse flatpak): niet vragen of het 'ook in de Winkel' staat"
nep flatpak 'if [ "$1" = search ]; then printf "Voorbeeld\torg.voorbeeld.App\n"; fi; exit 0'
rm -f "$TMP/gevraagd" "$TMP/winkel"
installeer "$TMP/voorbeeld.rpm"
klopt 'grep -q "appstream://org.voorbeeld.App" "$TMP/winkel" 2>/dev/null' "U057: staat het wel in de Winkel, dan gaat het daarheen"

# U195: een pakket zonder programma met een venster: niet 'staat in je startmenu' zeggen.
nep flatpak 'exit 0'
nep notify-send 'echo "$*" >>"'"$TMP"'/meldingen"'
rm -f "$TMP/meldingen"
installeer "$TMP/alleen-terminal.rpm"
klopt 'grep -q "Terminal" "$TMP/meldingen" 2>/dev/null && ! grep -q "staat nu in je startmenu\|is now in your start menu" "$TMP/meldingen"' \
    "U195: zonder plek in het startmenu: zeggen dat je het in de Terminal gebruikt"
# U198: mislukt de installatie (bijv. geen internet), dan niet 'Klaar' zeggen, ook niet zonder plek in het startmenu.
nep dnf 'exit 1'
nep kdialog 'echo "$*" >>"'"$TMP"'/fouten"; exit 0'
rm -f "$TMP/meldingen" "$TMP/fouten"
installeer "$TMP/kapot.rpm"
klopt '! grep -q "Klaar\|Done" "$TMP/meldingen" 2>/dev/null && grep -q "niet gelukt\|did not work" "$TMP/fouten" 2>/dev/null' \
    "U198: een mislukte installatie zegt dat het niet lukte (niet 'Klaar')"
# U351: een kapot .rpm-bestand: meteen zeggen, niet eerst een doosje maken.
nep rpm 'exit 1'
nep distrobox 'echo "$*" >>"'"$TMP"'/doos-log"; exit 0'
rm -f "$TMP/fouten" "$TMP/doos-log"
installeer "$TMP/half.rpm"
klopt 'grep -q "kapot\|broken" "$TMP/fouten" 2>/dev/null && [ ! -s "$TMP/doos-log" ]' "U351: een kapot .rpm-bestand: meteen een uitleg, geen doosje maken"
nep rpm '[ "$1" = -qp ] && echo voorbeeld; exit 0'
klopt 'grep -q "Het kan wel bij je eigen bestanden" "$ROOT/system_files/usr/bin/bugos-package" && ! grep -q "veilig doosje" "$ROOT/system_files/usr/bin/bugos-package"' \
    "U245: installeren zegt eerlijk dat het programma bij je bestanden kan (geen 'veilig doosje')"
# U424: het doosje maken mislukt omdat de computer vol is: dat zeggen, niet 'heb je internet?'.
nep distrobox 'case "$1" in list) exit 0;; create) echo "Error: writing blob: No space left on device" >&2; exit 1;; esac; exit 0'
rm -f "$TMP/fouten"
installeer "$TMP/half.rpm"
klopt 'grep -qi "vol\|full" "$TMP/fouten" 2>/dev/null && ! grep -qi "internet\|online" "$TMP/fouten"' "U424: doosje maken met een volle computer: dat wordt gezegd"
# D-06: flatpak search zoekt "ongeveer" (voor hello kwam Discord bovenaan). Alleen een app die precies zo heet of
# waarvan de app-naam op het pakket eindigt, telt; anders geen Winkel-vraag.
nep flatpak 'if [ "$1" = search ]; then printf "Discord\tcom.discordapp.Discord\nHello Flatpak\torg.example.HelloWorld\n"; fi; exit 0'
nep kdialog 'echo "$*" >>"'"$TMP"'/gevraagd"; exit 1'
rm -f "$TMP/gevraagd" "$TMP/winkel"
LANG=nl_NL.UTF-8 installeer "$TMP/hello_2.10-3_amd64.deb" >/dev/null 2>&1
klopt '! grep -qi "Winkel\|Store" "$TMP/gevraagd" 2>/dev/null && [ ! -f "$TMP/winkel" ]' \
    "D-06: hello.deb: geen 'staat ook in de Winkel' voor Discord of HelloWorld"
nep flatpak 'if [ "$1" = search ]; then printf "GIMP User Manual\torg.gimp.GIMP.Manual\nGNU Image Manipulation Program\torg.gimp.GIMP\n"; fi; exit 0'
nep kdialog 'echo "$*" >>"'"$TMP"'/gevraagd"; exit 0'
rm -f "$TMP/gevraagd" "$TMP/winkel"
LANG=nl_NL.UTF-8 installeer "$TMP/gimp_2.10.38_amd64.deb" >/dev/null 2>&1
klopt '[ "$(cat "$TMP/winkel" 2>/dev/null)" = "appstream://org.gimp.GIMP" ]' "D-06: gimp.deb: de echte GIMP (org.gimp.GIMP, niet de handleiding)"
nep flatpak 'if [ "$1" = search ]; then printf "Hello\tcom.example.Groeter\n"; fi; exit 0'
rm -f "$TMP/gevraagd" "$TMP/winkel"
LANG=nl_NL.UTF-8 installeer "$TMP/hello_2.10-3_amd64.deb" >/dev/null 2>&1
klopt '[ "$(cat "$TMP/winkel" 2>/dev/null)" = "appstream://com.example.Groeter" ]' "D-06: een app die precies 'hello' heet: wel de Winkel"

# D-07: een nieuw doosje: vooraf zeggen dat het minuten duurt en hoeveel MB, en dan echte stappen in één melding die
# wordt bijgewerkt (ophalen, klaarzetten, installeren), alles met lage voorrang.
# D-08: daarna het doosje weer uitzetten (het bleef draaien, 715 MB), maar niet als het al draaide.
nep flatpak 'exit 0'
nep kdialog 'echo "$*" >>"'"$TMP"'/gevraagd"; exit 0'
nep notify-send 'echo "$*" >>"'"$TMP"'/meldingen"; case " $* " in *" --print-id "*) echo 42;; esac'
nep podman 'echo "podman $*" >>"'"$TMP"'/doos-log"; [ "$1 $2" = "image exists" ] && exit 1; exit 0'
nep skopeo 'echo "{\"LayersData\":[{\"Size\":200000000},{\"Size\":100000000}]}"'
nep systemd-run 'echo "systemd-run $*" >>"'"$TMP"'/laag"; while [ "$#" -gt 0 ] && [ "$1" != -- ]; do shift; done; shift; exec "$@"'
nep distrobox 'echo "distrobox $*" >>"'"$TMP"'/doos-log"; case "$1" in list) [ -f "'"$TMP"'/doos-er" ] && echo " bugos-ubuntu | Exited (0) 1 minute ago ";; create) touch "'"$TMP"'/doos-er";; enter) shift; while [ "$1" != -- ]; do shift; done; shift; exec "$@";; esac; exit 0'
nep apt-get 'exit 0'
rm -f "$TMP/gevraagd" "$TMP/meldingen" "$TMP/doos-log" "$TMP/laag" "$TMP/doos-er"
LANG=nl_NL.UTF-8 installeer "$TMP/eigen_1.0_amd64.deb" >/dev/null 2>&1
if command -v jq >/dev/null 2>&1; then mb_ok='grep -q "ongeveer 287 MB" "$TMP/gevraagd"'; else mb_ok=true; fi
klopt 'grep -q "5 tot 15 minuten" "$TMP/gevraagd" 2>/dev/null && eval "$mb_ok"' "D-07: vooraf: de eerste keer duurt minuten, en hoeveel MB er gedownload wordt"
klopt 'grep -q "stap 1 van 3.*ophalen" "$TMP/meldingen" && grep -q "stap 2 van 3.*klaarzetten" "$TMP/meldingen" && grep -q "stap 3 van 3.*installeren" "$TMP/meldingen" && grep -q -- "--replace-id=42 Klaar" "$TMP/meldingen"' \
    "D-07: echte stappen (ophalen, klaarzetten, installeren) in één melding die wordt bijgewerkt"
klopt 'grep -q "podman pull quay.io/toolbx/ubuntu-toolbox" "$TMP/doos-log" && grep -q "CPUWeight=idle" "$TMP/laag" 2>/dev/null && grep -q "nice -n 19" "$TMP/laag" 2>/dev/null' \
    "D-07: ophalen, klaarzetten en installeren draaien met lage voorrang (CPUWeight=idle, nice)"
klopt 'grep -q "distrobox stop --yes bugos-ubuntu" "$TMP/doos-log"' "D-08: na het installeren gaat het doosje weer uit"
nep distrobox 'echo "distrobox $*" >>"'"$TMP"'/doos-log"; case "$1" in list) echo " bugos-ubuntu | Up 5 minutes ";; enter) shift; while [ "$1" != -- ]; do shift; done; shift; exec "$@";; esac; exit 0'
rm -f "$TMP/doos-log" "$TMP/gevraagd"
LANG=nl_NL.UTF-8 installeer "$TMP/eigen_1.0_amd64.deb" >/dev/null 2>&1
klopt '! grep -q "distrobox stop" "$TMP/doos-log" && ! grep -q "podman pull\|distrobox create" "$TMP/doos-log" && grep -q "een paar minuten" "$TMP/gevraagd"' \
    "D-08: draaide het doosje al (een programma eruit is open), dan blijft het aan; geen nieuw doosje"
# VM-test 2026-11-23: (1) een oudere .deb over een nieuwere versie in het doosje mislukte ("-y was used without
# --allow-downgrades"); (2) in het startmenu stond "Galculator (on bugos-ubuntu)". Nep-apt-get en nep-distrobox-export
# schrijven hun argumenten op; nep-dpkg-deb zegt dat het pakket één programma met een venster heeft.
nep apt-get 'echo "$*" >>"'"$TMP"'/apt-args"; exit 0'
nep rpm 'exit 1'
nep dpkg-deb 'echo "-rw-r--r-- root/root 100 2024-01-01 00:00 ./usr/share/applications/eigen.desktop"'
nep distrobox-export 'echo "$*" >>"'"$TMP"'/export-args"; exit 0'
rm -f "$TMP/apt-args" "$TMP/export-args"
LANG=nl_NL.UTF-8 installeer "$TMP/eigen_1.0_amd64.deb" >/dev/null 2>&1
klopt 'grep -q -- "install -y --allow-downgrades" "$TMP/apt-args" 2>/dev/null' \
    ".deb installeren: ook als er al een nieuwere versie in het doosje staat (--allow-downgrades)"
klopt 'grep -q -- "--app eigen --export-label none" "$TMP/export-args" 2>/dev/null' \
    ".deb naar het startmenu: zonder '(on bugos-ubuntu)' achter de naam (--export-label none)"
rm -f "$TMP/bin/rpm" "$TMP/bin/dpkg-deb" "$TMP/bin/distrobox-export"
rm -f "$TMP/bin/systemd-run" "$TMP/bin/apt-get"
nep podman 'exit 0'
nep skopeo 'exit 1'
nep notify-send 'exit 0'
nep distrobox 'case "$1" in list) echo " bugos-fedora ";; enter) shift; while [ "$1" != -- ]; do shift; done; shift; exec "$@";; esac'
# U465: programma's uit een .rpm/.deb worden bijgewerkt (elke dag, bij 'Updates vanzelf').
nep distrobox 'case "$1" in list) echo " bugos-ubuntu ";; upgrade) echo "$2" >>"'"$TMP"'/bijgewerkt";; esac; exit 0'
rm -f "$TMP/bijgewerkt"
mkdir -p "$TMP/thuis/.local/share/containers"
HOME="$TMP/thuis" PATH="$TMP/bin:$PATH" bash "$TMP/bugos-package" --bijwerken >/dev/null 2>&1
SDU="$ROOT/system_files/usr/lib/systemd/user"
klopt '[ "$(cat "$TMP/bijgewerkt" 2>/dev/null)" = bugos-ubuntu ] && grep -qx "ExecCondition=/usr/bin/bugos-updates mag-vanzelf" "$SDU/bugos-update-doosjes.service" && grep -qx "OnCalendar=daily" "$SDU/bugos-update-doosjes.timer" && grep -q "enable bugos-update-doosjes.timer" "$ROOT/build_files/build.sh"' \
    "U465: programma's uit een .rpm/.deb krijgen ook updates (hun doosje, elke dag bij 'Updates vanzelf')"
# U473: niet via een hotspot, opnieuw proberen als het mislukte, en niets doen voor een account zonder doosjes.
nep distrobox 'case "$1" in list) echo " bugos-ubuntu ";; upgrade) echo "$2" >>"'"$TMP"'/bijgewerkt"; exit 1;; esac; exit 0'
HOME="$TMP/thuis" PATH="$TMP/bin:$PATH" bash "$TMP/bugos-package" --bijwerken >/dev/null 2>&1; c1=$?
rm -f "$TMP/bijgewerkt"
HOME="$TMP/leeg" PATH="$TMP/bin:$PATH" bash "$TMP/bugos-package" --bijwerken >/dev/null 2>&1; c2=$?
klopt '[ "$c1" -ne 0 ] && [ "$c2" -eq 0 ] && [ ! -e "$TMP/bijgewerkt" ] && grep -q "Metered" "$SDU/bugos-update-doosjes.service" && grep -qx "Restart=on-failure" "$SDU/bugos-update-doosjes.service" && grep -qx "StartLimitBurst=4" "$SDU/bugos-update-doosjes.service" && grep -q "flock -w 3600 9" "$TMP/bugos-package" && grep -q "distrobox upgrade \"\$doos\" >/dev/null 2>&1 9>&-" "$TMP/bugos-package"' \
    "U473: doosjes bijwerken: niet via een hotspot, later opnieuw als het mislukte, niets zonder doosjes ($c1, $c2)"
# U494: met de hand ('Nu updaten') en de dagelijkse loopt al: niet wachten, gewoon klaar.
mkdir -p "$TMP/run494"
nep distrobox 'case "$1" in list) echo " bugos-ubuntu ";; upgrade) echo "$2" >>"'"$TMP"'/bijgewerkt";; esac; exit 0'
rm -f "$TMP/bijgewerkt"
flock "$TMP/run494/bugos-doosjes.slot" sleep 3 &
sleep 0.5
begin=$SECONDS
HOME="$TMP/thuis" XDG_RUNTIME_DIR="$TMP/run494" PATH="$TMP/bin:$PATH" bash "$TMP/bugos-package" --bijwerken --nu >/dev/null 2>&1; c494=$?
duur=$((SECONDS - begin))
wait
klopt '[ "$c494" -eq 0 ] && [ "$duur" -lt 2 ] && [ ! -e "$TMP/bijgewerkt" ]' "U494: 'Nu updaten' wacht niet op een dagelijkse doosjes-update die al loopt ($c494, ${duur}s)"
# VM-test 2026-11-16: een trage dubbelklik en daarna 'Openen' gaf twee keer de vraag en twee installaties tegelijk.
# Eén installatie tegelijk per doosje (slotmap met procesnummer in XDG_RUNTIME_DIR).
RUN="$TMP/run"; mkdir -p "$RUN"
# De nep-programma's terug zoals bovenaan (eerdere controles hierboven veranderden rpm, dnf en distrobox).
nep rpm '[ "$1" = -qp ] && echo voorbeeld; exit 0'
nep dnf 'printf "%s
" "$@" >"$NEP_UIT"'
nep distrobox 'case "$1" in list) echo " bugos-fedora ";; enter) shift; while [ "$1" != -- ]; do shift; done; shift; exec "$@";; esac'
nep podman 'exit 0'
nep flatpak 'exit 0'
nep kdialog 'echo "$*" >>"'"$TMP"'/gevraagd"; exit 0'
nep notify-send 'echo "$*" >>"'"$TMP"'/meldingen"'
mkdir -p "$RUN/bugos-package-bugos-fedora.bezig"; echo $$ >"$RUN/bugos-package-bugos-fedora.bezig/pid"   # $$ leeft
rm -f "$TMP/gevraagd" "$TMP/meldingen" "$TMP/dnf-args"
touch "$TMP/tweede.rpm"; XDG_RUNTIME_DIR="$RUN" PATH="$TMP/bin:$PATH" NEP_UIT="$TMP/dnf-args" bash "$TMP/bugos-package" "$TMP/tweede.rpm"
klopt '[ ! -e "$TMP/dnf-args" ] && grep -q "al bezig\|already installing" "$TMP/gevraagd" "$TMP/meldingen" 2>/dev/null'     "Eén tegelijk: loopt er al een installatie, dan geen tweede vraag of installatie, wel 'al bezig'"
echo 999999 >"$RUN/bugos-package-bugos-fedora.bezig/pid"   # dit proces bestaat niet (meer)
rm -f "$TMP/dnf-args"
XDG_RUNTIME_DIR="$RUN" PATH="$TMP/bin:$PATH" NEP_UIT="$TMP/dnf-args" bash "$TMP/bugos-package" "$TMP/tweede.rpm"
klopt 'grep -qxF -- "$TMP/tweede.rpm" "$TMP/dnf-args" 2>/dev/null && [ ! -e "$RUN/bugos-package-bugos-fedora.bezig" ]'     "Eén tegelijk: een oud slot (proces weg) wordt overgenomen, en na afloop is het slot weer weg"
nep flatpak 'if [ "$1" = search ]; then printf "Voorbeeld	org.voorbeeld.App
"; fi; exit 0'
nep bugos-store 'exit 0'
touch "$TMP/voorbeeld.rpm"; XDG_RUNTIME_DIR="$RUN" PATH="$TMP/bin:$PATH" NEP_UIT="$TMP/dnf-args" bash "$TMP/bugos-package" "$TMP/voorbeeld.rpm"
klopt '[ ! -e "$RUN/bugos-package-bugos-fedora.bezig" ]' "Eén tegelijk: naar de Winkel (exec) laat geen slot achter"

echo "$fouten fout(en)."
[ "$fouten" -eq 0 ]
