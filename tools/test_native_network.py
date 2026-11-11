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
# Echte uitslagen van bugos_wifi_agent tegen NetworkManager 1.56.1 (container van de BugOS-image, bekabeld 802.1X op
# een veth-paar zonder server: de inlog loopt altijd vast, zoals een verkeerd wachtwoord).
_echt_agent = {
    # eerste keer, wachtwoord gegeven: één keer gegeven, de tweede vraag (REQUEST_NEW) geweigerd; KDE niets gevraagd
    "inloggen": '{"gelukt": false, "staat": 4, "reden": 3, "apparaat_reden": 7, "gevraagd": 2, "opnieuw": true, '
                '"zonder": false, "te_laat": false, "fout": "", "melding": "", "bewaard": false}',
    # bekend netwerk (lege invoer), het opgeslagen wachtwoord werkte niet
    "inloggen ": '{"gelukt": false, "staat": 4, "reden": 3, "apparaat_reden": 7, "gevraagd": 1, "opnieuw": true, '
                 '"zonder": true, "te_laat": false, "fout": "", "melding": "", "bewaard": false}',
    # ons eigen tijdslimiet: NetworkManager gestopt
    "traag": '{"gelukt": false, "staat": 1, "reden": 0, "apparaat_reden": 0, "gevraagd": 0, "opnieuw": false, '
             '"zonder": false, "te_laat": true, "fout": "", "melding": "", "bewaard": false}',
    # een profiel zonder opgeslagen wachtwoord (van KDE, in KWallet) en geen gegeven: BugOS vraagt het zelf
    "nodig": '{"gelukt": false, "staat": 4, "reden": 3, "apparaat_reden": 7, "gevraagd": 1, "opnieuw": false, '
             '"zonder": true, "te_laat": false, "fout": "", "melding": "", "bewaard": false}',
    "opslaan": '{"gelukt": false, "staat": 0, "reden": 0, "apparaat_reden": 0, "gevraagd": 0, "opnieuw": false, '
               '"zonder": false, "te_laat": false, "fout": "org.freedesktop.NetworkManager.Settings.InvalidConnection", '
               '"melding": "No connection with the UUID was found.", "bewaard": false}',
    "apparaat": '{"gelukt": false, "staat": 0, "reden": 0, "apparaat_reden": 0, "gevraagd": 0, "opnieuw": false, '
                '"zonder": false, "te_laat": false, "fout": "org.freedesktop.NetworkManager.UnknownDevice", "melding": '
                '"No suitable device found for this connection (device lo not available because device is strictly '
                'unmanaged).", "bewaard": false}',
}
_echt_fout = {k: bi.agent_soort(bi.lees_agent_uitslag(v)) for k, v in _echt_agent.items()
              if bi.agent_soort(bi.lees_agent_uitslag(v)) != k.strip()}
klopt(not _echt_fout, f"school/werk: echte uitslagen van het hulpje (NetworkManager 1.56) in gewone woorden ({_echt_fout})")
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

# =============================================================== bluetooth ===
# 4. wat BlueZ weet (busctl --json=short ... GetManagedObjects)
_BT_JSON = json.dumps({"type": "a{oa{sa{sv}}}", "data": [{
    "/org/bluez": {"org.bluez.AgentManager1": {}, "org.bluez.ProfileManager1": {}},
    "/org/bluez/hci0": {"org.bluez.Adapter1": {
        "Address": {"type": "s", "data": "00:1A:7D:DA:71:13"}, "Name": {"type": "s", "data": "bugos"},
        "Powered": {"type": "b", "data": True}, "PowerState": {"type": "s", "data": "on"},
        "Discovering": {"type": "b", "data": True}}},
    "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_10": {"org.bluez.Device1": {
        "Address": {"type": "s", "data": "AA:BB:CC:DD:EE:10"}, "Name": {"type": "s", "data": "Galaxy Buds2"},
        "Alias": {"type": "s", "data": "Galaxy Buds2"}, "Icon": {"type": "s", "data": "audio-headset"},
        "Paired": {"type": "b", "data": False}, "Connected": {"type": "b", "data": False},
        "RSSI": {"type": "n", "data": -48}, "Adapter": {"type": "o", "data": "/org/bluez/hci0"}}},
    "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_14": {"org.bluez.Device1": {
        "Address": {"type": "s", "data": "AA:BB:CC:DD:EE:14"}, "Alias": {"type": "s", "data": "AA-BB-CC-DD-EE-14"},
        "Paired": {"type": "b", "data": False}, "Connected": {"type": "b", "data": False},
        "RSSI": {"type": "n", "data": -80}, "Adapter": {"type": "o", "data": "/org/bluez/hci0"}}},
    "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_01": {"org.bluez.Device1": {
        "Address": {"type": "s", "data": "AA:BB:CC:DD:EE:01"}, "Name": {"type": "s", "data": "Bugie's headphones"},
        "Icon": {"type": "s", "data": "audio-headset"}, "Paired": {"type": "b", "data": True},
        "Connected": {"type": "b", "data": True}, "Adapter": {"type": "o", "data": "/org/bluez/hci0"}},
        "org.bluez.Battery1": {"Percentage": {"type": "y", "data": 80}}},
}]})
_bs = bi.lees_bt_objecten(_BT_JSON)
_bp = {g.adres: g for g in _bs.apparaten}
klopt((_bs.adapter, _bs.aan, _bs.stroom, len(_bs.apparaten)) == ("/org/bluez/hci0", True, "on", 3)
      and _bp["AA:BB:CC:DD:EE:14"].naam == "" and _bp["AA:BB:CC:DD:EE:01"].batterij == 80
      and _bp["AA:BB:CC:DD:EE:10"].sterkte == -48 and _bp["AA:BB:CC:DD:EE:01"].gekoppeld,
      f"bluetooth: wat BlueZ weet lezen (kaart aan, 3 apparaten, naamloos = '', batterij) ({_bs})")
