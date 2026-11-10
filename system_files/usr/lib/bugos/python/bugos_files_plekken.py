"""BugOS Bestanden: waar je spullen staan en hoeveel ruimte ze innemen.

Jip-en-Janneke: hier staan de vaste plekken (Thuis, Documenten, Afbeeldingen, ...),
welke soorten bestanden er zijn (en hun kleurtje), en het tellen van hoe groot
een map is. Gedeeld door de andere bugos_files_*-stukjes.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

from bugos_ui import t
from bugos_drives import Schijf, mooie_maat
from PySide6.QtCore import QObject, QRunnable, QStorageInfo, Qt, Signal


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


STOP = threading.Event()  # gaat aan als het venster dichtgaat: dan stopt het tellen meteen


def mapgrootte(pad: Path, max_items: int = 500_000) -> int:
    """Hoeveel ruimte gebruikt deze map (met alles erin)? Blijft op dezelfde schijf; volgt geen snelkoppelingen."""
    try:
        apparaat = os.stat(pad).st_dev
    except OSError:
        return 0
    totaal, rij, gezien = 0, [str(pad)], 0
    while rij and gezien < max_items and not STOP.is_set():
        try:
            with os.scandir(rij.pop()) as inhoud:
                for e in inhoud:
                    gezien += 1
                    try:
                        st = e.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    if st.st_dev != apparaat:
                        continue
                    if e.is_dir(follow_symlinks=False):
                        rij.append(e.path)
                    elif e.is_file(follow_symlinks=False):
                        totaal += st.st_blocks * 512
        except OSError:
            continue
    return totaal


class Telsein(QObject):
    klaar = Signal(object)


class Teller(QRunnable):
    """Telt op de achtergrond hoe groot je Afbeeldingen, Video's, enzovoort zijn."""

    def __init__(self, mappen: list[tuple[str, Path]], sein: Telsein):
        super().__init__()
        self.mappen, self.sein = mappen, sein

    def run(self) -> None:
        uitslag = {sleutel: mapgrootte(pad) for sleutel, pad in self.mappen}
        try:
            self.sein.klaar.emit(uitslag)
        except RuntimeError:  # het venster is al dicht
            pass


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
