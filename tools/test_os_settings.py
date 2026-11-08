#!/usr/bin/env python3
"""Test van de OS-fouten in BugOS Instellingen (U001 en verder): schrijven we de juiste dingen weg,
en lezen we de uitvoer goed, ook als de computer een andere taal spreekt?

Er verandert niets aan je computer: de opdrachten worden opgevangen (bi.draai vervangen) of draaien
met nep-programma's in een tijdelijke map.

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_os_settings.py
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
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


# U008: uitvoer lezen we in het Engels, ook als jij Nederlands of Duits hebt (nep-nmcli en nep-lpstat praten
# Nederlands/Duits, net als de echte, tenzij LC_ALL=C.UTF-8; nmcli -t vertaalt nooit).
nep = TMP / "nep-bin"
nep.mkdir()
for naam, tekst in {
    "nmcli": 'if [ "$1" = -t ] || [ "$LC_ALL" = C.UTF-8 ]; then echo enabled; else echo ingeschakeld; fi',
    "lpstat": 'if [ "$LC_ALL" != C.UTF-8 ]; then d=Drucker; i="ist im Leerlauf"; else d=printer; i="is idle"; fi\n'
              'case "$1" in -d) echo "system default destination: HP";; *) printf "%s HP %s.  enabled since Mon\\n" '
              '"$d" "$i";; esac',
    "bluetoothctl": 'echo "Controller AA"; printf "\\tPowered: yes\\n"',
    "bugos-taal": 'echo "${LC_ALL:-leeg}"',
}.items():
    (nep / naam).write_text(f"#!/usr/bin/bash\n{tekst}\n")
    (nep / naam).chmod(0o755)
oud_pad = os.environ["PATH"]
os.environ.update(PATH=f"{nep}:{oud_pad}", LC_ALL="nl_NL.UTF-8", LANGUAGE="nl")
bi.VOORBEELD = False
klopt(bi.wifi_aan(), "U008: Instellingen ziet wifi aan, ook in het Nederlands")
klopt([p.naam for p in bi.printers()] == ["HP"], "U008: printers verschijnen, ook als CUPS Duits praat")
klopt(bi.draai("bugos-taal")[1].strip() == "nl_NL.UTF-8", "U008: onze eigen bugos-hulpjes houden je taal (meldingen)")
bi.VOORBEELD = True
lader = importlib.machinery.SourceFileLoader("startdata", str(BIN / "bugos-start-data"))
spec = importlib.util.spec_from_loader("startdata", lader)
sd = importlib.util.module_from_spec(spec)
lader.exec_module(sd)
klopt(sd.snel_status()["wifi"] is True and sd.tray_status()["wifi"] is True,
      "U008: het snelmenu en het taakbalk-icoontje zien wifi aan, ook in het Nederlands")
klopt(sd.draai("bugos-taal").strip() == "nl_NL.UTF-8", "U008: bugos-start-data laat bugos-hulpjes in je taal")
os.environ["PATH"] = oud_pad
os.environ.pop("LANGUAGE")


# U009: nachtlicht moet KWin het meteen laten weten (--notify), niet pas na opnieuw inloggen.
opdr, _ = vang(bi.zet_nachtlicht, True)
klopt(any(c[0] == "kwriteconfig6" and "--notify" in c and "NightColor" in c and c[-1] == "true" for c in opdr),
      "U009: nachtlicht aan zegt het meteen tegen KWin (--notify)")


# U011: een bekend netwerk met een veranderd wachtwoord: opnieuw vragen, en het opgeslagen netwerk starten met
# --ask (wachtwoord via de invoer, nooit op de opdrachtregel).
oud = (bi.VOORBEELD, bi.draai)
opdr = []
bi.VOORBEELD = False
bi.draai = lambda *cmd, **kw: (opdr.append((cmd, kw.get("invoer"))), (0, ""))[1]
bi.verbind("Thuis", "nieuw-geheim", True)
bi.VOORBEELD, bi.draai = oud
klopt(opdr and opdr[0][0][:6] == ("nmcli", "--ask", "connection", "up", "id", "Thuis")
      and not any("nieuw-geheim" in x for x in opdr[0][0]) and opdr[0][1] == "nieuw-geheim\n",
      "U011: bekend netwerk met nieuw wachtwoord: nmcli --ask connection up, wachtwoord via de invoer")

# Het venster (voorbeeldstand), voor de pagina's hieronder.
lader = importlib.machinery.SourceFileLoader("instellingen", str(BIN / "bugos-settings"))
spec = importlib.util.spec_from_loader("instellingen", lader)
mod = importlib.util.module_from_spec(spec)
sys.modules["instellingen"] = mod
lader.exec_module(mod)
from PySide6.QtCore import QThreadPool  # noqa: E402

app = mod.maak_app("bugos-settings", "bugos-settings", ["test"])
venster = mod.Instellingen("start")


def wacht() -> None:
    for _ in range(5):
        QThreadPool.globalInstance().waitForDone(5000)
        app.processEvents()


venster.ga_naar("wifi")
wacht()
wifi = venster.paginas["wifi"]
pogingen: list = []
gevraagd: list = []
oud_verbind = bi.verbind
bi.verbind = lambda naam, ww="", bekend=False: (pogingen.append((naam, ww, bekend)), (len(pogingen) > 1, ""))[1]
wifi.vraag_wachtwoord = lambda n, veranderd=False: (gevraagd.append(veranderd), "nieuw-geheim")[1]
wifi.verbind_met(bi.Netwerk("Home", 86, True, False), True)
wacht()
bi.verbind = oud_verbind
klopt(pogingen == [("Home", "", True), ("Home", "nieuw-geheim", True)] and gevraagd == [True],
      "U011: lukt een bekend netwerk niet, dan vraagt Instellingen het (nieuwe) wachtwoord en probeert opnieuw")


venster.close()
shutil.rmtree(TMP, ignore_errors=True)
print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
