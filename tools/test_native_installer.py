#!/usr/bin/env python3
"""Test van de live-stick en het installatieprogramma (iso_live/src): wifi, woorden, tijdzone, voortgang, klaar.

Alles gebeurt in een tijdelijke map met nep-programma's vooraan op PATH (nmcli, systemctl, liveinst, bugos-live ...);
er wordt niets aan de computer veranderd. Dit draait in de CI-container (Python 3.12, PySide6, geen node, geen
image). Met --beeld draait het IN de live-image (localhost/bugos-live:lokaal) en kijkt het naar de echte bestanden
van het installatieprogramma (zie beeld() onderaan).

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_native_installer.py
          podman run --rm --privileged -v <repo>:/repo:ro --entrypoint /usr/bin/bash localhost/bugos-live:lokaal \\
              -c "python3 /repo/tools/test_native_installer.py --beeld"
"""

from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "iso_live" / "src"
PY = ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"
TMP = Path(tempfile.mkdtemp(prefix="bugos-installer-test-"))
NEP = TMP / "nep"
LOG = TMP / "aanroepen.log"
NEP.mkdir()
BEELD = "--beeld" in sys.argv[1:]
fouten = 0


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


def nep(naam: str, inhoud: str) -> None:
    """Een nep-programma (bash) vooraan op PATH; het schrijft zijn naam en argumenten in het logboek."""
    pad = NEP / naam
    pad.write_text("#!/usr/bin/bash\n" f"printf '%s\\n' \"{naam} $*\" >> '{LOG}'\n" + inhoud + "\n",
                   encoding="utf-8", newline="\n")
    pad.chmod(0o755)


def log() -> list[str]:
    try:
        return LOG.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []


def schoon_pad() -> str:
    """PATH zonder de echte BugOS-programma's (bugos-*, liveinst): op een BugOS-computer staan die in /usr/bin, en dan
    zou de test die vinden in plaats van zijn eigen nep-versies. Per map een schaduwmap met al het andere."""
    mappen = []
    for i, m in enumerate(p for p in os.environ.get("PATH", "").split(os.pathsep) if p):
        bron = Path(m)
        try:
            namen = [x.name for x in bron.iterdir()]
        except OSError:
            continue
        if not any(n.startswith("bugos-") or n in ("liveinst", "kdialog") for n in namen):
            mappen.append(m)
            continue
        schaduw = TMP / f"pad-{i}"
        schaduw.mkdir(exist_ok=True)
        for n in namen:
            if not (n.startswith("bugos-") or n in ("liveinst", "kdialog")):
                try:
                    (schaduw / n).symlink_to(bron / n)
                except OSError:
                    pass
        mappen.append(str(schaduw))
    return os.pathsep.join(mappen)


def laad(naam: str, pad: Path):
    lader = importlib.machinery.SourceFileLoader(naam, str(pad))
    spec = importlib.util.spec_from_loader(naam, lader)
    m = importlib.util.module_from_spec(spec)
    sys.modules[naam] = m
    lader.exec_module(m)
    return m


def wacht(app, voorwaarde, seconden: float = 5.0) -> bool:
    eind = time.monotonic() + seconden
    while time.monotonic() < eind:
        app.processEvents()
        if voorwaarde():
            return True
        time.sleep(0.01)
    app.processEvents()
    return voorwaarde()


def bron(naam: str) -> str:
    return (SRC / naam).read_text(encoding="utf-8")