klopt([g.naam for g in bi.bt_nieuw(_bs)] == ["Galaxy Buds2"],
      "bluetooth: te koppelen = niet gekoppeld en met een naam")
klopt(bi.lees_bt_objecten("Call failed: Could not activate remote peer 'org.bluez': unit failed") == bi.BtStand()
      and bi.lees_bt_objecten('{"type":"x","data":[]}') == bi.BtStand() and bi.lees_bt_objecten('{"data":[[]]}')
      == bi.BtStand(), "bluetooth: rommel of geen bluetooth: een lege stand, geen fout")
_o, _st = vang(bi.bt_objecten, antwoord=lambda c: (1, ""))
klopt(_st == bi.BtStand() and _o and _o[0][0][:4] == ("busctl", "--system", "--json=short", "--timeout=5"),
      f"bluetooth: lezen met busctl; lukt het niet, dan een lege stand ({_o[:1]})")
# 5. wat voor apparaat
_soorten_bt = {i: bi.bt_soort(i) for i in ("audio-headset", "audio-card", "input-mouse", "input-keyboard", "input-gaming",
                                           "phone", "computer", "", "iets-anders")}
klopt(_soorten_bt == {"audio-headset": "geluid", "audio-card": "geluid", "input-mouse": "muis",
                      "input-keyboard": "toetsenbord", "input-gaming": "spel", "phone": "telefoon",
                      "computer": "computer", "": "apparaat", "iets-anders": "apparaat"},
      f"bluetooth: soort apparaat uit het icoon van BlueZ ({_soorten_bt})")
# 6. de code
klopt(bi.code_tekst(284913) == "284 913" and bi.code_tekst(7) == "000 007" and bi.code_tekst("0000") == "0000",
      "bluetooth: de code in twee groepjes van drie, zoals op een telefoon")
# 7. fouten van BlueZ in gewone woorden
_kf = {
    "org.bluez.Error.AuthenticationFailed": "codes", "org.bluez.Error.AuthenticationCanceled": "gestopt",
    "org.bluez.Error.AuthenticationRejected": "geweigerd", "org.bluez.Error.AuthenticationTimeout": "traag",
    "org.freedesktop.DBus.Error.NoReply": "traag", "org.freedesktop.DBus.Error.Timeout": "traag",
    "org.bluez.Error.ConnectionAttemptFailed": "bereik", "org.bluez.Error.Failed": "bereik",
    "org.bluez.Error.NotAvailable": "bereik", "org.bluez.Error.AlreadyExists": "al", "org.bluez.Error.InProgress": "bezig",
    "org.bluez.Error.NotReady": "uit", "org.freedesktop.DBus.Error.NameHasNoOwner": "geen",
    "org.freedesktop.DBus.Error.ServiceUnknown": "geen", "org.freedesktop.DBus.Error.UnknownObject": "geen",
    "org.freedesktop.DBus.Error.UnknownMethod": "geen", "org.example.Iets": "anders",
}
_kf_fout = {n: bi.bt_koppel_fout(n) for n, s in _kf.items() if bi.bt_koppel_fout(n) != s}
klopt(not _kf_fout, f"bluetooth: elke fout van BlueZ heeft een soort ({_kf_fout})")
klopt(bi.bt_koppel_fout("org.freedesktop.DBus.Error.UnknownObject", apparaat=True) == "weg",
      "bluetooth: een apparaat dat BlueZ al opruimde: 'opnieuw zoeken', niet 'bluetooth doet het niet' (N14)")
