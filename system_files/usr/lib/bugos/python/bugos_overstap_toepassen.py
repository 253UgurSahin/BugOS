"""Haal alles van je oude pc (bugos-switch): de stick lezen en de instellingen van Windows overzetten.

Het Windows-programma "BugOS Switch" zet een map BugOS-Switch op een USB-stick, met bugos-switch.json erin. Het
contract tussen de twee kanten staat in windows-switch/FORMAT.md (versie 2). Hier staat alles wat géén venster
nodig heeft, zodat het los te testen is:

  - de stick vinden en bugos-switch.json lezen (versie 1 en 2: elk nieuw veld mag ontbreken);
  - de onderdelen voor het overzicht ('wat gaat er mee');
  - instellingen: taal en notatie, tijdzone, toetsenborden, licht/donker, muis, grootte van het scherm;
  - wifi: alleen de NAAM van het netwerk, nooit het wachtwoord (de keuze van de eigenaar);
  - printers op het netwerk, net als 'Printer toevoegen' in Instellingen (eerst zonder software van de maker);
  - programma's: alleen VOORSTELLEN uit de Winkel (/usr/share/bugos/overstap-apps.json), nooit zelf installeren.

Voor elk onderdeel gebruiken we de functies die Instellingen zelf ook gebruikt (bugos_config: zet_taal, zet_regio,
zet_tijdzone via bugos-tijd, zet_toetsenborden, zet_donker via bugos-theme, zet_aanwijzer, zet_schaal, de printer-
functies). Dan doet "overzetten" precies wat jij in Instellingen had kunnen klikken, met dezelfde controles.

Elke stap geeft een Uitslag terug (goed / niet mogelijk / zelf doen) en gooit nooit een fout naar boven: één
onderdeel dat mislukt, mag de rest niet tegenhouden. Met BUGOS_INSTELLINGEN_VOORBEELD=1 verandert er niets
(voorbeeldstand voor tests en schermfoto's).
"""

from __future__ import annotations

import getpass
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import bugos_config as bi
from bugos_base import t

# Waar de gegevens van BugOS staan: /usr/share/bugos. Uit de plek van dit bestand (/usr/lib/bugos/python/..), zodat
# de tests in de repo (system_files/usr/lib/bugos/python) vanzelf system_files/usr/share/bugos lezen.
DATA = Path(__file__).resolve().parents[3] / "share" / "bugos"

# Mapnaam en infobestand van de Windows-overstap: de nieuwe en de oude (van voor de hernoeming).
MAPPEN = (("BugOS-Switch", "bugos-switch.json"), ("BugOS-Overstap", "bugos-overstap.json"))

# Windows-mapnaam -> xdg-naam van de BugOS-map (dezelfde zes als in versie 1).
KOPPELING = {
    "Documents": "DOCUMENTS",
    "Pictures": "PICTURES",
    "Music": "MUSIC",
    "Videos": "VIDEOS",
    "Desktop": "DESKTOP",
    "Downloads": "DOWNLOAD",
}

# De Windows-mapnamen in je eigen taal, voor de meldingen (U150).
MAP_NAAM = {"Documents": ("Documenten", "Documents"), "Pictures": ("Afbeeldingen", "Pictures"),
            "Music": ("Muziek", "Music"), "Videos": ("Video's", "Videos"), "Desktop": ("Bureaublad", "Desktop"),
            "Downloads": ("Downloads", "Downloads")}


def mapnaam(win: str) -> str:
    nl, en = MAP_NAAM.get(win, (win, win))
    return t(nl, en)


# =============================================================== de stick ===

def _op_schijf(schijf: Path) -> list[Path]:
    """De overstap-map op één schijf: BugOS-Switch, of anders BugOS-Overstap van de oude versie.
    Staan ze er allebei (beide versies gebruikt), dan alleen de nieuwe: anders staat de stick er twee keer."""
    for naam, bestand in MAPPEN:
        try:
            if (schijf / naam / bestand).is_file():
                return [schijf / naam]
        except OSError:   # een stick die net uitgetrokken wordt
            continue
    return []


def zoek_overstap(openen: bool = True) -> list[Path]:
    """Zoek op alle aangesloten schijven naar de map BugOS-Switch (of de oude BugOS-Overstap).
    openen: een stick die er net in zit, eerst openzetten (KDE doet dat niet vanzelf, U139). Welkom kijkt ook."""
    if os.environ.get("BUGOS_SCHIJVEN"):  # voor tests en screenshots
        return [m for p in os.environ["BUGOS_SCHIJVEN"].split(":") for m in _op_schijf(Path(p))]
    if openen:
        try:
            import bugos_drives
            bugos_drives.losse_openen_op_achtergrond()
        except Exception:  # noqa: BLE001  zonder udisks/lsblk gewoon kijken wat er al open is
            pass
    gebruiker = getpass.getuser()
    gevonden = []
    gezien: set[Path] = set()
    for basis in (Path("/run/media") / gebruiker, Path("/media") / gebruiker, Path("/media")):
        try:
            if basis.is_dir():
                for schijf in basis.iterdir():
                    for map_ in _op_schijf(schijf):
                        # Op Fedora is /media een koppeling naar /run/media: dan vonden we dezelfde stick twee keer
                        # (VM-test 2026-11-16). Het echte pad telt, één keer.
                        echt = map_.resolve()
                        if echt not in gezien:
                            gezien.add(echt)
                            gevonden.append(map_)
        except OSError:
            continue
    return gevonden


def info(map_: Path) -> dict:
    """bugos-switch.json van de stick (of het oude bugos-overstap.json). Kapot of geen object: {} (dan doen we
    alleen wat er als map op de stick staat, zoals bij versie 1)."""
    for _naam, bestand in MAPPEN:
        try:
            data = json.loads((map_ / bestand).read_text(encoding="utf-8-sig"))
        except FileNotFoundError:
            continue
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def versie(i: dict) -> int:
    """De versie van het bestand: 1 als het er niet staat (de eerste Windows-versie schreef het nog niet)."""
    v = i.get("versie", 1)
    return v if isinstance(v, int) and not isinstance(v, bool) else 1


# Alles op de stick komt van een andere computer (of van iemand anders): nooit zomaar vertrouwen. Deze hulpjes geven
# altijd het goede soort terug, ook als het bestand iets anders zegt.
def _dict(x) -> dict:
    return x if isinstance(x, dict) else {}


def _lijst(x) -> list:
    return x if isinstance(x, list) else []


def _tekst(x, lengte: int = 200) -> str:
    """Een tekst van de stick: zonder stuurtekens (geen regeleindes in een melding of opdracht), en niet te lang."""
    if not isinstance(x, str):
        return ""
    return "".join(c for c in x if c.isprintable())[:lengte].strip()


def binnen_stick(bron: Path, relatief) -> Path | None:
    """Een pad uit bugos-switch.json (relatief aan de map BugOS-Switch), maar alleen als het echt binnen die map
    blijft: '../../etc/passwd' of een absoluut pad wijzen we af."""
    tekst = _tekst(relatief, 400)
    if not tekst or tekst.startswith(("/", "\\")) or ":" in tekst:
        return None
    pad = bron / tekst.replace("\\", "/")
    try:
        echt, basis = pad.resolve(), bron.resolve()
    except OSError:
        return None
    if echt != basis and basis not in echt.parents:
        return None
    return pad


# ================================================================ uitslag ===

GOED, NIET, ZELF = "goed", "niet", "zelf"


@dataclass
class Uitslag:
    """Hoe één ding ging. soort: GOED (gedaan), NIET (kan niet, met de reden) of ZELF (doe dit zelf, met hoe)."""
    deel: str       # bestanden, bladwijzers, firefox, achtergrond, instellingen, wifi, printers
    soort: str
    tekst: str


