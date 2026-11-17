"""BugOS: het installatieprogramma (Anaconda WebUI) in gewone woorden. Alleen tijdens het bouwen van de ISO (build.sh).

Woorden: Cockpit kiest per taal een woordenboek po.<taal>.js.gz (Accept-Language of het koekje CockpitLang, bijv.
"en-us", "nl-nl"). Voor Engels is er normaal geen: dan staan de zinnen uit de code zelf er ("Passphrase", "Use entire
disk"). We zetten er een po.en_US.js.gz naast (en een kopie voor elke andere Engelse taal van Anaconda) en zetten de
Nederlandse zinnen achteraan in po.nl.js.gz (de laatste regel telt). index.js zelf veranderen we NIET voor woorden: daar
staat bijvoorbeeld "Timezone" ook als naam van een D-Bus-eigenschap.

Engels vanaf de eerste pagina (engels_vooraf): het venster van het installatieprogramma is slitherer (QtWebEngine; het
profiel van Fedora kiest dat, niet Firefox), en dat stuurt GEEN Accept-Language mee (gemeten in de live-image op
2026-11-12). Cockpit geeft dan een lege po.js, en dus bleven alle Engelse zinnen die van de code ("Installation method",
"Passphrase") zolang je de taal niet zelf aanklikte; pas dan zet de pagina het koekje CockpitLang en haalt hij po.js
opnieuw. Daarom laadt index.html vlak vóór po.js ook bugos-en.js: dezelfde Engelse woorden als po.en_US.js.gz. Komt er
daarna een echt woordenboek (Nederlands, Duits ...), dan wint dat: cockpit.locale() voegt samen en de laatste telt.

Tijdzone: het vinkje "Automatically set timezone" deed niets (BugOS vraagt nooit waar je bent) en hield de keuzelijsten
op America/New_York vast. tijdzone() zet het vinkje standaard uit (de CSS in build.sh verbergt het) en laat het
installatieprogramma de tijdzone raden uit het land van de gekozen taal (nl_NL -> Europe/Amsterdam), alleen als dat land
er één heeft. Dat gebeurt met prioriteit 30 ('taal' in Anaconda); kies je zelf een zone, dan is dat 90, en die wint.

De klok is een ANDER vinkje: "Automatically set date and time, using time servers" (bij ons "De klok vanzelf
gelijkzetten (via internet)", id anaconda-screen-date-time-auto-date-time). Dat staat aan omdat Anaconda het zo
meegeeft: de pagina leest NTPEnabled van de Timezone-module, en die is standaard True (de kickstart van build.sh zet
geen timesource --ntp-disable en geen timezone --nontp). Dat laten we bewust zo, het is goed voor gewone mensen:
aan betekent dat chronyd in het geïnstalleerde BugOS de klok gelijk houdt, net als Windows en elke telefoon. Het vraagt
alleen de tijd aan een tijdserver, niet waar je bent. Uit zou chronyd in het geïnstalleerde BugOS uitzetten
(Anaconda's ConfigureNTPTask), en dan loopt de klok langzaam weg. tijdzone() raakt dit vinkje dus NIET aan; de
CI-test kijkt dat na met het echte stukje uit index.js.

Gebruik (build.sh):  python3 bugos_webui.py /usr/share/cockpit/anaconda-webui [--zone-tab PAD] [--locales en_US,...]
Zonder --locales vraagt het de Engelse talen aan Anaconda zelf (pyanaconda.localization) en kijkt het de tijdzones bij
Anaconda na (pyanaconda.timezone), zodat de keuzelijsten de gok altijd kunnen tonen.
Python 3.12+ (de CI-test draait 3.12); alleen de standaardbibliotheek.
"""

from __future__ import annotations

import gzip
import json
import os
import re
import sys

