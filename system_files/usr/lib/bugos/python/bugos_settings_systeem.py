"""BugOS Instellingen: de pagina's Updates en meer, en Over deze computer (met wat ze over het
systeem vragen).
"""

from __future__ import annotations

import json
import os
import platform
from pathlib import Path

import bugos_config as bi
from bugos_ui import Kaart, Knop, Rij, bestaat, draai, label, start, t
from bugos_settings_onderdelen import Blad, op_achtergrond, schuifje
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
    zoekwoorden = "update bijwerken versie terug game spel modus ontwikkelaar programmeren lichte stand startmenu snelmenu"

    bezig = False   # loopt "Nu updaten" of "Terug" nog?

    def bouw(self) -> None:
        g = self.kaart(t("Updates", "Updates"))
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
        self.terug.clicked.connect(lambda _c=False: None if bi.VOORBEELD else self.updates("terug"))
        kr.addWidget(self.nu)
        kr.addWidget(self.terug)
        kr.addStretch(1)
        g.lay.addWidget(knoppen)
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
            g.voeg(Rij(ic, t(nl, en), t(unl, uen),
                       schuifje(status_van(script), lambda aan, s=script: zet_script(s, aan))))
            if script == "bugos-game-mode":
                # De FPS-teller meteen (MangoHud altijd verborgen klaar in games) of pas na opnieuw inloggen.
                g.voeg(Rij("grafiek", t("FPS-teller meteen klaar", "FPS counter ready at once"),
                           t("Aan: de teller gaat meteen aan en uit met game-modus; MangoHud draait dan verborgen mee "
                             "in games. Uit: de teller komt pas na opnieuw inloggen.",
                             "On: the counter turns on and off at once with game mode; MangoHud then runs hidden in "
                             "games. Off: the counter only appears after you log in again."),
                           schuifje(status_van("bugos-game-mode", "fps"),
                                    lambda aan: None if bi.VOORBEELD else start("bugos-game-mode", "fps",
                                                                                "aan" if aan else "uit"))))
        g = self.kaart(t("Taakbalk", "Taskbar"))
        for onderdeel, ic, (nl, en), (unl, uen) in (
                ("startmenu", "apps", ("BugOS-startmenu", "BugOS start menu"),
                 ("Uit: het gewone KDE-menu. Alt+F1 of de Windows-toets opent het.",
                  "Off: the regular KDE menu. Alt+F1 or the Windows key opens it.")),
                ("snelmenu", "schakelaar", ("Snelmenu op de taakbalk", "Quick menu on the taskbar"),
                 ("Grote knoppen voor wifi, bluetooth, geluid, donker en niet storen.",
                  "Big buttons for Wi-Fi, Bluetooth, sound, dark and do not disturb."))):
            g.voeg(Rij(ic, t(nl, en), t(unl, uen), schuifje(
                status_van("bugos-panel", onderdeel),
                lambda aan, o=onderdeel: None if bi.VOORBEELD else start("bugos-panel", o, "aan" if aan else "uit"))))
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

        def af(code: int = 1, status=QProcess.ExitStatus.CrashExit) -> None:
            if gedaan:
                return
            gedaan.append(True)
            if wat in ("nu", "terug"):
                self.bezig = False   # alleen de update zelf; een schakelaar die tussendoor klaar is, telt niet
            try:
                uit = bytes(proces.readAll()).decode(errors="ignore")
                proces.deleteLater()
                self.klaar_met(wat, code if status == QProcess.ExitStatus.NormalExit else 1, uit)
                venster = self.window()
                if getattr(venster, "sluit_na_update", False):
                    venster.close()   # je wilde al sluiten: nu het klaar is, gaat het dicht
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
                self.melding.toon(t("Dat lukte niet. Probeer het nog eens.", "That did not work. Try again."), "fout")
            return
        self.nu.setEnabled(True)
        self.terug.setEnabled(True)
        if code in (126, 127):
            # pkexec: 126 = je klikte Annuleren, 127 = geen toestemming.
            self.melding.toon(t("Niets gedaan: er was geen toestemming.", "Nothing done: permission was not given."))
        elif code != 0:
            self.melding.toon(t("Dat lukte niet. Ben je online? Probeer het later nog eens.",
                                "That did not work. Are you online? Try again later."), "fout", seconden=0)
        elif wat == "nu" and "No upgrade available" in uit:
            self.melding.toon(t("BugOS is al helemaal bij.", "BugOS is already up to date."), "goed")
        else:
            tekst = (t("Klaar. Start de computer opnieuw op om de nieuwe versie te gebruiken.",
                       "Done. Restart the computer to use the new version.") if wat == "nu" else
                     t("Klaar. Start de computer opnieuw op om terug te gaan.", "Done. Restart the computer to go back."))
            if wat == "terug":
                # bugos-updates zegt zelf wat er gebeurde (al klaar, of: updates gaan nu niet meer vanzelf),
                # en zet misschien 'Updates vanzelf' uit: de schakelaar opnieuw lezen.
                regels = [r.strip() for r in uit.splitlines() if r.strip()]
                if regels:
                    tekst = regels[-1]
                op_achtergrond(self, lambda: status_van("bugos-updates"), lambda aan: self.auto.zet_stil(aan is True))
            self.melding.toon(tekst, "goed", t("Nu opnieuw opstarten", "Restart now"), herstart, seconden=0)


# ===================================================== over deze computer ===

class OverPagina(Blad):
    sleutel, icoon = "over", "laptop"
    titel_nl, titel_en = "Over deze computer", "About this computer"
    zoekwoorden = "over versie processor geheugen naam computer systeem info"

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
