"""BugOS Instellingen: meldingen (plasmanotifyrc), standaardprogramma's (xdg-mime) en printers (CUPS).

Hoort bij bugos_config (importeer het via daar). draai, VOORBEELD, _VB en de KDE-hulpjes komen via
bugos_config (_c.draai), zodat een test die bi.draai of bi.VOORBEELD vervangt dat ook hier ziet.
"""

from __future__ import annotations

import getpass
import grp
import os
import pwd
import re
import shutil
import subprocess
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

import bugos_config as _c
from bugos_base import t


# =============================================================== meldingen ===

def lees_tot(tekst: str) -> bool:
    """Is 'Until' uit plasmanotifyrc nog niet voorbij? KDE schrijft 'jaar,maand,dag,uur,min,sec' of een ISO-tijd."""
    from datetime import datetime
    tekst = tekst.strip()
    if not tekst:
        return False
    nu = datetime.now().astimezone()
    # KConfig schrijft de seconden met een komma-deel ("7.913") en soms een tijdzone als 7e veld (U072).
    delen = tekst.split(",")
    try:
        if len(delen) >= 3:
            getallen = [int(float(x)) for x in delen[:6]]
            zone = None
            if len(delen) > 6:
                from zoneinfo import ZoneInfo
                try:
                    zone = ZoneInfo(delen[6].strip())
                except (ValueError, KeyError, OSError):
                    zone = None
            tot = datetime(*getallen, tzinfo=zone) if zone else datetime(*getallen).astimezone()
            return tot > nu
    except (ValueError, TypeError, OverflowError):
        pass
    try:
        tot = datetime.fromisoformat(tekst.replace("Z", "+00:00"))
        return (tot if tot.tzinfo else tot.astimezone()) > nu
    except ValueError:
        return False


def niet_storen() -> bool:
    if _c.VOORBEELD:
        return _c._VB["niet_storen"]
    return lees_tot(_c.kde_lees("plasmanotifyrc", "DoNotDisturb", "Until", ""))


def zet_niet_storen(aan: bool) -> None:
    """Aan: geen pop-ups tot je het weer uitzet (ze komen wel in de lijst)."""
    if _c.VOORBEELD:
        _c._VB["niet_storen"] = aan
        return
    _c.kde_schrijf("plasmanotifyrc", "DoNotDisturb", "Until", "2999,12,31,0,0,0" if aan else None)


def stil_bij_games() -> bool:
    if _c.VOORBEELD:
        return _c._VB["stil_bij_games"]
    return _c.kde_lees("plasmanotifyrc", "DoNotDisturb", "WhenFullscreen", "true") == "true"


def zet_stil_bij_games(aan: bool) -> None:
    if _c.VOORBEELD:
        _c._VB["stil_bij_games"] = aan
        return
    _c.kde_schrijf("plasmanotifyrc", "DoNotDisturb", "WhenFullscreen", "true" if aan else "false")


def meldingsgeluid() -> bool:
    if _c.VOORBEELD:
        return _c._VB["geluidje"]
    return _c.kde_lees("plasmanotifyrc", "DoNotDisturb", "NotificationSoundsMuted", "false") != "true"


def zet_meldingsgeluid(aan: bool) -> None:
    if _c.VOORBEELD:
        _c._VB["geluidje"] = aan
        return
    _c.kde_schrijf("plasmanotifyrc", "DoNotDisturb", "NotificationSoundsMuted", "false" if aan else "true")


def proefmelding(titel: str, tekst: str) -> bool:
    if _c.VOORBEELD:
        return True
    return _c.draai("notify-send", "-a", "BugOS", "-i", "bugos-logo", "--hint=string:desktop-entry:bugos-settings",
                    titel, tekst, timeout=5)[0] == 0   # (U323)


# ====================================================== standaardprogramma's ===

# (sleutel, icoon, (naam nl, naam en), bestandstypes)
SOORTEN = [
    ("internet", "wereld", ("Internet", "Internet"), ["x-scheme-handler/http", "x-scheme-handler/https", "text/html"]),
    ("mail", "praten", ("E-mail", "Email"), ["x-scheme-handler/mailto"]),
    ("fotos", "foto", ("Foto's", "Photos"), ["image/jpeg", "image/png", "image/webp", "image/gif", "image/heif"]),
    ("muziek", "muziek", ("Muziek", "Music"), ["audio/mpeg", "audio/flac", "audio/x-wav", "audio/ogg", "audio/mp4"]),
    ("videos", "film", ("Video's", "Videos"), ["video/mp4", "video/x-matroska", "video/webm", "video/x-msvideo",
                                               "video/quicktime"]),
    ("pdf", "document", ("PDF-bestanden", "PDF files"), ["application/pdf"]),
    ("kantoor", "document", ("Documenten (Word)", "Documents (Word)"),
     ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/vnd.oasis.opendocument.text",
      "application/msword", "application/rtf"]),
    ("rekenen", "grafiek", ("Rekenbladen (Excel)", "Spreadsheets (Excel)"),
     ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.oasis.opendocument.spreadsheet",
      "application/vnd.ms-excel", "text/csv"]),
    ("zip", "map", ("Zip-bestanden", "Zip files"),
     ["application/zip", "application/x-7z-compressed", "application/vnd.rar", "application/x-compressed-tar",
      "application/x-tar"]),
    ("tekst", "potlood", ("Tekstbestanden", "Text files"), ["text/plain"]),
]

_VB_APPS = {"internet": ("firefox.desktop", [("firefox.desktop", "Firefox"), ("org.chromium.Chromium.desktop", "Chromium")]),
            "mail": ("org.mozilla.Thunderbird.desktop", [("org.mozilla.Thunderbird.desktop", "Thunderbird")]),
            "fotos": ("org.kde.gwenview.desktop", [("org.kde.gwenview.desktop",
                                                    t("Gwenview (foto's bekijken)", "Gwenview (view photos)")),
                                                   ("org.kde.krita.desktop", "Krita")]),
            "muziek": ("org.kde.elisa.desktop", [("org.kde.elisa.desktop", t("Elisa (muziek)", "Elisa (music)")),
                                                 ("vlc.desktop", "VLC")]),
            "videos": ("org.kde.haruna.desktop", [("org.kde.haruna.desktop", "Haruna (video)"), ("vlc.desktop", "VLC")]),
            "pdf": ("org.kde.okular.desktop", [("org.kde.okular.desktop", t("Okular (documenten)", "Okular (documents)")),
                                               ("firefox.desktop", "Firefox")]),
            "kantoor": ("org.libreoffice.LibreOffice.writer.desktop",
                        [("org.libreoffice.LibreOffice.writer.desktop", "LibreOffice Writer")]),
            "rekenen": ("org.libreoffice.LibreOffice.calc.desktop",
                        [("org.libreoffice.LibreOffice.calc.desktop",
                          t("LibreOffice Calc (rekenbladen)", "LibreOffice Calc (spreadsheets)"))]),
            "zip": ("org.kde.ark.desktop", [("org.kde.ark.desktop", "Ark")]),
            # (voorbeeld) Tekstbestanden openen standaard in de eenvoudige Teksteditor, KWrite (A-14).
            "tekst": ("org.kde.kwrite.desktop", [("org.kde.kwrite.desktop", t("Teksteditor", "Text editor")),
                                                 ("org.kde.kate.desktop", t("Kate (voor programmeurs)",
                                                                            "Kate (for programmers)"))])}


def app_mappen() -> list[Path]:
    thuis = Path.home()
    mappen = [thuis / ".local/share/applications", thuis / ".local/share/flatpak/exports/share/applications",
              Path("/var/lib/flatpak/exports/share/applications")]
    for d in (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":"):
        if d:
            mappen.append(Path(d) / "applications")
    return mappen


def lees_mimeinfo(tekst: str) -> dict[str, list[str]]:
    """Uit: mimeinfo.cache -> {bestandstype: [programma.desktop, ...]}."""
    uit: dict[str, list[str]] = {}
    for regel in tekst.splitlines():
        if "=" in regel and not regel.startswith("["):
            soort, apps = regel.split("=", 1)
            uit.setdefault(soort.strip(), []).extend(a for a in apps.split(";") if a.strip())
    return uit


def lees_desktop_naam(tekst: str, taalcode: str = "nl") -> str | None:
    """De naam uit een .desktop-bestand (in de taal van de gebruiker); None als het programma verborgen is."""
    namen: dict[str, str] = {}
    in_hoofd = False
    for regel in tekst.splitlines():
        regel = regel.strip()
        if regel.startswith("["):
            in_hoofd = regel == "[Desktop Entry]"
        elif in_hoofd and "=" in regel:
            sleutel, waarde = (x.strip() for x in regel.split("=", 1))
            if sleutel == "NoDisplay" and waarde.lower() == "true":
                return None
            if sleutel == "Name" or sleutel == f"Name[{taalcode}]":
                namen[sleutel] = waarde
    return namen.get(f"Name[{taalcode}]") or namen.get("Name")