# vertrouwen vóór het koppelen (N8) en daarna verbinden, met busctl (betrouwbare exitcode)
_pad = "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_10"
_o, _ok = vang(bi.bt_vertrouw, _pad, True)
klopt(_ok and _o and _o[0][0] == ("busctl", "--system", "--timeout=5", "set-property", "org.bluez", _pad,
                                  "org.bluez.Device1", "Trusted", "b", "true"),
      f"bluetooth: vertrouwen met busctl set-property ... Trusted b true ({_o[:1]})")
_o, _ok = vang(bi.bt_vertrouw, "/org/bluez/hci0/dev_AA; rm -rf", True)
klopt(not _ok and not _o, "bluetooth: een vreemd pad gaat niet naar busctl")
_o, _uit = vang(bi.bt_vertrouw_en_verbind, _pad, "AA:BB:CC:DD:EE:10",
                antwoord_nm=lambda c, i: (1, "", "Call failed: Already Connected\n"))
klopt(_uit == (True, True) and any(c[0][-2:] == ("org.bluez.Device1", "Connect") for c in _o),
      f"bluetooth: na het koppelen verbinden; 'al verbonden' is ook goed ({_o})")
_o, _uit = vang(bi.bt_vertrouw_en_verbind, _pad, "AA:BB:CC:DD:EE:10",
                antwoord_nm=lambda c, i: (1, "", "Call failed: Software caused connection abort\n"))
klopt(_uit == (True, False), "bluetooth: verbinden lukt niet: dat weten we")
# 14. uit met een knop op de computer (rfkill hard)
_rf = TMP / "sys" / "class" / "rfkill" / "rfkill0"
_rf.mkdir(parents=True)
(_rf / "type").write_text("bluetooth\n")
(_rf / "hard").write_text("1\n")
(_rf / "soft").write_text("0\n")
_hard1 = bi.bt_hard_uit()
(_rf / "hard").write_text("0\n")
(_rf / "soft").write_text("1\n")
_hard0 = bi.bt_hard_uit()
shutil.rmtree(TMP / "sys")
klopt(_hard1 is True and _hard0 is False and bi.bt_hard_uit() is False,
      "bluetooth: 'hard' uit (vliegtuigknop) gezien; 'soft' uit en geen rfkill niet")

# ================================================================ pagina's ===
# (alles hierboven raakt Qt niet; vanaf hier het venster van Instellingen in de voorbeeldstand)
lader = importlib.machinery.SourceFileLoader("instellingen", str(BIN / "bugos-settings"))
spec = importlib.util.spec_from_loader("instellingen", lader)
mod = importlib.util.module_from_spec(spec)
sys.modules["instellingen"] = mod
lader.exec_module(mod)
from PySide6.QtCore import QThreadPool  # noqa: E402
from PySide6.QtWidgets import QApplication, QLineEdit  # noqa: E402,F401

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

# ---- wifi van school of werk: het eigen venster (geen KDE)
_kde = []
import subprocess  # noqa: E402

_oud_popen = subprocess.Popen


class _NepPopen:
    """Elk programma dat de pagina's los starten (KDE-instellingen, de koppel-wizard van KDE): opgevangen."""

    def __init__(self, cmd, *a, **k):  # noqa: ARG002
        _kde.append(cmd)


subprocess.Popen = _NepPopen
_netten = bi.netwerken()
_edu = next((n for n in _netten if n.naam == "eduroam"), None)
klopt(_edu is not None and _edu.zakelijk, "school/werk: de voorbeeldlijst heeft eduroam (school of werk)")
wifi.verbind_met(_edu, False)
zd = wifi.zakelijk_dialoog
klopt(zd.isVisible() and "eduroam" in zd.windowTitle() and not zd.ok.isEnabled() and not _kde,
      f"school/werk: eduroam opent BugOS' eigen venster, 'Verbinden' kan nog niet (KDE: {_kde})")
zd.gebruiker.setText("")
zd.gebruiker.textEdited.emit("student@student.tudelft.nl")
zd.gebruiker.setText("student@student.tudelft.nl")
klopt(zd.domein.text() == "tudelft.nl", f"school/werk: het domein vult zich in uit de gebruikersnaam ({zd.domein.text()!r})")
zd.gebruiker.editingFinished.emit()
zd.wachtwoord.setText("geheim")
klopt(zd.ok.isEnabled() and zd.hint.isHidden(), "school/werk: met naam en wachtwoord kan 'Verbinden'")
klopt(zd.wachtwoord.echoMode() == QLineEdit.EchoMode.Password and zd.oog.toolTip(),
      "school/werk: het wachtwoord zijn bolletjes, met een oogje om het te laten zien")
