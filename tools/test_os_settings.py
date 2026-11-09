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
import time
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
opdr, na = vang(bi.scherm_uit_na, antwoord=lambda c: (0, "true" if "WhenIdle" in c else "0"))
s = kde_sleutels(opdr)
klopt(na == 0 and s.get(("AC/Display", "TurnOffDisplayWhenIdle")) == "false",
      "U001: 'nooit' van een oudere BugOS (tijd 0, uitzetten nog aan) wordt bij het lezen goed gezet")

# U336: licht/donker zegt of het lukte (niet altijd 'Klaar'). U338: een wifi-netwerk vergeten. U335: een eigen
# achtergrondfoto wordt gekopieerd (van een stick verdween hij anders).
_, _ok = vang(bi.zet_donker, True, antwoord=lambda c: (1, ""))
opdr, _ = vang(bi.vergeet_netwerk, "Thuis wifi")
klopt(_ok is False and ("nmcli", "connection", "delete", "id", "Thuis wifi") in opdr,
      f"U336/U338: mislukt licht/donker zegt 'mislukt'; 'Vergeten' gooit het opgeslagen netwerk weg ({opdr})")
def _nm(c):
    if c[-1] == "show" and "UUID,TYPE" in c:
        return 0, "1234-abcd:802-11-wireless\n5678-ef01:802-11-wireless\n9999-0000:802-11-wireless\nkabel-1:802-3-ethernet\n"
    if "802-11-wireless.ssid" in c:
        return 0, {"1234-abcd": "Thuis", "5678-ef01": "Thuis", "9999-0000": "Thuis Ouders"}[c[-1]] + "\n"
    return 0, ""


# U366: een netwerknaam met ':' (nmcli schrijft 'Cafe\:Gast') wordt ook gevonden.
opdr2, _ = vang(bi.vergeet_netwerk, "Cafe:Gast", antwoord=lambda c: (0, "aaaa:802-11-wireless\n") if (c[-1] == "show" and "UUID,TYPE" in c)
                 else ((0, "Cafe\\:Gast\n") if "802-11-wireless.ssid" in c else (0, "")))
klopt(("nmcli", "connection", "delete", "uuid", "aaaa") in opdr2,
      f"U366: 'Vergeten' vindt ook een netwerk met een ':' in de naam ({opdr2[-1:]})")
opdr, _ = vang(bi.vergeet_netwerk, "Thuis", antwoord=_nm)
_weg = [c[-1] for c in opdr if c[:3] == ("nmcli", "connection", "delete")]
klopt(_weg == ["1234-abcd", "5678-ef01"],
      f"U345/U357: 'Vergeten' gooit elk profiel van dit netwerk weg ('Thuis' en 'Thuis 1'), niet 'Thuis Ouders' ({_weg})")
_stick = Path(tempfile.mkdtemp(prefix="bugos-stick-"))
(_stick / "vakantie.jpg").write_bytes(b"jpg")
_oud_data = os.environ.get("XDG_DATA_HOME")
_data = Path(tempfile.mkdtemp(prefix="bugos-data-"))
os.environ["XDG_DATA_HOME"] = str(_data)
opdr, _ = vang(bi.zet_achtergrond, str(_stick / "vakantie.jpg"))
_eigen = _data / "wallpapers" / "bugos-eigen"
_kopie = next(iter(sorted(_eigen.glob("vakantie*.jpg"))), None)
klopt(_kopie is not None and any(c[0] == "plasma-apply-wallpaperimage" and c[1] == str(_kopie) for c in opdr),
      f"U335: een eigen foto (van een stick) wordt eerst gekopieerd, zodat de achtergrond blijft ({opdr})")
# U343: een andere foto met dezelfde naam krijgt een nieuwe plek (anders ziet Plasma geen verandering); de oude gaat weg.
(_stick / "ander").mkdir()
(_stick / "ander" / "vakantie.jpg").write_bytes(b"andere foto")
import time as _tm  # noqa: E402
_tm.sleep(1.1)
opdr2, _ = vang(bi.zet_achtergrond, str(_stick / "ander" / "vakantie.jpg"))
_nu = sorted(_eigen.iterdir())
klopt(len(_nu) == 1 and opdr2 and opdr2[-1][1] == str(_nu[0]) and str(_nu[0]) != str(_kopie),
      f"U343: een andere foto met dezelfde naam wordt echt de nieuwe achtergrond ({[p.name for p in _nu]})")
# U356: de huidige eigen foto via een andere weg (een symlink, zoals /home -> /var/home) nog eens kiezen: hij blijft.
_echt = Path(tempfile.mkdtemp(prefix="bugos-echt-"))
(_echt / "wallpapers" / "bugos-eigen").mkdir(parents=True)
(_echt / "wallpapers" / "bugos-eigen" / "nu-1.jpg").write_bytes(b"jpg")
_link = Path(tempfile.mkdtemp(prefix="bugos-link-")) / "data"
_link.symlink_to(_echt)
os.environ["XDG_DATA_HOME"] = str(_echt)
vang(bi.zet_achtergrond, str(_link / "wallpapers" / "bugos-eigen" / "nu-1.jpg"))
klopt((_echt / "wallpapers" / "bugos-eigen" / "nu-1.jpg").exists(),
      "U356: de huidige eigen foto via een andere weg nog eens kiezen gooit hem niet weg")
if _oud_data is None:
    os.environ.pop("XDG_DATA_HOME", None)
else:
    os.environ["XDG_DATA_HOME"] = _oud_data

# U235: een laptop op de accu: Instellingen toont de accu-tijden (KDE: 5 min scherm uit), niet die van de lader.
_sys235 = Path(tempfile.mkdtemp(prefix="bugos-sys-"))
(_sys235 / "class" / "power_supply" / "BAT0").mkdir(parents=True)
for _b, _w in (("type", "Battery"), ("capacity", "60"), ("status", "Discharging")):
    (_sys235 / "class" / "power_supply" / "BAT0" / _b).write_text(_w + "\n")
_oud_sys = os.environ.get("BUGOS_SYS")
os.environ["BUGOS_SYS"] = str(_sys235)
opdr, na = vang(bi.scherm_uit_na, antwoord=lambda c: (0, "true" if "WhenIdle" in c else c[-1]))
if _oud_sys is None:
    os.environ.pop("BUGOS_SYS", None)
else:
    os.environ["BUGOS_SYS"] = _oud_sys
klopt(na == 300 and any("Battery" in c for c in opdr),
      f"U235: op de accu toont Instellingen de accu-tijd (KDE: 5 minuten), niet die van de lader ({na})")
# U399: twee batterijen (ThinkPad), stekker eruit: BAT0 'Not charging', BAT1 'Discharging': op de accu, samen geteld.
_sys399 = Path(tempfile.mkdtemp(prefix="bugos-sys-"))
for _n, _w in (("AC", {"type": "Mains", "online": "0"}),
               ("BAT0", {"type": "Battery", "capacity": "90", "status": "Not charging", "energy_now": "18000000", "energy_full": "20000000"}),
               ("BAT1", {"type": "Battery", "capacity": "40", "status": "Discharging", "energy_now": "8000000", "energy_full": "20000000"})):
    (_sys399 / "class" / "power_supply" / _n).mkdir(parents=True)
    for _k, _v in _w.items():
        (_sys399 / "class" / "power_supply" / _n / _k).write_text(_v + "\n")