def app_naam(desktop_id: str, taalcode: str = "nl", ook_verborgen: bool = False) -> str | None:
    for map_ in app_mappen():
        pad = map_ / desktop_id
        if pad.is_file():
            try:
                naam = lees_desktop_naam(pad.read_text(encoding="utf-8", errors="replace"), taalcode)
            except OSError:
                return None
            if naam is None and ook_verborgen:
                return desktop_id.removesuffix(".desktop")
            return naam
    return desktop_id.removesuffix(".desktop") if ook_verborgen else None


def apps_voor(sleutel: str, taalcode: str = "nl") -> list[tuple[str, str]]:
    """[(programma.desktop, naam)] die dit soort bestanden kunnen openen."""
    if _c.VOORBEELD:
        return _VB_APPS[sleutel][1]
    soorten = next(s for s in SOORTEN if s[0] == sleutel)[3]
    gezien: dict[str, str] = {}
    for map_ in app_mappen():
        try:
            cache = lees_mimeinfo((map_ / "mimeinfo.cache").read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        for soort in soorten:
            for app in cache.get(soort, []):
                if app not in gezien:
                    naam = app_naam(app, taalcode)
                    if naam:
                        gezien[app] = naam
    return sorted(gezien.items(), key=lambda x: x[1].lower())


def standaard_app(sleutel: str) -> str:
    """Welk programma.desktop opent dit nu?"""
    if _c.VOORBEELD:
        if _c._VB["apps"] is None:
            _c._VB["apps"] = {k: v[0] for k, v in _VB_APPS.items()}
        return _c._VB["apps"][sleutel]
    soort = next(s for s in SOORTEN if s[0] == sleutel)[3][0]
    return _c.draai("xdg-mime", "query", "default", soort, timeout=5)[1].strip()


def zet_standaard_app(sleutel: str, desktop_id: str) -> bool:
    if _c.VOORBEELD:
        standaard_app(sleutel)
        _c._VB["apps"][sleutel] = desktop_id
        return True
    soorten = next(s for s in SOORTEN if s[0] == sleutel)[3]
    goed = _c.draai("xdg-mime", "default", desktop_id, *soorten, timeout=10)[0] == 0
    if sleutel == "internet":
        _c.draai("xdg-settings", "set", "default-web-browser", desktop_id, timeout=10)
    return goed


# ------------------------------------------------- 'Een ander soort bestand...' ---
# Kies een bestand; BugOS zegt wat voor soort het is en laat je het programma kiezen (xdg-mime, net als KDE en GTK).

MIME_RE = re.compile(r"^[a-z0-9][a-z0-9.+-]*/[A-Za-z0-9][A-Za-z0-9.+_-]*$")
DESKTOP_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]*\.desktop$")
# Wat BugOS zelf regelt (programma's voor Windows, pakketten, mappen, de Winkel): niet om te zetten. Deels uit
# /etc/xdg/kde-mimeapps.list, deels een eigen keuze (review R14).
EIGEN_SOORTEN = {
    "application/x-ms-dos-executable", "application/x-msdownload", "application/x-msi",
    "application/vnd.microsoft.portable-executable", "application/x-rpm", "application/x-redhat-package-manager",
    "application/vnd.debian.binary-package", "application/x-deb", "inode/directory", "application/x-desktop",
    "application/x-executable", "application/x-sharedlib", "application/vnd.flatpak.ref",
    "application/vnd.flatpak.repo", "application/vnd.flatpak",
}
# Een ouder als zip (Word, EPUB) of 'een rij bytes' zegt niets: Ark is geen goed programma voor een Word-bestand (R15).
_LEGE_OUDERS = {"application/zip", "application/octet-stream"}


def mime_mappen() -> list[Path]:
    mappen = [Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "mime"]
    for d in (os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share").split(":"):
        if d:
            mappen.append(Path(d) / "mime")
    return mappen


def bestandssoort(pad: str) -> str | None:
    """Wat voor soort bestand is dit (application/epub+zip)? Alleen de soort wordt gelezen, het bestand niet geopend."""
    if _c.VOORBEELD:
        return "application/epub+zip"
    if not os.path.isabs(pad):
        return None
    soort = _c.draai("xdg-mime", "query", "filetype", pad, timeout=5)[1].strip()
    return soort if MIME_RE.match(soort) else None


def soort_naam(mime: str, taalcode: str = "nl") -> str:
    """'application/epub+zip' -> 'EPUB e-book' (of in het Nederlands), uit shared-mime-info. Anders de soort zelf."""
    if _c.VOORBEELD:
        return t("EPUB-e-boek", "EPUB e-book") if mime == "application/epub+zip" else mime
    if not MIME_RE.match(mime):
        return mime
    import xml.etree.ElementTree as ET
    ns = "{http://www.freedesktop.org/standards/shared-mime-info}"
    taal_sleutel = "{http://www.w3.org/XML/1998/namespace}lang"
    for m in mime_mappen():
        pad = m / (mime + ".xml")
        try:
            wortel = ET.parse(pad).getroot()
        except (OSError, ET.ParseError):
            continue
        gewoon, eigen = "", ""
        for c in wortel.iter(ns + "comment"):
            if c.get(taal_sleutel) == taalcode:
                eigen = (c.text or "").strip()
            elif c.get(taal_sleutel) is None:
                gewoon = (c.text or "").strip()
        naam = schone_tekst(eigen or gewoon, 80)
        if naam:
            return naam
    return mime


def ouders(mime: str, diepte: int = 3) -> list[str]:
    """De soorten waar deze soort een vorm van is (/usr/share/mime/subclasses), tot drie stappen ver."""
    tabel: dict[str, list[str]] = {}
    for m in mime_mappen():
        try:
            tekst = (m / "subclasses").read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for regel in tekst.splitlines():
            d = regel.split()
            if len(d) == 2:
                tabel.setdefault(d[0], []).append(d[1])
    uit: list[str] = []
    rij = [mime]
    for _ in range(diepte):
        volgende = []
        for s in rij:
            for o in tabel.get(s, []):
                if o not in uit and o != mime:
                    uit.append(o)
                    volgende.append(o)
        rij = volgende
    return uit


def _apps_voor_mimes(mimes: list[str], taalcode: str) -> list[tuple[str, str]]:
    gezien: dict[str, str] = {}
    for map_ in app_mappen():
        try:
            cache = lees_mimeinfo((map_ / "mimeinfo.cache").read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        for soort in mimes:
            for app in cache.get(soort, []):
                if app not in gezien and DESKTOP_RE.match(app):
                    naam = app_naam(app, taalcode)
                    if naam:
                        gezien[app] = naam
    return sorted(gezien.items(), key=lambda x: x[1].lower())


def apps_voor_soort(mime: str, taalcode: str = "nl") -> list[tuple[str, str]]:
    """Programma's voor precies deze soort, dan die voor de soorten waar hij een vorm van is (niet zip: R15)."""
    if _c.VOORBEELD:
        return [("org.kde.okular.desktop", "Okular"), ("org.kde.kate.desktop", t("Kate (tekst)", "Kate (text)"))]
    eerst = _apps_voor_mimes([mime], taalcode)
    dan = _apps_voor_mimes([o for o in ouders(mime) if o not in _LEGE_OUDERS], taalcode)
    return eerst + [a for a in dan if a[0] not in dict(eerst)]


def alle_apps(taalcode: str = "nl") -> list[tuple[str, str]]:
    """Elk programma dat bestanden kan openen (Exec met %f, %F, %u of %U), voor 'Een ander programma...'."""
    if _c.VOORBEELD:
        return [("org.kde.okular.desktop", "Okular"), ("org.kde.kate.desktop", "Kate"), ("firefox.desktop", "Firefox"),
                ("org.kde.ark.desktop", "Ark")]
    gezien: dict[str, str] = {}
    for map_ in app_mappen():
        try:
            bestanden = sorted(map_.glob("*.desktop"))
        except OSError:
            continue
        for pad in bestanden:
            if pad.name in gezien or not DESKTOP_RE.match(pad.name):
                continue
            try:
                tekst = pad.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            hoofd = tekst.split("\n[", 1)[0]
            if not re.search(r"^Type\s*=\s*Application\s*$", hoofd, re.M) or \
                    not re.search(r"^Exec\s*=.*%[fFuU]", hoofd, re.M):
                continue
            naam = lees_desktop_naam(tekst, taalcode)
            if naam:
                gezien[pad.name] = naam
    return sorted(gezien.items(), key=lambda x: x[1].lower())


def standaard_voor_soort(mime: str) -> str:
    if _c.VOORBEELD:
        return _c._VB.setdefault("soort_apps", {}).get(mime, "org.kde.okular.desktop")
    if not MIME_RE.match(mime):
        return ""
    return _c.draai("xdg-mime", "query", "default", mime, timeout=5)[1].strip()


def mag_soort_zetten(mime: str) -> bool:
    return bool(MIME_RE.match(mime)) and mime not in EIGEN_SOORTEN and not mime.startswith("x-scheme-handler/") \
        and not mime.startswith("inode/")


def zet_standaard_voor_soort(mime: str, desktop_id: str) -> bool:
    """Open deze soort voortaan met dit programma (~/.config/mimeapps.list, voor KDE en GTK)."""
    if not mag_soort_zetten(mime) or not DESKTOP_RE.match(desktop_id):
        return False
    if _c.VOORBEELD:
        _c._VB.setdefault("soort_apps", {})[mime] = desktop_id
        return True
    return _c.draai("xdg-mime", "default", desktop_id, mime, timeout=10)[0] == 0


# ------------------------------------------------------------------- meldingen per app ---

def app_meldingen(taalcode: str = "nl") -> list[tuple[str, str, bool]]:
    """[(app, naam, aan)] voor elke app die al eens een melding gaf (plasmanotifyrc [Applications][app]).
    BugOS zelf niet: updates en 'opnieuw opstarten' moet je blijven zien (review R21)."""
    if _c.VOORBEELD:
        return _c._VB.setdefault("app_meldingen", [("firefox", "Firefox", True),
                                                   ("org.mozilla.Thunderbird", "Thunderbird", True),
                                                   ("org.telegram.desktop", "Telegram", False)])
    pad = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "plasmanotifyrc"
    try:
        tekst = pad.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    uit = []
    for m in re.finditer(r"^\[Applications\]\[([^\]\n]+)\]\s*$", tekst, re.M):
        app = m.group(1)
        if app.startswith(("bugos", "org.bugos")) or not re.match(r"^[A-Za-z0-9._-]+$", app) or \
                any(a == app for a, _n, _x in uit):
            continue
        naam = app_naam(f"{app}.desktop", taalcode)
        if not naam:
            continue
        aan = _c.kde_lees_groepen("plasmanotifyrc", ["Applications", app], "ShowPopups", "true") != "false"
        uit.append((app, naam, aan))
    return sorted(uit, key=lambda x: x[1].lower())


def zet_app_meldingen(app: str, aan: bool) -> bool:
    """Berichtjes van deze app wel of niet in beeld (ze komen nog wel in de lijst: ShowInHistory blijft)."""
    if not re.match(r"^[A-Za-z0-9._-]+$", app) or app.startswith(("bugos", "org.bugos")):
        return False
    if _c.VOORBEELD:
        _c._VB["app_meldingen"] = [(a, n, aan if a == app else x) for a, n, x in app_meldingen()]
        return True
    return _c.kde_schrijf("plasmanotifyrc", ["Applications", app], "ShowPopups", None if aan else "false")


# ================================================================ printers ===
# Alles gaat via de gewone CUPS-programma's (lpstat, lpadmin, lpoptions, cancel). Wie in de groep wheel zit, is voor
# CUPS beheerder over de eigen socket (cups-files.conf: SystemGroup sys root wheel, PeerCred on): zonder wachtwoord.
# Anderen vragen via pkexec één keer het wachtwoord van een beheerder (org.bugos.printers.policy). Nooit een shell:
# alles is een lijst met argumenten, en wat van buiten komt (namen uit het netwerk, wat je typt) wordt eerst gecontroleerd.

LPADMIN = "/usr/bin/lpadmin"   # /usr/sbin is in Fedora een link naar bin: dit is het echte pad (pkexec, polkit)
LPINFO = "/usr/bin/lpinfo"
NAAM_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,126}$")   # een wachtrij: niet met '-' of '.' beginnen
TAAK_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]*-\d+$")


