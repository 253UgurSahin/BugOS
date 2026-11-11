#!/usr/bin/env python3
"""Test van pakket 'printers': printers toevoegen, instellen, pauzeren, verwijderen, de wachtrij, scannen,
standaardprogramma's ('Een ander soort bestand...') en meldingen per app, zonder KDE.

Er verandert niets aan je computer: de opdrachten worden opgevangen (bi.draai en bi.cups_draai vervangen), of
draaien met nep-programma's in een tijdelijke map. De uitvoer in de tests komt letterlijk van een echte BugOS
(CUPS 2.4.19, zie de spec 'printers' en de review).

Gebruik:  QT_QPA_PLATFORM=offscreen python3 tools/test_native_printers.py
"""

from __future__ import annotations

import getpass
import importlib.machinery
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = ROOT / "system_files" / "usr" / "lib" / "bugos" / "python"
BIN = ROOT / "system_files" / "usr" / "bin"
sys.path.insert(0, str(PY))
TMP = Path(tempfile.mkdtemp(prefix="bugos-printers-test-"))
os.environ.update(BUGOS_INSTELLINGEN_VOORBEELD="1", LC_ALL="nl_NL.UTF-8", HOME=str(TMP), BUGOS_SYS=str(TMP / "sys"),
                  XDG_CONFIG_HOME=str(TMP / ".config"))
os.environ.pop("LANGUAGE", None)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.dont_write_bytecode = True

import bugos_config as bi  # noqa: E402

fouten = 0
IK = getpass.getuser()


def klopt(voorwaarde: bool, wat: str) -> None:
    global fouten
    print(("OK    " if voorwaarde else "FOUT  ") + wat)
    if not voorwaarde:
        fouten += 1


def vang_cups(functie, *args, antwoord=lambda cmd: (0, ""), beheerder: bool = True):
    """Roep functie aan zonder voorbeeldstand; vang elke opdracht (bi.draai en bi.cups_draai). Geeft
    (opdrachten, timeouts, uitkomst). beheerder: wat bi.ben_beheerder() zegt."""
    oud = (bi.VOORBEELD, bi.draai, bi.cups_draai, bi.ben_beheerder, shutil.which)
    opdrachten: list = []
    tijden: list = []

    def nep(*cmd, **kw):
        opdrachten.append(cmd)
        tijden.append(kw.get("timeout"))
        return antwoord(cmd)
    bi.VOORBEELD = False
    bi.draai = bi.cups_draai = nep
    bi.ben_beheerder = lambda: beheerder
    shutil.which = lambda naam, *a, **k: "/usr/bin/" + naam
    try:
        uit = functie(*args)
    finally:
        bi.VOORBEELD, bi.draai, bi.cups_draai, bi.ben_beheerder, shutil.which = oud
    return opdrachten, tijden, uit


# ========================================================== 1. bouwstenen (stap 1) ===

# Test 8: cups_fout op echte foutmeldingen van CUPS.
FOUTEN = [
    (1, "lpadmin: Forbidden\n", "verboden"),
    (1, "cupsdisable: Operation failed: client-error-forbidden\n", "verboden"),
    (1, "cancel: cancel-job failed: Forbidden\n", "verboden"),
    (1, "lpadmin: Unable to connect to 192.0.2.10:631: Connection timed out\n", "onbereikbaar"),
    (1, "lpadmin: Unable to connect to 127.0.0.1:9: Host is down\n", "onbereikbaar"),
    (1, "ipptool: Unable to connect to printer.local on port 631 - Name or service not known\n", "onbereikbaar"),
    (1, "lpadmin: Unable to create PPD: Printer does not support required IPP attributes or document formats.\n",
     "geen_driverless"),
    (1, "lpadmin: The printer or class does not exist.\n", "bestaat_niet"),
    (1, "lpadmin: Printer name can only contain printable characters.\n", "anders"),
    (0, "lpadmin: Printer drivers are deprecated and will stop working in a future version of CUPS.\n", "ok"),
    (124, "", "onbereikbaar"),
]
klopt(all(bi.cups_fout(c, u) == s for c, u, s in FOUTEN),
      "test 8: cups_fout leest elke echte foutmelding goed: " + ", ".join(
          f"{u.strip()[:30]!r}={bi.cups_fout(c, u)}" for c, u, s in FOUTEN if bi.cups_fout(c, u) != s))

# Test 10: wie geen beheerder is, gaat via pkexec (met het echte pad van lpadmin); Annuleren = 'geweigerd'.
opd, tijd, uit = vang_cups(bi.als_beheerder, "lpadmin", "-p", "Q", "-E", beheerder=False,
                           antwoord=lambda c: (126, "Error executing command as another user: Request dismissed"))
klopt(opd == [("pkexec", "/usr/bin/lpadmin", "-p", "Q", "-E")] and uit[0] == "geweigerd" and tijd[0] >= 180,
      f"test 10: geen beheerder: één keer pkexec /usr/bin/lpadmin, Annuleren = niets gedaan ({opd}, {uit[0]}, {tijd})")
opd, _, uit = vang_cups(bi.als_beheerder, "lpadmin", "-x", "Q", beheerder=False,
                        antwoord=lambda c: (127, "Error executing command as another user: Not authorized\n"))
klopt(uit[0] == "geweigerd", "R11: pkexec 'Not authorized' (127) is 'geen toestemming', niet 'alleen een beheerder'")
_oud_which = shutil.which
bi.VOORBEELD, _oud_cd, _oud_bb = False, bi.cups_draai, bi.ben_beheerder
_gedraaid: list = []
bi.cups_draai = lambda *c, **k: (_gedraaid.append(c), (127, ""))[1]
bi.ben_beheerder = lambda: False
shutil.which = lambda n, *a, **k: None if n == "pkexec" else "/usr/bin/" + n
_zonder = bi.als_beheerder("lpadmin", "-x", "Q")
bi.VOORBEELD, bi.cups_draai, bi.ben_beheerder, shutil.which = True, _oud_cd, _oud_bb, _oud_which
klopt(_zonder[0] == "anders" and not _gedraaid, "R11: zonder pkexec: 'lukte niet', niet 'geen toestemming'")

# Test 11: beheerder, maar CUPS zegt Forbidden (net in wheel gezet): één keer pkexec, niet meer.
opd, _, uit = vang_cups(bi.als_beheerder, "lpadmin", "-p", "Q", "-E",
                        antwoord=lambda c: (1, "lpadmin: Forbidden\n"))
klopt([c[0] for c in opd] == ["lpadmin", "pkexec"] and uit[0] == "verboden",
      f"test 11: beheerder met 'Forbidden': daarna precies één keer pkexec ({[c[0] for c in opd]})")
opd, _, uit = vang_cups(bi.als_beheerder, "lpadmin", "-p", "Q", "-E",
                        antwoord=lambda c: (0, "lpadmin: Printer drivers are deprecated and will stop working in a "
                                               "future version of CUPS.\n"))
klopt(opd == [("lpadmin", "-p", "Q", "-E")] and uit[0] == "ok",
      "test 11: beheerder (wheel): lpadmin zonder pkexec en zonder wachtwoord; een waarschuwing is geen fout")
try:
    bi.als_beheerder("sh", "-c", "x")
    klopt(False, "als_beheerder weigert alles behalve lpadmin en lpinfo")
except ValueError:
    klopt(True, "als_beheerder weigert alles behalve lpadmin en lpinfo")

# Test 16: lees_lpstat: de reden onder de printer, gepauzeerd, de plek, en 'wacht op de printer' (review R6).
lp = ("printer HP_LaserJet is idle.  enabled since Mon 03 Nov 2026\n\tDescription: HP LaserJet van Bugie\n\tLocation: kamer\n"
      "printer Canon_PIXMA disabled since Sun 02 Nov 2026 -\n\tPaused\n\tDescription: Canon PIXMA\n"
      "printer Brother now printing Brother-12.  enabled since Mon\n")
prs = bi.lees_lpstat(lp, "system default destination: HP_LaserJet\n")
klopt([(p.omschrijving, p.staat, p.standaard) for p in prs]
      == [("HP LaserJet van Bugie", "klaar", True), ("Canon PIXMA", "gestopt", False), ("Brother", "bezig", False)],
      "test 16: de oude uitkomst van lees_lpstat (test_settings) blijft hetzelfde")
klopt(prs[1].gepauzeerd and prs[1].reden == "Paused" and prs[0].locatie == "kamer" and not prs[0].reden
      and not prs[0].gepauzeerd, "test 16: '\\tPaused' = gepauzeerd; '\\tLocation: kamer' = de plek; Description is geen reden")
lp2 = ("printer review_q now printing review_q-8.  enabled since Wed 11 Nov 2026 09:12:01 CET\n"
       "\tThe printer may not exist or is unavailable at this time.\n\tForm mounted:\n\tDescription: Review\n"
       "printer oud disabled since Wed 11 Nov 2026 -\n\tUnable to connect to printer; will retry in 30 seconds...\n"
       "printer printers_br disabled since Wed Nov 11 08:18:32 2026 -\n\tRejecting Jobs\n"
       "printer leeg is idle.  enabled since Wed\n\tForm mounted:\n\tBanner required\n")
prs2 = bi.lees_lpstat(lp2, "no system default destination\n")
klopt(prs2[0].staat == "bezig" and prs2[0].onbereikbaar and not prs2[0].gepauzeerd,
      "R6: een printer die uit staat ('may not exist or is unavailable'): wacht op de printer, niet eeuwig 'aan het printen'")
klopt(prs2[1].staat == "gestopt" and not prs2[1].gepauzeerd and prs2[1].reden.startswith("Unable to connect")
      and prs2[1].onbereikbaar, "test 16: gestopt na een fout ('Unable to connect to printer') is niet gepauzeerd")
