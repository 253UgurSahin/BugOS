#!/usr/bin/bash
# vm-qemu.sh - BugOS testen in een virtuele pc met QEMU (op Linux, met KVM).
# ==========================================================================
# Waarom QEMU (op Linux): het gebruikt KVM uit de Linux-kernel zelf, dus de VM is snel; de videokaart is virtio
# (met GL=1 zelfs met 3D, zoals op een echte pc); en alles is met de hand of met een script te besturen (QMP:
# schermfoto's, uitzetten). Op Windows zonder KVM wint QEMU weinig; gebruik daar VirtualBox.
#
# Alles staat in één map (standaard ~/bugos-vm, of VM_MAP=...): de schijf (qcow2), de UEFI-instellingen, het
# besturingskanaal (qmp.sock) en het logboek van QEMU. Een tweede VM? Geef een andere VM_MAP mee.
#
# Gebruik:
#   vm-qemu.sh nieuw <iso>          lege schijf van 64 GB maken en starten vanaf de ISO (installeren)
#   vm-qemu.sh start                starten vanaf de schijf (na het installeren)
#   vm-qemu.sh foto <bestand.png>   schermfoto van de draaiende VM
#   vm-qemu.sh uit                  netjes uitzetten (zoals de aan/uit-knop)
#   vm-qemu.sh bewaar <naam>        momentopname van de schijf (VM moet uit staan)
#   vm-qemu.sh terug <naam>         schijf terug naar die momentopname (VM moet uit staan)
#   vm-qemu.sh lijst                momentopnames tonen
#   vm-qemu.sh ssh [opdracht]       inloggen (als in de VM sshd aanstaat; poort 2222 op deze computer)
# Instellingen: VM_MAP, GEHEUGEN (MB, standaard 8192), KERNEN (standaard 4), GL=1 (3D, vraagt een venster),
#               AUDIO=pa of pipewire (standaard stil), ZONDER_VENSTER=1 (geen venster: besturen met foto en ssh),
#               VM_GEBRUIKER (voor ssh, standaard je eigen naam).

set -euo pipefail

MAP="${VM_MAP:-$HOME/bugos-vm}"
SCHIJF="$MAP/schijf.qcow2"
VARS="$MAP/uefi-vars.fd"
QMP="$MAP/qmp.sock"
GEHEUGEN="${GEHEUGEN:-8192}"
KERNEN="${KERNEN:-4}"

fout() { echo "vm-qemu: $*" >&2; exit 1; }

# De UEFI-firmware (OVMF): Fedora, Debian/Ubuntu en Arch zetten die op een andere plek. Geeft "code:vars".
ovmf() {
    local paar code vars
    for paar in "/usr/share/edk2/ovmf/OVMF_CODE.fd:/usr/share/edk2/ovmf/OVMF_VARS.fd" \
                "/usr/share/OVMF/OVMF_CODE_4M.fd:/usr/share/OVMF/OVMF_VARS_4M.fd" \
                "/usr/share/OVMF/OVMF_CODE.fd:/usr/share/OVMF/OVMF_VARS.fd" \
                "/usr/share/edk2/x64/OVMF_CODE.4m.fd:/usr/share/edk2/x64/OVMF_VARS.4m.fd"; do
        code="${paar%%:*}"
        vars="${paar#*:}"
        if [ -f "$code" ] && [ -f "$vars" ]; then
            echo "$code:$vars"
            return 0
        fi
    done
    fout "geen OVMF (UEFI) gevonden. Installeer edk2-ovmf (Fedora) of ovmf (Debian/Ubuntu)."
}

# Draait de VM? Alleen als het besturingskanaal echt antwoordt (een oud socketbestand telt niet).
draait() {
    [ -S "$QMP" ] && python3 -c 'import socket, sys; socket.socket(socket.AF_UNIX).connect(sys.argv[1])' "$QMP" 2>/dev/null
}