_oud399 = os.environ.get("BUGOS_SYS")
os.environ["BUGOS_SYS"] = str(_sys399)
_vb, bi.VOORBEELD = bi.VOORBEELD, False
_b399, _p399 = bi.batterij(), __import__("bugos_config_scherm")._profiel()
bi.VOORBEELD = _vb
if _oud399 is None:
    os.environ.pop("BUGOS_SYS", None)
else:
    os.environ["BUGOS_SYS"] = _oud399
klopt(_b399 is not None and _b399.procent == 65 and not _b399.aan_lader and _p399 == "Battery",
      f"U399: twee batterijen zonder lader: 65% samen, 'op de accu', accu-tijden ({_b399}, {_p399})")
# U405: alleen via USB-C geladen (type USB online), de oude AC-ingang offline, laadgrens 80% ('Not charging'): aan de lader.
_sys404 = Path(tempfile.mkdtemp(prefix="bugos-sys-"))
for _n, _w in (("AC", {"type": "Mains", "online": "0"}), ("ucsi-source-psy-USBC000:001", {"type": "USB", "online": "1"}),
               ("BAT0", {"type": "Battery", "capacity": "80", "status": "Not charging"})):
    (_sys404 / "class" / "power_supply" / _n).mkdir(parents=True)
    for _k, _v in _w.items():
        (_sys404 / "class" / "power_supply" / _n / _k).write_text(_v + "\n")
_oud404 = os.environ.get("BUGOS_SYS")
os.environ["BUGOS_SYS"] = str(_sys404)
_vb, bi.VOORBEELD = bi.VOORBEELD, False
_b404, _p404 = bi.batterij(), __import__("bugos_config_scherm")._profiel()
bi.VOORBEELD = _vb
if _oud404 is None:
    os.environ.pop("BUGOS_SYS", None)
else:
    os.environ["BUGOS_SYS"] = _oud404
klopt(_b404 is not None and _b404.aan_lader and _p404 == "AC",
      f"U405: laden via USB-C telt als 'aan de lader' ({_b404}, {_p404})")
# U243: met de lader erin (de accu zegt 'Unknown' door een laadgrens) gelden de tijden van de lader; en 10 min slapen
# (KDE op de accu) staat als keuze in Instellingen.
(_sys235 / "class" / "power_supply" / "BAT0" / "status").write_text("Unknown\n")
(_sys235 / "class" / "power_supply" / "AC").mkdir()
(_sys235 / "class" / "power_supply" / "AC" / "type").write_text("Mains\n")
(_sys235 / "class" / "power_supply" / "AC" / "online").write_text("1\n")
os.environ["BUGOS_SYS"] = str(_sys235)
_pr = bi._profiel() if hasattr(bi, "_profiel") else __import__("bugos_config_scherm")._profiel()
if _oud_sys is None:
    os.environ.pop("BUGOS_SYS", None)
else:
    os.environ["BUGOS_SYS"] = _oud_sys
klopt(_pr == "AC" and 600 in bi.SLAAP_KEUZES,
      f"U243: lader erin (accu 'Unknown'): de tijden van de lader; en 10 min slapen is een keuze ({_pr})")


# U061: Instellingen vraagt bluetoothctl niets op een computer zonder bluetooth (geen 5 s wachten per vraag).
_sys = Path(tempfile.mkdtemp(prefix="bugos-sys-"))
os.environ["BUGOS_SYS"] = str(_sys)
opdr, aan = vang(bi.bt_aan)
opdr2, lijst = vang(bi.bt_apparaten)
klopt(aan is False and lijst == [] and not any("bluetoothctl" in c[0] for c in opdr + opdr2),
      "U061: geen bluetooth-hardware: bluetooth 'uit', geen apparaten, en bluetoothctl niet gevraagd")
(_sys / "class" / "bluetooth" / "hci0").mkdir(parents=True)
opdr, _ = vang(bi.bt_aan, antwoord=lambda c: (0, "Controller 00:11 X\n\tPowered: yes\n"))
klopt(any(c[0] == "bluetoothctl" for c in opdr), "U061: met bluetooth-hardware wordt bluetoothctl wel gevraagd")
del os.environ["BUGOS_SYS"]


# U063: de namen van de achtergronden staan ook in het Engels (en niet altijd "Stip (licht)").
import bugos_config_scherm as _bcs  # noqa: E402
_bron = (ROOT / "system_files" / "usr" / "lib" / "bugos" / "python" / "bugos_config_scherm.py").read_text(encoding="utf-8")
klopt('t("Stip (licht)", "Dot (light)")' in _bron and 't("Stip (donker)", "Dot (dark)")' in _bron,
      "U063: de achtergrondnamen worden vertaald (Dot (light) / Dot (dark))")
os.environ["BUGOS_ACHTERGRONDEN"] = str(ROOT / "system_files/usr/share/wallpapers/bugos/contents")
_lijst = bi.bugos_achtergronden()
del os.environ["BUGOS_ACHTERGRONDEN"]
klopt(_lijst and Path(_lijst[0][1]).is_dir() and (Path(_lijst[0][1]) / "metadata.json").exists() and len(_lijst) == 3,
      f"U131: eerst de BugOS-achtergrond die meewisselt met licht en donker (het hele pakket) ({[n for n, _p in _lijst]})")


# U002: inloggen zonder wachtwoord op Fedora 44 (Plasma Login); SDDM alleen als Plasma Login er niet is.
def login_hulpje(wortel: Path) -> Path:
    """bugos-login, maar met /etc en /usr/lib/plasmalogin in een tijdelijke map, en 'id -u' zegt 0 (beheerder)."""
    (wortel / "bin").mkdir(parents=True, exist_ok=True)
    tekst = (BIN / "bugos-login").read_text(encoding="utf-8")
    tekst = tekst.replace("/usr/lib/plasmalogin", f"{wortel}/usr/lib/plasmalogin").replace("/etc/", f"{wortel}/etc/")
    (wortel / "login").write_text(tekst, encoding="utf-8")
    nep_id = wortel / "bin" / "id"
    # 'id -u' (wie ben ik): 0; 'id -u <naam>' (de gebruiker die vanzelf inlogt): een gewone gebruiker (U247)
    nep_id.write_text('#!/usr/bin/bash\nif [ "$1" = -u ] && [ -z "${2:-}" ]; then echo 0; '
                      'elif [ "$1" = -u ]; then echo 1000; else exec /usr/bin/id "$@"; fi\n')
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
    "nmcli": 'case "$*" in *TYPE*device*) echo wifi; exit;; esac\n'
             'if [ "$1" = -t ] || [ "$LC_ALL" = C.UTF-8 ]; then echo enabled; else echo ingeschakeld; fi',
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


# U006: 'Nu updaten' en 'Terug' zeggen hoe het ging; Annuleren bij het wachtwoord zet de schakelaar terug.
# Nep-pkexec doet wat in het bestand 'code' staat; nep-bugos-updates zegt 'auto'.
nep_pk = TMP / "nep-pk"
nep_pk.mkdir()
(nep_pk / "pkexec").write_text(f'#!/usr/bin/bash\necho "$2" >>"{nep_pk}/gedaan"\necho "uitvoer van $2"\n'
                               f'exit "$(cat "{nep_pk}/code")"\n')
(nep_pk / "bugos-updates").write_text("#!/usr/bin/bash\necho auto\n")
for f in ("pkexec", "bugos-updates"):
    (nep_pk / f).chmod(0o755)
