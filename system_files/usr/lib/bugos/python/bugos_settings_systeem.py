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
from bugos_settings_onderdelen import Blad, schuifje
from PySide6.QtCore import Qt
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


# ======================================================= updates en meer ===

class UpdatesPagina(Blad):
    sleutel, icoon = "updates", "verversen"
    titel_nl, titel_en = "Updates en meer", "Updates and more"
    uitleg_nl = "Zet dingen aan of uit met één tik. Je kunt het altijd terugdraaien."
    uitleg_en = "Turn things on or off with one tap. You can always undo it."
    zoekwoorden = "update bijwerken versie terug game spel modus ontwikkelaar programmeren lichte stand startmenu snelmenu"

    def bouw(self) -> None:
        g = self.kaart(t("Updates", "Updates"))
        auto = status_van("bugos-updates") or not bestaat("bugos-updates")
        g.voeg(Rij("verversen", t("Updates vanzelf", "Automatic updates"),
                   t("Aan: BugOS houdt zichzelf stil bij. Uit: jij kiest wanneer.",
                     "On: BugOS quietly keeps itself up to date. Off: you choose when."),
                   schuifje(auto, lambda aan: None if bi.VOORBEELD else
                            start("pkexec", "/usr/bin/bugos-updates", "auto" if aan else "hand"))))
        knoppen = QWidget()
        kr = QHBoxLayout(knoppen)
        kr.setContentsMargins(52, 4, 14, 12)
        nu = Knop(t("Nu updaten", "Update now"), "gewoon", "lijn:verversen")
        nu.clicked.connect(lambda _c=False: None if bi.VOORBEELD else start("pkexec", "/usr/bin/bugos-updates", "nu"))
        terug = Knop(t("Terug naar de vorige versie", "Back to the previous version"), "stil", "lijn:terug")
        terug.clicked.connect(lambda _c=False: None if bi.VOORBEELD else
                              start("pkexec", "/usr/bin/bugos-updates", "terug"))
        kr.addWidget(nu)
        kr.addWidget(terug)
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