klopt(prs2[2].gepauzeerd and prs2[3].reden == "" and not prs2[3].onbereikbaar,
      "test 16: 'Rejecting Jobs' telt als gepauzeerd; 'Form mounted:' en 'Banner required' zijn geen reden")
_vreemd = bi.lees_lpstat("printer X is idle.  enabled\n\tDescription: <b>Kantoor</b>\tmet tab\n", "")
klopt(_vreemd[0].omschrijving == "<b>Kantoor</b> met tab", "test 16: een tab in een omschrijving wordt een spatie")

# Test 17: verder, pauzeren, verwijderen.
opd, _, uit = vang_cups(bi.hervat_printer, "HP_LaserJet")
klopt(opd == [("lpadmin", "-p", "HP_LaserJet", "-E")] and uit == "ok",
      f"test 17: verder printen = lpadmin -p Q -E (zet aan en neemt weer aan) ({opd})")
opd, _, uit = vang_cups(bi.hervat_printer, "HP_LaserJet", beheerder=False, antwoord=lambda c: (0, ""))
klopt(opd == [("pkexec", "/usr/bin/lpadmin", "-p", "HP_LaserJet", "-E")],
      f"test 17: verder printen zonder beheerder: via pkexec, nooit cupsenable ({opd})")
opd, _, uit = vang_cups(bi.pauzeer_printer, "HP_LaserJet")
klopt(opd == [("cupsdisable", "HP_LaserJet")] and uit == "ok", f"test 17: pauzeren = cupsdisable, niet via pkexec ({opd})")
opd, _, uit = vang_cups(bi.verwijder_printer, "HP_LaserJet")
klopt(opd == [("lpadmin", "-x", "HP_LaserJet"), ("lpoptions", "-x", "HP_LaserJet")] and uit == "ok",
      f"test 17: verwijderen = lpadmin -x, en daarna je eigen keuzes weg (lpoptions -x) ({opd})")
opd, _, uit = vang_cups(bi.verwijder_printer, "HP_LaserJet", antwoord=lambda c: (1, "lpadmin: Forbidden\n"))
klopt([c[0] for c in opd] == ["lpadmin", "pkexec"] and uit == "verboden",
      "test 17: verwijderen mislukt: lpoptions -x niet, en de pagina hoort 'verboden'")
_alle: list = []
for f in (bi.hervat_printer, bi.pauzeer_printer, bi.verwijder_printer):
    for slecht in ("-x", ".verborgen", "a b", "x;reboot", "", "a" * 200):
        o, _, u = vang_cups(f, slecht)
        _alle += o + ([("uitkomst", u)] if u != "anders" else [])
klopt(not _alle, f"test 17: een vreemde naam ('-x', 'a b', 'x;reboot' ...) wordt nooit doorgegeven ({_alle[:2]})")

# Test 20: lees_lpq (echte uitvoer), ook met een afgeknipte eigenaar (review R10).
lpq = ("printers_br is not ready\nRank    Owner   Job     File(s)                         Total Size\n"
       "1st     bugie   1       Testpagina                      1024 bytes\n"
       "2nd     bugie   2       Brief aan de bank.pdf           1024 bytes\n"
       "3rd     review_ 5       Brief: aan de bank.pdf  1024 bytes\n"
       "active  bugie   7       Foto's\tvan oma                 20480 bytes\n")
q = bi.lees_lpq(lpq)
klopt(q.get(1) == ("Testpagina", False) and q.get(2) == ("Brief aan de bank.pdf", False)
      and q.get(5) == ("Brief: aan de bank.pdf", False) and q.get(7, ("", False))[1],
      f"test 20: lpq: titels per taaknummer, 'active' = wordt nu geprint ({q})")

# Test 21: taken: alleen je eigen documenten (uit lpstat -o), de titel uit lpq; annuleren met het nummer.
lang = "review_ptmp"


def antwoord_taken(c, ik=IK):
    if c[:2] == ("lpstat", "-o"):
        return 0, (f"HP-12 {ik} 1024 Wed Nov 11 08:18:33 2026\nHP-13 unknown 2048 Wed Nov 11 08:18:34 2026\n"
                   f"Canon_PIXMA-3 {ik} 1024 Wed Nov 11 08:18:35 2026\n")
    if c[:2] == ("lpq", "-P") and c[2] == "HP":
        return 0, (f"HP is ready and printing\nRank    Owner   Job     File(s)                         Total Size\n"
                   f"active  {ik[:7]:<7} 12      Brief aan de bank.pdf           1024 bytes\n"
                   f"2nd     unknown 13      unknown                         2048 bytes\n")
    return 0, ""


opd, _, tk = vang_cups(bi.taken, antwoord=antwoord_taken)
klopt([(x.printer, x.id, x.titel, x.actief) for x in tk] == [("HP", 12, "Brief aan de bank.pdf", True),
                                                             ("Canon_PIXMA", 3, "", False)],
      f"test 21: alleen eigen documenten, de titel per nummer uit lpq, '' als CUPS hem niet weet ({tk})")
import getpass as _gp  # noqa: E402

_oud_user = _gp.getuser
_gp.getuser = lambda: lang
opd, _, tk = vang_cups(bi.taken, antwoord=lambda c: antwoord_taken(c, lang))
_gp.getuser = _oud_user
klopt([(x.id, x.titel) for x in tk] == [(12, "Brief aan de bank.pdf"), (3, "")],
      "R10: een inlognaam van meer dan 7 tekens (lpq knipt hem af): je documenten staan er toch")
opd, _, ok = vang_cups(bi.annuleer_taak, "HP", 12)
klopt(opd == [("cancel", "HP-12")] and ok, f"test 21: annuleren = cancel HP-12 ({opd})")
opd, _, ok = vang_cups(bi.annuleer_taak, "-a", 1)
opd2, _, ok2 = vang_cups(bi.annuleer_taak, "HP;reboot", 1)
klopt(not opd and not opd2 and not ok and not ok2, "test 21: een vreemd taaknummer wordt nooit doorgegeven")

# Test 22: wachtrij leegmaken: eerst 'cancel -u jij' (U158); weigert CUPS dat (geen beheerder), dan één voor één.
opd, _, ok = vang_cups(bi.wachtrij_leegmaken)
klopt(opd == [("cancel", "-u", IK)] and ok, f"test 22: leegmaken als beheerder: precies 'cancel -u {IK}' (U158)")


def antwoord_leeg(c):
    if c[:2] == ("cancel", "-u"):
        return 1, ""
    return antwoord_taken(c)


opd, _, ok = vang_cups(bi.wachtrij_leegmaken, antwoord=antwoord_leeg)
klopt(opd[0] == ("cancel", "-u", IK) and ("cancel", "HP-12") in opd and ("cancel", "Canon_PIXMA-3") in opd
      and ("cancel", "HP-13") not in opd and ok,
      f"test 22: 'cancel -u' geweigerd (geen beheerder): elk eigen document met zijn nummer, die van anderen niet ({opd})")

# Test 26: cups_draai echt, met nep-programma's: geen invoer (dus nooit wachten op een wachtwoord), stderr erbij.
nep = TMP / "bin"
nep.mkdir()
(nep / "lpadmin").write_text('#!/usr/bin/bash\nif [ -t 0 ]; then echo TTY; fi\nif read -t 1 x; then echo GOT_INPUT; fi\n'
                             'echo "lpadmin: Forbidden" >&2\nexit 1\n', encoding="utf-8")
(nep / "traag").write_text("#!/usr/bin/bash\nexec sleep 5\n", encoding="utf-8")
(nep / "zegt").write_text('#!/usr/bin/bash\necho uit\necho fout >&2\n', encoding="utf-8")
for f in nep.iterdir():
    f.chmod(0o755)
os.environ["PATH"] = f"{nep}:{os.environ.get('PATH', '')}"
bi.VOORBEELD = False
code, tekst = bi.cups_draai("lpadmin", "-p", "Q")
controle = subprocess.run([str(nep / "lpadmin")], input="x\n", capture_output=True, text=True, timeout=10).stdout
klopt(code == 1 and "Forbidden" in tekst and "GOT_INPUT" not in tekst and "TTY" not in tekst and "GOT_INPUT" in controle,
      f"test 26: cups_draai geeft stderr mee en een lege invoer; met invoer zou het nep-lpadmin die lezen ({code}, {tekst!r})")
code, _ = bi.cups_draai("traag", timeout=1)
klopt(code == 124, f"test 26: te lang = 124 ({code})")
klopt(bi.cups_draai("zegt", fout=False) == (0, "uit\n") and bi.cups_draai("bestaat-niet-xyz") == (127, ""),
      "test 26: fout=False leest alleen stdout (review R5); een programma dat er niet is = 127")
bi.VOORBEELD = True

# Voorbeeldstand: verder, pauzeren, verwijderen veranderen de voorbeeldprinters (voor de foto's), zonder iets te draaien.
bi._VB["printers"] = None
klopt(bi.pauzeer_printer("HP_LaserJet") == "ok" and bi.printers()[0].gepauzeerd
      and bi.hervat_printer("HP_LaserJet") == "ok" and bi.printers()[0].staat == "klaar",
      "voorbeeld: pauzeren en verder printen")
bi._VB["printers"] = None


# ================================================= 2. instellingen van een printer (stap 2) ===