# Sleutel = de Engelse zin zoals hij in index.js staat (NA de Fedora->BugOS-vervanging van build.sh).
# Waarde = (English, Nederlands). Allemaal nagekeken in anaconda-webui 68 (tools/test_native_installer.py --beeld).
WOORDEN: dict[str, tuple[str, str]] = {
    # Stappen links en paginakoppen
    "Installation method": ("Where to install", "Waar installeren"),
    "Storage configuration": ("Disk", "Schijf"),
    "Create Account": ("Your account", "Je account"),
    "Create account": ("Your account", "Je account"),
    "Review and install": ("Check and install", "Controleren en installeren"),
    "Date and time": ("Date and time", "Datum en tijd"),
    # Datum en tijd. Het vinkje voor de klok (NTP) blijft aan: zie de uitleg bovenaan dit bestand.
    "Automatically set date and time, using time servers": (
        "Set the clock automatically (over the internet)", "De klok vanzelf gelijkzetten (via internet)"),
    # Zonder netwerk staat dat vinkje grijs (en aan); wie eroverheen gaat, krijgt deze uitleg. De Nederlandse
    # vertaling was leeg (dan toont cockpit Engels). Eerlijk: de klok zet zich gelijk zodra BugOS online is.
    "You must be connected to a network to enable automatic date and time.": (
        "Without internet the clock cannot set itself yet. It does so as soon as BugOS is online.",
        "Zonder internet kan de klok zich nog niet gelijkzetten. Dat gebeurt vanzelf zodra BugOS online is."),
    # Het schuifje naast de tijd stond ook in het Nederlands in het Engels (geen vertaling in po.nl).
    "Show AM/PM": ("12-hour clock (AM/PM)", "12-uursklok (AM/PM)"),
    "Timezone": ("Time zone", "Tijdzone"),
    # Waar installeren
    "Destination": ("Install on", "Installeren op"),
    "Change destination": ("Choose another disk", "Een andere schijf kiezen"),
    "How would you like to install?": ("How do you want to install BugOS?", "Hoe wil je BugOS installeren?"),
    "Use entire disk": ("Use the whole disk", "De hele schijf gebruiken"),
    # Ook als er meer schijven gekozen zijn, en ook als er geen Windows op staat (review I12).
    "Remove all partitions on the selected devices, including existing operating systems.": (
        "Everything on the chosen disk is erased: Windows too, if it is there, and your files.",
        "Alles op de gekozen schijf wordt gewist: ook Windows, als dat erop staat, en je bestanden."),
    # Te kleine schijf voor 'De hele schijf gebruiken'. De hint had geen Nederlandse vertaling (dan stond er Engels).
    "Not enough space on selected disks.": ("This disk is too small for BugOS.", "Deze schijf is te klein voor BugOS."),
    "The installation needs $0 of disk space; however, the capacity of the selected disks is only $1.": (
        "BugOS needs $0, but this disk holds only $1.", "BugOS heeft $0 nodig, maar op deze schijf past maar $1."),
    # Staat er al iets op de schijf (Windows, of een eerdere installatie), dan kiest Anaconda zelf 'De schijf delen':
    # de eerste keuze die kan, en die wist niets. Die zinnen waren stijf Nederlands met 'u' en vakwoorden (dual-booten,
    # partities, terugvorderen, aankoppelpunten). Elke sleutel letterlijk uit anaconda-webui 68 (zie --beeld).
    # build.sh zette de eerste twee al in het Nederlands; ze staan nu alleen hier, met Engels erbij.
    "Share disk with other operating systems": (
        "Share the disk with Windows or another system", "De schijf delen met Windows of een ander systeem"),
    "Share disk with other operating systems: $0": ("Share the disk with: $0", "De schijf delen met: $0"),
    "Keep current disk layout and use available space, to dual-boot with another OS.": (
        "What is on the disk now, such as Windows, stays. BugOS goes in the free space next to it.",
        "Wat er nu op de schijf staat, zoals Windows, blijft staan. BugOS komt in de vrije ruimte ernaast."),
    # Te weinig vrije ruimte: de reden en de hint staan achter elkaar onder die keuze, en het vinkje eronder staat dan
    # vast aan. 'Volgende' opent daarna het venster om ruimte te maken (zie hieronder); daar gaat de hint over.
    "Not enough free space on the selected disks.": (
        "There is not enough free space on the disk.", "Er is niet genoeg vrije ruimte op de schijf."),
    "To use this option, resize or remove existing partitions to free up at least $0.": (
        "In the next step you make room: make something smaller or delete something, until at least $0 is free.",
        "In de volgende stap maak je ruimte: maak iets kleiner of verwijder iets, tot er minstens $0 vrij is."),
    "Reclaim space (required)": ("Make room first (needed)", "Eerst ruimte maken (nodig)"),
    "Reclaim additional space": ("Make more room first (optional)", "Eerst meer ruimte maken (hoeft niet)"),
    # Zelf de indeling kiezen. Verbergen voor gewone mensen kan niet op een ondersteunde manier: Anaconda toont deze
    # keuze zodra er bruikbare delen op de schijf staan (geen instelling in het profiel), en hidden_webui_pages
    # verbergt alleen hele pagina's. Dus gewone woorden, met erbij dat het iets voor kenners is.
    "Mount point assignment": ("For experts: my own disk layout", "Voor kenners: mijn eigen schijfindeling"),
    "Assign partitions to mount points. Useful for pre-configured custom layouts.": (
        "Only if you divided the disk yourself beforehand: you choose which part is used for what.",
        "Alleen als je de schijf vooraf zelf hebt ingedeeld: je kiest welk deel waarvoor dient."),
    "Apply mount point assignment and install": ("Use my layout and install", "Mijn indeling gebruiken en installeren"),
    # Het venster na 'De schijf delen' als er te weinig vrij is ('Reclaim space'). Anaconda plant de stappen daar
    # alleen in: er verandert pas iets als je op de laatste pagina op Installeren drukt, en dat zeggen we ook.
    "Reclaim space": ("Make room for BugOS", "Ruimte maken voor BugOS"),
    "Remove or resize existing filesystems to free up space for the installation.": (
        "Choose what may become smaller or be deleted, so that BugOS fits.",
        "Kies wat kleiner mag worden of weg mag, zodat BugOS past."),
    "Removing a filesystem will permanently delete all of the data it contains. Resizing a partition can free up "
    "unused space, but is not risk-free. Be sure to have backups of anything important before reclaiming space.": (
        "Deleting a part erases everything on it for good. Making a part smaller keeps its files, but is never "
        "completely without risk: first copy anything important to a USB stick or another disk. Nothing changes "
        "until you press Install on the last page.",
        "Verwijder je een deel, dan is alles daarop voorgoed weg. Een deel kleiner maken houdt de bestanden erop, "
        "maar is nooit helemaal zonder risico: zet eerst alles wat belangrijk is op een USB-stick of een andere "
        "schijf. Er verandert pas iets als je op de laatste pagina op Installeren drukt."),
    # $0 en $1 worden in het venster vet (cockpit zet er elementen voor in de plaats); dezelfde volgorde houden.
    "Available free space: $0. Installation requires: $1.": (
        "Free space: $0. BugOS needs: $1.", "Vrije ruimte: $0. BugOS heeft nodig: $1."),
    # Alleen kleiner maken kan (het schuifje gaat tot de huidige grootte); 'Resize' en 'shrink' staan alleen hier.
    "Resize": ("Make smaller", "Kleiner maken"),
    "shrink": ("make smaller", "kleiner maken"),
    "shrink to $0": ("make smaller, to $0", "kleiner maken, tot $0"),
    "Unable to schedule deletion of $0": ("$0 cannot be deleted", "$0 kan niet worden verwijderd"),
    "Unable to schedule resizing of $0": ("$0 cannot be made smaller", "$0 kan niet kleiner worden gemaakt"),
    # Windows met BitLocker kan het installatieprogramma niet kleiner maken: zeg hoe het wel kan (in Windows zelf).
    "Windows partitions with BitLocker encryption cannot be resized": (
        "Windows is locked with BitLocker, so it cannot be made smaller here",
        "Windows is vergrendeld met BitLocker, daarom kan het hier niet kleiner"),
    "Reboot into Windows to resize BitLocker-encrypted partitions. Make at least $0 of free space available for "
    "installation.": (
        "Start Windows and make room there: in Disk Management, shrink the Windows drive until at least $0 is free. "
        "Then start from the BugOS USB stick again.",
        "Start Windows en maak daar ruimte: verklein in Schijfbeheer de Windows-schijf tot er minstens $0 vrij is. "
        "Start daarna opnieuw vanaf de BugOS-USB-stick."),
    # Schijf (versleutelen)
    "Encryption": ("Lock with a password", "Vergrendelen met een wachtwoord"),
    "Secure your data using disk-based encryption. Only applies to new partitions": (
        "Nobody can read your files without this password, not even with the disk taken out. "
        "You type it every time the computer starts. Forget it and your files are lost.",
        "Zonder dit wachtwoord kan niemand je bestanden lezen, ook niet als de schijf eruit wordt gehaald. "
        "Je typt het elke keer als de computer opstart. Vergeet je het, dan ben je je bestanden kwijt."),
    "Encrypt my data": ("Lock my files with a password (encryption)",
                        "Mijn bestanden vergrendelen met een wachtwoord (versleuteling)"),
    "Passphrase": ("Password", "Wachtwoord"),
    "Confirm passphrase": ("Type the password again", "Typ het wachtwoord nog een keer"),
    "Passphrases must match": ("The two passwords must be the same", "De twee wachtwoorden moeten hetzelfde zijn"),
    "Must be at least $0 characters": ("At least $0 characters", "Minstens $0 tekens"),
    "Medium": ("Medium", "Redelijk"),
    # Je account
    "Use local account": ("Account on this computer", "Account op deze computer"),
    "A standard user account with admin access for making system-wide changes.": (
        "An ordinary account that may also change the settings of this computer.",
        "Een gewoon account dat ook de computer mag instellen."),
    "Full name": ("Your name", "Je naam"),
    "User name": ("Login name", "Inlognaam"),
    # Controleren en installeren
    "Installation type": ("Disk use", "Schijfgebruik"),
    "Storage": ("Disk", "Schijf"),
    "Erase data and install": ("Erase disk and install", "Schijf wissen en installeren"),
    # Installeren
    "Installing": ("Installing BugOS", "BugOS wordt geïnstalleerd"),
    "Software installation": ("Copying BugOS", "BugOS kopiëren"),
    "System configuration": ("Setting up", "Instellen"),
    "Finalization": ("Finishing", "Afronden"),
    "Storage configuration: Storage is currently being configured.": (
        "Preparing the disk.", "De schijf wordt klaargemaakt."),
    "Software installation: Storage configuration complete. The software is now being installed onto your device.": (
        "BugOS is being copied to this computer. This takes 20 to 40 minutes. The percentage below goes up slowly: "
        "that is normal. Keep the computer on and leave the USB stick in.",
        "BugOS wordt naar deze computer gekopieerd. Dit duurt 20 tot 40 minuten. Het percentage hieronder loopt "
        "langzaam op: dat is normaal. Laat de computer aan en de USB-stick erin."),
    "System configuration: Software installation complete. The system is now being configured.": (
        "Almost done: BugOS is being set up.", "Bijna klaar: BugOS wordt ingesteld."),
    "Finalizing: The system configuration is complete. Finalizing installation may take a few moments.": (
        "Finishing. Nearly there.", "Afronden. Nog heel even."),
    # Klaar. De zin werkt ook op zichzelf: komt het BugOS-venster 'Nu opnieuw opstarten' om wat voor reden ook niet,
    # dan weet je nog steeds wat je moet doen (review I5). $0 (de naam van het systeem) is niet meer nodig.
    "Successfully installed": ("BugOS is installed", "BugOS is geïnstalleerd"),
    "To begin using $0, reboot your system.": (
        "Press Finish, then restart the computer. Take out the USB stick as soon as the screen goes black.",
        "Druk op Afronden en start daarna de computer opnieuw. Haal de USB-stick eruit zodra het scherm zwart wordt."),
    "Exit to live desktop": ("Finish", "Afronden"),
}

