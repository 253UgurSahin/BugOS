#!/usr/bin/env python3
"""Test van pakket 'account' in BugOS Instellingen: de klok met de hand, andere mensen (toevoegen, beheerder maken,
verwijderen, nieuw wachtwoord), je eigen foto, de notatie van datum en tijd, en de toetsenborden. Alles zonder KDE.

Er verandert niets aan je computer: de opdrachten worden opgevangen (bi.draai vervangen), D-Bus wordt nagedaan
(bi.accounts_roep vervangen) en de pagina's draaien in de voorbeeldstand. Geen root, geen polkit nodig.

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_native_account.py
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import re
import shutil
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"
BIN = ROOT / "system_files" / "usr" / "bin"
sys.path.insert(0, str(PY))
TMP = Path(tempfile.mkdtemp(prefix="bugos-account-test-"))
os.environ.update(BUGOS_INSTELLINGEN_VOORBEELD="1", LC_ALL="nl_NL.UTF-8", HOME=str(TMP), BUGOS_SYS=str(TMP / "sys"),
                  XDG_RUNTIME_DIR=str(TMP), BUGOS_ACCOUNTS_ICONEN=str(TMP / "iconen"))
os.environ.pop("LANGUAGE", None)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.dont_write_bytecode = True

import bugos_config as bi  # noqa: E402
import bugos_config_account as ca  # noqa: E402

fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


def vang(functie, *args, antwoord=lambda cmd: (0, ""), **kwargs):
    """Roep functie aan zonder voorbeeldstand, en geef de opdrachten die ze wilde draaien."""
    oud = (bi.VOORBEELD, bi.draai, shutil.which)
    opdrachten: list = []
    bi.VOORBEELD = False
    bi.draai = lambda *cmd, **kw: (opdrachten.append(cmd), antwoord(cmd))[1]
    shutil.which = lambda naam, *a, **k: "/usr/bin/" + naam
    try:
        uit = functie(*args, **kwargs)
    finally:
        bi.VOORBEELD, bi.draai, shutil.which = oud
    return opdrachten, uit


# ================================================================== de klok met de hand (stap 1) ===

def _ntp(aan: bool):
    def antwoord(cmd):
        if cmd[:2] == ("timedatectl", "show"):
            return 0, f"Timezone=Europe/Amsterdam\nNTP={'yes' if aan else 'no'}\nNTPSynchronized=no\n"
        return 0, ""
    return antwoord


_o14, _u14 = vang(bi.zet_klok, datetime(2026, 11, 11, 9, 30), antwoord=_ntp(False))
klopt(_u14 == (True, "") and ("timedatectl", "set-time", "2026-11-11 09:30:00") in _o14,
      f"14: klok zetten via timedatectl set-time, plaatselijke tijd ({_o14})")
_o14b, _u14b = vang(bi.zet_klok, datetime(2026, 11, 11, 9, 30), antwoord=_ntp(True))
klopt(_u14b == (False, "auto") and not any(c[:2] == ("timedatectl", "set-time") for c in _o14b),
      f"14: tijd gaat nog vanzelf: 'auto', en geen set-time ({_u14b})")


def _weigert(cmd):
    if cmd[:2] == ("timedatectl", "set-time"):
        return 1, ""
    return _ntp(False)(cmd)


_o14c, _u14c = vang(bi.zet_klok, datetime(2030, 1, 1, 12, 0), antwoord=_weigert)
klopt(_u14c == (False, "fout"), f"14: geweigerd en de klok staat niet op de gevraagde tijd: 'fout' ({_u14c})")
_bijna = datetime.now().replace(microsecond=0)
_bijna = _bijna.replace(year=_bijna.year + 1)   # stel: de klok liep een jaar achter, en het lukte na 25 s toch
_echt_now = ca.datetime
_stap = iter([datetime(2026, 1, 1, 8, 0), _bijna])


class _SprongDatum(datetime):
    @classmethod
    def now(cls, tz=None):   # eerst de oude tijd, daarna (na de time-out) staat de klok op de gevraagde tijd
        return next(_stap, _bijna) if tz is None else _echt_now.now(tz)


ca.datetime = _SprongDatum
try:
    _o14e, _u14e = vang(bi.zet_klok, _bijna, antwoord=_weigert)
finally:
    ca.datetime = _echt_now
klopt(_u14e == (True, ""), f"I5: timedatectl gaf het op, maar de klok staat wel goed: gelukt ({_u14e})")

# ============================================================== andere mensen: lezen (stap 2) ===

klopt(bi.uid_grenzen("UID_MIN 1000\nUID_MAX 60000\n") == (1000, 60000) and bi.uid_grenzen("rommel\nUID_MIN x\n")
      == (1000, 60000) and bi.uid_grenzen("# x\nUID_MIN   2000\n") == (2000, 60000), "1: UID_MIN en UID_MAX lezen")
klopt(bi.lees_ingelogd("   0 root  no closing\n1000 bugie no active\n1501 gast no online\n") == {"bugie", "gast"}
      and bi.lees_ingelogd("1000 bugie\n1501 gast\n") == {"bugie", "gast"},
      "2: wie is ingelogd (closing telt niet; oud systemd met twee kolommen: iedereen)")
(TMP / "iconen").mkdir()
(TMP / "iconen" / "gast").write_bytes(b"x")
_m3 = bi.lees_mensen([("root", 0, "root", "/bin/bash"), ("bugie", 1000, "Bugie,,,", "/bin/bash"),
                      ("gast", 1501, "", "/bin/bash"), ("nobody", 65534, "", "/sbin/nologin"),
                      ("svc", 1505, "", "/usr/sbin/nologin"), ("dicht", 1506, "", "/bin/false")],
                     ["bugie"], (1000, 60000), 1000, {"bugie"}, TMP / "iconen")
_g3 = {p.naam: p for p in _m3}
klopt(set(_g3) == {"bugie", "gast"} and _g3["gast"].volledige_naam == "Gast" and _g3["gast"].foto
      and not _g3["gast"].beheerder and not _g3["gast"].ingelogd and _g3["bugie"].ik and _g3["bugie"].beheerder
      and _g3["bugie"].volledige_naam == "Bugie" and _g3["bugie"].ingelogd,
      f"3: mensen uit pwd: geen systeemaccounts, naam uit gecos of inlognaam, foto, beheerder ({_m3})")

# ======================================================== andere mensen: veranderen (stap 2) ===

_P = bi.Persoon
_ik = _P("bugie", "Bugie", 1000, True, ik=True, ingelogd=True)
_gast = _P("gast", "Gast", 1501, False)
_werk = _P("werk", "Werk", 1502, True)
_alle = [_ik, _gast, _werk]
_o17, _u17 = vang(bi.verwijder_persoon, _gast, _alle)
_gdbus17 = [c for c in _o17 if c[0] == "gdbus"]
klopt(_u17 == (True, "") and _gdbus17 == [("gdbus", "call", "--system", "--interactive", "--timeout", "600", "--dest",
                                           "org.freedesktop.Accounts", "--object-path", "/org/freedesktop/Accounts",
                                           "--method", "org.freedesktop.Accounts.DeleteUser", "1501", "true")],
      f"17: verwijderen via gdbus DeleteUser <uid> true, met een ruime --timeout (I1) ({_gdbus17})")
klopt(ca._laatst_weg is not None, "17: na het verwijderen weet BugOS wanneer (voor het wachten bij toevoegen)")
_o17b, _u17b = vang(bi.verwijder_persoon, _ik, _alle)
klopt(_u17b == (False, "ik") and not _o17b, f"17: jezelf: 'ik', zonder iets te draaien, ook in de CI ({_u17b})")
_o17c, _u17c = vang(bi.verwijder_persoon, _P("werk", "Werk", 1502, True), [_P("bugie", "Bugie", 1000, False, ik=True),
                                                                          _P("werk", "Werk", 1502, True)])
klopt(_u17c == (False, "laatste") and not _o17c, f"17: de laatste beheerder: 'laatste' ({_u17c})")
_o17d, _u17d = vang(bi.verwijder_persoon, _gast, _alle,
                    antwoord=lambda c: (0, "1000 bugie no active\n1501 gast no active\n") if c[0] == "loginctl" else (0, ""))
klopt(_u17d == (False, "ingelogd") and not any(c[0] == "gdbus" for c in _o17d),
      f"17: nog ingelogd: 'ingelogd' en geen gdbus ({_u17d})")
# I1: gdbus gaf het op (rc 1), maar de persoon is wel weg: dan is het gelukt.
_oud_nb = ca.naam_bestaat
ca.naam_bestaat = lambda n: False
ca._laatst_weg = None
_o17e, _u17e = vang(bi.verwijder_persoon, _gast, _alle, antwoord=lambda c: (1, "") if c[0] == "gdbus" else (0, ""))
ca.naam_bestaat = lambda n: True
_oud_sleep = ca.time.sleep
ca.time.sleep = lambda s: None
_o17f, _u17f = vang(bi.verwijder_persoon, _gast, _alle, antwoord=lambda c: (1, "") if c[0] == "gdbus" else (0, ""))
ca.time.sleep = _oud_sleep
ca.naam_bestaat = _oud_nb
klopt(_u17e == (True, "") and ca._laatst_weg is not None and _u17f == (False, "geweigerd"),
      f"I1: gdbus gaf op maar de persoon is weg: gelukt; nog daar: geweigerd ({_u17e}, {_u17f})")
# I3: in de voorbeeldstand nooit loginctl of gdbus, en 'jezelf' komt uit p.ik (niet uit os.getuid()).
_o17g: list = []
_oud17g = bi.draai
bi.draai = lambda *c, **k: (_o17g.append(c), (0, ""))[1]
_vb17 = [p for p in bi.mensen() if not p.ik]
_u17g = bi.verwijder_persoon(_vb17[0], bi.mensen())
bi.draai = _oud17g
klopt(_u17g == (True, "") and not _o17g and all(p.uid >= 1500 for p in _vb17),
      f"I3: voorbeeldstand: verwijderen draait niets, voorbeeld-uids botsen niet met de CI ({_o17g})")
ca._VB_ACCOUNT["mensen"] = None    # weer de gewone voorbeeldlijst


class Dbus:
    """Doet AccountsService na: onthoudt elke aanroep, en antwoordt wat de test wil."""

    def __init__(self, antwoorden=None):
        self.aanroepen: list = []
        self.antwoorden = antwoorden or {}

    def __call__(self, pad, interface, methode, *args, timeout=600):
        self.aanroepen.append((pad, methode, args))
        a = self.antwoorden.get(methode, (True, "", []))
        return a(pad, args) if callable(a) else a


def met_dbus(nep, functie, *args, **kw):
    oud = (bi.VOORBEELD, bi.accounts_roep, bi.draai)
    bi.VOORBEELD, bi.accounts_roep = False, nep
    opdrachten: list = []
    bi.draai = lambda *c, **k: (opdrachten.append(c), (0, ""))[1]
    try:
        return functie(*args, **kw), opdrachten
    finally:
        bi.VOORBEELD, bi.accounts_roep, bi.draai = oud


_n21 = Dbus()
_u21a, _ = met_dbus(_n21, bi.zet_soort, _P("bugie", "Bugie", 1000, True, ik=True), False,
                    [_P("bugie", "Bugie", 1000, True, ik=True), _gast])
klopt(_u21a == (False, "laatste") and not _n21.aanroepen, f"21: de enige beheerder gewone gebruiker: 'laatste' ({_u21a})")
_u21b, _ = met_dbus(_n21, bi.zet_soort, _P("huiswerk", "Huiswerk", 1502, False), True, _alle)
_u21c, _ = met_dbus(_n21, bi.zet_soort, _werk, False, _alle)
klopt(_u21b == (True, "") and _u21c == (True, "") and _n21.aanroepen == [
    ("/org/freedesktop/Accounts/User1502", "SetAccountType", (1,)),
    ("/org/freedesktop/Accounts/User1502", "SetAccountType", (0,))], f"21: SetAccountType 1 en 0 ({_n21.aanroepen})")
_n21d = Dbus({"SetAccountType": (False, "org.freedesktop.Accounts.Error.PermissionDenied: Not authorized", [])})
_u21d, _ = met_dbus(_n21d, bi.zet_soort, _gast, True, _alle)
_n21e = Dbus({"SetAccountType": (False, "org.freedesktop.DBus.Error.UnknownObject: No such object path", [])})
_u21e, _ = met_dbus(_n21e, bi.zet_soort, _gast, True, _alle)
klopt(_u21d == (False, "geweigerd") and _u21e == (False, "later"), f"21: geweigerd en 'na een herstart' ({_u21d}, {_u21e})")
_n22 = Dbus()
_u22, _o22 = met_dbus(_n22, bi.zet_wachtwoord_van, 1502, "nieuw-geheim")
klopt(_u22 == (True, "") and len(_n22.aanroepen) == 1 and _n22.aanroepen[0][:2] == ("/org/freedesktop/Accounts/User1502",
                                                                                       "SetPassword")
      and _n22.aanroepen[0][2][0].startswith("$6$") and _n22.aanroepen[0][2][1] == "" and not _o22,
      f"22: nieuw wachtwoord voor iemand anders: één SetPassword met een hash, geen opdracht ({_n22.aanroepen[:1]})")

# ====================================================================== iemand toevoegen (stap 3) ===

_gast_bestaat = lambda n: n == "gast"  # noqa: E731
_f4 = {n: bi.inlognaam_fout(n, _gast_bestaat) for n in
       ("", "a" * 33, "Cafe", "-x", ".x", "a b", "a;rm", "x.", "x-", "2b", "root", "gast", "huis.werk", "creme-2")}
klopt(_f4 == {"": "leeg", "a" * 33: "lang", "Cafe": "teken", "-x": "teken", ".x": "teken", "a b": "teken",
              "a;rm": "teken", "x.": "teken", "x-": "teken", "2b": "teken", "root": "bestaat", "gast": "bestaat",
              "huis.werk": "", "creme-2": ""}, f"4: regels voor een inlognaam ({_f4})")
_v5 = {
    "Gast": bi.inlognaam_voor("Gast", lambda n: False),
    "Crème Brûlée": bi.inlognaam_voor("Crème Brûlée", lambda n: False),
    "creme bezet": bi.inlognaam_voor("Crème Brûlée", lambda n: n == "creme"),
    "beide bezet": bi.inlognaam_voor("Crème Brûlée", lambda n: n in ("creme", "creme.brulee")),
    "!!!": bi.inlognaam_voor("!!!", lambda n: False),
    "2B": bi.inlognaam_voor("2B", lambda n: False),
    "Huiswerk 2": bi.inlognaam_voor("Huiswerk 2", lambda n: False),
}
klopt(_v5 == {"Gast": "gast", "Crème Brûlée": "creme", "creme bezet": "creme.brulee", "beide bezet": "creme2",
              "!!!": "", "2B": "u2b", "Huiswerk 2": "huiswerk"}, f"5: een inlognaam bij een naam ({_v5})")
_lang = "Abcdefghijklmnopqrstuvwxyzabcdefghijklmn"   # 40 letters
_v5b = bi.inlognaam_voor(_lang, lambda n: n == _lang.lower()[:32])
klopt(len(_v5b) <= 32 and _v5b != _lang.lower()[:32] and _v5b.endswith("2") and bi.inlognaam_fout(_v5b, lambda n: False) == "",
      f"I11: een lange naam die al bestaat wordt toch uniek ({_v5b!r})")
# 6: alles wat wij goedkeuren, mag ook bij bugos-login (U002), anders lukt 'inloggen zonder wachtwoord' later niet.
_regel6 = next(r for r in (BIN / "bugos-login").read_text(encoding="utf-8").splitlines() if "=~" in r)
_patroon6 = re.search(r"\^\S*\$", _regel6).group(0)
_goed6 = [n for n, r in _f4.items() if r == ""] + [v for v in _v5.values() if v] + [_v5b]
klopt(all(re.fullmatch(_patroon6, n) for n in _goed6), f"6: elke goede inlognaam past ook bij bugos-login ({_goed6})")
klopt(bi.volledige_naam_fout("Gast") == "" and bi.volledige_naam_fout("  ") == "leeg"
      and bi.volledige_naam_fout("a:b") == "teken" and bi.volledige_naam_fout("a,b") == "teken"
      and bi.volledige_naam_fout("a\nb") == "teken", "B: een naam zonder : , of nieuwe regel")


def _maak(antwoorden, *args):
    nep = Dbus(antwoorden)
    oud_sleep = ca.time.sleep
    geslapen: list = []
    ca.time.sleep = lambda s: geslapen.append(s)
    try:
        uit, opdrachten = met_dbus(nep, bi.maak_persoon, *args)
    finally:
        ca.time.sleep = oud_sleep
    return uit, nep.aanroepen, opdrachten, geslapen


_oud_nb3 = ca.naam_bestaat
ca.naam_bestaat = lambda n: False
ca._laatst_weg = None
_pad18 = "/org/freedesktop/Accounts/User1501"
_u18, _a18, _o18, _ = _maak({"CreateUser": (True, "", [_pad18])}, "gast", "Gast", False, "geheim-123")
_m18 = [a[1] for a in _a18]
_hash18 = _a18[-1][2][0] if _a18 else ""
klopt(_u18 == (True, "") and _m18 == ["CreateUser", "Get", "SetPassword"] and _a18[0][2] == ("gast", "Gast", 0)
      and _a18[1][0] == _pad18 and _a18[1][2] == ("org.freedesktop.Accounts.User", "UserName")
      and _a18[2][0] == _pad18 and _hash18.startswith("$6$") and _a18[2][2][1] == "",
      f"18: toevoegen: CreateUser, wachten op het account, SetPassword met een hash ({_a18})")
klopt(not any("geheim-123" in " ".join(c) or _hash18 in " ".join(c) for c in _o18),
      "18: het wachtwoord en de hash staan nooit op een opdrachtregel")
_u18b, _a18b, _, _ = _maak({"CreateUser": (True, "", [_pad18])}, "werk", "Werk", True, "geheim-123")
klopt(_a18b[0][2] == ("werk", "Werk", 1), "18: als beheerder: CreateUser met 1")
_u19a, _a19a, _, _ = _maak({"CreateUser": (False, "org.freedesktop.Accounts.Error.PermissionDenied: Not authorized", [])},
                           "gast", "Gast", False, "geheim-123")
_u19b, _, _, _ = _maak({"CreateUser": (False, "org.freedesktop.Accounts.Error.UserExists: A user with name 'gast' "
                                              "already exists", [])}, "gast", "Gast", False, "geheim-123")
_u19c, _, _, _ = _maak({"CreateUser": (False, "org.freedesktop.Accounts.Error.Failed: running '/usr/sbin/useradd' "
                                              "failed: Child process exited with code 9", [])},
                       "video", "Video", False, "geheim-123")
_u19d, _a19d, _, _ = _maak({"CreateUser": (True, "", [_pad18]), "Get": (False, "UnknownObject", [])},
                           "gast", "Gast", False, "geheim-123")
klopt(_u19a == (False, "geweigerd") and [a[1] for a in _a19a] == ["CreateUser"] and _u19b == (False, "bestaat")
      and _u19c == (False, "bestaat") and _u19d == (False, "wachtwoord") and "SetPassword" not in [a[1] for a in _a19d],
      f"19: geweigerd, bestaat al (ook een groep: code 9), en het account komt niet: 'wachtwoord' "
      f"({_u19a}, {_u19b}, {_u19c}, {_u19d})")
_u20a, _a20a, _, _ = _maak({}, "Cafe", "Café", False, "geheim-123")
_u20b, _a20b, _, _ = _maak({}, "cafe", "a:b", False, "geheim-123")
klopt(_u20a == (False, "fout") and _u20b == (False, "fout") and not _a20a and not _a20b,
      "20: een rare naam: 'fout', zonder iets aan AccountsService te vragen")
ca._laatst_weg = time.monotonic()
_u24, _a24, _, _slaap24 = _maak({"CreateUser": (True, "", [_pad18])}, "gast", "Gast", False, "geheim-123")
klopt(_u24 == (True, "") and _slaap24 and _slaap24[0] >= 9 and _a24[0][1] == "CreateUser",
      f"24/I15: net iemand weggehaald: eerst ~10 s wachten, dan pas CreateUser ({_slaap24[:1]})")
ca._laatst_weg = None
ca.naam_bestaat = _oud_nb3

# =========================================================================== toetsenbord (stap 4) ===

_I = bi.Indeling
_lc7 = {
    "be": "   System Locale: LANG=en_US.UTF-8\n       VC Keymap: be\n      X11 Layout: be\n       X11 Model: pc105\n",
    "intl": "   X11 Layout: us\n    X11 Model: pc105\n  X11 Variant: intl\n  X11 Options: terminate:ctrl_alt_bksp\n",
    "niets": "   System Locale: LANG=C.UTF-8\n       VC Keymap: (unset)\n      X11 Layout: (unset)\n",
    "lijst": "      X11 Layout: be,us\n     X11 Variant: ,intl\n",
}
_u7 = {k: bi.lees_localectl(v) for k, v in _lc7.items()}
klopt(_u7 == {"be": _I("be"), "intl": _I("us", "intl"), "niets": None, "lijst": _I("be")}
      and bi.lees_localectl_alles(_lc7["intl"])["options"] == "terminate:ctrl_alt_bksp",
      f"7: het toetsenbord van het systeem uit localectl status ({_u7})")
_evdev8 = ("! model\n  pc105           Generic 105-key PC\n\n! layout\n  us              English (US)\n"
           "  be              Belgian\n\n! variant\n  intl            us: English (US, intl., with dead keys)\n\n"
           "! option\n  grp                  Switching to another layout\n  grp:win_space_toggle Win+Space\n")
_u8 = bi.lees_evdev_lst(_evdev8)
klopt(_u8 == [(_I("us"), "English (US)"), (_I("be"), "Belgian"), (_I("us", "intl"), "English (US, intl., with dead keys)")],
      f"8: evdev.lst: layouts en varianten, geen modellen of opties ({_u8})")
_echt8 = Path(bi.EVDEV[0])
if _echt8.is_file():
    _alle8 = {ind for ind, _b in bi.alle_toetsenborden()}
    _mist8 = [(lay, var) for lay, var, _n, _e in bi.BEKEND if _I(lay, var) not in _alle8]
    klopt(not _mist8, f"8: elk bekend toetsenbord staat in xkb ({_mist8})")
_n9 = (bi.toetsenbord_naam(_I("be"), "Belgian", nl=True), bi.toetsenbord_naam(_I("be"), "Belgian", nl=False),
       bi.toetsenbord_naam(_I("xx", "yy"), "Something (odd)", nl=True), bi.toetsenbord_naam(_I("xx", "yy"), "", nl=True),
       bi.toetsenbord_naam(_I("xx"), "", nl=False))
klopt(_n9[0] == "Belgisch (AZERTY)" and _n9[1] == "Belgian (AZERTY)" and _n9[2] and _n9[3] == "xx (yy)" and _n9[4] == "xx",
      f"9: de naam van een toetsenbord in gewone woorden ({_n9})")
klopt(len({(a, b) for a, b, _n, _e in bi.BEKEND}) == len(bi.BEKEND)
      and all(bi.goede_indeling(_I(a, b)) for a, b, _n, _e in bi.BEKEND), "9: de bekende toetsenborden: uniek en geldig")


def _kxkb(opties: str):
    def antwoord(cmd):
        if cmd[0] == "kreadconfig6" and "Options" in cmd:
            return 0, opties + "\n"
        return 0, ""
    return antwoord


_o11, _u11 = vang(bi.zet_toetsenborden, [_I("us", "intl"), _I("be")], antwoord=_kxkb("caps:escape,grp:alt_shift_toggle"))
_s11 = [c for c in _o11 if c[0] == "kwriteconfig6"]
_verwacht11 = [("LayoutList", "us,be"), ("VariantList", "intl,"), ("DisplayNames", ","), ("ResetOldOptions", "true"),
               ("Options", "caps:escape,grp:win_space_toggle")]
klopt(_u11 and [(c[c.index("--key") + 1], c[-1]) for c in _s11[:-1]] == _verwacht11
      and not any("--notify" in c for c in _s11[:-1]) and _s11[-1][-3:] == ("Use", "--notify", "true")
      and all(c[1:5] == ("--file", "kxkbrc", "--group", "Layout") for c in _s11),
      f"11: twee toetsenborden: eerst alles stil, als laatste Use=true met --notify (KWin past het meteen toe) ({_s11})")
_o11b, _u11b = vang(bi.zet_toetsenborden, [_I("be")], antwoord=_kxkb("caps:escape,grp:win_space_toggle"))
_s11b = {c[c.index("--key") + 1]: c[-1] for c in _o11b if c[0] == "kwriteconfig6"}
klopt(_u11b and _s11b["Options"] == "caps:escape" and _s11b["LayoutList"] == "be" and _s11b["DisplayNames"] == "",
      f"11: één toetsenbord: geen wisseltoets, andere opties blijven ({_s11b})")
_o11c, _ = vang(bi.zet_toetsenborden, [_I("us")], antwoord=_kxkb(""))
klopt(any(c[0] == "kwriteconfig6" and "Options" in c and c[-1] == "--delete" for c in _o11c),
      "11: geen opties over: de sleutel Options gaat weg")
_slecht12 = [[], [_I("us")] * 5, [_I("us;rm")], [_I("us", "a b")], [_I("")], [_I("US")]]
_u12 = [vang(bi.zet_toetsenborden, s) for s in _slecht12]
klopt(all(u is False and not o for o, u in _u12), f"12: rare toetsenborden: niets geschreven ({[u for _o, u in _u12]})")
_o13, _u13 = vang(bi.zet_systeem_toetsenbord, _I("be"), antwoord=lambda c: (0, _lc7["niets"]) if c[1:2] == ("status",)
                  else (0, ""))
_o13b, _u13b = vang(bi.zet_systeem_toetsenbord, _I("be"), antwoord=lambda c: (0, _lc7["intl"]) if c[1:2] == ("status",)
                    else (0, ""))
_set13 = [c for c in _o13 if c[1:2] == ("set-x11-keymap",)]
_set13b = [c for c in _o13b if c[1:2] == ("set-x11-keymap",)]
klopt(_u13 and _set13 == [("localectl", "set-x11-keymap", "be", "", "", "")]
      and _set13b == [("localectl", "set-x11-keymap", "be", "pc105", "", "terminate:ctrl_alt_bksp")],
      f"13/I13: het inlogscherm: localectl set-x11-keymap; model en opties blijven ({_set13}, {_set13b})")
_stand13 = iter([_lc7["niets"], _lc7["be"]])
_o13c, _u13c = vang(bi.zet_systeem_toetsenbord, _I("be"),
                    antwoord=lambda c: (0, next(_stand13)) if c[1:2] == ("status",) else (1, ""))
klopt(_u13c is True, "I5: localectl gaf het op, maar het inlogscherm heeft het toetsenbord wel: gelukt")
_o13d, _u13d = vang(bi.zet_systeem_toetsenbord, _I("us;x"))
klopt(_u13d is False and not _o13d, "13: een rare indeling gaat niet naar localectl")
# Lezen: kxkbrc (Use=true) of anders het systeem; niet gezet = Engels (VS) (I13).
_kx = {"Use": "true", "LayoutList": "us,be", "VariantList": "intl"}
_o13e, _u13e = vang(bi.toetsenborden, antwoord=lambda c: (0, _kx.get(c[c.index("--key") + 1], "")) if c[0] == "kreadconfig6"
                    else (0, ""))
_o13f, _u13f = vang(bi.toetsenborden, antwoord=lambda c: (0, "false") if c[0] == "kreadconfig6" else (0, _lc7["niets"]))
klopt(_u13e == [_I("us", "intl"), _I("be")] and _u13f == [_I("us")],
      f"13: je toetsenborden uit kxkbrc; nog niets gekozen: dat van het systeem, of Engels (VS) ({_u13e}, {_u13f})")

# ======================================================================== notatie (stap 5) ===

def _sleutels(opdrachten) -> dict:
    """{sleutel: waarde of None (weggehaald)} van elke kwriteconfig6-opdracht op plasma-localerc."""
    uit = {}
    for c in opdrachten:
        if c[0] == "kwriteconfig6" and "plasma-localerc" in c:
            uit[c[c.index("--key") + 1]] = None if c[-1] == "--delete" else c[-1]
    return uit


_o15, _u15 = vang(bi.zet_regio, "nl_BE")
_o15b, _u15b = vang(bi.zet_regio, "xx_YY")
klopt(_u15 is True and _sleutels(_o15) == {"LC_TIME": "nl_BE.UTF-8"}
      and all("Formats" in c for c in _o15 if c[0] == "kwriteconfig6") and _u15b is False and not _o15b,
      f"15/I2: notatie: alleen LC_TIME (geen papier, maten of geld erbij); een onbekende regio: niets ({_sleutels(_o15)})")


def _lang(waarde: str):
    return lambda c: (0, waarde + "\n") if c[0] == "kreadconfig6" and "LANG" in c else (0, "")


_oud_env16 = {k: os.environ.pop(k) for k in ("LANG", "LC_TIME") if k in os.environ}
_o16, _ = vang(bi.zet_taal, "nl", antwoord=_lang("en_US.UTF-8"))
_o16b, _ = vang(bi.zet_taal, "en", antwoord=_lang("en_GB.UTF-8"))
_s16, _s16b = _sleutels(_o16), _sleutels(_o16b)
klopt("LC_TIME" in _s16 and _s16["LC_TIME"] is None and "LC_NUMERIC" in _s16 and _s16["LC_NUMERIC"] is None
      and _s16.get("LANG") == "nl_NL.UTF-8" and not [k for k in _s16b if k.startswith("LC_")],
      f"16: een andere taal zet de notatie terug; Engels terwijl je al Engels had: geen LC_ ({_s16}, {_s16b})")
_r16 = {w: vang(bi.regio, antwoord=a)[1] for w, a in (
    ("lc_time", lambda c: (0, "en_US.UTF-8\n") if "LC_TIME" in c else (0, "nl_NL.UTF-8\n")),
    ("lang", lambda c: (0, "") if "LC_TIME" in c else (0, "de_DE.UTF-8\n")),
    ("c", lambda c: (0, "C.UTF-8\n")))}
os.environ.update(_oud_env16)
klopt(_r16 == {"lc_time": "en_US", "lang": "de_DE", "c": "en_US"},
      f"G: de notatie uit plasma-localerc: LC_TIME, anders LANG; C telt niet: Amerikaans ({_r16})")

# ============================================================ het venster van Instellingen (voorbeeldstand) ===

lader = importlib.machinery.SourceFileLoader("instellingen", str(BIN / "bugos-settings"))
spec = importlib.util.spec_from_loader("instellingen", lader)
mod = importlib.util.module_from_spec(spec)
lader.exec_module(mod)
from PySide6.QtCore import QThreadPool  # noqa: E402
from PySide6.QtWidgets import QLabel, QLineEdit  # noqa: E402

app = mod.maak_app("bugos-settings", "bugos-settings", ["test"])
venster = mod.Instellingen("start")
import bugos_settings_account as sa  # noqa: E402


def wacht() -> None:
    for _ in range(3):
        QThreadPool.globalInstance().waitForDone(5000)
        app.processEvents()


def teksten(w) -> str:
    return " ".join(x.text() for x in w.findChildren(QLabel) if not x.isHidden())


# 30: de klok met de hand via het BugOS-venster.
venster.ga_naar("tijd")
wacht()
tp = venster.paginas["tijd"]
tp.toon((ca.Tijd("Europe/Amsterdam", False, False), "nl"))
_gezet30: list = []


class _NepKlok30:
    def __init__(self, ouder):
        self.wanneer = datetime(2026, 11, 11, 9, 30)


setattr(_NepKlok30, "exec", lambda self: 1)
_oud30 = (sa.KlokDialoog, bi.zet_klok)
sa.KlokDialoog = _NepKlok30
bi.zet_klok = lambda w: (_gezet30.append(w), (True, ""))[1]
_zichtbaar30 = tp.zelf_rij.isVisibleTo(tp)
tp.zelf_rij.geklikt.emit()
wacht()
sa.KlokDialoog, bi.zet_klok = _oud30
klopt(_zichtbaar30 and _gezet30 == [datetime(2026, 11, 11, 9, 30)]
      and "De klok is gezet" in tp.melding.tekst.text(),
      f"30: klok zelf instellen: één keer zet_klok met de gekozen tijd ({_gezet30}, {tp.melding.tekst.text()!r})")
_kd = sa.KlokDialoog(venster)
klopt(_kd.datum.displayFormat().count("y") == 4 and _kd.sizeHint().height() <= 480 and _kd.sizeHint().width() <= 600,
      f"30: het klokvenster: heel jaartal, past op 1280x800 bij 150 % ({_kd.datum.displayFormat()}, {_kd.sizeHint()})")
tp.toon((ca.Tijd("Europe/Amsterdam", True, False), "nl"))
klopt("Wacht op internet" in tp.klok_rij.uitleg.text() and tp.zelf_rij.isHidden(),
      f"F: tijd vanzelf, maar nog niet gelijk: 'wacht op internet' ({tp.klok_rij.uitleg.text()!r})")

_bron_alles = (PY / "bugos_settings_account.py").read_text(encoding="utf-8")
# 25: de kaart Andere mensen (voorbeeldstand).
import bugos_shell  # noqa: E402

venster.ga_naar("inloggen")
wacht()
inl = venster.paginas["inloggen"]
_rijen25 = {r.titel.text(): r.uitleg.text() for r in inl.mensen_rijen}
klopt(set(_rijen25) == {"Werk", "Huiswerk", "Gast"} and "Bugie" not in _rijen25
      and "Standaard" in _rijen25["Huiswerk"] and "Beheerder" in _rijen25["Werk"] and "inlognaam werk" in _rijen25["Werk"]
      and inl.voeg_rij.titel.text() == "Iemand toevoegen" and inl.g3.lay.indexOf(inl.voeg_rij) > 0
      and [r.titel.text() for r in inl.mensen_rijen] == ["Gast", "Huiswerk", "Werk"],
      f"25: Andere mensen: drie mensen op naam (jij niet), soort en inlognaam, onderaan 'Iemand toevoegen' ({_rijen25})")
klopt(inl.alleen_beheerder.isHidden(), "A: een beheerder ziet geen 'alleen met het wachtwoord van een beheerder'")
_gb = bi.Gebruiker("bugie", "Bugie", False, False)
inl.toon((_gb, 15, True))
klopt(not inl.alleen_beheerder.isHidden() and len(inl.mensen_rijen) == 3,
      "A: geen beheerder: de uitleg staat er; een oude aanroep met drie dingen laat de mensen staan")
inl.toon((bi.gebruiker(), 15, True, bi.mensen()))


def _vraag(antwoord: bool):
    """Vervang VraagDialoog.exec: onthoud de vraag en klik 'ja' of 'nee'."""
    gezien: list = []

    def exec_(self):
        gezien.append((self.kop.text(), self.uitleg.text(), self.ja.text(), self.standaard))
        return 1 if antwoord else 0
    return gezien, exec_


# 28: verwijderen via het menu (de vraag: 'Verwijderen', Enter = Annuleren); de laatste beheerder kun je niet weghalen.
_gast28 = next(r.persoon for r in inl.mensen_rijen if r.persoon.naam == "gast")
_gezien28, _exec28 = _vraag(True)
_oud28 = bugos_shell.VraagDialoog.exec
bugos_shell.VraagDialoog.exec = _exec28
next(f for _i, tekst, f in inl.menu_voor(_gast28) if tekst.startswith("Verwijderen"))()
wacht()
bugos_shell.VraagDialoog.exec = _oud28
klopt(len(inl.mensen_rijen) == 2 and "Gast" not in [r.titel.text() for r in inl.mensen_rijen]
      and _gezien28 and _gezien28[0][0] == "Gast verwijderen?" and "USB-stick" in _gezien28[0][1]
      and _gezien28[0][3] == "Annuleren" and "is verwijderd" in inl.melding.tekst.text(),
      f"28: verwijderen vraagt het eerst (Enter = Annuleren) en dan is Gast weg ({_gezien28}, {inl.melding.tekst.text()!r})")
_een_beheerder = [bi.Persoon("bugie", "Bugie", 1000, False, ik=True), bi.Persoon("werk", "Werk", 1501, True)]
inl.vul_mensen(_een_beheerder)
klopt(not any(tekst.startswith("Verwijderen") for _i, tekst, _f in inl.menu_voor(_een_beheerder[1])),
      "28: de laatste beheerder heeft geen 'Verwijderen…' in het menu")
inl.toon((bi.gebruiker(), 15, True, bi.mensen()))
# C: beheerder maken vraagt het eerst; de tekst is gewone tekst (geen opmaak uit een naam: I8).
_huis = next(r.persoon for r in inl.mensen_rijen if r.persoon.naam == "huiswerk")
_gezien_c, _exec_c = _vraag(False)
bugos_shell.VraagDialoog.exec = _exec_c
next(f for _i, tekst, f in inl.menu_voor(_huis) if tekst == "Beheerder maken")()
wacht()
bugos_shell.VraagDialoog.exec = _oud28
klopt(_gezien_c and _gezien_c[0][0] == "Beheerder maken?" and "Huiswerk kan dan apps installeren" in _gezien_c[0][1]
      and "Standaard" in next(r.uitleg.text() for r in inl.mensen_rijen if r.persoon.naam == "huiswerk"),
      f"C: 'Beheerder maken' vraagt het eerst; Annuleren verandert niets ({_gezien_c})")
_gezien_c2, _exec_c2 = _vraag(True)
bugos_shell.VraagDialoog.exec = _exec_c2
next(f for _i, tekst, f in inl.menu_voor(_huis) if tekst == "Beheerder maken")()
wacht()
bugos_shell.VraagDialoog.exec = _oud28
klopt("Beheerder" in next(r.uitleg.text() for r in inl.mensen_rijen if r.persoon.naam == "huiswerk")
      and "is nu beheerder" in inl.melding.tekst.text(), f"C: en met 'ja' is Huiswerk beheerder ({inl.melding.tekst.text()!r})")
_vd = bugos_shell.VraagDialoog(venster, "x", "<h1>Gast</h1>", "Ja")
klopt(_vd.uitleg.textFormat() == bugos_shell.Qt.TextFormat.PlainText, "I8: een naam in een vraag wordt nooit opmaak")
# E / I6: nieuw wachtwoord voor iemand anders: het venster zegt voor wie.
_wv = sa.WachtwoordVoorDialoog(venster, "Huiswerk", beheerder=False)
_wv_tekst = teksten(_wv)
klopt("Nieuw wachtwoord voor Huiswerk" in _wv_tekst and "wachtwoord van een beheerder" in _wv_tekst
      and _wv.windowTitle() == "Nieuw wachtwoord voor Huiswerk" and "huidige wachtwoord" not in _wv_tekst,
      f"I6: het venster zegt van wie het wachtwoord is, en wiens wachtwoord BugOS daarna vraagt ({_wv_tekst!r})")
_ww_e: list = []


class _NepWw:
    def __init__(self, ouder, naam, beheerder=True):
        _ww_e.append(naam)
        self.wachtwoord = "nieuw-geheim"
        self.een = self.twee = QLineEdit()


setattr(_NepWw, "exec", lambda self: 1)
_oud_e = (sa.WachtwoordVoorDialoog, bi.zet_wachtwoord_van)
sa.WachtwoordVoorDialoog = _NepWw
bi.zet_wachtwoord_van = lambda uid, ww: (_ww_e.append((uid, ww)), (True, ""))[1]
next(f for _i, tekst, f in inl.menu_voor(_huis) if tekst.startswith("Nieuw wachtwoord"))()
wacht()
sa.WachtwoordVoorDialoog, bi.zet_wachtwoord_van = _oud_e
klopt(_ww_e == ["Huiswerk", (1502, "nieuw-geheim")] and "Het wachtwoord van Huiswerk is veranderd" in inl.melding.tekst.text(),
      f"E: nieuw wachtwoord voor Huiswerk ({_ww_e}, {inl.melding.tekst.text()!r})")
# De naam wijzigen gaat met de vraag van BugOS (geen QInputDialog meer).
_gezien_n: list = []


def _exec_naam(self):
    _gezien_n.append(self.kop.text())
    self.veld.setText("Bugie Lieveheersbeestje")
    return 1


bugos_shell.VraagDialoog.exec = _exec_naam
inl.wijzig_naam()
wacht()
bugos_shell.VraagDialoog.exec = _oud28
klopt(_gezien_n == ["Je naam"] and inl.ik.titel.text() == "Bugie Lieveheersbeestje" and "QInputDialog" not in _bron_alles,
      f"naam wijzigen met de vraag van BugOS ({_gezien_n}, {inl.ik.titel.text()!r})")
bi._VB["volledige_naam"] = "Bugie"
ca._VB_ACCOUNT["mensen"] = None
inl.ververs()
wacht()

# 26: 'Iemand toevoegen' opent het BugOS-venster en de nieuwe persoon staat meteen in de lijst.
_open26: list = []


class _NepPersoon:
    def __init__(self, ouder, volledig="", inlog=""):
        _open26.append((volledig, inlog))
        self.volledige_naam, self.inlognaam, self.wachtwoord, self.beheerder = "Gast twee", "gast2", "geheim-12", False

    def wis(self):
        self.wachtwoord = ""


setattr(_NepPersoon, "exec", lambda self: 1)
_oud26 = sa.PersoonDialoog
sa.PersoonDialoog = _NepPersoon
_voor26 = len(inl.mensen_rijen)
inl.voeg_rij.geklikt.emit()
wacht()
sa.PersoonDialoog = _oud26
klopt(len(inl.mensen_rijen) == _voor26 + 1 and "Gast twee" in [r.titel.text() for r in inl.mensen_rijen]
      and "Gast twee kan nu inloggen" in inl.melding.tekst.text() and _open26 == [("", "")],
      f"26: toevoegen: het BugOS-venster, daarna staat 'Gast twee' in de lijst ({inl.melding.tekst.text()!r})")
ca._VB_ACCOUNT["mensen"] = None
inl.ververs()
wacht()
# 27: het echte venster.
from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402


def typ(veld, tekst: str) -> None:
    """Typ zoals een mens, letter voor letter (ook é en û: QTest.keyClicks kan alleen ASCII)."""
    for teken in tekst:
        for soort in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            app.sendEvent(veld, QKeyEvent(soort, Qt.Key.Key_unknown, Qt.KeyboardModifier.NoModifier, teken))


_d27 = sa.PersoonDialoog(inl)
_d27.show()
typ(_d27.vol, "Crème Brûlée")
_volgt = _d27.inlog.text()
_d27.een.setText("abc")
_d27.twee.setText("abc")
_kort = (_d27.ok.isEnabled(), _d27.fout.text())
_d27.een.setText("geheim12")
_d27.twee.setText("geheim12")
_goed27 = _d27.ok.isEnabled()
_d27.inlog.clear()
typ(_d27.inlog, "Café")
_klein27 = (_d27.inlog.text(), _d27.fout.text(), _d27.ok.isEnabled())
_d27.inlog.clear()
typ(_d27.inlog, "Huis Werk")
_punt27 = _d27.inlog.text()
typ(_d27.vol, " x")
_blijft27 = _d27.inlog.text()
_d27.inlog.clear()
typ(_d27.inlog, "root")
_root27 = _d27.fout.text()
_maat27 = _d27.sizeHint()
klopt(_volgt == "creme" and not _kort[0] and "te kort" in _kort[1] and _goed27,
      f"27: de inlognaam volgt de naam ('creme'); OK pas met een wachtwoord van 6 tekens ({_volgt!r}, {_kort})")
klopt(_klein27[0] == "café" and "kleine letters" in _klein27[1] and not _klein27[2] and _punt27 == "huis.werk"
      and _blijft27 == "huis.werk" and "bestaat al" in _root27,
      f"27: zelf getypt: kleine letters, spatie wordt punt, volgt de naam dan niet meer; 'root' bestaat al "
      f"({_klein27}, {_punt27!r}, {_blijft27!r}, {_root27!r})")
klopt(_maat27.height() <= 480 and _maat27.width() <= 600,
      f"27: het venster past op 1280x800 bij 150 % ({_maat27.width()}x{_maat27.height()} <= 600x480)")
_d27.soort.knoppen["beheerder"].click()
klopt(_d27.beheerder and _d27.volledige_naam == "Crème Brûlée x", "27: soort account en naam komen goed terug")
_d27.wis()
klopt(_d27.wachtwoord == "", "B: na gebruik zijn de wachtwoordvelden leeg")
_d27.close()
_d27b = sa.PersoonDialoog(inl)
klopt(_d27b.fout.text() == "" and not _d27b.ok.isEnabled(), "B: een nieuw venster begint zonder rode tekst")
_d27b.close()

# 29: de kaart Toetsenbord (voorbeeldstand: VS-Internationaal en Belgisch; het inlogscherm heeft Engels (VS)).
venster.ga_naar("tijd")
tp.ververs()
wacht()
_t29 = [(r.titel.text(), r.uitleg.text()) for r in tp.toetsenbord_rijen]
klopt(len(_t29) == 2 and _t29[0][0].startswith("VS-Internationaal") and "Wordt eerst gebruikt" in _t29[0][1]
      and "accenten" in _t29[0][1] and _t29[1][0] == "Belgisch (AZERTY)"
      and "Windows-toets + spatie" in tp.voeg_toetsenbord.uitleg.text() and "Toetsenbord" in teksten(tp),
      f"29: twee toetsenborden, de eerste wordt eerst gebruikt, wisselen met Windows-toets + spatie ({_t29})")
klopt(tp.inlog_rij is not None and "Engels (VS)" in tp.inlog_rij.uitleg.text(),
      "H: een beheerder ziet dat het inlogscherm een ander toetsenbord heeft")
_m29 = {tekst: f for _i, tekst, f in tp.menu_toetsenbord(tp.toetsenbord_lijst[1])}
_m29a = [tekst for _i, tekst, _f in tp.menu_toetsenbord(tp.toetsenbord_lijst[0])]
klopt(set(_m29) == {"Als eerste gebruiken", "Weghalen"} and _m29a == ["Weghalen"],
      f"H: menu: 'Als eerste gebruiken' (niet bij de eerste) en 'Weghalen' ({list(_m29)}, {_m29a})")
_m29["Als eerste gebruiken"]()
wacht()
klopt([r.titel.text() for r in tp.toetsenbord_rijen][0] == "Belgisch (AZERTY)" and "meteen typen" in tp.melding.tekst.text()
      and tp.inlog_rij is not None, f"H: Belgisch als eerste; meteen typen ({tp.melding.tekst.text()!r})")
tp.inlog_rij.rechts.click()
wacht()
klopt(tp.inlog_rij is None and ca._VB_ACCOUNT["toetsenbord_inlog"] == ("be", "")
      and "inlogscherm gebruikt nu ook" in tp.melding.tekst.text(),
      f"H: 'Ook daar gebruiken': het inlogscherm krijgt Belgisch, de regel gaat weg ({tp.melding.tekst.text()!r})")
next(f for _i, tekst, f in tp.menu_toetsenbord(tp.toetsenbord_lijst[1]) if tekst == "Weghalen")()
wacht()
klopt(len(tp.toetsenbord_rijen) == 1 and tp.toetsenbord_rijen[0].rechts is None
      and "AZERTY" in tp.voeg_toetsenbord.uitleg.text() and "weggehaald" in tp.melding.tekst.text(),
      f"H: één toetsenbord over: geen menu, geen 'wisselen' ({tp.melding.tekst.text()!r})")
# Toevoegen: de bekende bovenaan, wat je al hebt niet; met vier kan er niets meer bij.
_kies29: list = []


class _NepKies29:
    def __init__(self, ouder, titel, items, huidig=None, hint=""):
        _kies29.append((titel, items, hint))
        self.gekozen = next(ind for ind, naam in items if naam.startswith("VS-Internationaal ("))


setattr(_NepKies29, "exec", lambda self: 1)
_oud29 = sa.KiesDialoog
sa.KiesDialoog = _NepKies29
tp.voeg_toetsenbord.geklikt.emit()
wacht()
sa.KiesDialoog = _oud29
_items29 = _kies29[0][1] if _kies29 else []
klopt(_kies29 and _kies29[0][0] == "Welk toetsenbord?" and _items29[0][1] == "Engels (VS)"
      and _I("be") not in [i for i, _n in _items29] and "AZERTY" in _kies29[0][2]
      and [r.titel.text() for r in tp.toetsenbord_rijen][1].startswith("VS-Internationaal"),
      f"H: toevoegen: een zoeklijst, de bekende bovenaan, Belgisch (heb je al) niet ({len(_items29)} keuzes)")
if _echt8.is_file():
    # In het Nederlands als de vertaling van xkb er is (op Ubuntu in de CI niet, in BugOS wel).
    _nl29 = any(v.gettext("Belgian") != "Belgian" for v in ca._xkb_vertalingen())
    _naam29 = "internationaal, met dode toetsen" if _nl29 else "intl., with dead keys"
    klopt(len(_items29) > 100 and all(n for _i, n in _items29) and any(_naam29 in n for _i, n in _items29),
          f"H: ook alle andere toetsenborden van xkb ({len(_items29)}, Nederlands: {_nl29})")
ca._VB_ACCOUNT.update(toetsenborden=[("us", ""), ("be", ""), ("nl", ""), ("de", "")], toetsenbord_inlog=("us", ""))
tp.ververs()
wacht()
klopt(len(tp.toetsenbord_rijen) == 4 and tp.voeg_toetsenbord.property("klikbaar") == "false"
      and "Hooguit 4" in tp.voeg_toetsenbord.uitleg.text(), "H: met vier toetsenborden kan er niets meer bij")
klopt(tp.inlog_rij is None, "H: het inlogscherm heeft al het eerste toetsenbord: geen regel")
ca._VB_ACCOUNT.update(toetsenborden=[("us", "intl"), ("be", "")], toetsenbord_inlog=("us", ""))
_oud29g = bi.gebruiker
bi.gebruiker = lambda: bi.Gebruiker("bugie", "Bugie", False, False)
tp.ververs()
wacht()
bi.gebruiker = _oud29g
klopt(tp.inlog_rij is None, "H: wie geen beheerder is, ziet de regel voor het inlogscherm niet")
_tp_nieuw = sa.TijdPagina(venster)
klopt([r.titel.text() for r in _tp_nieuw.g3.findChildren(sa.Rij)] == ["Even kijken…"],
      "I16: tot de toetsenborden gelezen zijn: 'Even kijken…'")
_tp_nieuw.toon_rest(None)
klopt(len(_tp_nieuw.toetsenbord_rijen) == 1, "I16: niet te lezen: toch een toetsenbord en 'toevoegen', nooit eeuwig wachten")
_tp_nieuw.deleteLater()
tp.ververs()
wacht()

# 10 en G: de notatie op de pagina.
from PySide6.QtCore import QLocale  # noqa: E402

_codes10 = [c for c, _nl, _en in bi.REGIOS]
klopt(len(set(_codes10)) == len(_codes10) and all(QLocale(c).language() != QLocale.Language.C for c in _codes10)
      and all(nl and en for _c, nl, en in bi.REGIOS), "10: elke notatie is uniek en Qt kent hem")
klopt(tp.regio_rij.uitleg.text().startswith("Nederland · ") and "week begint op maandag" in tp.regio_rij.uitleg.text(),
      f"G: Notatie: Nederland, met een voorbeeld en de eerste dag van de week ({tp.regio_rij.uitleg.text()!r})")
klopt("week begint op zondag" in sa.regio_voorbeeld("en_US") and sa.regio_naam("xx_YY"),
      f"G: Verenigde Staten: de week begint op zondag ({sa.regio_voorbeeld('en_US')!r})")
_kies_g: list = []


class _NepKiesG:
    def __init__(self, ouder, titel, items, huidig=None, hint=""):
        _kies_g.append((titel, items, huidig, hint))
        self.gekozen = "en_US"


setattr(_NepKiesG, "exec", lambda self: 1)
sa.KiesDialoog = _NepKiesG
tp.regio_rij.rechts.click()
wacht()
sa.KiesDialoog = _oud29
klopt(_kies_g and _kies_g[0][2] == "nl_NL" and len(_kies_g[0][1]) == len(bi.REGIOS) and "Zoek een land" == _kies_g[0][3]
      and any(n.startswith("Verenigde Staten — ") for _c, n in _kies_g[0][1])
      and tp.regio_rij.uitleg.text().startswith("Verenigde Staten") and "Meld je af" in tp.melding.tekst.text(),
      f"G: een andere notatie kiezen; daarna afmelden ({tp.melding.tekst.text()!r})")
ca._VB_ACCOUNT["regio"] = "nl_NL"
tp.ververs()
wacht()

# 31: geen sprongen naar KDE meer in de pagina's van dit pakket.
_bron = (PY / "bugos_settings_account.py").read_text(encoding="utf-8")
klopt(not hasattr(sa, "kde_instelling") and "kde_instelling(" not in _bron and "kcm_clock" not in _bron
      and 'kcm_users")' not in _bron, "31: Tijd en taal en Inloggen openen geen KDE-onderdeel meer")

QThreadPool.globalInstance().waitForDone(5000)
venster.close()
shutil.rmtree(TMP, ignore_errors=True)
print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