def _onthoud(soort: str, **velden) -> None:
    """Zet iets in het logboek van deze overstap (bugos_overstap_logboek), zodat 'Alles terugdraaien' weet hoe
    het was. Geen logboek actief (tests, oude aanroepen): dan gebeurt er niets. Nooit een fout."""
    try:
        import bugos_overstap_logboek as lb   # hier pas: dat onderdeel gebruikt dit onderdeel ook
        lb.onthoud(soort, **velden)
    except Exception:  # noqa: BLE001  onthouden mag het overzetten nooit tegenhouden
        pass


# De kop per onderdeel, in het overzicht en in de samenvatting.
DEEL_NAAM = {
    "bestanden": ("Je bestanden", "Your files"),
    "bladwijzers": ("Bladwijzers", "Bookmarks"),
    "firefox": ("Je Firefox van Windows", "Your Firefox from Windows"),
    "achtergrond": ("Je achtergrond", "Your wallpaper"),
    "instellingen": ("Instellingen", "Settings"),
    # D-10: taal en notatie hebben elk een eigen schuifje (staat uit als Windows iets anders had dan BugOS nu).
    "taal": ("Taal", "Language"),
    "notatie": ("Datum en tijd", "Date and time"),
    "wifi": ("Wifi-netwerken", "Wi-Fi networks"),
    "printers": ("Printers", "Printers"),
    # Bestanden slimmer (E) en terugdraaien (F).
    "extra": ("Andere mappen", "Other folders"),
    "lettertypen": ("Lettertypen", "Fonts"),
    "mail": ("E-mail", "E-mail"),
    "outlook": ("Outlook", "Outlook"),
    "terug": ("Terugdraaien", "Undo"),
}


def deel_naam(deel: str) -> str:
    nl, en = DEEL_NAAM.get(deel, (deel, deel))
    return t(nl, en)


# ============================================================== overzicht ===

@dataclass
class Onderdeel:
    """Een regel in het overzicht: wat er op de stick staat en mee kan. aan: hoe de schakelaar begint. Bijna alles
    begint aan; taal en notatie niet (D-10): die verander je alleen als je dat zelf aanzet."""
    sleutel: str
    icoon: str
    uitleg: str
    aan: bool = True


def windows_mappen(bron: Path) -> list[str]:
    """De mappen (Documents, Pictures ...) die echt op de stick staan."""
    uit = []
    for win in KOPPELING:
        try:
            if (bron / win).is_dir():
                uit.append(win)
        except OSError:
            continue
    return uit


def _kort(namen: list[str], hooguit: int = 3) -> str:
    """'A, B, C en nog 2' (of in het Engels): een lange lijst past niet in één regel."""
    if len(namen) <= hooguit:
        return ", ".join(namen)
    return t("{lijst} en nog {n}", "{lijst} and {n} more").format(lijst=", ".join(namen[:hooguit]), n=len(namen) - hooguit)


def onderdelen(bron: Path, i: dict | None = None) -> list[Onderdeel]:
    """Wat er van deze stick mee kan, in de volgorde van het overzicht. Ontbreekt iets (versie 1, of Windows kon
    het niet lezen), dan staat het er gewoon niet: niets om aan of uit te zetten."""
    import bugos_overstap_firefox as ff
    i = info(bron) if i is None else i
    uit: list[Onderdeel] = []
    mappen = windows_mappen(bron)
    if mappen:
        uit.append(Onderdeel("bestanden", "lijn:download",
                             t("{mappen}. Wat al op BugOS staat, wordt nooit overschreven.",
                               "{mappen}. What's already on BugOS is never overwritten.").format(
                                 mappen=", ".join(mapnaam(m) for m in mappen))))
    import bugos_overstap_bestanden as ob
    extra = ob.extra_mappen(bron, i)
    if extra:
        uit.append(Onderdeel("extra", "lijn:map",
                             t("{mappen}. Komen in je Thuismap, onder dezelfde naam.",
                               "{mappen}. Go to your Home folder, under the same name.").format(
                                 mappen=_kort([n for n, _p in extra]))))
    bronnen = ff.bladwijzer_bronnen(bron, i)
    if bronnen:
        uit.append(Onderdeel("bladwijzers", "lijn:ster",
                             t("Van {wat}. Ze komen vanzelf in Firefox, in de bladwijzerbalk.",
                               "From {wat}. They go into Firefox by themselves, on the bookmarks toolbar.").format(
                                 wat=_kort([b.naam for b in bronnen]))))
    if ff.profiel_op_stick(bron, i) is not None:
        uit.append(Onderdeel("firefox", "lijn:wereld",
                             t("Je tabbladen, geschiedenis en uitbreidingen, zonder wachtwoorden. Je huidige Firefox "
                               "blijft bewaard als reserve.",
                               "Your history, settings and extensions, without passwords. Your current Firefox is "
                               "kept as a backup.")))
    try:
        achtergrond = (bron / "achtergrond.jpg").is_file()
    except OSError:
        achtergrond = False
    if achtergrond:
        uit.append(Onderdeel("achtergrond", "lijn:foto",
                             t("Je oude Windows-achtergrond wordt ook je BugOS-achtergrond.",
                               "Your old Windows wallpaper becomes your BugOS wallpaper too.")))
    ins = _dict(i.get("instellingen"))
    # D-10: de taal en de notatie van datum en tijd apart, als 'nu -> straks', en standaard UIT. Een tester met een
    # Nederlandse BugOS en een Windows met taal en-NL en notatie en-US kreeg anders een Engelse BugOS met een
    # 12-uursklok en M/D/YY, terwijl het overzicht alleen het woord 'English' liet zien. Je koos de taal bij het
    # installeren of in Welkom; die verandert BugOS alleen als jij dat hier aanzet.
    taal_nu, taal_straks = taal_wissel(ins)
    if taal_straks:
        uit.append(Onderdeel("taal", "lijn:wereld", t(
            "{nu} -> {straks}. Staat standaard uit: zonder dit schuifje houdt BugOS de taal {nu}.",
            "{nu} -> {straks}. Off by default: without this switch BugOS keeps the language {nu}.").format(
                nu=taal_naam(taal_nu), straks=taal_naam(taal_straks)), aan=False))
    regio_nu, regio_straks = notatie_wissel(ins)
    if regio_straks:
        uit.append(Onderdeel("notatie", "lijn:klok", t(
            "{nu} -> {straks} ({voorbeeld}). Staat standaard uit: zonder dit schuifje blijven de datum en de tijd "
            "zoals nu.", "{nu} -> {straks} ({voorbeeld}). Off by default: without this switch the date and time stay "
            "as they are.").format(
                nu=regio_naam(regio_nu), straks=regio_naam(regio_straks), voorbeeld=regio_voorbeeld(regio_straks)),
            aan=False))
    wat = instellingen_kort(ins)
    if wat:
        uit.append(Onderdeel("instellingen", "lijn:schakelaar", _kort(wat, 6)))
    netten = [_tekst(_dict(w).get("naam"), 64) for w in _lijst(i.get("wifi"))]
    netten = [n for n in netten if n]
    if netten:
        uit.append(Onderdeel("wifi", "lijn:wifi",
                             t("{netten}. Zonder wachtwoord: ben je in de buurt, dan vraagt BugOS het één keer.",
                               "{netten}. Without passwords: when you're nearby, BugOS asks for it once.").format(
                                 netten=_kort(netten))))
    printers_ = [_tekst(_dict(p).get("naam"), 80) or _tekst(_dict(p).get("adres"), 80) for p in _lijst(i.get("printers"))]
    printers_ = [p for p in printers_ if p]
    if printers_:
        uit.append(Onderdeel("printers", "lijn:printer",
                             t("{printers}. Printers met een kabel komen vanzelf.",
                               "{printers}. Printers with a cable come by themselves.").format(printers=_kort(printers_))))
    letters = ob.lettertypen_op_stick(bron, i)
    if letters:
        uit.append(Onderdeel("lettertypen", "lijn:letter",
                             (t("{n} lettertypen die je zelf installeerde. Elk programma kan ze gebruiken.",
                                "{n} fonts you installed yourself. Every program can use them.") if len(letters) != 1 else
                              t("1 lettertype dat je zelf installeerde. Elk programma kan het gebruiken.",
                                "1 font you installed yourself. Every program can use it.")).format(n=len(letters))))
    tb = ob.thunderbird_op_stick(bron, i) is not None
    pst = ob.outlook_bestanden(bron, i)
    if tb or pst:
        wat = []
        if tb:
            wat.append(t("je Thunderbird (accounts, mappen en adresboek, zonder wachtwoorden)",
                         "your Thunderbird (accounts, folders and address book, without passwords)"))
        if pst:
            wat.append(t("je Outlook-mailbestanden", "your Outlook mail files"))
        tekst = t(" en ", " and ").join(wat)
        uit.append(Onderdeel("mail", "lijn:mail", tekst[:1].upper() + tekst[1:] + "."))
    return uit


