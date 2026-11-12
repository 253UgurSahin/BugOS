"""BugOS Bestanden: waar je spullen staan en hoeveel ruimte ze innemen.

Jip-en-Janneke: hier staan de vaste plekken (Thuis, Documenten, Afbeeldingen, ...),
welke soorten bestanden er zijn (en hun kleurtje), en het tellen van hoe groot
een map is. Gedeeld door de andere bugos_files_*-stukjes.
"""

from __future__ import annotations

import os
import stat as _stat
import threading
from pathlib import Path

from bugos_ui import t
from bugos_drives import Schijf, mooie_maat
from PySide6.QtCore import QStorageInfo, Qt


PAD_ROL = int(Qt.ItemDataRole.UserRole) + 1        # = QFileSystemModel.FilePathRole
INFO_ROL = int(Qt.ItemDataRole.UserRole) + 40     # prullenbak: pad van het .trashinfo-bestand
HERKOMST_ROL = int(Qt.ItemDataRole.UserRole) + 41  # prullenbak: waar het vandaan kwam

AFBEELDING = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".svg", ".avif", ".heic", ".ico"}
ODF = {".odt", ".ods", ".odp", ".odg"}
SOORTEN = {  # extensie -> (kleur, teken in het papiertje)
    "pdf": ("#D3263A", "tekst"), "doc": ("#2F7BF5", "tekst"), "docx": ("#2F7BF5", "tekst"),
    "odt": ("#2F7BF5", "tekst"), "rtf": ("#2F7BF5", "tekst"), "txt": ("#6B7280", "tekst"),
    "md": ("#6B7280", "tekst"), "xls": ("#14965A", "tabel"), "xlsx": ("#14965A", "tabel"),
    "ods": ("#14965A", "tabel"), "csv": ("#14965A", "tabel"), "ppt": ("#F2711C", "tekst"),
    "pptx": ("#F2711C", "tekst"), "odp": ("#F2711C", "tekst"), "zip": ("#6B7280", "doos"),
    "7z": ("#6B7280", "doos"), "rar": ("#6B7280", "doos"), "tar": ("#6B7280", "doos"), "gz": ("#6B7280", "doos"),
    "exe": ("#8B5CF6", "doos"), "msi": ("#8B5CF6", "doos"), "iso": ("#6B7280", "doos"),
    "mp3": ("#E2457A", "muziek"), "flac": ("#E2457A", "muziek"), "ogg": ("#E2457A", "muziek"),
    "wav": ("#E2457A", "muziek"), "m4a": ("#E2457A", "muziek"), "mp4": ("#0EA5A4", "film"),
    "mkv": ("#0EA5A4", "film"), "avi": ("#0EA5A4", "film"), "mov": ("#0EA5A4", "film"), "webm": ("#0EA5A4", "film"),
}
VERBERG_EXT = AFBEELDING | ODF | {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".rtf", ".md",
                                  ".csv", ".mp3", ".flac", ".ogg", ".wav", ".m4a", ".mp4", ".mkv", ".avi", ".mov", ".webm"}


def toon_naam(naam: str, is_map: bool) -> str:
    """'Recept.odt' wordt 'Recept'. Programma's en onbekende bestanden houden hun extensie (veiliger)."""
    p = Path(naam)
    if not is_map and p.suffix.lower() in VERBERG_EXT and p.stem:
        return p.stem
    return naam


# ================================================================ plekken ===

def thuis() -> Path:
    return Path.home()


def xdg_map(sleutel: str, standaard: str) -> Path:
    """Waar staat bijvoorbeeld 'Afbeeldingen'? Uit ~/.config/user-dirs.dirs (de taal van de gebruiker)."""
    bestand = Path(os.environ.get("XDG_CONFIG_HOME", thuis() / ".config")) / "user-dirs.dirs"
    try:
        for regel in bestand.read_text(encoding="utf-8").splitlines():
            if regel.startswith(f"XDG_{sleutel}_DIR="):
                waarde = regel.split("=", 1)[1].strip().strip('"').replace("$HOME", str(thuis()))
                pad = Path(waarde)
                if pad != thuis():
                    return pad
    except OSError:
        pass
    return thuis() / standaard


def plekken() -> list[tuple[str, str, str, Path]]:
    """(sleutel, naam, lijn-icoon, pad) voor de vaste plekken."""
    lijst = [("thuis", t("Thuis", "Home"), "huis", thuis())]
    for sleutel, xdg, std, nl, en, ic in (
        ("bureaublad", "DESKTOP", "Desktop", "Bureaublad", "Desktop", "computer"),
        ("documenten", "DOCUMENTS", "Documents", "Documenten", "Documents", "document"),
        ("afbeeldingen", "PICTURES", "Pictures", "Afbeeldingen", "Pictures", "foto"),
        ("muziek", "MUSIC", "Music", "Muziek", "Music", "muziek"),
        ("videos", "VIDEOS", "Videos", "Video's", "Videos", "film"),
        ("downloads", "DOWNLOAD", "Downloads", "Downloads", "Downloads", "download"),
    ):
        lijst.append((sleutel, t(nl, en), ic, xdg_map(xdg, std)))
    return lijst


def bijzondere_mappen() -> dict[str, str]:
    """Pad -> lijn-icoon, zodat 'Documenten' ook in het overzicht een eigen tekentje krijgt."""
    return {str(p): ic for sleutel, _n, ic, p in plekken() if sleutel != "thuis"}


