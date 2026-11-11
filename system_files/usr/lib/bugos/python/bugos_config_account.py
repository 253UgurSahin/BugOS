"""BugOS Instellingen: tijd en taal (timedatectl, plasma-localerc) en inloggen en wachtwoord
(AccountsService, bugos-login, kscreenlockerrc); ook de klok met de hand (timedatectl set-time),
andere mensen op deze computer (lezen uit pwd/grp, veranderen via AccountsService), je eigen foto
(AccountsService), de toetsenborden (kxkbrc, localectl) en de notatie van datum en tijd (plasma-localerc).

Hoort bij bugos_config (importeer het via daar). draai, VOORBEELD, _VB en de KDE-hulpjes komen via
bugos_config (_c.draai), zodat een test die bi.draai of bi.VOORBEELD vervangt dat ook hier ziet.
"""

from __future__ import annotations

import os
import re
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import bugos_config as _c
from bugos_base import t

# Wat de voorbeeldstand (BUGOS_INSTELLINGEN_VOORBEELD=1) voor dit onderdeel onthoudt. Hier en niet in _c._VB:
# dat staat in het gedeelde bugos_config.py.
_VB_ACCOUNT: dict = {"klok_gezet": None, "mensen": None, "foto": "", "regio": "nl_NL"}


# ============================================================ tijd en taal ===

@dataclass
class Tijd:
    zone: str           # bv. Europe/Amsterdam
    auto: bool          # klok vanzelf gelijkzetten via internet
    gelijk: bool        # en dat is ook gelukt


def lees_timedatectl(uitvoer: str) -> Tijd:
    """Uit: timedatectl show."""
    d = dict(r.split("=", 1) for r in uitvoer.splitlines() if "=" in r)
    return Tijd(d.get("Timezone", "") or "UTC", d.get("NTP", "no") == "yes", d.get("NTPSynchronized", "no") == "yes")


def tijd() -> Tijd:
    if _c.VOORBEELD:
        return Tijd(_c._VB["zone"], _c._VB["tijd_auto"], _c._VB["tijd_auto"])
    return lees_timedatectl(_c.draai("timedatectl", "show", timeout=5)[1])


WERELDDEEL = {"Europe": ("Europa", "Europe"), "America": ("Amerika", "America"), "Asia": ("Azië", "Asia"),
              "Africa": ("Afrika", "Africa"), "Australia": ("Australië", "Australia"),
              "Pacific": ("Stille Oceaan", "Pacific"), "Atlantic": ("Atlantische Oceaan", "Atlantic"),
              "Indian": ("Indische Oceaan", "Indian Ocean"), "Antarctica": ("Antarctica", "Antarctica"),
              "Arctic": ("Noordpool", "Arctic")}


def mooie_zone(zone: str, nl: bool = True) -> str:
    """'Europe/Amsterdam' -> 'Amsterdam (Europa)'."""
    if "/" not in zone:
        return zone
    deel, stad = zone.split("/", 1)
    stad = stad.replace("_", " ").replace("/", " / ")
    naam = WERELDDEEL.get(deel)
    return f"{stad} ({naam[0] if nl else naam[1]})" if naam else f"{stad} ({deel})"


def tijdzones() -> list[str]:
    if _c.VOORBEELD:
        return ["Europe/Amsterdam", "Europe/Brussels", "Europe/Berlin", "Europe/London", "Europe/Istanbul",
                "America/New_York", "America/Curacao", "Asia/Tokyo", "Australia/Sydney"]
    zones = [z.strip() for z in _c.draai("timedatectl", "list-timezones", timeout=5)[1].splitlines()]
    return [z for z in zones if "/" in z and not z.startswith("Etc/")]


def zet_tijdzone(zone: str) -> bool:
    """Via timedatectl; KDE vraagt het wachtwoord, net als Windows."""
    if _c.VOORBEELD:
        _c._VB["zone"] = zone
        return True
    return _c.draai("timedatectl", "set-timezone", zone, timeout=60)[0] == 0


def zet_tijd_auto(aan: bool) -> bool:
    if _c.VOORBEELD:
        _c._VB["tijd_auto"] = aan
        return True
    return _c.draai("timedatectl", "set-ntp", "true" if aan else "false", timeout=60)[0] == 0


def zet_klok(wanneer: datetime) -> tuple[bool, str]:
    """De klok met de hand zetten (plaatselijke tijd, zoals je hem typte). timedated zet ook de klok in de computer
    (RTC). KDE vraagt het wachtwoord van een beheerder, net als bij de tijdzone. Geeft (gelukt, reden): reden 'auto'
    als de tijd nog vanzelf via internet gaat (dan weigert timedated), anders 'fout'."""
    if _c.VOORBEELD:
        _VB_ACCOUNT["klok_gezet"] = wanneer
        return True, ""
    if tijd().auto:
        return False, "auto"
    begin, t0 = datetime.now(), time.monotonic()
    if _c.draai("timedatectl", "set-time", wanneer.strftime("%Y-%m-%d %H:%M:%S"), timeout=120)[0] == 0:
        return True, ""
    # timedatectl geeft het na 25 s op, ook als je dan nog in het wachtwoordvenster zit; de klok gaat daarna toch
    # gewoon. Dus nog even kijken: loopt de klok nu zoals gevraagd (2 minuten speling)? Alleen als je hem echt
    # verzette, anders zegt dit niets.
    if abs((wanneer - begin).total_seconds()) > 120:
        verwacht = wanneer + timedelta(seconds=time.monotonic() - t0)
        if abs((datetime.now() - verwacht).total_seconds()) <= 120:
            return True, ""
    return False, "fout"


# (code, landcode voor de klok en getallen, naam in die taal zelf)
TALEN = [("en", "en_US", "English"), ("nl", "nl_NL", "Nederlands"), ("de", "de_DE", "Deutsch"),
         ("fr", "fr_FR", "Français"), ("es", "es_ES", "Español"), ("it", "it_IT", "Italiano"),
         ("pt", "pt_PT", "Português"), ("pl", "pl_PL", "Polski"), ("tr", "tr_TR", "Türkçe"),
         ("uk", "uk_UA", "Українська"), ("ar", "ar_EG", "العربية")]