def cups_draai(*cmd: str, timeout: int = 15, fout: bool = True) -> tuple[int, str]:
    """Zoals draai, maar met de foutmelding erbij (CUPS zegt alles op stderr; fout=False: alleen stdout) en een lege
    invoer, zodat lpadmin nooit op een wachtwoord blijft wachten. Te lang: code 124. Bestaat het niet: 127."""
    if not shutil.which(cmd[0]):
        return 127, ""
    try:
        r = subprocess.run(list(cmd), input="", capture_output=True, text=True, timeout=timeout,
                           env=_c.omgeving(cmd[0]))
        return r.returncode, (r.stdout or "") + ((r.stderr or "") if fout else "")
    except subprocess.TimeoutExpired:
        return 124, ""
    except (OSError, subprocess.SubprocessError, ValueError):
        return 1, ""


_FOUTEN = (
    ("verboden", ("forbidden", "not-authorized", "unauthorized", "not authorized")),
    ("onbereikbaar", ("unable to connect", "timed out", "host is down", "no route to host", "name or service not known",
                      "connection refused", "unable to locate printer")),
    ("geen_driverless", ("unable to create ppd", "does not support required ipp attributes")),
    ("bestaat_niet", ("does not exist", "invalid destination")),
)


def cups_fout(code: int, uitvoer: str) -> str:
    """'ok' bij code 0 (een waarschuwing als 'drivers are deprecated' telt niet), anders wat er misging:
    verboden, onbereikbaar, geen_driverless, bestaat_niet of anders. (Geweigerd bij pkexec: zie als_beheerder.)"""
    if code == 0:
        return "ok"
    if code == 124:
        return "onbereikbaar"
    laag = uitvoer.lower()
    for soort, stukjes in _FOUTEN:
        if any(s in laag for s in stukjes):
            return soort
    return "anders"


def ben_beheerder() -> bool:
    """Mag ik CUPS zonder wachtwoord veranderen? (wheel, sys of root, zoals SystemGroup in cups-files.conf)"""
    if _c.VOORBEELD:
        return _c._VB.setdefault("printer_beheerder", True)
    if os.getuid() == 0:
        return True
    ik = getpass.getuser()
    try:
        eigen_gid = pwd.getpwnam(ik).pw_gid
    except KeyError:
        eigen_gid = os.getgid()
    for naam in ("wheel", "sys", "root"):
        try:
            g = grp.getgrnam(naam)
        except KeyError:
            continue
        if ik in g.gr_mem or g.gr_gid == eigen_gid:
            return True
    return False


def als_beheerder(*cmd: str, timeout: int = 15) -> tuple[str, str]:
    """Een opdracht die CUPS alleen van een beheerder aanneemt (lpadmin, of lpinfo voor printers met een kabel).
    Geeft (soort, uitvoer): 'ok', 'geweigerd' (geen wachtwoord gegeven) of wat cups_fout zegt. Hooguit één keer
    pkexec per keer: wie het wachtwoord niet weet, krijgt geen tweede venster (review R3)."""
    if cmd[0] not in ("lpadmin", "lpinfo"):
        raise ValueError(cmd[0])
    if _c.ben_beheerder():
        code, uit = _c.cups_draai(cmd[0], *cmd[1:], timeout=timeout)
        soort = cups_fout(code, uit)
        if soort != "verboden":   # verboden: pas net in de groep gezet, nog niet opnieuw ingelogd -> één keer pkexec
            return soort, uit
    if not shutil.which("pkexec"):
        return "anders", ""
    # Lang wachten: eerst typt iemand het wachtwoord, dan praat lpadmin nog met de printer (review R12).
    code, uit = _c.cups_draai("pkexec", LPADMIN if cmd[0] == "lpadmin" else LPINFO, *cmd[1:],
                              timeout=max(timeout, 180))
    if code in (126, 127):   # 126: Annuleren geklikt, 127: geen toestemming (pkexec zelf, review R11)
        return "geweigerd", uit
    return cups_fout(code, uit), uit


def schone_tekst(tekst: str, lengte: int = 127) -> str:
    """Een naam of plek van buiten (het netwerk, wat je typt): zonder tabs, regeleindes en andere stuurtekens."""
    return " ".join("".join(c if c.isprintable() else " " for c in tekst).split())[:lengte].strip()


# Wat lpstat -l -p onder een printer zet, en geen reden is (de reden staat er direct onder: '\tPaused').
_LPSTAT_SLEUTELS = ("Form mounted", "Content types", "Printer types", "Description", "Alerts", "Location",
                    "Connection", "Interface", "On fault", "After fault", "Users allowed", "Users denied",
                    "Forms allowed", "Forms not allowed", "Banner required", "Charset sets", "Default pitch",
                    "Default page size", "Default port settings")