zd.controle.setChecked(False)
klopt(not zd.waarschuwing.isHidden() and "minder veilig" in zd.waarschuwing.tekst.text(),
      "school/werk: de controle uit: een waarschuwing")
zd.methode.knoppen["ttls"].click()
klopt("TTLS" in zd.waarschuwing.tekst.text(), "school/werk: TTLS zonder controle: de strengere waarschuwing")
zd.methode.knoppen["peap"].click()
zd.controle.setChecked(True)
zd.domein.setText("")
klopt(not zd.ok.isEnabled() and not zd.hint.isHidden() and "domein" in zd.hint_tekst.text() and zd.meer.isChecked(),
      "school/werk: controle aan zonder domein: 'Verbinden' kan niet, en boven de knoppen staat waarom (N9)")
zd.domein.setText("nl")
klopt(not zd.ok.isEnabled() and "geen domein" in zd.hint_tekst.text(),
      "school/werk: 'nl' is geen domein (minstens twee delen) (N12)")
zd.domein.setText("tudelft.nl")
zd.reject()
wacht()

# zonder '@' in de gebruikersnaam: Meer opties gaat open en zegt wat er mist (geen grijze knop zonder reden)
wifi.open_zakelijk("eduroam")
zd = wifi.zakelijk_dialoog
zd.gebruiker.textEdited.emit("C")
zd.gebruiker.setText("C")
klopt(not zd.meer.isChecked() and zd.hint.isHidden(),
      "school/werk: tijdens het typen van de gebruikersnaam klapt er nog niets open")
zd.gebruiker.textEdited.emit("CORP\\jdoe")
zd.gebruiker.setText("CORP\\jdoe")
zd.gebruiker.editingFinished.emit()
zd.wachtwoord.setText("x")
klopt(not zd.domein.hasFocus(), "school/werk: de focus springt niet naar het domeinveld (dan typ je daar je wachtwoord)")
klopt(zd.meer.isChecked() and not zd.opties.isHidden() and not zd.hint.isHidden() and not zd.ok.isEnabled(),
      "school/werk: 'CORP\\jdoe': Meer opties klapt open, met de reden boven de knoppen (N9)")
zd.reject()
wacht()

# verbinden: wachtwoord 'fout' -> het venster blijft, met de reden; domein 'fout.nl' -> certificaat
wifi.open_zakelijk("eduroam")
zd = wifi.zakelijk_dialoog
zd.gebruiker.textEdited.emit("student@uni.nl")
zd.gebruiker.setText("student@uni.nl")
zd.wachtwoord.setText("fout")
zd.ok.click()
klopt(not zd.ok.isEnabled() and "Verbinden…" in zd.ok.text() and "minuut" in zd.banner.tekst.text(),
      "school/werk: tijdens het verbinden: 'Verbinden…' en een melding dat het even kan duren")
wacht()
klopt(zd.isVisible() and not zd.banner.isHidden() and "Kloppen je gebruikersnaam en wachtwoord" in zd.banner.tekst.text()
      and zd.wachtwoord.selectedText() == "fout" and zd.nieuw_uuid == "voorbeeld-eduroam",
      f"school/werk: verkeerd wachtwoord: het venster blijft, zegt het, en het wachtwoord is gekozen ({zd.banner.tekst.text()!r})")
_vergeten = []
_oud_vp = bi.vergeet_profiel
bi.vergeet_profiel = lambda u: (_vergeten.append(u), True)[1]
zd.reject()
wacht()
bi.vergeet_profiel = _oud_vp
klopt(_vergeten == ["voorbeeld-eduroam"], f"school/werk: Annuleren na een mislukt nieuw profiel gooit het weer weg ({_vergeten})")
bi.VB_NET["zakelijk"].clear()