# Test 18: de keuzes van drie echte soorten wachtrijen (hpcups, brlaser, IPP Everywhere). Uit het onderzoekslog.
HPCUPS = ("PageSize/Media Size: Card3x5 L L.FB Hagaki A6 A5 A5.FB A5.Duplex Photo4x6 Letter Letter.FB Letter.Duplex "
          "*A4 A4.FB A4.Duplex 8.5x13 Legal EnvA2 EnvDL Env10 Custom.WIDTHxHEIGHT\n"
          "Duplex/Double-Sided Printing: DuplexNoTumble DuplexTumble *None\n"
          "ColorModel/Output Mode: *RGB CMYGray KGray\n"
          "OutputMode/Print Quality: *Normal Draft Best Photo\n"
          "MediaType/Media Type: *Plain Glossy TransparencyFilm\n"
          "OptionDuplex/Duplexer Installed: *False True\n")
BRLASER = ("PageSize/Media Size: *A4 A5 A6 B5 B6 EnvC5 EnvMonarch EnvDL Executive Legal Letter\n"
           "Duplex/2-Sided Printing: *None DuplexNoTumble DuplexTumble\n")
EVERYWHERE = ("ColorModel/Output Mode: Gray *RGB\nDuplex/Duplex: *None DuplexNoTumble DuplexTumble\n"
              "cupsPrintQuality/cupsPrintQuality: Draft *Normal\n"
              "PageSize/Media Size: (null).Borderless 100x150mm.Borderless 100x150mm *A4 A4.Borderless Letter\n")
o = bi.printer_keuzes(bi.lees_lpoptions_l(HPCUPS))
klopt(o is not None and [k for k, _ in o.papieren] == ["A4", "A5", "A6", "Letter", "Legal", "Photo4x6", "EnvDL", "Env10"]
      and o.papier == "A4" and o.zijden is None and o.kleur == "kleur" and o.kleur_waarde == {"kleur": "RGB", "zw": "KGray"},
      f"test 18: hpcups: papier in vaste volgorde zonder .FB/.Duplex, geen twee kanten zonder duplex-eenheid, "
      f"kleur RGB / zwart-wit KGray ({o})")
o = bi.printer_keuzes(bi.lees_lpoptions_l(BRLASER))
klopt(o is not None and o.papier == "A4" and [k for k, _ in o.papieren] == ["A4", "A5", "A6", "Letter", "Legal", "EnvDL"]
      and o.zijden == "een" and o.zijden_waarde == {"een": "None", "twee": "DuplexNoTumble"} and o.kleur is None,
      f"test 18: brlaser: A4, twee kanten mogelijk, geen kleurkeuze; 'B5' (de Japanse maat) niet (review R19) ({o})")
o = bi.printer_keuzes(bi.lees_lpoptions_l(EVERYWHERE))
klopt(o is not None and [k for k, _ in o.papieren] == ["A4", "Letter", "100x150mm"] and o.kleur == "kleur"
      and o.kleur_waarde == {"kleur": "RGB", "zw": "Gray"} and o.zijden == "een",
      f"test 18: IPP Everywhere: '(null).Borderless' telt niet, foto 10 x 15 = 100x150mm, Gray/RGB ({o})")
o = bi.printer_keuzes(bi.lees_lpoptions_l("Duplex/2-Sided: None *DuplexTumble DuplexNoTumble\n"
                                          "PageSize/Media: *Folio A4\n"))
klopt(o.zijden == "twee" and o.zijden_waarde["twee"] == "DuplexTumble" and o.papieren[-1] == ("Folio", "Folio"),
      "test 18: korte kant (DuplexTumble) blijft zo; een papier dat BugOS niet kent maar wel gekozen is, staat erbij")
klopt(bi.lees_lpoptions_l("lpoptions: Unable to get PPD file for nope: No such file or directory\n") == {}
      and bi.printer_keuzes({}) is None, "test 18: 'Unable to get PPD file' (met code 0!) = niets te kiezen")

# Test 19: bewaren: alleen wat veranderd is; een beheerder voor iedereen, anderen alleen voor zichzelf.
(TMP / ".cups").mkdir(exist_ok=True)
(TMP / ".cups" / "lpoptions").write_text("Default Q\nDest Q Duplex=None PageSize=Letter\nDest R ColorModel=Gray\n")


def lees_hp(c):
    return (0, HPCUPS) if c[:2] == ("lpoptions", "-p") and "-l" in c else (0, "")


vang_cups(bi.printer_opties, "Q", antwoord=lambda c: (0, BRLASER) if "-l" in c else (0, ""))
opd, _, uit = vang_cups(bi.zet_printer_opties, "Q", {"PageSize": "A4", "Duplex": "DuplexNoTumble"})
klopt(opd == [("lpadmin", "-p", "Q", "-o", "Duplex=DuplexNoTumble"), ("lpoptions", "-p", "Q", "-r", "Duplex")]
      and uit == "ok",
      f"test 19: beheerder: alleen Duplex (A4 stond al), en je eigen oude keuze 'Duplex=None' weg ({opd})")
opd, _, uit = vang_cups(bi.zet_printer_opties, "Q", {"Duplex": "Nonsense"})
klopt(not opd and uit == "anders", "test 19: een waarde die de printer niet kent: niets doorgegeven (lpadmin slikt hem stil)")
opd, _, uit = vang_cups(bi.zet_printer_opties, "Q", {"Duplex": "DuplexNoTumble", "PageSize": "A5"}, "Printer in de gang",
                        beheerder=False)
klopt(opd == [("lpoptions", "-p", "Q", "-o", "Duplex=DuplexNoTumble", "-o", "PageSize=A5")] and uit == "ok",
      f"test 19: geen beheerder: lpoptions -o (alleen voor jou), geen lpadmin, geen pkexec, geen naam ({opd})")
opd, _, uit = vang_cups(bi.zet_printer_opties, "Q", {}, "Printer\tin de gang")
klopt(opd == [("lpadmin", "-p", "Q", "-D", "Printer in de gang")], f"test 19: een nieuwe naam (-D), zonder tab ({opd})")
opd, _, uit = vang_cups(bi.zet_printer_opties, "Onbekend", {"Duplex": "None"})
klopt(not opd and uit == "anders", "test 19: een printer die nog niet gelezen is: niets")
vang_cups(bi.printer_opties, "Q", antwoord=lees_hp)
opd, _, uit = vang_cups(bi.zet_printer_opties, "Q", {"ColorModel": "KGray"}, None, antwoord=lambda c: (1, "lpadmin: Forbidden"))
klopt([c[0] for c in opd] == ["lpadmin", "pkexec"] and uit == "verboden" and not any(c[0] == "lpoptions" for c in opd),
      "test 19: lukt het niet, dan blijven je eigen keuzes staan")


# ===================================================== 3. printer toevoegen (stap 3 en 4) ===

def ippfind_uit(*regels) -> str:
    """Zoals printf '%s\\0' x 9 het schrijft: elk veld eindigt op een NUL (review R5)."""
    return "".join("".join(v + "\0" for v in r) for r in regels)


UUID = "1c852a4d-b800-1f08-abcd-a1b2c3d4e5f6"
HP_IPP = ("HP OfficeJet Pro 8010 [A1B2C3]", "=ipp", "bugos.local", "631", "ipp/print", "HP OfficeJet Pro 8010 series",
          "Kamer boven", UUID, "application/pdf,image/pwg-raster,image/urf")
OUD = ("Oude printer", "=ipp", "bugos.local", "631", "ipp", "Samsung ML-1640", "", "",
       "application/vnd.hp-PCL,application/octet-stream")
HP_IPPS = ("HP OfficeJet Pro 8010 [A1B2C3]", "=ipps", "bugos.local", "443", "ipp/print", "HP OfficeJet Pro 8010 series",
           "Kamer boven", UUID, "application/pdf,image/pwg-raster,image/urf")
HP_URI_IPP = "ipp://HP%20OfficeJet%20Pro%208010%20%5BA1B2C3%5D._ipp._tcp.local/"   # letterlijk uit lpstat -l -e
HP_URI_IPPS = "ipps://HP%20OfficeJet%20Pro%208010%20%5BA1B2C3%5D._ipps._tcp.local/"

# Test 1 en 3: de drie echte regels uit het onderzoek (nep-adverteringen in de VM).
gv = bi.lees_ippfind(ippfind_uit(HP_IPP, OUD, HP_IPPS), "andere-pc")
hp_g = gv[0] if gv else None
klopt(len(gv) == 2 and hp_g.uri == HP_URI_IPPS and hp_g.reserve_uri == HP_URI_IPP and hp_g.locatie == "Kamer boven"
      and hp_g.driverless and hp_g.naam == "HP OfficeJet Pro 8010 series" and hp_g.soort == "netwerk"
      and hp_g.proef_uri == "ipps://bugos.local:443/ipp/print" and hp_g.reserve_proef == "ipp://bugos.local:631/ipp/print",
      f"test 1+3: ipp en ipps van dezelfde printer worden één (ipps eerst, ipp als reserve); '=ipp' gelezen ({gv})")
klopt(len(gv) == 2 and not gv[1].driverless and gv[1].naam == "Samsung ML-1640",
      "test 1: een printer die alleen PCL kan, heeft software van de maker nodig")
gv = bi.lees_ippfind(ippfind_uit(HP_IPP, OUD, HP_IPPS,
                                 ("Canon TS5300 series", "=ipp", "localhost", "60000", "ipp/print", "Canon TS5300 series",
                                  "", "", "image/urf"),
                                 ("Epson", "=ipp", "localhost.", "60001", "ipp/print", "", "", "", "image/pwg-raster")),
                     "bugos")
klopt([(g.naam, g.soort) for g in gv] == [("HP OfficeJet Pro 8010 series", "netwerk"),
                                          ("Canon TS5300 series", "kabel"), ("Epson", "kabel")]
      and gv[0].reserve_uri == "",
      f"test 2: wat deze computer zelf deelt (poort 631) niet; ipp-usb op localhost:60000 = met een kabel (R8) ({gv})")