def taal() -> str:
    if _c.VOORBEELD:
        return _c._VB["taal"]
    tekst = _c.kde_lees("plasma-localerc", "Translations", "LANGUAGE", "")
    if not tekst:
        tekst = _c.kde_lees("plasma-localerc", "Formats", "LANG", "") or os.environ.get("LANG", "")
    code = tekst.split(":")[0].split(".")[0].split("_")[0].lower()
    return code if any(code == c for c, _l, _n in TALEN) else "en"


# Landen met de euro: daar past Iers-Engels (dag/maand, A4, de euro) (U229).
EURO_LANDEN = {"NL", "BE", "DE", "AT", "FR", "LU", "ES", "PT", "IT", "IE", "FI", "GR", "SK", "SI", "EE", "LV", "LT",
               "HR", "MT", "CY"}
LC_STREEK = ("LC_PAPER", "LC_MEASUREMENT", "LC_MONETARY")
HOUDEN = ""   # formaten_voor: de LC_-instellingen laten zoals ze zijn


def formaten_voor(code: str, land: str) -> tuple[str, str | None]:
    """(LANG, streek voor papier/maten/geld) bij de gekozen taal. Engels buiten Engeland of Amerika is geen
    Amerikaans: in een euroland Iers-Engels (dag/maand, A4, de euro); elders (Polen, Turkije…) Engels met het
    datum op z'n Europees en het papier, de maten en het geld van je eigen land (U229, U232, U242).
    streek None haalt die weg, HOUDEN laat ze."""
    if code != "en":
        return land, None
    nu = (_c.kde_lees("plasma-localerc", "Formats", "LANG", "") or os.environ.get("LANG", "")).split(".")[0]
    if nu.startswith("en_"):
        return nu, HOUDEN   # al een Engelse streek (Brits, Iers, Amerikaans…): die houden
    if "_" not in nu or nu.startswith(("C", "POSIX")):
        return land, None
    land_code = nu.split("_")[1][:2]
    if land_code in ("US", "CA"):
        return f"en_{land_code}", None   # in Amerika of Canada: het Engels van daar (U257)
    if land_code in EURO_LANDEN:
        return "en_IE", None
    return "en_IE", nu   # dag/maand en 24 uur, zoals bijna overal buiten Amerika (U242)


def zet_taal(code: str) -> bool:
    """De taal van KDE en de BugOS-programma's; geldt na opnieuw inloggen (zo doet KDE dat ook)."""
    if _c.VOORBEELD:
        _c._VB["taal"] = code
        return True
    land = next((land for c, land, _n in TALEN if c == code), None)
    if land is None:
        return False
    goed = _c.kde_schrijf("plasma-localerc", "Translations", "LANGUAGE", code if code == "en" else f"{code}:en_US")
    lang, streek = formaten_voor(code, land)
    goed = _c.kde_schrijf("plasma-localerc", "Formats", "LANG", f"{lang}.UTF-8") and goed
    if streek != HOUDEN:
        for sleutel in LC_STREEK:
            goed = _c.kde_schrijf("plasma-localerc", "Formats", sleutel, f"{streek}.UTF-8" if streek else None) and goed
        # Een andere taal: ook de notatie van datum en tijd weer die van de taal (kies je daarna opnieuw).
        for sleutel in LC_REGIO + ("LC_NUMERIC",):
            goed = _c.kde_schrijf("plasma-localerc", "Formats", sleutel, None) and goed
    return goed


# De notatie van datum en tijd: 14:58 of 2:58 PM, 11-11-2026 of 11/11/2026, de week begint op maandag of zondag.
# (code, nl, en). Alle zijn er als glibc-locale in BugOS (glibc-all-langpacks).
REGIOS = [("nl_NL", "Nederland", "Netherlands"), ("nl_BE", "België (Nederlands)", "Belgium (Dutch)"),
          ("fr_BE", "België (Frans)", "Belgium (French)"), ("en_US", "Verenigde Staten", "United States"),
          ("en_GB", "Verenigd Koninkrijk", "United Kingdom"), ("en_IE", "Ierland", "Ireland"),
          ("en_CA", "Canada", "Canada"), ("en_AU", "Australië", "Australia"), ("en_ZA", "Zuid-Afrika", "South Africa"),
          ("en_IN", "India", "India"), ("de_DE", "Duitsland", "Germany"), ("de_AT", "Oostenrijk", "Austria"),
          ("de_CH", "Zwitserland", "Switzerland"), ("fr_FR", "Frankrijk", "France"), ("es_ES", "Spanje", "Spain"),
          ("it_IT", "Italië", "Italy"), ("pt_PT", "Portugal", "Portugal"), ("pt_BR", "Brazilië", "Brazil"),
          ("pl_PL", "Polen", "Poland"), ("tr_TR", "Turkije", "Türkiye"), ("uk_UA", "Oekraïne", "Ukraine"),
          ("ar_MA", "Marokko", "Morocco"), ("ar_EG", "Egypte", "Egypt"), ("nl_AW", "Aruba", "Aruba")]
# Alleen LC_TIME: de keuze gaat over de datum en de tijd. Getallen, papier, maten en geld blijven van je taal
# (U229/U242): wie een 12-uursklok wil, krijgt er geen Letter-papier en dollars bij (review I2).
LC_REGIO = ("LC_TIME",)


def _locale_code(tekst: str) -> str:
    """'nl_NL.UTF-8' of 'en_US.utf8@euro' -> 'nl_NL'; C en POSIX tellen niet."""
    code = tekst.split(":")[0].split(".")[0].split("@")[0].strip()
    return "" if code in ("C", "POSIX") else code


def regio() -> str:
    """Hoe je de datum en de tijd schrijft (de LC_TIME van je sessie), bv. 'nl_NL'. Niets gezet: Amerikaans."""
    if _c.VOORBEELD:
        return _VB_ACCOUNT["regio"]
    for tekst in (_c.kde_lees("plasma-localerc", "Formats", "LC_TIME", ""),
                  _c.kde_lees("plasma-localerc", "Formats", "LANG", ""),
                  os.environ.get("LC_TIME", ""), os.environ.get("LANG", "")):
        code = _locale_code(tekst)
        if code:
            return code
    return "en_US"


def zet_regio(code: str) -> bool:
    """De notatie van datum en tijd; geldt na opnieuw inloggen (plasma-localerc wordt dan doorgegeven)."""
    if code not in {c for c, _nl, _en in REGIOS}:
        return False
    if _c.VOORBEELD:
        _VB_ACCOUNT["regio"] = code
        return True
    goed = True
    for sleutel in LC_REGIO:
        goed = _c.kde_schrijf("plasma-localerc", "Formats", sleutel, f"{code}.UTF-8") and goed
    return goed


