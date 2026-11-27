"""BugOS Instellingen: de pagina's Updates, Gamen en programmeren, en Over deze computer (met wat ze over het
systeem vragen).
"""

from __future__ import annotations

import json
import os
import platform
import socket
import subprocess
import threading
from pathlib import Path

import bugos_config as bi
from bugos_ui import Kaart, Knop, Rij, bestaat, draai, label, start, t, vraag_ja
from bugos_settings_onderdelen import Blad, Doorloop, Sein, op_achtergrond, schuifje, tegelijk
from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget


# ============================================================== toestand ===

def status_van(script: str, *voor: str) -> bool:
    """Vraag een bugos-script of iets aan staat."""
    if bi.VOORBEELD:
        return script in ("bugos-updates", "bugos-panel", "bugos-schil")
    if not bestaat(script):
        return False
    # draai() vangt de uitvoer op (geen terminal): bugos-updates geeft dan het ene woord, geen zin voor mensen (A-15).
    _, uit = draai(script, *voor, "status", timeout=5)
    return uit.strip().endswith(("aan", "auto"))


def zet_script(script: str, aan: bool, aan_woord: str = "aan", uit_woord: str = "uit") -> None:
    if not bi.VOORBEELD:
        start(script, aan_woord if aan else uit_woord)


def op_live_stick() -> bool:
    """Draait BugOS vanaf de USB-stick om te proberen (niet geïnstalleerd)? Dan kun je niet updaten (U093)."""
    try:
        return "rd.live.image" in Path(os.environ.get("BUGOS_CMDLINE", "/proc/cmdline")).read_text().split()
    except OSError:
        return False


VOORBEELD_VERSIE = "44.20261110"


def versie() -> str:
    if bi.VOORBEELD:   # foto's en tests: een echte versie, niet die van de computer waarop ze draaien
        return VOORBEELD_VERSIE
    try:
        return json.loads(Path("/usr/share/bugos/image-info.json").read_text())["versie"]
    except (OSError, ValueError, KeyError):
        return os.environ.get("BUGOS_VERSIE", "")


def systeem_info() -> list[tuple[str, str]]:
    """Gegevens voor 'Over deze computer', in gewone taal."""
    info: list[tuple[str, str]] = [(t("BugOS-versie", "BugOS version"), versie() or "?")]
    if bi.VOORBEELD:   # dezelfde regels als echt, met geloofwaardige gegevens (niet de computer van de foto)
        return info + [(t("Processor", "Processor"), "Intel Core i5-1235U"), (t("Geheugen", "Memory"), "16 GB"),
                       (t("Opslag", "Storage"), t("180 GB vrij van 256 GB", "180 GB free of 256 GB")),
                       (t("Naam van deze computer", "Computer name"), "bugie-laptop"),
                       (t("Linux-kern", "Linux kernel"), "6.17.7-300.fc44.x86_64")]
    try:
        for regel in Path("/proc/cpuinfo").read_text().splitlines():
            if regel.startswith("model name"):
                info.append((t("Processor", "Processor"), regel.split(":", 1)[1].strip()))
                break
    except OSError:
        pass
    try:
        kb = int(next(r for r in Path("/proc/meminfo").read_text().splitlines()
                      if r.startswith("MemTotal")).split()[1])
        info.append((t("Geheugen", "Memory"), f"{kb / 1024 / 1024:.0f} GB"))
    except (OSError, StopIteration, ValueError):
        pass
    try:
        st = os.statvfs(str(Path.home()))
        vrij = st.f_bavail * st.f_frsize / 1000**3
        totaal = st.f_blocks * st.f_frsize / 1000**3
        info.append((t("Opslag", "Storage"),
                     t(f"{vrij:.0f} GB vrij van {totaal:.0f} GB", f"{vrij:.0f} GB free of {totaal:.0f} GB")))
    except OSError:
        pass
    # Wat 'hostname' zegt, maar zonder een programma te starten (dit gebeurt terwijl de pagina gebouwd wordt).
    naam = socket.gethostname().strip()
    if naam:
        info.append((t("Naam van deze computer", "Computer name"), naam))
    info.append((t("Linux-kern", "Linux kernel"), platform.release()))
    return info


