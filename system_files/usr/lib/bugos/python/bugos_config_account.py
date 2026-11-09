"""BugOS Instellingen: tijd en taal (timedatectl, plasma-localerc) en inloggen en wachtwoord
(AccountsService, bugos-login, kscreenlockerrc).

Hoort bij bugos_config (importeer het via daar). draai, VOORBEELD, _VB en de KDE-hulpjes komen via
bugos_config (_c.draai), zodat een test die bi.draai of bi.VOORBEELD vervangt dat ook hier ziet.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import bugos_config as _c


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


def gebruiker() -> Gebruiker:
    if _c.VOORBEELD:
        return Gebruiker("bugie", _c._VB["volledige_naam"], True, _c._VB["auto_inloggen"])
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
    teksten = []
    for pad in inlog_bestanden():
        p = Path(pad)
        bestanden = sorted(p.glob("*.conf")) if p.is_dir() else [p]
        for b in bestanden:
            try:
                teksten.append(b.read_text(encoding="utf-8"))
            except OSError:
                pass
    return Gebruiker(naam, vol or naam.capitalize(), beheerder, lees_autologin(teksten, naam))


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