# ================================================================ ruimte tellen ===
# Eén manier van tellen voor heel Bestanden, precies zoals 'du -s -x' (de schijfruimte, niet de 'grootte' van een
# bestand): een leeg 'sparse' bestand neemt niets in, een bestand met meer namen (hardlinks, zoals in Flatpak) telt
# één keer, en we blijven op het apparaat waar we begonnen (geen andere schijf, netwerkmap, /proc of btrfs-subvolume
# die er toevallig in hangt). Een snelkoppeling volgen we nooit (die van ~/.wine/dosdevices wijst naar /).
# tools/test_native_tools.py vergelijkt de uitkomst met de echte du.

_OPEN_MAP = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)


class Afgebroken(Exception):
    """Het tellen is gestopt (je verliet de pagina, of het venster ging dicht). Een halve telling mag nooit als
    uitslag gelden: dan stond er tien minuten een te klein getal."""


def tel_map(pad: Path | str, apparaat: int, gezien: set[tuple[int, int]], koppel: frozenset[str] | set[str] = frozenset(),
            stop: threading.Event | None = None) -> int:
    """Hoeveel ruimte alles ín deze map inneemt (de map zelf niet: die telt wie hem tegenkwam).

    apparaat: alleen wat op dit apparaat (st_dev) staat telt; een map op een ander apparaat wordt niet geopend.
    gezien: (apparaat, inode) van bestanden met meer namen die al geteld zijn; deel hem tussen tellingen die samen
    één totaal geven (dan telt een hardlink tussen twee mappen ook één keer, net als 'du map1 map2').
    koppel: plekken waar iets anders aan hangt (een netwerkmap, een tweede schijf). Die worden niet eens bekeken: een
    netwerkmap die niet meer antwoordt, laat elke 'stat' anders voor altijd wachten.
    stop: gaat die aan, dan stopt het tellen meteen (de uitkomst is dan te klein: kijk zelf naar stop).

    Elke map wordt via een eigen 'fd' gelezen (O_NOFOLLOW): dan kijkt stat alleen naar de naam in die map (geen heel
    pad opzoeken, een derde sneller) en kan een map die intussen een snelkoppeling werd, ons nergens anders heen
    sturen."""
    totaal, rij = 0, [os.fspath(pad)]
    # Alleen in de mappen waar een koppelpunt in zit, hoeven we elke naam na te kijken (dat scheelt veel werk).
    ouders = {os.path.dirname(k) for k in koppel}
    while rij:
        if stop is not None and stop.is_set():
            break
        map_ = rij.pop()
        try:
            fd = os.open(map_, _OPEN_MAP)
        except OSError:
            continue   # geen toestemming, of net weg: tellen wat we wel kunnen (net als du)
        try:
            nakijken = map_ in ouders
            with os.scandir(fd) as inhoud:
                for e in inhoud:
                    if nakijken and os.path.join(map_, e.name) in koppel:
                        continue
                    try:
                        st = e.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if st.st_dev != apparaat:
                        continue   # een andere schijf of subvolume die hier hangt: niet meetellen, niet in
                    if _stat.S_ISDIR(st.st_mode):
                        rij.append(os.path.join(map_, e.name))
                    elif st.st_nlink > 1:
                        sleutel = (st.st_dev, st.st_ino)
                        if sleutel in gezien:
                            continue   # dit bestand (met een andere naam) is al geteld
                        gezien.add(sleutel)
                    totaal += st.st_blocks * 512   # ook mappen en snelkoppelingen nemen een blokje in, zoals bij du
        except OSError:
            pass
        finally:
            os.close(fd)
    return totaal


def mapgrootte(pad: Path) -> int:
    """Hoeveel ruimte gebruikt deze map, met alles erin (zoals 'du -s -x')? 0 als hij er niet is."""
    try:
        st = os.stat(pad, follow_symlinks=False)
    except OSError:
        return 0
    if not _stat.S_ISDIR(st.st_mode):
        return st.st_blocks * 512
    return st.st_blocks * 512 + tel_map(pad, st.st_dev, set())


def voorbeeld_ruimte() -> list[int] | None:
    """Voor foto's: BUGOS_RUIMTE=totaal,vrij,afbeeldingen,videos,documenten,muziek,downloads (in bytes)."""
    try:
        getallen = [int(float(x)) for x in os.environ.get("BUGOS_RUIMTE", "").split(",") if x.strip()]
    except ValueError:
        return None
    return getallen if len(getallen) == 7 else None


def eigen_ruimte() -> tuple[int, int]:
    """(totaal, vrij) van de schijf waar je eigen bestanden op staan."""
    nep = voorbeeld_ruimte()
    if nep:
        return nep[0], nep[1]
    info = QStorageInfo(str(thuis()))
    return max(info.bytesTotal(), 0), max(info.bytesAvailable(), 0)


RUIMTE_SOORTEN = (  # (sleutel uit plekken(), kleur)
    ("afbeeldingen", "accent"), ("videos", "#0EA5A4"), ("documenten", "#2F7BF5"),
    ("muziek", "#E2457A"), ("downloads", "#8B5CF6"),
)


def schijf_van(pad: Path, lijst: list[Schijf]) -> Schijf | None:
    """Op welke (open) schijf staat deze map? De diepste wint."""
    beste = None
    for s in lijst:
        if s.wortel and zit_in(pad, Path(s.wortel)) and (beste is None or len(s.wortel) > len(beste.wortel)):
            beste = s
    return beste


def vrije_ruimte(pad: Path) -> str:
    info = QStorageInfo(str(pad))
    return mooie_maat(info.bytesAvailable()) if info.isValid() else ""


def zit_in(kind: Path, ouder: Path) -> bool:
    try:
        kind.resolve().relative_to(ouder.resolve())
        return True
    except ValueError:
        return False