def afmelden() -> None:
    """Vraag netjes of je wilt afmelden (het scherm van KDE)."""
    if _c.VOORBEELD:
        return
    _c.draai("gdbus", "call", "--session", "--dest", "org.kde.LogoutPrompt", "--object-path", "/LogoutPrompt",
          "--method", "org.kde.LogoutPrompt.promptLogout", timeout=5)


# ================================================== inloggen en wachtwoord ===

@dataclass
class Gebruiker:
    naam: str               # inlognaam, bv. bugie
    volledige_naam: str     # bv. Bugie
    beheerder: bool
    auto_inloggen: bool
    foto: str = ""          # pad van je foto (AccountsService), of ""


# Fedora 44 heeft Plasma Login (plasmalogin); SDDM alleen als Plasma Login er niet is (net als bugos-login).
PLASMALOGIN = "/usr/lib/plasmalogin"
PLASMALOGIN_BESTANDEN = ("/etc/plasmalogin.conf", "/etc/plasmalogin.conf.d")
SDDM_BESTANDEN = ("/etc/sddm.conf", "/etc/sddm.conf.d")


def inlog_bestanden() -> tuple[str, ...]:
    """De instellingen van het inlogscherm dat echt gebruikt wordt."""
    return PLASMALOGIN_BESTANDEN if Path(PLASMALOGIN).is_dir() else SDDM_BESTANDEN


def lees_autologin(teksten: list[str], naam: str) -> bool:
    """Staat in een bestand van het inlogscherm [Autologin] User=<naam>?"""
    for tekst in teksten:
        groep = ""
        for regel in tekst.splitlines():
            regel = regel.strip()
            if regel.startswith("[") and regel.endswith("]"):
                groep = regel[1:-1]
            elif groep == "Autologin" and "=" in regel:
                sleutel, waarde = (x.strip() for x in regel.split("=", 1))
                if sleutel == "User" and waarde == naam:
                    return True
    return False


def _inlog_teksten() -> list[str]:
    """De instellingen van het inlogscherm (voor 'inloggen zonder wachtwoord')."""
    teksten = []
    for pad in inlog_bestanden():
        p = Path(pad)
        bestanden = sorted(p.glob("*.conf")) if p.is_dir() else [p]
        for b in bestanden:
            try:
                teksten.append(b.read_text(encoding="utf-8"))
            except OSError:
                pass
    return teksten


def fotomap() -> Path:
    """Waar AccountsService de foto's van de mensen bewaart (het startmenu en het inlogscherm lezen ze daar)."""
    return Path(os.environ.get("BUGOS_ACCOUNTS_ICONEN", "/var/lib/AccountsService/icons"))


def _foto_van(naam: str) -> str:
    pad = fotomap() / naam
    return str(pad) if pad.is_file() else ""


def gebruiker() -> Gebruiker:
    if _c.VOORBEELD:
        return Gebruiker("bugie", _c._VB["volledige_naam"], True, _c._VB["auto_inloggen"], _VB_ACCOUNT["foto"])
    import grp
    import pwd
    try:
        pw = pwd.getpwuid(os.getuid())
        naam, vol = pw.pw_name, pw.pw_gecos.split(",")[0].strip()
    except KeyError:
        naam, vol = os.environ.get("USER", "?"), ""
    try:
        beheerder = naam in grp.getgrnam("wheel").gr_mem
    except KeyError:
        beheerder = False
    return Gebruiker(naam, vol or naam.capitalize(), beheerder, lees_autologin(_inlog_teksten(), naam),
                     _foto_van(naam))


def _accounts(methode: str, *args: str, timeout: int = 60) -> tuple[int, str]:
    return _c.draai("gdbus", "call", "--system", "--interactive", "--dest", "org.freedesktop.Accounts", "--object-path",
                 f"/org/freedesktop/Accounts/User{os.getuid()}", "--method",
                 f"org.freedesktop.Accounts.User.{methode}", *args, timeout=timeout)


def zet_volledige_naam(naam: str) -> bool:
    if _c.VOORBEELD:
        _c._VB["volledige_naam"] = naam
        return True
    return _accounts("SetRealName", naam)[0] == 0


def versleutel(wachtwoord: str) -> str:
    """Zoals /etc/shadow het bewaart (SHA-512 met zout), via de libcrypt van het systeem."""
    import ctypes
    import secrets
    tekens = "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
    zout = "$6$" + "".join(secrets.choice(tekens) for _ in range(16))
    # Fedora heeft alleen libcrypt.so.2 (libxcrypt); .so.1 is de oude naam (o.a. Ubuntu).
    lib = None
    for naam in ("libcrypt.so.2", "libcrypt.so.1"):
        try:
            lib = ctypes.CDLL(naam)
            break
        except OSError:
            continue
    if lib is None:
        raise OSError("libcrypt niet gevonden")
    lib.crypt.restype = ctypes.c_char_p
    lib.crypt.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    uit = lib.crypt(wachtwoord.encode("utf-8"), zout.encode("ascii"))
    return uit.decode("ascii") if uit else ""


def zet_wachtwoord(nieuw: str) -> tuple[bool, str]:
    """Nieuw wachtwoord via AccountsService; KDE vraagt eerst je huidige wachtwoord."""
    if _c.VOORBEELD:
        return True, ""
    try:
        hash_ = versleutel(nieuw)
    except OSError:
        hash_ = ""
    if not hash_:
        return False, "crypt"
    # Niet via gdbus: dan staat de hash op de opdrachtregel en kan elke gebruiker hem in 'ps' lezen.
    return _c._accounts_dbus("SetPassword", hash_, "")