def kan_terug() -> bool | None:
    """Is er een versie om naar terug te gaan? True, False, of None als we het niet weten (dan gewoon vragen).
    Zonder wachtwoord: 'bugos-updates kan-terug' leest alleen rpm-ostree status (B-24)."""
    if bi.VOORBEELD:
        return True
    if not bestaat("bugos-updates"):
        return None
    code, _ = draai("bugos-updates", "kan-terug", timeout=30)
    return True if code == 0 else False if code == 3 else None


# Wat rpm-ostree zegt als de updateserver (de registry) deze versie niet kent of niet wil geven: het internet werkt
# dan wél. Bijv. 'unable to retrieve auth token: invalid username/password: unauthorized' voor een image met een tag
# die er niet (meer) is, of 'manifest unknown' (B-01).
SERVER_WEIGERT = ("unauthorized", "manifest unknown", "name unknown", "denied:", "authentication required",
                  "invalid username/password", "status 404", "status code 404", "statuscode 404")
# Wat rpm-ostree, skopeo of curl zeggen als er geen internet is.
GEEN_INTERNET = ("could not resolve", "temporary failure in name resolution", "name or service not known",
                 "network is unreachable", "no route to host", "connection timed out", "i/o timeout",
                 "no such host", "connection refused", "tls handshake timeout")


def online() -> bool | None:
    """Werkt het internet? (NetworkManager kijkt zelf even: 'full' = ja.) None als we het niet weten."""
    if not bestaat("nmcli"):
        return None
    code, uit = draai("nmcli", "-t", "networking", "connectivity", "check", timeout=15)
    if code != 0 or not uit.strip():
        return None
    return uit.strip().splitlines()[-1].strip() == "full"


def update_fout(uit: str, internet: bool | None = None) -> str:
    """Waarom 'Nu updaten' niet lukte, in gewone woorden. Eerst stond hier altijd 'Ben je online?', ook als de computer
    gewoon online was maar de updateserver deze versie van BugOS niet kende: dan zocht je naar een internetprobleem
    dat er niet was (B-01). internet: wat online() zei (None = niet gevraagd of niet te weten)."""
    klein = uit.lower()
    # Een netwerkfout in de uitvoer, of NetworkManager zegt 'niet online': dan is het echt het internet.
    if internet is False or (internet is not True and any(w in klein for w in GEEN_INTERNET)):
        return t("Dat lukte niet: je computer is niet online. Maak verbinding met internet en probeer het nog eens.",
                 "That did not work: your computer is not online. Connect to the internet and try again.")
    if any(w in klein for w in SERVER_WEIGERT):
        return t("Dat lukte niet: de updateserver kent deze versie van BugOS niet. Je internet werkt wel; aan jouw kant "
                 "kun je hier niets aan doen.",
                 "That did not work: the update server does not know this version of BugOS. Your internet works; "
                 "there is nothing you can do about this on your side.")
    if internet is True:
        return t("Dat lukte niet, terwijl je internet wel werkt. Probeer het later nog eens.",
                 "That did not work, although your internet works. Try again later.")
    return t("Dat lukte niet. Ben je online? Probeer het later nog eens.",
             "That did not work. Are you online? Try again later.")


def herstart() -> None:
    """Vraag netjes of je opnieuw wilt opstarten (het scherm van KDE: opgeslagen werk eerst)."""
    start("gdbus", "call", "--session", "--dest", "org.kde.LogoutPrompt", "--object-path", "/LogoutPrompt",
          "--method", "org.kde.LogoutPrompt.promptReboot")


# ======================================================= updates en meer ===

