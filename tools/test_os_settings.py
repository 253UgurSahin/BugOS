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


# U006: 'Nu updaten' en 'Terug' zeggen hoe het ging; Annuleren bij het wachtwoord zet de schakelaar terug.
# Nep-pkexec doet wat in het bestand 'code' staat; nep-bugos-updates zegt 'auto'.
nep_pk = TMP / "nep-pk"
nep_pk.mkdir()
(nep_pk / "pkexec").write_text(f'#!/usr/bin/bash\necho "$2" >>"{nep_pk}/gedaan"\necho "uitvoer van $2"\n'
                               f'exit "$(cat "{nep_pk}/code")"\n')
(nep_pk / "bugos-updates").write_text("#!/usr/bin/bash\necho auto\n")
for f in ("pkexec", "bugos-updates"):
    (nep_pk / f).chmod(0o755)
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


venster.close()
shutil.rmtree(TMP, ignore_errors=True)
print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
