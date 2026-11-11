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

print(f"\n{fouten} fout(en).")
sys.exit(1 if fouten else 0)