class Schakelaars:
    """Schakelaars voor bugos-scripts (game-modus, lichte stand, startmenu, ...), voor elke pagina die ze toont."""

    def schakel(self, script: str, *voor: str):
        """Een schakelaar voor een bugos-script (game-modus, lichte stand, startmenu, ...). Tijdens het omzetten op
        slot, en daarna opnieuw lezen wat er echt staat: lukte het niet (offline, Annuleren), dan springt hij terug,
        en snel aan-uit loopt niet door elkaar (U126)."""
        if not hasattr(self, "schakels"):
            self.schakels = {}
            self.onbekend: set = set()
        # Hoe hij staat, vraagt ververs_schakels() op de achtergrond (bij het openen van de pagina). Eerst vroeg dit
        # het script hier, terwijl het venster gebouwd werd: zeven scripts (bugos-panel praat ook nog met Plasma)
        # voor je een venster zag. Tot het antwoord er is, staat de schakelaar op slot: niet omzetten voor we weten
        # hoe hij staat. (Voorbeeldstand: meteen, er draait niets.)
        bekend = bi.VOORBEELD
        schuif = schuifje(status_van(script, *voor) if bekend else False,
                          lambda aan: self.zet_schakel(script, voor, aan))
        self.schakels[(script, voor)] = schuif
        if not bekend:
            schuif.setEnabled(False)
            self.onbekend.add((script, voor))
        return schuif

    def zet_schakel(self, script: str, voor: tuple, aan: bool) -> None:
        if bi.VOORBEELD:
            return
        schuif = self.schakels[(script, voor)]
        schuif.setEnabled(False)
        self.onbekend.discard((script, voor))   # wat er na het omzetten staat, leest het omzetten zelf
        # Los gestart (in een eigen draad die wacht), zodat sluiten van Instellingen bijvoorbeeld het klaarzetten
        # van de ontwikkelaarsmodus (5-10 minuten) niet afbreekt.
        sein = Sein(self)
        sein.klaar.connect(lambda _c: op_achtergrond(
            self, lambda: status_van(script, *voor), lambda stand: (schuif.zet_stil(stand is True), schuif.setEnabled(True))))

        def wacht_op_script() -> None:
            try:
                code = subprocess.Popen([script, *voor, "aan" if aan else "uit"], stdout=subprocess.DEVNULL,
                                        stderr=subprocess.DEVNULL, start_new_session=True).wait()
            except OSError:
                code = 127
            try:
                sein.klaar.emit(code)
            except RuntimeError:   # Instellingen is al dicht
                pass

        threading.Thread(target=wacht_op_script, daemon=True).start()

    def ververs_schakels(self) -> None:
        """Bij het openen van de pagina: lezen wat er nu echt aan staat (ook als het buiten Instellingen veranderde)."""
        schakels = dict(getattr(self, "schakels", {}))
        if not schakels or bi.VOORBEELD:
            return
        sleutels = list(schakels)

        def klaar(standen) -> None:
            for k in sleutels:
                eerste = k in self.onbekend
                if k in (standen or {}) and (eerste or schakels[k].isEnabled()):   # (niet midden in het omzetten)
                    schakels[k].zet_stil(standen[k] is True)
                if eerste:   # nu weten we hoe hij staat; ging het lezen mis, dan toch niet voor altijd op slot
                    self.onbekend.discard(k)
                    schakels[k].setEnabled(True)
        # Tegelijk: elk script kost een paar honderd ms (bash, en bugos-panel vraagt het ook nog aan Plasma).
        op_achtergrond(self, lambda: dict(zip(sleutels, tegelijk(*[lambda k=k: status_van(k[0], *k[1])
                                                                     for k in sleutels]))), klaar)

    def ververs(self) -> None:
        self.ververs_schakels()


