"""BugOS Bestanden: veilige acties met je bestanden.

Jip-en-Janneke: nooit iets overschrijven ('Naam (2).jpg'), weggooien gaat naar de
prullenbak (zodat het terug kan), en kopiëren of verplaatsen gebeurt op de
achtergrond, zonder halve kopieën als het misgaat.
"""

from __future__ import annotations

import errno
import os
import shutil
import urllib.parse
from datetime import datetime
from pathlib import Path

from bugos_ui import t
from bugos_files_plekken import thuis, zit_in
from PySide6.QtCore import QThread, Signal


# ========================================================= veilige acties ===

def vrije_naam(doel: Path) -> Path:
    """Bestaat 'doel' al? Dan 'Naam (2).jpg', 'Naam (3).jpg', ... Nooit iets overschrijven."""
    if not doel.exists() and not doel.is_symlink():
        return doel
    stam, ext = (doel.name, "") if doel.is_dir() else (doel.stem, doel.suffix)
    i = 2
    while True:
        kandidaat = doel.with_name(f"{stam} ({i}){ext}")
        if not kandidaat.exists() and not kandidaat.is_symlink():
            return kandidaat
        i += 1


def prullenbak() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", thuis() / ".local" / "share")) / "Trash"


def zelfde_schijf(a: Path, b: Path) -> bool:
    """Staat 'a' zelf op dezelfde schijf als 'b'? Bij een snelkoppeling telt waar de koppeling staat,
    niet waar hij naar wijst (die gaat gewoon naar de prullenbak, ook als hij naar een stick wijst)."""
    try:
        return os.lstat(a).st_dev == os.stat(b).st_dev
    except OSError:
        return False


def naar_prullenbak(pad: Path) -> tuple[Path, Path]:
    """Zet iets in de prullenbak (volgens de freedesktop-afspraak, dus ook KDE ziet het).

    Geeft (plek in de prullenbak, .trashinfo-bestand) terug, zodat het terug kan.
    """
    bak = prullenbak()
    (bak / "files").mkdir(parents=True, exist_ok=True)
    (bak / "info").mkdir(parents=True, exist_ok=True)
    naam, i = pad.name, 2
    while True:
        info = bak / "info" / f"{naam}.trashinfo"
        try:  # naam vastleggen: maak het info-bestand als eerste, alleen als het nog niet bestaat
            fd = os.open(info, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            naam = f"{pad.stem} ({i}){pad.suffix}" if pad.is_file() else f"{pad.name} ({i})"
            i += 1
            continue
        if (bak / "files" / naam).exists():
            os.close(fd)
            info.unlink(missing_ok=True)
            naam = f"{pad.stem} ({i}){pad.suffix}" if pad.is_file() else f"{pad.name} ({i})"
            i += 1
            continue
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("[Trash Info]\n")
            f.write(f"Path={urllib.parse.quote(str(pad.absolute()))}\n")
            f.write(f"DeletionDate={datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}\n")
        doel = bak / "files" / naam
        try:
            os.rename(pad, doel)
        except OSError:
            info.unlink(missing_ok=True)
            raise
        return doel, info


def lees_herkomst(info: Path) -> Path | None:
    try:
        for regel in info.read_text(encoding="utf-8").splitlines():
            if regel.startswith("Path="):
                return Path(urllib.parse.unquote(regel[5:].strip()))
    except OSError:
        pass
    return None


def terugzetten(bestand: Path, info: Path) -> Path:
    """Zet iets uit de prullenbak terug waar het stond (of ernaast, als daar al iets staat)."""
    herkomst = lees_herkomst(info) or (thuis() / bestand.name)
    doel = vrije_naam(herkomst)
    doel.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(bestand), str(doel))
    info.unlink(missing_ok=True)
    return doel


def prullenbak_inhoud() -> list[tuple[Path, Path, Path | None]]:
    """(bestand, info, herkomst) van alles in de prullenbak, nieuwste eerst."""
    bak = prullenbak()
    uit = []
    for info in (bak / "info").glob("*.trashinfo"):
        bestand = bak / "files" / info.name[: -len(".trashinfo")]
        if bestand.exists() or bestand.is_symlink():
            uit.append((bestand, info, lees_herkomst(info)))
    uit.sort(key=lambda x: x[1].stat().st_mtime if x[1].exists() else 0, reverse=True)
    return uit


