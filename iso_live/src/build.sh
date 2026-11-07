#!/usr/bin/bash
# BugOS live-USB klaarmaken (draait tijdens het bouwen van de ISO).
# Gebaseerd op het voorbeeld van Titanoboa (Universal Blue, Apache-2.0).

set -exo pipefail

IMAGE_REF="${IMAGE_REF:?}"
BUGOS_VARIANT="${BUGOS_VARIANT:-main}"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

mkdir -p "$(realpath /root)"
# bwrap/podman willen hierin schrijven tijdens de bouw.
mount -o remount,rw /proc/sys || true

# ---------------------------------------------------------------------------
# 1. BugOS zelf op de stick zetten.
#    Vroeger haalde het installatieprogramma BugOS tijdens het installeren van
#    internet. Dat werkte niet zonder internet, niet zolang het pakket op
#    GitHub privé is, en het duurde lang. Nu zit BugOS zelf op de stick en
#    installeert het programma vanaf daar.
#    Hoe: als "OCI-map" (de ingepakte lagen, precies zoals ze in GitHub
#    Packages staan) in /var/lib/bugos-stick/bugos. Het installatieprogramma
#    leest die rechtstreeks (ostreecontainer --transport=oci).
#    Waarom niet uitgepakt in de containeropslag (zoals Bazzite)?
#    BugOS haalt bestanden van de fundering (Fedora Kinoite) weg; die "verwijderd"-merktekens
#    (whiteouts) kan de opslag binnen deze bouwstap niet aanmaken ("open
#    /etc/.wh.bazaar: invalid argument"). Een OCI-map wordt niet uitgepakt,
#    dus dat probleem bestaat dan niet. Nadeel: de stick wordt een paar GB
#    groter, omdat de ingepakte lagen niet met de live-omgeving gedeeld worden.
#    Het wachtwoord voor GitHub Packages komt als "secret" binnen (alleen
#    tijdens het bouwen, het komt niet in de ISO): zie iso_live/Containerfile.
# ---------------------------------------------------------------------------
STICK_OCI=/var/lib/bugos-stick/bugos
SKOPEO_ARGS=()
if [ -s /run/secrets/ghcr ]; then
    SKOPEO_ARGS+=(--src-authfile /run/secrets/ghcr)
fi
# IMAGE_SOURCE (alleen voor lokaal testen): haal hem uit een andere opslagplaats,
# bijvoorbeeld een eigen registry op localhost:5000 (dan IMAGE_SOURCE_TLS=false).
# In iso.yml niet gebruikt: daar is de bron gewoon IMAGE_REF.
BRON="${IMAGE_SOURCE:-${IMAGE_REF%:*}}"
if [ "${IMAGE_SOURCE_TLS:-true}" = false ]; then
    SKOPEO_ARGS+=(--src-tls-verify=false)
fi
# Precies dezelfde versie als waar de live-omgeving op gebouwd is (IMAGE_DIGEST,
# door iso.yml doorgegeven). Anders kan er tussendoor een nieuwere BugOS op
# GitHub komen, en installeer je iets anders dan je op de stick probeerde.
if [ -n "${IMAGE_DIGEST:-}" ]; then
    BRON_REF="${BRON}@${IMAGE_DIGEST}"
else
    BRON_REF="${BRON}:${IMAGE_REF##*:}"
fi
rm -rf "$STICK_OCI"
mkdir -p "$(dirname "$STICK_OCI")"
skopeo copy "${SKOPEO_ARGS[@]}" "docker://${BRON_REF}" "oci:${STICK_OCI}"
# Controle: kan het installatieprogramma hem lezen, en is het een bootc-beeld?
skopeo inspect "oci:${STICK_OCI}" --format '{{index .Labels "containers.bootc"}}' | grep -qx 1
du -sh "$STICK_OCI"

