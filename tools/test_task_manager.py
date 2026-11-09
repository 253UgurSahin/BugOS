#!/usr/bin/env python3
"""Test van BugOS Taakbeheer met een nep-/proc: er wordt niets op je eigen computer gestopt.

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_task_manager.py
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"))

TMP = Path(tempfile.mkdtemp(prefix="bugos-taken-test-"))
PROC = TMP / "proc"
os.environ.update(BUGOS_PROC=str(PROC), BUGOS_SYS=str(TMP / "sys"), LC_ALL="nl_NL.UTF-8", HOME=str(TMP / "thuis"),
                  XDG_CONFIG_HOME=str(TMP / "thuis" / ".config"), XDG_CONFIG_DIRS=str(TMP / "etc"),
                  XDG_DATA_HOME=str(TMP / "thuis" / ".local" / "share"), XDG_DATA_DIRS=str(TMP / "share"))
os.environ.pop("BUGOS_TAKEN_VOORBEELD", None)

fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


def schrijf(pad: Path, tekst: str) -> None:
    pad.parent.mkdir(parents=True, exist_ok=True)
    pad.write_text(tekst, encoding="utf-8")


GEBRUIKER = "/user.slice/user-1000.slice/user@1000.service"


def proces(pid: int, naam: str, groep: str, tijd: int = 10, rss: int = 1000, pss_kb: int = 0, kernel: bool = False,
           ppid: int = 1) -> None:
    vlaggen = 0x00200000 if kernel else 0x00400100
    velden = ["S", str(ppid), "0", "0", "0", "-1", str(vlaggen), "0", "0", "0", "0", str(tijd), "0", "0", "0",
              "20", "0", "1", "0", "100", "1000000", str(rss)] + ["0"] * 10
    schrijf(PROC / str(pid) / "stat", f"{pid} ({naam}) " + " ".join(velden) + "\n")
    schrijf(PROC / str(pid) / "cgroup", f"0::{groep}\n")
    if pss_kb:
        schrijf(PROC / str(pid) / "smaps_rollup", f"Rss: {pss_kb * 2} kB\nPss: {pss_kb} kB\n")


def processor(bezig: int, rust: int) -> None:
    schrijf(PROC / "stat", f"cpu  {bezig} 0 0 {rust} 0 0 0 0 0 0\ncpu0 1 0 0 1 0 0 0 0 0 0\ncpu1 1 0 0 1 0 0 0 0 0 0\n")


# --- een nep-computer
processor(1000, 9000)
schrijf(PROC / "meminfo", "MemTotal:       16000000 kB\nMemFree:  500000 kB\nMemAvailable:    8000000 kB\n")
schrijf(PROC / "diskstats", "   8       0 sda 100 0 2000 0 50 0 4000 0 0 120 0 0 0\n"
                            "   8       1 sda1 90 0 1800 0 40 0 3000 0 0 100 0 0 0\n"
                            "   7       0 loop0 5 0 80 0 0 0 0 0 0 1 0 0 0\n")
schrijf(PROC / "net" / "dev", "Inter-|   Receive\n face |bytes\n"
                              "    lo: 999999 1 0 0 0 0 0 0 999999 1 0 0 0 0 0 0\n"
                              "  eth0: 5000 10 0 0 0 0 0 0 3000 8 0 0 0 0 0 0\n"
                              "docker0: 70000 1 0 0 0 0 0 0 70000 1 0 0 0 0 0 0\n")
FIREFOX = f"{GEBRUIKER}/app.slice/app-flatpak-org.mozilla.firefox-12345.scope"
proces(100, "firefox", FIREFOX, tijd=100, pss_kb=200_000)
proces(101, "Isolated Web Co", FIREFOX, tijd=50, pss_kb=100_000, ppid=100)
proces(150, "notitie", f"{GEBRUIKER}/app.slice/app-org.voorbeeld.Notities-77.scope", tijd=5, pss_kb=20_000)
proces(200, "plasmashell", f"{GEBRUIKER}/session.slice/plasma-plasmashell.service", tijd=40, pss_kb=300_000)
proces(250, "discord", f"{GEBRUIKER}/app.slice/app-discord@autostart.service", tijd=3, pss_kb=90_000)
proces(300, "NetworkManager", "/system.slice/NetworkManager.service", tijd=7, rss=4000)
proces(2, "kthreadd", "/", kernel=True)
schrijf(TMP / "share" / "applications" / "org.mozilla.firefox.desktop",
        "[Desktop Entry]\nType=Application\nName=Firefox\nName[nl]=Firefox webbrowser\nIcon=org.mozilla.firefox\n")
schrijf(TMP / "share" / "applications" / "discord.desktop", "[Desktop Entry]\nName=Discord\nIcon=discord\n")

import bugos_tasks as bt  # noqa: E402

# 1. de computer meten
klopt(bt.cpu_tijden() == (1000, 10000), "processor: bezig en totaal uit /proc/stat")
klopt(bt.aantal_kernen() == 2, "processor: 2 kernen")
klopt(bt.geheugen() == (16000000 * 1024, 8000000 * 1024), "geheugen: totaal en beschikbaar")
klopt(bt.schijf_tellers() == (2000 * 512, 4000 * 512, 120), "schijf: alleen hele schijven (geen sda1, geen loop)")
klopt(bt.netwerk_tellers() == (5000, 3000), "internet: zonder lo en docker")
klopt(bt.temperatuur() is None and bt.videokaart() is None, "temperatuur en videokaart: niet aanwezig, geen fout")
schrijf(TMP / "sys" / "class" / "hwmon" / "hwmon0" / "name", "k10temp\n")
schrijf(TMP / "sys" / "class" / "hwmon" / "hwmon0" / "temp1_input", "52000\n")
schrijf(TMP / "sys" / "class" / "drm" / "card0" / "device" / "gpu_busy_percent", "37\n")
klopt(bt.temperatuur() == 52.0 and bt.videokaart() == 37.0, "temperatuur (52 °C) en videokaart (37%) als ze er zijn")

# 2. processen
lijst = bt.processen()
klopt(sorted(p.pid for p in lijst) == [100, 101, 150, 200, 250, 300], "processen: alles behalve de kernel zelf")
ff = next(p for p in lijst if p.pid == 100)
klopt(ff.geheugen == 200_000 * 1024 and ff.tijd == 100, "processen: geheugen (Pss) en processortijd")
klopt(next(p for p in lijst if p.pid == 300).geheugen == 4000 * bt.PAGINA, "processen: zonder Pss telt RSS")

# 3. soorten
klopt(bt.soort_van(FIREFOX)[:2] == ("app", "org.mozilla.firefox"), "soort: Flatpak-app")
klopt(bt.soort_van(f"{GEBRUIKER}/app.slice/app-org.kde.konsole@0b3e9c.service")[:2] == ("app", "org.kde.konsole"),
      "soort: app als dienst (KDE)")
klopt(bt.soort_van(f"{GEBRUIKER}/app.slice/app-org.kde.plasma\\x2dsystemmonitor-7.scope")[1]
      == "org.kde.plasma-systemmonitor", "soort: \\x2d wordt weer een streepje")
klopt(bt.soort_van(f"{GEBRUIKER}/session.slice/plasma-plasmashell.service")[0] == "achtergrond",
      "soort: bureaublad is achtergrond")
klopt(bt.soort_van("/system.slice/NetworkManager.service")[0] == "systeem", "soort: systeemdienst")

# 4. meten en groeperen (twee keer, zodat er 'per seconde' uit komt)
meter = bt.Meter()
meter.meet()
processor(1500, 9500)  # 500 bezig van 1000
proces(100, "firefox", FIREFOX, tijd=300, pss_kb=200_000)  # Firefox: 200 tikjes erbij
m = meter.meet()
klopt(abs(m["processor"] - 50.0) < 0.01, "meting: processor 50% (500 van 1000 tikjes)")
taken = {x.naam: x for x in m["taken"]}
firefox = taken.get("Firefox webbrowser")
klopt(firefox is not None and firefox.soort == "app" and sorted(firefox.pids) == [100, 101],
      "groeperen: Firefox met al zijn onderdelen als één programma (naam uit het .desktop-bestand)")
klopt(firefox is not None and abs(firefox.processor - 20.0) < 0.01 and firefox.geheugen == 300_000 * 1024,
      "groeperen: Firefox 20% kracht en 300 MB samen")
klopt("Notities" in taken and taken["Notities"].soort == "app", "groeperen: zonder .desktop een nette naam (Notities)")
klopt(taken["Bureaublad (Plasma)"].beschermd and taken["Bureaublad (Plasma)"].soort == "achtergrond",
      "groeperen: het bureaublad heeft een gewone naam en kan niet per ongeluk dicht")
klopt(taken["Netwerk"].soort == "systeem" and taken["Netwerk"].beschermd, "groeperen: systeem (Netwerk) beschermd")
klopt(next(x for x in m["taken"]).soort == "app", "volgorde: eerst de programma's")
# Lange namen kort de kernel in tot 15 tekens; die moeten toch beschermd zijn.
SESSIE = f"{GEBRUIKER}/session.slice"
lang = [bt.Proces(400, "xdg-desktop-por", 1, 1, 1, True, f"{SESSIE}/xdg-desktop-portal-kde.service"),
        bt.Proces(401, "polkit-kde-auth", 1, 1, 1, True, f"{SESSIE}/plasma-polkit-agent.service"),
        bt.Proces(402, "kwin_wayland_wr", 1, 1, 1, True, f"{SESSIE}/plasma-kwin_wayland.service"),
        bt.Proces(403, "startplasma-way", 1, 1, 1, True, "/user.slice/user-1000.slice/session-2.scope"),
        bt.Proces(404, "spotify", 1, 1, 1, True, f"{SESSIE}/spotify-helper.service")]
beschermd = {x.pids[0]: x.beschermd for x in bt.groepeer(lang, {})}
klopt(all(beschermd[p] for p in (400, 401, 402, 403)) and not beschermd[404],
      "beschermd: ook lange namen (xdg-desktop-portal-kde, kwin_wayland_wrapper, startplasma) en plasma-diensten")
# B002: de rest van wat de sessie nodig heeft (gezien in de echte BugOS live-sessie, met hun eenheden).
GEB = "/user.slice/user-1000.slice/user@1000.service"
kern = [bt.Proces(500, "dbus-broker-lau", 1, 1, 1, True, f"{GEB}/session.slice/dbus-broker.service"),
        bt.Proces(501, "(sd-pam)", 1, 1, 1, True, f"{GEB}/init.scope"),
        bt.Proces(502, "at-spi-bus-laun", 1, 1, 1, True, f"{GEB}/session.slice/at-spi-dbus-bus.service"),
        bt.Proces(503, "at-spi2-registr", 1, 1, 1, True,
                  f"{GEB}/session.slice/dbus-:1.28-org.a11y.atspi.Registry@0.service"),
        bt.Proces(504, "dconf-service", 1, 1, 1, True, f"{GEB}/session.slice/dconf.service"),
        bt.Proces(505, "xdg-document-po", 1, 1, 1, True, f"{GEB}/app.slice/xdg-document-portal.service"),
        bt.Proces(506, "xdg-permission-", 1, 1, 1, True, f"{GEB}/app.slice/xdg-permission-store.service"),
        bt.Proces(507, "ssh-agent", 1, 1, 1, True, f"{GEB}/app.slice/ssh-agent.service"),
        bt.Proces(508, "kdeconnectd", 1, 1, 1, True, f"{GEB}/app.slice/app-org.kde.kdeconnect.daemon@autostart.service")]
beschermd = {x.pids[0]: x.beschermd for x in bt.groepeer(kern, {})}
klopt(all(beschermd[p] for p in range(500, 507)),
      "beschermd: sessie-berichtenbus, gebruikersbeheer, toegankelijkheid, dconf en de Flatpak-portalen")
klopt(not beschermd[507] and not beschermd[508], "niet beschermd: gewone achtergrondhulpjes (ssh-agent, KDE Connect)")

# 5. advies in gewone woorden
klopt(bt.advies([10, 20, 30], 4, 16, m["taken"])[0] == "goed", "advies: rustig -> 'Alles loopt soepel'")
soort, zin = bt.advies([90, 95, 99], 4, 16, m["taken"])
klopt(soort == "let_op" and "Firefox webbrowser" in zin, "advies: druk -> noemt wie de meeste kracht gebruikt")
soort, zin = bt.advies([10], 15, 16, m["taken"])
klopt(soort == "let_op" and "geheugen" in zin and "Firefox webbrowser" in zin,
      "advies: geheugen bijna vol -> sluit iets, en noemt de grootste")

# 6. sluiten (veilig: alleen met nep-nummers)
klopt("w.closeWindow()" in bt.sluit_script([100, 101]) and "[100, 101]" in bt.sluit_script([101, 100]),
      "sluiten: KWin-scriptje sluit de vensters van precies deze programma's")
klopt(bt.stop([999999999]) == 0, "stoppen: een proces dat niet bestaat geeft geen fout")
klopt(bt.leeft([100, 999999]) == [100], "nog open: kijkt in /proc")

# 7. opstarten
etc = TMP / "etc" / "autostart"
schrijf(etc / "discord.desktop", "[Desktop Entry]\nType=Application\nName=Discord\nIcon=discord\nExec=discord\n")
schrijf(etc / "intern.desktop", "[Desktop Entry]\nType=Application\nName=Intern\nExec=x\nNoDisplay=true\n")
schrijf(etc / "gnome.desktop", "[Desktop Entry]\nType=Application\nName=Gnome\nExec=x\nOnlyShowIn=GNOME;\n")
eigen = TMP / "thuis" / ".config" / "autostart"
schrijf(eigen / "notities.desktop", "[Desktop Entry]\nType=Application\nName=Notities\nExec=notities\n")
lijst = {x.naam: x for x in bt.opstart_lijst()}
klopt(sorted(lijst) == ["Discord", "Notities"] and all(x.aan for x in lijst.values()),
      "opstarten: Discord en Notities staan aan; systeemonderdelen en GNOME-dingen zie je niet")
bt.zet_opstart(lijst["Discord"], False)
klopt((eigen / "discord.desktop").read_text().strip().endswith("Hidden=true") and (etc / "discord.desktop").exists(),
      "opstarten uit: alleen voor jou (het origineel blijft heel)")
klopt(not {x.naam: x for x in bt.opstart_lijst()}["Discord"].aan, "opstarten: Discord staat nu uit")
bt.zet_opstart({x.naam: x for x in bt.opstart_lijst()}["Discord"], True)
klopt(not (eigen / "discord.desktop").exists() and {x.naam: x for x in bt.opstart_lijst()}["Discord"].aan,
      "opstarten weer aan: zoals het was")
bt.zet_opstart(lijst["Notities"], False)
klopt("Hidden=true" in (eigen / "notities.desktop").read_text() and "Exec=notities" in (eigen / "notities.desktop")
      .read_text(), "opstarten uit (eigen programma): Hidden=true, de rest blijft")
# Een eigen aangepaste versie van een systeem-programma (andere opdracht, commentaar) blijft heel.
aangepast = "# mijn eigen versie\n[Desktop Entry]\nType=Application\nName=Discord\nExec=discord --start-minimized\n"
schrijf(eigen / "discord.desktop", aangepast)
d = {x.naam: x for x in bt.opstart_lijst()}["Discord"]
bt.zet_opstart(d, False)
tekst = (eigen / "discord.desktop").read_text()
klopt("Exec=discord --start-minimized" in tekst and "# mijn eigen versie" in tekst and "Hidden=true" in tekst,
      "opstarten uit (eigen aangepaste versie): eigen opdracht en commentaar blijven, alleen Hidden=true erbij")
bt.zet_opstart({x.naam: x for x in bt.opstart_lijst()}["Discord"], True)
tekst = (eigen / "discord.desktop").read_text()
klopt((eigen / "discord.desktop").exists() and "Exec=discord --start-minimized" in tekst and "Hidden=false" in tekst,
      "opstarten weer aan (eigen aangepaste versie): het bestand blijft, met Hidden=false")
klopt(not list(eigen.glob(".*bugos-nieuw")), "opstarten: geen tijdelijke bestanden achtergebleven")
# U075: staat een systeem-programma voor de hele computer uit (Hidden=true), dan kun je hem voor jezelf aanzetten.
schrijf(etc / "chat.desktop", "[Desktop Entry]\nType=Application\nName=Chat\nExec=chat --stil\nHidden=true\n")
c = {x.naam: x for x in bt.opstart_lijst()}["Chat"]
klopt(not c.aan, "U075: systeem-programma met Hidden=true staat uit")
bt.zet_opstart(c, True)
tekst = (eigen / "chat.desktop").read_text() if (eigen / "chat.desktop").exists() else ""
klopt({x.naam: x for x in bt.opstart_lijst()}["Chat"].aan and "Exec=chat --stil" in tekst and "Hidden=false" in tekst,
      "U075: aanzetten maakt een eigen kopie met Hidden=false (en hij staat echt aan)")
bt.zet_opstart({x.naam: x for x in bt.opstart_lijst()}["Chat"], False)
klopt(not {x.naam: x for x in bt.opstart_lijst()}["Chat"].aan, "U075: en weer uit")
bt.zet_opstart({x.naam: x for x in bt.opstart_lijst()}["Chat"], True)
klopt({x.naam: x for x in bt.opstart_lijst()}["Chat"].aan, "U075: na uit weer aan: staat aan")

# U125: wat BugOS start, krijgt zijn eigen systemd-scope (zoals KDE dat doet): dan staat het in Taakbeheer onder
# zijn eigen naam, en niet onder wie het startte (het snelmenu, Welkom, Instellingen).
import bugos_base  # noqa: E402

_rt = TMP / "runtime"
(_rt / "systemd").mkdir(parents=True)
(_rt / "systemd" / "private").write_text("")
_apps = TMP / "share-u125" / "applications"
_apps.mkdir(parents=True)
(_apps / "bugos-settings.desktop").write_text("[Desktop Entry]\nName=Settings\nExec=bugos-settings\n")
_oud_env = {k: os.environ.get(k) for k in ("XDG_RUNTIME_DIR", "XDG_DATA_DIRS")}
os.environ.update(XDG_RUNTIME_DIR=str(_rt), XDG_DATA_DIRS=str(TMP / "share-u125"))
_which = bugos_base.shutil.which
bugos_base.shutil.which = lambda n, *a, **k: "/usr/bin/" + n
_cmd = bugos_base.eigen_plek(("bugos-settings", "tijd"))
_niet = bugos_base.eigen_plek(("pkexec", "bugos-updates", "nu"))
(_apps / "rare naam+x.desktop").write_text("[Desktop Entry]\nName=X\nExec=x\n")
_raar = bugos_base.eigen_plek(("rare naam+x",))
bugos_base.shutil.which = _which
for _k, _v in _oud_env.items():
    if _v is None:
        os.environ.pop(_k, None)
    else:
        os.environ[_k] = _v
_eenheid = _cmd[5].split("=", 1)[1] if len(_cmd) > 6 else ""
klopt(_cmd[:3] == ["systemd-run", "--user", "--scope"] and _cmd[-2:] == ["bugos-settings", "tijd"]
      and bt.soort_van(f"/user.slice/user-1000.slice/user@1000.service/app.slice/{_eenheid}")[:2] == ("app", "bugos-settings")
      and _niet == ["pkexec", "bugos-updates", "nu"],
      f"U125: Instellingen starten in een eigen scope, die Taakbeheer als 'Instellingen' ziet ({_eenheid})")
klopt(_raar == ["rare naam+x"], "U146: een naam die systemd niet toestaat (spatie, +): gewoon starten, niet via systemd-run")

# 8. het venster (zonder scherm)
lader = importlib.machinery.SourceFileLoader("taakbeheer", str(ROOT / "system_files" / "usr" / "bin" /
                                                               "bugos-task-manager"))
spec = importlib.util.spec_from_loader("taakbeheer", lader)
tb = importlib.util.module_from_spec(spec)
sys.modules["taakbeheer"] = tb
lader.exec_module(tb)
app = tb.maak_app("bugos-task-manager", "bugos-task-manager", ["test"])
venster = tb.Taakbeheer()
try:
    venster.stop_meten()  # de test geeft zelf de metingen
    app.processEvents()
    venster.nieuwe_meting(m)
    app.processEvents()
    namen = sorted(r.taak.naam for r in venster.rijen.values())
    klopt(namen == ["Discord", "Firefox webbrowser", "Notities"],
          "venster: de open programma's staan in de lijst (ook Discord, dat vanzelf meestartte)")
    klopt(all(r.property("klikbaar") == "true" for r in venster.rijen.values()),
          "venster: elk programma is aan te klikken (dan komt 'Sluiten' onderin)")
    achter = {r.taak.naam: r for r in venster.achter_rijen.values()}
    klopt(achter["Bureaublad (Plasma)"].property("klikbaar") == "false"
          and achter["Netwerk"].property("klikbaar") == "false",
          "venster: het bureaublad en het netwerk kun je niet kiezen (horen bij BugOS)")
    klopt(venster.statussen[0].tekst.text() == "Alles loopt soepel." and venster.kort["processor"].text() == "50%",
          "venster: bovenaan hoe het gaat, en de processor")
    firefox_sleutel = next(s for s, r in venster.rijen.items() if r.taak.naam == "Firefox webbrowser")
    venster.kies(firefox_sleutel)
    klopt(not venster.balk.isHidden() and venster.balk.aantal.text() == "Firefox webbrowser"
          and venster.rijen[firefox_sleutel].property("gekozen") == "true",
          "kiezen: Firefox licht op en onderin staat de knoppenbalk met zijn naam")
    venster.kies(None)
    klopt(venster.balk.isHidden(), "kiezen: niets gekozen, balk weg")
    venster.nieuwe_meting(m)
    klopt(len(venster.rijen) == 3, "venster: een nieuwe meting werkt de regels bij (geen dubbele)")
    venster.ga_naar("opstarten")
    app.processEvents()
    rijen = venster.paginas["opstarten"].findChildren(tb.OpstartRij)
    klopt(len(rijen) == 3, "venster: Opstarten toont de programma's met een schuifje")
    # Sluiten mag het venster niet laten vastlopen, ook als KWin traag antwoordt.
    import time as _tijd  # noqa: E402
    _gestopt: list = []
    tb.Taakbeheer.sluit_vensters = staticmethod(lambda pids: (_tijd.sleep(1.5), True)[1])
    _oud_stop = tb.bt.stop
    tb.bt.stop = lambda pids, hard=False: _gestopt.append((sorted(pids), hard)) or len(pids)
    begin = _tijd.monotonic()
    venster.sluiten(venster.rijen[firefox_sleutel].taak)
    klopt(_tijd.monotonic() - begin < 0.5, "sluiten: het venster loopt niet vast terwijl KWin de vensters sluit")
    while venster.draden and _tijd.monotonic() - begin < 10:
        app.processEvents()
        _tijd.sleep(0.02)
    klopt(not venster.draden and "wordt gesloten" in venster.programmas.melding.tekst.text(),
          "sluiten: daarna de melding 'wordt gesloten'")
    # 'Geforceerd sluiten' kijkt pas bij het klikken welke processen er nu bij horen.
    venster.forceren_sleutel("bestaat-niet-meer", "Weg")
    klopt("al gesloten" in venster.programmas.melding.tekst.text() and not _gestopt,
          "geforceerd sluiten: programma is intussen weg, dan wordt er niets gestopt")
    venster.forceren_sleutel(firefox_sleutel, "Firefox webbrowser")
    while venster.draden and _tijd.monotonic() - begin < 20:
        app.processEvents()
        _tijd.sleep(0.02)
    klopt(_gestopt == [([100, 101], True)], "geforceerd sluiten: precies de processen die er nu bij Firefox horen")
    tb.bt.stop = _oud_stop
finally:
    venster.close()  # stopt ook het meten op de achtergrond

# U311: geminimaliseerd of verborgen meet Taakbeheer niet; weer in beeld meteen wel; stoppen gaat meteen.
import time as _tijd  # noqa: E402
import bugos_tasks_ui as _tu  # noqa: E402

_d = _tu.Meetdraad()
_tel = []
_d.meter.meet = lambda: _tel.append(1) or {}
_d.zet_zichtbaar(False)
_d.start()
_tijd.sleep(0.6)
_verborgen = len(_tel)
_d.zet_zichtbaar(True)
_tijd.sleep(0.4)
_zichtbaar = len(_tel)
_t0 = _tijd.time()
_d.stop()
_d.wait(3000)
klopt(_verborgen == 0 and _zichtbaar >= 1 and _tijd.time() - _t0 < 1.0,
      f"U311: Taakbeheer meet niet als het venster weg is, wel meteen weer in beeld, en stopt meteen ({_verborgen}, {_zichtbaar})")

shutil.rmtree(TMP, ignore_errors=True)  # alleen onze eigen tijdelijke testmap
print()
print("Alles goed." if not fouten else f"{fouten} fout(en).")
sys.exit(1 if fouten else 0)
