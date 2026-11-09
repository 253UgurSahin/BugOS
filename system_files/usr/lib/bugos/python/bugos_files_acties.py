"""BugOS Bestanden: veilige acties met je bestanden.

Jip-en-Janneke: nooit iets overschrijven ('Naam (2).jpg'), weggooien gaat naar de
prullenbak (zodat het terug kan), en kopiëren of verplaatsen gebeurt op de
achtergrond, zonder halve kopieën als het misgaat.
"""

from __future__ import annotations

import ctypes
import errno
import os
import re
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


# Een naam mag 255 bytes zijn; het info-bestand heet "<naam>.trashinfo" (10 bytes langer). Bij een heel
# lange naam korten we de naam in de prullenbak in (de extensie blijft); Path= houdt de echte naam (U076).
_MAX_NAAM = 255 - len(".trashinfo")


def _prullenbak_naam(stam: str, ext: str, achter: str) -> str:
    if len(ext.encode()) > 40:   # vreemd lange "extensie": gewoon als deel van de naam zien
        stam, ext = stam + ext, ""
    while stam and len(f"{stam}{achter}{ext}".encode()) > _MAX_NAAM:
        stam = stam[:-1]
    return f"{stam}{achter}{ext}"


def naar_prullenbak(pad: Path) -> tuple[Path, Path]:
    """Zet iets in de prullenbak (volgens de freedesktop-afspraak, dus ook KDE ziet het).

    Geeft (plek in de prullenbak, .trashinfo-bestand) terug, zodat het terug kan.
    """
    bak = prullenbak()
    (bak / "files").mkdir(parents=True, exist_ok=True)
    (bak / "info").mkdir(parents=True, exist_ok=True)
    stam, ext = (pad.stem, pad.suffix) if pad.is_file() else (pad.name, "")
    naam, i = _prullenbak_naam(stam, ext, ""), 2
    while True:
        info = bak / "info" / f"{naam}.trashinfo"
        try:  # naam vastleggen: maak het info-bestand als eerste, alleen als het nog niet bestaat
            fd = os.open(info, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            naam = _prullenbak_naam(stam, ext, f" ({i})")
            i += 1
            continue
        if (bak / "files" / naam).exists():
            os.close(fd)
            info.unlink(missing_ok=True)
            naam = _prullenbak_naam(stam, ext, f" ({i})")
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


# Een USB-stick (FAT/exFAT) kent niet alles wat je computer kent. Dat zijn geen echte fouten:
# - een naam met : ? * " < > | (of te lang): dat ene bestand kan er niet op, de rest wel;
# - een bestand groter dan 4 GB op FAT32;
# - een snelkoppeling (symlink): die kan zo'n stick niet bewaren;
# - de rechten (wie mag lezen, chmod): die kan zo'n stick niet onthouden. De inhoud staat er dan gewoon.
NAAM_FOUTEN = (errno.EINVAL, errno.EILSEQ, errno.ENAMETOOLONG)
RECHTEN_FOUTEN = (errno.EPERM, errno.ENOTSUP, errno.EACCES)


class KopieFout(OSError):
    """Een echte fout bij het kopiëren, met de uitleg al in gewone woorden (in strerror)."""


def _foutnummer(tekst: str) -> int | None:
    """copytree bewaart van elke fout alleen de tekst ('[Errno 22] Invalid argument: ...'): haal het nummer eruit."""
    m = re.match(r"\[Errno (\d+)\]", tekst)
    return int(m.group(1)) if m else None


def _reden(nummer: int | None, bron: str) -> str | None:
    """Waarom kon dit ene ding niet mee? None = een echte fout (schijf vol, stick eruit)."""
    if nummer in NAAM_FOUTEN:
        return t("de naam heeft een teken dat deze schijf niet kent (zoals : ? * of \")",
                 "the name has a character this drive does not allow (like : ? * or \")")
    if nummer == errno.EFBIG:
        return t("groter dan 4 GB, en dat past niet op deze schijf", "larger than 4 GB, which this drive cannot store")
    if nummer in RECHTEN_FOUTEN and os.path.islink(bron):
        return t("een snelkoppeling, en die kan deze schijf niet bewaren", "a shortcut, which this drive cannot store")
    return None


def leesbare_fout(nummer: int | None, wat: str) -> str:
    """Een fout in gewone woorden, zonder Python-lijstjes."""
    if nummer == errno.ENOSPC:
        uitleg = t("de schijf is vol", "the drive is full")
    elif nummer in (errno.EIO, errno.ENODEV, errno.ENXIO, errno.ENOENT):
        uitleg = t("de schijf reageert niet meer (is hij eruit gehaald?)", "the drive stopped responding (was it unplugged?)")
    elif nummer:
        uitleg = os.strerror(nummer)
    else:
        uitleg = t("er ging iets mis", "something went wrong")
    return t(f"'{wat}' lukte niet: {uitleg}.", f"'{wat}' did not work: {uitleg}.")


def _kopieer_bestand(bron: Path, doel: Path) -> None:
    """Eén bestand kopiëren met inhoud en datum. Kan de schijf de rechten niet bewaren, dan is dat goed zo."""
    shutil.copyfile(bron, doel, follow_symlinks=False)
    try:
        shutil.copystat(bron, doel, follow_symlinks=False)
    except OSError as e:
        if e.errno not in RECHTEN_FOUTEN:
            raise


def _bekijk_fouten(fouten: list, bron: Path, tijdelijk: Path, achter: list) -> None:
    """Loop de fouten van copytree na. Wat de schijf alleen niet kan bewaren, komt in 'achter';
    is er één echte fout bij, dan gaat de hele kopie weg (dat doet de beller)."""
    for fout in fouten:
        if not (isinstance(fout, tuple) and len(fout) == 3):
            raise KopieFout(errno.EIO, leesbare_fout(None, bron.name))
        # os.fspath: bij submappen geeft copytree een os.DirEntry in plaats van tekst
        van, naar, tekst = (os.fspath(x) if isinstance(x, (str, os.PathLike)) else str(x) for x in fout)
        nummer = _foutnummer(tekst)
        if nummer in RECHTEN_FOUTEN and os.path.lexists(naar) and not os.path.islink(van):
            try:  # alleen de rechten of de datum: de inhoud staat er wel (even groot = helemaal)
                if os.path.isdir(van) or os.path.getsize(van) == os.path.getsize(naar):
                    continue
            except OSError:
                pass
        reden = _reden(nummer, van)
        if reden is None:
            raise KopieFout(nummer or errno.EIO, leesbare_fout(nummer, bron.name))
        if os.path.lexists(naar):
            ruim_op(Path(naar))  # half bestand (te groot): weg, het staat in de lijst
        rel = os.path.relpath(van, bron)
        achter.append((Path(van), bron.name if rel == "." else f"{bron.name}/{rel}", reden))


def hoofdletter_reden() -> str:
    return t("er staat al iets met dezelfde naam in andere hoofdletters, en deze schijf ziet dat als hetzelfde",
             "something with the same name in other capitals is already there, and this drive sees them as the same")


def kent_hoofdletters(map_: Path) -> bool:
    """Ziet deze schijf 'Foto.jpg' en 'foto.jpg' als twee bestanden? (FAT/exFAT op een USB-stick: nee.)"""
    proef = map_ / f".bugos-Hoofdletters-{os.getpid()}"
    try:
        proef.touch(exist_ok=False)
    except OSError:
        return True  # kunnen we niet proberen: dan doen we zoals altijd
    try:
        return not (map_ / proef.name.lower()).exists()
    finally:
        proef.unlink(missing_ok=True)


def dubbele_namen(map_: Path) -> list[Path]:
    """Alles in 'map_' (ook dieper) dat alleen in hoofdletters verschilt van iets ernaast: de tweede en verder."""
    dubbel = []
    for wortel, mappen, bestanden in os.walk(map_):
        gezien: set[str] = set()
        for naam in sorted(mappen + bestanden):
            sleutel = naam.casefold()
            if sleutel in gezien:
                dubbel.append(Path(wortel) / naam)
            gezien.add(sleutel)
        mappen[:] = [m for m in mappen if (Path(wortel) / m) not in dubbel]
    return dubbel


def schrijf_weg(pad: Path) -> None:
    """Zorg dat wat we kopieerden echt op de schijf staat, niet alleen in het geheugen van de computer.

    Een USB-stick krijgt het pas later; trek je hem er dan uit, dan is het weg. Dit kan even duren,
    dus alleen op de achtergrond (in de Klus). Lukt het wegschrijven niet, dan is dat een echte fout."""
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        fd = os.open(pad, os.O_RDONLY)
    except (OSError, AttributeError):
        os.sync()  # dan maar alles in één keer
        return
    try:
        if libc.syncfs(fd) != 0:  # alleen de schijf waar 'pad' op staat
            nummer = ctypes.get_errno()
            raise KopieFout(nummer, leesbare_fout(nummer, pad.name))
    finally:
        os.close(fd)


def kopieer_een(bron: Path, doelmap: Path, verplaats: bool, achter: list | None = None,
                bij_wegschrijven=None) -> Path | None:
    """Kopieer of verplaats één ding naar 'doelmap'. Nooit overschrijven; nooit een map in zichzelf.

    Kan de schijf een paar bestanden niet bewaren (een naam met ':' op een stick), dan komt de rest wel
    over en staan die bestanden in 'achter' als (pad, naam, reden). Bij verplaatsen blijven ze op de oude plek."""
    achter = [] if achter is None else achter
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
    # Alleen wat de schijf niet kan bewaren (zie NAAM_FOUTEN) blijft achter, en dat zeggen we erbij.
    tijdelijk = vrije_naam(doelmap / f".{doel.name}.bugos-bezig")
    hier = len(achter)
    try:
        if bron.is_dir() and not bron.is_symlink():
            # Op een stick die geen hoofdletters kent, zou 'IMG_1.JPG' 'img_1.jpg' overschrijven (en bij
            # verplaatsen ben je er dan één kwijt). Zo'n tweede blijft hier staan, en dat zeggen we.
            overslaan: set[Path] = set()
            if not kent_hoofdletters(doelmap):
                for p in dubbele_namen(bron):
                    overslaan.add(p)
                    rel = os.path.relpath(p, bron)
                    achter.append((p, f"{bron.name}/{rel}", hoofdletter_reden()))
            try:
                shutil.copytree(bron, tijdelijk, symlinks=True,
                                ignore=(lambda map_, namen: {n for n in namen if Path(map_) / n in overslaan})
                                if overslaan else None)
            except shutil.Error as e:
                _bekijk_fouten(list(e.args[0]) if e.args and isinstance(e.args[0], list) else [None],
                               bron, tijdelijk, achter)
        else:
            _kopieer_bestand(bron, tijdelijk)
        os.rename(tijdelijk, doel)
    except OSError as e:
        ruim_op(tijdelijk)
        reden = _reden(e.errno, str(bron))
        if reden is None or len(achter) > hier:
            del achter[hier:]  # alles is weg, dus ook niets 'achtergebleven'
            raise
        achter.append((bron, bron.name, reden))  # het hele ding kan er niet op (bijv. de naam zelf)
        return None
    except BaseException:
        ruim_op(tijdelijk)
        raise
    if verplaats:  # naar een andere schijf: het origineel pas weg als de kopie helemaal klaar is
        if bij_wegschrijven:
            bij_wegschrijven()
        schrijf_weg(doel)  # ... en echt op de stick staat, niet alleen in het geheugen
        if bron.is_dir() and not bron.is_symlink():
            if len(achter) > hier:
                weg_behalve(bron, [p for p, _n, _r in achter[hier:]])
            else:
                shutil.rmtree(bron)
        else:
            bron.unlink()
    return doel


def weg_behalve(map_: Path, bewaar: list[Path]) -> None:
    """Gooi een verplaatste map weg, maar laat staan wat niet mee kon (en de mappen eromheen)."""
    def bewaren(p: Path) -> bool:
        return any(p == b or b in p.parents for b in bewaar)

    for wortel, mappen, bestanden in os.walk(map_, topdown=False):
        for naam in bestanden + [m for m in mappen if os.path.islink(os.path.join(wortel, m))]:
            p = Path(wortel) / naam
            if not bewaren(p):
                p.unlink(missing_ok=True)
        for naam in mappen:
            p = Path(wortel) / naam
            if not p.is_symlink() and not bewaren(p):
                try:
                    p.rmdir()  # alleen als hij leeg is
                except OSError:
                    pass
    try:
        map_.rmdir()
    except OSError:
        pass


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
    wegschrijven = Signal()  # bezig met echt wegschrijven naar de stick: nog niet eruit halen
    klaar = Signal(int, str)

    def __init__(self, bronnen: list[Path], doelmap: Path, verplaats: bool):
        super().__init__()
        self.bronnen, self.doelmap, self.verplaats = bronnen, doelmap, verplaats
        self.achter: list[tuple[Path, str, str]] = []  # wat de schijf niet kon bewaren: (pad, naam, reden)

    def run(self) -> None:
        gelukt, fout = 0, ""
        for i, bron in enumerate(self.bronnen):
            self.voortgang.emit(i, len(self.bronnen))
            try:
                if kopieer_een(bron, self.doelmap, self.verplaats, self.achter, self.wegschrijven.emit) is not None:
                    gelukt += 1
            except ValueError as e:
                fout = str(e)
            except (OSError, shutil.Error) as e:
                fout = e.strerror if isinstance(e, KopieFout) else \
                    leesbare_fout(e.errno if isinstance(e, OSError) else None, bron.name)
        if gelukt and not self.verplaats and not all(zelfde_schijf(x, self.doelmap) for x in self.bronnen):
            # Gekopieerd naar een andere schijf (een stick): pas 'Klaar' als het er echt op staat.
            self.wegschrijven.emit()
            try:
                schrijf_weg(self.doelmap)
            except OSError as e:
                fout = e.strerror or leesbare_fout(e.errno, self.doelmap.name)
        self.klaar.emit(gelukt, fout)


def achter_uitleg(achter: list[tuple[Path, str, str]], verplaats: bool) -> str:
    """'2 bestanden konden niet mee: ...' in gewone woorden (de eerste paar met de reden)."""
    n = len(achter)
    regels = [f"'{naam}': {reden}" for _p, naam, reden in achter[:3]]
    if n > 3:
        regels.append(t(f"en nog {n - 3}", f"and {n - 3} more"))
    lijst = "; ".join(regels)
    plek = t(" Ze staan nog op de oude plek.", " They are still in their old place.") if verplaats else ""
    return t(f"{n} {'bestand kon' if n == 1 else 'bestanden konden'} niet mee: {lijst}. De rest staat er wel.{plek}",
             f"{n} {'file' if n == 1 else 'files'} could not go along: {lijst}. Everything else is there.{plek}")
