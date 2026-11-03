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
#    GitHub privé is, en het duurde lang. Nu zit BugOS zelf op de stick (in de
#    containeropslag van de live-omgeving) en installeert het programma vanaf
#    daar. De stick wordt daar nauwelijks groter van: de live-omgeving ÍS al
#    BugOS, en mksquashfs slaat bestanden die precies gelijk zijn maar één
#    keer op.
#    Het wachtwoord voor GitHub Packages komt als "secret" binnen (alleen
#    tijdens het bouwen, het komt niet in de ISO): zie iso_live/Containerfile.
#    Belangrijk:
#    - De opslag staat op de gewone plek (/var/lib/containers/storage), net
#      als bij Aurora en Bazzite. Andere plekken gaven bij hen fouten.
#    - De live-omgeving draait zelf op "overlayfs". Daarop kan de opslag
#      alleen werken met fuse-overlayfs; zonder dat faalt zowel deze stap als
#      het installeren ("'overlay' is not supported over overlayfs").
#    - Start het ingebouwde beeld nooit met "podman run" op de stick: het is
#      alleen bedoeld om te installeren (lezen gaat goed, starten niet).
# ---------------------------------------------------------------------------
rpm -q fuse-overlayfs || {
    echo "fuse-overlayfs ontbreekt: zonder kan BugOS niet vanaf de stick installeren" >&2
    exit 1
}
AUTH_ARGS=()
if [ -s /run/secrets/ghcr ]; then
    AUTH_ARGS=(--authfile /run/secrets/ghcr)
fi
# Precies dezelfde versie als waar de live-omgeving op gebouwd is (IMAGE_DIGEST,
# door iso.yml doorgegeven). Anders kan er tussendoor een nieuwere BugOS op
# GitHub komen: dan installeer je iets anders dan je probeerde, en wordt de
# stick twee keer zo groot (geen gelijke bestanden meer om te delen).
if [ -n "${IMAGE_DIGEST:-}" ]; then
    podman pull "${AUTH_ARGS[@]}" "${IMAGE_REF%:*}@${IMAGE_DIGEST}"
    podman tag "${IMAGE_REF%:*}@${IMAGE_DIGEST}" "$IMAGE_REF"
    [ "$(podman image inspect --format '{{.Digest}}' "$IMAGE_REF")" = "$IMAGE_DIGEST" ]
else
    podman pull "${AUTH_ARGS[@]}" "$IMAGE_REF"
fi
# Controles: de gewone plek, en kan het installatieprogramma hem lezen?
[ "$(podman info --format '{{.Store.GraphRoot}}')" = /var/lib/containers/storage ]
skopeo inspect --raw "containers-storage:${IMAGE_REF}" >/dev/null
podman images

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

[User Interface]
# De pagina "Date and time" (half Engels) slaan we over: de tijdzone staat in
# de kickstart hieronder op Europe/Amsterdam, en de tijd komt van internet.
# (De oude namen "root-password" en "network" bestaan niet in deze versie.)
hidden_webui_pages =
    anaconda-screen-date-time

[Localization]
# Niet via internet raden (dat vraagt het aan een Fedora-server, en kan
# Nederlands overschrijven): BugOS begint in het Nederlands.
use_geolocation = False

[Timezone]
geolocation_provider =
EOF

echo "BugOS release ${VERSION_ID:-1}" >/etc/system-release

# Het venster heette "Anaconda Web UI".
sed -i 's|<title translate>Anaconda Web UI</title>|<title>BugOS installeren</title>|' \
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

# Taal, toetsenbord en tijdzone staan alvast goed voor Nederland.
# us(euro): het gewone Amerikaanse toetsenbord, met het euroteken op AltGr+5.
lang nl_NL.UTF-8
keyboard --vckeymap=us --xlayouts='us(euro)'
timezone Europe/Amsterdam

%onerror
run0 --user=liveuser --setenv=WAYLAND_DISPLAY=wayland-0 --setenv=DISPLAY=:0 \\
    yad --timeout=0 --text-info --no-buttons --width=640 --height=420 \\
    --title=BugOS --text="Het installeren is niet gelukt. Er is niets aan je computer veranderd als dit vóór het kopiëren gebeurde. Maak een foto van dit scherm en meld het op github.com/253UgurSahin/BugOS/issues" \\
    </tmp/anaconda.log