class UpdatesPagina(Schakelaars, Blad):
    sleutel, icoon = "updates", "verversen"
    titel_nl, titel_en = "Updates", "Updates"
    uitleg_nl = "BugOS houdt zichzelf bij. Ging er iets mis? Dan ga je met één knop terug."
    uitleg_en = "BugOS keeps itself up to date. Did something go wrong? One button takes you back."
    zoekwoorden = ("update bijwerken versie terug vorige versie taakbeheer back-up hulp "
                   "updates update upgrade version roll back rollback previous version task manager backup help")

    bezig = False   # loopt "Nu updaten" of "Terug" nog?

    def bouw(self) -> None:
        g = self.kaart(t("Updates", "Updates"))
        if op_live_stick():
            g.voeg(Rij("verversen", t("Updates", "Updates"),
                       t("Op de USB-stick om te proberen kun je niet updaten. Na het installeren gaat het vanzelf.",
                         "You cannot update on the try-out USB stick. Once installed, it happens automatically.")))
            self.auto = self.nu = self.terug = None
            self.bouw_rest()
            return
        # Hoe 'Updates vanzelf' staat, leest ververs() op de achtergrond (eerst gebeurde dat hier, tijdens het bouwen
        # van het venster). Tot dan op slot. (Voorbeeldstand: meteen.)
        self.auto_onbekend = not bi.VOORBEELD
        auto = (status_van("bugos-updates") or not bestaat("bugos-updates")) if bi.VOORBEELD else False
        self.auto = schuifje(auto, lambda aan: None if bi.VOORBEELD else self.updates("auto" if aan else "hand"))
        self.auto.setEnabled(not self.auto_onbekend)
        g.voeg(Rij("verversen", t("Updates vanzelf", "Automatic updates"),
                   t("Aan: BugOS houdt zichzelf stil bij. Uit: jij kiest wanneer.",
                     "On: BugOS quietly keeps itself up to date. Off: you choose when."), self.auto))
        knoppen = QWidget()
        # Een Doorloop: op een half scherm (640 px) komt 'Terug naar de vorige versie' onder 'Nu updaten', en springt
        # de rij minder in, in plaats van dat de pagina opzij schuift (B-02). 52 px: onder de tekst van de regel.
        kr = Doorloop(8, smal_links=14)
        knoppen.setLayout(kr)
        kr.setContentsMargins(52, 4, 14, 12)
        self.nu = Knop(t("Nu updaten", "Update now"), "gewoon", "lijn:verversen")
        self.nu.clicked.connect(lambda _c=False: None if bi.VOORBEELD else self.updates("nu"))
        self.terug = Knop(t("Terug naar de vorige versie", "Back to the previous version"), "stil", "lijn:terug")
        self.terug.clicked.connect(lambda _c=False: None if bi.VOORBEELD else self.vraag_terug())
        kr.addWidget(self.nu)
        kr.addWidget(self.terug)
        g.lay.addWidget(knoppen)
        self.bouw_rest()

    auto_onbekend = False   # 'Updates vanzelf' nog niet gelezen

    def ververs(self) -> None:
        super().ververs()
        if self.auto is None or not self.auto_onbekend:
            return

        def klaar(aan) -> None:
            if self.auto_onbekend and aan is not None and not getattr(self, "bezig_keuze", False):
                self.auto.zet_stil(aan is True)
            self.auto_onbekend = False
            if not getattr(self, "bezig_keuze", False):
                self.auto.setEnabled(True)
        op_achtergrond(self, lambda: status_van("bugos-updates") or not bestaat("bugos-updates"), klaar)

    def vraag_terug(self) -> None:
        """Eerst kijken of er wel een vorige versie is: zo niet, dan meteen dat zeggen, zonder eerst de ernstige
        waarschuwing (B-24). Dat kijken leest rpm-ostree (even geduld), dus op de achtergrond."""
        if bi.VOORBEELD:    # (foto's en tests: er is altijd een vorige versie)
            self.na_kan_terug(True)
            return
        if self.terug is not None:
            self.terug.setEnabled(False)   # niet twee keer klikken terwijl we kijken
        op_achtergrond(self, kan_terug, self.na_kan_terug)

    def na_kan_terug(self, kan: bool | None) -> None:
        if self.terug is not None and not self.bezig:
            self.terug.setEnabled(True)
        if kan is False:
            self.melding.toon(t("Er is geen oudere versie om naar terug te gaan.",
                                "There is no older version to go back to."))
            return
        self.vraag_terug_echt()

    def vraag_terug_echt(self) -> None:
        """Eerst zeggen wat 'terug' ook terugzet: wat sinds de update in het systeem veranderde, hoort bij de nieuwe
        versie (elke versie heeft zijn eigen /etc) (U368)."""
        if vraag_ja(self, t("Terug naar de vorige versie?", "Go back to the previous version?"), t(
                "Je bestanden blijven gewoon staan. Maar wat je sinds de laatste update in het systeem veranderde, gaat "
                "ook terug: een nieuw wachtwoord (dan geldt het oude weer), nieuwe gebruikers, en wifi-netwerken die je "
                "sindsdien toevoegde.",
                "Your files stay where they are. But what you changed in the system since the last update goes back "
                "too: a new password (the old one works again), new users, and Wi-Fi networks you added since."),
                t("Terug", "Go back"),
                enter_is_nee=True):   # Enter uit gewoonte = niets doen, zoals bij weggooien in Bestanden (U380)
            self.updates("terug")

    def bouw_rest(self) -> None:
        """Onder de kaart Updates: de handige hulpmiddelen."""
        g = self.kaart(t("Handige hulpmiddelen", "Handy tools"))
        for programma, ic, (nl, en), (unl, uen) in (
                ("bugos-task-manager", "grafiek", ("Taakbeheer", "Task Manager"),
                 ("Zien wat je computer doet, een programma sluiten dat vastzit.",
                  "See what your computer does, close a program that is stuck.")),
                ("bugos-backup", "opslag", ("Back-up", "Backup"),
                 ("Je bestanden veilig op een USB-schijf.", "Your files safe on a USB drive.")),
                ("bugos-help", "handig", ("Er werkt iets niet", "Something is not working"),
                 ("BugOS zoekt het probleem voor je.", "BugOS finds the problem for you."))):
            rij = Rij(ic, t(nl, en), t(unl, uen), klikbaar=True)
            rij.geklikt.connect(lambda p=programma: None if bi.VOORBEELD else start(p))
            g.voeg(rij)

    def updates(self, wat: str) -> None:
        """bugos-updates nu/terug/auto/hand als beheerder, zonder dat het venster vastloopt; daarna zeggen hoe
        het ging. (Een update kan lang duren: daarom QProcess en geen draai.)"""
        self.niet_sluiten = False   # (U490)
        if wat in ("nu", "terug"):
            self.nu.setEnabled(False)
            self.terug.setEnabled(False)
            bezig = (t("Bezig met updaten… Dit kan even duren. Laat Instellingen open tot het klaar is.",
                       "Updating… This can take a while. Keep Settings open until it is done.") if wat == "nu" else
                     t("Bezig met teruggaan naar de vorige versie…", "Going back to the previous version…"))
            self.melding.toon(bezig, seconden=0)
        proces = QProcess(self)
        proces.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        gedaan: list[bool] = []
        if wat in ("nu", "terug"):
            self.bezig = True   # Instellingen gaat pas dicht als dit klaar is (zie Instellingen.closeEvent)
        else:
            self.bezig_keuze = True   # ook 'vanzelf'/'zelf': sluiten zou de wachtwoordvraag afbreken (U212)
            if self.auto is not None:
                self.auto.setEnabled(False)   # niet nog een keer tijdens de wachtwoordvraag (twee vragen, de laatste wint) (U532)

        def af(code: int = 1, status=QProcess.ExitStatus.CrashExit) -> None:
            if gedaan:
                return
            gedaan.append(True)
            echt = code if status == QProcess.ExitStatus.NormalExit else 1
            if wat == "nu" and echt == 0:
                # Daarna ook je eigen apps en je .rpm/.deb-programma's, en pas dan 'Klaar' (en 'Nu opnieuw opstarten'):
                # opnieuw opstarten midden in die update kon een doosje half bijgewerkt achterlaten (U475, U480).
                uit0 = bytes(proces.readAll()).decode(errors="ignore")
                self.melding.toon(t("Bijna klaar: je eigen apps worden bijgewerkt…", "Almost done: updating your own apps…"),
                                  seconden=0)
                self.eigen_bijwerken(lambda: verder(echt, uit0))
                return
            verder(echt, None)

        def verder(echt: int, uit: str | None) -> None:
            if wat in ("nu", "terug"):
                self.bezig = False   # alleen de update zelf; een schakelaar die tussendoor klaar is, telt niet
            else:
                self.bezig_keuze = False
                if self.auto is not None:
                    self.auto.setEnabled(True)
            try:
                if uit is None:
                    uit = bytes(proces.readAll()).decode(errors="ignore")
                proces.deleteLater()
                self.klaar_met(wat, echt, uit)
                venster = self.window()
                if wat in ("auto", "hand") and getattr(venster, "sluit_na_update", False) and not self.bezig:
                    venster.close()
                if wat in ("nu", "terug") and getattr(venster, "sluit_na_update", False):
                    if echt == 0 and not getattr(self, "niet_sluiten", False):
                        # Je wilde al sluiten: de uitkomst (opnieuw opstarten, updates uit) als melding, dan dicht.
                        start("notify-send", "--app-name=BugOS", "--icon=system-software-update",
                              "--hint=string:desktop-entry:bugos-settings",   # (U323)
                              t("Instellingen", "Settings"), self.melding.tekst.text())
                        venster.close()
                    else:
                        venster.sluit_na_update = False   # mislukt: open laten, zodat je de melding ziet
            except RuntimeError:
                pass    # Instellingen ging dicht terwijl het nog bezig was: niemand meer om het te zeggen.

        proces.finished.connect(af)
        proces.errorOccurred.connect(lambda soort: af() if soort == QProcess.ProcessError.FailedToStart else None)
        proces.start("pkexec", ["/usr/bin/bugos-updates", wat])

    def eigen_bijwerken(self, na) -> None:
        """Je eigen apps (flatpak --user) en je .rpm/.deb-doosjes bijwerken, als jezelf (geen wachtwoord); daarna na()."""
        p = QProcess(self)
        p.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        klaar: list[bool] = []

        def einde(*_a) -> None:
            if klaar:
                return
            klaar.append(True)
            p.deleteLater()
            na()

        p.finished.connect(einde)
        p.errorOccurred.connect(lambda soort: einde() if soort == QProcess.ProcessError.FailedToStart else None)
        # Met een tijdslimiet: hangt het (internet weg), dan blijft Instellingen niet voor altijd 'bezig' (U487).
        p.start("bash", ["-c", "timeout 30m flatpak update --user --noninteractive --assumeyes; "
                         "[ -x /usr/bin/bugos-package ] && timeout 60m /usr/bin/bugos-package --bijwerken --nu; exit 0"])

    def klaar_met(self, wat: str, code: int, uit: str) -> None:
        if wat in ("auto", "hand"):
            # Lees opnieuw wat er echt staat: zei je 'Annuleren' bij het wachtwoord, dan springt de schakelaar terug.
            op_achtergrond(self, lambda: status_van("bugos-updates"), lambda aan: self.auto.zet_stil(aan is True))
            if code != 0 and code not in (126, 127):
                # bugos-updates zegt zelf waarom (bijv. 'kon niet bewaard worden'), in jouw taal (U422).
                regels = [r.strip() for r in uit.splitlines() if r.strip()]
                eigen = t("Dat lukte niet", "That did not work")
                self.melding.toon(regels[-1] if regels and regels[-1].startswith(eigen) and len(regels[-1]) < 300 else
                                  t("Dat lukte niet. Probeer het nog eens.", "That did not work. Try again."), "fout")
            return
        self.nu.setEnabled(True)
        self.terug.setEnabled(True)
        if code in (126, 127):
            # pkexec: 126 = je klikte Annuleren, 127 = geen toestemming.
            self.melding.toon(t("Niets gedaan: er was geen toestemming.", "Nothing done: permission was not given."))
        elif wat == "terug" and code == 3:
            # bugos-updates: er is nog geen vorige versie (dat zegt het zelf, in de taal van de gebruiker)
            regels = [r.strip() for r in uit.splitlines() if r.strip()]
            self.melding.toon(regels[-1] if regels else t("Er is nog geen vorige versie.",
                                                          "There is no previous version yet."))
        elif code != 0 and "Transaction in progress" in uit:
            # Er loopt al een update (vanzelf, of van een ander account): dat is geen 'ben je online?' (U389).
            self.melding.toon(t("Er loopt al een update. Probeer het over een paar minuten nog eens.",
                                "An update is already running. Try again in a few minutes."), "let_op", seconden=0)
        elif code != 0 and any(w in uit.lower() for w in ("no space left on device", "not enough disk space", "not enough free space", "not enough space")):
            # Een volle computer is geen 'ben je online?' (U411).
            self.melding.toon(t("Dat lukte niet: je computer is vol. Maak eerst ruimte (bijv. de prullenbak leegmaken in "
                                "Bestanden) en probeer het dan opnieuw.",
                                "That did not work: your computer is full. Make room first (for example empty the trash "
                                "in Files) and try again."), "fout", seconden=0)
        elif code != 0:
            # Meteen wat de uitvoer zegt; daarna nog even vragen of het internet werkt, en dan precies zeggen wat er
            # mis is (B-01): 'niet online' of 'de updateserver kent deze versie niet', niet altijd 'Ben je online?'.
            eerst = update_fout(uit)
            self.melding.toon(eerst, "fout", seconden=0)

            def precies(internet) -> None:
                beter = update_fout(uit, internet)
                try:
                    if self.melding.tekst.text() == eerst and beter != eerst:   # (niet over een nieuwere melding heen)
                        self.melding.toon(beter, "fout", seconden=0)
                except RuntimeError:
                    pass   # Instellingen is al dicht
            op_achtergrond(self, online, precies)
        elif wat == "nu" and "bugos-update-klaar" in uit:
            self.melding.toon(t("Er staat al een nieuwe BugOS klaar. Start de computer opnieuw op om hem te gebruiken.",
                                "A new BugOS is already waiting. Restart the computer to use it."),
                              "goed", t("Nu opnieuw opstarten", "Restart now"), herstart, seconden=0)
        elif wat == "nu" and "No upgrade available" in uit:
            self.melding.toon(t("BugOS is al helemaal bij.", "BugOS is already up to date."), "goed")
        else:
            tekst = (t("Klaar. Start de computer opnieuw op om de nieuwe versie te gebruiken.",
                       "Done. Restart the computer to use the new version.") if wat == "nu" else
                     t("Klaar. Start de computer opnieuw op om terug te gaan.", "Done. Restart the computer to go back."))
            if wat == "terug":
                # bugos-updates zegt zelf wat er gebeurde (al klaar, of: updates gaan nu niet meer vanzelf),
                # en zet misschien 'Updates vanzelf' uit: de schakelaar opnieuw lezen.
                regels = [r.strip() for r in uit.splitlines()
                          if r.strip() and r.strip() not in ("bugos-blijft", "bugos-niet-bewaard")]
                if regels:
                    tekst = regels[-1]
                if "bugos-niet-bewaard" in uit:
                    # Teruggezet, maar 'zelf updaten' kon niet bewaard worden: een waarschuwing, en Instellingen niet
                    # vanzelf dichtdoen (U490).
                    self.niet_sluiten = True
                    if "bugos-blijft" in uit:
                        self.melding.toon(tekst, "let_op", seconden=0)
                    else:
                        self.melding.toon(tekst, "let_op", t("Nu opnieuw opstarten", "Restart now"), herstart, seconden=0)
                    op_achtergrond(self, lambda: status_van("bugos-updates"), lambda aan: self.auto.zet_stil(aan is True))
                    return
                op_achtergrond(self, lambda: status_van("bugos-updates"), lambda aan: self.auto.zet_stil(aan is True))
                if "bugos-blijft" in uit:
                    # Je draait de oude versie al: geen 'Nu opnieuw opstarten' nodig (U393).
                    self.melding.toon(tekst, "goed", seconden=0)
                    return
            self.melding.toon(tekst, "goed", t("Nu opnieuw opstarten", "Restart now"), herstart, seconden=0)


