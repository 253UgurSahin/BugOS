#!/usr/bin/bash
# BugOS - bouwscript
# ==================
# Dit script draait één keer tijdens het bouwen van BugOS (niet op de pc van
# de gebruiker). Het legt onze bestanden neer, installeert extra programma's
# en zet de BugOS-naam en -stijl goed.

set -ouex pipefail

BUGOS_VARIANT="${BUGOS_VARIANT:-main}"
BUGOS_VERSION="${BUGOS_VERSION:-dev}"

# 1. Onze eigen bestanden (scripts, stijl, logo, instellingen) neerleggen.
# --remove-destination: eerst het bestaande bestand weghalen en dan een nieuw bestand schrijven, in plaats van
# het bestaande bestand te overschrijven. Overschrijven ging in een lokale bouw (podman in Docker Desktop) mis
# bij bestanden die al in de fundering stonden en groter werden (/etc/xdg/user-dirs.defaults,
# /etc/xdg/PlasmaDiscoverUpdates): de nieuwe lengte bleef, maar de oude inhoud kwam terug met nul-bytes erachter.
# Weghalen en opnieuw schrijven is in elke bouwomgeving goed.
cp -av --remove-destination /ctx/system_files/. /
# Vaste rechten, wat de bouwmap ook zegt (vanaf Windows is alles 0777, en dan
# klaagt systemd over "world-writable" diensten): bestanden 0644, mappen 0755,
# alleen de programma's in /usr/bin uitvoerbaar.
(cd /ctx/system_files && find . -type f -print0) | while IFS= read -r -d '' f; do chmod 0644 "/${f#./}"; done
(cd /ctx/system_files && find . -mindepth 1 -type d -print0) | while IFS= read -r -d '' d; do chmod 0755 "/${d#./}"; done
chmod 0755 /usr/bin/bugos-* /usr/libexec/bugos-user-check /usr/libexec/bugos-hide-system-drives /usr/libexec/bugos-taal-standaard \
    /usr/libexec/bugos-schil-of-plasma
# De Python-onderdelen van BugOS vooraf vertalen: /usr is straks alleen-lezen, dus anders doet elke app dat bij
# elke start opnieuw. Met een controlegetal (checked-hash): ostree zet de tijden van bestanden gelijk, en een
# veranderd bestand (usr-overlay bij het zoeken naar een fout) wordt dan toch opnieuw gelezen (U313, U319).
find /usr/lib/bugos/python -name __pycache__ -prune -exec rm -rf {} +
python3 -m compileall -q --invalidation-mode checked-hash /usr/lib/bugos/python

# De pictogrammen van de apps in de BugOS Winkel meeleveren. Anders zie je op een vers systeem (de catalogus
# van Flathub is dan nog niet opgehaald) en zonder internet bij Firefox, LibreOffice, Spotify en Steam alleen een
# grijs bestandje. Lukt het ophalen niet (geen internet tijdens het bouwen), dan gaat de bouw gewoon door.
python3 - <<'EOF' || true
import json, pathlib, urllib.request
uit = pathlib.Path("/usr/share/bugos/store-icons")
uit.mkdir(parents=True, exist_ok=True)
apps = [a["id"] for a in json.load(open("/usr/share/bugos/store.json", encoding="utf-8"))["apps"]]
def haal(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "bugos-build"}), timeout=20).read()
for app_id in apps:
    try:
        icoon = json.loads(haal(f"https://flathub.org/api/v2/appstream/{app_id}")).get("icon") or ""
        if icoon.startswith("https://dl.flathub.org/"):
            (uit / f"{app_id}.png").write_bytes(haal(icoon))
    except Exception as e:  # noqa: BLE001
        print("BugOS Winkel: geen pictogram voor", app_id, e)