# Annuleren terwijl het nog verbindt: dat profiel stoppen en (nieuw) weggooien; de late uitslag doet niets meer
_gestopt, _vergeten = [], []
_oud_an = (bi.verbind_zakelijk, bi.stop_profiel, bi.vergeet_profiel)
bi.verbind_zakelijk = lambda uuid, ww="": (time.sleep(0.8), (True, "", "", ""))[1]
bi.stop_profiel = lambda u: (_gestopt.append(u), True)[1]
bi.vergeet_profiel = lambda u: (_vergeten.append(u), True)[1]
wifi.open_zakelijk("eduroam")
zd = wifi.zakelijk_dialoog
_klaar_an = []
zd.klaar.connect(_klaar_an.append)
zd.gebruiker.textEdited.emit("student@uni.nl")
zd.gebruiker.setText("student@uni.nl")
zd.wachtwoord.setText("goed")
zd.ok.click()
wacht_ms(300)
klopt(zd.bezig and zd.uuid == "voorbeeld-eduroam", "school/werk: eerst opgeslagen, nu bezig met verbinden")
zd.reject()
wacht()
bi.verbind_zakelijk, bi.stop_profiel, bi.vergeet_profiel = _oud_an
klopt(_gestopt == ["voorbeeld-eduroam"] and _vergeten == ["voorbeeld-eduroam"] and _klaar_an == [False]
      and not zd.isVisible(),
      f"school/werk: Annuleren tijdens het verbinden stopt het en gooit het nieuwe profiel weg ({_gestopt}, {_vergeten}, {_klaar_an})")
bi.VB_NET["zakelijk"].clear()

wifi.open_zakelijk("eduroam")
zd = wifi.zakelijk_dialoog
zd.gebruiker.setText("student@uni.nl")
zd.domein.textEdited.emit("fout.nl")
zd.domein.setText("fout.nl")
zd.wachtwoord.setText("goed")
zd.ok.click()
wacht()
klopt(zd.isVisible() and zd.meer.isChecked() and "radius.voorbeeld.nl" in zd.banner.tekst.text()
      and "fout.nl" in zd.banner.tekst.text(),
      f"school/werk: verkeerd domein: Meer opties open, met de naam van de server ({zd.banner.tekst.text()!r})")
zd.domein.setText("uni.nl")
zd.ok.click()
wacht()
klopt(not zd.isVisible() and zd.gelukt and "Verbonden met eduroam" in wifi.melding.tekst.text()
      and next((n.verbonden for n in bi.netwerken() if n.naam == "eduroam"), False),
      f"school/werk: goed: het venster gaat dicht, 'Verbonden met eduroam.' ({wifi.melding.tekst.text()!r})")
klopt(zd.wachtwoord.text() == "", "school/werk: het wachtwoord blijft niet in het venster staan")
wacht()

# een bekend netwerk van school of werk dat niet meer wil: het venster opent ingevuld, met de reden
_oud_zk = (bi.bekend_netwerk, bi.zakelijk_profiel, bi.verbind_zakelijk)
bi.bekend_netwerk = lambda naam: True
bi.zakelijk_profiel = lambda naam: bi.ZakelijkProfiel(naam, "oud@uni.nl", domein="uni.nl", uuid="u-5")
bi.verbind_zakelijk = lambda uuid, ww="": (False, "wachtwoord", "", "")
wifi.verbind(_edu)
wacht()
bi.bekend_netwerk, bi.zakelijk_profiel, bi.verbind_zakelijk = _oud_zk
zd = wifi.zakelijk_dialoog
klopt(zd.isVisible() and zd.gebruiker.text() == "oud@uni.nl" and zd.uuid == "u-5" and "Inloggen lukte niet" in zd.banner.tekst.text()
      and zd.nieuw_uuid == "",
      "school/werk: bekend netwerk dat niet meer wil: het venster opent met de oude naam en de reden")
zd.reject()
wacht()

# verborgen netwerk van school of werk: met een naamveld
klopt(not wifi.school.isHidden() and wifi.school.parent() is wifi.ander.parent(),
      "school/werk: naast 'Ander netwerk…' staat 'Netwerk van school of werk…'")
_bewaard = []
_oud_bz = bi.bewaar_zakelijk
bi.bewaar_zakelijk = lambda p: (_bewaard.append(p), ("voorbeeld-" + p.naam, ""))[1]
wifi.school.click()
zd = wifi.zakelijk_dialoog
klopt(zd.netnaam is not None and "school of werk" in zd.windowTitle(), "school/werk: verborgen: venster met een naamveld")
zd.gebruiker.textEdited.emit("a@b.nl")
zd.gebruiker.setText("a@b.nl")
zd.wachtwoord.setText("x")
klopt(not zd.ok.isEnabled(), "school/werk: verborgen: zonder netwerknaam kan 'Verbinden' niet")
zd.netnaam.setText("Kantoor")
zd.ok.click()
wacht()
bi.bewaar_zakelijk = _oud_bz
klopt(_bewaard and _bewaard[0].verborgen and _bewaard[0].naam == "Kantoor", "school/werk: verborgen: het profiel is 'hidden'")
wacht()
wifi.toon((True, [], False, False))
klopt(wifi.school.isHidden(), "school/werk: zonder wifi in de computer ook geen knop 'Netwerk van school of werk…' (N15)")
wifi.ververs()
wacht()
subprocess.Popen = _oud_popen
klopt(not _kde, f"school/werk: nergens een KDE-venster ({_kde})")
_bron_pag = (PY / "bugos_settings_netwerk.py").read_text(encoding="utf-8")
klopt("kcm_networkmanagement" not in _bron_pag and sn.WifiPagina.kde == "",
      "school/werk: de wifi-pagina verwijst niet meer naar KDE (kcm_networkmanagement)")