# Wat CUPS zegt als hij een printer op het netwerk niet vindt; de wachtrij blijft dan 'aan het printen' (review R6).
_ONBEREIKBAAR = ("may not exist or is unavailable", "not responding", "unable to connect",
                 "waiting for printer to become available", "unable to locate printer", "host is down",
                 "connection refused")


@dataclass
class Printer:
    naam: str           # technische naam (voor lp)
    omschrijving: str   # wat je ziet
    staat: str          # klaar, bezig of gestopt
    standaard: bool
    gepauzeerd: bool = False    # bewust gepauzeerd (cupsdisable), niet gestopt door een fout
    reden: str = ""             # wat CUPS erbij zegt ('Paused', 'Unable to connect to printer')
    locatie: str = ""
    onbereikbaar: bool = False  # CUPS wacht op de printer (uit, of niet op hetzelfde netwerk)


def lees_lpstat(printers_uit: str, standaard_uit: str) -> list[Printer]:
    """Uit: lpstat -l -p (printers) en lpstat -d (de standaard)."""
    m = re.search(r"destination:\s*(\S+)", standaard_uit)
    standaard = m.group(1) if m else ""
    lijst: list[Printer] = []
    net_printer = False
    for regel in printers_uit.splitlines():
        m = re.match(r"^printer (\S+) (is idle|now printing|disabled)", regel)
        if m:
            naam, staat = m.group(1), m.group(2)
            lijst.append(Printer(naam, naam.replace("_", " "),
                                 "klaar" if staat == "is idle" else "bezig" if staat == "now printing" else "gestopt",
                                 naam == standaard))
            net_printer = True
            continue
        direct_eronder, net_printer = net_printer, False
        if not lijst:
            continue
        tekst = regel.strip()
        if direct_eronder and regel.startswith("\t") and not regel.startswith("\t\t") and tekst and \
                not any(tekst == k or tekst.startswith(k + ":") for k in _LPSTAT_SLEUTELS):
            lijst[-1].reden = schone_tekst(tekst, 200)
        elif tekst.startswith("Description:"):
            omschrijving = schone_tekst(tekst.split(":", 1)[1])
            if omschrijving:
                lijst[-1].omschrijving = omschrijving
        elif tekst.startswith("Location:"):
            lijst[-1].locatie = schone_tekst(tekst.split(":", 1)[1])
    for p in lijst:
        p.gepauzeerd = p.staat == "gestopt" and p.reden in ("Paused", "Rejecting Jobs")
        p.onbereikbaar = any(s in p.reden.lower() for s in _ONBEREIKBAAR)
    return lijst


def printers() -> list[Printer]:
    if _c.VOORBEELD:
        if _c._VB["printers"] is None:
            _c._VB["printers"] = [Printer("HP_LaserJet", "Bugie's HP LaserJet", "klaar", True,
                                          locatie=t("Studeerkamer", "Study")),
                                  Printer("Canon_PIXMA", t("Canon PIXMA (boven)", "Canon PIXMA (upstairs)"), "gestopt",
                                          False, reden="Unable to connect to printer", onbereikbaar=True)]
        return _c._VB["printers"]
    if not shutil.which("lpstat"):
        return []
    return lees_lpstat(_c.draai("lpstat", "-l", "-p", timeout=8)[1], _c.draai("lpstat", "-d", timeout=8)[1])


def _eigen_regels() -> list[str]:
    """De regels van lpstat -o die van jou zijn (die van anderen kun je zonder beheerder niet weghalen, U158).
    Alleen lpstat -o zegt de hele naam van de eigenaar; lpq knipt hem af (review R10)."""
    ik = getpass.getuser()
    return [r for r in _c.draai("lpstat", "-o", timeout=8)[1].splitlines()
            if len(r.split()) >= 2 and r.split()[1] == ik]


def wachtrij() -> int:
    """Hoeveel documenten staan te wachten om geprint te worden."""
    if _c.VOORBEELD:
        return len(taken())
    return len(_eigen_regels())


def zet_standaard_printer(naam: str) -> bool:
    if _c.VOORBEELD:
        for p in printers():
            p.standaard = p.naam == naam
        return True
    return _c.draai("lpoptions", "-d", naam, timeout=8)[0] == 0


def testpagina(naam: str) -> bool:
    if _c.VOORBEELD:
        return True
    proef = "/usr/share/cups/data/testprint"
    if not os.path.exists(proef):
        return False
    return _c.draai("lp", "-d", naam, proef, timeout=15)[0] == 0


def _vb_printer(naam: str) -> Printer | None:
    return next((p for p in printers() if p.naam == naam), None)


def hervat_printer(naam: str) -> str:
    """Verder printen na een fout of een pauze: lpadmin -p Q -E zet hem aan én laat hem weer documenten aannemen.
    (Niet cupsenable via pkexec: dat is in BugOS een link naar cupsaccept, die op zijn eigen naam let.)"""
    if not NAAM_RE.match(naam):
        return "anders"
    if _c.VOORBEELD:
        p = _vb_printer(naam)
        if p:
            p.staat, p.gepauzeerd, p.reden, p.onbereikbaar = "klaar", False, "", False
        return "ok"
    return _c.als_beheerder("lpadmin", "-p", naam, "-E", timeout=15)[0]


def pauzeer_printer(naam: str) -> str:
    """Even niet printen (alleen voor een beheerder, zonder wachtwoord; nooit via pkexec)."""
    if not NAAM_RE.match(naam):
        return "anders"
    if _c.VOORBEELD:
        p = _vb_printer(naam)
        if p:
            p.staat, p.gepauzeerd, p.reden = "gestopt", True, "Paused"
        return "ok"
    code, uit = _c.cups_draai("cupsdisable", naam, timeout=8)
    return cups_fout(code, uit)


def verwijder_printer(naam: str) -> str:
    if not NAAM_RE.match(naam):
        return "anders"
    if _c.VOORBEELD:
        _c._VB["printers"] = [p for p in printers() if p.naam != naam]
        return "ok"
    soort = _c.als_beheerder("lpadmin", "-x", naam, timeout=15)[0]
    if soort == "ok":
        _c.cups_draai("lpoptions", "-x", naam, timeout=8)   # ook jouw eigen keuzes voor deze printer weg
    return soort


# ------------------------------------------------------------- instellingen van een printer ---
# Papier, één of twee kanten, kleur of zwart-wit: de PPD-namen (PageSize, Duplex, ColorModel) werken voor elke
# wachtrij, ook voor IPP Everywhere (lpadmin zet daar ook print-color-mode mee).

def lees_lpoptions_l(uitvoer: str) -> dict[str, tuple[list[str], str]]:
    """Uit: lpoptions -p Q -l -> {sleutel: ([keuzes], huidige)}. Elke regel 'Sleutel/Naam: a *b c'. Een foutregel
    ('lpoptions: Unable to get PPD file for nope: ...', met code 0!) heeft geen '/' voor de ':' en telt niet mee."""
    uit: dict[str, tuple[list[str], str]] = {}
    for regel in uitvoer.splitlines():
        kop, dubbelepunt, rest = regel.partition(":")
        if not dubbelepunt or "/" not in kop:
            continue
        sleutel = kop.split("/", 1)[0].strip()
        if not re.match(r"^[A-Za-z][A-Za-z0-9_-]*$", sleutel):
            continue
        keuzes, huidig = [], ""
        for k in rest.split():
            if k.startswith("*"):
                k = k[1:]
                huidig = k
            if k:
                keuzes.append(k)
        if keuzes:
            uit[sleutel] = (keuzes, huidig)
    return uit


@dataclass
class Opties:
    papier: str | None                  # wat er nu gekozen is (PageSize), None: geen regel
    papieren: list[tuple[str, str]]     # [(PageSize-keuze, wat je ziet)]
    zijden: str | None                  # 'een' of 'twee'; None: deze printer kan geen twee kanten
    zijden_waarde: dict[str, str]       # {'een': 'None', 'twee': 'DuplexNoTumble'}
    kleur: str | None                   # 'kleur' of 'zw'; None: geen keuze (een zwart-witprinter)
    kleur_waarde: dict[str, str]        # {'kleur': 'RGB', 'zw': 'Gray'}


_FOTO = ("4x6", "Photo4x6", "Card4x6", "100x150mm")
_GRIJS = ("KGray", "Gray", "Grayscale", "Black", "Mono", "Monochrome", "CMYGray")
_KLEUR = ("RGB", "CMYK", "Color", "CMY", "RGBW")