def zet_eigen_wachtwoord(huidig: str, nieuw: str, timeout: int = 60) -> tuple[bool, str]:
    """Voor wie geen beheerder is: AccountsService wil dan het wachtwoord van een beheerder. Daarom 'passwd',
    precies zoals in een terminal: het vraagt je huidige wachtwoord en twee keer het nieuwe (via PAM).
    passwd leest van een terminal, dus geven we het een eigen nep-terminal (pty) en typen we de antwoorden
    als het erom vraagt. Niets op de opdrachtregel. Geeft (gelukt, reden): reden 'simpel' als het nieuwe
    wachtwoord te makkelijk is, anders 'fout'."""
    if _c.VOORBEELD:
        return True, ""
    import select
    import subprocess
    import termios
    import time
    if not shutil.which("passwd"):
        return False, "fout"
    baas, slaaf = os.openpty()
    stand = termios.tcgetattr(slaaf)
    stand[3] &= ~termios.ECHO    # wat wij typen, komt niet terug op het scherm
    termios.tcsetattr(slaaf, termios.TCSANOW, stand)
    try:
        proces = subprocess.Popen(["passwd"], stdin=slaaf, stdout=slaaf, stderr=slaaf, start_new_session=True,
                                  env=_c.omgeving("passwd"), close_fds=True)
    except OSError:
        os.close(baas)
        os.close(slaaf)
        return False, "fout"
    os.close(slaaf)
    antwoorden = [huidig, nieuw, nieuw]
    alles = nu = ""
    einde = time.monotonic() + timeout
    try:
        while time.monotonic() < einde:
            klaar, _, _ = select.select([baas], [], [], 0.5)
            if not klaar:
                if proces.poll() is not None:
                    break
                continue
            try:
                stuk = os.read(baas, 1024).decode(errors="ignore")
            except OSError:      # passwd is klaar (de nep-terminal is dicht)
                break
            if not stuk:
                break
            alles += stuk
            nu += stuk
            if "BAD PASSWORD" in alles:
                break            # te makkelijk: passwd zou het opnieuw vragen, maar wij stoppen
            if nu.rstrip().lower().endswith("password:"):
                if not antwoorden:
                    break        # vraagt het nog eens: dan klopte er iets niet
                time.sleep(0.05)
                os.write(baas, (antwoorden.pop(0) + "\n").encode())
                nu = ""
    finally:
        if proces.poll() is None:
            proces.kill()
        code = proces.wait()
        os.close(baas)
    if code == 0 and not antwoorden:
        return True, ""
    return False, "simpel" if "BAD PASSWORD" in alles else "fout"


def _accounts_dbus(methode: str, *args: str, timeout: int = 60) -> tuple[bool, str]:
    """AccountsService rechtstreeks over D-Bus (in dit proces), met de wachtwoordvraag van KDE erbij."""
    try:
        from PySide6.QtDBus import QDBus, QDBusConnection, QDBusMessage
    except ImportError:
        return False, "dbus"
    bericht = QDBusMessage.createMethodCall("org.freedesktop.Accounts", f"/org/freedesktop/Accounts/User{os.getuid()}",
                                            "org.freedesktop.Accounts.User", methode)
    bericht.setArguments(list(args))
    bericht.setInteractiveAuthorizationAllowed(True)
    antwoord = QDBusConnection.systemBus().call(bericht, QDBus.CallMode.Block, timeout * 1000)
    if antwoord.type() == QDBusMessage.MessageType.ErrorMessage:
        return False, antwoord.errorMessage()
    return True, ""


def zet_auto_inloggen(aan: bool, naam: str) -> bool:
    """Inloggen zonder wachtwoord: een klein hulpje als beheerder (pkexec vraagt het wachtwoord één keer)."""
    if _c.VOORBEELD:
        _c._VB["auto_inloggen"] = aan
        return True
    return _c.draai("pkexec", "/usr/bin/bugos-login", "aan" if aan else "uit", naam, timeout=120)[0] == 0


SLOT_KEUZES = (5, 15, 30, 0)   # minuten; 0 = nooit


def slot_na() -> int:
    """Na hoeveel minuten niets doen gaat het scherm op slot (0 = nooit)."""
    if _c.VOORBEELD:
        return _c._VB["slot_na"]
    if _c.kde_lees("kscreenlockerrc", "Daemon", "Autolock", "true") != "true":
        return 0
    try:
        return int(_c.kde_lees("kscreenlockerrc", "Daemon", "Timeout", "5"))
    except ValueError:
        return 5


def slot_herlees() -> None:
    _c.draai("gdbus", "call", "--session", "--dest", "org.freedesktop.ScreenSaver", "--object-path", "/ScreenSaver",
          "--method", "org.kde.screensaver.configure", timeout=5)


def zet_slot_na(minuten: int) -> None:
    if _c.VOORBEELD:
        _c._VB["slot_na"] = minuten
        return
    _c.kde_schrijf("kscreenlockerrc", "Daemon", "Autolock", "true" if minuten else "false")
    if minuten:
        _c.kde_schrijf("kscreenlockerrc", "Daemon", "Timeout", str(minuten))
    slot_herlees()


def slot_na_slapen() -> bool:
    if _c.VOORBEELD:
        return _c._VB["slot_na_slapen"]
    return _c.kde_lees("kscreenlockerrc", "Daemon", "LockOnResume", "true") == "true"


def zet_slot_na_slapen(aan: bool) -> None:
    if _c.VOORBEELD:
        _c._VB["slot_na_slapen"] = aan
        return
    _c.kde_schrijf("kscreenlockerrc", "Daemon", "LockOnResume", "true" if aan else "false")
    slot_herlees()


def vergrendel() -> None:
    if not _c.VOORBEELD:
        _c.draai("loginctl", "lock-session", timeout=5)


# ======================================================== andere mensen ===
# Lezen gaat uit pwd en grp (zoals gebruiker()): dat mist nooit iemand en heeft geen D-Bus nodig. Veranderen gaat
# via AccountsService; dat vraagt zelf het wachtwoord van een beheerder (polkit), net als Windows.

@dataclass
class Persoon:
    naam: str               # inlognaam
    volledige_naam: str
    uid: int
    beheerder: bool         # lid van wheel (zo telt AccountsService het op Fedora ook)
    foto: str = ""          # pad, of ""
    ingelogd: bool = False
    ik: bool = False        # dat ben jij


def uid_grenzen(tekst: str) -> tuple[int, int]:
    """UID_MIN en UID_MAX uit /etc/login.defs: daartussen zitten de mensen (de rest is het systeem)."""
    grenzen = {"UID_MIN": 1000, "UID_MAX": 60000}
    for regel in tekst.splitlines():
        delen = regel.split()
        if len(delen) >= 2 and delen[0] in grenzen and delen[1].isdigit():
            grenzen[delen[0]] = int(delen[1])
    return grenzen["UID_MIN"], grenzen["UID_MAX"]