# R5: een TXT-waarde met een regeleinde en tabs maakt geen nep-printer meer.
kwaad = ("Review Evil [ABCD]", "=ipp", "bugos.local", "9", "", "Evil",
         "a\nFake Printer\t=ipp\tevil.example\t631\tipp/print\tFake\t\t\timage/urf", "x", "a")
gv = bi.lees_ippfind(ippfind_uit(kwaad), "andere-pc")
klopt(len(gv) == 1 and gv[0].naam == "Evil" and "\t" not in gv[0].locatie and "\n" not in gv[0].locatie,
      f"R5: tabs en regeleindes uit het netwerk maken geen extra printer en staan niet in de plek ({gv})")
klopt(bi.lees_ippfind("lpadmin: rommel op stderr\n" + ippfind_uit(("x",) * 3), "a") == [],
      "R5: half werk of rommel geeft geen printer")
# Test 4: al toegevoegd? (lpstat -v), alleen blijvende wachtrijen tellen (lpstat -l -e, R1).
app_ = bi.lees_lpstat_v(f"device for HP_OfficeJet_Pro_8010_A1B2C3: {HP_URI_IPPS}\ndevice for USB: usb://HP/LaserJet%201020?serial=FN0000\n")
hp_g = bi.lees_ippfind(ippfind_uit(HP_IPP, HP_IPPS), "andere-pc")[0]
usb_g = bi.Gevonden("HP LaserJet 1020", "", "usb://HP/LaserJet%201020?serial=XX", "", "usb", False, False, "")
klopt(bi.al_toegevoegd(hp_g, app_) and bi.al_toegevoegd(usb_g, app_)
      and not bi.al_toegevoegd(bi.lees_ippfind(ippfind_uit(OUD), "andere-pc")[0], app_),
      "test 4: een printer die er al is, ziet BugOS (ook via de DNS-SD-naam, en usb zonder serienummer)")
klopt(bi.lees_lpstat_e("HP_OfficeJet_Pro_8010_A1B2C3 network none " + HP_URI_IPP + "cups\n"
                       "printers_test permanent ipp://localhost/printers/printers_test ipp://localhost:631/x\n"
                       "Tijdelijk temporary ipp://localhost/printers/Tijdelijk ipp://x/\n") == {"printers_test"},
      "R1: alleen 'permanent' is een bezette naam; wat CUPS zelf tijdelijk maakt niet")
# Test 5: oude printers met een kabel (de vorm uit de documentatie van CUPS; de VM heeft er geen).
usb = bi.lees_lpinfo_usb("Device: uri = usb://HP/LaserJet%201020?serial=FN0000\n        class = direct\n"
                         "        info = HP LaserJet 1020\n        make-and-model = HP LaserJet 1020\n"
                         "        device-id = MFG:Hewlett-Packard;CMD:ZJS;MDL:HP LaserJet 1020;\n        location = \n"
                         "Device: uri = hp\n        class = direct\n        info = HP\n")
klopt(len(usb) == 1 and usb[0].uri == "usb://HP/LaserJet%201020?serial=FN0000" and usb[0].soort == "usb"
      and not usb[0].driverless and usb[0].model_hint == "HP LaserJet 1020",
      f"test 5: lpinfo -l: één printer met een kabel, met merk en model; 'hp' zonder usb:// niet ({usb})")
# Test 6: de wachtrij-naam is die van CUPS zelf (R1).
klopt(bi.wachtrij_naam("HP OfficeJet Pro 8010 [A1B2C3]", set()) == "HP_OfficeJet_Pro_8010_A1B2C3"
      and bi.wachtrij_naam("Canon TS5300 series", set()) == "Canon_TS5300_series"
      and bi.wachtrij_naam("Printer_192.168.1.20", set()) == "Printer_192_168_1_20",
      "test 6 / R1: de naam is precies de tijdelijke naam van CUPS (dan staat hij maar één keer in een printvenster)")
_n = [bi.wachtrij_naam("HP OfficeJet Pro 8010 [A1B2C3]", {"hp_officejet_pro_8010_a1b2c3"}),
      bi.wachtrij_naam("-x; rm -rf /", set()), bi.wachtrij_naam("é" * 300, set()), bi.wachtrij_naam("a" * 300, set())]
klopt(_n[0] == "HP_OfficeJet_Pro_8010_A1B2C3_2" and all(bi.NAAM_RE.match(x) and not x.startswith("-") for x in _n)
      and len(_n[3]) <= 127, f"test 6: bezet = _2; rare tekens en lange namen geven een veilige naam ({_n})")
# Test 7: een getypt adres.
goed_ = {"192.168.1.20": ["ipp://192.168.1.20/ipp/print", "ipps://192.168.1.20/ipp/print"],
         "printer.local": ["ipp://printer.local/ipp/print", "ipps://printer.local/ipp/print"],
         "ipps://10.0.0.5:631/ipp/print": ["ipps://10.0.0.5:631/ipp/print"],
         "[fe80::1]": ["ipp://[fe80::1]/ipp/print", "ipps://[fe80::1]/ipp/print"], " 10.0.0.9 ": None}
klopt(all(bi.adres_kandidaten(k) == (v or bi.adres_kandidaten(k.strip())) for k, v in goed_.items())
      and len(bi.adres_kandidaten(" 10.0.0.9 ")) == 2,
      "test 7: 192.168.1.20, printer.local, [fe80::1] en een ipps://-link zijn adressen")
klopt(not any(bi.adres_kandidaten(x) for x in ("", "a b", "http://x", "x;reboot", "999.1.1.1", "-p", "1.2.3",
                                               "printer.local/../x", "ipp://x/$(reboot)")),
      "test 7: '', 'a b', 'http://x', 'x;reboot', '999.1.1.1', '-p' zijn geen adres")
klopt(bi.adres_vervolg("192.168.1.20") == ("Printer_192_168_1_20", "ipp://192.168.1.20/ipp/print",
                                           "socket://192.168.1.20:9100")
      and bi.adres_vervolg("[fe80::1]")[2] == "socket://[fe80::1]:9100"
      and bi.adres_vervolg("ipp://10.0.0.5:631/ipp/print")[2] == "socket://10.0.0.5:9100",
      "test 7: na een getypt adres: de naam, en de adressen voor software van de maker (ipp, poort 9100)")


def cups_antwoord(lpadmin=(0, ""), lpstat_d="system default destination: Oud", ipptool=(0, ""), pkexec=None,
                  blijvend=""):
    """Een nep-CUPS: lpadmin (een functie van de opdracht of een vast antwoord), lpstat -d, ipptool, pkexec."""
    def antwoord(c):
        if c[0] == "lpadmin":
            return lpadmin(c) if callable(lpadmin) else lpadmin
        if c[0] == "pkexec":
            return pkexec(c) if callable(pkexec) else pkexec or (lpadmin(c) if callable(lpadmin) else lpadmin)
        if c[0] == "ipptool":
            return ipptool(c) if callable(ipptool) else ipptool
        if c[:3] == ("lpstat", "-l", "-e"):
            return 0, blijvend
        if c[:2] == ("lpstat", "-d"):
            return 0, lpstat_d
        return 0, ""
    return antwoord


HP_ADD = ("lpadmin", "-p", "HP_OfficeJet_Pro_8010_A1B2C3", "-E", "-v", HP_URI_IPPS, "-m", "everywhere", "-D",
          "HP OfficeJet Pro 8010 series", "-L", "Kamer boven")
# Test 9: als beheerder (wheel): lpadmin -m everywhere, zonder wachtwoord.
opd, tijd, uit = vang_cups(bi.printer_toevoegen, hp_g, antwoord=cups_antwoord())
klopt(HP_ADD in opd and tijd[opd.index(HP_ADD)] == 45 and uit == ("ok", "HP_OfficeJet_Pro_8010_A1B2C3")
      and not any(c[0] in ("pkexec", "ipptool") for c in opd),
      f"test 9: beheerder: lpadmin -p <naam van CUPS> -E -v ipps://... -m everywhere -D -L, 45 s ({opd})")
# Test 10: geen beheerder: eerst zonder wachtwoord kijken welk adres antwoordt, dan precies één pkexec (R3).
opd, _, uit = vang_cups(bi.printer_toevoegen, hp_g, beheerder=False, antwoord=cups_antwoord())
_pk = [c for c in opd if c[0] == "pkexec"]
klopt(_pk == [("pkexec", "/usr/bin/lpadmin") + HP_ADD[1:]] and opd.index(_pk[0]) > [c[0] for c in opd].index("ipptool")
      and ("lpoptions", "-d", "HP_OfficeJet_Pro_8010_A1B2C3") not in opd and uit[0] == "ok",
      f"test 10 / R3: geen beheerder: eerst ipptool (zonder wachtwoord), dan één keer pkexec lpadmin ({opd})")
opd, _, uit = vang_cups(bi.printer_toevoegen, hp_g, beheerder=False, antwoord=cups_antwoord(
    ipptool=lambda c: (0, "") if c[3].startswith("ipp://") else (1, "ipptool: Unable to connect to bugos.local on port 443")))
_pk = [c for c in opd if c[0] == "pkexec"]
klopt(len(_pk) == 1 and _pk[0][6] == HP_URI_IPP and [c[3] for c in opd if c[0] == "ipptool"]
      == ["ipps://bugos.local:443/ipp/print", "ipp://bugos.local:631/ipp/print"] and uit[0] == "ok",
      f"test 10 / R3: ipps antwoordt niet, ipp wel: één pkexec met ipp:// ({_pk})")
opd, _, uit = vang_cups(bi.printer_toevoegen, hp_g, beheerder=False, antwoord=cups_antwoord(
    ipptool=(1, "ipptool: Unable to connect to bugos.local on port 443 - Host is down\n")))
klopt(not any(c[0] == "pkexec" for c in opd) and uit == ("onbereikbaar", ""),
      "R3: antwoordt geen enkel adres: geen wachtwoordvenster, maar 'kan de printer niet bereiken'")
