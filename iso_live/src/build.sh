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
# 1. De BugOS die geïnstalleerd gaat worden, alvast op de stick zetten.
#    Dan kan installeren ook zonder internet.
# ---------------------------------------------------------------------------
AUTH=()
[ -f /run/secrets/ghcr ] && AUTH=(--authfile /run/secrets/ghcr)
podman pull "${AUTH[@]}" "$IMAGE_REF"

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
install -Dm0644 "$SRC/bugos-installeren.desktop" /usr/share/applications/bugos-installeren.desktop
install -Dm0755 "$SRC/bugos-live" /usr/bin/bugos-live
# Installeer-knop ook op het bureaublad van de live-gebruiker.
install -Dm0755 "$SRC/bugos-installeren.desktop" /etc/skel/Desktop/bugos-installeren.desktop

# Dingen die op een live-stick niet horen te draaien.
for s in rpm-ostreed-automatic.timer uupd.timer rpm-ostree-countme.service \
    bootloader-update.service bugos-eerste-start.service; do
    systemctl disable "$s" 2>/dev/null || true
done
systemctl --global disable bugos-updatecheck.timer 2>/dev/null || true

# Het installatieprogramma heeft veel ruimte nodig in /var/tmp.
rm -rf /var/tmp
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
