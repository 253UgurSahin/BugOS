"""BugOS: verbind met één opgeslagen netwerk en geef zelf het wachtwoord (een 'secret agent' van NetworkManager).

Waarom niet 'nmcli --ask': nmcli vraagt bij school- en werkwifi eerst de gebruikersnaam en plakt de eerste regel van
stdin daar achter (het wachtwoord kwam zo in de gebruikersnaam, die onversleuteld door de lucht gaat). En als nmcli geen
antwoord heeft, vraagt NetworkManager het volgende 'agent': dat is KDE (plasma-nm), met zijn eigen wachtwoordvenster.

Dit hulpje registreert zich als agent op dezelfde D-Bus-verbinding die de verbinding start. NetworkManager vraagt dan
eerst ons. We geven het wachtwoord één keer. Vraagt NetworkManager het opnieuw (REQUEST_NEW: het wachtwoord klopte
niet), dan zeggen we 'UserCanceled': dan stopt NetworkManager, zonder een tweede poging en zonder KDE-venster.

    python3 -I bugos_wifi_agent.py <uuid> [<seconden>]      (het wachtwoord op stdin, precies zoals getypt; leeg = geen)

Op stdout één regel JSON (zie uitslag()); code 0 als het verbonden is. Alleen python3-dbus en GLib (zitten in de image).
Het wachtwoord komt nooit op de opdrachtregel, in de uitvoer of in een log.
"""

from __future__ import annotations

import json
import sys

NM = "org.freedesktop.NetworkManager"
AGENT_IFACE = NM + ".SecretAgent"
AGENT_PAD = "/org/freedesktop/NetworkManager/SecretAgent"   # het pad waarop NetworkManager agents aanroept
AGENT_NAAM = "org.bugos.instellingen.wifi"

VRAAG_OPNIEUW = 0x2           # NM_SECRET_AGENT_GET_SECRETS_FLAG_REQUEST_NEW: het vorige wachtwoord werkte niet

# NMActiveConnectionState
ACTIEF, UIT = 2, 4

# Welk geheim hoort bij welk stuk van het profiel.
GEHEIM = {"802-1x": "password", "802-11-wireless-security": "psk"}


def antwoord(instelling: str, vlaggen: int, wachtwoord: str, al_gegeven: bool) -> dict | None:
    """Wat geven we NetworkManager als hij om een geheim vraagt? Een dict met het geheim, of None = 'UserCanceled'
    (stop: niet nog eens proberen, en niet een ander agent laten vragen)."""
    if vlaggen & VRAAG_OPNIEUW or al_gegeven or not wachtwoord or instelling not in GEHEIM:
        return None
    return {instelling: {GEHEIM[instelling]: wachtwoord}}