# ============================================================ instellingen ===

def _tz() -> dict:
    """De tabel Windows-tijdzone -> IANA (uit CLDR windowsZones.xml, staat in /usr/share/bugos)."""
    if not hasattr(_tz, "data"):
        try:
            _tz.data = _dict(json.loads((DATA / "windows-tijdzones.json").read_text(encoding="utf-8")).get("zones"))
        except (OSError, ValueError):
            _tz.data = {}
    return _tz.data


# CLDR noemt nog een paar oude namen (ze werken, maar Instellingen laat de nieuwe zien): de nieuwe gebruiken.
NIEUWE_NAAM = {"Asia/Calcutta": "Asia/Kolkata", "Europe/Kiev": "Europe/Kyiv", "Asia/Katmandu": "Asia/Kathmandu",
               "Asia/Rangoon": "Asia/Yangon", "Asia/Saigon": "Asia/Ho_Chi_Minh", "America/Godthab": "America/Nuuk",
               "Pacific/Truk": "Pacific/Chuuk", "Pacific/Ponape": "Pacific/Pohnpei",
               "Atlantic/Faeroe": "Atlantic/Faroe", "America/Buenos_Aires": "America/Argentina/Buenos_Aires"}


def land_van(code: str) -> str:
    """'nl-NL' of 'nl_NL' -> 'NL'; 'nl' -> ''. (Het land maakt de tijdzone precies: W. Europe -> Amsterdam.)"""
    delen = re.split(r"[-_]", code or "")
    return delen[-1].upper() if len(delen) >= 2 and re.fullmatch(r"[A-Za-z]{2}", delen[-1]) else ""


def iana_zone(windows_id: str, land="") -> str:
    """'W. Europe Standard Time' (+ land 'NL') -> 'Europe/Amsterdam'. Onbekend: ''. 'land' mag ook een rij landen
    zijn (notatie, dan taal): de eerste die bij deze Windows-zone hoort, telt. Zo krijgt iemand met notatie 'en-US'
    en taal 'en-NL' in 'W. Europe' Amsterdam, niet Berlijn (VM-test 2026-11-16). Zonder passend land de zone die
    CLDR voor de hele Windows-zone kiest ('001')."""
    zones = _dict(_tz().get(windows_id))
    landen = [land] if isinstance(land, str) else list(land)
    zone = next((zones[l.upper()] for l in landen if l and l.upper() in zones), "") or zones.get("001") or ""
    return NIEUWE_NAAM.get(zone, zone) if isinstance(zone, str) else ""


# Windows-toetsenbord (KLID, 8 tekens hex) -> xkb (layout, variant). Alleen de gewone: een onbekende raden we niet,
# die melden we (dan kies je hem zelf in Instellingen > Tijd en taal > Toetsenbord).
KLID = {
    "00000409": ("us", ""), "00020409": ("us", "intl"), "00010409": ("us", "dvorak"),
    "00000809": ("gb", ""), "00001809": ("ie", ""), "00004009": ("in", "eng"),
    "00000413": ("nl", ""), "00000813": ("be", ""), "0000080C": ("be", ""), "0001080C": ("be", ""),
    "00000407": ("de", ""), "00000C07": ("at", ""), "00000807": ("ch", ""), "0000100C": ("ch", "fr"),
    "0000040C": ("fr", ""), "0000140C": ("fr", ""), "00001009": ("ca", "fr"), "00011009": ("ca", "multix"),
    "00000C0C": ("ca", "fr-legacy"), "0000040A": ("es", ""), "0000080A": ("latam", ""), "00000410": ("it", ""),
    "00000816": ("pt", ""), "00000416": ("br", ""), "00010416": ("br", ""), "00000415": ("pl", ""),
    "00010415": ("pl", "qwertz"), "0000041F": ("tr", ""), "0001041F": ("tr", "f"), "00000422": ("ua", ""),
    "00000419": ("ru", ""), "00000401": ("ara", ""), "00000406": ("dk", ""), "0000041D": ("se", ""),
    "00000414": ("no", ""), "0000040B": ("fi", ""), "00000405": ("cz", ""), "0000040E": ("hu", ""),
    "00000408": ("gr", ""), "00000418": ("ro", ""), "00010418": ("ro", "std"), "0000041A": ("hr", ""),
    "00000424": ("si", ""), "0000041B": ("sk", ""), "00000402": ("bg", ""), "0000040D": ("il", ""),
    "00000425": ("ee", ""), "00000426": ("lv", ""), "00000427": ("lt", ""), "00000411": ("jp", ""),
    "00000412": ("kr", ""), "00000429": ("ir", ""), "0000046E": ("lu", ""), "0000040F": ("is", ""),
}


def xkb_voor(klid) -> bi.Indeling | None:
    """'00020409' (of '0409:00020409' zoals Get-WinUserLanguageList het schrijft) -> Indeling('us', 'intl')."""
    tekst = _tekst(klid, 40).upper()
    if ":" in tekst:
        tekst = tekst.split(":", 1)[1]
    if not re.fullmatch(r"[0-9A-F]{1,8}", tekst):
        return None
    paar = KLID.get(tekst.zfill(8))
    return bi.Indeling(*paar) if paar else None


def taal_code(tekst) -> str:
    """'nl-NL' -> 'nl' (de code van BugOS); '' als het niets is."""
    return re.split(r"[-_]", _tekst(tekst, 20))[0].lower()


def taal_naam(code: str) -> str:
    """De naam van de taal zoals BugOS hem laat zien (in die taal zelf: Nederlands, Deutsch)."""
    return next((n for c, _l, n in bi.TALEN if c == code), code)


def regio_code(tekst) -> str:
    """'nl-NL' -> 'nl_NL' (zoals in REGIOS van Instellingen)."""
    delen = re.split(r"[-_]", _tekst(tekst, 20))
    return f"{delen[0].lower()}_{delen[-1].upper()}" if len(delen) >= 2 else ""


def regio_naam(code: str) -> str:
    return next((t(nl, en) for c, nl, en in bi.REGIOS if c == code), code)


# Hoe de klok en de datum er in zo'n land uitzien: een kort voorbeeld bij 'nu -> straks' (D-10). Wie 'Verenigde
# Staten' leest, weet niet dat dat een 12-uursklok en maand/dag betekent; '2:58 PM, 11/16/26' zegt het meteen.
# Alleen de landen met een andere gewoonte dan 24 uur en dag-maand-jaar staan hier; de rest krijgt 14:58 en 16-11-2026
# (met het scheidingsteken van dat land).
_REGIO_VOORBEELD = {
    "en_US": "2:58 PM, 11/16/26", "en_CA": "2:58 p.m., 2026-11-16", "en_AU": "2:58 pm, 16/11/26",
    "en_IN": "2:58 PM, 16/11/26", "en_GB": "14:58, 16/11/2026", "en_IE": "14:58, 16/11/2026",
    "en_ZA": "14:58, 2026/11/16", "ar_EG": "2:58 PM, 16/11/2026",
}


