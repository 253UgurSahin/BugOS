"""Haal alles van je oude pc: de 'bestanden slimmer'-onderdelen (onderdeel E) aan de BugOS-kant.

Wat BugOS Switch op Windows sinds 2026-11-16 ook meeneemt (zie windows-switch/FORMAT.md), en wat BugOS ermee doet:
  - extra mappen die je zelf koos (bijvoorbeeld D:\\Foto's): elk in je Thuismap, onder dezelfde naam;
  - je eigen lettertypen: in ~/.local/share/fonts/Van Windows, zodat elk programma ze kan gebruiken;
  - Thunderbird: je accounts, mappen en adresboek (nooit de wachtwoorden: die vraagt Thunderbird één keer);
  - Outlook-mailbestanden (.pst): in Documenten, met eerlijke uitleg (BugOS kan ze niet zelf openen);
  - bestanden die alleen in OneDrive stonden: BugOS zegt welke, en waar je ze vindt.

Elke stap geeft een Uitslag (goed / niet / zelf doen) en onthoudt in het logboek wat hij neerzette (zie
bugos_overstap_logboek), zodat 'Alles terugdraaien' het weer weg kan halen. Nooit wordt iets overschreven.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import bugos_config as bi
import bugos_overstap_toepassen as ot
from bugos_base import t

GOED, NIET, ZELF = ot.GOED, ot.NIET, ot.ZELF

# Thunderbird als Flatpak (uit de Winkel) en als gewoon programma: waar ze hun profielen bewaren.
FLATPAK_THUNDERBIRD = "org.mozilla.Thunderbird"
# Wat er van een Thunderbird-profiel nooit mee gaat, bovenop wat ook bij Firefox thuisblijft (wachtwoorden en
# cookies): ImapMail is een kopie van de mail op de server; die haalt Thunderbird zelf opnieuw op.
THUNDERBIRD_NIET = frozenset({"ImapMail"})


def _naam_goed(naam: str) -> bool:
    """Een mapnaam van de stick die we in je Thuismap mogen gebruiken: geen pad, geen verborgen map (.config!),
    niets raars. De naam komt van een andere computer, dus we zijn voorzichtig."""
    return (bool(naam) and len(naam) <= 120 and naam.isprintable() and "/" not in naam and "\\" not in naam
            and not naam.startswith(".") and naam not in ("..",) and naam.strip() == naam)


# ============================================================== extra mappen ===

def extra_mappen(bron: Path, i: dict) -> list[tuple[str, Path]]:
    """[(naam, map op de stick)] van de extra mappen die echt op de stick staan."""
    uit = []
    for e in ot._lijst(i.get("extra")):
        e = ot._dict(e)
        naam = ot._tekst(e.get("naam"), 120)
        pad = ot.binnen_stick(bron, e.get("map"))
        try:
            if _naam_goed(naam) and pad is not None and pad.is_dir():
                uit.append((naam, pad))
        except OSError:
            continue
    return uit


def extra_doel(naam: str) -> Path:
    """Waar een extra map komt: in je Thuismap, onder dezelfde naam. Bestaat die al, dan komen de bestanden erbij
    (rsync --ignore-existing: wat er al staat, wordt nooit overschreven)."""
    return Path.home() / naam


# ================================================================ lettertypen ===

def lettertypen_map() -> Path:
    basis = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return basis / "fonts" / "Van Windows"


_LETTERTYPE = re.compile(r".+\.(ttf|otf|ttc|otc)$", re.IGNORECASE)


def lettertypen_op_stick(bron: Path, i: dict) -> list[Path]:
    info = ot._dict(i.get("lettertypen"))
    pad = ot.binnen_stick(bron, info.get("map") or "Lettertypen") if info else None
    try:
        if pad is None or not pad.is_dir():
            return []
        return sorted(p for p in pad.iterdir() if p.is_file() and _LETTERTYPE.fullmatch(p.name))
    except OSError:
        return []


def zet_lettertypen(bron: Path, i: dict) -> list[ot.Uitslag]:
    """Je lettertypen in ~/.local/share/fonts/Van Windows. Een lettertype dat er al (precies zo) staat, slaan we over;
    een ander bestand met dezelfde naam krijgt een eigen naam (nooit overschrijven)."""
    import bugos_overstap_logboek as lb
    lijst = lettertypen_op_stick(bron, i)
    if not lijst:
        return []
    doel = lettertypen_map()
    nieuw = 0
    try:
        if not doel.exists():
            doel.mkdir(parents=True)
            lb.onthoud("map", pad=str(doel))
        for p in lijst:
            plek = doel / p.name
            if plek.exists():
                if plek.stat().st_size == p.stat().st_size:
                    continue   # (vrijwel zeker) hetzelfde lettertype van een vorige keer
                plek = _vrije_naam(plek)
            shutil.copyfile(p, plek)
            lb.bestand_erbij(plek)
            nieuw += 1
    except OSError:
        return [ot.Uitslag("lettertypen", ZELF, t("Lukte niet: is je computer vol, of is de stick eruit? Probeer het "
                                                  "opnieuw.", "Did not work: is your computer full, or was the drive "
                                                  "unplugged? Try again."))]
    # fc-cache: dan kennen alle programma's ze meteen (anders pas na opnieuw inloggen).
    if nieuw and shutil.which("fc-cache"):
        try:
            subprocess.run(["fc-cache", "-f", str(doel)], capture_output=True, timeout=120)
        except (OSError, subprocess.SubprocessError):
            pass
    if not nieuw:
        return [ot.Uitslag("lettertypen", GOED, t("Ze stonden er al.", "They were already there."))]
    return [ot.Uitslag("lettertypen", GOED, t("{n} lettertypen staan erin. Een programma dat al open was, ziet ze na "
                                              "opnieuw openen.", "{n} fonts are installed. A program that was already "
                                              "open sees them after you open it again.").format(n=nieuw)
                       if nieuw != 1 else t("1 lettertype staat erin.", "1 font is installed."))]


def _vrije_naam(pad: Path) -> Path:
    n = 2
    while (nieuw := pad.with_name(f"{pad.stem} ({n}){pad.suffix}")).exists():
        n += 1
    return nieuw


# =============================================================== Thunderbird ===

def thunderbird_op_stick(bron: Path, i: dict) -> Path | None:
    """De map van het Thunderbird-profiel op de stick, alleen als het echt een profiel is."""
    pad = ot.binnen_stick(bron, i.get("thunderbird_profiel"))
    try:
        if pad is None or not pad.is_dir() or not ((pad / "prefs.js").is_file() or (pad / "Mail").is_dir()):
            return None
    except OSError:
        return None
    return pad


def thunderbird_soort() -> str:
    """'flatpak' (uit de Winkel), 'rpm' (gewoon programma) of '' (Thunderbird is er (nog) niet)."""
    if shutil.which("thunderbird"):
        return "rpm"
    if shutil.which("flatpak"):
        try:
            if subprocess.run(["flatpak", "info", FLATPAK_THUNDERBIRD], capture_output=True, timeout=15).returncode == 0:
                return "flatpak"
        except (OSError, subprocess.SubprocessError):
            pass
    return ""


def thunderbird_map(soort: str) -> Path:
    """De map met profiles.ini. Zonder Thunderbird: die van de Flatpak (zo installeer je hem in de Winkel), zodat
    je mail meteen klaarstaat zodra je hem installeert."""
    if soort == "rpm":
        return Path.home() / ".thunderbird"
    return Path.home() / ".var" / "app" / FLATPAK_THUNDERBIRD / ".thunderbird"


def thunderbird_draait() -> bool:
    if not shutil.which("pgrep"):
        return False
    for naam in ("thunderbird", "thunderbird-bin"):
        try:
            if subprocess.run(["pgrep", "-u", str(os.getuid()), "-x", naam], capture_output=True,
                              timeout=5).returncode == 0:
                return True
        except (OSError, subprocess.SubprocessError):
            pass
    return False


def zet_thunderbird(bron: Path, i: dict) -> list[ot.Uitslag]:
    """Het Thunderbird-profiel van Windows als nieuw profiel 'Van Windows', en dat wordt het standaardprofiel. Een
    profiel dat er al was, blijft (als reserve). Is Thunderbird er nog niet, dan staat alles alvast klaar."""
    import bugos_overstap_firefox as ff
    pad = thunderbird_op_stick(bron, i)
    if pad is None:
        return []
    naam = ff.map_titel(ot._tekst(i.get("computer"), 40))
    if bi.VOORBEELD:
        return [ot.Uitslag("mail", GOED, t("Thunderbird opent met je accounts, mappen en adresboek.",
                                           "Thunderbird opens with your accounts, folders and address book."))]
    if thunderbird_draait():
        return [ot.Uitslag("mail", ZELF, t("Thunderbird stond open. Sluit hem en druk nog eens op Overzetten (alleen "
                                           "'E-mail' aan is genoeg).", "Thunderbird was open. Close it and press "
                                           "Transfer again (only 'E-mail' on is enough)."))]
    soort = thunderbird_soort()
    map_ = thunderbird_map(soort)
    ini = ff._ini(map_ / "profiles.ini")
    if any(ini[s].get("Name") == naam for s in ini.sections() if s.startswith("Profile")):
        return [ot.Uitslag("mail", GOED, t("Je Thunderbird van Windows stond er al.",
                                           "Your Thunderbird from Windows was already there."))]
    fout = ff.profiel_erbij(map_, pad, naam, "van-windows", THUNDERBIRD_NIET)
    if fout == "kopie":
        return [ot.Uitslag("mail", ZELF, t("Kopiëren lukte niet (is je computer vol, of is de stick eruit?). Probeer "
                                           "het opnieuw.", "Copying did not work (is your computer full, or was the "
                                           "drive unplugged?). Try again."))]
    if fout == "ini":
        return [ot.Uitslag("mail", ZELF, t("Het profiel staat er, maar kiezen lukte niet. Start Thunderbird met "
                                           "'thunderbird -P' en kies '{n}'.", "The profile is there, but choosing it "
                                           "did not work. Start Thunderbird with 'thunderbird -P' and choose "
                                           "'{n}'.").format(n=naam))]
    tekst = t("Je accounts, mappen en adresboek staan klaar. Je wachtwoord vraagt Thunderbird één keer per account.",
              "Your accounts, folders and address book are ready. Thunderbird asks your password once per account.")
    if not soort:
        # Nog geen Thunderbird: alles staat al klaar in de map van de Flatpak; installeren doe je zelf (de eigenaar:
        # BugOS installeert nooit zelf iets).
        return [ot.Uitslag("mail", ZELF, tekst + " " + t("Installeer nu Thunderbird in de Winkel: dan is alles er "
                                                         "meteen.", "Now install Thunderbird from the Store: then "
                                                         "everything is there right away."))]
    return [ot.Uitslag("mail", GOED, tekst)]


# ================================================================== Outlook ===

def outlook_bestanden(bron: Path, i: dict) -> list[Path]:
    """De .pst-bestanden die op de stick staan (in Outlook/ of in Documents/)."""
    uit = []
    for rel in ot._lijst(ot._dict(i.get("outlook")).get("pst")):
        p = ot.binnen_stick(bron, rel)
        try:
            if p is not None and p.is_file() and p.suffix.lower() == ".pst":
                uit.append(p)
        except OSError:
            continue
    return uit


def zet_outlook(bron: Path, i: dict, documenten: Path) -> list[ot.Uitslag]:
    """De .pst-bestanden uit Outlook/ naar Documenten/Outlook-bestanden (die uit Documents gingen al mee met je
    bestanden), en eerlijk zeggen wat je ermee kunt: BugOS en Thunderbird openen .pst niet zelf."""
    import bugos_overstap_logboek as lb
    lijst = outlook_bestanden(bron, i)
    if not lijst:
        return []
    doel = documenten / "Outlook-bestanden"
    namen = []
    try:
        for p in lijst:
            if "Outlook" not in p.relative_to(bron).parts[:1]:
                namen.append(p.name)   # stond in Documents: is al met je bestanden meegekomen
                continue
            if not doel.exists():
                doel.mkdir(parents=True)
                lb.onthoud("map", pad=str(doel))
            plek = doel / p.name
            if plek.exists() and plek.stat().st_size == p.stat().st_size:
                namen.append(p.name)
                continue
            if plek.exists():
                plek = _vrije_naam(plek)
            shutil.copyfile(p, plek)
            lb.bestand_erbij(plek)
            namen.append(plek.name)
    except (OSError, ValueError):
        return [ot.Uitslag("outlook", ZELF, t("Je Outlook-bestanden kopiëren lukte niet. Probeer het opnieuw.",
                                              "Copying your Outlook files did not work. Try again."))]
    return [ot.Uitslag("outlook", ZELF, t(
        "Je Outlook-mailbestanden ({b}) staan in Documenten. Staat je mail bij outlook.com, Gmail of je werk, dan staat "
        "hij gewoon online: voeg je account toe in Thunderbird of open hem in Firefox. Een oud archief (.pst) kan "
        "Thunderbird alleen op Windows inlezen: doe dat daar, en neem dan je Thunderbird mee.",
        "Your Outlook mail files ({b}) are in Documents. If your mail is at outlook.com, Gmail or work, it is simply "
        "online: add your account in Thunderbird or open it in Firefox. An old archive (.pst) can only be read by "
        "Thunderbird on Windows: do that there, then bring your Thunderbird along.").format(b=ot._kort(namen, 3)))]


# ================================================================= OneDrive ===

def cloud_uitslag(i: dict) -> list[ot.Uitslag]:
    """Bestanden die alleen in OneDrive stonden en NIET mee zijn gekomen: zeg welke, en waar je ze vindt."""
    c = ot._dict(i.get("cloud"))
    aantal = c.get("aantal")
    if not isinstance(aantal, int) or isinstance(aantal, bool) or aantal <= 0 or c.get("meegenomen") is True:
        return []
    voorbeelden = [n for n in (ot._tekst(v, 80) for v in ot._lijst(c.get("voorbeelden"))) if n]
    tekst = t("{n} bestanden stonden alleen in OneDrive en zijn niet meegekomen{v}. Ze staan nog in OneDrive: open ze "
              "in Firefox via onedrive.live.com.", "{n} files were only in OneDrive and did not come along{v}. They are "
              "still in OneDrive: open them in Firefox at onedrive.live.com.").format(
                  n=aantal, v=(t(" (bijv. {b})", " (e.g. {b})").format(b=ot._kort(voorbeelden, 3)) if voorbeelden else ""))
    return [ot.Uitslag("bestanden", ZELF, tekst)]