def lees_ingelogd(uitvoer: str) -> set[str]:
    """Wie is nu ingelogd, uit 'loginctl list-users --no-legend' (UID USER LINGER STATE). 'closing' is al aan het
    afmelden. Een oud systemd geeft alleen UID en USER: dan telt iedereen in de lijst."""
    namen = set()
    for regel in uitvoer.splitlines():
        delen = regel.split()
        if len(delen) >= 4:
            if delen[3] in ("active", "online"):
                namen.add(delen[1])
        elif len(delen) >= 2:
            namen.add(delen[1])
    return namen


def lees_mensen(rijen, wheel, grenzen: tuple[int, int], ik_uid: int, ingelogd: set[str],
                fotomap_: str | Path) -> list[Persoon]:
    """rijen: (naam, uid, gecos, shell) zoals pwd.getpwall(). Alleen echte mensen: een uid tussen de grenzen en een
    shell waarmee je kunt inloggen."""
    uit = []
    for naam, uid, gecos, shell in rijen:
        if not grenzen[0] <= uid <= grenzen[1] or shell.endswith(("nologin", "false")):
            continue
        vol = (gecos or "").split(",")[0].strip() or naam.capitalize()
        foto = Path(fotomap_) / naam
        uit.append(Persoon(naam, vol, uid, naam in wheel, str(foto) if foto.is_file() else "", naam in ingelogd,
                           uid == ik_uid))
    return uit


def _vb_mensen() -> list[Persoon]:
    if _VB_ACCOUNT["mensen"] is None:
        _VB_ACCOUNT["mensen"] = [
            Persoon("bugie", "Bugie", 1000, True, "", True, True),
            Persoon("werk", t("Werk", "Work"), 1501, True),
            Persoon("huiswerk", t("Huiswerk", "Homework"), 1502, False),
            Persoon("gast", t("Gast", "Guest"), 1503, False),
        ]
    return _VB_ACCOUNT["mensen"]


def ingelogd_nu() -> set[str]:
    return lees_ingelogd(_c.draai("loginctl", "list-users", "--no-legend", timeout=5)[1])


def mensen() -> list[Persoon]:
    """Iedereen die op deze computer kan inloggen (jij ook: ik=True)."""
    from dataclasses import replace
    if _c.VOORBEELD:
        return [replace(p) for p in _vb_mensen()]
    import grp
    import pwd
    try:
        grenzen = uid_grenzen(Path("/etc/login.defs").read_text(encoding="utf-8", errors="replace"))
    except OSError:
        grenzen = (1000, 60000)
    try:
        wheel = list(grp.getgrnam("wheel").gr_mem)
    except KeyError:
        wheel = []
    rijen = [(p.pw_name, p.pw_uid, p.pw_gecos, p.pw_shell) for p in pwd.getpwall()]
    return lees_mensen(rijen, wheel, grenzen, os.getuid(), ingelogd_nu(), fotomap())


def naam_bestaat(naam: str) -> bool:
    """Bestaat er al iemand of een groep met deze naam? (useradd faalt ook bij een groep: code 9.)"""
    if _c.VOORBEELD:
        return naam in {p.naam for p in _vb_mensen()} | {"root", "wheel"}
    import grp
    import pwd
    for zoek in (pwd.getpwnam, grp.getgrnam):
        try:
            zoek(naam)
            return True
        except KeyError:
            pass
    return False


def accounts_roep(pad: str, interface: str, methode: str, *args, timeout: int = 600) -> tuple[bool, str, list]:
    """Eén aanroep naar AccountsService in dít proces (QtDBus), met de wachtwoordvraag van polkit erbij. Zo staat
    een wachtwoord(-hash) nooit op een opdrachtregel. De tijd is ruim: het wachtwoordvenster telt mee.
    Geeft (gelukt, 'foutnaam: foutmelding', antwoorden); een objectpad komt terug als tekst."""
    try:
        from PySide6.QtDBus import QDBus, QDBusConnection, QDBusMessage, QDBusObjectPath
    except ImportError:
        return False, "dbus", []
    bericht = QDBusMessage.createMethodCall("org.freedesktop.Accounts", pad, interface, methode)
    bericht.setArguments(list(args))
    bericht.setInteractiveAuthorizationAllowed(True)
    antwoord = QDBusConnection.systemBus().call(bericht, QDBus.CallMode.Block, timeout * 1000)
    if antwoord.type() == QDBusMessage.MessageType.ErrorMessage:
        return False, f"{antwoord.errorName()}: {antwoord.errorMessage()}", []
    return True, "", [a.path() if isinstance(a, QDBusObjectPath) else a for a in antwoord.arguments()]


def _reden(fout: str) -> str:
    """Een D-Bus-fout van AccountsService in één woord, voor de melding op de pagina."""
    if any(w in fout for w in ("PermissionDenied", "AccessDenied", "InteractiveAuthorizationRequired",
                               "NotAuthorized", "Not authorized")):
        return "geweigerd"
    if any(w in fout for w in ("UnknownObject", "does not exist", "UnknownMethod")):
        return "later"
    return "fout"


def _user_pad(uid: int) -> str:
    return f"/org/freedesktop/Accounts/User{int(uid)}"


def laatste_beheerder(p: Persoon, alle: list[Persoon]) -> bool:
    """Is dit de enige beheerder? Die mag niet weg en niet gewone gebruiker worden."""
    return p.beheerder and sum(1 for x in alle if x.beheerder) <= 1


def zet_soort(p: Persoon, beheerder: bool, alle: list[Persoon]) -> tuple[bool, str]:
    """Beheerder maken of een gewone gebruiker. Reden: 'laatste' (er moet een beheerder blijven), 'geweigerd',
    'later' (AccountsService kent de persoon nog niet: na een herstart), 'fout'."""
    if not beheerder and laatste_beheerder(p, alle):
        return False, "laatste"
    if _c.VOORBEELD:
        for x in _vb_mensen():
            if x.naam == p.naam:
                x.beheerder = beheerder
        return True, ""
    ok, fout, _ = _c.accounts_roep(_user_pad(p.uid), "org.freedesktop.Accounts.User", "SetAccountType",
                                   1 if beheerder else 0)
    return (True, "") if ok else (False, _reden(fout))


_laatst_weg: float | None = None   # wanneer we iemand weghaalden (zie maak_persoon: AccountsService heeft even nodig)