opd, _, uit = vang_cups(bi.printer_toevoegen, hp_g, beheerder=False,
                        antwoord=cups_antwoord(pkexec=(126, "Error executing command as another user: Request dismissed")))
klopt(uit == ("geweigerd", "") and len([c for c in opd if c[0] == "pkexec"]) == 1,
      "test 10: Annuleren in het wachtwoordvenster: 'niets gedaan', geen tweede venster")
# Test 12: als beheerder: ipps lukt niet, dan ipp (geen wachtwoord, dus mag het nog eens).
opd, _, uit = vang_cups(bi.printer_toevoegen, hp_g, antwoord=cups_antwoord(
    lpadmin=lambda c: (1, "lpadmin: Unable to connect to bugos.local:443: Connection refused\n") if HP_URI_IPPS in c
    else (0, "")))
_lp = [c for c in opd if c[0] == "lpadmin"]
klopt(len(_lp) == 2 and _lp[1][5] == HP_URI_IPP and uit[0] == "ok", f"test 12: ipps lukt niet: dan ipp ({_lp})")
# Test 13: geen IPP Everywhere: 'geen_driverless', niet nog eens en niet via pkexec.
opd, _, uit = vang_cups(bi.printer_toevoegen, hp_g, antwoord=cups_antwoord(lpadmin=(
    1, "lpadmin: Unable to create PPD: Printer does not support required IPP attributes or document formats.\n")))
klopt(uit == ("geen_driverless", "") and [c[0] for c in opd].count("lpadmin") == 1 and "pkexec" not in [c[0] for c in opd],
      "test 13: 'Unable to create PPD': software van de maker kiezen, geen tweede poging, geen pkexec")
# Test 14 / R20: de eerste printer wordt de standaard: voor iedereen (beheerder), anders alleen voor jou.
opd, _, uit = vang_cups(bi.printer_toevoegen, hp_g, antwoord=cups_antwoord(lpstat_d="no system default destination\n"))
klopt(("lpadmin", "-d", "HP_OfficeJet_Pro_8010_A1B2C3") in opd and not any(c[:2] == ("lpoptions", "-d") for c in opd),
      "test 14 / R20: eerste printer van een beheerder: standaard voor iedereen (lpadmin -d)")
opd, _, uit = vang_cups(bi.printer_toevoegen, hp_g, beheerder=False,
                        antwoord=cups_antwoord(lpstat_d="no system default destination\n"))
klopt(("lpoptions", "-d", "HP_OfficeJet_Pro_8010_A1B2C3") in opd and len([c for c in opd if c[0] == "pkexec"]) == 1,
      "test 14: zonder beheerder: standaard alleen voor jou (lpoptions -d), geen tweede wachtwoordvenster")
opd, _, uit = vang_cups(bi.printer_toevoegen, hp_g, antwoord=cups_antwoord())
klopt(not any(c[1:2] == ("-d",) and c[0] in ("lpadmin", "lpoptions") for c in opd),
      "test 14: is er al een standaard, dan blijft die")
# R12: de tijd was om, maar lpadmin maakte de wachtrij toch: dat is gelukt.
_na_lpadmin: list = []


def antwoord_traag(c):
    if c[0] == "lpadmin":
        _na_lpadmin.append(c)
        return 124, ""
    if c[:3] == ("lpstat", "-l", "-e") and _na_lpadmin:
        return 0, "HP_OfficeJet_Pro_8010_A1B2C3 permanent ipp://localhost/printers/x ipps://x/\n"
    return cups_antwoord()(c)


opd, _, uit = vang_cups(bi.printer_toevoegen, hp_g, antwoord=antwoord_traag)
klopt(uit == ("ok", "HP_OfficeJet_Pro_8010_A1B2C3") and [c[0] for c in opd].count("lpadmin") == 1,
      f"R12: tijd om, maar de wachtrij is er: gelukt (geen tweede poging met een andere naam) ({uit})")
# R1: de tijdelijke wachtrij van CUPS met dezelfde naam is niet 'bezet'.
opd, _, uit = vang_cups(bi.printer_toevoegen, hp_g, antwoord=cups_antwoord(
    blijvend="HP_OfficeJet_Pro_8010_A1B2C3 network none ipp://x/ ipp://y/\n"))
klopt(uit == ("ok", "HP_OfficeJet_Pro_8010_A1B2C3"), "R1: de tijdelijke printer van CUPS maakt de naam niet bezet (geen _2)")
# Een getypt adres.
opd, _, uit = vang_cups(bi.printer_toevoegen_adres, "192.168.1.20", antwoord=cups_antwoord(
    lpadmin=(1, "lpadmin: Unable to connect to 192.168.1.20:631: Host is down\n")))
klopt(uit == ("onbereikbaar", "") and [c[0] for c in opd].count("lpadmin") == 1
      and ("-D", "192.168.1.20") == next(c for c in opd if c[0] == "lpadmin")[8:10],
      "adres: onbereikbaar: niet nog een halve minuut met ipps:// op hetzelfde adres")
opd, _, uit = vang_cups(bi.printer_toevoegen_adres, "192.168.1.20", antwoord=cups_antwoord(
    lpadmin=(1, "lpadmin: Bad device-uri\n")))
klopt(uit == ("geen_antwoord", "") and [c[5] for c in opd if c[0] == "lpadmin"]
      == ["ipp://192.168.1.20/ipp/print", "ipps://192.168.1.20/ipp/print"],
      "adres: ipp en ipps lukken niet (geen IPP): 'geen_antwoord' (dan merk en model, poort 9100)")
opd, _, uit = vang_cups(bi.printer_toevoegen_adres, "x;reboot")
klopt(not opd and uit == ("geen_adres", ""), "adres: geen adres, dan ook geen opdracht")
opd, _, uit = vang_cups(bi.printer_toevoegen_adres, "192.168.1.20", beheerder=False, antwoord=cups_antwoord(
    ipptool=lambda c: (1, "ipptool: Unable to connect to 192.168.1.20 on port 631 - Host is down")))
klopt(uit == ("onbereikbaar", "") and [c[0] for c in opd].count("ipptool") == 1 and "pkexec" not in [c[0] for c in opd],
      "adres zonder beheerder: antwoordt hij niet, dan geen wachtwoordvenster en geen tweede halve minuut")
# Ontdekken: zonder beheerder geen lpinfo (alleen een beheerder mag dat), met de kabelknop één pkexec lpinfo (R7).
opd, _, _ = vang_cups(bi.gevonden_printers, beheerder=False)
klopt(opd[0][:2] == ("ippfind", "-T") and "%s\\0" * 9 in opd[0] and not any(c[0] in ("lpinfo", "pkexec") for c in opd),
      f"ontdekken: ippfind met NUL tussen de velden (R5); zonder beheerder geen lpinfo ({opd[0][:8]})")
opd, _, _ = vang_cups(bi.gevonden_printers, True, beheerder=False)
klopt(("pkexec", "/usr/bin/lpinfo", "-l", "--include-schemes", "usb", "-v") in opd,
      "R7: 'Printer met een kabel?': één keer pkexec lpinfo (alleen lezen)")
opd, _, gv = vang_cups(bi.gevonden_printers, antwoord=lambda c: (0, ippfind_uit(OUD, HP_IPP, HP_IPPS)) if c[0] == "ippfind"
                       else (0, f"device for X: {HP_URI_IPP}\n") if c[:2] == ("lpstat", "-v")
                       else (0, "X permanent ipp://localhost/printers/X ipp://y/\n") if c[:2] == ("lpstat", "-l") else (0, ""))
klopt(("lpinfo", "-l", "--include-schemes", "usb", "-v") in opd and [g.al_toegevoegd for g in gv] == [False, True]
      and gv[0].naam == "Samsung ML-1640",
      f"ontdekken als beheerder: ook usb; wat er al is, staat onderaan ({[(g.naam, g.al_toegevoegd) for g in gv]})")

# Test 15: printersoftware van de maker (lpinfo -m), echte regels uit de VM.
LPINFO_M = ("drv:///hp/hpcups.drv/hp-officejet_pro_8000_a809.ppd HP Officejet Pro 8000 a809, hpcups 3.26.6\n"
            "drv:///hp/hpijs.drv/hp-officejet_pro_8000_a809-hpijs.ppd HP Officejet Pro 8000 a809 hpijs, 3.26.6\n"
            "lsb/usr/HP/hp-officejet_pro_8000_a809.ppd.gz HP Officejet Pro 8000 a809, hpcups 3.26.6\n"
            "drv:///brlaser.drv/br2300d.ppd Brother HL-L2300D series, using brlaser v6\n"
            "everywhere IPP Everywhere\n"
            "drv:///cupsfilters.drv/pwgrast.ppd Generic IPP Everywhere Printer\n"
            "driverless:ipp://x/ipp/print HP x\n"
            "raw Raw Queue\n"
            "drv:///hp/hpijs.drv/hp-laserjet_1020-hpijs.ppd HP LaserJet 1020 hpijs, 3.26.6, requires proprietary plugin\n"
            "drv:///hp/hpcups.drv/hp-laserjet_1020.ppd HP LaserJet 1020, hpcups 3.26.6, requires proprietary plugin\n"
            "lsb/usr/HP/hp-laserjet_1020.ppd.gz HP LaserJet 1020, hpcups 3.26.6, requires proprietary plugin\n"
            "gutenprint.5.3://escp2-r220/expert Epson Stylus Photo R220 - CUPS+Gutenprint v5.3.5\n"
            "gutenprint.5.3://escp2-r220/simple Epson Stylus Photo R220 - CUPS+Gutenprint v5.3.5 Simplified\n")