def regio_voorbeeld(code: str) -> str:
    """Een voorbeeld van de klok en de datum in die notatie (zie _REGIO_VOORBEELD); anders 24 uur en dag eerst."""
    if code in _REGIO_VOORBEELD:
        return _REGIO_VOORBEELD[code]
    if code.startswith(("de_", "pl_", "tr_", "uk_")):
        teken = "."
    elif code.startswith(("fr_", "es_", "it_", "pt_", "ar_")):
        teken = "/"
    else:
        teken = "-"
    return f"14:58, 16{teken}11{teken}2026"


def taal_wissel(ins: dict) -> tuple[str, str]:
    """(taal nu, taal van Windows) als die verschillen en BugOS de taal van Windows heeft; anders (nu, '').
    'nu' is de taal die je bij het installeren of in Welkom koos (of later zelf in Instellingen)."""
    nu = bi.taal()
    code = taal_code(_dict(ins).get("taal"))
    if code and code != nu and code in {c for c, _l, _n in bi.TALEN}:
        return nu, code
    return nu, ""


def notatie_wissel(ins: dict) -> tuple[str, str]:
    """(notatie nu, notatie van Windows) als die verschillen en BugOS hem kent; anders (nu, '')."""
    nu = bi.regio()
    code = regio_code(_dict(ins).get("notatie"))
    if code and code != nu and code in {c for c, _nl, _en in bi.REGIOS}:
        return nu, code
    return nu, ""


def schaal_waarde(procent) -> float | None:
    """125 -> 1.25 uit de vaste lijst van Instellingen (SCHALEN); iets wat daar niet in de buurt komt: None."""
    if not isinstance(procent, (int, float)) or isinstance(procent, bool) or not 50 <= procent <= 400:
        return None
    kies = min(bi.SCHALEN, key=lambda s: abs(s - procent / 100))
    return kies if abs(kies - procent / 100) <= 0.13 else None


def instellingen_kort(ins: dict) -> list[str]:
    """Wat er in 'instellingen' staat, in een paar woorden voor het overzicht ('tijdzone Amsterdam', 'donker' ...).
    De taal en de notatie staan hier alleen als ze al zo staan ('taal Nederlands (blijft)'); verschillen ze, dan
    hebben ze elk een eigen schuifje met 'nu -> straks' (D-10). De tijdzone ook als 'nu -> straks'."""
    wat = []
    taal_nu, _straks = taal_wissel(ins)
    if taal_code(ins.get("taal")) == taal_nu:
        wat.append(t("taal {n} (blijft)", "language {n} (stays)").format(n=taal_naam(taal_nu)))
    nl = t("nl", "en") == "nl"
    zone = iana_zone(_tekst(ins.get("tijdzone")), (land_van(_tekst(ins.get("notatie"))), land_van(_tekst(ins.get("taal")))))
    if zone:
        try:
            zone_nu = bi.tijd().zone
        except Exception:  # noqa: BLE001  geen timedatectl: dan alleen de nieuwe zone
            zone_nu = ""
        if zone_nu == zone:
            wat.append(t("tijdzone {z} (blijft)", "time zone {z} (stays)").format(z=bi.mooie_zone(zone, nl=nl)))
        elif zone_nu:
            wat.append(t("tijdzone {nu} -> {z}", "time zone {nu} -> {z}").format(
                nu=bi.mooie_zone(zone_nu, nl=nl), z=bi.mooie_zone(zone, nl=nl)))
        else:
            wat.append(t("tijdzone {z}", "time zone {z}").format(z=bi.mooie_zone(zone, nl=nl)))
    borden = [b for b in (xkb_voor(k) for k in _lijst(ins.get("toetsenborden"))) if b]
    if borden:
        wat.append(t("toetsenbord {b}", "keyboard {b}").format(
            b=bi.toetsenbord_naam(borden[0], nl=t("nl", "en") == "nl")))
    if isinstance(ins.get("donker"), bool):
        wat.append(t("donker", "dark") if ins["donker"] else t("licht", "light"))
    if _dict(ins.get("muis")):
        wat.append(t("muis", "mouse"))
    waarde = schaal_waarde(ins.get("schaal"))
    if waarde:
        wat.append(t("grootte {p}", "size {p}").format(p=f"{round(waarde * 100)} %"))
    return wat


def _taal_en_notatie(ins: dict, met_taal: bool = True, met_notatie: bool = True) -> list[Uitslag]:
    """De taal en de notatie van Windows. met_taal / met_notatie: alleen als je dat schuifje aanzette (D-10). Staat
    het uit en had Windows iets anders, dan zegt de samenvatting dat het blijft zoals het was (geen fout)."""
    uit = []
    code = taal_code(ins.get("taal"))
    regio_oud = bi.regio()
    if code and not met_taal:
        nu, straks = taal_wissel(ins)
        if straks:
            uit.append(Uitslag("taal", GOED, t("Blijft {nu} (Windows had {w}). Wil je dat toch, kies het dan in "
                                               "Instellingen > Tijd en taal.", "Stays {nu} (Windows had {w}). If you "
                                               "want it after all, choose it in Settings > Time and language.").format(
                                                   nu=taal_naam(nu), w=taal_naam(straks))))
        code = ""
    if code:
        if code not in {c for c, _l, _n in bi.TALEN}:
            uit.append(Uitslag("instellingen", NIET,
                               t("Taal '{c}': die heeft BugOS (nog) niet. Kies een andere in Instellingen > Tijd en taal.",
                                 "Language '{c}': BugOS does not have it (yet). Choose another in Settings > Time and "
                                 "language.").format(c=_tekst(ins.get("taal"), 20))))
        elif bi.taal() == code:
            uit.append(Uitslag("instellingen", GOED, t("Taal: {n} (stond al zo).", "Language: {n} (already set).").format(
                n=taal_naam(code))))
        # (onthoud, ..., zet)[-1]: eerst in het logboek hoe het was, dan pas veranderen; het resultaat van het
        # veranderen beslist de elif. Zo blijft de rij elif's (al zo / gelukt / niet gelukt) zoals hij was.
        elif (_onthoud("instelling", naam="taal", oud=bi.taal()),
              # zet_taal zet ook de notatie terug: die dus ook onthouden.
              _onthoud("instelling", naam="regio", oud=regio_oud),
              bi.zet_taal(code))[-1]:
            # zet_taal zet de notatie ook terug naar die van de taal (LC_TIME weg). Staat 'Datum en tijd' uit, dan
            # houden we de notatie die je had (D-10): de taal aan is niet ook een 12-uursklok aan.
            if not met_notatie and regio_oud in {c for c, _nl, _en in bi.REGIOS}:
                bi.zet_regio(regio_oud)
            uit.append(Uitslag("instellingen", GOED,
                               t("Taal: {n}. Dat zie je na opnieuw inloggen.", "Language: {n}. You'll see it after you "
                                 "sign in again.").format(n=taal_naam(code))))
        else:
            uit.append(Uitslag("instellingen", ZELF, t("Taal: lukte niet. Kies hem in Instellingen > Tijd en taal.",
                                                       "Language: did not work. Choose it in Settings > Time and language.")))
    regio = regio_code(ins.get("notatie"))
    if regio and not met_notatie:
        nu, straks = notatie_wissel(ins)
        if straks:
            uit.append(Uitslag("notatie", GOED, t("Blijft zoals in {nu} (Windows had {w}). Wil je dat toch, kies het "
                                                  "dan in Instellingen > Tijd en taal.", "Stays as in {nu} (Windows had "
                                                  "{w}). If you want it after all, choose it in Settings > Time and "
                                                  "language.").format(nu=regio_naam(nu), w=regio_naam(straks))))
        regio = ""
    if regio:
        if regio not in {c for c, _nl, _en in bi.REGIOS}:
            uit.append(Uitslag("instellingen", NIET,
                               t("Notatie van datum en tijd ({c}): die kent BugOS nog niet. Kies er een in Instellingen > "
                                 "Tijd en taal.", "Date and time format ({c}): BugOS does not know it yet. Choose one in "
                                 "Settings > Time and language.").format(c=_tekst(ins.get("notatie"), 20))))
        elif bi.regio() == regio:
            uit.append(Uitslag("instellingen", GOED, t("Datum en tijd zoals in {r} (stond al zo).",
                                                       "Date and time as in {r} (already set).").format(r=regio_naam(regio))))
        elif (_onthoud("instelling", naam="regio", oud=bi.regio()), bi.zet_regio(regio))[-1]:
            uit.append(Uitslag("instellingen", GOED, t("Datum en tijd zoals in {r}.", "Date and time as in {r}.").format(
                r=regio_naam(regio))))
        else:
            uit.append(Uitslag("instellingen", ZELF, t("Notatie: lukte niet. Kies hem in Instellingen > Tijd en taal.",
                                                       "Format: did not work. Choose it in Settings > Time and language.")))
    return uit