KOP = {"": {"language": "en_US", "language-direction": "ltr"}}
WEBUI = "/usr/share/cockpit/anaconda-webui"
ZONE_TAB = "/usr/share/zoneinfo/zone.tab"


# ================================================================================================ tijdzone ===
# Het stukje in index.js (anaconda-webui 68) dat de tijdzone zet als jij kiest: lx=({timezone:t})=>pb("Set...",[t,90]);
# Groep 3 (pb) is de D-Bus-aanroep van de Timezone-module. Precies één keer, anders stopt het bouwen.
R_ZET = re.compile(r'([\w$]+)=\(\{timezone:([\w$]+)\}\)=>([\w$]+)\("SetTimezoneWithPriority",\[\2,90\]\);')
# Het begin van het tijdzonevak: ({locale:t,setSectionValid:e,setTimezoneLabel:o})=>{let[r,l]=(0,oe.useState)(!0)
# (r = het vinkje 'Automatically set timezone', standaard aan). Ook precies één keer. Let op: het vak erboven, 'Date and
# time', begint bijna net zo (({locale:t,setSectionValid:e,timezone:o})=>{let[r,l]=(0,te.useState)(!0)), maar daar is r
# het vinkje voor de klok (NTP), en dat moet aan blijven (zie bovenaan). 'setTimezoneLabel' maakt het verschil.
R_VAK = re.compile(r'\(\{locale:([\w$]+),setSectionValid:([\w$]+),setTimezoneLabel:([\w$]+)\}\)=>\{'
                   r'let\[([\w$]+),([\w$]+)\]=\(0,([\w$]+)\.useState\)\(!0\)')