def verwijder_persoon(p: Persoon, alle: list[Persoon]) -> tuple[bool, str]:
    """Iemand van deze computer halen, met al zijn bestanden. Reden: 'ik', 'laatste', 'ingelogd', 'geweigerd',
    'fout'. Bestanden bewaren bieden we niet: het volgende nieuwe account krijgt hetzelfde uid, en dus die map."""
    global _laatst_weg
    if p.ik:
        return False, "ik"
    if laatste_beheerder(p, alle):
        return False, "laatste"
    if _c.VOORBEELD:
        if p.ingelogd:
            return False, "ingelogd"
        _VB_ACCOUNT["mensen"] = [x for x in _vb_mensen() if x.naam != p.naam]
        return True, ""
    if p.naam in ingelogd_nu():
        return False, "ingelogd"
    if lees_autologin(_inlog_teksten(), p.naam):
        # Eerst 'inloggen zonder wachtwoord' uit (daarna kent bugos-login die naam niet meer).
        if _c.draai("pkexec", "/usr/bin/bugos-login", "uit", p.naam, timeout=600)[0] != 0:
            return False, "geweigerd"
    # Niet via QtDBus: DeleteUser wil een int64 en PySide6 stuurt een klein getal als int32 (InvalidArgs). gdbus
    # leest de soorten uit de beschrijving van de dienst. Het uid lazen we zelf (een getal: niets in te smokkelen).
    # --timeout: anders geeft gdbus het na 25 s op, terwijl je nog je wachtwoord typt of de bestanden nog weggaan.
    code = _c.draai("gdbus", "call", "--system", "--interactive", "--timeout", "600", "--dest",
                    "org.freedesktop.Accounts", "--object-path", "/org/freedesktop/Accounts", "--method",
                    "org.freedesktop.Accounts.DeleteUser", str(int(p.uid)), "true", timeout=610)[0]
    if code != 0:
        # Toch weg? (gdbus kan opgeven terwijl AccountsService doorwerkt.) Even kijken.
        for _ in range(6):
            if not naam_bestaat(p.naam):
                break
            time.sleep(0.5)
        else:
            return False, "geweigerd"
    _laatst_weg = time.monotonic()
    return True, ""


def zet_foto(pad: str) -> bool:
    """Je eigen foto (het startmenu en het inlogscherm laten hem zien). AccountsService kopieert het bestand naar
    /var/lib/AccountsService/icons/<naam>; voor jezelf is geen wachtwoord nodig. pad '' haalt de foto weg.
    Het bestand is een tijdelijke kopie van de pagina: die gaat daarna altijd weg."""
    if _c.VOORBEELD:
        # De voorbeeldstand bewaart de kopie zelf (dat is dan 'de map van AccountsService'); de vorige gaat weg.
        oud = _VB_ACCOUNT["foto"]
        if oud and oud != pad:
            Path(oud).unlink(missing_ok=True)
        _VB_ACCOUNT["foto"] = pad
        return True
    try:
        ok, _fout, _ = _c.accounts_roep(_user_pad(os.getuid()), "org.freedesktop.Accounts.User", "SetIconFile", pad,
                                        timeout=30)
    finally:
        if pad:
            Path(pad).unlink(missing_ok=True)
    return ok


def zet_wachtwoord_van(uid: int, nieuw: str) -> tuple[bool, str]:
    """Een nieuw wachtwoord voor iemand anders (een beheerder mag dat). Reden: 'crypt', 'geweigerd', 'later', 'fout'.
    De hash gaat over D-Bus in dit proces, nooit op een opdrachtregel."""
    if _c.VOORBEELD:
        return True, ""
    try:
        hash_ = versleutel(nieuw)
    except OSError:
        hash_ = ""
    if not hash_:
        return False, "crypt"
    ok, fout, _ = _c.accounts_roep(_user_pad(uid), "org.freedesktop.Accounts.User", "SetPassword", hash_, "")
    return (True, "") if ok else (False, _reden(fout))


# Strenger dan bugos-login (U002: ^[a-z_][a-z0-9_.-]{0,31}$), dus wat hier mag, mag daar altijd. useradd op Fedora
# neemt ook hoofdletters aan (Jan.Jansen), en dan weigert bugos-login hem later: daarom kijken we zelf.
INLOGNAAM = re.compile(r"[a-z][a-z0-9._-]{0,31}")


def volledige_naam_fout(naam: str) -> str:
    """'' als de naam goed is, anders 'leeg', 'teken' (: , of een nieuwe regel: die breken /etc/passwd) of 'lang'."""
    if not naam.strip():
        return "leeg"
    if any(c in naam for c in ":,\n\r"):
        return "teken"
    if len(naam) > 64:
        return "lang"
    return ""


def inlognaam_fout(naam: str, bestaat=None) -> str:
    """'' als de inlognaam kan, anders 'leeg', 'lang', 'teken' of 'bestaat'."""
    bestaat = bestaat or naam_bestaat
    if not naam:
        return "leeg"
    if len(naam) > 32:
        return "lang"
    if not INLOGNAAM.fullmatch(naam) or naam.endswith((".", "-")):
        return "teken"
    if naam == "root" or bestaat(naam):
        return "bestaat"
    return ""


def inlognaam_voor(volledig: str, bestaat=None) -> str:
    """Een inlognaam bij een naam: 'Crème Brûlée' -> 'creme', of 'creme.brulee' / 'creme2' als die al bestaat."""
    import unicodedata
    bestaat = bestaat or naam_bestaat
    plat = "".join(c for c in unicodedata.normalize("NFKD", volledig) if not unicodedata.combining(c)).lower()
    woorden = re.findall(r"[a-z0-9]+", plat)
    if not woorden:
        return ""
    if woorden[0][0].isdigit():
        woorden[0] = "u" + woorden[0]
    basis = woorden[0]
    kandidaten = [basis]
    if len(woorden) > 1:
        kandidaten.append(".".join(woorden))
    # Lang? Dan het getal achter een ingekorte naam, anders knipt '…2' weer terug tot de naam die al bestaat.
    kandidaten += [basis[:32 - len(str(n))] + str(n) for n in range(2, 100)]
    for k in kandidaten:
        k = k[:32].rstrip(".-")
        if inlognaam_fout(k, bestaat) == "":
            return k
    return ""


WACHT_NA_WEG = 10.0   # seconden: haal je iemand weg en voeg je meteen iemand toe, dan raakt AccountsService in de war