def prullenbak_legen() -> int:
    """Gooi alles in de prullenbak echt weg. Geeft terug hoeveel dingen niet weg konden.

    Het info-bestand gaat pas weg als het ding zelf weg is: wat niet weg kon, blijft dus gewoon
    zichtbaar in de prullenbak (en neemt niet stiekem ruimte in)."""
    bak = prullenbak()
    mislukt = 0

    def weg(p: Path) -> bool:
        try:
            if p.is_dir() and not p.is_symlink():
                shutil.rmtree(p)
            else:
                p.unlink(missing_ok=True)
            return True
        except OSError:
            return False

    if (bak / "info").is_dir():
        for info in (bak / "info").glob("*.trashinfo"):
            if weg(bak / "files" / info.name[: -len(".trashinfo")]):
                info.unlink(missing_ok=True)
            else:
                mislukt += 1
    if (bak / "files").is_dir():  # losse dingen zonder info-bestand
        for p in (bak / "files").iterdir():
            if not (bak / "info" / f"{p.name}.trashinfo").exists() and not weg(p):
                mislukt += 1
    return mislukt


def kopieer_een(bron: Path, doelmap: Path, verplaats: bool) -> Path | None:
    """Kopieer of verplaats één ding naar 'doelmap'. Nooit overschrijven; nooit een map in zichzelf."""
    if bron.is_dir() and zit_in(doelmap, bron):
        raise ValueError(t(f"'{bron.name}' kan niet in zichzelf.", f"'{bron.name}' cannot go inside itself."))
    if verplaats and bron.parent.resolve() == doelmap.resolve():
        return bron  # staat er al
    doel = vrije_naam(doelmap / bron.name)
    if verplaats:
        try:
            os.rename(bron, doel)  # op dezelfde schijf: in één keer, niets half
            return doel
        except OSError as e:
            if e.errno != errno.EXDEV:
                raise
    # Eerst onder een verborgen tijdelijke naam; pas als alles er is, krijgt hij zijn echte naam.
    # Gaat het mis (schijf vol, stick eruit, venster dicht), dan blijft er geen halve kopie achter.
    tijdelijk = vrije_naam(doelmap / f".{doel.name}.bugos-bezig")
    try:
        if bron.is_dir() and not bron.is_symlink():
            shutil.copytree(bron, tijdelijk, symlinks=True)
        else:
            shutil.copy2(bron, tijdelijk, follow_symlinks=False)
        os.rename(tijdelijk, doel)
    except BaseException:
        ruim_op(tijdelijk)
        raise
    if verplaats:  # naar een andere schijf: het origineel pas weg als de kopie helemaal klaar is
        if bron.is_dir() and not bron.is_symlink():
            shutil.rmtree(bron)
        else:
            bron.unlink()
    return doel


def ruim_op(pad: Path) -> None:
    """Haal een halve kopie weg (stil: er was al een fout)."""
    try:
        if pad.is_dir() and not pad.is_symlink():
            shutil.rmtree(pad, ignore_errors=True)
        else:
            pad.unlink(missing_ok=True)
    except OSError:
        pass


class Klus(QThread):
    """Kopiëren of verplaatsen op de achtergrond, zodat het venster niet vastloopt."""

    voortgang = Signal(int, int)
    klaar = Signal(int, str)

    def __init__(self, bronnen: list[Path], doelmap: Path, verplaats: bool):
        super().__init__()
        self.bronnen, self.doelmap, self.verplaats = bronnen, doelmap, verplaats

    def run(self) -> None:
        gelukt, fout = 0, ""
        for i, bron in enumerate(self.bronnen):
            self.voortgang.emit(i, len(self.bronnen))
            try:
                kopieer_een(bron, self.doelmap, self.verplaats)
                gelukt += 1
            except (OSError, ValueError, shutil.Error) as e:
                fout = str(e)
        self.klaar.emit(gelukt, fout)