def _papier_namen() -> list[tuple[tuple[str, ...], str]]:
    # 'B5' is in CUPS de Japanse maat (JIS); de gewone B5 heet ISOB5 (review R19).
    return [(("A4",), "A4"), (("A5",), "A5"), (("A3",), "A3"), (("A6",), "A6"), (("ISOB5",), "B5"),
            (("Letter",), t("Letter (VS)", "Letter (US)")), (("Legal",), t("Legal (VS)", "Legal (US)")),
            (_FOTO, t("Foto 10 x 15 cm", "Photo 10 x 15 cm")), (("EnvDL",), t("Envelop DL", "Envelope DL")),
            (("Env10",), t("Envelop #10", "Envelope #10"))]


def printer_keuzes(ruw: dict[str, tuple[list[str], str]]) -> Opties | None:
    """Van de ruwe keuzes (lees_lpoptions_l) naar wat Bugie kiest: papier, kanten, kleur."""
    if not ruw:
        return None
    papier, papieren = None, []
    if "PageSize" in ruw:
        keuzes, papier = ruw["PageSize"]
        gewoon = [k for k in keuzes if "." not in k and not k.startswith("(") and not k.startswith("Custom")]
        for namen, tekst in _papier_namen():
            k = next((n for n in namen if n in gewoon), None)
            if k and len(papieren) < 8:
                papieren.append((k, tekst))
        if papier and papier not in [k for k, _ in papieren]:
            papieren.append((papier, papier))
    zijden, zijden_waarde = None, {}
    if "Duplex" in ruw:
        keuzes, nu = ruw["Duplex"]
        geen_eenheid = "OptionDuplex" in ruw and ruw["OptionDuplex"][1] == "False"   # 'Duplexer Installed: *False'
        if "None" in keuzes and "DuplexNoTumble" in keuzes and not geen_eenheid:
            zijden = "een" if nu == "None" else "twee"
            zijden_waarde = {"een": "None", "twee": nu if nu in ("DuplexNoTumble", "DuplexTumble") else "DuplexNoTumble"}
    kleur, kleur_waarde = None, {}
    if "ColorModel" in ruw:
        keuzes, nu = ruw["ColorModel"]
        grijs = next((k for k in _GRIJS if k in keuzes), None)
        kleurig = nu if nu in keuzes and nu not in _GRIJS else next((k for k in _KLEUR if k in keuzes), None)
        if grijs and kleurig:
            kleur = "zw" if nu in _GRIJS else "kleur"
            kleur_waarde = {"kleur": kleurig, "zw": grijs}
    return Opties(papier, papieren, zijden, zijden_waarde, kleur, kleur_waarde)


_GELEZEN: dict[str, dict[str, tuple[list[str], str]]] = {}   # wat printer_opties het laatst las: om mee te controleren


def _vb_opties() -> dict:
    brlaser = {"PageSize": (["A4", "A5", "A6", "B5", "B6", "EnvC5", "EnvMonarch", "EnvDL", "Executive", "Legal",
                             "Letter"], "A4"),
               "Duplex": (["None", "DuplexNoTumble", "DuplexTumble"], "None"), "ColorModel": (["Gray", "RGB"], "RGB")}
    hpcups = {"PageSize": (["Card3x5", "L", "L.FB", "Hagaki", "A6", "A5", "A5.FB", "A5.Duplex", "Photo4x6",
                            "Letter", "Letter.FB", "Letter.Duplex", "A4", "A4.FB", "A4.Duplex", "8.5x13", "Legal",
                            "EnvA2", "EnvDL", "Env10", "Custom.WIDTHxHEIGHT"], "A4"),
              "Duplex": (["DuplexNoTumble", "DuplexTumble", "None"], "None"),
              "ColorModel": (["RGB", "CMYGray", "KGray"], "RGB"), "OptionDuplex": (["False", "True"], "False")}
    return _c._VB.setdefault("printer_opties", {"HP_LaserJet": brlaser, "Canon_PIXMA": hpcups})


def printer_opties(naam: str) -> Opties | None:
    """De keuzes van deze printer, of None als BugOS ze niet kan lezen (dan in het printvenster van je programma)."""
    if not NAAM_RE.match(naam):
        return None
    if _c.VOORBEELD:
        ruw = {k: (list(v[0]), v[1]) for k, v in _vb_opties().get(naam, {}).items()}
    else:
        ruw = lees_lpoptions_l(_c.cups_draai("lpoptions", "-p", naam, "-l", timeout=8, fout=False)[1])
    _GELEZEN[naam] = ruw
    return printer_keuzes(ruw)


def zet_printer_opties(naam: str, wijzigingen: dict[str, str], beschrijving: str | None = None) -> str:
    """Bewaar de keuzes. Een beheerder voor iedereen (lpadmin -o, en -D voor de naam), anders alleen voor jou
    (lpoptions -o, zonder wachtwoord). Elke waarde moet een keuze zijn die printer_opties net las."""
    ruw = _GELEZEN.get(naam)
    if not NAAM_RE.match(naam) or ruw is None:
        return "anders"
    for sleutel, waarde in wijzigingen.items():
        if sleutel not in ruw or waarde not in ruw[sleutel][0]:
            return "anders"   # lpadmin slikt een onzinwaarde zonder iets te zeggen: dus zelf weigeren
    nieuw = {k: v for k, v in wijzigingen.items() if ruw[k][1] != v}
    beheerder = _c.ben_beheerder()
    if beschrijving is not None:
        beschrijving = schone_tekst(beschrijving)
        if not beschrijving or not beheerder:
            beschrijving = None
    if not nieuw and beschrijving is None:
        return "ok"
    if _c.VOORBEELD:
        for k, v in nieuw.items():
            _vb_opties()[naam][k] = (_vb_opties()[naam][k][0], v)
        if beschrijving:
            p = _vb_printer(naam)
            if p:
                p.omschrijving = beschrijving
        return "ok"
    o = [x for k, v in nieuw.items() for x in ("-o", f"{k}={v}")]
    if not beheerder:
        code, uit = _c.cups_draai("lpoptions", "-p", naam, *o, timeout=8)
        return cups_fout(code, uit)
    soort = _c.als_beheerder("lpadmin", "-p", naam, *o, *(("-D", beschrijving) if beschrijving else ()), timeout=15)[0]
    if soort == "ok" and nieuw:
        # Had je zelf eerder iets gekozen (~/.cups/lpoptions), dan zou dat de nieuwe keuze verbergen: weg ermee.
        try:
            eigen = (Path.home() / ".cups" / "lpoptions").read_text(encoding="utf-8", errors="replace")
        except OSError:
            eigen = ""
        for regel in eigen.splitlines():
            d = regel.split()
            if len(d) >= 2 and d[0] in ("Dest", "Default") and d[1] == naam:
                for k in nieuw:
                    if any(x.startswith(k + "=") for x in d[2:]):
                        _c.cups_draai("lpoptions", "-p", naam, "-r", k, timeout=8)
    return soort


@dataclass
class Taak:
    printer: str
    id: int
    titel: str       # '' als CUPS het niet weet (de pagina zegt dan 'Document')
    actief: bool     # wordt nu geprint


def lees_lpq(uitvoer: str) -> dict[int, tuple[str, bool]]:
    """Uit: lpq -P <printer> -> {taaknummer: (titel, wordt nu geprint)}. De kolom met de eigenaar knipt CUPS af op
    7 tekens: daar kijken we dus niet naar. Welke van jou zijn, zegt lpstat -o (review R10)."""
    uit: dict[int, tuple[str, bool]] = {}
    for regel in uitvoer.splitlines():
        m = re.match(r"^(\S+)\s+(\S+)\s+(\d+)\s+(.*?)\s+(\d+) bytes$", regel.strip())
        if m:
            uit[int(m.group(3))] = (schone_tekst(m.group(4), 100), m.group(1) == "active")
    return uit


def taken() -> list[Taak]:
    """Jouw documenten die nog geprint moeten worden, het eerste eerst."""
    if _c.VOORBEELD:
        return _c._VB.setdefault("taken", [Taak("HP_LaserJet", 12, t("Brief aan de bank.pdf", "Letter to the bank.pdf"),
                                                True)])
    lijst: list[Taak] = []
    for regel in _eigen_regels():
        printer, _, nummer = regel.split()[0].rpartition("-")
        if NAAM_RE.match(printer) and nummer.isdigit():
            lijst.append(Taak(printer, int(nummer), "", False))
    titels: dict[str, dict[int, tuple[str, bool]]] = {}
    for taak in lijst:
        if taak.printer not in titels:
            titels[taak.printer] = lees_lpq(_c.draai("lpq", "-P", taak.printer, timeout=8)[1])
        taak.titel, taak.actief = titels[taak.printer].get(taak.id, ("", False))
    return lijst


