#!/usr/bin/env python3
"""Test van de OS-fouten in BugOS Instellingen (U001 en verder): schrijven we de juiste dingen weg,
en lezen we de uitvoer goed, ook als de computer een andere taal spreekt?

Er verandert niets aan je computer: de opdrachten worden opgevangen (bi.draai vervangen) of draaien
met nep-programma's in een tijdelijke map.

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_os_settings.py
"""

from __future__ import annotations

import os
import pwd
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"
BIN = ROOT / "system_files" / "usr" / "bin"
sys.path.insert(0, str(PY))
TMP = Path(tempfile.mkdtemp(prefix="bugos-os-settings-test-"))
os.environ.update(BUGOS_INSTELLINGEN_VOORBEELD="1", LC_ALL="nl_NL.UTF-8", HOME=str(TMP), BUGOS_SYS=str(TMP / "sys"))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.dont_write_bytecode = True

import bugos_config as bi  # noqa: E402

fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


def vang(functie, *args, antwoord=lambda cmd: (0, "")):
    """Roep functie aan zonder voorbeeldstand, en geef de opdrachten die ze wilde draaien."""
    oud = (bi.VOORBEELD, bi.draai, shutil.which)
    opdrachten: list = []
    bi.VOORBEELD = False
    bi.draai = lambda *cmd, **kw: (opdrachten.append(cmd), antwoord(cmd))[1]
    shutil.which = lambda naam, *a, **k: "/usr/bin/" + naam
    try:
        uit = functie(*args)
    finally:
        bi.VOORBEELD, bi.draai, shutil.which = oud
    return opdrachten, uit


def kde_sleutels(opdrachten) -> dict:
    """{(groep/groep, sleutel): waarde} uit de kwriteconfig6-opdrachten."""
    uit = {}
    for c in opdrachten:
        if c[0] != "kwriteconfig6":
            continue
        groepen = [c[i + 1] for i, x in enumerate(c) if x == "--group"]
        sleutel = c[c.index("--key") + 1]
        uit[("/".join(groepen), sleutel)] = c[-1]
    return uit


# U001: scherm uit 'Nooit' moet ook echt nooit zijn (TurnOffDisplayWhenIdle=false), en niet meteen dimmen.
opdr, _ = vang(bi.zet_scherm_uit_na, 0)
s = kde_sleutels(opdr)
klopt(all(s.get((f"{p}/Display", "TurnOffDisplayWhenIdle")) == "false" for p in bi.PROFIELGROEPEN)
      and all(s.get((f"{p}/Display", "DimDisplayWhenIdle")) == "false" for p in bi.PROFIELGROEPEN),
      "U001: scherm uit 'nooit' zet uitzetten en dimmen echt uit")
opdr, _ = vang(bi.zet_scherm_uit_na, 600)
s = kde_sleutels(opdr)
klopt(s.get(("AC/Display", "TurnOffDisplayWhenIdle")) == "true" and s.get(("AC/Display", "DimDisplayWhenIdle")) == "true"
      and s.get(("AC/Display", "TurnOffDisplayIdleTimeoutSec")) == "600",
      "U001: scherm uit na 10 minuten zet het weer aan")
_, na = vang(bi.scherm_uit_na, antwoord=lambda c: (0, "false" if "TurnOffDisplayWhenIdle" in c else "30"))
klopt(na == 0, "U001: staat uitzetten uit, dan leest Instellingen 'nooit'")
_, na = vang(bi.scherm_uit_na, antwoord=lambda c: (0, "true" if "TurnOffDisplayWhenIdle" in c else "300"))
klopt(na == 300, "U001: staat uitzetten aan, dan de tijd")


# U002: inloggen zonder wachtwoord op Fedora 44 (Plasma Login); SDDM alleen als Plasma Login er niet is.
def login_hulpje(wortel: Path) -> Path:
    """bugos-login, maar met /etc en /usr/lib/plasmalogin in een tijdelijke map, en 'id -u' zegt 0 (beheerder)."""
    (wortel / "bin").mkdir(parents=True, exist_ok=True)
    tekst = (BIN / "bugos-login").read_text(encoding="utf-8")
    tekst = tekst.replace("/usr/lib/plasmalogin", f"{wortel}/usr/lib/plasmalogin").replace("/etc/", f"{wortel}/etc/")
    (wortel / "login").write_text(tekst, encoding="utf-8")
    nep_id = wortel / "bin" / "id"
    nep_id.write_text('#!/usr/bin/bash\nif [ "$1" = -u ]; then echo 0; else exec /usr/bin/id "$@"; fi\n')
    nep_id.chmod(0o755)
    return wortel / "login"