# Landen met meer zones, waar één zone toch bijna iedereen heeft (review I9): het vasteland. Wie op de Canarische
# eilanden of de Azoren woont, kiest zelf (de pagina vraagt altijd om het na te kijken). De VS, Canada, Australië,
# Brazilië, Rusland, Mexico en Indonesië niet: daar is geen zone die voor bijna iedereen klopt.
VOORKEUR = {"ES": "Europe/Madrid", "PT": "Europe/Lisbon", "NZ": "Pacific/Auckland", "UA": "Europe/Kyiv",
            "CN": "Asia/Shanghai", "CL": "America/Santiago", "EC": "America/Guayaquil"}
_ZONE = re.compile(r"[A-Za-z_]+(/[A-Za-z0-9_+\-]+)+")


def _verschuiving(zone: str) -> tuple:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return tuple(datetime(2026, m, 15, 12, tzinfo=ZoneInfo(zone)).utcoffset() for m in (1, 7))


def landen_met_een_zone(zone_tab: str, verschuiving=_verschuiving) -> dict[str, str]:
    """Land -> tijdzone, alleen als elke zone van dat land op 15 januari en 15 juli dezelfde UTC-tijd heeft
    (Duitsland: Berlin en Busingen, dus wel). De zone is de eerste van dat land in zone.tab.
    Niet langtable: die geeft voor Indonesië alleen Asia/Jayapura."""
    rijen: dict[str, list[str]] = {}
    for regel in zone_tab.splitlines():
        if not regel or regel.startswith("#"):
            continue
        d = regel.split("\t")
        if len(d) >= 3 and re.fullmatch(r"[A-Z]{2}", d[0]) and _ZONE.fullmatch(d[2]):
            rijen.setdefault(d[0], []).append(d[2])
    uit = {}
    for land, zones in sorted(rijen.items()):
        try:
            if len({verschuiving(z) for z in zones}) == 1:
                uit[land] = zones[0]
        except (ValueError, KeyError, OSError):   # een zone die zoneinfo niet kent: dat land niet raden
            continue
    return uit