def annuleer_taak(printer: str, nummer: int) -> bool:
    taak = f"{printer}-{nummer}"
    if not TAAK_RE.match(taak):
        return False
    if _c.VOORBEELD:
        _c._VB["taken"] = [x for x in taken() if (x.printer, x.id) != (printer, nummer)]
        return True
    return _c.draai("cancel", taak, timeout=8)[0] == 0


def wachtrij_leegmaken() -> bool:
    if _c.VOORBEELD:
        _c._VB["taken"] = []
        return True
    # 'cancel -a' vraagt CUPS om álles (van iedereen): dat mag alleen een beheerder. Je eigen documenten wel (U158).
    # Maar 'cancel -u jij' weigert CUPS voor wie geen beheerder is ('Forbidden'): dan één voor één, met hun nummer.
    if _c.draai("cancel", "-u", getpass.getuser(), timeout=8)[0] == 0:
        return True
    goed = True
    for regel in _eigen_regels():
        taak = regel.split()[0]
        if TAAK_RE.match(taak):
            goed = _c.draai("cancel", taak, timeout=8)[0] == 0 and goed
    return goed


# ------------------------------------------------------------------------------ printer toevoegen ---
# Printers op je wifi (en via ipp-usb die met een kabel) melden zich met DNS-SD; ippfind vindt ze. Bijna elke printer
# van na ongeveer 2015 werkt zonder eigen software ('driverless', IPP Everywhere / AirPrint): lpadmin -m everywhere.

URI_RE = re.compile(r"^(ipps?|socket|usb|dnssd)://[^\s'\"\\]+$")
_HOST_RE = re.compile(r"^(?=.{1,253}$)[A-Za-z0-9]([A-Za-z0-9-]{0,62}[A-Za-z0-9])?(\.[A-Za-z0-9]([A-Za-z0-9-]{0,62}[A-Za-z0-9])?)*\.?$")
_PAD_RE = re.compile(r"^[A-Za-z0-9._~/%-]*$")
_DRIVERLESS = ("image/pwg-raster", "image/urf", "application/pdf")
_IPPFIND_VELDEN = ("{service_name}", "{service_scheme}", "{service_hostname}", "{service_port}", "{txt_rp}",
                   "{txt_ty}", "{txt_note}", "{txt_UUID}", "{txt_pdl}")
IPPTOOL_TEST = "/usr/share/cups/ipptool/get-printer-attributes.test"


@dataclass
class Gevonden:
    naam: str            # wat je ziet: "HP OfficeJet Pro 8010 series"
    dienst: str          # de DNS-SD-naam "HP OfficeJet Pro 8010 [A1B2C3]" ('' bij usb): daar komt de wachtrij-naam van
    uri: str             # wat lpadmin -v krijgt
    locatie: str         # de plek uit de printer zelf (TXT note), of ''
    soort: str           # 'netwerk', 'kabel' (ipp-usb) of 'usb' (een oude printer met een kabel)
    driverless: bool     # werkt zonder eigen software van de maker
    al_toegevoegd: bool
    model_hint: str      # merk en model, om de lijst met printersoftware alvast te filteren
    reserve_uri: str = ""    # ipp:// als uri ipps:// is
    proef_uri: str = ""      # ipps://host:poort/pad: om zonder wachtwoord te kijken of hij antwoordt (review R3)
    reserve_proef: str = ""


def _eigen_host() -> str:
    import socket
    return socket.gethostname().split(".")[0].lower()


def lees_ippfind(uitvoer: str, eigen_host: str) -> list[Gevonden]:
    """Uit: ippfind --exec printf '%s\\0' x 9. Elk veld eindigt op een NUL (die kan niet in een naam of TXT-waarde van
    het netwerk staan, een tab of regeleinde wel: review R5). Printers met een ipp- én een ipps-ingang worden één."""
    velden = uitvoer.split("\0")
    per: dict[str, dict[str, list[str]]] = {}
    volgorde: list[str] = []
    for i in range(0, len(velden) - 8, 9):
        dienst, schema, host, poort, rp, ty, notitie, uuid, pdl = velden[i:i + 9]
        schema = schema.lstrip("=")          # ippfind schrijft '=ipp' en '=ipps'
        host_l = host.lower().rstrip(".")
        if schema not in ("ipp", "ipps") or not poort.isdigit() or not dienst.strip() or len(dienst) > 63:
            continue
        eigen = host_l in ("localhost", "127.0.0.1", "::1") or host_l in (eigen_host, eigen_host + ".local")
        if eigen and int(poort) == 631:      # een printer die deze computer zelf deelt
            continue
        sleutel = uuid.strip().lower() or dienst
        if sleutel not in per:
            per[sleutel] = {}
            volgorde.append(sleutel)
        per[sleutel][schema] = [dienst, host, poort, rp, ty, notitie, pdl,
                                "kabel" if eigen and 60000 <= int(poort) <= 65535 else "netwerk"]
    uit: list[Gevonden] = []
    for sleutel in volgorde:
        ingangen = per[sleutel]
        schema = "ipps" if "ipps" in ingangen else "ipp"
        dienst, host, poort, rp, ty, notitie, pdl, soort = ingangen[schema]

        def maak(sch: str) -> tuple[str, str]:
            d, h, p, r = ingangen[sch][:4]
            uri = f"{sch}://{urllib.parse.quote(d, safe='')}._{sch}._tcp.local/"
            proef = f"{sch}://{h.rstrip('.')}:{p}/{r}" if _HOST_RE.match(h) and _PAD_RE.match(r) else ""
            return uri, proef
        uri, proef = maak(schema)
        reserve, reserve_proef = maak("ipp") if schema == "ipps" and "ipp" in ingangen else ("", "")
        naam = schone_tekst(ty) or schone_tekst(re.sub(r"\s*\[[0-9A-Fa-f]{4,}\]$", "", dienst)) or t("Printer", "Printer")
        uit.append(Gevonden(naam, dienst, uri, schone_tekst(notitie), soort,
                            any(x in pdl for x in _DRIVERLESS), False, schone_tekst(ty, 60), reserve, proef,
                            reserve_proef))
    return uit


def lees_lpinfo_usb(uitvoer: str) -> list[Gevonden]:
    """Uit: lpinfo -l --include-schemes usb -v. Blokken 'Device: uri = usb://...' met 'info =' en 'make-and-model ='."""
    uit: list[Gevonden] = []
    huidig: dict[str, str] | None = None

    def klaar() -> None:
        if huidig and URI_RE.match(huidig.get("uri", "")) and huidig["uri"].startswith("usb://"):
            mm = schone_tekst(huidig.get("make-and-model", ""))
            naam = schone_tekst(huidig.get("info", "")) or mm or t("Printer met een kabel", "Printer with a cable")
            uit.append(Gevonden(naam, "", huidig["uri"], "", "usb", False, False, mm if mm.lower() != "unknown" else naam))
    for regel in uitvoer.splitlines():
        m = re.match(r"^Device:\s*uri\s*=\s*(\S+)\s*$", regel)
        if m:
            klaar()
            huidig = {"uri": m.group(1)}
            continue
        m = re.match(r"^\s+([a-z-]+)\s*=\s*(.*)$", regel)
        if m and huidig is not None:
            huidig[m.group(1)] = m.group(2)
    klaar()
    return uit


def lees_lpstat_v(uitvoer: str) -> dict[str, str]:
    """Uit: lpstat -v -> {wachtrij: apparaat-uri}."""
    uit = {}
    for regel in uitvoer.splitlines():
        m = re.match(r"^device for (\S+):\s*(\S+)", regel)
        if m:
            uit[m.group(1)] = m.group(2)
    return uit


def lees_lpstat_e(uitvoer: str) -> set[str]:
    """Uit: lpstat -l -e -> de namen van de echte (blijvende) wachtrijen. 'network' is een printer die CUPS alleen op
    het netwerk ziet, 'temporary' een tijdelijke wachtrij die CUPS zelf maakt om er één keer op te printen: die
    namen zijn niet 'bezet' (review R1)."""
    return {d[0] for d in (r.split() for r in uitvoer.splitlines()) if len(d) >= 2 and d[1] == "permanent"}


def _blijvende_wachtrijen() -> set[str]:
    return lees_lpstat_e(_c.draai("lpstat", "-l", "-e", timeout=8)[1])


def al_toegevoegd(g: Gevonden, apparaten: dict[str, str]) -> bool:
    for uri in apparaten.values():
        los = urllib.parse.unquote(uri)
        if uri == g.uri or (g.reserve_uri and uri == g.reserve_uri):
            return True
        if g.dienst and (g.dienst + "._ipp" in los):    # ook ._ipps
            return True
        if g.soort == "usb" and uri.split("?")[0] == g.uri.split("?")[0]:
            return True
    return False