def _tijdzone(ins: dict) -> list[Uitslag]:
    windows_id = _tekst(ins.get("tijdzone"), 80)
    if not windows_id:
        return []
    zone = iana_zone(windows_id, (land_van(_tekst(ins.get("notatie"))), land_van(_tekst(ins.get("taal")))))
    if not zone:
        return [Uitslag("instellingen", NIET, t("Tijdzone '{w}': die kent BugOS niet. Kies hem in Instellingen > Tijd en "
                                                "taal.", "Time zone '{w}': BugOS does not know it. Choose it in Settings > "
                                                "Time and language.").format(w=windows_id))]
    mooi = bi.mooie_zone(zone, nl=t("nl", "en") == "nl")
    if bi.tijd().zone == zone:
        return [Uitslag("instellingen", GOED, t("Tijdzone: {z} (stond al zo).", "Time zone: {z} (already set).").format(z=mooi))]
    # Via bugos-tijd en pkexec, net als Instellingen: BugOS vraagt hier je wachtwoord (de klok is van iedereen).
    _onthoud("instelling", naam="tijdzone", oud=bi.tijd().zone)
    if bi.zet_tijdzone(zone):
        return [Uitslag("instellingen", GOED, t("Tijdzone: {z}.", "Time zone: {z}.").format(z=mooi))]
    return [Uitslag("instellingen", ZELF, t("Tijdzone {z}: lukte niet (geen wachtwoord gegeven?). Zet hem in Instellingen > "
                                            "Tijd en taal.", "Time zone {z}: did not work (no password given?). Set it in "
                                            "Settings > Time and language.").format(z=mooi))]


def _toetsenborden(ins: dict) -> list[Uitslag]:
    ruw = [_tekst(k, 40) for k in _lijst(ins.get("toetsenborden"))]
    ruw = [k for k in ruw if k]
    if not ruw:
        return []
    goed: list[bi.Indeling] = []
    onbekend: list[str] = []
    for k in ruw:
        ind = xkb_voor(k)
        if ind is None or not bi.goede_indeling(ind):
            onbekend.append(k)
        elif ind not in goed:
            goed.append(ind)
    uit = []
    nl = t("nl", "en") == "nl"
    if goed:
        goed = goed[:bi.MAX_TOETSENBORDEN]
        namen = ", ".join(bi.toetsenbord_naam(i, nl=nl) for i in goed)
        if bi.toetsenborden() == goed:
            uit.append(Uitslag("instellingen", GOED, t("Toetsenbord: {n} (stond al zo).", "Keyboard: {n} (already set).").format(
                n=namen)))
        elif (_onthoud("instelling", naam="toetsenborden", oud=[[i.layout, i.variant] for i in bi.toetsenborden()]),
              bi.zet_toetsenborden(goed))[-1]:
            uit.append(Uitslag("instellingen", GOED, t("Toetsenbord: {n}.", "Keyboard: {n}.").format(n=namen)
                               + (t(" Wisselen: Windows-toets + spatie.", " Switch: Windows key + space.") if len(goed) > 1 else "")))
        else:
            uit.append(Uitslag("instellingen", ZELF, t("Toetsenbord: lukte niet. Kies het in Instellingen > Tijd en taal.",
                                                       "Keyboard: did not work. Choose it in Settings > Time and language.")))
    if onbekend:
        uit.append(Uitslag("instellingen", ZELF,
                           t("Dit toetsenbord van Windows kent BugOS niet ({k}). Kies het zelf in Instellingen > Tijd en "
                             "taal > Toetsenbord.", "BugOS does not know this Windows keyboard ({k}). Choose it yourself "
                             "in Settings > Time and language > Keyboard.").format(k=", ".join(onbekend[:4]))))
    return uit


def _donker(ins: dict) -> list[Uitslag]:
    donker = ins.get("donker")
    if not isinstance(donker, bool):
        return []
    naam = t("donker", "dark") if donker else t("licht", "light")
    if bi.donker() == donker:
        return [Uitslag("instellingen", GOED, t("Uiterlijk: {n} (stond al zo).", "Appearance: {n} (already set).").format(n=naam))]
    _onthoud("instelling", naam="donker", oud=bi.donker())
    if bi.zet_donker(donker):
        return [Uitslag("instellingen", GOED, t("Uiterlijk: {n}.", "Appearance: {n}.").format(n=naam))]
    return [Uitslag("instellingen", ZELF, t("Uiterlijk: lukte niet. Kies licht of donker in Instellingen > Uiterlijk.",
                                            "Appearance: did not work. Choose light or dark in Settings > Appearance."))]


def snelheid_van_windows(stand) -> int | None:
    """De muissnelheid van Windows (1-20, gewoon 10) -> die van Instellingen (0-100, gewoon 50)."""
    if not isinstance(stand, int) or isinstance(stand, bool) or not 1 <= stand <= 20:
        return None
    if stand <= 10:
        return round((stand - 1) / 9 * 50)
    return 50 + round((stand - 10) / 10 * 50)


def zet_scrollen(sysnaam: str, factor: float) -> bool:
    """Hoeveel een muiswiel per tikje schuift, op één apparaat (KWin InputDevice.scrollFactor, net als 'Scrollsnelheid'
    van KDE; KWin bewaart het zelf in kcminputrc, net als bij zet_aanwijzer). 1.0 is gewoon (3 regels)."""
    if bi.VOORBEELD:
        return True
    if not re.fullmatch(r"[A-Za-z0-9_]{1,40}", sysnaam):
        return False
    return bi.draai("busctl", "--user", "set-property", "org.kde.KWin", f"/org/kde/KWin/InputDevice/{sysnaam}",
                    "org.kde.KWin.InputDevice", "scrollFactor", "d", f"{factor:.2f}", timeout=5)[0] == 0