# U093: op de USB-stick om te proberen geen updateknoppen (die werken daar niet), wel de rest van de pagina.
import bugos_settings_systeem as _sys  # noqa: E402
from PySide6.QtWidgets import QLabel, QPushButton  # noqa: E402

(TMP / "cmdline").write_text("BOOT_IMAGE=/images/pxeboot/vmlinuz root=live:CDLABEL=BugOS rd.live.image quiet\n")
os.environ["BUGOS_CMDLINE"] = str(TMP / "cmdline")
_live = _sys.UpdatesPagina(venster)
del os.environ["BUGOS_CMDLINE"]
_knoppen = [k.text() for k in _live.findChildren(QPushButton)]
klopt(_live.auto is None and "Nu updaten" not in _knoppen and "Update now" not in _knoppen
      and any(r for r in _live.findChildren(QLabel) if "USB-stick" in r.text() or "USB stick" in r.text())
      and len(_live.findChildren(_sys.QWidget)) > 20,
      "U093: live-USB: Updates zegt dat het daar niet kan, zonder knoppen; de rest van de pagina staat er wel")
_live.deleteLater()
venster.ga_naar("updates")
wacht()
upd = venster.paginas["updates"]


def update_proef(wat: str, code: int) -> str:
    (nep_pk / "code").write_text(str(code))
    upd.melding.hide()
    upd.updates(wat)
    for _ in range(200):
        app.processEvents()
        time.sleep(0.02)
        if upd.nu.isEnabled() and not upd.melding.isHidden():
            break
    return upd.melding.tekst.text()


# (LC_ALL=C.UTF-8: in deze testomgeving bestaat nl_NL niet, en dan klaagt bash op stderr; de taal van
# Instellingen zelf ligt al vast.)
os.environ.update(PATH=f"{nep_pk}:{oud_pad}", LC_ALL="C.UTF-8")
bi.VOORBEELD = False
mislukt = update_proef("nu", 1)
gelukt = update_proef("nu", 0)
herstart_knop = upd.melding.knop.isVisibleTo(upd.melding)
terug_tekst = update_proef("terug", 0)   # nep-pkexec zegt "uitvoer van terug": dat moet Instellingen tonen
geen_vorige = update_proef("terug", 3)   # bugos-updates: er is nog geen vorige versie
(nep_pk / "pkexec").write_text(f'#!/usr/bin/bash\necho "$2" >>"{nep_pk}/gedaan"\necho bugos-update-klaar\n'
                               f'exit "$(cat "{nep_pk}/code")"\n')
al_klaar = update_proef("nu", 0)
(nep_pk / "pkexec").write_text(f'#!/usr/bin/bash\necho "$2" >>"{nep_pk}/gedaan"\necho "uitvoer van $2"\n'
                               f'exit "$(cat "{nep_pk}/code")"\n')
geannuleerd = update_proef("terug", 126)
upd.auto.setChecked(False)        # jij zet 'Updates vanzelf' uit, en klikt dan Annuleren bij het wachtwoord
for _ in range(200):
    app.processEvents()
    QThreadPool.globalInstance().waitForDone(20)
    time.sleep(0.02)
    if upd.auto.isChecked():
        break
# Instellingen sluiten terwijl een update loopt: niet stoppen, wachten en daarna vanzelf dicht.
# ("nu" duurt even; een schakelaar die tussendoor klaar is, mag de update niet als klaar laten tellen.)
(nep_pk / "pkexec").write_text(f'#!/usr/bin/bash\n[ "$2" = nu ] && sleep 2\necho "$2" >>"{nep_pk}/gedaan"\nexit 0\n')
(nep_pk / "code").write_text("0")
(nep_pk / "notify-send").write_text(f'#!/usr/bin/bash\necho "$*" >"{nep_pk}/melding"\n')
(nep_pk / "notify-send").chmod(0o755)
venster.show()
upd.updates("nu")
upd.updates("auto")
for _ in range(50):
    app.processEvents()
    time.sleep(0.02)
klopt(upd.bezig, "U006: een schakelaar die klaar is terwijl 'Nu updaten' loopt, laat de update niet als klaar tellen")
venster.close()
bleef_open = venster.isVisible() and upd.bezig
for _ in range(300):
    app.processEvents()
    time.sleep(0.02)
    if not venster.isVisible():
        break
dicht_na_afloop = not venster.isVisible() and not upd.bezig
# ... en mislukt de update, dan blijft Instellingen open met de foutmelding (niet stil dicht).
(nep_pk / "pkexec").write_text(f'#!/usr/bin/bash\nsleep 1\necho "$2" >>"{nep_pk}/gedaan"\nexit 1\n')
venster.show()
venster.sluit_na_update = False
upd.updates("nu")
app.processEvents()
venster.close()
for _ in range(300):
    app.processEvents()
    time.sleep(0.02)
    if not upd.bezig:
        break
for _ in range(10):
    app.processEvents()
open_na_fout = venster.isVisible() and "lukte niet" in upd.melding.tekst.text()
venster.close()
bi.VOORBEELD = True
os.environ.update(PATH=oud_pad, LC_ALL="nl_NL.UTF-8")
klopt(bleef_open, "U006: Instellingen sluiten tijdens 'Nu updaten': het venster blijft open, de update loopt door")
klopt(dicht_na_afloop, "U006: daarna gaat Instellingen vanzelf dicht")
klopt(open_na_fout, "U046: mislukt de update nadat je Instellingen sloot, dan blijft het open met de foutmelding")
klopt((nep_pk / "melding").exists() and "opnieuw op" in (nep_pk / "melding").read_text(),
      "U046: gaat Instellingen vanzelf dicht na de update, dan zie je de uitkomst als melding (opnieuw opstarten)")
# U017 (instelbaar): onder Game-modus staat de keuze "FPS-teller meteen klaar".
from PySide6.QtWidgets import QLabel  # noqa: E402
_teksten = [w.text() for w in upd.findChildren(QLabel)]
klopt(any("FPS" in x and ("meteen" in x or "at once" in x) for x in _teksten),
      "U017: Instellingen heeft de keuze 'FPS-teller meteen klaar'")
klopt("lukte niet" in mislukt, "U006: 'Nu updaten' mislukt: dat zegt Instellingen ook")
klopt("opnieuw op" in gelukt and herstart_knop, "U006: 'Nu updaten' gelukt: klaar, met een knop om opnieuw op te starten")
klopt("toestemming" in geannuleerd, "U006: Annuleren bij het wachtwoord: niets gedaan")
klopt(geen_vorige == "uitvoer van terug" and "online" not in geen_vorige,
      "U041: 'Terug' zonder vorige versie: Instellingen zegt wat bugos-updates zegt, niet 'Ben je online?'")
klopt("klaar" in al_klaar and "opnieuw op" in al_klaar,
      "U041: 'Nu updaten' terwijl er al een update klaarstaat: zegt 'staat al klaar, start opnieuw op'")
klopt(terug_tekst == "uitvoer van terug", "U033: na 'Terug' toont Instellingen wat bugos-updates zegt (bijv. dat updates nu uit staan)")
klopt(upd.auto.isChecked() and (nep_pk / "gedaan").read_text().split()[:7] == ["nu", "nu", "terug", "terug", "nu", "terug", "hand"],
      "U006: Annuleren bij 'Updates vanzelf' uit: de schakelaar springt terug")