# past op een klein scherm: de knoppen blijven te zien (het middenstuk schuift)
wifi.open_zakelijk("eduroam")
zd = wifi.zakelijk_dialoog
zd.meer.setChecked(True)
zd.controle.setChecked(False)
wacht()
klopt(zd.height() <= sn.vrije_hoogte(zd) and zd.vlak.maximumHeight() < 16777215,
      f"school/werk: met Meer opties open past het venster op het scherm ({zd.height()} <= {sn.vrije_hoogte(zd)})")
zd.reject()
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

# ================================================================ bluetooth: apparaat toevoegen ===
from PySide6.QtCore import QObject, QTimer, Signal  # noqa: E402

venster.ga_naar("bluetooth")
wacht()
bt = venster.paginas["bluetooth"]
_kde.clear()
subprocess.Popen = _NepPopen


def open_koppel(ms: int = 2000):
    bt.koppel_nieuw()
    wacht()
    d = getattr(bt, "koppel_dialoog", None)
    if d is not None:
        wacht_ms(ms)
    return d


bi._VB["bt"] = True
kd = open_koppel()
_rij_namen = list(kd.rijen) if kd is not None else []
klopt(kd is not None and kd.isVisible() and isinstance(kd.koppelaar, sn.NepKoppelaar) and not _kde,
      "bluetooth: 'Nieuw apparaat koppelen' opent BugOS' eigen venster (geen KDE-wizard)")
klopt(_rij_namen[:1] == ["Galaxy Buds2"] and set(_rij_namen) == {"Galaxy Buds2", "Keyboard K380", "Galaxy A54",
                                                                    "Xbox Wireless Controller"},
      f"bluetooth: na het zoeken 4 apparaten (zonder naam niet), de dichtstbijzijnde eerst ({_rij_namen})")
klopt(kd.rijen["Galaxy A54"].uitleg.text() == "Telefoon" and kd.rijen["Galaxy Buds2"].uitleg.text() == "Koptelefoon of speaker",
      "bluetooth: elk apparaat zegt in gewone woorden wat het is")
klopt(kd.height() <= sn.vrije_hoogte(kd) and kd.weg_knop.isVisible(), "bluetooth: het venster past op het scherm")

# de telefoon: 'Nee, ze zijn anders' -> codes; opnieuw -> 'Ja, koppelen' -> gekoppeld
kd.rijen["Galaxy A54"].geklikt.emit()
wacht_ms(700)
klopt(kd.staat == "vergelijk" and kd.code.text() == "284 913" and kd.ja_knop.text() == "Ja, koppelen"
      and kd.nee_knop.text() == "Nee, ze zijn anders" and kd.code.accessibleName() == "2 8 4 9 1 3",
      f"bluetooth: telefoon: 'Zie je deze code ook?' met 284 913 ({kd.staat}, {kd.code.text()!r})")
kd.nee_knop.click()
wacht_ms(600)
klopt(kd.staat == "fout" and "codes kwamen niet overeen" in kd.banner.tekst.text()
      and kd.nee_knop.text() == "Terug naar de lijst" and kd.ja_knop.text() == "Opnieuw proberen",
      f"bluetooth: 'Nee' -> de codes kwamen niet overeen, met 'Terug naar de lijst' en 'Opnieuw proberen' ({kd.banner.tekst.text()!r})")
kd.ja_knop.click()
wacht_ms(700)
klopt(kd.staat == "vergelijk", "bluetooth: 'Opnieuw proberen' koppelt hetzelfde apparaat nog eens")
kd.ja_knop.click()
wacht_ms(800)
wacht()
klopt(not kd.isVisible() and "Galaxy A54" in bt.melding.tekst.text() and "gekoppeld" in bt.melding.tekst.text()
      and any(a.naam == "Galaxy A54" for a in bi.bt_apparaten()),
      f"bluetooth: 'Ja, koppelen' -> gekoppeld, het venster dicht, de telefoon in de lijst ({bt.melding.tekst.text()!r})")
wacht()
klopt(any(r.titel.text() == "Galaxy A54" for r in bt.lijst.findChildren(sn.Rij)),
      "bluetooth: de nieuwe telefoon staat op de pagina")