def uitslag(**kw) -> dict:
    """De regel die we op stdout zetten. gelukt; staat/reden: van de actieve verbinding (NMActiveConnectionState,
    ...StateReason); apparaat_reden: NMDeviceStateReason als het apparaat mislukte; gevraagd: zo vaak vroeg NM een
    geheim; opnieuw: NM vroeg het opnieuw (het wachtwoord klopte niet); zonder: NM vroeg het, maar we hadden er geen;
    te_laat: onze eigen tijd was op; fout/melding: een D-Bus-fout (naam en tekst) bij het starten."""
    u = {"gelukt": False, "staat": 0, "reden": 0, "apparaat_reden": 0, "gevraagd": 0, "opnieuw": False,
         "zonder": False, "te_laat": False, "fout": "", "melding": "", "bewaard": False}
    u.update(kw)
    return u


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1].startswith("-"):
        print(json.dumps(uitslag(fout="gebruik")))
        return 2
    uuid = argv[1]
    seconden = int(argv[2]) if len(argv) > 2 and argv[2].isdigit() else 45
    wachtwoord = sys.stdin.read()   # precies zoals getypt: geen spaties of tabs eraf
    try:
        import dbus
        import dbus.mainloop.glib
        import dbus.service
        from gi.repository import GLib
    except ImportError:
        print(json.dumps(uitslag(fout="geen_dbus")))
        return 1

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    lus = GLib.MainLoop()
    stand = uitslag()
    toestand = {"pad": None, "actief": None, "apparaten": set(), "gegeven": False, "klaar": False,
                "vroeg": {}, "mislukt": {}}   # signalen die binnenkwamen voordat we ons pad kenden

    class Geannuleerd(dbus.DBusException):
        _dbus_error_name = AGENT_IFACE + ".UserCanceled"

    class GeenGeheimen(dbus.DBusException):
        _dbus_error_name = AGENT_IFACE + ".NoSecrets"

    class Agent(dbus.service.Object):
        @dbus.service.method(AGENT_IFACE, in_signature="a{sa{sv}}osasu", out_signature="a{sa{sv}}")
        def GetSecrets(self, verbinding, pad, instelling, hints, vlaggen):  # noqa: N802, ARG002
            if toestand["pad"] is None or str(pad) != toestand["pad"]:
                raise GeenGeheimen("Niet onze verbinding")   # iets anders: dan mag een ander agent het vragen
            stand["gevraagd"] += 1
            if int(vlaggen) & VRAAG_OPNIEUW:
                stand["opnieuw"] = True
            if not wachtwoord:
                stand["zonder"] = True
            geheim = antwoord(str(instelling), int(vlaggen), wachtwoord, toestand["gegeven"])
            if geheim is None:
                raise Geannuleerd("BugOS vraagt het zelf")
            toestand["gegeven"] = True
            return dbus.Dictionary({k: dbus.Dictionary(v, signature="sv") for k, v in geheim.items()},
                                   signature="sa{sv}")

        @dbus.service.method(AGENT_IFACE, in_signature="os", out_signature="")
        def CancelGetSecrets(self, pad, instelling):  # noqa: N802, ARG002
            pass

        @dbus.service.method(AGENT_IFACE, in_signature="a{sa{sv}}o", out_signature="")
        def SaveSecrets(self, verbinding, pad):  # noqa: N802, ARG002
            pass

        @dbus.service.method(AGENT_IFACE, in_signature="a{sa{sv}}o", out_signature="")
        def DeleteSecrets(self, verbinding, pad):  # noqa: N802, ARG002
            pass

    def klaar(**kw) -> None:
        if toestand["klaar"]:
            return
        toestand["klaar"] = True
        stand.update(kw)
        lus.quit()

    def eigenschap(pad: str, iface: str, naam: str):
        return bus.get_object(NM, pad).Get(iface, naam, dbus_interface="org.freedesktop.DBus.Properties")

    def actief_veranderd(staat, reden, pad=None) -> None:
        if toestand["actief"] is None:
            toestand["vroeg"][str(pad)] = (int(staat), int(reden))
            return
        if str(pad) != toestand["actief"]:
            return
        stand["staat"], stand["reden"] = int(staat), int(reden)
        if int(staat) == ACTIEF:
            klaar(gelukt=True)
        elif int(staat) == UIT:
            klaar(gelukt=False)

    def apparaat_veranderd(nieuw, oud, reden, pad=None) -> None:  # noqa: ARG001
        if int(nieuw) != 120:   # 120 = NM_DEVICE_STATE_FAILED
            return
        toestand["mislukt"][str(pad)] = int(reden)
        if str(pad) in toestand["apparaten"]:
            stand["apparaat_reden"] = int(reden)

    def te_laat() -> bool:
        if toestand["actief"]:
            try:
                bus.get_object(NM, "/org/freedesktop/NetworkManager").DeactivateConnection(
                    toestand["actief"], dbus_interface=NM)
            except dbus.DBusException:
                pass
        klaar(te_laat=True)
        return False

    def gestart(actief) -> None:
        toestand["actief"] = str(actief)
        try:
            toestand["apparaten"] = {str(a) for a in eigenschap(str(actief), NM + ".Connection.Active", "Devices")}
            staat = int(eigenschap(str(actief), NM + ".Connection.Active", "State"))
        except dbus.DBusException:
            staat = 0
        for a in toestand["apparaten"]:
            if a in toestand["mislukt"]:
                stand["apparaat_reden"] = toestand["mislukt"][a]
        if str(actief) in toestand["vroeg"]:
            actief_veranderd(*toestand["vroeg"][str(actief)], pad=str(actief))
        if staat == ACTIEF:
            klaar(gelukt=True, staat=staat)
        elif staat == UIT:
            klaar(gelukt=False, staat=staat)

    def mislukt(e) -> None:
        klaar(fout=e.get_dbus_name() or "", melding=str(e.get_dbus_message() or ""))

    try:
        Agent(bus, AGENT_PAD)
        manager = bus.get_object(NM, "/org/freedesktop/NetworkManager/AgentManager")
        manager.RegisterWithCapabilities(AGENT_NAAM, dbus.UInt32(0), dbus_interface=NM + ".AgentManager")
        bus.add_signal_receiver(actief_veranderd, signal_name="StateChanged",
                                dbus_interface=NM + ".Connection.Active", path_keyword="pad")
        bus.add_signal_receiver(apparaat_veranderd, signal_name="StateChanged",
                                dbus_interface=NM + ".Device", path_keyword="pad")
        instellingen = bus.get_object(NM, "/org/freedesktop/NetworkManager/Settings")
        toestand["pad"] = str(instellingen.GetConnectionByUuid(uuid, dbus_interface=NM + ".Settings"))
        bus.get_object(NM, "/org/freedesktop/NetworkManager").ActivateConnection(
            dbus.ObjectPath(toestand["pad"]), dbus.ObjectPath("/"), dbus.ObjectPath("/"), dbus_interface=NM,
            reply_handler=gestart, error_handler=mislukt)
    except dbus.DBusException as e:
        print(json.dumps(uitslag(fout=e.get_dbus_name() or "", melding=str(e.get_dbus_message() or ""))))
        return 1
    GLib.timeout_add_seconds(max(5, seconden), te_laat)
    lus.run()
    if not stand["apparaat_reden"] and len(toestand["mislukt"]) == 1:   # het apparaat was al van de verbinding los
        stand["apparaat_reden"] = next(iter(toestand["mislukt"].values()))

    # Gelukt met een nieuw wachtwoord: staat het nu ook echt in het profiel? NetworkManager bewaart wat een agent geeft
    # (password-flags 0); zo niet, dan zetten we het er zelf in (via D-Bus, niet via een opdrachtregel).
    if stand["gelukt"] and wachtwoord and toestand["gegeven"]:
        stand["bewaard"] = bewaar(bus, dbus, toestand["pad"], wachtwoord)
    try:
        manager.Unregister(dbus_interface=NM + ".AgentManager")
    except dbus.DBusException:
        pass
    print(json.dumps(stand))
    return 0 if stand["gelukt"] else 1


def bewaar(bus, dbus, pad: str, wachtwoord: str) -> bool:
    verbinding = bus.get_object(NM, pad)
    iface = NM + ".Settings.Connection"
    try:
        instellingen = verbinding.GetSettings(dbus_interface=iface)
        stuk = "802-1x" if "802-1x" in instellingen else "802-11-wireless-security"
        try:
            geheimen = verbinding.GetSecrets(stuk, dbus_interface=iface)
            if str(geheimen.get(stuk, {}).get(GEHEIM[stuk], "")) == wachtwoord:
                return True
        except dbus.DBusException:
            pass
        instellingen[stuk][GEHEIM[stuk]] = wachtwoord
        verbinding.Update2(instellingen, dbus.UInt32(0x1), dbus.Dictionary({}, signature="sv"), dbus_interface=iface)
        return True
    except (dbus.DBusException, KeyError):
        return False


if __name__ == "__main__":
    sys.exit(main(sys.argv))