# U065: de grote aanwijzer altijd in kcminputrc schrijven (plasma-apply-cursortheme negeert --size als het
# thema al het huidige is) en KDE laten weten dat de aanwijzer veranderd is.
opd, _ = vang(bi.zet_grote_aanwijzer, True)
klopt(kde_sleutels(opd).get(("Mouse", "cursorSize")) == "48" and not any(c[0] == "plasma-apply-cursortheme" for c in opd)
      and any(c[0] == "gdbus" and "org.kde.KGlobalSettings.notifyChange" in c and c[-2:] == ("5", "0") for c in opd),
      "U065: grote aanwijzer: cursorSize=48 geschreven en KDE verteld dat de aanwijzer veranderde")
opd, _ = vang(bi.zet_grote_aanwijzer, False)
klopt(kde_sleutels(opd).get(("Mouse", "cursorSize")) == "24", "U065: grote aanwijzer uit: terug naar 24")

# U066: de schermlezer via de kded-module van Plasma 6.8 (kaccess start Orca niet meer).
opd, _ = vang(bi.zet_toetshulp, "schermlezer", True)
klopt(any(c[0] == "gdbus" and "/modules/screenreader" in c and c[-2:] == ("org.kde.screenreader.setEnabled", "true")
          for c in opd) and not kde_sleutels(opd), "U066: schermlezer aan via org.kde.kded6 /modules/screenreader")
_, aan = vang(bi.toetshulp, "schermlezer", antwoord=lambda c: (0, "(true,)\n") if c[0] == "gdbus" else (0, "false"))
_, uit = vang(bi.toetshulp, "schermlezer", antwoord=lambda c: (0, "(false,)\n") if c[0] == "gdbus" else (0, "true"))
klopt(aan is True and uit is False, "U066: de schermlezer-schakelaar leest de kded-module, niet kaccessrc")
opd, _ = vang(bi.zet_toetshulp, "schermlezer", True, antwoord=lambda c: (1, "") if c[0] == "gdbus" else (0, ""))
klopt(kde_sleutels(opd).get(("ScreenReader", "Enabled")) == "true", "U066: zonder de kded-module: zoals vroeger via kaccessrc")
opd, _ = vang(bi.zet_toetshulp, "plaktoetsen", True)
klopt(kde_sleutels(opd).get(("Keyboard", "StickyKeys")) == "true" and not any(c[0] == "gdbus" for c in opd),
      "U066: plaktoetsen blijven via kaccessrc")

# U069: in het Engels zoeken vindt de gewone instellingen ook (en elk woord los, in welke taal dan ook).
from PySide6.QtWidgets import QWidget  # noqa: E402
_start = venster.paginas["start"]
_mist = []
for _w in ["night light", "night", "sleep", "screen reader", "sticky keys", "do not disturb", "version", "mute", "font", "scale", "game mode", "left-handed", "lid", "screen off", "about", "magnifier", "lock screen"]:
    _start.zoek(_w)
    _rijen = [r for r in _start.zoek_kaart.findChildren(QWidget) if hasattr(r, "titel")]
    if not _rijen or any(r.titel.text() in ("Niks gevonden", "Nothing found") for r in _rijen):
        _mist.append(_w)
_start.zoek("")
klopt(not _mist, f"U069: Engelse zoekwoorden in Instellingen vinden iets (niet: {_mist})")

# U109-U111: wifi: een verborgen netwerk (wachtwoord via de invoer), en een computer zonder wifi.
opd, _ = vang(bi.verbind, "Thuis", "geheim123", False, True)
klopt(opd and opd[0][:6] == ("nmcli", "--ask", "device", "wifi", "connect", "Thuis") and "hidden" in opd[0]
      and "geheim123" not in opd[0], f"U109: verborgen netwerk: nmcli ... hidden yes, het wachtwoord niet op de opdrachtregel ({opd[:1]})")
_, geen = vang(bi.heeft_wifi, antwoord=lambda c: (0, "ethernet\nloopback\n"))
_, wel = vang(bi.heeft_wifi, antwoord=lambda c: (0, "wifi\nethernet\n"))
klopt(geen is False and wel is True, "U111: Instellingen ziet of de computer wifi heeft")
venster.ga_naar("wifi")
wacht()
_wp = venster.paginas["wifi"]
_wp.toon((True, [], False, False))
klopt(_wp.lijst.isHidden() and _wp.schakel.isHidden() and "geen wifi" in _wp.hoofd.uitleg.text().lower()
      if hasattr(_wp.hoofd, "uitleg") else _wp.lijst.isHidden(),
      "U111: Wifi-pagina zonder wifi in de computer: 'Deze computer heeft geen wifi', geen schakelaar of lijst")
_wp.toon((True, [], False, True))
klopt(not _wp.lijst.isHidden() and not _wp.ander.isHidden(), "U109: met wifi: de lijst en 'Ander netwerk…' staan er")
_oud_verbind = bi.verbind
bi.verbind = lambda *a, **k: (False, "")
_wp.verbind_met(bi.Netwerk("Bibliotheek", 50, False, False), bekend=True)
wacht()
wacht()
bi.verbind = _oud_verbind
klopt("wachtwoord" not in _wp.melding.tekst.text().lower() and "password" not in _wp.melding.tekst.text().lower(),
      f"U110: een open netwerk dat niet lukt vraagt niet naar een wachtwoord ({_wp.melding.tekst.text()})")

# U114: 'Eigen foto kiezen' begint in de echte map Afbeeldingen (uit user-dirs.dirs), niet altijd ~/Pictures.
import bugos_settings_scherm as _scherm  # noqa: E402

_xdg = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
_xdg.mkdir(parents=True, exist_ok=True)
_echte = Path.home() / "Mijn Fotos"
_echte.mkdir(exist_ok=True)
_oud_dirs = (_xdg / "user-dirs.dirs").read_text() if (_xdg / "user-dirs.dirs").exists() else None
(_xdg / "user-dirs.dirs").write_text('XDG_PICTURES_DIR="$HOME/Mijn Fotos"\n')
_gevraagd: list = []
_oud_dlg = _scherm.QFileDialog.getOpenFileName
_scherm.QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (_gevraagd.append(a[2]), ("", ""))[1])
venster.ga_naar("uiterlijk")
wacht()
venster.paginas["uiterlijk"].kies_foto()
_scherm.QFileDialog.getOpenFileName = _oud_dlg
if _oud_dirs is None:
    (_xdg / "user-dirs.dirs").unlink()
else:
    (_xdg / "user-dirs.dirs").write_text(_oud_dirs)
klopt(_gevraagd == [str(_echte)], f"U114: 'Eigen foto kiezen' begint in de map Afbeeldingen van de gebruiker ({_gevraagd})")

# U126: Updates en meer: een schakelaar gaat op slot tijdens het omzetten en leest daarna wat er echt staat
# (lukt het niet, bijv. offline, dan springt hij terug).
_nep_ls = TMP / "nep-lichte-stand"
_nep_ls.mkdir()
(_nep_ls / "bugos-light-mode").write_text("#!/usr/bin/bash\n[ \"$1\" = status ] && { echo uit; exit 0; }\nsleep 0.3; exit 1\n")
(_nep_ls / "bugos-light-mode").chmod(0o755)
_oud_path = os.environ["PATH"]
os.environ["PATH"] = f"{_nep_ls}:{_oud_path}"
bi.VOORBEELD = False
_up = _sys.UpdatesPagina(venster)
_sch = _up.schakels[("bugos-light-mode", ())]
_sch.setChecked(True)
_op_slot = not _sch.isEnabled()
for _ in range(60):
    wacht()
    if _sch.isEnabled():
        break
    time.sleep(0.1)