def _vb_gevonden() -> list[Gevonden]:
    return _c._VB.setdefault("gevonden", [
        Gevonden("HP OfficeJet Pro 8010 series", "HP OfficeJet Pro 8010 [A1B2C3]",
                 "ipps://HP%20OfficeJet%20Pro%208010%20%5BA1B2C3%5D._ipps._tcp.local/", t("Boven", "Upstairs"),
                 "netwerk", True, False, "HP OfficeJet Pro 8010 series",
                 "ipp://HP%20OfficeJet%20Pro%208010%20%5BA1B2C3%5D._ipp._tcp.local/"),
        Gevonden("Canon TS5300 series", "Canon TS5300 series", "ipp://Canon%20TS5300%20series._ipp._tcp.local/", "",
                 "kabel", True, False, "Canon TS5300 series"),
        # Een oude laserprinter met alleen een kabel: werkt met brlaser (de HP LaserJet 1020 uit de spec kan nooit:
        # die heeft de 'proprietary plugin' van HP nodig, review R2).
        Gevonden("Brother HL-L2300D series", "", "usb://Brother/HL-L2300D%20series?serial=E00000A0", "", "usb", False,
                 False, "Brother HL-L2300D series"),
    ])


def gevonden_printers(met_kabel: bool | None = None) -> list[Gevonden]:
    """Printers die BugOS kan toevoegen: op je netwerk, met een kabel (ipp-usb), en voor een beheerder ook oude
    printers met een kabel (lpinfo mag alleen een beheerder). met_kabel=True: ook zonder beheerder, met het
    wachtwoord van een beheerder (één keer pkexec lpinfo, review R7)."""
    if _c.VOORBEELD:
        lijst = [Gevonden(**vars(g)) for g in _vb_gevonden()]
        namen = {p.naam for p in printers()}
        for g in lijst:
            g.al_toegevoegd = wachtrij_naam(g.dienst or g.naam, set()) in namen
    else:
        cmd = ["ippfind", "-T", "5", "_ipp._tcp", "_ipps._tcp", "--exec", "/usr/bin/printf",
               "%s\\0" * len(_IPPFIND_VELDEN), *_IPPFIND_VELDEN, ";"]
        lijst = lees_ippfind(_c.cups_draai(*cmd, timeout=15, fout=False)[1], _eigen_host())
        if met_kabel or (met_kabel is None and _c.ben_beheerder()):
            if _c.ben_beheerder():
                uit = _c.cups_draai("lpinfo", "-l", "--include-schemes", "usb", "-v", timeout=25, fout=False)[1]
            else:
                soort, uit = _c.als_beheerder("lpinfo", "-l", "--include-schemes", "usb", "-v", timeout=25)
                if soort != "ok":
                    uit = ""
            lijst += lees_lpinfo_usb(uit)
        apparaten = lees_lpstat_v(_c.draai("lpstat", "-v", timeout=8)[1])
        blijvend = _blijvende_wachtrijen()
        apparaten = {q: u for q, u in apparaten.items() if q in blijvend or not blijvend}
        for g in lijst:
            g.al_toegevoegd = al_toegevoegd(g, apparaten)
    return sorted(lijst, key=lambda g: (g.al_toegevoegd, not g.driverless, g.naam.lower()))


def wachtrij_naam(tekst: str, bezet: set[str]) -> str:
    """De naam van de wachtrij, precies zoals CUPS hem zelf maakt van de DNS-SD-naam (cups_queue_name in dest.c:
    alleen letters en cijfers, de rest één '_', geen '_' aan het eind). Dan staat de printer in een printvenster maar
    één keer, en niet ook nog eens als tijdelijke printer van CUPS (review R1). Bezet: _2, _3 ..."""
    naam = ""
    for c in tekst:
        if c.isascii() and c.isalnum():
            naam += c
        elif not naam or naam[-1] != "_":
            naam += "_"
    if len(naam) > 1 and naam.endswith("_"):
        naam = naam[:-1]
    naam = naam[:100]
    if not naam.strip("_"):
        naam = "Printer"
    if not NAAM_RE.match(naam):
        naam = "Printer_" + naam
    laag = {b.lower() for b in bezet}
    basis, n = naam, 2
    while naam.lower() in laag:
        naam, n = f"{basis}_{n}", n + 1
    return naam


def antwoordt(uri: str) -> str:
    """Kijk zonder wachtwoord of de printer op dit adres antwoordt (ipptool, als jezelf). 'ok', 'onbereikbaar' of
    'anders' (hij antwoordt, maar niet als een gewone printer)."""
    code, uit = _c.cups_draai("ipptool", "-T", "10", uri, IPPTOOL_TEST, timeout=20)
    if code == 0:
        return "ok"
    soort = cups_fout(code, uit)
    return "onbereikbaar" if soort in ("onbereikbaar", "bestaat_niet") or code == 127 else "anders"


def _voeg_toe(basis: str, paren: list[tuple[str, str]], model: str, omschrijving: str, locatie: str) -> tuple[str, str]:
    """Voeg een wachtrij toe. paren: [(uri, proef-uri)], de beste eerst. Een beheerder probeert ze om de beurt
    (zonder wachtwoord). Wie geen beheerder is, krijgt maar één wachtwoordvenster: eerst zonder wachtwoord kijken
    welk adres antwoordt (ipptool), dan één keer pkexec lpadmin (review R3)."""
    paren = [(u, p) for u, p in paren if URI_RE.match(u)]
    omschrijving = schone_tekst(omschrijving) or t("Printer", "Printer")
    locatie = schone_tekst(locatie)
    if not paren or (model != "everywhere" and model not in _MODELLEN):
        return "anders", ""
    naam = wachtrij_naam(basis, _blijvende_wachtrijen())
    if not _c.ben_beheerder():
        proeven = [(u, p) for u, p in paren if p]
        if proeven:
            gekozen, laatste = None, "onbereikbaar"
            for uri, proef in proeven:
                laatste = _c.antwoordt(proef)
                if laatste == "ok":
                    gekozen = uri
                    break
                if laatste == "onbereikbaar" and len(proeven) > 1 and adres_host(proef) == adres_host(proeven[-1][1]):
                    break   # hetzelfde adres: een tweede poging duurt weer een halve minuut
            if gekozen is None:
                return laatste, ""
            paren = [(gekozen, "")]
        else:
            paren = paren[:1]
    soort = "anders"
    for i, (uri, _proef) in enumerate(paren):
        soort, uit = _c.als_beheerder("lpadmin", "-p", naam, "-E", "-v", uri, "-m", model, "-D", omschrijving,
                                      *(("-L", locatie) if locatie else ()), timeout=45)
        if soort == "onbereikbaar" and not uit and naam in _blijvende_wachtrijen():
            soort = "ok"   # de tijd was om, maar lpadmin (als root) maakte hem toch (review R12)
        if soort not in ("onbereikbaar", "anders"):
            break
        volgende = paren[i + 1][0] if i + 1 < len(paren) else ""
        if soort == "onbereikbaar" and volgende and adres_host(volgende) == adres_host(uri):
            break   # hetzelfde adres (ipp en ipps op 192.168.1.20): niet nog een halve minuut wachten
    if soort != "ok":
        return soort, ""
    if "no system default" in _c.draai("lpstat", "-d", timeout=8)[1]:
        # De eerste printer wordt de standaard: voor iedereen als een beheerder hem toevoegt (review R20).
        if not _c.ben_beheerder() or _c.als_beheerder("lpadmin", "-d", naam, timeout=15)[0] != "ok":
            zet_standaard_printer(naam)
    return "ok", naam


def _vb_voeg_toe(basis: str, omschrijving: str, locatie: str) -> tuple[str, str]:
    naam = wachtrij_naam(basis, {p.naam for p in printers()})
    printers().append(Printer(naam, schone_tekst(omschrijving), "klaar", not printers(), locatie=schone_tekst(locatie)))
    return "ok", naam


def printer_toevoegen(g: Gevonden) -> tuple[str, str]:
    """Een gevonden printer toevoegen, zonder eigen software (IPP Everywhere). ('ok', wachtrij) of (foutsoort, '');
    'geen_driverless': hij heeft software van de maker nodig (dan kies je merk en model)."""
    if _c.VOORBEELD:
        return _vb_voeg_toe(g.dienst or g.naam, g.naam, g.locatie)
    paren = [(g.uri, g.proef_uri)] + ([(g.reserve_uri, g.reserve_proef)] if g.reserve_uri else [])
    return _voeg_toe(g.dienst or g.naam, paren, "everywhere", g.naam, g.locatie)