ml = bi.lees_lpinfo_m(LPINFO_M)
klopt(ml == [("drv:///brlaser.drv/br2300d.ppd", "Brother HL-L2300D series"),
             ("gutenprint.5.3://escp2-r220/simple", "Epson Stylus Photo R220"),
             ("drv:///hp/hpcups.drv/hp-officejet_pro_8000_a809.ppd", "HP Officejet Pro 8000 a809")],
      f"test 15 / R2: elk model één keer (hpcups, Simplified), zonder everywhere/raw/driverless en zonder "
      f"'requires proprietary plugin' ({ml})")
import bugos_config_meldingen as bcm  # noqa: E402

bcm._MODELLEN.clear()
opd, _, uit = vang_cups(bi.printer_toevoegen_model, "usb://HP/LaserJet%201020?serial=FN0000", "HP LaserJet 1020",
                        "HP LaserJet 1020", "lsb/usr/HP/hp-laserjet_1020.ppd.gz")
klopt(not opd and uit == ("anders", ""), "test 15: een model dat niet uit lpinfo -m kwam, wordt nooit doorgegeven")
opd, tijd, ml = vang_cups(bi.modellen, "HP Officejet Pro 8000 a809 series",
                          antwoord=lambda c: (0, LPINFO_M) if c[0] == "lpinfo" else (0, ""))
klopt(opd == [("lpinfo", "--make-and-model", "HP Officejet Pro 8000", "-m")] and tijd == [40]
      and ml == [("drv:///hp/hpcups.drv/hp-officejet_pro_8000_a809.ppd", "HP Officejet Pro 8000 a809")],
      f"R2: eerst alleen wat bij merk en model past (een paar tellen, niet de hele lijst) ({opd}, {ml})")
opd, _, ml = vang_cups(bi.modellen, "Canon iP4000 (x)+ series",
                       antwoord=lambda c: (1, "") if c[0] == "lpinfo" else (0, ""))
klopt(opd and opd[0][2] == "Canon iP4000 \\(x\\)\\+" and ml == [],
      f"R2: merk en model zijn voor CUPS een reguliere expressie: tekens als ( en + letterlijk ({opd})")
opd, _, uit = vang_cups(bi.printer_toevoegen_model, "usb://HP/x", "HP Officejet", "HP Officejet Pro 8000",
                        "drv:///hp/hpcups.drv/hp-officejet_pro_8000_a809.ppd", antwoord=cups_antwoord())
klopt(("lpadmin", "-p", "HP_Officejet", "-E", "-v", "usb://HP/x", "-m",
       "drv:///hp/hpcups.drv/hp-officejet_pro_8000_a809.ppd", "-D", "HP Officejet Pro 8000") in opd and uit[0] == "ok",
      "test 15: met een gekozen model: lpadmin -m <dat model>")
opd, _, uit = vang_cups(bi.printer_toevoegen_model, "usb://HP/x", "HP Officejet", "HP Officejet",
                        "drv:///hp/hpcups.drv/hp-officejet_pro_8000_a809.ppd", beheerder=False, antwoord=cups_antwoord())
klopt([c[0] for c in opd].count("pkexec") == 1 and "ipptool" not in [c[0] for c in opd],
      "test 15: zonder beheerder: één wachtwoordvenster (een usb-printer kun je niet eerst proberen)")


# ============================================= 5. standaardprogramma's: een ander soort bestand ===

# Test 23: de soort van een bestand, zijn naam, waar hij een vorm van is, en welke programma's hem openen.
deel = TMP / "share"
(deel / "mime" / "application").mkdir(parents=True)
(deel / "mime" / "application" / "x-test.xml").write_text(
    '<?xml version="1.0" encoding="utf-8"?>\n<mime-type xmlns="http://www.freedesktop.org/standards/shared-mime-info" '
    'type="application/x-test">\n  <comment>Test document</comment>\n  <comment xml:lang="de">Testdokument</comment>\n'
    '  <comment xml:lang="nl">Testdocument</comment>\n</mime-type>\n', encoding="utf-8")
(deel / "mime" / "subclasses").write_text("application/x-test application/zip\napplication/x-test text/plain\n"
                                          "application/zip application/octet-stream\n", encoding="utf-8")
(deel / "applications").mkdir()
(deel / "applications" / "mimeinfo.cache").write_text(
    "[MIME Cache]\napplication/x-test=testlezer.desktop;\napplication/zip=org.kde.ark.desktop;\n"
    "text/plain=org.kde.kate.desktop;../kwaad.desktop;\n", encoding="utf-8")
for _naam, _inhoud in (("testlezer", "Name=Testlezer\nExec=testlezer %f"), ("org.kde.ark", "Name=Ark\nExec=ark %U"),
                       ("org.kde.kate", "Name=Kate\nExec=kate %U"), ("verborgen", "Name=Weg\nNoDisplay=true\nExec=x %f"),
                       ("zonder", "Name=Zonder bestand\nExec=zonder")):
    (deel / "applications" / f"{_naam}.desktop").write_text(f"[Desktop Entry]\nType=Application\n{_inhoud}\n",
                                                           encoding="utf-8")
_oud_xdg = os.environ.get("XDG_DATA_DIRS")
os.environ["XDG_DATA_DIRS"] = str(deel)
opd, _, s1 = vang_cups(bi.bestandssoort, "/home/bugie/boek.epub", antwoord=lambda c: (0, "application/epub+zip\n"))
_, _, s2 = vang_cups(bi.bestandssoort, "/home/bugie/x", antwoord=lambda c: (0, "xdg-mime: rare uitvoer; rm -rf\n"))
opd3, _, s3 = vang_cups(bi.bestandssoort, "-x")
klopt(opd == [("xdg-mime", "query", "filetype", "/home/bugie/boek.epub")] and s1 == "application/epub+zip"
      and s2 is None and s3 is None and not opd3,
      "test 23: bestandssoort = xdg-mime query filetype; rare uitvoer of een pad dat geen pad is: niets")
_, _, n_nl = vang_cups(bi.soort_naam, "application/x-test", "nl")
_, _, n_en = vang_cups(bi.soort_naam, "application/x-test", "en")
_, _, n_x = vang_cups(bi.soort_naam, "application/x-onbekend", "nl")
klopt((n_nl, n_en, n_x) == ("Testdocument", "Test document", "application/x-onbekend"),
      f"test 23: de naam van de soort uit shared-mime-info, in je eigen taal ({n_nl}, {n_en}, {n_x})")
klopt(bi.ouders("application/x-test") == ["application/zip", "text/plain", "application/octet-stream"],
      f"test 23: ouders uit subclasses, tot drie stappen ({bi.ouders('application/x-test')})")
_, _, aps = vang_cups(bi.apps_voor_soort, "application/x-test", "nl")
klopt(aps == [("testlezer.desktop", "Testlezer"), ("org.kde.kate.desktop", "Kate")],
      f"test 23 / R15: eerst de programma's voor precies deze soort, dan de ouders, maar geen Ark via zip ({aps})")
_, _, alle_ = vang_cups(bi.alle_apps, "nl")
klopt([a for a, _n in alle_ if a in ("testlezer.desktop", "org.kde.ark.desktop", "verborgen.desktop", "zonder.desktop")]
      == ["org.kde.ark.desktop", "testlezer.desktop"],
      f"test 23: 'Een ander programma': alleen programma's die een bestand kunnen openen, niets verborgens ({alle_})")
if _oud_xdg is None:
    os.environ.pop("XDG_DATA_DIRS", None)
else:
    os.environ["XDG_DATA_DIRS"] = _oud_xdg
# Test 24: voortaan openen met ... (xdg-mime default); wat BugOS zelf regelt niet (R14).
opd, _, ok = vang_cups(bi.zet_standaard_voor_soort, "application/epub+zip", "org.kde.okular.desktop")
klopt(opd == [("xdg-mime", "default", "org.kde.okular.desktop", "application/epub+zip")] and ok,
      "test 24: xdg-mime default org.kde.okular.desktop application/epub+zip")
_geweigerd = []
for _m, _a in (("inode/directory", "a.desktop"), ("application/x-msi", "a.desktop"), ("x-scheme-handler/http", "a.desktop"),
               ("application/vnd.flatpak.ref", "a.desktop"), ("application/epub+zip", "../x.desktop"),
               ("application/epub+zip", "-x.desktop"), ("../etc/passwd", "a.desktop"), ("application/pdf", "a.sh")):
    o, _, ok = vang_cups(bi.zet_standaard_voor_soort, _m, _a)
    if o or ok:
        _geweigerd.append((_m, _a))
klopt(not _geweigerd, f"test 24 / R14: mappen, .msi, links, Flatpak-bestanden en rare namen: nooit ({_geweigerd})")


# =========================================================================== 9. het venster ===

lader = importlib.machinery.SourceFileLoader("instellingen", str(BIN / "bugos-settings"))
spec = importlib.util.spec_from_loader("instellingen", lader)
mod = importlib.util.module_from_spec(spec)
sys.modules["instellingen"] = mod
lader.exec_module(mod)
import bugos_settings_meldingen as sm  # noqa: E402
import bugos_shell  # noqa: E402
import bugos_ui  # noqa: E402
from PySide6.QtCore import QThreadPool  # noqa: E402
from PySide6.QtWidgets import QDialog  # noqa: E402

app = mod.maak_app("bugos-settings", "bugos-settings", ["test"])
kde_open: list = []
bugos_ui.kde_instelling = lambda m: kde_open.append(m)
for _m in (sm, mod):
    if hasattr(_m, "kde_instelling"):
        _m.kde_instelling = lambda m: kde_open.append(m)
gevraagd: list = []
_antwoord_vraag = [True]