bi.VOORBEELD = True
os.environ["PATH"] = _oud_path
klopt(_op_slot and _sch.isEnabled() and not _sch.isChecked(),
      "U126: lichte stand aanzetten lukt niet: de schakelaar was op slot en springt daarna terug naar uit")
_up.deleteLater()

# U133/U136: past een pagina niet (smal venster, grote letters), dan kun je opzij schuiven; de zijbalk groeit mee.
import bugos_shell as _shell  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402

venster.resize(920, 600)
venster.ga_naar("scherm")
wacht()
_pag = venster.paginas["scherm"]
_hb = _pag.horizontalScrollBar()
_past = _pag.widget().minimumSizeHint().width() <= _pag.viewport().width()
klopt(_pag.horizontalScrollBarPolicy() != Qt.ScrollBarPolicy.ScrollBarAlwaysOff and (_past or _hb.maximum() > 0),
      f"U133: Scherm op 920 breed: alles past, of je kunt opzij schuiven (max {_hb.maximum()})")
_oud_s = _shell.bugos_ui.SCHAAL
_shell.bugos_ui.SCHAAL = 1.2
_v2 = _shell.Venster("x")
_shell.bugos_ui.SCHAAL = _oud_s
klopt(_v2.zij.width() == round(_shell.ZIJBALK_BREEDTE * 1.2) or _v2.zij.minimumWidth() == round(_shell.ZIJBALK_BREEDTE * 1.2),
      "U136: met grote letters is de zijbalk breder (de namen passen)")
_v2.deleteLater()
venster.resize(1120, 760)

# U155: aan de lader maar laadt niet (laadgrens 80%), en een batterij die niet 'BAT0' heet.
_ps = TMP / "sys-u155" / "class" / "power_supply" / "axp288_fuel_gauge"
_ps.mkdir(parents=True)
for _k, _v in (("type", "Battery"), ("capacity", "80"), ("status", "Not charging")):
    (_ps / _k).write_text(_v + "\n")
_muis = _ps.parent / "hid-muis-battery"
_muis.mkdir()
for _k, _v in (("type", "Battery"), ("scope", "Device"), ("capacity", "10"), ("status", "Discharging")):
    (_muis / _k).write_text(_v + "\n")
os.environ["BUGOS_SYS"] = str(TMP / "sys-u155")
bi.VOORBEELD = False
_bat = bi.batterij()
bi.VOORBEELD = True
del os.environ["BUGOS_SYS"]
klopt(_bat is not None and _bat.procent == 80 and _bat.aan_lader and not _bat.laadt,
      f"U155: batterij met een andere naam, aan de lader maar niet laden (niet de batterij van de muis) ({_bat})")
# U157: zonder bluetooth in de computer: geen tegel en geen schakelaar die niets doen, en niet 8 s wachten.
_oud_hw = bi.bt_hardware
bi.bt_hardware = lambda: False
_opd, _gelukt = vang(bi.zet_bt, True)
bi.bt_hardware = _oud_hw
klopt(_gelukt is False and not any(c[0] == "bluetoothctl" for c in _opd), "U157: geen bluetooth: niet aan bluetoothctl vragen")
venster.ga_naar("bluetooth")
wacht()
_btp = venster.paginas["bluetooth"]
_btp.toon((False, [], False))
klopt(_btp.schakel.isHidden() and _btp.nieuw.isHidden(), "U157: Bluetooth-pagina zonder bluetooth: 'heeft geen bluetooth', geen knoppen")
_btp.toon((False, [], True))
# U165: met de vliegtuigstand uit (hci0 weg, de rfkill-schakelaar niet): wel bluetooth, en weer aan te zetten.
_rf = TMP / "sys-u165"
(_rf / "class" / "rfkill" / "rfkill0").mkdir(parents=True)
(_rf / "class" / "rfkill" / "rfkill0" / "type").write_text("bluetooth\n")
(_rf / "class" / "rfkill" / "rfkill0" / "soft").write_text("1\n")
(_rf / "class" / "bluetooth").mkdir(parents=True)
os.environ["BUGOS_SYS"] = str(_rf)
_heeft = bi.bt_hardware()
_opd, _ = vang(bi.zet_bt, True)
del os.environ["BUGOS_SYS"]
klopt(_heeft and any(c[:2] == ("rfkill", "unblock") for c in _opd),
      "U165: bluetooth uit met de vliegtuigstand: Instellingen ziet bluetooth en zet hem weer aan (rfkill unblock)")
(_rf / "class" / "rfkill" / "rfkill0" / "soft").write_text("0\n")
os.environ["BUGOS_SYS"] = str(_rf)
_spook = bi.bt_hardware()
del os.environ["BUGOS_SYS"]
klopt(not _spook, "U188: een bluetooth-schakelaar die niet uit staat en geen kaart: geen bluetooth (geen nep-tegel)")
# U156: een energieprofiel dat niet lukt: de pagina leest opnieuw wat echt aan staat.
venster.ga_naar("energie")
wacht()
_ep = venster.paginas["energie"]
_gelezen: list = []
_ep.ververs = lambda: _gelezen.append(1)
_oud_ez = bi.zet_energieprofiel
bi.zet_energieprofiel = lambda p: False
_ep.zet_profiel("performance")
wacht()
wacht()
bi.zet_energieprofiel = _oud_ez
del _ep.ververs
klopt(_gelezen, "U156: energieprofiel lukt niet: de keuze springt terug naar wat echt aan staat")
# U158: de wachtrij telt alleen je eigen documenten, en leegmaken vraagt CUPS alleen om die (cancel -u jij).
import getpass as _gp  # noqa: E402

_ik = _gp.getuser()
_, _aantal = vang(bi.wachtrij, antwoord=lambda c: (0, f"HP-12 {_ik} 1024 Mon\nHP-13 iemand 2048 Mon\n"))
_opd, _ = vang(bi.wachtrij_leegmaken)
klopt(_aantal == 1 and _opd and _opd[-1] == ("cancel", "-u", _ik),
      f"U158: wachtrij: alleen je eigen documenten tellen en weghalen ({_aantal}, {_opd[-1:]})")
# U159: een scanprogramma uit de Winkel (Flatpak) wordt gevonden.
_, _scan = vang(bi.scanprogramma, antwoord=lambda c: (0, "") if c[:3] == ("flatpak", "info", "org.kde.skanpage") else (1, ""))
_which = shutil.which
shutil.which = lambda n, *a, **k: "/usr/bin/flatpak" if n == "flatpak" else None
bi.VOORBEELD, _oud_d = False, bi.draai
bi.draai = lambda *c, **k: (0, "") if c[:3] == ("flatpak", "info", "org.kde.skanpage") else (1, "")
_scan = bi.scanprogramma()
bi.VOORBEELD, bi.draai, shutil.which = True, _oud_d, _which
klopt(_scan == "flatpak:org.kde.skanpage", f"U159: Skanpage uit de Winkel (Flatpak) telt als scanprogramma ({_scan})")