def _muis(ins: dict) -> list[Uitslag]:
    muis = _dict(ins.get("muis"))
    if not muis:
        return []
    links = muis.get("linkshandig")
    snelheid = snelheid_van_windows(muis.get("snelheid"))
    regels = muis.get("scrollregels")
    regels = regels if isinstance(regels, int) and not isinstance(regels, bool) and 1 <= regels <= 100 else None
    apparaten = bi.aanwijzers()
    if not apparaten:
        return [Uitslag("instellingen", ZELF, t("Muis: er is nu geen muis te zien. Stel hem in via Instellingen > Muis en "
                                                "touchpad.", "Mouse: no mouse can be seen right now. Set it up in Settings > "
                                                "Mouse and touchpad."))]
    gedaan, mislukt = [], False
    for a in apparaten:
        # Links- of rechtshandig geldt in Windows voor alles (ook het touchpad); snelheid en scrollen voor de muis.
        if isinstance(links, bool) and "linkshandig" in a.kan and a.linkshandig != links:
            _onthoud("muis", sysnaam=a.sysnaam, wat="linkshandig", oud=a.linkshandig)
            mislukt |= not bi.zet_aanwijzer(a.sysnaam, "linkshandig", links)
        if a.touchpad:
            continue
        if snelheid is not None and "snelheid" in a.kan and a.snelheid != snelheid:
            _onthoud("muis", sysnaam=a.sysnaam, wat="snelheid", oud=a.snelheid)
            mislukt |= not bi.zet_aanwijzer(a.sysnaam, "snelheid", snelheid)
        if regels is not None:
            try:
                import bugos_overstap_logboek as lb
                oud_factor = lb.lees_scrollen(a.sysnaam)
            except Exception:  # noqa: BLE001
                oud_factor = None
            if oud_factor is not None:
                _onthoud("scrollen", sysnaam=a.sysnaam, oud=oud_factor)
            mislukt |= not zet_scrollen(a.sysnaam, max(0.1, min(10.0, regels / 3)))
    if isinstance(links, bool):
        gedaan.append(t("linkshandig", "left-handed") if links else t("rechtshandig", "right-handed"))
    if snelheid is not None:
        gedaan.append(t("snelheid zoals op Windows", "speed as on Windows"))
    if regels is not None:
        # Ook voor programma's die het wieltje zelf tellen (Qt/KDE): zo veel regels per tikje.
        if not bi.VOORBEELD:
            # Was er niets gezet, dan onthouden we None: terugdraaien haalt de regel dan weer weg.
            _onthoud("kde", bestand="kdeglobals", groep="KDE", sleutel="WheelScrollLines",
                     oud=bi.kde_lees("kdeglobals", "KDE", "WheelScrollLines", "") or None)
            bi.kde_schrijf("kdeglobals", "KDE", "WheelScrollLines", str(regels))
        gedaan.append(t("{n} regels per tikje", "{n} lines per notch").format(n=regels))
    if mislukt:
        return [Uitslag("instellingen", ZELF, t("Muis: niet alles lukte. Kijk in Instellingen > Muis en touchpad.",
                                                "Mouse: not everything worked. Check Settings > Mouse and touchpad."))]
    if not gedaan:
        return []
    return [Uitslag("instellingen", GOED, t("Muis: {w}.", "Mouse: {w}.").format(w=", ".join(gedaan)))]


def _schaal(ins: dict) -> list[Uitslag]:
    """Alles groter of kleiner, maar alleen als het op dit scherm past: dezelfde regel als Instellingen (er moet minstens
    1024 x 700 overblijven, grootste_schaal). Een laptop van 1280 x 800 krijgt dus geen 125 %, ook al had Windows dat."""
    procent = ins.get("schaal")
    if procent is None:
        return []
    waarde = schaal_waarde(procent)
    if waarde is None:
        return [Uitslag("instellingen", NIET, t("Grootte {p} %: die kent BugOS niet.", "Size {p} %: BugOS does not know it.")
                        .format(p=_tekst(str(procent), 8)))]
    p = f"{round(waarde * 100)} %"
    schermen = [s for s in (bi.beeldschermen() or []) if s.aan]
    if not schermen:
        return [Uitslag("instellingen", ZELF, t("Grootte {p}: geen scherm gevonden. Kies hem in Instellingen > Scherm.",
                                                "Size {p}: no display found. Choose it in Settings > Display.").format(p=p))]
    hoofd = next((s for s in schermen if s.hoofd), schermen[0])
    grens = bi.grootste_schaal(hoofd)
    if waarde > grens + 1e-6:
        return [Uitslag("instellingen", NIET,
                        t("Grootte {p}: past niet op dit scherm (hooguit {g}). Het blijft zoals het is.",
                          "Size {p}: does not fit this screen (at most {g}). It stays as it is.").format(
                            p=p, g=f"{round(grens * 100)} %"))]
    if abs(hoofd.schaal - waarde) < 0.01:
        return [Uitslag("instellingen", GOED, t("Grootte: {p} (stond al zo).", "Size: {p} (already set).").format(p=p))]
    # Eén scherm: zoals Instellingen (alle schermen). Meer schermen: alleen het hoofdscherm (daar gold het in Windows).
    _onthoud("schaal", scherm=hoofd.naam if len(schermen) >= 2 else None, oud=hoofd.schaal)
    if bi.zet_schaal(waarde, hoofd.naam if len(schermen) >= 2 else None):
        return [Uitslag("instellingen", GOED, t("Grootte: {p}.", "Size: {p}.").format(p=p))]
    return [Uitslag("instellingen", ZELF, t("Grootte {p}: lukte niet. Kies hem in Instellingen > Scherm.",
                                            "Size {p}: did not work. Choose it in Settings > Display.").format(p=p))]


def zet_instellingen(ins: dict, met_taal: bool = True, met_notatie: bool = True,
                     met_rest: bool = True) -> list[Uitslag]:
    """De instellingen van Windows, elk los: wat mislukt, houdt de rest niet tegen.
    met_taal / met_notatie: de schuifjes 'Taal' en 'Datum en tijd' (D-10; in het venster standaard uit als Windows
    iets anders had); met_rest: het schuifje 'Instellingen' (tijdzone, toetsenbord, donker, muis, grootte).
    Zonder die argumenten: alles (de opdracht --zet zonder venster, en de tests)."""
    ins = _dict(ins)
    uit: list[Uitslag] = []
    stappen = [lambda i: _taal_en_notatie(i, met_taal, met_notatie)]
    if met_rest:
        stappen += [_tijdzone, _toetsenborden, _donker, _muis, _schaal]
    for stap in stappen:
        try:
            uit.extend(stap(ins))
        except Exception as e:  # noqa: BLE001  nooit het hele overzetten laten stoppen om één instelling
            uit.append(Uitslag("instellingen", ZELF, t("Iets ging mis ({e}). Kijk zelf even in Instellingen.",
                                                       "Something went wrong ({e}). Have a look in Settings yourself.")
                               .format(e=type(e).__name__)))
    return uit


# ===================================================================== wifi ===

def wifi_soort(beveiliging: str) -> str:
    """Wat netsh zegt (WPA2-Personal, WPA3-Personal, WPA2-Enterprise, Open, WEP ...) -> 'psk', 'sae', 'open',
    'zakelijk', 'wep' of '' (onbekend). Op woorden, want het kan ook 'WPA2-Persoonlijk' zijn."""
    b = beveiliging.lower()
    if any(w in b for w in ("enterprise", "802.1x", "eap", "onderneming", "zakelijk")):
        return "zakelijk"
    if "wep" in b:
        return "wep"
    if "wpa3" in b and "wpa2" not in b:
        return "sae"
    if "wpa" in b or "personal" in b or "persoonlijk" in b or "psk" in b:
        return "psk"
    # Leeg is 'onbekend', niet 'open': een beveiligd netwerk als open opslaan, geeft alleen een verbinding die mislukt.
    if b in ("open", "none", "geen") or b.startswith("open"):
        return "open"
    return ""


def _bekende_namen() -> tuple[set[str], set[str]]:
    """(namen van alle opgeslagen verbindingen, netwerknamen (SSID) van de opgeslagen wifi)."""
    if bi.VOORBEELD:
        return set(bi.VB_NET["opgeslagen"]), set(bi.VB_NET["opgeslagen"])
    namen = set()
    code, uit = bi.draai("nmcli", "-t", "-f", "NAME", "connection", "show")
    if code != 0:
        raise OSError("nmcli")
    for regel in uit.splitlines():
        delen = bi.splits_nmcli(regel)
        if delen and delen[0]:
            namen.add(delen[0])
    return namen, {o.naam for o in bi.opgeslagen_wifi()}