def tijdzone_tabel(zone_tab: str, geldig=None, verschuiving=_verschuiving) -> dict[str, str]:
    """De tabel voor het installatieprogramma: landen met één zone, plus VOORKEUR (alleen landen uit zone.tab).
    geldig: de zones die Anaconda kent (None = niet nakijken); de rest valt eruit, met een waarschuwing."""
    uit = landen_met_een_zone(zone_tab, verschuiving)
    bekend = {r.split("\t")[0] for r in zone_tab.splitlines() if r and not r.startswith("#")}
    uit.update({land: zone for land, zone in VOORKEUR.items() if land in bekend})
    if geldig is not None:
        weg = sorted(land for land, zone in uit.items() if zone not in geldig)
        if weg:
            print(f"bugos_webui: let op, Anaconda kent de zone van deze landen niet, die raden we niet: {weg}",
                  file=sys.stderr)
        uit = {land: zone for land, zone in uit.items() if land not in weg}
    return dict(sorted(uit.items()))


def tijdzone(js: str, landen: dict[str, str]) -> str:
    """Zet het vinkje 'automatisch' standaard uit en raad de tijdzone uit de taal (prioriteit 30)."""
    assert "bugosTzGok" not in js, "index.js is al aangepast (bugos_webui.py twee keer gedraaid?)"
    assert all(re.fullmatch(r"[A-Z]{2}", k) and _ZONE.fullmatch(v) for k, v in landen.items()), "rare tijdzonetabel"
    m = list(R_ZET.finditer(js))
    assert len(m) == 1, f"SetTimezoneWithPriority: {len(m)} plekken in index.js (anaconda-webui bijgewerkt?)"
    roep = m[0].group(3)
    # json.dumps: niets uit de tabel kan uit de string breken; '<' als < voor de zekerheid.
    tabel = json.dumps(landen, separators=(",", ":"), sort_keys=True).replace("<", "\\u003c")
    # "nl-nl" -> NL; "sr-rs@latin" -> RS; "en" of "de" (geen land) -> niets. Lukt de aanroep niet: niets (geen fout).
    gok = ("var bugosTzLanden=" + tabel + ";"
           "function bugosTzGok(t){try{var m=/^[a-z]{2,3}-([a-z]{2})(?![a-z0-9])/.exec(String(t||\"\"));"
           "var l=m&&m[1].toUpperCase();"
           "var z=l&&Object.prototype.hasOwnProperty.call(bugosTzLanden,l)&&bugosTzLanden[l];if(!z)return;"
           "var p=" + roep + "(\"SetTimezoneWithPriority\",[z,30]);"
           "p&&p.catch&&p.catch(function(){})}catch(e){}}")
    js = js[:m[0].end()] + gok + js[m[0].end():]
    v = list(R_VAK.finditer(js))
    assert len(v) == 1, f"tijdzonevak: {len(v)} plekken in index.js (anaconda-webui bijgewerkt?)"
    loc, react = v[0].group(1), v[0].group(6)
    # Het vinkje start uit (!1), en bij elke taal één gok. De extra naam staat in dezelfde 'let'-lijst, dus de
    # volgorde van de React-hooks blijft vast. (Niet naar latere namen zoals allValidTimezones verwijzen.)
    nieuw = (v[0].group(0)[:-len("(!0)")] + "(!1),bugosTzKlaar=(0," + react + ".useEffect)(()=>{bugosTzGok("
             + loc + ")},[" + loc + "])")
    return js[:v[0].start()] + nieuw + js[v[0].end():]


