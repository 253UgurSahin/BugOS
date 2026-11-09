"""BugOS Instellingen: de pagina's Updates en meer, en Over deze computer (met wat ze over het
systeem vragen).
"""

from __future__ import annotations

import json
import os
import platform
import subprocess
import threading
from pathlib import Path

import bugos_config as bi
from bugos_ui import Kaart, Knop, Rij, bestaat, draai, label, start, t
from bugos_settings_onderdelen import Blad, Sein, op_achtergrond, schuifje
from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget


# ============================================================== toestand ===

def status_van(script: str, *voor: str) -> bool:
    """Vraag een bugos-script of iets aan staat."""
    if bi.VOORBEELD:
        return script in ("bugos-updates", "bugos-panel")
    if not bestaat(script):
        return False
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


def versie() -> str:
    try:
        return json.loads(Path("/usr/share/bugos/image-info.json").read_text())["versie"]
    except (OSError, ValueError, KeyError):
        return os.environ.get("BUGOS_VERSIE", "")


def systeem_info() -> list[tuple[str, str]]:
    """Gegevens voor 'Over deze computer', in gewone taal."""
    info: list[tuple[str, str]] = [(t("BugOS-versie", "BugOS version"), versie() or "?")]
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
    code, uit = draai("hostname", timeout=3)
    if code == 0 and uit.strip():
        info.append((t("Naam van deze computer", "Computer name"), uit.strip()))
    info.append((t("Linux-kern", "Linux kernel"), platform.release()))
    return info


def herstart() -> None:
    """Vraag netjes of je opnieuw wilt opstarten (het scherm van KDE: opgeslagen werk eerst)."""
    start("gdbus", "call", "--session", "--dest", "org.kde.LogoutPrompt", "--object-path", "/LogoutPrompt",
          "--method", "org.kde.LogoutPrompt.promptReboot")


# ======================================================= updates en meer ===

