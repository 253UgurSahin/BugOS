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
            "tekst": ("org.kde.kate.desktop", [("org.kde.kate.desktop", t("Kate (tekst)", "Kate (text)")),
                                               ("org.kde.kwrite.desktop", "KWrite")])}


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