# ======================================================================================================== bugos-live ===
def test_live() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ["LANG"] = os.environ["LC_ALL"] = "en_US.UTF-8"   # Engels: de standaardtaal van de stick
    os.environ.pop("LANGUAGE", None)
    os.environ.pop("BUGOS_INSTELLINGEN_VOORBEELD", None)
    sys.path.insert(0, str(PY))
    # nmcli: antwoord uit twee bestandjes, zodat elke test zijn eigen toestand kiest.
    (TMP / "conn").write_text("none\n", encoding="utf-8")
    (TMP / "types").write_text("ethernet\nloopback\n", encoding="utf-8")
    nep("nmcli", f'case "$*" in *CONNECTIVITY*) cat \'{TMP}/conn\' ;; *TYPE*) [ -f \'{TMP}/types-kapot\' ] && exit 8; '
                 f'cat \'{TMP}/types\' ;; esac')
    nep("bugos-settings", "exit 0")
    live = laad("bugos_live", SRC / "bugos-live")
    import bugos_ui

    app = bugos_ui.maak_app("bugos-live", "bugos-live", ["bugos-live"])

    # 21. 'Wifi kiezen' opent BugOS Instellingen op de wifi-pagina, niet KDE.
    w = live.Live()
    w.timer.stop()   # de test kiest zelf wanneer er gekeken wordt
    wacht(app, lambda: not w._bezig)
    gestart = []
    echt_popen = live.subprocess.Popen
    live.subprocess.Popen = lambda cmd, **kw: gestart.append((list(cmd), kw.get("start_new_session")))
    try:
        w.wifi.click()
    finally:
        live.subprocess.Popen = echt_popen
    klopt(gestart == [(["bugos-settings", "wifi"], True)],
          f"21: 'Choose Wi-Fi' opent bugos-settings wifi (in een eigen sessie) ({gestart})")
    for naam in ("bugos-live", "bugos-install", "build.sh"):
        tekst = bron(naam)
        klopt("systemsettings" not in tekst and "kcm_" not in tekst, f"21: {naam} opent geen KDE-instellingen")

    def stand(conn: str, types: str | None, kapot: bool = False) -> tuple[bool, str]:
        (TMP / "conn").write_text(conn + "\n", encoding="utf-8")
        if types is not None:
            (TMP / "types").write_text(types, encoding="utf-8")
        if kapot:
            (TMP / "types-kapot").write_text("", encoding="utf-8")
        else:
            (TMP / "types-kapot").unlink(missing_ok=True)
        w._wifi_gevraagd = float("-inf")   # opnieuw naar de wifi-kaart vragen
        w.kijk_internet()
        wacht(app, lambda: not w._bezig)
        return not w.wifi.isHidden(), w.chip.text()

    # 22. De knop staat er alleen zonder internet EN met een wifi-kaart.
    zicht, chip = stand("none", "ethernet\nloopback\n")
    klopt(not zicht and "No internet" in chip, f"22: geen internet, geen wifi-kaart (kabel-pc): geen wifi-knop ({chip})")
    zicht, _ = stand("none", "ethernet\nwifi\nloopback\n")
    klopt(zicht, "22: geen internet, wel een wifi-kaart: de knop 'Choose Wi-Fi' staat er")
    zicht, chip = stand("full", None)
    klopt(not zicht and "online" in chip, f"22: online: geen wifi-knop, de chip zegt 'You are online' ({chip})")
    zicht, _ = stand("none", "ethernet\n", kapot=True)
    klopt(zicht, "22: nmcli kan de apparaten niet noemen: de knop staat er (Instellingen legt het verder uit)")
    # I7: niet elke 3 s twee keer nmcli in de GUI-draad: de wifi-kaart wordt hooguit elke 30 s gevraagd.
    stand("none", "wifi\n")
    voor = sum(1 for r in log() if "TYPE" in r)
    w.kijk_internet()
    wacht(app, lambda: not w._bezig)
    w.kijk_internet()
    wacht(app, lambda: not w._bezig)
    na = sum(1 for r in log() if "TYPE" in r)
    klopt(voor >= 1 and na == voor, f"22: de wifi-kaart wordt niet elke 3 s opnieuw gevraagd ({voor} -> {na})")
    nep("nmcli", "sleep 3; echo full")
    begin = time.monotonic()
    w._wifi_gevraagd = float("-inf")
    w.kijk_internet()
    duur = time.monotonic() - begin
    klopt(duur < 0.5, f"22: een trage nmcli laat het venster niet vastlopen ({duur:.2f} s)")
    wacht(app, lambda: not w._bezig, 8)
    w.close()


def main() -> int:
    os.environ["PATH"] = str(NEP) + os.pathsep + schoon_pad()
    test_live()
    shutil.rmtree(TMP, ignore_errors=True)
    print()
    print("Alles goed." if not fouten else f"{fouten} fout(en).")
    return 1 if fouten else 0


if __name__ == "__main__":
    sys.exit(main())