class UpdatesPagina(Blad):
    sleutel, icoon = "updates", "verversen"
    titel_nl, titel_en = "Updates en meer", "Updates and more"
    uitleg_nl = "Zet dingen aan of uit met één tik. Je kunt het altijd terugdraaien."
    uitleg_en = "Turn things on or off with one tap. You can always undo it."
    zoekwoorden = ("taakbalk fps fps-teller snelmenu update bijwerken versie terug game spel modus ontwikkelaar programmeren lichte stand startmenu "
                   "snelmenu updates update upgrade version roll back rollback game mode gaming developer coding "
                   "programming light mode start menu quick menu taskbar")

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
        auto = status_van("bugos-updates") or not bestaat("bugos-updates")
        self.auto = schuifje(auto, lambda aan: None if bi.VOORBEELD else self.updates("auto" if aan else "hand"))
        g.voeg(Rij("verversen", t("Updates vanzelf", "Automatic updates"),
                   t("Aan: BugOS houdt zichzelf stil bij. Uit: jij kiest wanneer.",
                     "On: BugOS quietly keeps itself up to date. Off: you choose when."), self.auto))
        knoppen = QWidget()
        kr = QHBoxLayout(knoppen)
        kr.setContentsMargins(52, 4, 14, 12)
        self.nu = Knop(t("Nu updaten", "Update now"), "gewoon", "lijn:verversen")
        self.nu.clicked.connect(lambda _c=False: None if bi.VOORBEELD else self.updates("nu"))
        self.terug = Knop(t("Terug naar de vorige versie", "Back to the previous version"), "stil", "lijn:terug")
        self.terug.clicked.connect(lambda _c=False: None if bi.VOORBEELD else self.vraag_terug())
        kr.addWidget(self.nu)
        kr.addWidget(self.terug)
        kr.addStretch(1)
        g.lay.addWidget(knoppen)
        self.bouw_rest()

    def vraag_terug(self) -> None:
        """Eerst zeggen wat 'terug' ook terugzet: wat sinds de update in het systeem veranderde, hoort bij de nieuwe
        versie (elke versie heeft zijn eigen /etc) (U368)."""
        from PySide6.QtWidgets import QMessageBox
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(t("Terug naar de vorige versie", "Back to the previous version"))
        box.setText(t("Terug naar de vorige versie?", "Go back to the previous version?"))
        box.setInformativeText(t(
            "Je bestanden blijven gewoon staan. Maar wat je sinds de laatste update in het systeem veranderde, gaat ook "
            "terug: een nieuw wachtwoord (dan geldt het oude weer), nieuwe gebruikers, en wifi-netwerken die je sindsdien "
            "toevoegde.",
            "Your files stay where they are. But what you changed in the system since the last update goes back too: "
            "a new password (the old one works again), new users, and Wi-Fi networks you added since."))
        ja = box.addButton(t("Terug", "Go back"), QMessageBox.ButtonRole.AcceptRole)
        annuleer = box.addButton(t("Annuleren", "Cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(annuleer)   # Enter uit gewoonte = niets doen, zoals bij weggooien in Bestanden (U380)
        box.exec()
        if box.clickedButton() is ja:
            self.updates("terug")

    def bouw_rest(self) -> None:
        """Alles onder de kaart Updates (spelen en werken, taakbalk, hulp)."""
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
                           t("Aan: de teller gaat meteen aan en uit met game-modus; MangoHud draait dan verborgen mee "
                             "in games. Uit: de teller komt pas na opnieuw inloggen.",
                             "On: the counter turns on and off at once with game mode; MangoHud then runs hidden in "
                             "games. Off: the counter only appears after you log in again."),
                           self.schakel("bugos-game-mode", "fps")))
        g = self.kaart(t("Taakbalk", "Taskbar"))
        for onderdeel, ic, (nl, en), (unl, uen) in (
                ("startmenu", "apps", ("BugOS-startmenu", "BugOS start menu"),
                 ("Uit: het gewone KDE-menu. Alt+F1 of de Windows-toets opent het.",
                  "Off: the regular KDE menu. Alt+F1 or the Windows key opens it.")),
                ("snelmenu", "schakelaar", ("Snelmenu op de taakbalk", "Quick menu on the taskbar"),
                 ("Grote knoppen voor wifi, bluetooth, game-modus, donker, niet storen en geluid.",
                  "Big buttons for Wi-Fi, Bluetooth, game mode, dark, do not disturb and sound."))):   # (U476)
            g.voeg(Rij(ic, t(nl, en), t(unl, uen), self.schakel("bugos-panel", onderdeel)))
        g = self.kaart(t("Hulp", "Help"))
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

    def schakel(self, script: str, *voor: str):
        """Een schakelaar voor een bugos-script (game-modus, lichte stand, startmenu, ...). Tijdens het omzetten op
        slot, en daarna opnieuw lezen wat er echt staat: lukte het niet (offline, Annuleren), dan springt hij terug,
        en snel aan-uit loopt niet door elkaar (U126)."""
        if not hasattr(self, "schakels"):
            self.schakels = {}
        schuif = schuifje(status_van(script, *voor), lambda aan: self.zet_schakel(script, voor, aan))
        self.schakels[(script, voor)] = schuif
        return schuif

    def zet_schakel(self, script: str, voor: tuple, aan: bool) -> None:
        if bi.VOORBEELD:
            return
        schuif = self.schakels[(script, voor)]
        schuif.setEnabled(False)
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

    def ververs(self) -> None:
        """Bij het openen van de pagina: lezen wat er nu echt aan staat (ook als het buiten Instellingen veranderde)."""
        schakels = dict(getattr(self, "schakels", {}))
        if not schakels or bi.VOORBEELD:
            return
        op_achtergrond(self, lambda: {k: status_van(k[0], *k[1]) for k in schakels},
                       lambda standen: [schakels[k].zet_stil(v is True) for k, v in (standen or {}).items()
                                        if schakels[k].isEnabled()])

    def updates(self, wat: str) -> None:
        """bugos-updates nu/terug/auto/hand als beheerder, zonder dat het venster vastloopt; daarna zeggen hoe
        het ging. (Een update kan lang duren: daarom QProcess en geen draai.)"""
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

        def af(code: int = 1, status=QProcess.ExitStatus.CrashExit) -> None:
            if gedaan:
                return
            gedaan.append(True)
            if wat in ("nu", "terug"):
                self.bezig = False   # alleen de update zelf; een schakelaar die tussendoor klaar is, telt niet
            else:
                self.bezig_keuze = False
            try:
                uit = bytes(proces.readAll()).decode(errors="ignore")
                proces.deleteLater()
                echt = code if status == QProcess.ExitStatus.NormalExit else 1
                self.klaar_met(wat, echt, uit)
                venster = self.window()
                if wat in ("auto", "hand") and getattr(venster, "sluit_na_update", False) and not self.bezig:
                    venster.close()
                if wat in ("nu", "terug") and getattr(venster, "sluit_na_update", False):
                    if echt == 0:
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
        if wat == "nu" and code == 0:
            # 'Nu updaten' werkt als beheerder alleen de apps voor iedereen bij. Ook je eigen apps (VS Code uit de
            # ontwikkelaarsmodus) en je .rpm/.deb-programma's: anders kregen die met 'Ik kies zelf' nooit een update (U475).
            QProcess.startDetached("flatpak", ["update", "--user", "--noninteractive", "--assumeyes"])
            QProcess.startDetached("/usr/bin/bugos-package", ["--bijwerken"])
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
            self.melding.toon(t("Dat lukte niet. Ben je online? Probeer het later nog eens.",
                                "That did not work. Are you online? Try again later."), "fout", seconden=0)
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
                regels = [r.strip() for r in uit.splitlines() if r.strip() and r.strip() != "bugos-blijft"]
                if regels:
                    tekst = regels[-1]
                op_achtergrond(self, lambda: status_van("bugos-updates"), lambda aan: self.auto.zet_stil(aan is True))
                if "bugos-blijft" in uit:
                    # Je draait de oude versie al: geen 'Nu opnieuw opstarten' nodig (U393).
                    self.melding.toon(tekst, "goed", seconden=0)
                    return
            self.melding.toon(tekst, "goed", t("Nu opnieuw opstarten", "Restart now"), herstart, seconden=0)