print(len(list(uit.glob("*.png"))), "van", len(apps), "Winkel-pictogrammen")
EOF
chmod 0644 /usr/share/bugos/store-icons/* 2>/dev/null || true

# 2. Extra programma's installeren.
#    --skip-unavailable: als een pakket (even) niet bestaat, gaat de bouw
#    gewoon door in plaats van te stoppen.
#    Alleen wat de basis nog NIET heeft. 'dnf5 install' van een pakket dat er al is, werkt het bij naar de nieuwste
#    versie in 'updates'; zo'n los bijgewerkt pakket kan nieuwere bibliotheken nodig hebben dan de basis heeft, zonder
#    dat rpm dat weet (zie D-09 hieronder: precies zo ging KWrite stuk). De basis is één geheel dat samen getest is:
#    packages.txt vult aan en werkt niets van de basis stukje voor stukje bij. Nieuwe pakketten mogen wel meenemen
#    wat ze nodig hebben.
mapfile -t ALLE_PAKKETTEN < <(grep -vE '^\s*(#|$)' /ctx/packages.txt)
PAKKETTEN=()
for pakket in "${ALLE_PAKKETTEN[@]}"; do
    # rpm -q kent ook 'provides' niet, alleen pakketnamen: precies wat packages.txt bevat.
    if rpm -q "$pakket" >/dev/null 2>&1; then
        echo "packages.txt: $pakket zit al in de basis, blijft zoals de basis hem heeft"
    else
        PAKKETTEN+=("$pakket")
    fi
done
if [ "${#PAKKETTEN[@]}" -gt 0 ]; then
    dnf5 install -y --skip-unavailable "${PAKKETTEN[@]}"
fi

# D-09: de teksteditor moet echt starten. De basis van Universal Blue (kinoite-main:44 van 2026-11-16) zet zelf Kate
# erbij en haalt daarvoor kate, kate-libs en KWrite 26.08.3 uit 'updates', gebouwd tegen KDE Frameworks 6.32; de
# frameworks van de basis bleven op 6.31 (Fedora's eigen Kinoite had nog 26.08.2, dat paste). De eis van kate-libs op
# libKF6ConfigCore staat er zonder versie in, dus rpm en dnf zien niets, maar KWrite stopte meteen met "symbol lookup
# error: libkateprivate.so.26.08.3: undefined symbol: _ZN7KConfig8copyFromERKS_": geen enkel .txt ging open.
# LD_BIND_NOW=1 zoekt bij het starten alle symbolen op, dus 'kwrite --version' laat zo'n gat meteen zien.
# Is het stuk, dan werken we ALLE KDE Frameworks (de kf6-pakketten met versie 6.x) samen bij naar de versie in
# 'updates': de frameworks horen één set met één versie te zijn (nagegaan 2026-11-16: 81 pakketten, alleen kf6,
# Plasma en de rest blijven zoals ze zijn; Plasma 6.8 werkt met nieuwere frameworks). Zo blijft het geheel kloppen,
# zoals bij een Fedora met alle updates. Alleen als het nodig is: zolang het past, blijft de basis precies de basis.
# Lukt het daarna nog niet, dan stopt de bouw luid: liever geen beeld dan een BugOS waarin niets van tekst opengaat.
editor_start() {
    local p
    for p in kwrite kate; do
        command -v "$p" >/dev/null 2>&1 || continue
        LD_BIND_NOW=1 QT_QPA_PLATFORM=offscreen HOME=/tmp timeout 60 "$p" --version >/dev/null 2>&1 || return 1
    done
}
if ! editor_start; then
    echo "D-09: de teksteditor start niet met de KDE Frameworks van de basis; frameworks samen bijwerken"
    mapfile -t FRAMEWORKS < <(rpm -qa --qf '%{NAME} %{VERSION}\n' 'kf6-*' | awk '$2 ~ /^6\./ {print $1}' | sort -u)
    dnf5 upgrade -y "${FRAMEWORKS[@]}"
    if ! editor_start; then
        echo "D-09: de teksteditor start nog steeds niet, ook met bijgewerkte frameworks" >&2
        LD_BIND_NOW=1 QT_QPA_PLATFORM=offscreen HOME=/tmp kwrite --version >&2 || true
        exit 1
    fi
fi

# Geen KDE Discover: de BugOS Winkel doet alle apps zelf, ook die van buiten de BugOS-selectie (Flathub),
# en opent zelf de .flatpakref-bestanden van flathub.org. Haal hem weg als de basis hem meebrengt, met de
# PackageKit-, systeemupdate- en updatemelder-onderdelen (plasma-discover-notifier werkte Flatpak-apps
# stilletjes bij, ook bij 'Ik kies zelf wanneer' (U321)). Updates doet BugOS zelf (stap 6).
# Zonder --nodeps: hangt er ooit iets van Discover af, dan moet de bouw luid stoppen, niet dat pakket breken.
# Nagegaan op Kinoite 44 (Plasma 6.8.2, 2026-11-12): de basis heeft plasma-discover, -flatpak, -kns, -libs en
# -notifier; rpm -e --test van precies deze lijst slaagt, en niets anders (ook niets uit packages.txt) heeft ze nodig.
mapfile -t TEVEEL < <(rpm -q --qf '%{NAME}\n' plasma-discover plasma-discover-flatpak plasma-discover-kns \
    plasma-discover-libs plasma-discover-packagekit plasma-discover-offline-updates plasma-discover-rpm-ostree \
    plasma-discover-notifier 2>/dev/null | grep -v 'not installed' || true)
if [ "${#TEVEEL[@]}" -gt 0 ]; then
    rpm -e "${TEVEEL[@]}"
fi

# Geen KDE Partition Manager. De basis (Kinoite) brengt hem mee. Het startmenu verbergt hem al (style.sh), maar zijn
# Solid-actie 'Reformat or Edit with Partition Manager' stond nog bij elke USB-stick in 'Schijven en apparaten' (het
# systeemvak). Bestanden maakt zelf USB-sticks leeg en richt een nieuwe schijf zelf in. Een tweede interne schijf
# wissen kan Bestanden pas met het pakket tools, dat ook de knop 'Schijfbeheer (voor gevorderden)' uit Bestanden
# haalt. Zonder dat pakket verdwijnt die knop hier vanzelf (Bestanden laat hem alleen zien als partitionmanager er
# is), en kan BugOS een tweede interne schijf niet meer wissen of indelen: dit hoort dus in hetzelfde beeld als tools.
# Niets anders heeft kde-partitionmanager of kpmcore nodig (rpm -e --test op Kinoite 44 en op BugOS slaagt).
# Zelfde aanpak als bij Discover: alleen als hij er is, en zonder --nodeps.
mapfile -t SCHIJFBEHEER < <(rpm -q --qf '%{NAME}\n' kde-partitionmanager kpmcore 2>/dev/null \
    | grep -v 'not installed' || true)
if [ "${#SCHIJFBEHEER[@]}" -gt 0 ]; then
    rpm -e "${SCHIJFBEHEER[@]}"
fi

# Geen Xwayland Video Bridge. Het stond als technisch icoontje ("Xwayland Video Bridge") onder het pijltje in het
# systeemvak, en Plasma kan dat soort icoon niet verbergen (VM-test A-12). Het enige wat het doet: schermdelen naar
# oude X11-programma's (zoals de oude Discord-app). Bewuste keuze van de eigenaar (2026-11-14): weg ermee. Wie
# schermdelen in zo'n programma mist: de Flatpak-versies uit de Winkel delen het scherm via de portal, zonder brug.
# Niets heeft het pakket nodig (rpm -q --whatrequires op BugOS, 2026-11-14). Zelfde aanpak: alleen als het er is.
mapfile -t BRUG < <(rpm -q --qf '%{NAME}\n' xwaylandvideobridge 2>/dev/null | grep -v 'not installed' || true)
if [ "${#BRUG[@]}" -gt 0 ]; then
    rpm -e "${BRUG[@]}"
fi

# 32-bits Windows-programma's (de meeste installatieprogramma's, zoals die van Notepad++) (D-03).
# Fedora 44 levert Wine als "wow64" in /usr/lib64/wine-wow64. Het SELinux-beleid kent alleen /usr/lib(64)/wine: daar
# krijgen de Windows-dll's het label textrel_shlib_t (Wine moet die in het geheugen kunnen aanpassen: "execmod").
# De wine-wow64-map viel erbuiten (label lib_t), dus weigerde SELinux execmod op i386-windows/ntdll.dll; Wine zei
# "failed to set ... protection on syswow64\ntdll.dll ... noexec filesystem?" en het programma liep vast.
# De boolean selinuxuser_execmod helpt niet: die staat al aan, en de controle gebeurt met de rechten van wie het
# composefs-bestandssysteem van ostree aankoppelde (kernel_t), niet die van de gebruiker (zie de AVC: scontext kernel_t).
# Dus dezelfde regels als Fedora voor /usr/lib/wine, nu ook voor wine-wow64. semanage zet ze in het beleid van het
# image (/etc/selinux, file_contexts.local); ostree labelt /usr met dat beleid als het image wordt neergezet.
# De paden met /usr/lib: SELinux leest /usr/lib64 als /usr/lib (file_contexts.subs_dist). In één 'semanage import'
# (één keer het beleid opnieuw bouwen); nagegaan in het image: matchpathcon geeft daarna textrel_shlib_t.
# In de *-windows-mappen ALLE bestanden, niet alleen .exe/.dll: de Mono-setup laadt appwiz.cpl via rundll32, en ook
# .dll16, .tlb, .msstyles enz. is Windows-code die Wine in het geheugen laadt (VM-test 2026-11-16: execmod geweigerd
# op appwiz.cpl; 1656 bestanden in wine-wow64 hadden nog lib_t).
if [ -d /usr/lib64/wine-wow64 ]; then
    semanage import <<'REGELS'
fcontext -a -t textrel_shlib_t '/usr/lib/wine-wow64/.+\.so'
fcontext -a -t textrel_shlib_t '/usr/lib/wine-wow64/.+-windows/.+'
REGELS
    # Luid stoppen als het toch niet klopt: anders werken 32-bits Windows-programma's stilletjes niet.
    for f in /usr/lib64/wine-wow64/wine/i386-windows/ntdll.dll /usr/lib64/wine-wow64/wine/x86_64-windows/ntdll.dll \
        /usr/lib64/wine-wow64/wine/i386-windows/appwiz.cpl; do
        if [ -e "$f" ] && ! matchpathcon "$f" | grep -q textrel_shlib_t; then
            echo "LET OP: $f krijgt niet het SELinux-label textrel_shlib_t: $(matchpathcon "$f")" >&2
            exit 1
        fi
    done
fi

# Apps als Flatpak, niet als pakket in BugOS zelf (wens van de eigenaar, 2026-11-16): alles wat je in de Winkel
# onder 'Mijn apps' ziet, moet je kunnen verwijderen, daar en in Instellingen > Apps. Een pakket in het beeld van BugOS
# kun je niet los verwijderen (het systeem is 'onbreekbaar glas'), een Flatpak wel, en later weer installeren.
# Daarom zitten Firefox en Steam niet meer in het beeld (Firefox stond in packages.txt, Steam werd hier met
# 'dnf5 install steam' toegevoegd); bugos-first-boot zet ze na het installeren klaar als Flatpak van Flathub
# (/usr/share/bugos/standaard-apps.txt), en onthoudt wat je daarna zelf verwijdert.
# Voor Steam als Flatpak blijft steam-devices (packages.txt): de udev-regels voor controllers horen op de computer
# zelf, niet in de Flatpak-doos. Game-modus werkt via de GameMode-portal, de FPS-teller via de MangoHud-uitbreiding
# (bugos-flatpak-style).
#
# Brengt de basis zelf een app mee die ook in de Winkel staat, dan gaat dat pakket er hier ook uit, zodat de app niet
# als 'hoort bij BugOS zelf' (niet te verwijderen) in de Winkel staat. Per regel: pakket, Flathub-id, en of BugOS de
# Flatpak dan klaarzet (ja: je had die app, dus je houdt hem; nee: BugOS heeft er zelf iets voor).
# Zelfde aanpak als bij Discover hierboven: alleen als het pakket er is, en zonder --nodeps. Maar heeft iets anders
# het pakket nodig (rpm -e --test mislukt), dan blijft het staan en gaat de bouw door: een app die blijft, is beter
# dan een beeld dat niet bouwt. De Winkel laat zo'n app dan niet in 'Mijn apps' zien (bugos_apps.mijn_apps_ids),
# zodat daar nooit een app zonder 'Verwijderen' staat.
WINKEL_PAKKETTEN=(
    # kinoite-main brengt Firefox mee, met firefox-langpacks erbij. Die heeft Firefox nodig: dus samen weg
    # (anders weigert rpm -e --test, en had je twee Firefoxen: het pakket en de Flatpak). Komma = samen.
    # 'nee': je kiest je browser zelf in Welkom (bugos-browser); bugos-first-boot zet Firefox alleen terug voor wie
    # BugOS al had (toen zat Firefox erin).
    "firefox,firefox-langpacks org.mozilla.firefox nee"
    "steam com.valvesoftware.Steam ja"
    # Filelight zit in de basis (Kinoite 44), maar is verborgen: Bestanden laat zelf zien wat de meeste ruimte
    # inneemt. Wie hem toch wil, haalt hem uit de Winkel (en kan hem dan ook weer verwijderen).
    "filelight org.kde.filelight nee"
    # Niet zeker of de basis deze meebrengt; is het zo, dan worden ze een Flatpak die je houdt.
    "kcalc org.kde.kcalc ja"
    "elisa-player org.kde.elisa ja"
    "marble org.kde.marble ja"
    "gwenview org.kde.gwenview ja"
    "okular org.kde.okular ja"
)
STANDAARD_APPS=/usr/share/bugos/standaard-apps.txt
for regel in "${WINKEL_PAKKETTEN[@]}"; do
    read -r pakketten app_id klaarzetten <<<"$regel"
    # Het eerste pakket is de app zelf; de rest (na een komma) hoort erbij en gaat mee weg, als het er is.
    pakket="${pakketten%%,*}"
    rpm -q "$pakket" >/dev/null 2>&1 || continue
    weg=()
    IFS=, read -r -a alle <<<"$pakketten"
    for p in "${alle[@]}"; do
        if rpm -q "$p" >/dev/null 2>&1; then weg+=("$p"); fi
    done
    if rpm -e --test "${weg[@]}" >/dev/null 2>&1; then
        rpm -e "${weg[@]}"
        echo "Winkel: pakket $pakket weg; $app_id komt als Flatpak (klaarzetten: $klaarzetten)"
        if [ "$klaarzetten" = ja ] && ! grep -qx "$app_id" "$STANDAARD_APPS"; then
            printf '# Zat in de basis als pakket %s (build.sh): nu een Flatpak die je kunt verwijderen.\n%s\n' \
                "$pakket" "$app_id" >>"$STANDAARD_APPS"
        fi
    else
        echo "LET OP: pakket $pakket kan niet weg (iets anders heeft het nodig); $app_id blijft een deel van BugOS zelf."
    fi
done

# 3. BugOS is een eigen systeem, net als Bazzite (naam, logo, ondertekende updates): zie system.sh.
# shellcheck source=build_files/system.sh
. /ctx/system.sh

# 4. BugOS-stijl als standaard voor nieuwe gebruikers: zie style.sh.
# shellcheck source=build_files/style.sh
. /ctx/style.sh

# 5. Bestandstypes koppelen: .exe -> bugos-exe, .rpm/.deb -> bugos-package.
update-desktop-database /usr/share/applications || true

# 6. Diensten aanzetten.
systemctl enable bugos-first-boot.service
# Het vangnet voor de standaard-apps: zonder internet bij de eerste start later nog eens (zie de timer zelf).
systemctl enable bugos-first-boot.timer
# Geen gebruiker na het installeren? Dan alsnog KDE's assistent om er een te maken.
systemctl enable bugos-user-check.service
# De systeemdelen (wortel, /boot, EFI) niet als volle, rode schijven in KDE-bestandsvensters (B-06).
systemctl enable bugos-hide-system-drives.service
# Engels als standaard, maar internationaal (dag/maand, 24 uur, A4) als de computer niet in de VS staat.
systemctl enable bugos-taal-standaard.service
# Updates: BugOS regelt dit zelf (geen uupd van Universal Blue).
#  - het systeem: rpm-ostree haalt de nieuwe BugOS op de achtergrond op en zet
#    hem klaar ("stage"); hij wordt actief bij de volgende keer opstarten.
#  - de apps (Flatpak): bugos-update-apps.timer, elke dag.
#  bugos-updates auto|hand zet ze allebei aan of uit.
if grep -q '^#\?AutomaticUpdatePolicy=' /etc/rpm-ostreed.conf 2>/dev/null; then
    sed -i 's|^#\?AutomaticUpdatePolicy=.*|AutomaticUpdatePolicy=stage|' /etc/rpm-ostreed.conf
else
    printf '[Daemon]\nAutomaticUpdatePolicy=stage\n' >>/etc/rpm-ostreed.conf
fi
systemctl enable rpm-ostreed-automatic.timer bugos-update-apps.timer
systemctl enable podman.socket || true
# Elke gebruiker: dagelijks kijken of er een update is (doet alleen iets bij "zelf updaten").
systemctl --global enable bugos-updatecheck.timer
# Programma's uit een .rpm/.deb (in hun doosje) ook bijwerken, bij "Updates vanzelf" (U465).
systemctl --global enable bugos-update-doosjes.timer

# 7. Standaard: updates automatisch (de gebruiker kan dit omzetten).
mkdir -p /etc/bugos
echo "UPDATES=auto" >/etc/bugos/updates.conf

# Opruimen zodat er geen extra softwarebronnen aan blijven staan.
dnf5 clean all
rm -rf /var/lib/dnf /run/dnf