# QEMU starten, op de achtergrond, met een logboek in de map. "$@" = extra opties (bijvoorbeeld de ISO).
draai() {
    command -v qemu-system-x86_64 >/dev/null || fout "qemu-system-x86_64 ontbreekt (Fedora: dnf install qemu-kvm)."
    [ -w /dev/kvm ] || fout "/dev/kvm is er niet of je mag hem niet gebruiken (zit je in de groep kvm?)."
    draait && fout "de VM draait al."
    local fw code
    fw="$(ovmf)"
    code="${fw%%:*}"
    # Beeld: gewone virtio; met GL=1 virtio met 3D (vraagt een venster met OpenGL); ZONDER_VENSTER=1: geen venster.
    local beeld=(-device virtio-vga -display gtk)
    if [ -n "${GL:-}" ]; then
        beeld=(-device virtio-vga-gl -display "gtk,gl=on")
    fi
    if [ -n "${ZONDER_VENSTER:-}" ]; then
        beeld=(-device virtio-vga -display none)
    fi
    rm -f "$QMP"
    # Netwerk: "user" (zoals NAT in VirtualBox), met poort 2222 op deze computer naar ssh in de VM.
    # Muis: usb-tablet, dan klopt de muispositie ook zonder "muis vangen".
    nohup qemu-system-x86_64 \
        -name BugOS -machine q35,accel=kvm -cpu host -smp "$KERNEN" -m "$GEHEUGEN" \
        -drive if=pflash,format=raw,readonly=on,file="$code" \
        -drive if=pflash,format=raw,file="$VARS" \
        -drive file="$SCHIJF",if=virtio,format=qcow2,discard=unmap \
        -netdev user,id=net0,hostfwd=tcp:127.0.0.1:2222-:22 -device virtio-net-pci,netdev=net0 \
        -device qemu-xhci -device usb-tablet \
        -audiodev "${AUDIO:-none},id=geluid" -device intel-hda -device hda-duplex,audiodev=geluid \
        "${beeld[@]}" \
        -qmp "unix:$QMP,server,nowait" \
        "$@" >"$MAP/qemu.log" 2>&1 &
    # Even wachten tot het besturingskanaal er is; lukt dat niet, dan staat de reden in het logboek.
    for _ in $(seq 1 20); do
        draait && return 0
        sleep 0.5
    done
    fout "QEMU startte niet; zie $MAP/qemu.log"
}

# Eén QMP-opdracht sturen (JSON) en het antwoord tonen, via python3 (dat heeft elke Linux).
qmp() {
    draait || fout "de VM draait niet."
    python3 - "$QMP" "$1" <<'EOF'
import json, socket, sys
s = socket.socket(socket.AF_UNIX)
s.connect(sys.argv[1])
f = s.makefile("rw")
f.readline()                                   # welkomstregel van QEMU
f.write(json.dumps({"execute": "qmp_capabilities"}) + "\n")
f.flush()
f.readline()
f.write(sys.argv[2] + "\n")
f.flush()
print(f.readline().strip())
EOF
}

opdracht="${1:-}"
shift || true
case "$opdracht" in
    nieuw)
        iso="${1:?geef de ISO}"
        [ -f "$iso" ] || fout "ISO niet gevonden: $iso"
        [ -e "$SCHIJF" ] && fout "$SCHIJF bestaat al. Gooi de map $MAP weg of gebruik een andere VM_MAP."
        mkdir -p "$MAP"
        fw="$(ovmf)"
        cp "${fw#*:}" "$VARS"
        qemu-img create -q -f qcow2 "$SCHIJF" 64G
        draai -drive file="$(realpath "$iso")",media=cdrom,readonly=on -boot order=d,menu=off
        echo "De VM start vanaf de ISO. Na het installeren: 'vm-qemu.sh uit' en dan 'vm-qemu.sh start'."
        ;;
    start)
        [ -e "$SCHIJF" ] || fout "nog geen VM; begin met: vm-qemu.sh nieuw <iso>"
        draai -boot order=c,menu=off
        ;;
    foto)
        doel="$(realpath -m "${1:?geef een bestandsnaam}")"
        qmp "{\"execute\": \"screendump\", \"arguments\": {\"filename\": \"$doel\", \"format\": \"png\"}}" >/dev/null
        echo "$doel"
        ;;
    uit)
        qmp '{"execute": "system_powerdown"}' >/dev/null
        echo "Uitzetten gevraagd (zoals de aan/uit-knop)."
        ;;
    bewaar)
        draait && fout "zet de VM eerst uit (vm-qemu.sh uit)."
        qemu-img snapshot -c "${1:?geef een naam}" "$SCHIJF"
        echo "Bewaard: $1"
        ;;
    terug)
        draait && fout "zet de VM eerst uit (vm-qemu.sh uit)."
        qemu-img snapshot -a "${1:?geef een naam}" "$SCHIJF"
        echo "Terug naar: $1"
        ;;
    lijst)
        qemu-img snapshot -l "$SCHIJF"
        ;;
    ssh)
        exec ssh -p 2222 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
            "${VM_GEBRUIKER:-$USER}@127.0.0.1" "$@"
        ;;
    *)
        sed -n '2,23p' "$0"
        exit 1
        ;;
esac
