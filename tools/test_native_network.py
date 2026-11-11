#!/usr/bin/env python3
"""Test van het pakket 'network': wifi van school of werk, opgeslagen netwerken, de kabel en bluetooth koppelen,
allemaal in BugOS zelf (geen KDE-venster).

Er verandert niets aan je computer: de opdrachten worden opgevangen (bi.draai / bi.draai_nm vervangen), draaien met
nep-programma's in een tijdelijke map, of de pagina's draaien in de voorbeeldstand. D-Bus wordt niet gebruikt.

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_native_network.py
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"
BIN = ROOT / "system_files" / "usr" / "bin"
sys.path.insert(0, str(PY))
TMP = Path(tempfile.mkdtemp(prefix="bugos-native-network-test-"))
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


def vang(functie, *args, antwoord=lambda cmd: (0, ""), antwoord_nm=None, **kwargs):
    """Roep functie aan zonder voorbeeldstand; geef [(opdracht, invoer)] en de uitkomst. Vangt bi.draai
    (antwoord -> (code, uitvoer)) en bi.draai_nm (antwoord_nm -> (code, uitvoer, fouten))."""
    oud = (bi.VOORBEELD, bi.draai, bi.draai_nm, shutil.which)
    opdrachten: list = []
    if antwoord_nm is None:
        def antwoord_nm(cmd, invoer):  # noqa: ARG001
            code, uit = antwoord(cmd)
            return code, uit, ""
    bi.VOORBEELD = False
    bi.draai = lambda *cmd, **kw: (opdrachten.append((cmd, kw.get("invoer"))), antwoord(cmd))[1]
    bi.draai_nm = lambda *cmd, **kw: (opdrachten.append((cmd, kw.get("invoer"))), antwoord_nm(cmd, kw.get("invoer")))[1]
    shutil.which = lambda naam, *a, **k: "/usr/bin/" + naam
    try:
        uit = functie(*args, **kwargs)
    finally:
        bi.VOORBEELD, bi.draai, bi.draai_nm, shutil.which = oud
    return opdrachten, uit


def nep_programma(map_: Path, naam: str, inhoud: str) -> None:
    map_.mkdir(parents=True, exist_ok=True)
    p = map_ / naam
    p.write_text("#!/usr/bin/bash\n" + inhoud, encoding="utf-8", newline="\n")
    p.chmod(0o755)


# =============================================================== de kabel ===
_, k = vang(bi.kabel, antwoord=lambda c: (0, "ethernet:connected:enp0s1\nloopback:connected (externally):lo\n"))
klopt(k == ("verbonden", "enp0s1"), f"kabel: verbonden ({k})")
_, k = vang(bi.kabel, antwoord=lambda c: (0, "ethernet:unavailable:enp3s0\n"))
klopt(k == ("los", "enp3s0"), f"kabel: niet aangesloten ({k})")
_, k = vang(bi.kabel, antwoord=lambda c: (0, "ethernet:disconnected:enp3s0\n"))
klopt(k == ("uit", "enp3s0"), f"kabel: zit erin, niet verbonden ({k})")
_, k = vang(bi.kabel, antwoord=lambda c: (0, "wifi:connected:wlan0\n"))
klopt(k == ("", ""), f"kabel: geen netwerkpoort ({k})")
_, k = vang(bi.kabel, antwoord=lambda c: (0, "ethernet:unavailable:enp3s0\nethernet:connecting (getting IP configuration):enp4s0\n"))
klopt(k == ("bezig", "enp4s0"), f"kabel: met twee poorten telt de beste ({k})")
o, ok = vang(bi.kabel_verbind, "enp3s0")
klopt(ok and o and o[0][0][:2] == ("nmcli", "--wait") and o[0][0][-3:] == ("device", "connect", "enp3s0"),
      f"kabel: verbinden met nmcli device connect ({o[:1]})")
o, ok = vang(bi.kabel_verbind, "--help")
klopt(not ok and not o, "kabel: een apparaatnaam die met '-' begint, gaat niet naar nmcli")

# =========================================================== draai_nm echt ===
_nep = TMP / "nep-bin"
nep_programma(_nep, "nepnm", 'echo out; echo err >&2; exit 4\n')
nep_programma(_nep, "nepslaap", 'sleep 3\n')
klopt(bi.draai_nm(str(_nep / "nepnm")) == (4, "out\n", "err\n"), "draai_nm: geeft code, uitvoer en fouten")
klopt(bi.draai_nm(str(_nep / "bestaat-niet")) == (127, "", ""), "draai_nm: een programma dat er niet is: 127")
_t0 = time.time()
klopt(bi.draai_nm(str(_nep / "nepslaap"), timeout=1)[0] == 124 and time.time() - _t0 < 2.5,
      "draai_nm: te traag: 124 (en niet blijven wachten)")

# ===================================================== opgeslagen netwerken ===
def _antw_opg(cmd):
    if "NAME,UUID,TYPE,ACTIVE" in cmd:
        return 0, ("Home:u-1:802-11-wireless:yes\nWired connection 1:u-2:802-3-ethernet:yes\n"
                   "Cafe\\: De Hoek:u-3:802-11-wireless:no\nHome 1:u-4:802-11-wireless:no\n")
    if "802-11-wireless.ssid" in cmd:
        return 0, {"u-1": "Home\n", "u-3": "Cafe\\: De Hoek\n", "u-4": "Home\n"}[cmd[-1]]
    return 0, ""


_, _opg = vang(bi.opgeslagen_wifi, antwoord=_antw_opg)
klopt([(o.naam, o.uuids, o.actief) for o in _opg] == [("Home", ["u-1", "u-4"], True), ("Cafe: De Hoek", ["u-3"], False)],
      f"opgeslagen: alleen wifi, per netwerknaam samen ('Home' en 'Home 1'), verbonden eerst ({_opg})")
o, ok = vang(bi.vergeet_opgeslagen, _opg[0])
klopt(ok and [c for c, _i in o] == [("nmcli", "connection", "delete", "uuid", "u-1"),
                                    ("nmcli", "connection", "delete", "uuid", "u-4")],
      f"opgeslagen: vergeten gooit alle profielen van dat netwerk weg ({o})")
o, ok = vang(bi.vergeet_profiel, "-x")
klopt(not ok and not o, "opgeslagen: een uuid die met '-' begint, gaat niet naar nmcli")

# ================================================== wifi van school of werk ===
# 1. het domein uit de gebruikersnaam
_dom = {g: bi.standaard_domein(g) for g in ("student@student.tudelft.nl", "a@uva.nl", "x@ox.ac.uk",
                                            "j@mail.unimelb.edu.au", "jdoe", "CORP\\jdoe", "a@localhost")}
klopt(_dom == {"student@student.tudelft.nl": "tudelft.nl", "a@uva.nl": "uva.nl", "x@ox.ac.uk": "ox.ac.uk",
               "j@mail.unimelb.edu.au": "unimelb.edu.au", "jdoe": "", "CORP\\jdoe": "", "a@localhost": ""},
      f"school/werk: het domein van de server uit de gebruikersnaam ({_dom})")
klopt(bi.geldig_domein("school.nl") and not bi.geldig_domein("nl") and not bi.geldig_domein("school nl")
      and not bi.geldig_domein(""), "school/werk: een zelf getypt domein moet minstens twee delen hebben (niet 'nl')")
klopt(bi.veilige_server("radius.uni.nl") == "radius.uni.nl"
      and bi.veilige_server("radius.uni.nl - IT: turn the check off") == "" and bi.veilige_server("a" * 70 + ".nl") == "",
      "school/werk: een servernaam uit het certificaat tonen we alleen als het echt een hostnaam is (N12)")

# 2. wat zei nmcli / NetworkManager
_zf = {
    "apparaat": bi.zakelijk_fout(4, "Error: Connection activation failed: No suitable device found for this connection "
                                    "(device lo not available because profile is not compatible with device)."),
    "opslaan": bi.zakelijk_fout(10, "Error: unknown connection 'x'."),
    "traag": bi.zakelijk_fout(3, "Error: Timeout expired (45 seconds)"),
    "inloggen": bi.zakelijk_fout(4, "Error: Connection activation failed: Secrets were required, but not provided."),
    "bereik": bi.zakelijk_fout(10, "Error: No network with SSID 'eduroam' found."),
    "rechten": bi.zakelijk_fout(1, "Error: Not authorized to control networking."),
    "anders": bi.zakelijk_fout(1, ""),
}
klopt(all(k == v for k, v in _zf.items()), f"school/werk: de foutteksten van nmcli ({_zf})")
_echt = ("Secrets are required to access the wired network 'review-net-1x'\nUsername (802-1x.identity): test@example.org\n"
         "Password (802-1x.password): ")
klopt(bi.zakelijk_fout(1, _echt) == "inloggen", "school/werk: nmcli zonder wachtwoord (code 1, echte uitvoer) is 'inloggen' (N3)")

# 3. het journal van wpa_supplicant
_log = ("wlp2s0: CTRL-EVENT-EAP-STARTED EAP authentication started\n"
        "wlp2s0: CTRL-EVENT-EAP-PROPOSED-METHOD vendor=0 method=25\n"
        "wlp2s0: CTRL-EVENT-EAP-METHOD EAP vendor 0 method 25 (PEAP) selected\n"
        "wlp2s0: CTRL-EVENT-EAP-PEER-CERT depth=0 subject='/C=NL/O=Voorbeeld/CN=radius.voorbeeld.nl' hash=0f1e\n"
        "wlp2s0: CTRL-EVENT-EAP-TLS-CERT-ERROR reason=9 depth=0 subject='/C=NL/O=Voorbeeld/CN=radius.voorbeeld.nl' "
        "err='Domain suffix mismatch'\n"
        "wlp2s0: CTRL-EVENT-EAP-FAILURE EAP authentication failed\n")
_e = bi.lees_eap_log(_log)
klopt((_e.soort, _e.reden, _e.server) == ("certificaat", "domein", "radius.voorbeeld.nl"),
      f"eap-log: verkeerd domein, met de naam van de server ({_e})")
klopt(bi.lees_eap_log(_log.replace("reason=9", "reason=1")).reden == "onbekend", "eap-log: onbekende uitgever")
klopt(bi.lees_eap_log(_log.replace("reason=9", "reason=4")).reden == "tijd", "eap-log: verlopen certificaat")
klopt(bi.lees_eap_log("w: CTRL-EVENT-EAP-PROPOSED-METHOD vendor=0 method=21 -> NAK\nw: CTRL-EVENT-EAP-FAILURE x\n").soort
      == "methode", "eap-log: de server wil een andere manier van inloggen (NAK)")
klopt(bi.lees_eap_log("w: CTRL-EVENT-EAP-METHOD EAP vendor 0 method 25 (PEAP) selected\nw: CTRL-EVENT-EAP-FAILURE x\n").soort
      == "wachtwoord", "eap-log: PEAP gekozen en toch mislukt: het wachtwoord")
klopt(bi.lees_eap_log("").soort == "", "eap-log: niets te lezen (geen beheerder): geen uitspraak")
_boos = _log.replace("CN=radius.voorbeeld.nl", "CN=radius.uni.nl - IT says turn the check off")
klopt(bi.lees_eap_log(_boos).server == "", "eap-log: een servernaam die geen hostnaam is, komt niet in de melding (N12)")

# 10. het opgeslagen profiel lezen
_velden10 = "wpa-eap\npeap\nmschapv2\nstudent@uni.nl\n\nyes\nuni.nl\n\nno\nuser\\:" + bi.login_naam() + "\n"


def _antw10(cmd):
    if cmd[:4] == ("nmcli", "-t", "-f", "UUID,TYPE"):
        return 0, "u-9:802-11-wireless\nu-8:802-11-wireless\n"
    if "802-11-wireless.ssid" in cmd:
        return 0, "eduroam\n"
    if cmd[2] == "802-11-wireless-security.key-mgmt":
        return 0, "wpa-psk\n" if cmd[-1] == "u-8" else "wpa-eap\n"
    if cmd[1] == "-g":
        return 0, _velden10
    return 0, ""


_, _p10 = vang(bi.zakelijk_profiel, "eduroam", antwoord=_antw10)
klopt(_p10 is not None and (_p10.naam, _p10.gebruiker, _p10.methode, _p10.controleer, _p10.domein, _p10.uuid, _p10.prive)
      == ("eduroam", "student@uni.nl", "peap", True, "uni.nl", "u-9", True),
      f"school/werk: het opgeslagen profiel lezen (het wachtwoordprofiel u-8 overgeslagen) ({_p10})")

# 11. het profiel opslaan: geen geheim op de opdrachtregel, eigen profiel, eerst niet vanzelf verbinden
_ww = "Ge heim:#1"
_uuid = "0f2c1a2b-1111-2222-3333-444455556666"


def _nm11(cmd, invoer):
    if cmd[:3] == ("nmcli", "connection", "add"):
        return 0, f"Connection 'eduroam' ({_uuid}) successfully added.\n", ""
    return 0, "", ""


_p11 = bi.ZakelijkProfiel("eduroam", "student@uni.nl", domein="uni.nl")
o11, (_u11, _f11) = vang(bi.bewaar_zakelijk, _p11, antwoord_nm=_nm11)
_add = o11[0][0] if o11 else ()


def _na(cmd, sleutel):
    return cmd[cmd.index(sleutel) + 1] if sleutel in cmd else None


klopt(_u11 == _uuid and _f11 == "" and _add[:3] == ("nmcli", "connection", "add")
      and _na(_add, "connection.permissions") == "user:" + bi.login_naam() and _na(_add, "802-1x.system-ca-certs") == "yes"
      and _na(_add, "802-1x.domain-suffix-match") == "uni.nl" and _na(_add, "802-1x.password-flags") == "0"
      and _na(_add, "connection.autoconnect") == "no" and "802-1x.ca-cert" not in _add,
      f"school/werk: nieuw profiel alleen voor jou, met controle, en nog niet vanzelf verbinden (N4) ({_add})")
klopt(not any(_ww in x for c, _i in o11 for x in c) and not any(c[:3] == ("nmcli", "connection", "edit") for c, _i in o11),
      "school/werk: opslaan zet geen wachtwoord op de opdrachtregel, en gebruikt de nmcli-editor niet (N5)")
o, _ = vang(bi.bewaar_zakelijk, bi.ZakelijkProfiel("eduroam", "s@uni.nl", controleer=False, domein="uni.nl"), antwoord_nm=_nm11)
klopt(_na(o[0][0], "802-1x.system-ca-certs") == "no" and "802-1x.domain-suffix-match" not in o[0][0],
      "school/werk: zonder controle geen systeemcertificaten en geen domein")
o, _ = vang(bi.bewaar_zakelijk, bi.ZakelijkProfiel("eduroam", "s@uni.nl", domein="uni.nl", ca_bestand="/x/ca.pem"),
            antwoord_nm=_nm11)
klopt(_na(o[0][0], "802-1x.system-ca-certs") == "no" and _na(o[0][0], "802-1x.ca-cert") == "/x/ca.pem",
      "school/werk: met een eigen certificaatbestand precies dat ene certificaat")
o, (_u, _f) = vang(bi.bewaar_zakelijk, bi.ZakelijkProfiel("eduroam", "s@uni.nl", uuid="u-7", prive=False, domein="uni.nl"),
                   antwoord_nm=_nm11)
klopt(o and o[0][0][:5] == ("nmcli", "connection", "modify", "uuid", "u-7") and _na(o[0][0], "802-1x.anonymous-identity") == ""
      and _na(o[0][0], "802-1x.ca-cert") == "" and _na(o[0][0], "connection.permissions") == "user:" + bi.login_naam(),
      f"school/werk: een bestaand profiel aanpassen (lege waarden wissen), en het wordt van jou alleen (N13) ({o[:1]})")
o, (_u, _f) = vang(bi.bewaar_zakelijk, bi.ZakelijkProfiel("eduroam", "s@uni.nl", domein="nl"), antwoord_nm=_nm11)
klopt(_f == "opslaan" and not o, "school/werk: een domein van één deel ('nl') wordt niet opgeslagen")
o, (_u, _f) = vang(bi.bewaar_zakelijk, bi.ZakelijkProfiel("eduroam", "s@uni.nl", uuid="u-7", ca_bestand="/tmp/nep.pem"),
                   antwoord_nm=lambda c, i: (2, "", "Error: failed to modify 802-1x.ca-cert: 802-1x.ca-cert: Failed to "
                                                    "recognize certificate.\n"))
klopt(_f == "ca_bestand", f"school/werk: een bestand dat geen certificaat is, krijgt een eigen melding (N6) ({_f})")
o, (_u, _f) = vang(bi.bewaar_zakelijk, _p11, antwoord_nm=lambda c, i: (1, "", "Error: Failed to add 'x' connection: "
                                                                             "Insufficient privileges.\n"))
klopt(_f == "rechten", "school/werk: geen rechten om op te slaan")

# 12. verbinden: het wachtwoord gaat via stdin naar ons eigen hulpje, nooit naar 'nmcli --ask' (N1, N2)
_agent_ok = json.dumps({"gelukt": True, "staat": 2})
o12, u12 = vang(bi.verbind_zakelijk, _uuid, _ww, antwoord_nm=lambda c, i: (0, _agent_ok + "\n", ""))
_c12, _i12 = o12[0] if o12 else ((), None)
klopt(u12 == (True, "", "", "") and _c12[:3] == ("python3", "-I", bi.AGENT) and _uuid in _c12 and _i12 == _ww
      and not any(_ww in x for x in _c12) and "--ask" not in _c12 and "nmcli" not in _c12,
      f"school/werk: verbinden met bugos_wifi_agent, het wachtwoord precies via stdin ({_c12})")
o, _ = vang(bi.verbind_zakelijk, _uuid, "", antwoord_nm=lambda c, i: (0, _agent_ok, ""))
klopt(o and o[0][1] == "", "school/werk: een bekend netwerk: lege invoer (niet None), geen wachtwoord")
_opnieuw = json.dumps({"gelukt": False, "staat": 4, "reden": 9, "apparaat_reden": 7, "gevraagd": 2, "opnieuw": True})


def _antw12(cmd):
    return (0, _log) if cmd[0] == "journalctl" else (0, "")


_, u = vang(bi.verbind_zakelijk, _uuid, "pw", antwoord=_antw12, antwoord_nm=lambda c, i: (1, _opnieuw, ""))
klopt(u == (False, "certificaat", "domein", "radius.voorbeeld.nl"), f"school/werk: mislukt + journal = certificaat ({u})")
_, u = vang(bi.verbind_zakelijk, _uuid, "pw", antwoord_nm=lambda c, i: (1, _opnieuw, ""))
klopt(u == (False, "inloggen", "", ""), f"school/werk: mislukt, journal niet te lezen: 'inloggen' ({u})")
_soorten = {
    "nodig": bi.agent_soort({"gelukt": False, "staat": 4, "reden": 9, "gevraagd": 1, "zonder": True}),
    "bereik": bi.agent_soort({"gelukt": False, "staat": 4, "reden": 3, "apparaat_reden": 53}),
    "traag": bi.agent_soort({"gelukt": False, "te_laat": True}),
    "rechten": bi.agent_soort({"fout": "org.freedesktop.NetworkManager.PermissionDenied", "melding": "Not authorized"}),
    "opslaan": bi.agent_soort({"fout": "org.freedesktop.NetworkManager.Settings.InvalidConnection", "melding": "x"}),
    "apparaat": bi.agent_soort({"fout": "org.freedesktop.NetworkManager.UnknownDevice",
                                "melding": "No suitable device found for this connection"}),
    "anders": bi.agent_soort({}),
}
klopt(all(k == v for k, v in _soorten.items()), f"school/werk: de uitslag van het hulpje in gewone woorden ({_soorten})")
_, u = vang(bi.verbind_zakelijk, _uuid, "pw", antwoord_nm=lambda c, i: (124, "", "Timeout"))
klopt(u[:2] == (False, "traag"), "school/werk: het hulpje te traag: 'traag'")
_, u = vang(bi.verbind_zakelijk, _uuid, "a\nb", antwoord_nm=lambda c, i: (0, _agent_ok, ""))
klopt(u[:2] == (False, "anders"), "school/werk: een wachtwoord met een regeleinde gaat er niet in")

# het hulpje zelf: één keer het wachtwoord, nooit opnieuw (dan stopt NetworkManager, en vraagt KDE niets)
import bugos_wifi_agent as wa  # noqa: E402

klopt(wa.antwoord("802-1x", 1, " a\tb ", False) == {"802-1x": {"password": " a\tb "}},
      "hulpje: geeft het wachtwoord precies zoals getypt (ook spaties en tabs) (N5)")
klopt(wa.antwoord("802-1x", 1 | wa.VRAAG_OPNIEUW, "pw", False) is None, "hulpje: vraagt NetworkManager het opnieuw: stop")
klopt(wa.antwoord("802-1x", 1, "pw", True) is None, "hulpje: maar één keer per poging (geen tweede poging op je account)")
klopt(wa.antwoord("802-1x", 1, "", False) is None, "hulpje: geen wachtwoord: stop (BugOS vraagt het zelf)")
klopt(wa.antwoord("vpn", 1, "pw", False) is None, "hulpje: alleen wifi en 802.1X")
klopt(wa.antwoord("802-11-wireless-security", 1, "pw", False) == {"802-11-wireless-security": {"psk": "pw"}},
      "hulpje: kan ook een gewoon wifi-wachtwoord geven")
_bron_agent = (PY / "bugos_wifi_agent.py").read_text(encoding="utf-8")
klopt("RequestDefault" not in _bron_agent and "UserCanceled" in _bron_agent and "sys.stdin.read()" in _bron_agent
      and ".strip()" not in _bron_agent.split("sys.stdin.read()")[1].split("\n")[0],
      "hulpje: leest het wachtwoord van stdin zonder iets eraf te halen, en zegt 'UserCanceled' op een tweede vraag")

# W5: het certificaatbestand van de ICT-afdeling
_ca = TMP / "Downloads" / "ca.crt"
_ca.parent.mkdir(parents=True)
_ca.write_text("-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n")
_nep_ca = TMP / "Downloads" / "foto.jpg"
_nep_ca.write_bytes(b"\xff\xd8\xff" + b"0" * 500)
_oud_vb = bi.VOORBEELD
bi.VOORBEELD = False
_pad, _f = bi.kopieer_ca(str(_ca), "edu roam/2")
_pad2, _f2 = bi.kopieer_ca(str(_nep_ca), "eduroam")
bi.VOORBEELD = _oud_vb
klopt(_f == "" and _pad == str(TMP / ".cert" / "bugos-wifi" / "edu_roam_2.pem") and Path(_pad).is_file()
      and (Path(_pad).parent.stat().st_mode & 0o777) == 0o700,
      f"certificaat: gekopieerd naar ~/.cert/bugos-wifi/ (map 0700), veilige naam ({_pad})")
klopt(_pad2 == "" and _f2 == "ca_bestand", "certificaat: een foto is geen certificaat: eigen melding")

# ================================================================ pagina's ===
# (alles hierboven raakt Qt niet; vanaf hier het venster van Instellingen in de voorbeeldstand)
lader = importlib.machinery.SourceFileLoader("instellingen", str(BIN / "bugos-settings"))
spec = importlib.util.spec_from_loader("instellingen", lader)
mod = importlib.util.module_from_spec(spec)
sys.modules["instellingen"] = mod
lader.exec_module(mod)
from PySide6.QtCore import QThreadPool  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = mod.maak_app("bugos-settings", "bugos-settings", ["test"])
venster = mod.Instellingen("start")
sn = sys.modules["bugos_settings_netwerk"]


def wacht(rondes: int = 5) -> None:
    for _ in range(rondes):
        QThreadPool.globalInstance().waitForDone(5000)
        app.processEvents()


def wacht_ms(ms: int) -> None:
    eind = time.time() + ms / 1000
    while time.time() < eind:
        QThreadPool.globalInstance().waitForDone(20)
        app.processEvents()
        time.sleep(0.01)


venster.ga_naar("wifi")
wacht()
wifi = venster.paginas["wifi"]

# ---- de kabel op de pagina
bi.VB_NET["kabel"] = "los"
wifi.ververs()
wacht()
klopt(not wifi.kabel.isHidden() and "Niet aangesloten" in wifi.kabel.uitleg.text() and wifi.kabel_knop.isHidden(),
      f"kabel-regel: 'Niet aangesloten' als de kabel eruit is ({wifi.kabel.uitleg.text()!r})")
bi.VB_NET["kabel"] = "uit"
wifi.ververs()
wacht()
klopt(not wifi.kabel_knop.isHidden(), "kabel-regel: kabel erin maar niet verbonden: knop 'Verbinden'")
_kv = []
_oud_kv = bi.kabel_verbind
bi.kabel_verbind = lambda apparaat: (_kv.append(apparaat), True)[1]
wifi.kabel_knop.click()
wacht()
bi.kabel_verbind = _oud_kv
klopt(_kv == ["enp3s0"], f"kabel-regel: 'Verbinden' verbindt die poort ({_kv})")
bi.VB_NET["kabel"] = ""
wifi.ververs()
wacht()
klopt(wifi.kabel.isHidden(), "kabel-regel: zonder netwerkpoort geen regel")
wifi.toon((True, [], False, False))
klopt(wifi.kabel.isHidden() and wifi.lijst.isHidden(), "kabel-regel: de oude vorm (True/False) werkt nog (U111)")
wifi.toon((True, [], ("verbonden", "enp0s1"), False))
klopt(not wifi.kabel.isHidden() and "geen wifi" in wifi.hoofd.uitleg.text().lower(),
      "kabel-regel: zonder wifi in de computer staat de kabel er wel")
wifi.ververs()
wacht()

# ---- opgeslagen netwerken (in de eerste kaart, onder de schakelaar)
klopt(not wifi.opgeslagen.isHidden() and wifi.opgeslagen.parent() is wifi.hoofd.parent(),
      "opgeslagen: de regel 'Opgeslagen netwerken' staat in de eerste kaart, onder de wifi-schakelaar")
wifi.opgeslagen.geklikt.emit()
wacht()
_od = wifi.opgeslagen_dialoog
_namen = list(_od.rijen)
klopt(_od.isVisible() and _namen[:1] == ["Home"] and set(_namen) == {"Home", "Home-5G", "eduroam", "Hotel Zonneveld"}
      and _od.rijen["Home"].uitleg.text() == "Nu verbonden",
      f"opgeslagen: het venster toont de 4 voorbeeldnetwerken, 'Home' (verbonden) eerst ({_namen})")
_od.rijen["Hotel Zonneveld"].rechts.click()
wacht()
klopt("Hotel Zonneveld" not in _od.rijen and not _od.banner.isHidden() and "vergeten" in _od.banner.tekst.text(),
      f"opgeslagen: 'Vergeten' haalt de regel weg en zegt het ({_od.banner.tekst.text()!r})")
_oud_vo = bi.vergeet_opgeslagen
bi.vergeet_opgeslagen = lambda o: False
_od.rijen["Home-5G"].rechts.click()
wacht()
bi.vergeet_opgeslagen = _oud_vo
klopt("Home-5G" in _od.rijen and "lukte niet" in _od.banner.tekst.text() and _od.rijen["Home-5G"].rechts.isEnabled(),
      "opgeslagen: lukt vergeten niet, dan zegt het venster dat (en de knop doet het weer)")
_od.accept()
wacht()
wifi.toon((True, [], False, False))
klopt(wifi.opgeslagen.isHidden(), "opgeslagen: zonder wifi in de computer geen regel 'Opgeslagen netwerken'")
wifi.ververs()
wacht()

# ---- de lay-out-notities: kopjes met een knop, de wachtwoordvraag in BugOS-stijl, Engelse voorbeeldnamen
klopt(wifi.zoek_knop.parent().objectName() == "sectie_met_knop",
      "wifi: 'Opnieuw zoeken' staat in het kopje 'Netwerken in de buurt' (sectie_met_knop)")
import bugos_shell  # noqa: E402

_vd = {}


def _nep_exec(self):
    _vd["echo"] = self.veld.echoMode() if self.veld is not None else None
    _vd["uitleg"] = self.uitleg.text()
    self.veld.setText("ge heim")
    return 1


_oud_exec = bugos_shell.VraagDialoog.exec
bugos_shell.VraagDialoog.exec = _nep_exec
_ww = wifi.vraag_wachtwoord(bi.Netwerk("Thuis", 80, True, False))
bugos_shell.VraagDialoog.exec = lambda self: 0
_ww_weg = wifi.vraag_wachtwoord(bi.Netwerk("Thuis", 80, True, False), veranderd=True)
bugos_shell.VraagDialoog.exec = _oud_exec
from PySide6.QtWidgets import QLineEdit  # noqa: E402

klopt(_ww == "ge heim" and _ww_weg == "" and _vd.get("echo") == QLineEdit.EchoMode.Password and "Thuis" in _vd["uitleg"],
      f"wifi: het wachtwoord vragen gaat met BugOS' eigen vraag (bolletjes), Annuleren geeft '' ({_vd})")
_bron_cfg = (PY / "bugos_config_netwerk.py").read_text(encoding="utf-8")
klopt('t("Buren", "Neighbours")' in _bron_cfg and 't("Telefoon", "Phone")' in _bron_cfg and 't("Muis", "Mouse")' in _bron_cfg,
      "voorbeeldstand: de namen van buren, muis en telefoon zijn er ook in het Engels")
klopt(sn.apparaat_icoon("phone") == "telefoon", "bluetooth: een telefoon heeft het telefoon-icoon (geen tekstballon)")

# ==================================================================== eind ===
venster.close()
shutil.rmtree(TMP, ignore_errors=True)
print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