def login(wortel: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(wortel / "login"), *args], capture_output=True, text=True,
                          env={**os.environ, "PATH": f"{wortel}/bin:{os.environ['PATH']}"})


ik = pwd.getpwuid(os.getuid()).pw_name
wortel = TMP / "login-pl"
login_hulpje(wortel)
(wortel / "usr" / "lib" / "plasmalogin").mkdir(parents=True)
r = login(wortel, "aan", ik)
pl = wortel / "etc" / "plasmalogin.conf.d" / "50-bugos-login.conf"
klopt(r.returncode == 0 and pl.is_file() and f"User={ik}" in pl.read_text() and "[Autologin]" in pl.read_text()
      and not (wortel / "etc" / "sddm.conf.d").exists(),
      "U002: met Plasma Login komt 'zonder wachtwoord' in /etc/plasmalogin.conf.d")
klopt(login(wortel, "status", ik).stdout.strip() == "aan", "U002: status leest Plasma Login")
r = login(wortel, "uit", ik)
klopt(r.returncode == 0 and not pl.exists() and login(wortel, "status", ik).stdout.strip() == "uit",
      "U002: weer uit haalt het bestand weg")
wortel = TMP / "login-sddm"
login_hulpje(wortel)
r = login(wortel, "aan", ik)
klopt(r.returncode == 0 and (wortel / "etc" / "sddm.conf.d" / "50-bugos-login.conf").is_file()
      and login(wortel, "status", ik).stdout.strip() == "aan", "U002: zonder Plasma Login nog steeds via SDDM")
# Een geldige inlognaam met een punt (jan.jansen) mag; rare namen niet. Of hij bestaat checkt 'id'.
regel = next(r for r in (BIN / "bugos-login").read_text().splitlines() if "=~" in r)
patroon = re.search(r"\^\S*\$", regel).group(0)
klopt(re.fullmatch(patroon, "jan.jansen") and re.fullmatch(patroon, "bugie")
      and not re.fullmatch(patroon, "-root") and not re.fullmatch(patroon, ".x") and not re.fullmatch(patroon, "a b")
      and not re.fullmatch(patroon, "a;rm"), "U002: inlognaam jan.jansen mag, rare namen niet")
klopt(login(TMP / "login-sddm", "status", "bestaat.niet.echt").returncode == 2, "U002: een naam die niet bestaat: nee")
# Instellingen leest wat het inlogscherm echt gebruikt.
import bugos_config_account as acc  # noqa: E402
oud = (acc.PLASMALOGIN, acc.PLASMALOGIN_BESTANDEN, acc.SDDM_BESTANDEN, bi.VOORBEELD)
wortel = TMP / "login-lees"
(wortel / "etc" / "plasmalogin.conf.d").mkdir(parents=True)
(wortel / "etc" / "sddm.conf.d").mkdir(parents=True)
(wortel / "etc" / "plasmalogin.conf.d" / "50-bugos-login.conf").write_text(f"[Autologin]\nUser={ik}\nSession=plasma\n")
acc.PLASMALOGIN = str(wortel / "usr" / "lib" / "plasmalogin")
acc.PLASMALOGIN_BESTANDEN = (str(wortel / "etc" / "plasmalogin.conf"), str(wortel / "etc" / "plasmalogin.conf.d"))
acc.SDDM_BESTANDEN = (str(wortel / "etc" / "sddm.conf"), str(wortel / "etc" / "sddm.conf.d"))
bi.VOORBEELD = False
zonder_pl = bi.gebruiker().auto_inloggen
Path(acc.PLASMALOGIN).mkdir(parents=True)
met_pl = bi.gebruiker().auto_inloggen
acc.PLASMALOGIN, acc.PLASMALOGIN_BESTANDEN, acc.SDDM_BESTANDEN, bi.VOORBEELD = oud
klopt(met_pl and not zonder_pl, "U002: Instellingen leest Plasma Login als dat er is (en anders SDDM)")


shutil.rmtree(TMP, ignore_errors=True)
print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