def nep_exec(self):
    gevraagd.append(self)
    return QDialog.DialogCode.Accepted if _antwoord_vraag[0] else QDialog.DialogCode.Rejected


bugos_shell.VraagDialoog.exec = nep_exec
venster = mod.Instellingen("printers")


def wacht() -> None:
    for _ in range(3):
        QThreadPool.globalInstance().waitForDone(5000)
        app.processEvents()


wacht()
pp = venster.paginas["printers"]
klopt(len(pp.lijst.findChildren(mod.Rij)) == 2 and "wacht" in pp.wacht_rij.titel.text(),
      "venster: twee printers en de wachtrij (zoals test_settings)")
rijen = pp.lijst.findChildren(mod.Rij)
klopt(rijen[0].uitleg.text() == "Klaar om te printen · Studeerkamer" and rijen[1].uitleg.text().startswith("Gestopt"),
      f"venster: klaar met de plek erbij; de Canon is gestopt ({[r.uitleg.text() for r in rijen]})")
klopt(len(pp.taak_rijen) == 1 and pp.taak_rijen[0].titel.text() == "Brief aan de bank.pdf"
      and pp.taak_rijen[0].rechts.text() == "Annuleren" and "wordt nu geprint" in pp.taak_rijen[0].uitleg.text()
      and pp.taak_rijen[0].rechts.accessibleName() in ("", "Annuleren")
      and pp.taak_rijen[0].rechts.accessibleDescription() == "Brief aan de bank.pdf",
      "wachtrij: je document met zijn naam en een knop 'Annuleren'; de schermlezer hoort welk document (U039, test 27)")
menu_hp = [x[1] for x in pp.menu(bi.printers()[0])]
menu_canon = [x[1] for x in pp.menu(bi.printers()[1])]
klopt("Printen pauzeren" in menu_hp and "Verder printen" not in menu_hp and "Printer verwijderen" in menu_hp,
      f"menu: een printer die klaarstaat: pauzeren en verwijderen ({menu_hp})")
klopt("Verder printen" in menu_canon and "Als standaard gebruiken" in menu_canon,
      f"menu: een gestopte printer: verder printen ({menu_canon})")
pp.beheerder = False
klopt("Printen pauzeren" not in [x[1] for x in pp.menu(bi.printers()[0])],
      "menu: zonder beheerder geen 'pauzeren' (cupsdisable kan niet via pkexec)")
pp.beheerder = True
_vreemd_p = bi.Printer("-x", "Vreemd", "klaar", False)
klopt([x[1] for x in pp.menu(_vreemd_p)] == ["Als standaard gebruiken", "Testpagina printen"],
      "menu: een wachtrij met een naam die BugOS niet vertrouwt: alleen standaard en testpagina")
# Verwijderen: eerst de vraag (Enter = Annuleren), dan weg.
_verw = next(x for x in pp.menu(bi.printers()[1]) if x[1] == "Printer verwijderen")
_antwoord_vraag[0] = False
_verw[2]()
wacht()
klopt(len(bi.printers()) == 2 and gevraagd and gevraagd[-1].standaard == "Annuleren"
      and "Canon PIXMA (boven)" in gevraagd[-1].uitleg.text(),
      "verwijderen: eerst de vraag met de naam erin; Enter en Annuleren laten de printer staan (vraag_ja)")
_antwoord_vraag[0] = True
_verw[2]()
wacht()
klopt([p.naam for p in bi.printers()] == ["HP_LaserJet"] and len(pp.lijst.findChildren(mod.Rij)) == 1
      and pp.melding.tekst.text() == "Printer verwijderd.", "verwijderen: weg, de lijst is bijgewerkt, 'Printer verwijderd.'")
bi._VB["printers"] = None
pp.wachtrij_rijen(7, [bi.Taak("HP_LaserJet", i, f"doc{i}", False) for i in range(7)], {"HP_LaserJet": "HP"})
klopt(len(pp.taak_rijen) == 6 and pp.taak_rijen[-1].titel.text() == "en nog 2 meer" and
      pp.wacht_rij.titel.text() == "7 documenten staan te wachten" and pp.taak_rijen[0].titel.text() == "doc0",
      "wachtrij: hooguit vijf documenten, dan 'en nog 2 meer'")
pp.leeg_knop.click()
wacht()
klopt(not pp.taak_rijen and pp.wacht_rij.titel.text() == "Niets staat te wachten" and not pp.leeg_knop.isVisible(),
      "wachtrij: 'Alles annuleren' maakt hem leeg")
bi._VB.pop("taken", None)

# Printerinstellingen (test 27): de HP in de voorbeeldstand.
bi._VB["printers"] = None
bi._VB.pop("printer_opties", None)
pp.ververs()
wacht()
hp = bi.printers()[0]
d = sm.PrinterInstellingen(pp, hp, True)
wacht()
klopt(d.papier_knop.text() == "A4" and d.zijden.knoppen["een"].isChecked() and d.kleur.knoppen["kleur"].isChecked()
      and not d.papier_rij.isHidden() and not d.banner.isVisibleTo(d) and d.bewaar.isEnabled(),
      "instellingen: papier A4, één kant, kleur; geen melding meer na het laden")
_bewaard: list = []
_echt_zet = bi.zet_printer_opties
bi.zet_printer_opties = lambda naam, w, b=None: (_bewaard.append((naam, w, b)), "ok")[1]
d.kleur.knoppen["zw"].click()
d.bewaar.click()
wacht()
bi.zet_printer_opties = _echt_zet
klopt(_bewaard == [("HP_LaserJet", {"ColorModel": "Gray"}, None)] and d.uitkomst == "ok",
      f"instellingen: zwart-wit kiezen en bewaren geeft alleen ColorModel=Gray door ({_bewaard})")
d2 = sm.PrinterInstellingen(pp, bi.printers()[1], False)
wacht()
klopt(d2.zijden_rij.isHidden() and d2.kleur.knoppen["kleur"].isChecked() and d2.naam_veld is None and d2.weg is None
      and "alleen voor jou" in d2.uitleg.text(),
      "instellingen zonder beheerder: geen naam, geen verwijderen, 'alleen voor jou'; geen twee kanten zonder duplex-eenheid")
bi.zet_printer_opties = lambda naam, w, b=None: "verboden"
d2.kleur.knoppen["zw"].click()
d2.bewaar.click()
wacht()
bi.zet_printer_opties = _echt_zet
klopt(d2.result() == 0 and d2.banner.isVisibleTo(d2) and "beheerder" in d2.banner.tekst.text() and d2.bewaar.isEnabled()
      and d2.uitleg.isHidden(), "instellingen: lukt het niet, dan blijft het venster open met de melding in gewone woorden")
_echt_opties = bi.printer_opties
bi.printer_opties = lambda naam: None
d3 = sm.PrinterInstellingen(pp, hp, True)
wacht()
bi.printer_opties = _echt_opties
klopt(d3.papier_rij.isHidden() and "printvenster" in d3.banner.tekst.text() and d3.weg.isEnabled(),
      "instellingen die BugOS niet kan lezen: dat zeggen, en de naam en verwijderen blijven")
_echt_exec = sm.PrinterInstellingen.exec
sm.PrinterInstellingen.exec = lambda self: (self.klaar("ok"), 1)[1]
pp.instellingen(hp)
klopt(pp.melding.tekst.text() == "Bewaard.", "instellingen: na bewaren zegt de pagina 'Bewaard.'")
sm.PrinterInstellingen.exec = _echt_exec
bi._VB.pop("printer_opties", None)

# Printer toevoegen (test 27): de knop opent geen KDE meer maar het eigen venster.
import bugos_settings_onderdelen as so  # noqa: E402

klopt(pp.nieuw.text() == "Printer toevoegen" and pp.nieuw.parent().objectName() == "sectie_met_knop",
      "toevoegen: 'Printer toevoegen' staat rechts naast het kopje (sectie_met_knop, layout D10)")
bi._VB["printers"] = None
bi._VB.pop("gevonden", None)
dt = sm.PrinterToevoegen(pp, True)
wacht()
_rijen_t = dt.lijst.findChildren(mod.Rij)
_per_titel = {r.titel.text(): r for r in _rijen_t}
klopt(len(_rijen_t) == 3 and sum("software van de maker" in r.uitleg.text() for r in _rijen_t) == 1
      and _per_titel["HP OfficeJet Pro 8010 series"].uitleg.text() == "Op je netwerk · Boven"
      and _per_titel["Canon TS5300 series"].uitleg.text() == "Met een kabel aangesloten"
      and _rijen_t[-1].titel.text() == "Brother HL-L2300D series"
      and not dt.status.isVisibleTo(dt) and dt.uitleg.isVisibleTo(dt) and dt.opnieuw.isEnabled(),
      f"toevoegen: drie gevonden printers, wie software van de maker nodig heeft onderaan "
      f"({[(r.titel.text(), r.uitleg.text()) for r in _rijen_t]})")
klopt(dt.vlak.maximumHeight() >= dt.lijst.sizeHint().height() and dt.kabel is None,
      "toevoegen: drie printers staan er helemaal (geen schuifbalk); een beheerder ziet alle kabelprinters al")
dt.toon_gevonden(bi.gevonden_printers() * 2)
klopt(dt.lijst.sizeHint().height() > dt.vlak.maximumHeight() <= sm.px(4 * sm.PrinterToevoegen.RIJ)
      and dt.vlak.maximumHeight() >= 3 * 60,
      f"toevoegen: zes printers: drie en een half in beeld, de rest schuift (review R4) ({dt.vlak.maximumHeight()})")
