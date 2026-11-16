"""Haal alles van je oude pc: onthouden wat er veranderd is, zodat je alles kunt terugdraaien (onderdeel F).

Jip-en-Janneke: terwijl BugOS je spullen van Windows neerzet, schrijft hij in een logboek wat hij doet: welke
bestanden hij neerzette, welke instellingen hij veranderde (en hoe ze eerst waren), welke wifi-netwerken en
printers erbij kwamen. Met de knop 'Alles terugdraaien' loopt BugOS dat logboek achterstevoren af:
  - bestanden en mappen van je oude pc gaan naar de PRULLENBAK (nooit echt weg: je kunt ze nog terughalen);
  - een bestand dat je na het overzetten zelf hebt veranderd, blijft staan (dat is nu van jou);
  - instellingen worden weer zoals ze waren (taal, notatie, tijdzone, toetsenbord, licht/donker, muis, grootte);
  - wifi-netwerken en printers die erbij kwamen, gaan eruit; je standaardprinter wordt weer de oude;
  - het Firefox- en Thunderbird-profiel van Windows gaan naar de prullenbak, het vorige profiel is weer het
    standaardprofiel.

Waar: ~/.local/share/bugos/overstap/logboek.json. Na het terugdraaien krijgt het bestand een andere naam
(logboek-teruggedraaid-<tijd>.json), zodat een volgende overstap met een schoon logboek begint.

Waarom een eigen bestand en niet 'alles van na tijdstip X weg': je kunt na het overzetten zelf al dingen gemaakt
hebben. Alleen wat BugOS zelf neerzette, staat in het logboek, dus alleen dat gaat terug.

Alles wat hier gebeurt, gooit nooit een fout naar boven: het overzetten mag niet mislukken omdat het logboek niet
geschreven kon worden. Terugdraaien geeft per onderdeel een Uitslag (goed / niet / zelf doen), net als overzetten.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path

import bugos_config as bi
import bugos_overstap_toepassen as ot
from bugos_base import t

GOED, NIET, ZELF = ot.GOED, ot.NIET, ot.ZELF


def map_() -> Path:
    """De map met het logboek (XDG_DATA_HOME, zoals de rest van BugOS; in tests een nep-thuismap)."""
    basis = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return basis / "bugos" / "overstap"


def pad() -> Path:
    return map_() / "logboek.json"


# ================================================================ het logboek ===

# Acties met een OUDE waarde: welke velden zeggen 'over hetzelfde ding' (dan telt alleen de eerste keer).
_EEN_KEER = {
    "instelling": ("naam",),
    "muis": ("sysnaam", "wat"),
    "scrollen": ("sysnaam",),
    "kde": ("bestand", "groep", "sleutel"),
    "schaal": ("scherm",),
    "achtergrond": (),
    "standaardprinter": (),
    "ini": ("pad",),
}


def _sleutel(soort: str, velden: dict) -> tuple | None:
    """('instelling', 'taal') voor een actie die maar één keer mag tellen, anders None."""
    if soort not in _EEN_KEER:
        return None
    return (soort,) + tuple(str(velden.get(v)) for v in _EEN_KEER[soort])


class Logboek:
    """Het logboek van één (of meer) keer overzetten. Elke actie wordt meteen opgeslagen: valt de stroom uit
    halverwege, dan weet BugOS toch wat er al stond."""

    def __init__(self, bestand: Path | None = None):
        self.bestand = bestand or pad()
        self._slot = threading.Lock()   # het venster en de achtergrond-taak schrijven er allebei in
        self.data: dict = {"versie": 1, "acties": [], "uitslagen": []}
        try:
            d = json.loads(self.bestand.read_text(encoding="utf-8"))
            if isinstance(d, dict) and isinstance(d.get("acties"), list):
                self.data = d
                self.data.setdefault("uitslagen", [])
        except (OSError, ValueError):
            pass

    # ---------------------------------------------------------------- schrijven ---

    def begin(self, computer: str = "", gebruiker: str = "") -> None:
        """Een nieuwe keer overzetten: van welke computer, en wanneer (voor 'Overgezet op ... van ...')."""
        with self._slot:
            self.data["computer"] = ot._tekst(computer, 60)
            self.data["gebruiker"] = ot._tekst(gebruiker, 60)
            self.data["tijd"] = datetime.now().isoformat(timespec="seconds")
            self.data["uitslagen"] = []
        self._bewaar()

    def onthoud(self, soort: str, **velden) -> None:
        """Eén ding dat BugOS veranderde. soort: bestand, map, profielmap, ini, firefox_voorkeuren, achtergrond,
        instelling, muis, scrollen, kde, schaal, wifi, printer, standaardprinter, lettertypen.

        Bij een oude waarde (instelling, muis, achtergrond ...) telt alleen de EERSTE: zet je twee keer over, dan moet
        terugdraaien naar hoe het was vóór de eerste keer, niet naar wat de eerste keer neerzette."""
        sleutel = _sleutel(soort, velden)
        with self._slot:
            if sleutel is not None and any(_sleutel(a.get("soort", ""), a) == sleutel for a in self.data["acties"]):
                return
            self.data["acties"].append({"soort": soort, **velden})
        self._bewaar()

    def bestand_erbij(self, p: Path) -> None:
        """Een bestand dat BugOS neerzette. Met grootte en tijd: zo zien we bij terugdraaien of je het daarna zelf
        veranderde (dan blijft het staan)."""
        try:
            st = p.stat()
        except OSError:
            return
        self.onthoud("bestand", pad=str(p), grootte=st.st_size, tijd=st.st_mtime)

    def bestanden_erbij(self, paden: list[Path], mappen: list[Path] = ()) -> None:
        """Veel bestanden tegelijk (na een rsync): één keer opslaan in plaats van duizend keer."""
        nieuw = []
        for m in mappen:
            nieuw.append({"soort": "map", "pad": str(m)})
        for p in paden:
            try:
                st = p.stat()
            except OSError:
                continue
            nieuw.append({"soort": "bestand", "pad": str(p), "grootte": st.st_size, "tijd": st.st_mtime})
        if not nieuw:
            return
        with self._slot:
            self.data["acties"].extend(nieuw)
        self._bewaar()

    def uitslagen(self, lijst: list) -> None:
        """Hoe het ging (de samenvatting), zodat je die later nog eens kunt zien."""
        with self._slot:
            self.data["uitslagen"] = [{"deel": u.deel, "soort": u.soort, "tekst": u.tekst} for u in lijst]
        self._bewaar()

    def _bewaar(self) -> None:
        """In een los bestand en dan in één keer op zijn plek: nooit een half logboek."""
        try:
            self.bestand.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.bestand.with_name(self.bestand.name + ".nieuw")
            with self._slot:
                tekst = json.dumps(self.data, ensure_ascii=False, indent=1)
            tmp.write_text(tekst, encoding="utf-8")
            os.replace(tmp, self.bestand)
        except OSError:
            pass   # vol of alleen-lezen: overzetten gaat gewoon door

    # ------------------------------------------------------------------ lezen ---

    def leeg(self) -> bool:
        return not self.data.get("acties")

    def samenvatting(self) -> str:
        """'Overgezet op 16 november om 19:30 van LAPTOP-PIET: 230 bestanden, instellingen, 2 wifi-netwerken.'"""
        acties = self.data.get("acties", [])
        bestanden = sum(1 for a in acties if a.get("soort") == "bestand")
        delen = []
        if bestanden:
            delen.append(t("{n} bestanden", "{n} files").format(n=bestanden) if bestanden != 1 else
                         t("1 bestand", "1 file"))
        if any(a.get("soort") in ("instelling", "muis", "scrollen", "kde", "schaal", "achtergrond") for a in acties):
            delen.append(t("instellingen", "settings"))
        wifi = sum(1 for a in acties if a.get("soort") == "wifi")
        if wifi:
            delen.append(t("{n} wifi-netwerken", "{n} Wi-Fi networks").format(n=wifi) if wifi != 1 else
                         t("1 wifi-netwerk", "1 Wi-Fi network"))
        printers_ = sum(1 for a in acties if a.get("soort") == "printer")
        if printers_:
            delen.append(t("{n} printers", "{n} printers").format(n=printers_) if printers_ != 1 else
                         t("1 printer", "1 printer"))
        if any(a.get("soort") == "profielmap" for a in acties):
            delen.append(t("Firefox of Thunderbird", "Firefox or Thunderbird"))
        wanneer = ""
        try:
            d = datetime.fromisoformat(str(self.data.get("tijd")))
            wanneer = t("op {d} om {u}", "on {d} at {u}").format(d=d.strftime("%d-%m-%Y"), u=d.strftime("%H:%M"))
        except ValueError:
            pass
        van = ot._tekst(self.data.get("computer"), 60)
        kop = t("Overgezet", "Transferred")
        if wanneer:
            kop += " " + wanneer
        if van:
            kop += " " + t("van {c}", "from {c}").format(c=van)
        return kop + (": " + ", ".join(delen) if delen else "") + "."

    def oude_uitslagen(self) -> list:
        return [ot.Uitslag(ot._tekst(u.get("deel"), 30), ot._tekst(u.get("soort"), 10), ot._tekst(u.get("tekst"), 600))
                for u in self.data.get("uitslagen", []) if isinstance(u, dict)]


# Het logboek waar de overstap NU in schrijft. None = niets onthouden (bijvoorbeeld in oude tests, of
# 'bugos-switch --zet' zonder venster: dan schrijft die zelf een logboek, zie bugos-switch).
ACTIEF: Logboek | None = None


def onthoud(soort: str, **velden) -> None:
    """Zet iets in het actieve logboek (als er een is). Nooit een fout."""
    if ACTIEF is not None:
        try:
            ACTIEF.onthoud(soort, **velden)
        except Exception:  # noqa: BLE001  het logboek mag het overzetten nooit tegenhouden
            pass


def maak_map(p: Path) -> None:
    """Maak een map (met alles erboven wat nog niet bestaat) en onthoud elke map die BugOS zo NIEUW maakte. Dan
    haalt terugdraaien ze weer weg als ze leeg zijn (in de VM bleven anders lege mappen als 'fonts' en '.thunderbird'
    achter). Een map die er al was, komt niet in het logboek: die blijft altijd."""
    nieuw = []
    m = p
    while not m.exists() and m != m.parent:
        nieuw.append(m)
        m = m.parent
    p.mkdir(parents=True, exist_ok=True)
    for m in reversed(nieuw):   # bovenste eerst; terugdraaien begint toch bij de diepste
        onthoud("map", pad=str(m))


def bestand_erbij(p: Path) -> None:
    if ACTIEF is not None:
        try:
            ACTIEF.bestand_erbij(p)
        except Exception:  # noqa: BLE001
            pass


# ============================================================= rsync-logboek ===
# rsync schrijft met --log-file-format='%i %n' per bestand een regel: '2026/11/16 19:30:01 [1234] >f+++++++++ a/b.txt'.
# '>f+++++++++' = een nieuw bestand, 'cd+++++++++' = een nieuwe map. Bestanden die er al waren, slaat rsync over
# (--ignore-existing), die staan er dus niet in: precies wat we willen (alleen wat BugOS neerzette).
_RSYNC_REGEL = re.compile(r"^\S+ \S+ \[\d+\] ([>c][fd]\+{9}) (.+)$")


def rsync_opties(logbestand: Path) -> list[str]:
    """De extra opties voor rsync, zodat we daarna weten welke bestanden nieuw waren."""
    return [f"--log-file={logbestand}", "--log-file-format=%i %n"]


def lees_rsync_log(logbestand: Path, doel: Path) -> tuple[list[Path], list[Path]]:
    """(nieuwe bestanden, nieuwe mappen) uit een rsync-logboek, als volle paden onder 'doel'."""
    bestanden, mappen = [], []
    try:
        regels = logbestand.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return [], []
    for regel in regels:
        m = _RSYNC_REGEL.match(regel)
        if not m:
            continue
        soort, naam = m.groups()
        naam = naam.rstrip("/")
        if naam == "." and soort.startswith("cd"):
            # 'cd+++++++++ ./': de doelmap zelf is nieuw (bijv. 'Foto's 2019' in je Thuismap). Ook onthouden: anders
            # blijft na terugdraaien een lege map staan (gezien in de VM).
            mappen.append(doel)
            continue
        # Nooit iets buiten de doelmap (een rare naam met ../ zou dat kunnen): dan niet onthouden.
        if not naam or naam == "." or naam.startswith("/") or ".." in Path(naam).parts:
            continue
        (mappen if soort.startswith("cd") else bestanden).append(doel / naam)
    return bestanden, mappen


# ========================================================== oude waarden lezen ===
# Vlak vóór BugOS iets verandert, lezen we hoe het was. Lukt dat lezen niet, dan onthouden we niets (en zegt
# terugdraaien voor dat onderdeel 'kijk zelf even').

def lees_scrollen(sysnaam: str) -> float | None:
    """Het scrollFactor van een muis bij KWin (1.0 = gewoon), of None."""
    if bi.VOORBEELD or not re.fullmatch(r"[A-Za-z0-9_]{1,40}", sysnaam):
        return None
    code, uit = bi.draai("busctl", "--user", "get-property", "org.kde.KWin", f"/org/kde/KWin/InputDevice/{sysnaam}",
                         "org.kde.KWin.InputDevice", "scrollFactor", timeout=5)
    m = re.fullmatch(r"\s*d\s+([\d.]+)\s*", uit or "")
    return float(m.group(1)) if code == 0 and m else None


def lees_achtergrond() -> str:
    """Het plaatje dat nu de achtergrond is (het eerste 'Image=' van de achtergrond-plug-in van KDE), of ''."""
    config = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    try:
        tekst = (config / "plasma-org.kde.plasma.desktop-appletsrc").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    in_groep = False
    for regel in tekst.splitlines():
        if regel.startswith("["):
            in_groep = regel.endswith("[Wallpaper][org.kde.image][General]")
        elif in_groep and regel.startswith("Image="):
            return regel[len("Image="):].strip()
    return ""


def lees_standaardprinter() -> str:
    try:
        return next((p.naam for p in bi.printers() if p.standaard), "")
    except Exception:  # noqa: BLE001
        return ""


# =============================================================== terugdraaien ===

def _zelfde(p: Path, actie: dict) -> bool:
    """Is dit bestand nog precies zoals BugOS het neerzette (zelfde grootte, zelfde tijd)?"""
    try:
        st = p.stat()
    except OSError:
        return False
    return st.st_size == actie.get("grootte") and abs(st.st_mtime - float(actie.get("tijd") or 0)) < 2


def _naar_prullenbak(p: Path) -> bool:
    """Naar de prullenbak van KDE (freedesktop-afspraak), zoals Bestanden dat doet. Nooit echt weggooien."""
    try:
        import bugos_files_acties as fa
        fa.naar_prullenbak(p)
        return True
    except Exception:  # noqa: BLE001  (bijv. een andere schijf): dan laten staan en zeggen
        return False


def _zet_ini_terug(actie: dict) -> bool:
    """profiles.ini / installs.ini weer zoals ze waren. inhoud None: het bestand was er niet (dan weg)."""
    p = Path(str(actie.get("pad")))
    oud = actie.get("inhoud")
    try:
        if oud is None:
            p.unlink(missing_ok=True)
        else:
            tmp = p.with_name(p.name + ".bugos-terug")
            tmp.write_text(str(oud), encoding="utf-8")
            os.replace(tmp, p)
        return True
    except OSError:
        return False


def _zet_firefox_voorkeuren_terug(actie: dict) -> str:
    """De bladwijzers die BugOS klaarzette voor Firefox. Heeft Firefox ze nog niet ingelezen (de voorkeur staat er
    nog), dan halen we ze weer weg: 'goed'. Anders staan ze al in Firefox: 'zelf' (map weghalen)."""
    import bugos_overstap_firefox as ff
    profiel = Path(str(actie.get("profiel")))
    prefs = profiel / "prefs.js"
    try:
        regels = prefs.read_text(encoding="utf-8").splitlines()
    except OSError:
        return "zelf"
    namen = [json.dumps(n) for n in actie.get("namen", [])]
    nog = any(r.startswith('user_pref("browser.places.importBookmarksHTML", true)') for r in regels)
    if not nog:
        return "zelf"
    if ff.draait(profiel):
        return "zelf"
    regels = [r for r in regels if not any(r.startswith(f"user_pref({n},") for n in namen)]
    try:
        tmp = prefs.with_name("prefs.js.bugos-terug")
        tmp.write_text("\n".join(regels) + "\n", encoding="utf-8")
        os.replace(tmp, prefs)
        (profiel / ff.EIGEN_BESTAND).unlink(missing_ok=True)
    except OSError:
        return "zelf"
    return "goed"


def terugdraaien(boek: Logboek | None = None) -> list[ot.Uitslag]:
    """Draai alles in het logboek terug, achterstevoren. Geeft per onderdeel een Uitslag. Na afloop krijgt het
    logboek een andere naam (een volgende overstap begint schoon)."""
    boek = boek or Logboek()
    acties = list(boek.data.get("acties", []))
    if not acties:
        return [ot.Uitslag("terug", NIET, t("Er is niets om terug te draaien.", "There is nothing to undo."))]
    if bi.VOORBEELD:
        return [ot.Uitslag("terug", GOED, t("Alles staat weer zoals voor het overzetten.",
                                            "Everything is back to how it was before the transfer."))]
    weg, veranderd, kwijt, niet_weg = 0, [], 0, []
    mappen: list[Path] = []
    instellingen_ok, instellingen_mis = [], []
    wifi_ok, wifi_mis, printers_ok, printers_mis = [], [], [], []
    profielen_ok, zelf_doen = [], []
    achtergrond_ok = None
    fonts_veranderd = False

    # Taal vóór de notatie: zet_taal zet de notatie ook terug naar die van de taal, dus de oude notatie moet daarna.
    volgorde = {"taal": 0, "regio": 1}

    def instelling_terug(a: dict) -> None:
        naam, oud = a.get("naam"), a.get("oud")
        ok = False
        try:
            if naam == "taal":
                ok = bi.zet_taal(str(oud))
            elif naam == "regio":
                ok = bi.zet_regio(str(oud))
            elif naam == "tijdzone":
                ok = bi.zet_tijdzone(str(oud))   # vraagt je wachtwoord (de klok is van iedereen)
            elif naam == "toetsenborden":
                ok = bi.zet_toetsenborden([bi.Indeling(str(x[0]), str(x[1])) for x in oud])
            elif naam == "donker":
                ok = bi.zet_donker(bool(oud))
        except Exception:  # noqa: BLE001
            ok = False
        (instellingen_ok if ok else instellingen_mis).append(naam)

    instelling_acties = sorted([a for a in acties if a.get("soort") == "instelling"],
                               key=lambda a: volgorde.get(a.get("naam"), 2))
    for a in instelling_acties:
        instelling_terug(a)

    for a in reversed(acties):
        soort = a.get("soort")
        try:
            if soort == "bestand":
                p = Path(str(a.get("pad")))
                if not p.exists():
                    kwijt += 1   # al weg (door jou weggegooid): niets te doen
                elif _zelfde(p, a):
                    if _naar_prullenbak(p):
                        weg += 1
                        fonts_veranderd |= "/fonts/" in str(p)
                    else:
                        niet_weg.append(p.name)
                else:
                    veranderd.append(p.name)
            elif soort == "map":
                mappen.append(Path(str(a.get("pad"))))
            elif soort == "profielmap":
                p = Path(str(a.get("pad")))
                if p.exists():
                    if _naar_prullenbak(p):
                        # Van welk programma: Thunderbird staat in een map met 'thunderbird' in de naam.
                        profielen_ok.append("mail" if "thunderbird" in str(p).lower() else "firefox")
                    else:
                        niet_weg.append(p.name)
            elif soort == "ini":
                if not _zet_ini_terug(a):
                    zelf_doen.append(("firefox", t("Kies je vorige profiel in about:profiles.",
                                                   "Choose your previous profile in about:profiles.")))
            elif soort == "firefox_voorkeuren":
                if _zet_firefox_voorkeuren_terug(a) == "zelf":
                    zelf_doen.append(("bladwijzers", t(
                        "De bladwijzers staan al in Firefox: haal de map '{m}' weg van de bladwijzerbalk (rechtsklik > "
                        "Verwijderen).", "The bookmarks are already in Firefox: remove the '{m}' folder from the "
                        "bookmarks toolbar (right-click > Delete).").format(m=ot._tekst(a.get("map"), 80))))
            elif soort == "achtergrond":
                oud = str(a.get("oud") or "")
                plaatje = oud[len("file://"):] if oud.startswith("file://") else oud
                if plaatje and Path(plaatje).exists():
                    r = subprocess.run(["plasma-apply-wallpaperimage", plaatje], capture_output=True, timeout=10)
                    achtergrond_ok = r.returncode == 0
                else:
                    achtergrond_ok = False
            elif soort == "muis":
                ok = bi.zet_aanwijzer(str(a.get("sysnaam")), str(a.get("wat")), a.get("oud"))
                (instellingen_ok if ok else instellingen_mis).append("muis")
            elif soort == "scrollen":
                ok = ot.zet_scrollen(str(a.get("sysnaam")), float(a.get("oud")))
                (instellingen_ok if ok else instellingen_mis).append("muis")
            elif soort == "kde":
                ok = bi.kde_schrijf(str(a.get("bestand")), str(a.get("groep")), str(a.get("sleutel")), a.get("oud"))
                (instellingen_ok if ok else instellingen_mis).append("muis")
            elif soort == "schaal":
                ok = bi.zet_schaal(float(a.get("oud")), a.get("scherm"))
                (instellingen_ok if ok else instellingen_mis).append("grootte")
            elif soort == "wifi":
                uuid = ot._tekst(a.get("uuid"), 60)
                naam = ot._tekst(a.get("naam"), 64)
                cmd = ["nmcli", "connection", "delete", "uuid", uuid] if uuid else ["nmcli", "connection", "delete",
                                                                                   "id", naam]
                code, _u, _f = bi.draai_nm(*cmd, timeout=20)
                (wifi_ok if code == 0 else wifi_mis).append(naam)
            elif soort == "printer":
                import bugos_config_meldingen as bm
                wachtrij = ot._tekst(a.get("wachtrij"), 120)
                (printers_ok if bm.verwijder_printer(wachtrij) == "ok" else printers_mis).append(
                    ot._tekst(a.get("naam"), 100) or wachtrij)
            elif soort == "standaardprinter":
                oud = ot._tekst(a.get("oud"), 120)
                if oud:
                    bi.zet_standaard_printer(oud)
        except Exception:  # noqa: BLE001  één onderdeel dat raar doet, houdt de rest niet tegen
            continue

    # Mappen die BugOS maakte en nu leeg zijn, ook weg (diepste eerst). Een map met iets van jou erin blijft.
    for m in sorted(set(mappen), key=lambda p: len(p.parts), reverse=True):
        try:
            m.rmdir()
        except OSError:
            pass
    if fonts_veranderd and shutil.which("fc-cache"):
        subprocess.run(["fc-cache", "-f"], capture_output=True, timeout=120)

    # ------------------------------------------------------------- de uitslagen ---
    uit: list[ot.Uitslag] = []
    if weg or veranderd or niet_weg:
        tekst = (t("{n} bestanden van je oude pc staan in de prullenbak (daar kun je ze nog terughalen).",
                   "{n} files from your old PC are in the trash (you can still get them back from there).")
                 if weg != 1 else t("1 bestand van je oude pc staat in de prullenbak (daar kun je het nog terughalen).",
                                    "1 file from your old PC is in the trash (you can still get it back from there).")
                 ).format(n=weg)
        if veranderd:
            tekst += " " + t("Bleef staan omdat je het zelf veranderde: {b}.",
                             "Kept because you changed it yourself: {b}.").format(b=ot._kort(veranderd, 3))
        uit.append(ot.Uitslag("bestanden", GOED if not niet_weg else ZELF, tekst + (
            " " + t("Kon niet naar de prullenbak: {b}. Gooi die zelf weg in Bestanden.",
                    "Could not go to the trash: {b}. Throw those away yourself in Files.").format(
                        b=ot._kort(niet_weg, 3)) if niet_weg else "")))
    for deel in dict.fromkeys(profielen_ok):
        uit.append(ot.Uitslag(deel, GOED, t(
            "Het profiel van Windows staat in de prullenbak; Firefox opent weer met je vorige profiel.",
            "The profile from Windows is in the trash; Firefox opens with your previous profile again.")
            if deel == "firefox" else t(
            "Je Thunderbird van Windows staat in de prullenbak.", "Your Thunderbird from Windows is in the trash.")))
    if achtergrond_ok is not None:
        uit.append(ot.Uitslag("achtergrond", GOED if achtergrond_ok else ZELF,
                              t("Je vorige achtergrond is terug.", "Your previous wallpaper is back.") if achtergrond_ok
                              else t("Kies je achtergrond in Instellingen > Uiterlijk.",
                                     "Choose your wallpaper in Settings > Appearance.")))
    if instellingen_ok or instellingen_mis:
        if instellingen_mis:
            uit.append(ot.Uitslag("instellingen", ZELF, t("Niet alles kon terug ({w}). Kijk in Instellingen.",
                                                          "Not everything could go back ({w}). Check Settings.").format(
                                                              w=", ".join(sorted(set(instellingen_mis))))))
        else:
            tekst = t("Je instellingen zijn weer zoals ze waren.", "Your settings are back to how they were.")
            if {"taal", "regio"} & set(instellingen_ok):
                tekst += " " + t("Taal en notatie zie je na opnieuw inloggen.",
                                 "Language and format show after you sign in again.")
            uit.append(ot.Uitslag("instellingen", GOED, tekst))
    if wifi_ok:
        uit.append(ot.Uitslag("wifi", GOED, t("Weg: {n}.", "Removed: {n}.").format(n=ot._kort(wifi_ok, 5))))
    if wifi_mis:
        uit.append(ot.Uitslag("wifi", ZELF, t("Haal zelf weg in Instellingen > Wifi en internet: {n}.",
                                              "Remove yourself in Settings > Wi-Fi and internet: {n}.").format(
                                                  n=ot._kort(wifi_mis, 5))))
    if printers_ok:
        uit.append(ot.Uitslag("printers", GOED, t("Weg: {n}.", "Removed: {n}.").format(n=ot._kort(printers_ok, 5))))
    if printers_mis:
        uit.append(ot.Uitslag("printers", ZELF, t("Haal zelf weg in Instellingen > Printers en scannen: {n}.",
                                                  "Remove yourself in Settings > Printers and scanning: {n}.").format(
                                                      n=ot._kort(printers_mis, 5))))
    for deel, z in dict.fromkeys(zelf_doen):   # elke zin één keer
        uit.append(ot.Uitslag(deel, ZELF, z))
    if not uit:
        uit.append(ot.Uitslag("terug", GOED, t("Alles staat weer zoals voor het overzetten.",
                                               "Everything is back to how it was before the transfer.")))
    # Het logboek is klaar: een andere naam, zodat de volgende overstap schoon begint (en dit nog na te lezen is).
    try:
        if boek.bestand.exists():
            boek.bestand.rename(boek.bestand.with_name(f"logboek-teruggedraaid-{time.strftime('%Y%m%d-%H%M%S')}.json"))
    except OSError:
        pass
    return uit