# het toetsenbord: de code typen, met hoeveel cijfers er al getypt zijn
kd = open_koppel()
klopt("Galaxy A54" not in kd.rijen, "bluetooth: een gekoppeld apparaat staat niet meer in de lijst om te koppelen")
kd.rijen["Keyboard K380"].geklikt.emit()
wacht_ms(500)
klopt(kd.staat == "typ" and kd.code.text() == "503 172" and "Typ deze code op Keyboard K380" in kd.vraag_label.text(),
      f"bluetooth: toetsenbord: 'Typ deze code' met 503 172 ({kd.code.text()!r})")
wacht_ms(500)
klopt("2 van de 6 cijfers getypt" in kd.code_onder.text(), f"bluetooth: je ziet hoeveel cijfers getypt zijn ({kd.code_onder.text()!r})")
wacht_ms(1600)
wacht()
klopt(not kd.isVisible() and "Keyboard K380 is gekoppeld en verbonden" in bt.melding.tekst.text(),
      f"bluetooth: toetsenbord gekoppeld en verbonden ({bt.melding.tekst.text()!r})")

# een oud apparaat met een pincode
kd = open_koppel()
kd.koppelaar.pin_voor = "Galaxy Buds2"
kd.rijen["Galaxy Buds2"].geklikt.emit()
wacht_ms(600)
klopt(kd.staat == "pin" and kd.invoer.isVisible() and kd.invoer.text() == "0000" and kd.ja_knop.isEnabled()
      and "0000 of 1234" in kd.invoer_uitleg.text(), "bluetooth: pincode: het veld met 0000, en waar je hem vindt")
kd.invoer.setText("")
klopt(not kd.ja_knop.isEnabled(), "bluetooth: pincode: leeg kan niet")
# Annuleren tijdens het koppelen: terug naar de lijst, en de late uitslag doet niets meer
kd.weg_knop.click()
wacht_ms(500)
klopt(kd.isVisible() and kd.staat == "lijst" and kd.stapel.currentIndex() == 0,
      "bluetooth: Annuleren tijdens het koppelen gaat terug naar de lijst")
# geluid dat koppelt maar (nog) niet verbindt: dat zeggen, niet 'gelukt'
_oud_vv = bi.bt_vertrouw_en_verbind
bi.bt_vertrouw_en_verbind = lambda pad, adres="": (True, False)
kd.koppelaar.pin_voor = ""
kd.rijen["Galaxy Buds2"].geklikt.emit()
wacht_ms(1100)
wacht()
bi.bt_vertrouw_en_verbind = _oud_vv
klopt(not kd.isVisible() and "Verbinden lukte nog niet" in bt.melding.tekst.text(),
      f"bluetooth: gekoppeld maar niet verbonden: 'klik erop in de lijst' ({bt.melding.tekst.text()!r})")
wacht()

# niets gevonden, bluetooth uit tijdens het zoeken, de kaart weg
kd = sn.KoppelDialoog(bt, sn.NepKoppelaar())
kd.koppelaar.stop_klokken()
kd.open()
kd.niets.stop()
kd.toon_lijst_inhoud()
_titels = [r.titel.text() for r in kd.groep.findChildren(sn.Rij)]
klopt(_titels == ["Nog niets gevonden"], f"bluetooth: na een tijdje niets gevonden: dat zeggen, met wat je kunt doen ({_titels})")
kd.koppelaar.gevonden.emit(bi.BtStand("/org/bluez/hci0", False, "off", []))
klopt("Bluetooth staat uit" in kd.zoek_banner.tekst.text(), "bluetooth: uitgezet tijdens het zoeken: 'Bluetooth staat uit'")
kd.koppelaar.gevonden.emit(bi.BtStand())
klopt("doet het nu niet" in kd.zoek_banner.tekst.text(), "bluetooth: de kaart is weg: 'Bluetooth doet het nu niet'")
kd.reject()
klopt(kd.koppelaar.gesloten, "bluetooth: dicht = stoppen met zoeken")
wacht()

# bluetooth uit: eerst aanzetten; uit met een knop op de computer: zeggen wat je moet doen
bi._VB["bt"] = False
kd = open_koppel(300)
klopt(bi._VB["bt"] and kd is not None and kd.isVisible(), "bluetooth: staat bluetooth uit, dan zet 'koppelen' hem eerst aan")
kd.reject()
wacht()
bt.koppel_dialoog = None
_oud_hard = bi.bt_hard_uit
bi.bt_hard_uit = lambda: True
bt.koppel_nieuw()
wacht()
klopt(getattr(bt, "koppel_dialoog", None) is None and "vliegtuigstand" in bt.melding.tekst.text(),
      f"bluetooth: uit met een knop op de computer: geen venster, maar wat je moet doen ({bt.melding.tekst.text()!r})")