# ---------------------------------------------------------------------------
# 2. Kernel: voor Secure Boot moet de live-stick een door Fedora ondertekende
#    kernel hebben. Is dat al zo, dan laten we hem staan.
# ---------------------------------------------------------------------------
if [ "$(rpm -q --qf '%{VENDOR}' kernel-core)" != "Fedora Project" ]; then
    kernel_pkgs=(kernel kernel-core kernel-modules kernel-modules-core kernel-modules-extra)
    dnf -y versionlock delete "${kernel_pkgs[@]}" kernel-devel kernel-devel-matched || true
    dnf --setopt=protect_running_kernel=False -y remove "${kernel_pkgs[@]}" || true
    (cd /usr/lib/modules && rm -rf -- ./*)
    dnf -y --repo fedora,updates --setopt=tsflags=noscripts install kernel kernel-core
    depmod "$(find /usr/lib/modules -maxdepth 1 -mindepth 1 -type d -printf '%P\n' | head -1)"
fi
dnf install -yq nvidia-gpu-firmware || true

# Live-opstartbestand (initramfs) maken.
dnf install -y dracut-live
kernel=$(find /usr/lib/modules -maxdepth 1 -mindepth 1 -type d -printf '%P\n' | head -1)
DRACUT_NO_XATTR=1 dracut -v --force --zstd --reproducible --no-hostonly \
    --add "dmsquash-live dmsquash-live-autooverlay" \
    "/usr/lib/modules/${kernel}/initramfs.img" "${kernel}"

# Live-gebruiker die vanzelf inlogt, in het KDE-bureaublad.
dnf install -y livesys-scripts
sed -i "s/^livesys_session=.*/livesys_session=kde/" /etc/sysconfig/livesys
systemctl enable livesys.service livesys-late.service

# ---------------------------------------------------------------------------
# 3. Het installatieprogramma (Anaconda, de nieuwe web-versie).
# ---------------------------------------------------------------------------
dnf versionlock clear -qy || true
dnf install -qy --allowerasing firefox anaconda-live anaconda-webui \
    libblockdev-btrfs libblockdev-lvm libblockdev-dm yad jq
mkdir -p /var/lib/rpm-state

# shellcheck source=/dev/null
. /etc/os-release
mkdir -p /etc/anaconda/profile.d
cat >/etc/anaconda/profile.d/bugos.conf <<EOF
# BugOS: zo min mogelijk vragen tijdens het installeren.
[Profile]
profile_id = bugos
# Alles wat we hier niet zelf zeggen, zoals bij Fedora Kinoite (de fundering
# van BugOS): een alleen-lezen systeem met btrfs.
base_profile = fedora-kinoite

[Profile Detection]
os_id = ${ID}

[Network]
default_on_boot = FIRST_WIRED_WITH_LINK

[Bootloader]
efi_dir = fedora
menu_auto_hide = True

[Storage]
default_scheme = BTRFS
btrfs_compression = zstd:1
default_partitioning =
    /     (min 1 GiB, max 70 GiB)
    /home (min 500 MiB, free 50 GiB)
    /var  (btrfs)

# De pagina "Date and time" blijft zichtbaar: BugOS is voor de hele wereld,
# dus de gebruiker kiest zelf zijn tijdzone (er staat er geen vast in de
# kickstart hieronder).

[Localization]
# Niet via internet raden: dat vraagt het aan een Fedora-server, en BugOS
# verzamelt niets. BugOS begint in het Engels; de gebruiker kiest op de eerste
# pagina zelf een andere taal (alle talen van Fedora zijn er).
use_geolocation = False

[Timezone]
geolocation_provider =
EOF

echo "BugOS release ${VERSION_ID:-1}" >/etc/system-release

# Het venster heette "Anaconda Web UI".
sed -i 's|<title translate>Anaconda Web UI</title>|<title>Install BugOS</title>|' \
    /usr/share/cockpit/anaconda-webui/index.html

# Nederlandse teksten van het installatieprogramma: waar "Fedora" in staat
# wordt "BugOS", en een paar zinnen die nog niet vertaald waren. We zetten
# extra regels achteraan in het woordenboek; de laatste telt.
python3 - <<'PY'
import gzip
import json

pad = "/usr/share/cockpit/anaconda-webui/po.nl.js.gz"
tekst = gzip.open(pad, "rt", encoding="utf-8").read()
extra = {
    "Welcome to Fedora Linux": "Welkom bij BugOS",
    "About Fedora": "Over BugOS",
    "About": "Over",
    "Reinstall Fedora": "BugOS opnieuw installeren",
    "Fedora linux requires at least $0 of disk space.": "BugOS heeft minstens $0 schijfruimte nodig.",
    "Share disk with other operating systems": "De schijf delen met Windows of een ander systeem",
    "Share disk with other operating systems: $0": "De schijf delen met: $0",
    "Use local account": "Account op deze computer",
    "A standard user account with admin access for making system-wide changes.":
        "Een gewoon account dat ook de computer mag instellen.",
    "Installation of the system failed": "Het installeren is niet gelukt",
    "Not enough available free space": "Niet genoeg vrije ruimte",
    "$0 is required, but only $1 is available.": "Er is $0 nodig, maar er is maar $1 vrij.",
    "Insufficient disk space": "Niet genoeg schijfruimte",
    "Please select at least one disk to continue": "Kies minstens één schijf om verder te gaan",
    "The Anaconda installation has stopped unexpectedly.": "Het installatieprogramma is onverwacht gestopt.",
}
eind = tekst.rstrip().rfind("\n});")
assert eind > 0, "po.nl.js heeft een onbekende vorm"
nieuw = "".join(",\n " + json.dumps(k, ensure_ascii=False) + ": [null, " + json.dumps(v, ensure_ascii=False) + "]"
                for k, v in extra.items())
tekst = tekst[:eind] + nieuw + tekst[eind:]
with gzip.open(pad, "wt", encoding="utf-8") as f:
    f.write(tekst)
PY
# Kies je in het installatieprogramma Engels, dan gebruikt het de Engelse
# zinnen uit het programma zelf. Daar ook "Fedora" -> "BugOS" (alleen deze
# zichtbare zinnen; de controles op de systeemnaam in de code blijven heel).
WEBUI_JS=/usr/share/cockpit/anaconda-webui/index.js.gz
zcat "$WEBUI_JS" | sed \
    -e 's/Welcome to Fedora Linux/Welcome to BugOS/g' \
    -e 's/Reinstall Fedora/Reinstall BugOS/g' \
    -e 's/About Fedora/About BugOS/g' \
    -e 's/Fedora linux requires at least/BugOS requires at least/g' \
    | gzip -9 >"$WEBUI_JS.nieuw"
mv "$WEBUI_JS.nieuw" "$WEBUI_JS"
# Het Nederlandse woordenboek gebruikt de Engelse zin als sleutel. Nu de
# Engelse zinnen veranderd zijn, ook de nieuwe sleutels toevoegen.
python3 - <<'PY'
import gzip
import json

pad = "/usr/share/cockpit/anaconda-webui/po.nl.js.gz"
tekst = gzip.open(pad, "rt", encoding="utf-8").read()
extra = {
    "Welcome to BugOS": "Welkom bij BugOS",
    "Reinstall BugOS": "BugOS opnieuw installeren",
    "About BugOS": "Over BugOS",
    "BugOS requires at least $0 of disk space.": "BugOS heeft minstens $0 schijfruimte nodig.",
}
eind = tekst.rstrip().rfind("\n});")
assert eind > 0, "po.nl.js heeft een onbekende vorm"
nieuw = "".join(",\n " + json.dumps(k, ensure_ascii=False) + ": [null, " + json.dumps(v, ensure_ascii=False) + "]"
                for k, v in extra.items())
with gzip.open(pad, "wt", encoding="utf-8") as f:
    f.write(tekst[:eind] + nieuw + tekst[eind:])
PY
# Bewaakt dat er na de vervanging in onze eigen regels geen Fedora meer staat.
if zcat /usr/share/cockpit/anaconda-webui/po.nl.js.gz | grep -q '\[null, "[^"]*Fedora'; then
    echo "Let op: er staat nog 'Fedora' in de Nederlandse teksten van het installatieprogramma" >&2
fi

# Waarschuwing voor BitLocker, vóórdat het installatieprogramma opent.
# Dit zat eerst in de kickstart, maar daar kwam het venster niet op het
# scherm en de controle zag de schijven niet (lsblk --json zet partities
# "onder" de schijf). Nu een klein programma dat als de live-gebruiker draait.
install -Dm0755 "$SRC/bugos-installeren" /usr/bin/bugos-installeren

# Wat het installatieprogramma doet.
mkdir -p /usr/share/anaconda/post-scripts
cat >>/usr/share/anaconda/interactive-defaults.ks <<EOF

%pre
mkdir -p /tmp/bugos_logs
%end

# Standaard Engels met het Amerikaanse toetsenbord. In het installatieprogramma
# kiest de gebruiker zelf een andere taal, een ander toetsenbord en de tijdzone.
lang en_US.UTF-8
keyboard --vckeymap=us --xlayouts='us'

%onerror
tail -n 60 /tmp/anaconda.log | run0 --user=liveuser --setenv=WAYLAND_DISPLAY=wayland-0 --setenv=DISPLAY=:0 \\
    yad --timeout=0 --text-info --no-buttons --width=640 --height=420 \\
    --title=BugOS --text="Installing BugOS did not work. If this happened before copying started, nothing on your computer was changed. Take a photo of this screen and report it at github.com/253UgurSahin/BugOS/issues\n\nThat page is public: check the photo for your name, your computer's name or other personal details first."
%end

# BugOS vanaf de stick zelf installeren (zie stap 1): geen internet nodig.
ostreecontainer --url=/var/lib/bugos-stick/bugos --transport=oci --no-signature-verification
%include /usr/share/anaconda/post-scripts/bugos-updates.ks
EOF

# Na het installeren: updates voortaan van GitHub halen. BugOS kwam van de
# stick (OCI-map); zonder dit zou de computer later in die map op de stick
# naar updates zoeken. bootc switch --mutate-in-place past alleen
# die verwijzing aan, er wordt niets gedownload.
cat >/usr/share/anaconda/post-scripts/bugos-updates.ks <<EOF
%post --erroronfail --log=/tmp/bugos_logs/bootc-switch.log
bootc switch --mutate-in-place --transport registry ${IMAGE_REF}
%end
EOF

# Nvidia-versie: de stuurprogramma's zijn ondertekend met de sleutel van
# Universal Blue. Die moet bij Secure Boot één keer worden toegevoegd.
if [ "$BUGOS_VARIANT" = nvidia ]; then
    mkdir -p /usr/share/bugos
    # Vaste versie (commit) en controlegetal: de pc gaat deze sleutel vertrouwen, dus nooit
    # zomaar "wat er nu op main staat". Nieuwe sleutel bij Universal Blue? Dan hier beide bijwerken.
    SB_COMMIT=20fce9fe76de494ff901f017a50d6f4dfc1661e0
    SB_SHA256=4e5c68474cb133fd8984d9599762cece9100c3e6cd8a9709aeaabd85dd9e70d1
    curl -fsSL --retry 3 -o /usr/share/bugos/sb_pubkey.der \
        "https://github.com/ublue-os/akmods/raw/${SB_COMMIT}/certs/public_key.der"
    echo "${SB_SHA256}  /usr/share/bugos/sb_pubkey.der" | sha256sum -c -
    cat >>/usr/share/anaconda/post-scripts/bugos-updates.ks <<'EOF'
%post --nochroot --log=/tmp/bugos_logs/secureboot.log
if [ -d /sys/firmware/efi ] && mokutil --sb-state 2>/dev/null | grep -q enabled; then
    if printf 'bugos\nbugos\n' | mokutil --import /usr/share/bugos/sb_pubkey.der; then
        run0 --user=liveuser --setenv=WAYLAND_DISPLAY=wayland-0 --setenv=DISPLAY=:0 \
            yad --on-top --width=560 --title=BugOS --button=OK:0 \
            --text="<b>One more step when the computer restarts</b>\n\nYour computer will show a blue screen (MOK Manager). Choose:\n  1. <b>Enroll MOK</b>\n  2. <b>Continue</b>\n  3. <b>Yes</b>\n  4. Type the password: <b>bugos</b>\n  5. <b>Reboot</b>\n\nThis is needed so your Nvidia graphics card works properly." || true
    else
        echo "BugOS: mokutil --import lukte niet" >&2
        run0 --user=liveuser --setenv=WAYLAND_DISPLAY=wayland-0 --setenv=DISPLAY=:0 \
            yad --on-top --width=560 --title=BugOS --button=OK:0 \
            --text="<b>The Nvidia key could not be added</b>\n\nBugOS is installed, but with Secure Boot on, the Nvidia driver may not start.\nTurn Secure Boot off in the BIOS/UEFI settings, or open 'Something is not working' after the restart." || true
    fi
fi
%end
EOF
fi

# ---------------------------------------------------------------------------
# 4. De live-omgeving zelf.
# ---------------------------------------------------------------------------
# Welkomstscherm met "Proberen" of "Installeren".
install -Dm0644 "$SRC/bugos-live.desktop" /etc/xdg/autostart/bugos-live.desktop
install -Dm0755 "$SRC/bugos-live" /usr/bin/bugos-live

# Precies één installeer-knop, en die heet BugOS.
# De live-scripts van Fedora (livesys-kde) zetten liveinst.desktop
# ("Install to Hard Drive", met een leeg pictogram) vanzelf op het bureaublad
# en in het menu. In plaats van er een tweede knop naast te zetten, maken we
# van dát bestand de BugOS-knop. Zo staat er altijd maar één.
# 0755: livesys kopieert hem naar het bureaublad; met het uitvoerbit vraagt
# KDE niet of je deze "onbekende starter" wel vertrouwt.
install -Dm0755 "$SRC/bugos-installeren.desktop" /usr/share/applications/liveinst.desktop
rm -f /usr/share/applications/bugos-installeren.desktop /etc/skel/Desktop/bugos-installeren.desktop
# Anaconda's eigen bureaubladhulpje (doet op deze stick niets) en BugOS'
# automatisch openen van interne schijven: dat laatste kan het verkleinen of
# wissen van Windows laten mislukken ("apparaat bezet"). Op de stick dus niet.
rm -f /etc/xdg/autostart/liveinst-setup.desktop /etc/xdg/autostart/bugos-schijven-openen.desktop
# Geen vraag om een "portemonnee"-wachtwoord (KWallet) op de stick.
printf '[Wallet]\nEnabled=false\n' >/etc/xdg/kwalletrc

# Dingen die op een live-stick niet horen te draaien.
# Updates en het klaarzetten van apps zouden op de stick honderden MB binnen-
# halen, in het geheugen (de stick kan niet schrijven). Dat maakt hem traag en
# het geheugen kan vollopen. Na het installeren draaien ze gewoon wel (dit
# geldt alleen voor de stick).
for s in rpm-ostreed-automatic.timer bugos-apps-bijwerken.timer uupd.timer rpm-ostree-countme.service \
    bootloader-update.service bugos-eerste-start.service \
    flatpak-preinstall.service brew-setup.service brew-update.timer brew-upgrade.timer \
    rpm-ostree-countme.timer ublue-system-setup.service tailscaled.service; do
    systemctl disable "$s" 2>/dev/null || true
done
systemctl --global disable bugos-updatecheck.timer 2>/dev/null || true
systemctl --global disable ublue-user-setup.service 2>/dev/null || true

# Taal op de stick: Engels, met het Amerikaanse toetsenbord. Alle BugOS-
# schermen zijn er ook in andere talen (zie docs/VERTALEN.md); in het
# installatieprogramma kies je zelf de taal en het toetsenbord voor de computer.
echo "LANG=en_US.UTF-8" >/etc/locale.conf
echo "KEYMAP=us" >/etc/vconsole.conf
mkdir -p /etc/X11/xorg.conf.d
cat >/etc/X11/xorg.conf.d/00-keyboard.conf <<'EOF'
Section "InputClass"
    Identifier "system-keyboard"
    MatchIsKeyboard "on"
    Option "XkbLayout" "us"
EndSection
EOF

# Het installatieprogramma in BugOS-kleuren, met het lieveheersbeestje.
# Het programma (Anaconda WebUI) haalt zijn logo en kleuren uit de
# "branding" van Cockpit. Zonder eigen map kreeg je die van Fedora: blauw,
# met het Fedora-logo. /etc/cockpit/branding wordt als eerste gelezen,
# wat er ook in os-release staat.
[ -f /usr/share/bugos/merk/merk-donker-256.png ] || {
    echo "Basisbeeld te oud: /usr/share/bugos/merk ontbreekt (eerst BugOS opnieuw bouwen)" >&2
    exit 1
}
BRANDING=/etc/cockpit/branding
mkdir -p "$BRANDING"
install -m0644 /usr/share/bugos/merk/merk-donker-256.png "$BRANDING/logo.png"
install -m0644 /usr/share/bugos/merk/merk-256.png "$BRANDING/apple-touch-icon.png"
install -m0644 /usr/share/bugos/merk/merk-256.png "$BRANDING/favicon.ico"
cat >"$BRANDING/branding.css" <<'EOF'
/* BugOS: het installatieprogramma in de huisstijl (docs/HUISSTIJL.md). */
#badge {
    inline-size: 80px;
    block-size: 80px;
    background-image: url("logo.png");
    background-size: contain;
    background-repeat: no-repeat;
}

