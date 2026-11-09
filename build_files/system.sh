#!/usr/bin/bash
# BugOS - bouwscript, stap 3: BugOS als eigen systeem (naam, logo, updates)
# =========================================================================
# Wordt ingelezen door build.sh (". /ctx/system.sh"), niet los gedraaid: het
# gebruikt BUGOS_VARIANT en BUGOS_VERSION van build.sh, en zet BEELD_ID.

# 3. BugOS is een eigen systeem, net als Bazzite.
#    De fundering is kaal Fedora Kinoite van Universal Blue (zie Containerfile);
#    alles wat daar "Fedora" of "Kinoite" heet, wordt hier BugOS. Ook de ID:
#    ID=bugos, met ID_LIKE=fedora zodat programma's weten dat BugOS op Fedora
#    lijkt (dnf, fwupd en het installatieprogramma kijken daarnaar).
#    VERSION_ID (bijv. 44) blijft het Fedora-nummer: dnf en Flatpak hebben dat nodig.

# Bij Fedora is /usr/lib/os-release een verwijzing naar een bestand van het
# pakket fedora-release. Eerst een echt eigen bestand maken, anders passen we
# straks het bestand van Fedora aan in plaats van dat van BugOS.
if [ -L /usr/lib/os-release ]; then
    cp --remove-destination "$(readlink -f /usr/lib/os-release)" /usr/lib/os-release
fi

if [ "$BUGOS_VARIANT" = nvidia ]; then
    BEELD_ID=bugos-nvidia
else
    BEELD_ID=bugos
fi

# os_zet SLEUTEL WAARDE: zet een regel in os-release (vervangen of erbij).
os_zet() {
    if grep -q "^$1=" /usr/lib/os-release; then
        sed -i "s|^$1=.*|$1=$2|" /usr/lib/os-release
    else
        echo "$1=$2" >>/usr/lib/os-release
    fi
}
# De velden die programma's laten zien ("Over dit systeem", hostnamectl,
# fastfetch, lsb_release) en de namen waarop andere programma's het systeem
# herkennen.
os_zet NAME '"BugOS"'
os_zet ID bugos
os_zet ID_LIKE '"fedora"'
os_zet PRETTY_NAME "\"BugOS ${BUGOS_VERSION}\""
os_zet VERSION "\"${BUGOS_VERSION}\""
os_zet VARIANT '"BugOS"'
os_zet VARIANT_ID "${BEELD_ID}"
os_zet VERSION_CODENAME '""'
os_zet CPE_NAME "\"cpe:/o:bugos:bugos:${BUGOS_VERSION}\""
os_zet HOME_URL '"https://github.com/253UgurSahin/BugOS"'
os_zet DOCUMENTATION_URL '"https://github.com/253UgurSahin/BugOS/tree/main/docs"'
os_zet SUPPORT_URL '"https://github.com/253UgurSahin/BugOS/issues"'
os_zet BUG_REPORT_URL '"https://github.com/253UgurSahin/BugOS/issues"'
os_zet LOGO bugos-logo
os_zet DEFAULT_HOSTNAME '"bugos"'
os_zet IMAGE_ID "\"${BEELD_ID}\""
os_zet IMAGE_VERSION "\"${BUGOS_VERSION}\""
os_zet OSTREE_VERSION "'${BUGOS_VERSION}'"
os_zet BUILD_ID "\"${BUGOS_VERSION}\""
os_zet ANSI_COLOR '"0;38;2;222;47;62"'
os_zet BUGOS_VARIANT "\"${BUGOS_VARIANT}\""
# Fedora's einddatum en Red Hat-meldplekken horen niet bij BugOS. (PLATFORM_ID
# blijft: dnf heeft die nodig.)
sed -i -e '/^SUPPORT_END=/d' -e '/^REDHAT_/d' /usr/lib/os-release
cat /usr/lib/os-release

mkdir -p /usr/share/bugos
cat >/usr/share/bugos/image-info.json <<EOF
{
  "naam": "BugOS",
  "variant": "${BUGOS_VARIANT}",
  "versie": "${BUGOS_VERSION}"
}
EOF

# Logo ook beschikbaar maken als gewoon pictogram.
install -Dm0644 /usr/share/bugos/logo.svg /usr/share/icons/hicolor/scalable/apps/bugos-logo.svg
install -Dm0644 /usr/share/bugos/logo.svg /usr/share/pixmaps/bugos-logo.svg

# 3b. Wat de gebruiker verder nog als Fedora, Kinoite of Universal Blue zou
#     zien, wordt BugOS.