def nieuw_wifi(naam: str, soort: str, verborgen: bool) -> tuple[bool, str]:
    """Maak een wifi-profiel ZONDER wachtwoord. psk-flags 1 ('agent-owned'): het wachtwoord bewaart niet
    NetworkManager maar jouw sessie (de KDE-wachtwoordkluis). Is het netwerk in de buurt, dan vraagt BugOS het één
    keer, en daarna weet hij het. Alleen voor jou (connection.permissions), net als school- en werkwifi in
    Instellingen; dan hoeft er ook geen beheerderswachtwoord bij."""
    if bi.VOORBEELD:
        bi.VB_NET["opgeslagen"].append(naam)
        return True, ""
    cmd = ["nmcli", "connection", "add", "type", "wifi", "con-name", naam, "ssid", naam,
           "connection.permissions", "user:" + bi.login_naam(), "connection.autoconnect", "yes"]
    if soort in ("psk", "sae"):
        cmd += ["wifi-sec.key-mgmt", "wpa-psk" if soort == "psk" else "sae", "wifi-sec.psk-flags", "1"]
    if verborgen:
        cmd += ["802-11-wireless.hidden", "yes"]
    code, uit, fout = bi.draai_nm(*cmd, timeout=20)
    return code == 0, (fout or uit).strip()[:200]


def geldige_ssid(naam: str) -> bool:
    """Een wifi-naam: 1 tot 32 bytes, zonder stuurtekens. ('-' vooraan mag niet: dan leest nmcli het als optie.)"""
    return bool(naam) and len(naam.encode("utf-8")) <= 32 and naam.isprintable() and not naam.startswith("-")


def zet_wifi(lijst) -> list[Uitslag]:
    """De wifi-netwerken van Windows, op naam. Een netwerk dat BugOS al kent (dezelfde naam of netwerknaam),
    blijft precies zoals het is: nooit overschrijven."""
    netten = []
    for w in _lijst(lijst):
        w = _dict(w)
        naam = _tekst(w.get("naam"), 64)
        if naam:
            netten.append((naam, wifi_soort(_tekst(w.get("beveiliging"), 60)), w.get("verborgen") is True))
    if not netten:
        return []
    try:
        namen, ssids = _bekende_namen()
    except OSError:
        return [Uitslag("wifi", ZELF, t("Wifi kon BugOS nu niet bekijken. Verbind zelf in Instellingen > Wifi en internet.",
                                        "BugOS could not look at Wi-Fi right now. Connect yourself in Settings > Wi-Fi "
                                        "and internet."))]
    opgeslagen, al, zakelijk, anders, mislukt = [], [], [], [], []
    for naam, soort, verborgen in netten:
        if naam in namen or naam in ssids:
            al.append(naam)
        elif soort == "zakelijk":
            zakelijk.append(naam)
        elif soort not in ("psk", "sae", "open") or not geldige_ssid(naam):
            anders.append(naam)
        else:
            gelukt, melding = nieuw_wifi(naam, soort, verborgen)
            (opgeslagen if gelukt else mislukt).append(naam)
            if gelukt:
                namen.add(naam)   # twee keer hetzelfde netwerk op de stick: één profiel
                # nmcli zegt "Connection 'x' (<uuid>) successfully added.": met de uuid halen we bij terugdraaien
                # precies dit profiel weg (ook als er later een tweede met dezelfde naam bij kwam).
                m = re.search(r"\(([0-9a-fA-F-]{36})\)", melding)
                _onthoud("wifi", naam=naam, uuid=m.group(1) if m else "")
    uit = []
    if opgeslagen:
        uit.append(Uitslag("wifi", GOED, t("Opgeslagen: {n}. Ben je in de buurt, dan vraagt BugOS één keer het wachtwoord.",
                                           "Saved: {n}. When you're nearby, BugOS asks for the password once.").format(
                                               n=_kort(opgeslagen, 5))))
    if al:
        uit.append(Uitslag("wifi", GOED, t("Al bekend, niets veranderd: {n}.", "Already known, nothing changed: {n}.").format(
            n=_kort(al, 5))))
    if zakelijk:
        uit.append(Uitslag("wifi", ZELF, t("School- of werknetwerk: {n}. Log één keer in via Instellingen > Wifi en internet "
                                           "(met je naam en wachtwoord van school of werk).",
                                           "School or work network: {n}. Sign in once in Settings > Wi-Fi and internet "
                                           "(with your school or work name and password).").format(n=_kort(zakelijk, 5))))
    if anders:
        uit.append(Uitslag("wifi", ZELF, t("Verbind zelf in Instellingen > Wifi en internet: {n}.",
                                           "Connect yourself in Settings > Wi-Fi and internet: {n}.").format(n=_kort(anders, 5))))
    if mislukt:
        uit.append(Uitslag("wifi", ZELF, t("Opslaan lukte niet: {n}. Verbind zelf in Instellingen > Wifi en internet.",
                                           "Saving did not work: {n}. Connect yourself in Settings > Wi-Fi and internet.")
                           .format(n=_kort(mislukt, 5))))
    return uit


# ================================================================= printers ===

def printer_adres(tekst: str) -> str:
    """Het adres van een Windows-printer zoals BugOS het typt: 'IP_192.168.1.40' en '192.168.1.40_1' (namen van
    Windows-poorten) -> '192.168.1.40'; 'http://printer:631/ipp/print' -> 'printer:631'. Anders zoals het is."""
    tekst = _tekst(tekst, 200)
    m = re.fullmatch(r"(?:IP_)?(\d{1,3}(?:\.\d{1,3}){3})(?:_\d+)?", tekst)
    if m:
        return m.group(1)
    m = re.fullmatch(r"(?:https?|ipps?)://([A-Za-z0-9.\-\[\]:]+)(?:/.*)?", tekst)
    if m:
        return m.group(1).split(":")[0] if not m.group(1).startswith("[") else m.group(1)
    return tekst


def _bestaande_printers() -> dict[str, str]:
    """{wachtrij: apparaat-uri} van de printers die er al zijn."""
    if bi.VOORBEELD:
        return {p.naam: "" for p in bi.printers()}
    return bi.lees_lpstat_v(bi.draai("lpstat", "-v", timeout=8)[1])


def _al_toegevoegd(adres: str, apparaten: dict[str, str]) -> str:
    """De wachtrij die al naar dit adres gaat (ipp://192.168.1.40/..., socket://192.168.1.40:9100), of ''."""
    if not adres:
        return ""
    gezocht = adres.split(":")[0].strip("[]").lower()
    for naam, uri in apparaten.items():
        # 'ipp://192.168.1.40:631/ipp/print' -> '192.168.1.40': de poort en het pad doen er niet toe.
        if bi.adres_host(uri).split(":")[0].strip("[]").lower() == gezocht:
            return naam
    return ""


def printer_erbij(naam: str, adres: str) -> tuple[str, str]:
    """Voeg een printer toe op zijn adres, zoals 'Printer toevoegen > Op adres' in Instellingen: IPP Everywhere
    (zonder software van de maker), eerst ipp:// en dan ipps://. Met de naam uit Windows, die zie je in het
    printvenster. Geeft (soort, wachtrij) zoals printer_toevoegen_adres."""
    import bugos_config_meldingen as bm
    kandidaten = bi.adres_kandidaten(adres)
    if not kandidaten:
        return "geen_adres", ""
    basis = bm.schone_tekst(naam) or bi.adres_vervolg(adres)[0]
    if bi.VOORBEELD:
        return bm._vb_voeg_toe(basis, basis, "")
    soort, wachtrij = bm._voeg_toe(basis, [(u, u) for u in kandidaten], "everywhere", basis, "")
    return ("geen_antwoord" if soort == "anders" else soort), wachtrij