bt.toon((False, [], True, True))
klopt("vliegtuigstand" in bt.hoofd.uitleg.text(), "bluetooth: ook de regel bovenaan zegt dat de knop op de computer uit staat (N15)")
bi.bt_hard_uit = _oud_hard
subprocess.Popen = _oud_popen
klopt(not _kde, f"bluetooth: nergens een KDE-venster ({_kde})")
klopt("bluedevil" not in _bron_pag and "kcm_" not in (PY / "bugos_settings_netwerk.py").read_text(encoding="utf-8")
      and sn.BluetoothPagina.kde == "" and not hasattr(sn, "kde_instelling"),
      "bluetooth: de pagina verwijst niet meer naar KDE (bluedevil, kcm_bluetooth)")
klopt(sn.apparaat_icoon("input-mouse") == "muis" and sn.apparaat_icoon("audio-headset") == "geluid",
      "bluetooth: een gekoppelde muis heeft een muis-icoon (niet het bluetooth-teken)")

# 27. ons BlueZ-agent, zonder bus: met een nep-bericht
from PySide6.QtDBus import QDBusObjectPath  # noqa: E402


class NepBericht:
    def __init__(self):
        self.later = False

    def setDelayedReply(self, v):  # noqa: N802
        self.later = v

    def createReply(self, *a):  # noqa: N802, ARG002
        return ("antwoord",)

    def createErrorReply(self, naam, tekst):  # noqa: N802, ARG002
        return ("fout", naam)


class NepK(QObject):
    vraag = Signal(str, str, object)


agent = sn.BluetoothAgent()
verstuurd: list = []
agent.stuur = verstuurd.append
nk = NepK()
nk.pad = "/org/bluez/hci0/dev_X"
agent.koppelaar = nk
vragen: list = []
nk.vraag.connect(lambda *a: vragen.append(a))
_m = NepBericht()
agent.RequestConfirmation(QDBusObjectPath(nk.pad), 123456, _m)
klopt(_m.later and vragen == [("vergelijk", nk.pad, 123456)] and not verstuurd,
      "agent: 'zie je deze code?' wacht op jouw klik (geen antwoord vanzelf)")
agent.antwoord(True)
klopt(verstuurd == [("antwoord",)], "agent: 'Ja' stuurt het antwoord aan BlueZ")
_m2 = NepBericht()
agent.RequestConfirmation(QDBusObjectPath("/org/bluez/hci0/dev_ANDER"), 1, _m2)
klopt(verstuurd[-1] == ("fout", "org.bluez.Error.Rejected") and len(vragen) == 1,
      "agent: een vraag over een ander apparaat wordt meteen geweigerd")
_m3 = NepBericht()
agent.AuthorizeService(QDBusObjectPath(nk.pad), "0000110b-0000-1000-8000-00805f9b34fb", _m3)
_m4 = NepBericht()
agent.AuthorizeService(QDBusObjectPath("/org/bluez/hci0/dev_ANDER"), "x", _m4)
klopt(verstuurd[-2:] == [("antwoord",), ("fout", "org.bluez.Error.Rejected")],
      "agent: toestemming alleen voor het apparaat dat je koppelt")
QTimer.singleShot(0, lambda: agent.geef(42))
klopt(agent.RequestPasskey(QDBusObjectPath(nk.pad)) == 42 and vragen[-1][0] == "passkey",
      "agent: de code die je typt, gaat als getal terug (wachtlus)")
QTimer.singleShot(0, agent.Cancel)
klopt(agent.RequestPinCode(QDBusObjectPath(nk.pad)) == "" and vragen[-1][0] == "stop",
      "agent: BlueZ stopt (Cancel) tijdens een vraag: de wachtlus stopt, het venster hoort het")
agent.DisplayPasskey(QDBusObjectPath(nk.pad), 503172, 3)
klopt(vragen[-1] == ("typ", nk.pad, (503172, 3)), "agent: de code om te typen, met hoeveel er getypt zijn")
_m5 = NepBericht()
agent.RequestConfirmation(QDBusObjectPath(nk.pad), 7, _m5)
_n = len(verstuurd)
agent.annuleer()
klopt(verstuurd[_n:] == [("fout", "org.bluez.Error.Canceled")], "agent: venster dicht tijdens een vraag: 'Canceled'")
agent.koppelaar = None

# ==================================================================== eind ===
venster.close()
shutil.rmtree(TMP, ignore_errors=True)
print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