#brand::before {
    content: "BugOS";
}

.anaconda {
    /* De balk bovenaan: rustig donker (inkt), zodat rood alleen voor de knop is. */
    --brand-default-light: #2A2B31;
    --brand-default: #16171C;
    --brand-default-dark: #0E0F13;

    .logo {
        background-image: url("logo.png");
        /* Het programma maakt het logo normaal wit; ons beestje blijft in kleur. */
        filter: none;
        mix-blend-mode: normal;
    }
}

:not(.pf-v6-theme-dark) .anaconda {
    /* Knoppen en keuzes: lieveheersbeestjesrood. */
    --pf-t--global--color--brand--default: #DE2F3E;
    --pf-t--global--color--brand--hover: #C41D3A;
}

.pf-v6-theme-dark .anaconda {
    --pf-t--global--color--brand--default: #EE3F49;
    --pf-t--global--color--brand--hover: #DE2F3E;
}

/* Weg met de Fedora-dingen: de QR-code en link naar het Fedora-forum op het
   laatste scherm, "Fout melden" (Red Hat Bugzilla) en "Over Fedora" in het
   menu, en het vinkje voor een root-account (heeft een gewone gebruiker niet
   nodig). */
.anaconda .feedback-section {
    display: none;
}
#about-modal-dropdown-item-report,
#about-modal-dropdown-item-about,
.pf-v6-c-menu__list-item:has(#about-modal-dropdown-item-report),
.pf-v6-c-menu__list-item:has(#about-modal-dropdown-item-about) {
    display: none !important;
}
.anaconda .pf-v6-c-form__section:has(#anaconda-screen-accounts-root-account-enable-root-account) {
    display: none;
}

/* Onze letters (zitten in BugOS). */
.anaconda {
    --pf-t--global--font--family--body: "Inter", sans-serif;
    --pf-t--global--font--family--heading: "Funnel Display", "Inter", sans-serif;
}
EOF

# Voor de zekerheid ook op de plek die Cockpit op naam van het systeem kiest
# (ID uit os-release, bij ons "bugos"), mocht /etc/cockpit/branding niet
# gelezen worden.
mkdir -p "/usr/share/cockpit/branding/${ID}"
cp -a "$BRANDING"/. "/usr/share/cockpit/branding/${ID}/"

# Het installatieprogramma heeft veel ruimte nodig in /var/tmp: het zet elk
# onderdeel van BugOS daar eerst helemaal neer. 75% van het geheugen, zodat
# het ook op een pc met weinig geheugen lukt.
find /var/tmp -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null || true
mkdir -p /var/tmp
cat >/etc/systemd/system/var-tmp.mount <<'EOF'
[Unit]
Description=Larger temporary folder for the live USB

[Mount]
What=tmpfs
Where=/var/tmp
Type=tmpfs
Options=size=75%%,nr_inodes=1m

[Install]
WantedBy=local-fs.target
EOF
systemctl enable var-tmp.mount

# ---------------------------------------------------------------------------
# 5. Wat Titanoboa/image-builder nodig heeft om een ISO te maken.
# ---------------------------------------------------------------------------
dnf install -y grub2-efi-x64-cdboot xorriso isomd5sum
mkdir -p /boot/efi
cp -av /usr/lib/efi/*/*/EFI /boot/efi/
cp -v /boot/efi/EFI/fedora/grubx64.efi /boot/efi/EFI/BOOT/fbx64.efi || true
rm -f /etc/localtime
systemd-firstboot --timezone UTC
mkdir -p /usr/lib/bootc-image-builder
cp "$SRC/iso.yaml" /usr/lib/bootc-image-builder/iso.yaml