# U010: wie geen beheerder is, verandert zijn eigen wachtwoord via passwd (PAM), in een nep-terminal;
# geen wachtwoord op de opdrachtregel, en geen vraag om het wachtwoord van een beheerder.
nep_pw = TMP / "nep-pw"
nep_pw.mkdir()
(nep_pw / "passwd").write_text(f"""#!/usr/bin/bash
[ -t 0 ] || {{ echo "geen terminal"; exit 3; }}
echo "$*" >"{nep_pw}/argv"
echo "Changing password for user jan."
printf "Current password: "; read -r a
printf "New password: "; read -r b
if [ "${{#b}}" -lt 8 ]; then echo "BAD PASSWORD: The password is shorter than 8 characters"
    printf "New password: "; read -r b; exit 1; fi
printf "Retype new password: "; read -r c
[ "$a" = "oud-geheim" ] || {{ echo "passwd: Authentication token manipulation error"; exit 1; }}
[ "$b" = "$c" ] || exit 1
echo "$b" >"{nep_pw}/nieuw"
echo "passwd: all authentication tokens updated successfully."
""")
(nep_pw / "passwd").chmod(0o755)
os.environ.update(PATH=f"{nep_pw}:{oud_pad}", LC_ALL="C.UTF-8")
bi.VOORBEELD = False
goed = bi.zet_eigen_wachtwoord("oud-geheim", "nieuw-geheim-123", timeout=10)
fout_oud = bi.zet_eigen_wachtwoord("verkeerd", "nieuw-geheim-123", timeout=10)
simpel = bi.zet_eigen_wachtwoord("oud-geheim", "kort", timeout=10)
bi.VOORBEELD = True
os.environ.update(PATH=oud_pad, LC_ALL="nl_NL.UTF-8")
klopt(goed == (True, "") and (nep_pw / "nieuw").read_text().strip() == "nieuw-geheim-123"
      and (nep_pw / "argv").read_text().strip() == "",
      "U010: eigen wachtwoord via passwd in een nep-terminal (niets op de opdrachtregel)")
klopt(fout_oud == (False, "fout"), "U010: verkeerd huidig wachtwoord: lukt niet")
klopt(simpel == (False, "simpel"), "U010: te makkelijk wachtwoord: dat zeggen we (en we blijven niet hangen)")
w = mod.WachtwoordDialoog(venster, huidig=True)
w.een.setText("nieuw-geheim")
w.twee.setText("nieuw-geheim")
zonder = w.ok.isEnabled()
w.nu.setText("oud-geheim")
klopt(not zonder and w.ok.isEnabled() and w.huidig_wachtwoord == "oud-geheim",
      "U010: wie geen beheerder is, typt ook zijn huidige wachtwoord in het venster")
import bugos_settings_account as sa  # noqa: E402
import bugos_settings_onderdelen as mod_onderdelen  # noqa: E402
venster.ga_naar("inloggen")
wacht()
inl = venster.paginas["inloggen"]
aanroepen: list = []


class NepDialoog:
    def __init__(self, ouder, huidig=False):
        aanroepen.append(("dialoog", huidig))
        self.wachtwoord, self.huidig_wachtwoord = "nieuw-geheim", "oud-geheim" if huidig else ""


# Zoals QDialog: het venster "uitvoeren" geeft 1 (OK). (Met setattr, zodat de codecheck dit niet voor
# het uitvoeren van tekst als code aanziet: dat gebeurt hier niet.)
setattr(NepDialoog, "exec", lambda self: 1)


oud_dlg, oud_eigen, oud_ww = sa.WachtwoordDialoog, bi.zet_eigen_wachtwoord, bi.zet_wachtwoord
sa.WachtwoordDialoog = NepDialoog
bi.zet_eigen_wachtwoord = lambda h, n: (aanroepen.append(("passwd", h, n)), (True, ""))[1]
bi.zet_wachtwoord = lambda n: (aanroepen.append(("accounts", n)), (True, ""))[1]
inl.gebruiker = bi.Gebruiker("jan", "Jan", False, False)
inl.wijzig_wachtwoord()
wacht()
inl.gebruiker = bi.Gebruiker("bugie", "Bugie", True, False)
inl.wijzig_wachtwoord()
wacht()
sa.WachtwoordDialoog, bi.zet_eigen_wachtwoord, bi.zet_wachtwoord = oud_dlg, oud_eigen, oud_ww
klopt(aanroepen == [("dialoog", True), ("passwd", "oud-geheim", "nieuw-geheim"), ("dialoog", False),
                    ("accounts", "nieuw-geheim")],
      "U010: geen beheerder: via passwd; beheerder: zoals eerst via AccountsService")


# U070: lukt "tijd vanzelf" of de schermgrootte niet (bijv. Annuleren bij het wachtwoord), dan opnieuw lezen,
# zodat het schuifje en de keuze terugspringen naar wat echt is ingesteld.
# U068: na een andere tijdzone time.tzset(), anders toont Instellingen de klok nog in de oude tijdzone.
for naam in ("tijd", "scherm"):
    venster.ga_naar(naam)
    wacht()
tp, sp = venster.paginas["tijd"], venster.paginas["scherm"]
gelezen: list = []
oud_auto, oud_schaal, oud_zone = bi.zet_tijd_auto, bi.zet_schaal, bi.zet_tijdzone
oud_kies, oud_tzset = sa.KiesDialoog, time.tzset
tp.ververs, sp.ververs = (lambda: gelezen.append("tijd")), (lambda: gelezen.append("scherm"))
bi.zet_tijd_auto, bi.zet_schaal = (lambda aan: False), (lambda w: False)
tp.zet_auto(True)
_ss = sys.modules["bugos_settings_scherm"]
_oud_gg = _ss.groot_genoeg
_ss.groot_genoeg = lambda: 2.0   # een groot scherm: dan mag 150% (zie U397)
sp.zet_grootte(1.5)
_ss.groot_genoeg = _oud_gg
wacht()
wacht()
klopt("tijd" in gelezen and "scherm" in gelezen, f"U070: mislukt: tijd en schermgrootte worden opnieuw gelezen ({gelezen})")


class NepKies:
    def __init__(self, *a, **k):
        self.gekozen = "Europe/London"


setattr(NepKies, "exec", lambda self: 1)
tz: list = []
sa.KiesDialoog, time.tzset = NepKies, (lambda: tz.append(1))
bi.zet_tijdzone = lambda z: True
tp.kies_zone_uit(("Europe/Amsterdam", ["Europe/Amsterdam", "Europe/London"]))
wacht()
wacht()
klopt(tz == [1], "U068: na een gelukte nieuwe tijdzone leest Instellingen de tijdzone opnieuw (time.tzset)")
bi.zet_tijd_auto, bi.zet_schaal, bi.zet_tijdzone = oud_auto, oud_schaal, oud_zone
sa.KiesDialoog, time.tzset = oud_kies, oud_tzset
del tp.ververs, sp.ververs


# U025: het snelmenu start Instellingen via bugos-start-data --start instelling:<pagina> (los van Plasma).
qml = (ROOT / "system_files/usr/share/plasma/plasmoids/org.bugos.quickmenu/contents/ui/main.qml").read_text()
open_regels = qml[qml.index("onOpen:"):]
klopt('"bugos-start-data --start " + root.aanhalen("instelling:" + pagina)' in open_regels
      and 'voerUit(wat === "instellingen" ? "bugos-settings"' not in qml,
      "U025: het snelmenu opent Instellingen via bugos-start-data (los, en elke klik werkt)")
gestart: list = []
oud_los = sd.los_starten
sd.los_starten = lambda *cmd: (gestart.append(cmd), True)[1]
sd.start("instelling:")
sd.start("instelling:wifi")
sd.los_starten = oud_los
klopt(gestart == [("bugos-settings",), ("bugos-settings", "wifi")],
      "U025: instelling: opent de startpagina, instelling:wifi de wifi-pagina")