def maak_persoon(naam: str, volledig: str, beheerder: bool, wachtwoord: str) -> tuple[bool, str]:
    """Iemand toevoegen: een account met een eigen map, en meteen een wachtwoord. Reden: 'fout' (rare naam),
    'crypt', 'geweigerd', 'bestaat', 'wachtwoord' (het account is er, maar op slot: het wachtwoord lukte niet).
    Het wachtwoord gaat alleen als hash over D-Bus in dit proces, nooit op een opdrachtregel of in een bestand."""
    if inlognaam_fout(naam) or volledige_naam_fout(volledig) or not wachtwoord:
        return False, "fout"
    if _c.VOORBEELD:
        lijst = _vb_mensen()
        lijst.append(Persoon(naam, volledig.strip(), max(p.uid for p in lijst) + 1, beheerder))
        return True, ""
    try:
        hash_ = versleutel(wachtwoord)   # eerst: nooit een account zonder wachtwoord
    except OSError:
        hash_ = ""
    if not hash_:
        return False, "crypt"
    # Net iemand weggehaald? Dan maakt AccountsService het nieuwe account wel, maar zonder D-Bus-object
    # ('An object is already exported'), en kan het geen wachtwoord krijgen. Even wachten voorkomt dat.
    if _laatst_weg is not None:
        rest = WACHT_NA_WEG - (time.monotonic() - _laatst_weg)
        if rest > 0:
            time.sleep(rest)
    ok, fout, uit = _c.accounts_roep("/org/freedesktop/Accounts", "org.freedesktop.Accounts", "CreateUser",
                                     naam, volledig.strip(), 1 if beheerder else 0)
    if not ok:
        if "UserExists" in fout or ("useradd" in fout and "code 9" in fout):
            return False, "bestaat"
        return False, "geweigerd" if _reden(fout) == "geweigerd" else "fout"
    pad = str(uit[0]) if uit and str(uit[0]).startswith("/org/freedesktop/Accounts/") else ""
    # Het nieuwe account moet er op D-Bus zijn voordat het een wachtwoord kan krijgen (even wachten, hooguit 5 s).
    klaar = False
    for _ in range(10):
        if not pad:
            gevonden = _c.accounts_roep("/org/freedesktop/Accounts", "org.freedesktop.Accounts", "FindUserByName",
                                        naam, timeout=5)
            if gevonden[0] and gevonden[2]:
                pad = str(gevonden[2][0])
        if pad and _c.accounts_roep(pad, "org.freedesktop.DBus.Properties", "Get", "org.freedesktop.Accounts.User",
                                    "UserName", timeout=5)[0]:
            klaar = True
            break
        time.sleep(0.5)
    if not klaar:
        return False, "wachtwoord"
    if not _c.accounts_roep(pad, "org.freedesktop.Accounts.User", "SetPassword", hash_, "")[0]:
        return False, "wachtwoord"
    return True, ""


# ========================================================== toetsenbord ===
# Je eigen toetsenborden staan in ~/.config/kxkbrc (KWin past ze meteen toe); het toetsenbord van het inlogscherm
# (en van nieuwe mensen) is van het systeem: locale1, via localectl (vraagt het wachtwoord van een beheerder).

@dataclass(frozen=True)
class Indeling:
    layout: str          # bv. "us", "be"
    variant: str = ""    # bv. "intl"


MAX_TOETSENBORDEN = 4    # xkb kent vier groepen

# (layout, variant, nl, en): de gewone keuzes bovenaan, in gewone woorden.
BEKEND = [
    ("us", "", "Engels (VS)", "English (US)"),
    ("us", "intl", "VS-Internationaal (accenten met ' en \")", "US-International (accents with ' and \")"),
    ("us", "altgr-intl", "VS-Internationaal met AltGr", "US-International with AltGr"),
    ("nl", "", "Nederlands", "Dutch"),
    ("be", "", "Belgisch (AZERTY)", "Belgian (AZERTY)"),
    ("fr", "", "Frans (AZERTY)", "French (AZERTY)"),
    ("de", "", "Duits (QWERTZ)", "German (QWERTZ)"),
    ("gb", "", "Engels (VK)", "English (UK)"),
    ("tr", "", "Turks (Q)", "Turkish (Q)"),
    ("tr", "f", "Turks (F)", "Turkish (F)"),
    ("es", "", "Spaans", "Spanish"), ("it", "", "Italiaans", "Italian"), ("pt", "", "Portugees", "Portuguese"),
    ("pl", "", "Pools", "Polish"), ("ua", "", "Oekraïens", "Ukrainian"), ("ara", "", "Arabisch", "Arabic"),
    ("ch", "", "Zwitsers (Duits)", "Swiss (German)"), ("ch", "fr", "Zwitsers (Frans)", "Swiss (French)"),
]
EVDEV = ("/usr/share/X11/xkb/rules/evdev.lst", "/usr/share/xkeyboard-config-2/rules/evdev.lst")
_LAYOUT = re.compile(r"[a-z0-9_]{1,32}")
_VARIANT = re.compile(r"[a-z0-9_-]{0,32}")
_VB_ACCOUNT.update(toetsenborden=[("us", "intl"), ("be", "")], toetsenbord_inlog=("us", ""))


def lees_evdev_lst(tekst: str) -> list[tuple[Indeling, str]]:
    """Alle toetsenborden uit evdev.lst van xkb: (indeling, Engelse beschrijving). Een layout-regel is
    '  us   English (US)', een variant-regel '  intl   us: English (US, intl., with dead keys)'."""
    uit: list[tuple[Indeling, str]] = []
    deel = ""
    for regel in tekst.splitlines():
        if regel.startswith("!"):
            deel = regel[1:].strip()
            continue
        delen = regel.split(None, 1)
        if len(delen) < 2 or deel not in ("layout", "variant"):
            continue
        naam, rest = delen[0], delen[1].strip()
        if deel == "layout":
            uit.append((Indeling(naam), rest))
        elif ":" in rest:
            ouder, beschrijving = rest.split(":", 1)
            uit.append((Indeling(ouder.strip(), naam), beschrijving.strip()))
    return uit