# /etc/system-release was een verwijzing naar "Fedora release 44". Het
# opstartprogramma (bootupd) noemt de opstartkeuze in het BIOS/UEFI-menu
# daarnaar, dus daar stond "Fedora". Nu een eigen bestand: "BugOS release 44".
# (/etc/fedora-release blijft Fedora, voor programma's die dat nodig hebben.)
rm -f /etc/system-release
printf 'BugOS release %s\n' "$(. /usr/lib/os-release && echo "${VERSION_ID}")" >/etc/system-release

# De "eerste keer opstarten"-assistent van KDE (plasma-setup) maakt zelf een
# gebruiker en zet het thema van Fedora neer. Bij BugOS maakt het
# installatieprogramma de gebruiker al, en BugOS Welkom doet de rest.
# Dit bestand betekent voor plasma-setup: "al gedaan".
touch /etc/plasma-setup-done

# Het "Welcome Center" van KDE (met "Welcome to Fedora" en het Fedora-logo)
# verschijnt bij de eerste keer inloggen. BugOS heeft een eigen welkomstapp
# (bugos-welcome), dus deze gaat er helemaal uit. Geen ander pakket heeft hem
# nodig (alleen plasma-workspace "raadt hem aan").
# rpm -e in plaats van dnf remove: dan gaan er niet stilletjes andere
# pakketten mee die toevallig alleen hierdoor waren binnengekomen.
if rpm -q plasma-welcome >/dev/null 2>&1; then
    rpm -e plasma-welcome
fi
rm -rf /usr/share/plasma/plasma-welcome

# fastfetch kiest zijn logo op ID; bugos kent hij niet. Dus geven we hem zelf
# een instelling met het lieveheersbeestje (fastfetch leest /etc/xdg).
mkdir -p /etc/xdg/fastfetch
cat >/usr/share/bugos/fastfetch-logo.txt <<'EOF'
$1      ▄▄▄
$1    ▄█▀ ▀█▄
$2  ▄████$1█$2████▄
$2 ██ ▀▀ $1█$2 ▀▀ ██
$2 ████▄▄$1█$2▄▄████
$2  ▀████$1█$2████▀
$2     ▀▀$1▀$2▀▀
EOF
cat >/etc/xdg/fastfetch/config.jsonc <<'EOF'
{
    "logo": {
        "type": "file",
        "source": "/usr/share/bugos/fastfetch-logo.txt",
        "color": { "1": "white", "2": "red" }
    },
    "modules": [
        "title", "separator",
        { "type": "os", "format": "{pretty-name}" },
        "kernel", "uptime", "packages", "shell", "de", "terminal",
        "cpu", "gpu", "memory", "disk", "break", "colors"
    ]
}
EOF

# Ondertekende updates. GitHub ondertekent elke BugOS met cosign (build.yml,
# "Ondertekenen"). Staat de bijbehorende openbare sleutel in deze repo
# (system_files/etc/pki/containers/bugos.pub), dan installeren computers alleen
# nog een update met die handtekening: wie stiekem een ander beeld in GitHub
# Packages zet, komt er niet in. Zonder sleutel (nog niet ingesteld) blijft
# alles zoals het was; zie docs/ONDERTEKENEN.md.
SLEUTEL=/etc/pki/containers/bugos.pub
if [ -s "$SLEUTEL" ]; then
    BEELD_BRON="ostree-image-signed:docker://ghcr.io/253ugursahin/${BEELD_ID}"
    # Regel voor onze plek in GitHub Packages; de rest van policy.json (ook die van
    # Universal Blue) blijft zoals hij is.
    jq --arg sleutel "$SLEUTEL" '.transports.docker["ghcr.io/253ugursahin"] =
        [{"type": "sigstoreSigned", "keyPath": $sleutel, "signedIdentity": {"type": "matchRepository"}}]' \
        /etc/containers/policy.json >/tmp/policy.json
    install -m0644 /tmp/policy.json /etc/containers/policy.json
    rm -f /tmp/policy.json
    mkdir -p /etc/containers/registries.d
    printf 'docker:\n  ghcr.io/253ugursahin:\n    use-sigstore-attachments: true\n' \
        >/etc/containers/registries.d/bugos.yaml
    systemctl enable bugos-ondertekend.service
else
    BEELD_BRON="ostree-unverified-registry:ghcr.io/253ugursahin/${BEELD_ID}"
    echo "LET OP: geen $SLEUTEL; updates worden niet op een handtekening gecontroleerd (zie docs/ONDERTEKENEN.md)."
fi