# ===================================================== over deze computer ===

class SpelenPagina(Schakelaars, Blad):
    sleutel, icoon = "spelen", "spel"
    titel_nl, titel_en = "Gamen en programmeren", "Gaming and coding"
    uitleg_nl = "Game-modus, ontwikkelaarsmodus en de lichte stand. Aan of uit met één tik; uitzetten gooit niets weg."
    uitleg_en = "Game mode, developer mode and light mode. On or off with one tap; turning off deletes nothing."
    zoekwoorden = ("game spel spelen gamen modus fps fps-teller steam ontwikkelaar ontwikkelaarsmodus programmeren code vs code "
                   "containers lichte stand oude computer traag snel game mode gaming games fps counter developer "
                   "developer mode coding programming vscode containers docker podman distrobox light mode old computer slow fast")

    def bouw(self) -> None:
        g = self.kaart(t("Spelen en werken", "Play and work"))
        for script, ic, (nl, en), (unl, uen) in (
                ("bugos-game-mode", "spel", ("Game-modus", "Game mode"),
                 ("Volle kracht, meldingen stil en een FPS-teller in games.",
                  "Full power, quiet notifications and an FPS counter in games.")),
                ("bugos-developer", "code", ("Ontwikkelaarsmodus", "Developer mode"),
                 ("VS Code, containers en programmeertalen. Uitzetten gooit niets weg.",
                  "VS Code, containers and programming languages. Turning off deletes nothing.")),
                ("bugos-light-mode", "ster", ("Lichte stand", "Light mode"),
                 ("Zware effecten uit, zodat een oudere computer vlot blijft.",
                  "Heavy effects off, so an older computer stays fast."))):
            g.voeg(Rij(ic, t(nl, en), t(unl, uen), self.schakel(script)))
            if script == "bugos-game-mode":
                # De FPS-teller meteen (MangoHud altijd verborgen klaar in games) of pas na opnieuw inloggen.
                g.voeg(Rij("grafiek", t("FPS-teller meteen klaar", "FPS counter ready at once"),
                           t("Aan: de teller verschijnt meteen als je game-modus aanzet. "
                             "Uit: pas nadat je opnieuw inlogt.",
                             "On: the counter appears right away when you turn on game mode. "
                             "Off: only after you log in again."),
                           self.schakel("bugos-game-mode", "fps")))