# ===================================================== over deze computer ===

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
        blok.addWidget(label(f"BugOS {versie()}".strip(), "groot", wrap=False))
        blok.addWidget(label(t("Gratis, veilig en open. Gebouwd op Fedora en KDE.",
                               "Free, safe and open. Built on Fedora and KDE."), "sub"))
        boven.lay.addLayout(blok, 1)
        self.lay.addWidget(boven)
        g = self.kaart()
        self.info = systeem_info()
        for sleutel, waarde in self.info:
            rij = QWidget()
            r = QHBoxLayout(rij)
            r.setContentsMargins(16, 14, 16, 14)
            r.addWidget(label(sleutel, "klein", wrap=False))
            r.addStretch(1)
            r.addWidget(label(waarde, "kop3", kopieerbaar=True), 0, Qt.AlignmentFlag.AlignRight)
            g.voeg(rij)
        kopieer = Knop(t("Gegevens kopiëren", "Copy details"), "gewoon", "lijn:kopieer")
        kopieer.clicked.connect(self.kopieer)
        self.lay.addWidget(kopieer, 0, Qt.AlignmentFlag.AlignLeft)

    def kopieer(self) -> None:
        QApplication.clipboard().setText("\n".join(f"{k}: {v}" for k, v in self.info))
        self.melding.toon(t("Gekopieerd. Je kunt het nu plakken in een bericht.",
                            "Copied. You can now paste it into a message."), "goed")