# Wat tijdzone() erin zet, om het precies terug te kunnen draaien (ontdoe_tijdzone). Het blok met de tabel begint met
# onze eigen naam en eindigt op het einde van bugosTzGok; de tabel is gewone JSON met alleen landcodes en zones (zie de
# assert in tijdzone()), dus '}catch(e){}}' kan er niet in staan.
GOK_BEGIN = "var bugosTzLanden="
GOK_EIND = "p&&p.catch&&p.catch(function(){})}catch(e){}}"
R_HAAK = re.compile(r'\(!1\),bugosTzKlaar=\(0,[\w$]+\.useEffect\)\(\(\)=>\{bugosTzGok\(([\w$]+)\)\},\[\1\]\)')


def ontdoe_tijdzone(js: str) -> str:
    """Het omgekeerde van tijdzone(): geeft index.js terug zoals het uit anaconda-webui kwam (op de Fedora->BugOS-
    woorden van build.sh na). Alleen voor de test in de echte live-image (tools/test_native_installer.py --beeld): daar
    is index.js al aangepast, en zo kan de test nakijken dat tijdzone() op het origineel precies dit beeld oplevert.
    Een andere vorm (niet of twee keer aangepast) geeft een AssertionError."""
    assert js.count(GOK_BEGIN) == 1 and js.count("function bugosTzGok(") == 1, "index.js: geen (of dubbele) gok"
    begin = js.index(GOK_BEGIN)
    eind = js.index(GOK_EIND, begin) + len(GOK_EIND)
    js = js[:begin] + js[eind:]
    haak = list(R_HAAK.finditer(js))
    assert len(haak) == 1, f"index.js: {len(haak)} keer de aangepaste tijdzonehaak"
    return js[:haak[0].start()] + "(!0)" + js[haak[0].end():]