def alle_toetsenborden() -> list[tuple[Indeling, str]]:
    """Elk toetsenbord dat xkb kent (het eerste evdev.lst dat er is), of [] als er geen is."""
    for pad in EVDEV:
        try:
            return lees_evdev_lst(Path(pad).read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return []


def toetsenbord_naam(ind: Indeling, beschrijving: str = "", nl: bool = True) -> str:
    """De naam die je ziet: uit BEKEND, anders de beschrijving van xkb (in het Nederlands vertaald), anders de code."""
    for layout, variant, naam_nl, naam_en in BEKEND:
        if (layout, variant) == (ind.layout, ind.variant):
            return naam_nl if nl else naam_en
    if beschrijving:
        if nl:
            for vertaling in _xkb_vertalingen():
                vertaald = vertaling.gettext(beschrijving)
                if vertaald != beschrijving:
                    return vertaald
        return beschrijving
    return f"{ind.layout} ({ind.variant})" if ind.variant else ind.layout


_XKB_VERTALING: list = []


def _xkb_vertalingen() -> list:
    """De Nederlandse namen van xkb (eenmaal opzoeken: de keuzelijst vraagt er honderden)."""
    if not _XKB_VERTALING:
        import gettext
        _XKB_VERTALING.extend(gettext.translation(d, languages=["nl"], fallback=True)
                              for d in ("xkeyboard-config-2", "xkeyboard-config"))
    return _XKB_VERTALING


def lees_localectl_alles(uitvoer: str) -> dict[str, str]:
    """De regels 'X11 Layout:', 'X11 Model:', 'X11 Variant:' en 'X11 Options:' uit 'localectl status'
    ('' als ze niet gezet zijn)."""
    uit = {"layout": "", "model": "", "variant": "", "options": ""}
    for regel in uitvoer.splitlines():
        if ":" not in regel:
            continue
        sleutel, waarde = (x.strip() for x in regel.split(":", 1))
        if sleutel.startswith("X11 ") and sleutel[4:].lower() in uit:
            uit[sleutel[4:].lower()] = "" if waarde == "(unset)" else waarde
    return uit


def lees_localectl(uitvoer: str) -> Indeling | None:
    """Het toetsenbord van het systeem (inlogscherm), of None als het niet gezet is."""
    d = lees_localectl_alles(uitvoer)
    if not d["layout"]:
        return None
    return Indeling(d["layout"].split(",")[0], d["variant"].split(",")[0])


def _localectl_status() -> str:
    return _c.draai("localectl", "status", timeout=5)[1]


def systeem_toetsenbord() -> Indeling:
    """Het toetsenbord van het inlogscherm. Niet gezet: Engels (VS), dat gebruikt het inlogscherm dan (I13)."""
    if _c.VOORBEELD:
        return Indeling(*_VB_ACCOUNT["toetsenbord_inlog"])
    return lees_localectl(_localectl_status()) or Indeling("us")


def _lijst(tekst: str) -> list[str]:
    return [x.strip() for x in tekst.split(",")] if tekst.strip() else []


def toetsenborden() -> list[Indeling]:
    """Je eigen toetsenborden; de eerste wordt eerst gebruikt. Nog niets gekozen: dat van het systeem."""
    if _c.VOORBEELD:
        return [Indeling(*x) for x in _VB_ACCOUNT["toetsenborden"]]
    if _c.kde_lees("kxkbrc", "Layout", "Use", "false") == "true":
        layouts = _lijst(_c.kde_lees("kxkbrc", "Layout", "LayoutList", ""))
        varianten = _lijst(_c.kde_lees("kxkbrc", "Layout", "VariantList", ""))
        varianten += [""] * (len(layouts) - len(varianten))
        lijst = [Indeling(lay, var) for lay, var in zip(layouts, varianten) if lay]
        if lijst:
            return lijst
    return [systeem_toetsenbord()]


def goede_indeling(ind: Indeling) -> bool:
    return bool(_LAYOUT.fullmatch(ind.layout)) and bool(_VARIANT.fullmatch(ind.variant))


def zet_toetsenborden(lijst: list[Indeling]) -> bool:
    """Schrijf je toetsenborden in kxkbrc. Eerst alles stil, en als laatste Use=true mét --notify: dan leest KWin
    de hele groep opnieuw en kun je meteen typen (los herladen via D-Bus doet niets, nagekeken). Met twee of meer:
    wisselen met Windows-toets + spatie. Andere opties (bv. caps:escape uit KDE) blijven staan."""
    if not 1 <= len(lijst) <= MAX_TOETSENBORDEN or not all(goede_indeling(i) for i in lijst):
        return False
    if _c.VOORBEELD:
        _VB_ACCOUNT["toetsenborden"] = [(i.layout, i.variant) for i in lijst]
        return True
    opties = [o for o in _lijst(_c.kde_lees("kxkbrc", "Layout", "Options", "")) if not o.startswith("grp:")]
    if len(lijst) > 1:
        opties.append("grp:win_space_toggle")

    def stil(sleutel: str, waarde: str | None) -> bool:
        cmd = ["kwriteconfig6", "--file", "kxkbrc", "--group", "Layout", "--key", sleutel]
        cmd += ["--delete"] if waarde is None else [waarde]
        return _c.draai(*cmd, timeout=5)[0] == 0

    goed = stil("LayoutList", ",".join(i.layout for i in lijst))
    goed = stil("VariantList", ",".join(i.variant for i in lijst)) and goed
    goed = stil("DisplayNames", "," * (len(lijst) - 1)) and goed
    goed = stil("ResetOldOptions", "true") and goed
    goed = stil("Options", ",".join(opties) if opties else None) and goed
    return _c.kde_schrijf("kxkbrc", "Layout", "Use", "true") and goed


def zet_systeem_toetsenbord(ind: Indeling) -> bool:
    """Ook voor het inlogscherm (en wie nieuw is): localectl, het wachtwoord van een beheerder. Het model en de opties
    die er al staan, geven we terug (anders wist localectl ze, I13). Zonder --no-convert: ook de tekstconsole."""
    if not goede_indeling(ind):
        return False
    if _c.VOORBEELD:
        _VB_ACCOUNT["toetsenbord_inlog"] = (ind.layout, ind.variant)
        return True
    nu = lees_localectl_alles(_localectl_status())
    if _c.draai("localectl", "set-x11-keymap", ind.layout, nu["model"], ind.variant, nu["options"],
                timeout=120)[0] == 0:
        return True
    # localectl geeft het na 25 s op, ook als je dan nog je wachtwoord typt; daarna gebeurt het toch (I5).
    return lees_localectl(_localectl_status()) == ind