dt.toon_gevonden(bi.gevonden_printers())
_per_titel["HP OfficeJet Pro 8010 series"].rechts.click()
wacht()
klopt(dt.result() == QDialog.DialogCode.Accepted and dt.toegevoegd == ("HP_OfficeJet_Pro_8010_A1B2C3",
                                                                      "HP OfficeJet Pro 8010 series")
      and "HP_OfficeJet_Pro_8010_A1B2C3" in [p.naam for p in bi.printers()],
      f"toevoegen: 'Toevoegen' voegt hem toe onder de naam van CUPS en sluit het venster ({dt.toegevoegd})")
# Een oude printer met een kabel: merk en model kiezen (KiesDialoog), eerst wat past.
dt = sm.PrinterToevoegen(pp, True)
wacht()
_gekozen_lijsten: list = []


def kies_exec(self, keuze=[None]):
    _gekozen_lijsten.append([self.lijst.item(i).data(sm.Qt.ItemDataRole.UserRole) for i in range(self.lijst.count())])
    self.gekozen = keuze[0] if keuze[0] is not None else self.gekozen
    return QDialog.DialogCode.Accepted if keuze[0] else QDialog.DialogCode.Rejected


so.KiesDialoog.exec = kies_exec
_usb_rij = next(r for r in dt.lijst.findChildren(mod.Rij) if "software" in r.uitleg.text())
kies_exec.__defaults__[0][0] = None
_usb_rij.rechts.click()
wacht()
klopt(_gekozen_lijsten and _gekozen_lijsten[-1] == ["drv:///brlaser.drv/br2300d.ppd", "__alle__"]
      and dt.status.isVisibleTo(dt) and "geen software" in dt.status.tekst.text() and dt.result() == 0
      and dt.sluit.isEnabled(),
      f"model: eerst wat bij 'Brother HL-L2300D' past, dan 'ander merk'; Annuleren = eerlijk 'geen software' "
      f"({_gekozen_lijsten[-1:]}, {dt.status.tekst.text()[:40]!r})")
kies_exec.__defaults__[0][0] = "drv:///brlaser.drv/br2300d.ppd"
_usb_rij.rechts.click()
wacht()
klopt(dt.result() == QDialog.DialogCode.Accepted and dt.toegevoegd
      and dt.toegevoegd[0] == "Brother_HL_L2300D_series",
      f"model: kiezen en toevoegen ({dt.toegevoegd})")
# Een adres typen: eerst een fout adres (de vraag zegt het), dan een goed.
dt = sm.PrinterToevoegen(pp, False)
wacht()
klopt(dt.kabel is not None and "wachtwoord van een beheerder" in dt.uitleg.text(),
      "toevoegen zonder beheerder: 'Printer met een kabel?' en vooraf: BugOS vraagt het wachtwoord van een beheerder")
_teksten = ["x;reboot", "192.168.1.20"]
_vragen: list = []


def adres_exec(self):
    _vragen.append(self.uitleg.text())
    if self.veld is not None and _teksten:
        self.veld.setText(_teksten.pop(0))
    return QDialog.DialogCode.Accepted


bugos_shell.VraagDialoog.exec = adres_exec
dt.ander.click()
wacht()
bugos_shell.VraagDialoog.exec = nep_exec
klopt(len(_vragen) == 2 and "geen printeradres" in _vragen[1] and dt.toegevoegd == ("Printer_192_168_1_20", "192.168.1.20"),
      f"adres: 'x;reboot' is geen adres (de vraag zegt het), 192.168.1.20 wel ({dt.toegevoegd})")
# Geen IPP Everywhere op dat adres: door naar merk en model met ipp://adres; antwoordt hij helemaal niet als IPP: poort 9100.
_modellen_uri: list = []
_echt_adres, _echt_model = bi.printer_toevoegen_adres, bi.printer_toevoegen_model
for _soort, _uri in (("geen_driverless", "ipp://10.0.0.7/ipp/print"), ("geen_antwoord", "socket://10.0.0.7:9100")):
    bi.printer_toevoegen_adres = lambda tekst, s=_soort: (s, "")
    bi.printer_toevoegen_model = lambda uri, basis, naam, model: (_modellen_uri.append((uri, basis)), ("ok", "Q"))[1]
    kies_exec.__defaults__[0][0] = "drv:///brlaser.drv/br2300d.ppd"
    _teksten[:] = ["10.0.0.7"]
    dt = sm.PrinterToevoegen(pp, True)
    wacht()
    bugos_shell.VraagDialoog.exec = adres_exec
    dt.ander.click()
    wacht()
    bugos_shell.VraagDialoog.exec = nep_exec
bi.printer_toevoegen_adres, bi.printer_toevoegen_model = _echt_adres, _echt_model
klopt(_modellen_uri == [("ipp://10.0.0.7/ipp/print", "Printer_10_0_0_7"), ("socket://10.0.0.7:9100", "Printer_10_0_0_7")]
      and "__alle__" not in _gekozen_lijsten[-1] and len(_gekozen_lijsten[-1]) >= 6,
      f"adres: geen IPP Everywhere -> merk en model op ipp://; geen IPP -> poort 9100; zonder merk de hele lijst "
      f"({_modellen_uri})")
# Tijdens het toevoegen kun je het venster niet sluiten (het gebeurt toch).
dt = sm.PrinterToevoegen(pp, True)
wacht()
dt.zet_bezig(True)
dt.reject()
klopt(dt.result() == 0 and not dt.sluit.isEnabled(), "toevoegen: tijdens het toevoegen gaat het venster niet dicht")
dt.zet_bezig(False)
dt.reject()
# Na het toevoegen: de pagina zegt het, met 'Testpagina printen'.
_echt_exec_t = sm.PrinterToevoegen.exec
sm.PrinterToevoegen.exec = lambda self: (setattr(self, "toegevoegd", ("Q", "Kantoorprinter")), 1)[1]
pp.toevoegen()
sm.PrinterToevoegen.exec = _echt_exec_t
wacht()
klopt(pp.melding.tekst.text() == "Kantoorprinter is toegevoegd." and pp.melding.knop.text() == "Testpagina printen",
      "toevoegen: 'Kantoorprinter is toegevoegd.' met de knop 'Testpagina printen'")
# Standaardprogramma's (test 27): tien soorten, en 'Een ander soort bestand...' in plaats van KDE's bestandstypes.
pg = venster.paginas["programmas"]
venster.ga_naar("programmas")
wacht()
klopt(len(pg.rijen) == 10 and list(pg.rijen)[5:9] == ["pdf", "kantoor", "rekenen", "zip"]
      and pg.rijen["kantoor"].uitleg.text() == "LibreOffice Writer" and pg.rijen["zip"].uitleg.text() == "Ark"
      and pg.ander.text() == "Een ander soort bestand...",
      f"programma's: tien soorten (ook Word, Excel en zip) en 'Een ander soort bestand...' "
      f"({[(k, r.uitleg.text()) for k, r in pg.rijen.items()]})")
_keuzes_rij: list = []


def kies_rij_exec(self):
    _gekozen_lijsten.append([self.lijst.item(i).data(sm.Qt.ItemDataRole.UserRole) for i in range(self.lijst.count())])
    if not _keuzes_rij:
        return QDialog.DialogCode.Rejected
    self.gekozen = _keuzes_rij.pop(0)
    return QDialog.DialogCode.Accepted


so.KiesDialoog.exec = kies_rij_exec
_keuzes_rij[:] = ["org.kde.kate.desktop"]
pg.kies_soort("application/epub+zip")
wacht()
klopt(_gekozen_lijsten[-1] == ["org.kde.okular.desktop", "org.kde.kate.desktop", "__alle__"]
      and bi.standaard_voor_soort("application/epub+zip") == "org.kde.kate.desktop"
      and pg.melding.tekst.text() == "EPUB-e-boek opent voortaan met Kate (tekst).",
      f"programma's: een EPUB: de programma's ervoor, en 'Een ander programma...' ({pg.melding.tekst.text()!r})")
_keuzes_rij[:] = ["__alle__", "firefox.desktop"]
pg.kies_soort("application/epub+zip")
wacht()
klopt(_gekozen_lijsten[-1] == ["org.kde.okular.desktop", "org.kde.kate.desktop", "firefox.desktop", "org.kde.ark.desktop"]
      and bi.standaard_voor_soort("application/epub+zip") == "firefox.desktop"
      and pg.melding.tekst.text() == "EPUB-e-boek opent voortaan met Firefox.",
      "programma's: 'Een ander programma...' laat alle programma's zien")
_keuzes_rij[:] = []
pg.kies_soort("application/epub+zip")
wacht()
klopt(bi.standaard_voor_soort("application/epub+zip") == "firefox.desktop", "programma's: Annuleren verandert niets")
pg.kies_soort("application/x-msi")
klopt(pg.melding.tekst.text() == "Dit soort bestand regelt BugOS zelf.", "programma's: een .msi regelt BugOS zelf")
pg.kies_soort("application/octet-stream")
klopt(pg.melding.tekst.text() == "BugOS weet niet wat voor bestand dit is.",
      "programma's: een onbekende soort: dat zeggen, niet een lijst met alles")
_echt_fd = sm.QFileDialog.getOpenFileName
sm.QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: (str(TMP / "boek.epub"), ""))
_keuzes_rij[:] = ["org.kde.okular.desktop"]
pg.ander.click()
wacht()
sm.QFileDialog.getOpenFileName = _echt_fd
klopt(bi.standaard_voor_soort("application/epub+zip") == "org.kde.okular.desktop"
      and "opent voortaan met Okular" in pg.melding.tekst.text(),
      "programma's: de knop: een bestand kiezen, dan het programma")
bi._VB.pop("soort_apps", None)
so.KiesDialoog.exec = kies_exec

bi._VB["printers"] = None
bi._VB.pop("gevonden", None)
klopt(not kde_open, f"nergens KDE geopend ({kde_open})")

print(f"\n{fouten} fout(en).")
sys.exit(1 if fouten else 0)
