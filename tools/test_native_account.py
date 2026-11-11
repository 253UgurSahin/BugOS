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
from PySide6.QtTest import QTest  # noqa: E402

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
_d27 = sa.PersoonDialoog(inl)
_d27.show()
QTest.keyClicks(_d27.vol, "Crème Brûlée")
_volgt = _d27.inlog.text()
_d27.een.setText("abc")
_d27.twee.setText("abc")
_kort = (_d27.ok.isEnabled(), _d27.fout.text())
_d27.een.setText("geheim12")
_d27.twee.setText("geheim12")
_goed27 = _d27.ok.isEnabled()
_d27.inlog.clear()
QTest.keyClicks(_d27.inlog, "Café")
_klein27 = (_d27.inlog.text(), _d27.fout.text(), _d27.ok.isEnabled())
_d27.inlog.clear()
QTest.keyClicks(_d27.inlog, "Huis Werk")
_punt27 = _d27.inlog.text()
QTest.keyClicks(_d27.vol, " x")
_blijft27 = _d27.inlog.text()
_d27.inlog.clear()
QTest.keyClicks(_d27.inlog, "root")
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