%end

# BugOS vanaf de stick zelf installeren (zie stap 1): geen internet nodig.
ostreecontainer --url=${IMAGE_REF} --transport=containers-storage --no-signature-verification
%include /usr/share/anaconda/post-scripts/bugos-updates.ks
EOF

# Na het installeren: updates voortaan van GitHub halen. BugOS kwam van de
# stick (containers-storage); zonder dit zou de computer later in zijn eigen
# lege opslag naar updates zoeken. bootc switch --mutate-in-place past alleen
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
    curl --retry 3 -Lo /usr/share/bugos/sb_pubkey.der https://github.com/ublue-os/akmods/raw/main/certs/public_key.der
    cat >>/usr/share/anaconda/post-scripts/bugos-updates.ks <<'EOF'
%post --nochroot --log=/tmp/bugos_logs/secureboot.log
if [ -d /sys/firmware/efi ] && mokutil --sb-state 2>/dev/null | grep -q enabled; then
    printf 'bugos\nbugos\n' | mokutil --import /usr/share/bugos/sb_pubkey.der || true
    run0 --user=liveuser --setenv=WAYLAND_DISPLAY=wayland-0 --setenv=DISPLAY=:0 \
        yad --on-top --width=560 --title=BugOS --button=OK:0 \
        --text="<b>Nog één stapje bij het opnieuw opstarten</b>\n\nJe computer laat een blauw scherm zien (MOK Manager). Kies daar:\n  1. <b>Enroll MOK</b>\n  2. <b>Continue</b>\n  3. <b>Yes</b>\n  4. Typ het wachtwoord: <b>bugos</b>\n  5. <b>Reboot</b>\n\nDit is nodig zodat je Nvidia-videokaart goed werkt." || true
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
# flatpak-preinstall en brew-setup kwamen mee van Aurora: op de stick haalden
# ze honderden MB aan apps en Homebrew binnen, in het geheugen (de stick kan
# niet schrijven). Dat maakt hem traag en het geheugen kan vollopen. Na het
# installeren draaien ze gewoon wel (dit geldt alleen voor de stick).
for s in rpm-ostreed-automatic.timer uupd.timer rpm-ostree-countme.service \
    bootloader-update.service bugos-eerste-start.service \
    flatpak-preinstall.service brew-setup.service brew-update.timer brew-upgrade.timer \
    rpm-ostree-countme.timer ublue-system-setup.service tailscaled.service; do
    systemctl disable "$s" 2>/dev/null || true
done
systemctl --global disable bugos-updatecheck.timer 2>/dev/null || true
systemctl --global disable ublue-user-setup.service 2>/dev/null || true

# Taal op de stick: Nederlands, met het Amerikaanse toetsenbord (dat gebruikt
# bijna iedereen in Nederland). Zonder dit startte de stick in het Engels.
# In het installatieprogramma kies je zelf de taal en het toetsenbord voor
# de computer; Nederlands staat dan al klaar.
echo "LANG=nl_NL.UTF-8" >/etc/locale.conf
echo "KEYMAP=us" >/etc/vconsole.conf
mkdir -p /etc/X11/xorg.conf.d
cat >/etc/X11/xorg.conf.d/00-keyboard.conf <<'EOF'
Section "InputClass"
    Identifier "system-keyboard"
    MatchIsKeyboard "on"
    Option "XkbLayout" "us"
    Option "XkbVariant" "euro"
EndSection
EOF

# Het installatieprogramma in BugOS-kleuren, met het lieveheersbeestje.
# Het programma (Anaconda WebUI) haalt zijn logo en kleuren uit de
# "branding" van Cockpit. Zonder eigen map kreeg je die van Fedora: blauw,
# met de Aurora-"A" als logo. /etc/cockpit/branding wordt als eerste gelezen,
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
# (ID uit os-release, bij ons "aurora"), mocht /etc/cockpit/branding niet
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
Description=Grotere tijdelijke map voor de live-USB

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
systemd-firstboot --timezone Europe/Amsterdam
mkdir -p /usr/lib/bootc-image-builder
cp "$SRC/iso.yaml" /usr/lib/bootc-image-builder/iso.yaml