def adres_kandidaten(tekst: str) -> list[str]:
    """Wat je typt (192.168.1.20, printer.local, [fe80::1] of een hele ipp://-link) -> de adressen om te proberen."""
    tekst = tekst.strip()
    if re.match(r"^(ipps?)://[A-Za-z0-9.\-\[\]:]+(:\d{1,5})?(/[A-Za-z0-9._~/%-]*)?$", tekst):
        return [tekst]
    delen = tekst.split(".")
    ipv4 = len(delen) == 4 and all(d.isdigit() and len(d) <= 3 and int(d) <= 255 for d in delen)
    ipv6 = bool(re.match(r"^\[[0-9A-Fa-f:]{2,39}\]$", tekst)) and tekst.count(":") >= 2
    naam = bool(_HOST_RE.match(tekst)) and not tekst.endswith(".") and not all(d.isdigit() for d in delen)
    if ipv4 or ipv6 or naam:
        return [f"ipp://{tekst}/ipp/print", f"ipps://{tekst}/ipp/print"]
    return []


def adres_host(uri: str) -> str:
    """Het stuk tussen // en het pad: '192.168.1.20', '[fe80::1]' of 'printer.local:631'."""
    return uri.split("://", 1)[-1].split("/", 1)[0]


def adres_vervolg(tekst: str) -> tuple[str, str, str]:
    """Voor een getypt adres: (basis van de wachtrij-naam, ipp://host/ipp/print, socket://host:9100). De laatste twee
    zijn voor software van de maker: een IPP-printer zonder IPP Everywhere, of een die alleen poort 9100 kent."""
    kandidaten = adres_kandidaten(tekst)
    host = adres_host(kandidaten[0]) if kandidaten else ""
    kaal = host[:host.index("]") + 1] if host.startswith("[") and "]" in host else host.split(":")[0]
    return wachtrij_naam("Printer_" + kaal.strip("[]"), set()), f"ipp://{host}/ipp/print", f"socket://{kaal}:9100"


def printer_toevoegen_adres(tekst: str) -> tuple[str, str]:
    """Een printer op een adres dat je typt. ('ok', wachtrij), of een foutsoort ('geen_driverless': kies merk en model;
    'geen_antwoord': hij antwoordt niet als een gewone printer, probeer het met software van de maker)."""
    kandidaten = adres_kandidaten(tekst)
    if not kandidaten:
        return "geen_adres", ""
    basis = adres_vervolg(tekst)[0]
    if _c.VOORBEELD:
        return _vb_voeg_toe(basis, tekst.strip(), "")
    soort, naam = _voeg_toe(basis, [(u, u) for u in kandidaten], "everywhere", tekst.strip(), "")
    return ("geen_antwoord" if soort == "anders" else soort), naam


# Printersoftware van de maker (hplip, gutenprint, brlaser, splix): alleen voor printers die niet zonder kunnen.
_MODELLEN: dict[str, str] = {}   # wat lpinfo -m deze keer gaf: alleen die mag lpadmin -m krijgen (geen eigen bestanden)
_GEEN_MODEL = ("everywhere", "raw")


def _model_sleutel(tekst: str) -> str:
    """'HP LaserJet 1020, hpcups 3.26.6' en 'HP LaserJet 1020 hpijs, 3.26.6' -> 'hp laserjet 1020'."""
    kort = re.split(r",| - |\s+using\s+", tekst, maxsplit=1)[0]
    kort = re.sub(r"\s+(hpijs|pcl3|Foomatic.*|CUPS\+Gutenprint.*)$", "", kort, flags=re.I)
    return " ".join(kort.lower().split())


def _model_voorkeur(uri: str, tekst: str) -> int:
    if uri.startswith("drv:///hp/hpcups") or "simplified" in tekst.lower():
        return 0
    if "hpijs" in uri or "hpijs" in tekst.lower():
        return 2
    if uri.startswith("lsb/"):
        return 3
    return 1


def lees_lpinfo_m(uitvoer: str) -> list[tuple[str, str]]:
    """Uit: lpinfo -m -> [(model-uri, merk en model)], elk model één keer, met de beste software. Weg: wat zonder
    software werkt (everywhere, driverless), en wat 'requires proprietary plugin' zegt: dat kan BugOS niet
    installeren, die printer zou nooit printen (review R2)."""
    beste: dict[str, tuple[int, str, str]] = {}
    for regel in uitvoer.splitlines():
        uri, _, tekst = regel.strip().partition(" ")
        tekst = schone_tekst(tekst, 200)
        if not uri or not tekst or uri in _GEEN_MODEL or uri.startswith("driverless:") or "pwgrast.ppd" in uri:
            continue
        if "requires proprietary plugin" in tekst.lower() or not re.match(r"^[A-Za-z0-9:/._+%=-]+$", uri):
            continue
        sleutel = _model_sleutel(tekst)
        kandidaat = (_model_voorkeur(uri, tekst), uri, re.split(r",| - |\s+using\s+", tekst, maxsplit=1)[0].strip())
        if sleutel and (sleutel not in beste or kandidaat < beste[sleutel]):
            beste[sleutel] = kandidaat
    return sorted(((uri, naam) for _v, uri, naam in beste.values()), key=lambda x: x[1].lower())


def model_woorden(hint: str) -> list[str]:
    """'HP OfficeJet Pro 8010 series' -> ['HP', 'OfficeJet', 'Pro', '8010'] (CUPS zet 'series' er zelden bij)."""
    return [w for w in schone_tekst(hint, 80).split() if w.lower() != "series"][:4]


def _regex_letterlijk(tekst: str) -> str:
    """cups-driverd leest --make-and-model als een reguliere expressie: tekens als + en ( letterlijk maken."""
    return "".join("\\" + c if c in ".[]()*+?{}|^$\\" else c for c in tekst)


def modellen(hint: str = "") -> list[tuple[str, str]] | None:
    """De printersoftware in BugOS voor dit merk en model (hint, een paar tellen), of voor alles (hint '', soms een
    minuut: 10 000 regels). None als CUPS de lijst niet gaf."""
    woorden = model_woorden(hint)
    if _c.VOORBEELD:
        hint = " ".join(woorden)
        lijst = _c._VB.setdefault("modellen", [
            ("drv:///hp/hpcups.drv/hp-laserjet_p1505.ppd", "HP LaserJet P1505"),
            ("drv:///hp/hpcups.drv/hp-deskjet_2130_series.ppd", "HP DeskJet 2130 Series"),
            ("drv:///brlaser.drv/br2300d.ppd", "Brother HL-L2300D series"),
            ("gutenprint.5.3://escp2-r220/expert", "Epson Stylus Photo R220"),
            ("drv:///splix-samsung.drv/ml1640.ppd", "Samsung ML-1640"),
            ("gutenprint.5.3://bjc-PIXMA-iP4000/expert", "Canon PIXMA iP4000")])
        lijst = [m for m in lijst if not hint or all(w.lower() in m[1].lower() for w in hint.split())]
        lijst = [m for m in lijst if not hint or any(all(w.lower() in m[1].lower() for w in p)
                                                    for p in (woorden, woorden[:2]))]
    elif woorden:
        lijst = []
        for proef in ([woorden, woorden[:2]] if len(woorden) > 2 else [woorden]):
            code, uit = _c.cups_draai("lpinfo", "--make-and-model", _regex_letterlijk(" ".join(proef)), "-m",
                                      timeout=40, fout=False)
            if code not in (0, 1) and not uit.strip():
                return None
            lijst = [m for m in lees_lpinfo_m(uit) if all(w.lower() in m[1].lower() for w in proef)]
            if lijst:
                break
    else:
        code, uit = _c.cups_draai("lpinfo", "-m", timeout=120, fout=False)
        if code != 0 and not uit.strip():
            return None
        lijst = lees_lpinfo_m(uit)
    _MODELLEN.update(lijst)
    return lijst


def printer_toevoegen_model(uri: str, basis: str, omschrijving: str, model: str) -> tuple[str, str]:
    """Een printer met software van de maker: model moet uit modellen() komen (nooit een eigen bestand)."""
    if model not in _MODELLEN or not URI_RE.match(uri):
        return "anders", ""
    if _c.VOORBEELD:
        return _vb_voeg_toe(basis, omschrijving, "")
    return _voeg_toe(basis, [(uri, "")], model, omschrijving, "")


def scanprogramma() -> str | None:
    if _c.VOORBEELD:
        return "skanpage"
    gevonden = next((p for p in ("skanpage", "skanlite", "simple-scan") if shutil.which(p)), None)
    if gevonden:
        return gevonden
    # Uit de BugOS Winkel komt hij als Flatpak: dan heet hij niet 'skanpage' op het pad (U159).
    for app_id in ("org.kde.skanpage", "org.kde.skanlite", "org.gnome.SimpleScan"):
        if shutil.which("flatpak") and _c.draai("flatpak", "info", app_id, timeout=10)[0] == 0:
            return f"flatpak:{app_id}"
    return None
