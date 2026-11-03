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
# ---------------------------------------------------------------------------
AUTH_ARGS=()
if [ -s /run/secrets/ghcr ]; then
    AUTH_ARGS=(--authfile /run/secrets/ghcr)
fi
podman pull "${AUTH_ARGS[@]}" "$IMAGE_REF"
# Controle: staat hij er echt, en kan het installatieprogramma hem lezen?
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
hidden_spokes =
    NetworkSpoke
    PasswordSpoke
hidden_webui_pages =
    root-password
    network

[Localization]
use_geolocation = True
EOF

echo "BugOS release ${VERSION_ID:-1}" >/etc/system-release

# Wat het installatieprogramma doet.
mkdir -p /usr/share/anaconda/post-scripts
cat >>/usr/share/anaconda/interactive-defaults.ks <<EOF

%pre
mkdir -p /tmp/bugos_logs
%end

# Waarschuwen als er een met BitLocker versleutelde Windows-schijf is.
%pre --log=/tmp/bugos_logs/bitlocker.log
if lsblk -o FSTYPE --json | jq -e '.blockdevices | map(select(.fstype == "BitLocker")) | length > 0' >/dev/null; then
    run0 --user=liveuser yad --on-top --width=520 --title=BugOS \\
        --text="<b>Let op: er staat een versleutelde Windows-schijf (BitLocker) op deze computer.</b>\n\nWil je BugOS naast Windows zetten? Zorg dat je je BitLocker-herstelsleutel hebt opgeschreven (account.microsoft.com/devices/recoverykey).\n\nDoorgaan?" \\
        --button="Ja, doorgaan":0 --button="Stoppen":10
    if [ \$? -eq 10 ]; then pkill liveinst; pkill firefox; exit 0; fi
fi
%end

%onerror
run0 --user=liveuser yad --timeout=0 --text-info --no-buttons --width=640 --height=420 \\
    --title=BugOS --text="Het installeren is niet gelukt. Er is niets aan je computer veranderd als dit vóór het kopiëren gebeurde. Maak een foto van dit scherm en meld het op github.com/253UgurSahin/BugOS/issues" \\
    </tmp/anaconda.log
%end

# BugOS vanaf de stick zelf installeren (zie stap 1): geen internet nodig.
ostreecontainer --url=${IMAGE_REF} --transport=containers-storage --no-signature-verification
%include /usr/share/anaconda/post-scripts/bugos-updates.ks
EOF

# Na het installeren: updates voortaan van GitHub halen.
cat >/usr/share/anaconda/post-scripts/bugos-updates.ks <<EOF
%post --erroronfail --log=/tmp/bugos_logs/bootc-switch.log
sed -i 's|container-image-reference=.*|container-image-reference=ostree-unverified-registry:${IMAGE_REF}|' /ostree/deploy/default/deploy/*.origin
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
    run0 --user=liveuser yad --on-top --width=560 --title=BugOS --button=OK:0 \
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
install -Dm0644 "$SRC/bugos-installeren.desktop" /usr/share/applications/liveinst.desktop
rm -f /usr/share/applications/bugos-installeren.desktop /etc/skel/Desktop/bugos-installeren.desktop

# Dingen die op een live-stick niet horen te draaien.
# flatpak-preinstall en brew-setup kwamen mee van Aurora: op de stick haalden
# ze honderden MB aan apps en Homebrew binnen, in het geheugen (de stick kan
# niet schrijven). Dat maakt hem traag en het geheugen kan vollopen. Na het
# installeren draaien ze gewoon wel (dit geldt alleen voor de stick).
for s in rpm-ostreed-automatic.timer uupd.timer rpm-ostree-countme.service \
    bootloader-update.service bugos-eerste-start.service \
    flatpak-preinstall.service brew-setup.service brew-update.timer brew-upgrade.timer; do
    systemctl disable "$s" 2>/dev/null || true
done
systemctl --global disable bugos-updatecheck.timer 2>/dev/null || true

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
EndSection
EOF

# Het installatieprogramma in BugOS-kleuren, met het lieveheersbeestje.
# Het programma (Anaconda WebUI) haalt zijn logo en kleuren uit de
# "branding" van Cockpit, en kiest die map op naam van het systeem (ID in
# os-release, bij ons "aurora"). Die map bestond niet, dus kreeg je die van
# Fedora: blauw, met de Aurora-"A" als logo.
BRANDING=/usr/share/cockpit/branding/aurora
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
EOF

# Het installatieprogramma heeft veel ruimte nodig in /var/tmp.
find /var/tmp -mindepth 1 -maxdepth 1 -exec rm -rf {} + 2>/dev/null || true
mkdir -p /var/tmp
cat >/etc/systemd/system/var-tmp.mount <<'EOF'
[Unit]
Description=Grotere tijdelijke map voor de live-USB

[Mount]
What=tmpfs
Where=/var/tmp
Type=tmpfs
Options=size=50%%,nr_inodes=1m

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