PRINTER_REDEN = {
    "onbereikbaar": ("antwoordt niet. Staat hij aan, en zit hij op hetzelfde netwerk?",
                     "does not answer. Is it switched on, and on the same network?"),
    "geen_driverless": ("heeft software van de maker nodig. Kies merk en model in Instellingen > Printers en scannen.",
                        "needs software from the maker. Choose brand and model in Settings > Printers and scanning."),
    "geen_antwoord": ("antwoordt niet als een gewone printer. Probeer hem in Instellingen > Printers en scannen.",
                      "does not answer like a normal printer. Try it in Settings > Printers and scanning."),
    "geweigerd": ("geen wachtwoord gegeven. Voeg hem toe in Instellingen > Printers en scannen.",
                  "no password given. Add it in Settings > Printers and scanning."),
    "geen_adres": ("heeft geen netwerkadres dat BugOS kan gebruiken.", "has no network address BugOS can use."),
}


def zet_printers(lijst) -> list[Uitslag]:
    """De netwerkprinters van Windows. Wat niet lukt, staat in de lijst (met wat je kunt doen), en de rest gaat door."""
    printers_ = []
    for p in _lijst(lijst):
        p = _dict(p)
        adres = printer_adres(p.get("adres"))
        naam = _tekst(p.get("naam"), 100) or adres
        if naam:
            printers_.append((naam, adres, p.get("standaard") is True))
    if not printers_:
        return []
    try:
        apparaten = _bestaande_printers()
    except Exception:  # noqa: BLE001
        apparaten = {}
    uit = []
    for naam, adres, standaard in printers_:
        try:
            al = _al_toegevoegd(adres, apparaten)
            if al:
                uit.append(Uitslag("printers", GOED, t("{n}: was er al.", "{n}: was already there.").format(n=naam)))
                continue
            soort, wachtrij = printer_erbij(naam, adres)
        except Exception:  # noqa: BLE001  een printer die raar doet, houdt de andere niet tegen
            soort, wachtrij = "geen_antwoord", ""
        if soort == "ok":
            _onthoud("printer", wachtrij=wachtrij, naam=naam)
            if standaard:
                try:
                    import bugos_overstap_logboek as lb
                    _onthoud("standaardprinter", oud=lb.lees_standaardprinter())
                except Exception:  # noqa: BLE001
                    pass
                bi.zet_standaard_printer(wachtrij)
            apparaten[wachtrij] = f"ipp://{adres}/ipp/print"
            uit.append(Uitslag("printers", GOED, (t("{n}: toegevoegd, en je standaardprinter.", "{n}: added, and your "
                                                    "default printer.") if standaard else
                                                  t("{n}: toegevoegd.", "{n}: added.")).format(n=naam)))
        else:
            nl, en = PRINTER_REDEN.get(soort, PRINTER_REDEN["geen_antwoord"])
            uit.append(Uitslag("printers", ZELF, f"{naam} ({adres}): " + t(nl, en)))
    return uit


# ============================================================= programma's ===

@dataclass
class Suggestie:
    """Een programma van Windows en wat BugOS ervoor heeft. soort: winkel / ingebouwd / niet."""
    soort: str
    naam: str                   # de naam op BugOS (of de Windows-naam als er niets is)
    id: str                     # Flathub-id voor de Winkel ('' als er niets te openen is)
    tekst: str                  # één eerlijke regel
    windows: list[str] = field(default_factory=list)   # de Windows-namen die hierbij horen


_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]*(\.[A-Za-z0-9_-]+){2,}")


def app_regels(pad: Path | None = None) -> list[dict]:
    """De regels uit overstap-apps.json, met hun regex al klaar. Een kapotte regel slaan we over."""
    try:
        data = json.loads((pad or DATA / "overstap-apps.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    regels = []
    for r in _lijst(_dict(data).get("apps")):
        r = _dict(r)
        try:
            patroon = re.compile(str(r.get("windows", "")), re.IGNORECASE)
        except re.error:
            continue
        if r.get("soort") not in ("winkel", "ingebouwd", "niet", "negeer") or not patroon.pattern:
            continue
        if r.get("id") and not _ID.fullmatch(str(r["id"])):
            continue
        regels.append(dict(r, patroon=patroon))
    return regels


def suggesties(programmas, regels: list[dict] | None = None) -> tuple[list[Suggestie], list[str]]:
    """(voorstellen, programma's zonder regel). Elk programma hoort bij de eerste regel die past; een BugOS-app staat
    er één keer (Word en Excel samen bij LibreOffice). Hulpstukken van Windows (negeer) verdwijnen. Nooit installeren:
    dit is alleen wat we laten zien."""
    regels = app_regels() if regels is None else regels
    per: dict[tuple, Suggestie] = {}
    rest: list[str] = []
    for p in _lijst(programmas):
        naam = _tekst(_dict(p).get("naam") if isinstance(p, dict) else p, 120)
        if not naam:
            continue
        regel = next((r for r in regels if r["patroon"].search(naam)), None)
        if regel is None:
            if naam not in rest:
                rest.append(naam)
            continue
        if regel["soort"] == "negeer":
            continue
        sleutel = (regel["soort"], regel.get("id") or "", regel.get("naam") or naam, regel.get("nl", ""))
        s = per.get(sleutel)
        if s is None:
            s = per[sleutel] = Suggestie(regel["soort"], str(regel.get("naam") or naam), str(regel.get("id") or ""),
                                         t(str(regel.get("nl", "")), str(regel.get("en", ""))))
        if naam not in s.windows:
            s.windows.append(naam)
    volgorde = {"winkel": 0, "ingebouwd": 1, "niet": 2}
    lijst = sorted(per.values(), key=lambda s: (volgorde.get(s.soort, 3), s.naam.lower()))
    return lijst, sorted(rest, key=str.lower)


def winkel_opdracht(app_id: str) -> list[str]:
    """De Winkel op de pagina van deze app (bugos-store appstream://<id>); installeren doe je daar zelf."""
    if not _ID.fullmatch(app_id):
        return []
    return ["bugos-store", f"appstream://{app_id}"]


# =========================================================== voorbeeldstand ===

def voorbeeld_uitslagen() -> list[Uitslag]:
    """Een samenvatting zoals na het overzetten (voor de schermtest en de schermfoto's)."""
    return [
        Uitslag("bestanden", GOED, t("Documenten, Afbeeldingen en Muziek staan op hun plek.",
                                     "Documents, Pictures and Music are in place.")),
        Uitslag("bladwijzers", GOED, t("Ze staan in Firefox, in de map 'Van Windows' op de bladwijzerbalk.",
                                       "They are in Firefox, in the 'From Windows' folder on the bookmarks toolbar.")),
        Uitslag("instellingen", GOED, t("Taal: Nederlands. Dat zie je na opnieuw inloggen.",
                                        "Language: Nederlands. You'll see it after you sign in again.")),
        Uitslag("instellingen", GOED, t("Tijdzone: Amsterdam (Europa).", "Time zone: Amsterdam (Europe).")),
        Uitslag("instellingen", NIET, t("Grootte 125 %: past niet op dit scherm (hooguit 100 %). Het blijft zoals het is.",
                                        "Size 125 %: does not fit this screen (at most 100 %). It stays as it is.")),
        Uitslag("wifi", GOED, t("Opgeslagen: Thuis-5G. Ben je in de buurt, dan vraagt BugOS één keer het wachtwoord.",
                                "Saved: Thuis-5G. When you're nearby, BugOS asks for the password once.")),
        Uitslag("wifi", ZELF, t("School- of werknetwerk: eduroam. Log één keer in via Instellingen > Wifi en internet "
                                "(met je naam en wachtwoord van school of werk).",
                                "School or work network: eduroam. Sign in once in Settings > Wi-Fi and internet "
                                "(with your school or work name and password).")),
        Uitslag("printers", ZELF, "HP LaserJet (192.168.1.40): " + t(*PRINTER_REDEN["onbereikbaar"])),
    ]