# U026: een bluetooth-apparaat dat niet verbonden is, kun je ook vergeten ('…'-menu op elke regel).
venster.ga_naar("bluetooth")
wacht()
bt = venster.paginas["bluetooth"]
bt.toon((True, [bi.Apparaat("AA:BB:CC:DD:EE:02", "Oude koptelefoon", "audio-headset", False, None)]))
rijen = [r for r in bt.lijst.findChildren(mod.Rij) if r.titel.text() == "Oude koptelefoon"]
klopt(len(rijen) == 1 and rijen[0].rechts is not None, "U026: een apparaat dat niet verbonden is, heeft ook een '…'-menu")
vergeten: list = []
oud_menu, oud_vergeet = mod_onderdelen.menu_bij, bi.bt_vergeet
mod_onderdelen.menu_bij = lambda knop, items: [f() for _ic, tekst, f in items if tekst == "Vergeten"]
bi.bt_vergeet = lambda adres: vergeten.append(adres)
if rijen:
    rijen[0].rechts.click()
wacht()
mod_onderdelen.menu_bij, bi.bt_vergeet = oud_menu, oud_vergeet
klopt(vergeten == ["AA:BB:CC:DD:EE:02"], "U026: 'Vergeten' werkt ook als het apparaat niet verbonden is")


# U022: het start- en snelmenu volgen de taal die je in KDE koos (LANGUAGE), behalve bij C/POSIX.
def start_data_taal(**env) -> str:
    oud_env = dict(os.environ)
    for k in ("LC_ALL", "LC_MESSAGES", "LANG", "LANGUAGE"):
        os.environ.pop(k, None)
    os.environ.update(env)
    try:
        return sd._taal()
    finally:
        os.environ.clear()
        os.environ.update(oud_env)


klopt(start_data_taal(LANG="en_US.UTF-8", LANGUAGE="nl:en_US") == "nl"
      and start_data_taal(LC_ALL="en_US.UTF-8", LANGUAGE="de") == "de"
      and start_data_taal(LANG="nl_NL.UTF-8") == "nl"
      and start_data_taal(LANG="C.UTF-8", LANGUAGE="nl") != "nl"
      and start_data_taal(LC_ALL="POSIX", LANGUAGE="nl") != "nl",
      "U022: bugos-start-data: de eerste taal uit LANGUAGE wint, behalve bij C/POSIX")


# U027: de live-stick in twee talen: eerst Engels, dan Nederlands (opstartmenu en de vensters bij installeren).
iso_yaml = (ROOT / "iso_live/src/iso.yaml").read_text(encoding="utf-8")
namen = re.findall(r'name: "([^"]*)"', iso_yaml)
klopt(len(namen) == 2 and all(" / " in n for n in namen) and namen[0].startswith("Try or install BugOS")
      and "proberen of installeren" in namen[0] and "veilige stand" in namen[1] and "safe mode" in namen[1],
      "U027: opstartmenu van de stick: Engels / Nederlands")
iso_bouw = (ROOT / "iso_live/src/build.sh").read_text(encoding="utf-8")
teksten = re.findall(r'--text(?:-info)?[^"]*?--text="([^"]*)"|--text="([^"]*)"', iso_bouw)
teksten = [a or b for a, b in teksten]
paren = (("Installing BugOS did not work", "is niet gelukt"), ("One more step", "Nog één stap"),
         ("could not be added", "kon niet worden toegevoegd"))
klopt(len(teksten) == 3 and all(0 <= x.find(en) < x.find(nl) for x, (en, nl) in zip(teksten, paren)),
      "U027: de vensters bij het installeren: eerst Engels, dan Nederlands")
klopt("mokutil --timeout -1" in iso_bouw and "Press a key" in iso_bouw and "Druk op een toets" in iso_bouw
      and "'Something is not working' after the restart" not in iso_bouw,
      "U289: Nvidia en Secure Boot: het blauwe scherm wacht op je, de uitleg zegt 'druk op een toets', geen dood spoor naar Hulp")


venster.close()
# U227: na een KDE-venster (koptelefoon koppelen, printer toevoegen) terug in Instellingen: opnieuw kijken.
from PySide6.QtCore import QEvent as _QE  # noqa: E402

venster.ga_naar("printers")
wacht()
_pr = venster.paginas["printers"]
_tel = []
_pr.ververs = lambda: _tel.append(1)
_actief = [False]
venster.isActiveWindow = lambda: _actief[0]
app.sendEvent(venster, _QE(_QE.Type.ActivationChange))   # weg: het KDE-venster heeft de aandacht
_actief[0] = True
app.sendEvent(venster, _QE(_QE.Type.ActivationChange))   # terug
app.sendEvent(venster, _QE(_QE.Type.ActivationChange))   # nog eens actief, zonder weg te zijn geweest
klopt(_tel == [1], f"U227: terug in Instellingen na een KDE-venster: de printers worden opnieuw bekeken ({_tel})")
del _pr.ververs
del venster.isActiveWindow

# U368: 'Terug naar de vorige versie' vraagt het eerst, en zegt dat wachtwoord, nieuwe gebruikers en wifi ook teruggaan.
from PySide6.QtWidgets import QMessageBox as _QMB2  # noqa: E402

_up = venster.paginas["updates"]
_teksten, _gestart, _std = [], [], []
_oud_exec, _oud_up = _QMB2.exec, _up.updates
_QMB2.exec = lambda self: (_teksten.append(self.informativeText()), _std.append(self.defaultButton().text() if self.defaultButton() else ""))[0] or 0   # 'Annuleren'
_up.updates = lambda wat: _gestart.append(wat)
_up.vraag_terug()
_QMB2.exec, _up.updates = _oud_exec, _oud_up
klopt(_teksten and "wachtwoord" in _teksten[0] and "wifi" in _teksten[0] and not _gestart,
      f"U368: 'terug' waarschuwt eerst dat wachtwoord, gebruikers en wifi ook teruggaan; Annuleren doet niets ({_gestart})")
klopt(_std == ["Annuleren"], f"U380: in de vraag 'terug' doet Enter uit gewoonte niets (Annuleren is de standaard) ({_std})")

# U374: 'Grote letters' uit zet terug wat er stond (eigen grootte en menulettertype), niet altijd 10 punten.
_cfg = Path(tempfile.mkdtemp(prefix="bugos-cfg-"))
_oud_cfg = os.environ.get("XDG_CONFIG_HOME")
os.environ["XDG_CONFIG_HOME"] = str(_cfg)
_eigen = {"font": "Inter,11,-1,5,400,0,0,0,0,0,0,0,0,0,0,1", "menuFont": "Noto Sans,12,-1,5,400,0,0,0,0,0,0,0,0,0,0,1"}
vang(bi.zet_grote_tekst, True, antwoord=lambda c: (0, next((v for k, v in _eigen.items() if c[c.index("--key") + 1] == k), "")) if "--key" in c else (0, ""))
opdr, _ = vang(bi.zet_grote_tekst, False)
if _oud_cfg is None:
    os.environ.pop("XDG_CONFIG_HOME", None)
else:
    os.environ["XDG_CONFIG_HOME"] = _oud_cfg