def ingebouwde_tabel(js: str) -> dict[str, str]:
    """De tabel land -> zone die tijdzone() in een (al aangepaste) index.js heeft gezet."""
    begin = js.index(GOK_BEGIN) + len(GOK_BEGIN)
    return json.loads(js[begin:js.index(";function bugosTzGok(", begin)])


def geldige_zones() -> set[str]:
    """De zones die de keuzelijsten van Anaconda kennen ('Europe/Amsterdam', ...)."""
    from pyanaconda.timezone import get_all_regions_and_timezones
    return {f"{regio}/{stad}" for regio, steden in get_all_regions_and_timezones().items() for stad in steden}


def patch_index(map_: str, landen: dict[str, str]) -> int:
    """Pas index.js.gz aan; geeft het aantal tekens dat erbij kwam."""
    pad = os.path.join(map_, "index.js.gz")
    oud = _lees(pad)
    nieuw = tijdzone(oud, landen)
    _schrijf_gz(pad, nieuw)
    return len(nieuw) - len(oud)


# ================================================================================================= woorden ===


def po_engels(taal: str = "en_US") -> str:
    """Een heel Cockpit-woordenboek met de Engelse woorden: cockpit.locale({...});"""
    data: dict = {"": dict(KOP[""], language=taal)}
    data.update({k: [None, en] for k, (en, _nl) in WOORDEN.items()})
    return "cockpit.locale(" + json.dumps(data, ensure_ascii=False, indent=1) + ");\n"


def achter_aan(tekst: str, taal: int) -> str:
    """Zet de woorden (0 = Engels, 1 = Nederlands) achteraan in een bestaand po-bestand; de laatste sleutel telt.
    Zelfde manier als de Nederlandse regels in build.sh. Een onbekende vorm stopt het bouwen (AssertionError)."""
    eind = tekst.rstrip().rfind("\n});")
    assert eind > 0, "po-bestand heeft een onbekende vorm (geen '\\n});' aan het eind)"
    nieuw = "".join(",\n " + json.dumps(k, ensure_ascii=False) + ": [null, " + json.dumps(v[taal], ensure_ascii=False)
                    + "]" for k, v in WOORDEN.items())
    return tekst[:eind] + nieuw + tekst[eind:]


def _lees(pad: str) -> str:
    with gzip.open(pad, "rt", encoding="utf-8") as f:
        return f.read()


def _schrijf_gz(pad: str, tekst: str) -> None:
    with gzip.open(pad + ".nieuw", "wt", encoding="utf-8", compresslevel=9) as f:
        f.write(tekst)
    os.replace(pad + ".nieuw", pad)


def schrijf(map_: str, engelse_locales) -> list[str]:
    """Zet de woorden in de map van het installatieprogramma. Geeft de namen van de bestanden die veranderd zijn."""
    gedaan = []
    for loc in engelse_locales:
        assert re.fullmatch(r"en(_[A-Z]{2})?", loc), f"geen Engelse taal: {loc!r}"
        pad = os.path.join(map_, f"po.{loc}.js.gz")
        if os.path.exists(pad):
            _schrijf_gz(pad, achter_aan(_lees(pad), 0))
        else:
            _schrijf_gz(pad, po_engels(loc))
        gedaan.append(os.path.basename(pad))
    pad = os.path.join(map_, "po.nl.js.gz")
    _schrijf_gz(pad, achter_aan(_lees(pad), 1))
    gedaan.append(os.path.basename(pad))
    return gedaan


