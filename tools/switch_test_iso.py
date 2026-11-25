#!/usr/bin/env python3
"""Een kleine test-ISO voor de zelftest van BugOS Switch (windows-switch.yml, -Taak Zelftest).

Zoals de echte BugOS-ISO (Titanoboa: xorriso -R -iso-level 3, géén Joliet): alleen Rock Ridge-namen, de mappen
LiveOS, images/pxeboot en EFI/BOOT + EFI/fedora, en grub.cfg met root=live:CDLABEL=BugOS-Live en het merkteken
bugos.stick=2 (iso_live/src/build.sh). LiveOS/squashfs.img is hier 3.000.000 bytes in plaats van 5 GB.

Gebruik:  python tools/switch_test_iso.py <uit.iso>   (nodig: pip install pycdlib)
"""

import io
import sys

import pycdlib

GRUB = """set timeout=5
set default="0"
search --no-floppy --set=root -l 'BugOS-Live'

menuentry 'Try or install BugOS / BugOS proberen of installeren' {
  linux /images/pxeboot/vmlinuz quiet rhgb root=live:CDLABEL=BugOS-Live enforcing=0 rd.live.image bugos.stick=2
  initrd /images/pxeboot/initrd.img
}
"""


def main(uit: str) -> int:
    iso = pycdlib.PyCdlib()
    iso.new(interchange_level=3, rock_ridge="1.09", vol_ident="BugOS-Live")
    for pad, rr in (("/LIVEOS", "LiveOS"), ("/IMAGES", "images"), ("/IMAGES/PXEBOOT", "pxeboot"), ("/EFI", "EFI"),
                    ("/EFI/BOOT", "BOOT"), ("/EFI/FEDORA", "fedora")):
        iso.add_directory(pad, rr_name=rr)
    bestanden = [
        ("/LIVEOS/SQUASHFS.IMG;1", "squashfs.img", bytes(range(256)) * (3000000 // 256) + bytes(3000000 % 256)),
        ("/IMAGES/PXEBOOT/VMLINUZ.;1", "vmlinuz", b"kernel" * 1000),
        ("/IMAGES/PXEBOOT/INITRD.IMG;1", "initrd.img", b"initrd" * 5000),
        ("/EFI/BOOT/BOOTX64.EFI;1", "BOOTX64.EFI", b"MZshim" * 100),
        ("/EFI/BOOT/GRUBX64.EFI;1", "grubx64.efi", b"MZgrub" * 100),
        ("/EFI/BOOT/GRUB.CFG;1", "grub.cfg", GRUB.encode()),
        ("/EFI/FEDORA/GRUB.CFG;1", "grub.cfg", GRUB.encode()),
    ]
    for pad, rr, data in bestanden:
        iso.add_fp(io.BytesIO(data), len(data), pad, rr_name=rr)
    iso.write(uit)
    iso.close()
    print(f"test-ISO gemaakt: {uit}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