_terug = kde_sleutels(opdr)
klopt(_terug.get(("General", "font")) == _eigen["font"] and _terug.get(("General", "menuFont")) == _eigen["menuFont"],
      f"U374: 'Grote letters' uit zet je eigen lettertypes terug ({_terug.get(('General', 'menuFont'))})")

# U383: een oude momentopname van de lettertypes wordt vernieuwd als 'Grote letters' weer aangaat.
_cfg2 = Path(tempfile.mkdtemp(prefix="bugos-cfg-"))
(_cfg2 / "bugos").mkdir()
(_cfg2 / "bugos" / "grote-letters-voor.json").write_text('{"General/menuFont": "Oud,9,-1,5,400,0,0,0,0,0,0,0,0,0,0,1"}')
_oud_cfg2 = os.environ.get("XDG_CONFIG_HOME")
os.environ["XDG_CONFIG_HOME"] = str(_cfg2)
vang(bi.zet_grote_tekst, True, antwoord=lambda c: (0, "Nieuw,10,-1,5,400,0,0,0,0,0,0,0,0,0,0,1") if "--key" in c else (0, ""))
_snap = (_cfg2 / "bugos" / "grote-letters-voor.json").read_text()
if _oud_cfg2 is None:
    os.environ.pop("XDG_CONFIG_HOME", None)
else:
    os.environ["XDG_CONFIG_HOME"] = _oud_cfg2
klopt("Oud" not in _snap and "Nieuw" in _snap, f"U383: 'Grote letters' aan maakt een nieuwe momentopname (geen oude) ({_snap[:60]})")

# U393: 'terug' terwijl je de oude versie al draait: de melding zegt dat hij blijft (en niet de merktekst).
_up.klaar_met("terug", 0, "Klaar. Deze versie blijft nu ook na opnieuw opstarten.\nbugos-blijft\n")
klopt(_up.melding.tekst.text() == "Klaar. Deze versie blijft nu ook na opnieuw opstarten.",
      f"U393: na 'terug' op de oude versie: 'deze versie blijft' ({_up.melding.tekst.text()!r})")
# U389: 'Nu updaten' terwijl er al een update loopt: zeg dat, niet 'ben je online?'.
_up.klaar_met("nu", 1, "error: Transaction in progress: (null)\n")
klopt("al een update" in _up.melding.tekst.text(), f"U389: er loopt al een update: dat wordt gezegd ({_up.melding.tekst.text()!r})")
# U422: 'hand' lukte niet omdat bewaren mislukte: Instellingen toont wat bugos-updates zegt.
_t422 = sys.modules["bugos_settings_systeem"].t
_up.klaar_met("hand", 1, _t422("Dat lukte niet: de keuze kon niet bewaard worden (is je computer vol?).",
                               "That did not work: the choice could not be saved (is your computer full?).") + "\n")
klopt("could not be saved" in _up.melding.tekst.text() or "kon niet bewaard" in _up.melding.tekst.text(),
      f"U422: updatekeuze niet bewaard: Instellingen zegt waarom ({_up.melding.tekst.text()!r})")
_up.klaar_met("nu", 1, "error: Writing objects: No space left on device\n")
klopt("vol" in _up.melding.tekst.text() and "online" not in _up.melding.tekst.text(),
      f"U411: updaten met een volle computer: dat wordt gezegd ({_up.melding.tekst.text()!r})")

# U445: de klok in het Engels volgt je regio: 2:05 PM in de VS, 9 November met 24 uur in Ierland.
_uit445 = {}
for _l445 in ("en_US.UTF-8", "en_IE.UTF-8", "de_DE.UTF-8"):
    _uit445[_l445] = __import__("subprocess").run(
        [sys.executable, "-c", "import sys; sys.path.insert(0, sys.argv[1]); from datetime import datetime; "
         "import bugos_settings_account as a; print(a._engels_nu(datetime(2026, 11, 9, 14, 5)))",
         str(ROOT / "system_files/usr/lib/bugos/python")],
        capture_output=True, text=True, env=dict(os.environ, LANG=_l445, LC_ALL=_l445), timeout=60).stdout.strip()
klopt("2:05" in _uit445["en_US.UTF-8"] and "PM" in _uit445["en_US.UTF-8"] and "9 November" in _uit445["en_IE.UTF-8"]
      and "14:05" in _uit445["en_IE.UTF-8"], f"U445: de klok in het Engels volgt je regio ({_uit445})")
klopt("November 2026" in _uit445["de_DE.UTF-8"] and "9." in _uit445["de_DE.UTF-8"],
      f"U452: in het Duits de datum zoals Duitsers hem schrijven ({_uit445['de_DE.UTF-8']!r})")
# U397: op een klein scherm (hier 800×600) worden groottes waarbij niets meer past, niet aangeboden.
_sp2 = venster.paginas["scherm"]
_sp2.toon((None, False, 1.0))
_aan = {w: k.isEnabled() for w, k in _sp2.grootte.knoppen.items()}
klopt(_aan[1.0] and not _aan[2.0] and not _aan[1.5], f"U397: op een klein scherm geen 150-200% (dan past niets meer) ({_aan})")
# U407: een grootte kiezen vraagt de huidige schaal niet opnieuw (kscreen-doctor, tot 8 s): het venster blijft vlot.
_oud407 = sys.modules["bugos_settings_scherm"].bi.schaal
_gevraagd407 = []
sys.modules["bugos_settings_scherm"].bi.schaal = lambda: (_gevraagd407.append(1), 1.0)[1]
_sp2.zet_grootte(2.0)
sys.modules["bugos_settings_scherm"].bi.schaal = _oud407
klopt(not _gevraagd407 and "te groot" in _sp2.melding.tekst.text(),
      f"U407: een grootte kiezen wacht niet op kscreen-doctor ({len(_gevraagd407)} keer gevraagd)")

# U353: zoeken in Instellingen vindt ook woorden die op de pagina's staan (taakbalk, fps, opslag, dubbelklikken…).
_mist = []
for _w in ("taakbalk", "dubbelklikken", "fps", "opslag", "schijfruimte", "computernaam", "lettergrootte", "tekstgrootte",
           "vergroten", "standaardapps"):
    venster.paginas["start"].zoek(_w)
    _lay = venster.paginas["start"].zoek_kaart.lay
    _rijen = [_lay.itemAt(i).widget() for i in range(_lay.count())]
    _rijen = [w for w in _rijen if isinstance(w, mod.Rij) and w.titel.text() not in ("Niks gevonden", "Nothing found")]
    if not _rijen:
        _mist.append(_w)
venster.paginas["start"].zoek("")
klopt(not _mist, f"U353: zoeken in Instellingen vindt ook woorden van de pagina's zelf (niet: {_mist})")
# U350: muis/touchpad: lukt het omzetten niet, dan springt de schakelaar terug (Instellingen kijkt opnieuw).
_mp = venster.paginas["muis"]
_ververst = []
_oud_v, _oud_z = _mp.ververs, bi.zet_aanwijzer
_mp.ververs = lambda: _ververst.append(1)
bi.zet_aanwijzer = lambda *a: False
_mp.zet(bi.Aanwijzer("touchpad", "Touchpad", True, True, False, False, 50, True, {"tikken"}), "tikken", True)
wacht()
_mp.ververs, bi.zet_aanwijzer = _oud_v, _oud_z
klopt(_ververst == [1], f"U350: lukt een muis- of touchpadinstelling niet, dan staat de schakelaar weer zoals het echt is ({_ververst})")

shutil.rmtree(TMP, ignore_errors=True)
print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