# Wat ujust en de andere Universal Blue-hulpjes over "dit systeem" lezen.
# Daar stond kinoite-main; dan zou bijvoorbeeld "ujust rebase-helper" de
# computer naar kaal Kinoite kunnen omzetten.
mkdir -p /usr/share/ublue-os
cat >/usr/share/ublue-os/image-info.json <<EOF
{
  "image-name": "${BEELD_ID}",
  "image-flavor": "${BUGOS_VARIANT}",
  "image-vendor": "253ugursahin",
  "image-ref": "${BEELD_BRON}",
  "image-tag": "latest",
  "base-image-name": "kinoite",
  "fedora-version": "$(. /usr/lib/os-release && echo "${VERSION_ID}")"
}
EOF

# Universal Blue's eigen update-dienst (uupd) en Fedora's rpm-ostree-
# updatemeldingen: BugOS regelt updates zelf (stap 6). Twee dingen die
# tegelijk updaten, zitten elkaar in de weg.
# Ook flatpak-system-update.timer van Universal Blue: BugOS werkt de apps bij met bugos-update-apps.timer, en
# 'Updates zelf doen' zet alleen die uit; anders liepen de app-updates toch elke dag door (U087).
for eenheid in uupd.timer ublue-update.timer flatpak-system-update.timer flatpak-user-update.timer; do
    if [ -e "/usr/lib/systemd/system/$eenheid" ]; then
        systemctl mask "$eenheid"
    fi
done

# De zoekbalk (KRunner): Fedora zet hier zijn eigen keuzes neer. Zonder dat
# bestand gelden de gewone KDE-instellingen.
rm -f /usr/share/kde-settings/kde-profile/default/xdg/krunnerrc

# Firefox: begint niet meer op de Fedora-startpagina, en heet "for BugOS".
# browser.tabs.inTitlebar=0: Firefox krijgt dezelfde vensterbalk als alle andere vensters
# (geen eigen knoppen meer in de tabbalk), zodat het één geheel blijft.
FF=/usr/lib64/firefox
if [ -d "$FF" ]; then
    sed -i -e 's|https://start.fedoraproject.org/|about:home|' -e '/browser.newtabpage.pinned/d' \
        "$FF/browser/defaults/preferences/firefox-redhat-default-prefs.js" || true
    mkdir -p "$FF/distribution"
    cat >"$FF/distribution/distribution.ini" <<'EOF'
[Global]
id=bugos
version=1.0
about=Mozilla Firefox for BugOS

[Preferences]
app.distributor="bugos"
app.distributor.channel="bugos"
browser.tabs.inTitlebar=0
EOF
fi

# Logo's: veel programma's gebruiken vaste bestandsnamen voor "het logo van
# dit systeem" (Over dit systeem, het installatieprogramma, sommige menu's).
# Daar staat het Fedora-logo. Wij leggen er het lieveheersbeestje neer.
MERK=/usr/share/bugos/brand
for png in system-logo.png fedora-logo-sprite.png fedora-logo.png fedora_logo_med.png fedora-logo-small.png; do
    install -Dm0644 "$MERK/mark-256.png" "/usr/share/pixmaps/$png"
done
# De "witte" versie is voor donkere achtergronden: het beestje met lichte kop.
install -Dm0644 "$MERK/mark-dark-256.png" /usr/share/pixmaps/system-logo-white.png
# fedora-logo.svg en fedora_whitelogo.svg zijn (verwijzingen naar) het Fedora-logo.
rm -f /usr/share/pixmaps/fedora-logo.svg /usr/share/pixmaps/fedora_whitelogo.svg
install -Dm0644 "$MERK/logo.svg" /usr/share/pixmaps/fedora-logo.svg
install -Dm0644 "$MERK/logo-white.svg" /usr/share/pixmaps/fedora_whitelogo.svg
# Het algemene "logo van de distributie" (ook voor het pictogram start-here).
install -Dm0644 "$MERK/mark.svg" /usr/share/icons/hicolor/scalable/distributor-logo.svg
install -Dm0644 "$MERK/mark-ink.svg" /usr/share/icons/hicolor/scalable/places/distributor-logo-symbolic.svg

# "Over dit systeem" (KDE Info-centrum): onze naam, versie, logo en website.
# Name en Version moeten er expliciet in: anders pakt KDE ze per regel uit
# Fedora's eigen bestand in kde-profile, en staat er "Fedora 44". Dat
# bestand halen we ook weg, zodat er niets van Fedora kan doorschemeren.
rm -f /usr/share/kde-settings/kde-profile/default/xdg/kcm-about-distrorc
cat >/etc/xdg/kcm-about-distrorc <<EOF
[General]
Name=BugOS
Version=${BUGOS_VERSION}
LogoPath=/usr/share/pixmaps/system-logo.png
Website=https://github.com/253UgurSahin/BugOS
Variant=
EOF