class OverPagina(Blad):
    sleutel, icoon = "over", "laptop"
    titel_nl, titel_en = "Over deze computer", "About this computer"
    zoekwoorden = ("opslag schijfruimte schijf ruimte computernaam naam van deze computer over versie processor geheugen naam computer systeem info about about this computer version "
                   "processor cpu memory ram name computer system info information")

    def bouw(self) -> None:
        boven = Kaart(marge=24, ruimte=18, richting="h")
        logo = QLabel()
        logo.setPixmap(QPixmap("/usr/share/bugos/logo.svg").scaled(
            56, 56, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        boven.lay.addWidget(logo)
        blok = QVBoxLayout()
        blok.setSpacing(2)
        # De versie op de regel eronder (die breekt af): een lang versienummer in de grote letter schoof de pagina met
        # grote letters op een smal scherm opzij.
        blok.addWidget(label("BugOS", "groot", wrap=False))
        regel = t("Gratis, veilig en open. Gebouwd op Fedora en KDE.", "Free, safe and open. Built on Fedora and KDE.")
        v = versie()
        if v:
            regel = t("Versie", "Version") + " " + v + " · " + regel
        blok.addWidget(label(regel, "sub"))
        boven.lay.addLayout(blok, 1)
        self.lay.addWidget(boven)
        g = self.kaart()
        self.info = systeem_info()
        for sleutel, waarde in self.info:
            # De waarde krijgt de vrije breedte (rechts uitgelijnd): een lange processornaam past op één regel, en
            # breekt alleen af als het echt niet past. Marges zoals een gewone Rij.
            rij = QWidget()
            rij.setObjectName("info")
            r = QHBoxLayout(rij)
            r.setContentsMargins(14, 12, 12, 12)
            r.setSpacing(16)
            r.addWidget(label(sleutel, "klein", wrap=False), 0, Qt.AlignmentFlag.AlignVCenter)
            w = label(waarde, "kop3", kopieerbaar=True)
            w.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            r.addWidget(w, 1)
            g.voeg(rij)
        kopieer = Knop(t("Gegevens kopiëren", "Copy details"), "gewoon", "lijn:kopieer")
        kopieer.clicked.connect(self.kopieer)
        self.lay.addWidget(kopieer, 0, Qt.AlignmentFlag.AlignLeft)
        # De enige weg naar alle KDE-instellingen: voor wie meer wil, uit het zicht van de rest (Bugie-test).
        g = self.kaart(t("Voor gevorderden", "For advanced users"))
        meer = Rij("code", t("Geavanceerde instellingen", "Advanced settings"),
                   t("Alle instellingen van KDE, het onderdeel waar BugOS op draait. Hier hoef je normaal niet te zijn.",
                     "All settings of KDE, the part BugOS runs on. You normally never need to be here."), klikbaar=True)
        meer.geklikt.connect(lambda: None if bi.VOORBEELD else start("systemsettings"))
        g.voeg(meer)

    def kopieer(self) -> None:
        QApplication.clipboard().setText("\n".join(f"{k}: {v}" for k, v in self.info))
        self.melding.toon(t("Gekopieerd. Je kunt het nu plakken in een bericht.",
                            "Copied. You can now paste it into a message."), "goed")