# ===================================================================================== Engels vanaf het begin ===
# slitherer stuurt geen Accept-Language mee, dus cockpit geeft bij het openen een lege po.js (zie bovenaan). bugos-en.js
# zet onze Engelse woorden er dan al in, vóór po.js. Zelfde inhoud als po.en_US.js.gz, met dezelfde cockpit.locale(...).
ENGELS_JS = "bugos-en.js"
PO_TAG = '<script type="text/javascript" src="po.js"></script>'
ENGELS_TAG = f'<script type="text/javascript" src="{ENGELS_JS}"></script>'


def html_engels(html: str) -> str:
    """Laat index.html bugos-en.js laden, vlak vóór po.js. Na index.js (daar zit cockpit in, en cockpit.locale moet
    bestaan) en vóór po.js (een echt woordenboek dat daarna komt, wint). Een andere vorm stopt het bouwen."""
    assert ENGELS_JS not in html, "index.html laadt bugos-en.js al (bugos_webui.py twee keer gedraaid?)"
    assert html.count(PO_TAG) == 1, f"index.html: {html.count(PO_TAG)} keer po.js (anaconda-webui bijgewerkt?)"
    assert 0 <= html.find('src="index.js"') < html.find(PO_TAG), "index.html: geen index.js vóór po.js"
    # Zelfde inspringing als de regel van po.js, zodat het bestand er net zo uitziet.
    begin_regel = html.rfind("\n", 0, html.index(PO_TAG)) + 1
    inspring = html[begin_regel:html.index(PO_TAG)]
    return html.replace(PO_TAG, ENGELS_TAG + "\n" + inspring + PO_TAG)


def engels_vooraf(map_: str) -> list[str]:
    """Schrijf bugos-en.js(.gz) en laat index.html hem laden. Geeft de namen van de veranderde bestanden.
    Cockpit levert bugos-en.js.gz als bugos-en.js (gzip als Content-Encoding), net als index.js.gz."""
    _schrijf_gz(os.path.join(map_, ENGELS_JS + ".gz"), po_engels("en_US"))
    pad = os.path.join(map_, "index.html")
    with open(pad, encoding="utf-8") as f:
        html = f.read()
    with open(pad + ".nieuw", "w", encoding="utf-8", newline="") as f:
        f.write(html_engels(html))
    os.replace(pad + ".nieuw", pad)
    return [ENGELS_JS + ".gz", "index.html"]


def engelse_locales() -> list[str]:
    """De Engelse talen die Anaconda op de eerste pagina laat kiezen (en_US, en_GB, en_IN ...), zonder .UTF-8."""
    from pyanaconda.localization import get_language_locales
    uit = ["en_US"]
    for loc in get_language_locales("en"):
        kort = loc.split(".")[0].split("@")[0]
        if re.fullmatch(r"en_[A-Z]{2}", kort) and kort not in uit:
            uit.append(kort)
    return uit


def _optie(args: list[str], naam: str) -> str | None:
    if naam not in args:
        return None
    i = args.index(naam)
    waarde = args[i + 1]
    del args[i:i + 2]
    return waarde


def main(argv: list[str]) -> int:
    args = list(argv)
    lijst = _optie(args, "--locales")
    zone_tab = _optie(args, "--zone-tab") or ZONE_TAB
    map_ = args[0] if args else WEBUI
    # Zonder --locales draaien we in de image: dan komen de talen en de geldige zones van Anaconda zelf.
    locales = [x for x in lijst.split(",") if x] if lijst is not None else engelse_locales()
    geldig = geldige_zones() if lijst is None else None
    with open(zone_tab, encoding="utf-8") as f:
        landen = tijdzone_tabel(f.read(), geldig)
    erbij = patch_index(map_, landen)
    print(f"bugos_webui: tijdzone uit de taal voor {len(landen)} landen (index.js +{erbij} tekens)")
    gedaan = schrijf(map_, locales)
    print(f"bugos_webui: woorden in {len(gedaan)} bestanden ({', '.join(gedaan[:3])} ...)")
    # Als laatste: pas als alles hierboven gelukt is, laadt index.html ons Engelse woordenboek.
    print(f"bugos_webui: Engels vanaf de eerste pagina ({', '.join(engels_vooraf(map_))})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
