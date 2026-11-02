# 🐞 De BugOS-bouwtekening

> Uitgelegd zo simpel als het kan. Als oma het niet snapt, moeten we het opnieuw opschrijven.

## Wat is BugOS?

BugOS is een gratis besturingssysteem voor je computer, net als Windows.
Het is gemaakt voor **iedereen**:

- 👵 **Oma** moet het kunnen gebruiken zonder hulp.
- 🎮 **Gamers** moeten er goed op kunnen spelen.
- 🛠️ **Programmeurs** moeten er fijn op kunnen werken.

Het belangrijkste idee: **BugOS kan niet stuk.**

## De keuzes die we samen hebben gemaakt

| Onderwerp | Wat we kozen | Waarom, in gewone taal |
|---|---|---|
| Fundering | Fedora Atomic (via Aurora van Universal Blue) | Het systeem is van "onbreekbaar glas". Elke update is een complete nieuwe versie. Gaat er iets mis? Dan kies je bij het opstarten de vorige versie. |
| Schil | Eigen BugOS-jas op de KDE-motor | KDE regelt al goed: vensters, wifi, bluetooth en schermen. Wij maken het startmenu, de taakbalk, de stijl en de eigen BugOS-apps. |
| Uiterlijk | Eigen BugOS-stijl, licht of donker | Knoppen zitten waar je ze van Windows kent, maar het ziet er anders uit. Je kiest zelf licht of donker. |
| Updates | Standaard vanzelf, met een schakelaar voor "zelf doen" | Oma hoeft er niks voor te doen. Wie zelf wil kiezen, kan dat. |
| Programma's | De BugOS Winkel, plus dubbelklikken op downloads | Net als je telefoon, en ook net als Windows. |
| Windows-programma's | Dubbelklik op een `.exe` start hem via Wine | Werkt het niet, dan legt BugOS uit wat je in plaats daarvan kunt gebruiken. |
| Gamers | Steam en Proton, game-modus, controllers en Nvidia | Spelen zonder gedoe. |
| Programmeurs | Ontwikkelaarsmodus-schakelaar, containers, VS Code en programmeertalen | Alles staat klaar met één klik, en oma ziet er niks van. |
| Talen | Alle talen van KDE | Onze eigen schermen eerst in het Nederlands en Engels. |
| Installeren | USB-stick, ook naast Windows, plus een Windows-overstap-programma | Overstappen moet makkelijk zijn. |
| Computers | Gewone pc's en laptops, Nvidia, oude pc's (met lichte stand) | De lichte stand gaat vanzelf aan op trage computers. |
| Privacy | Geen account en niks verzamelen | Je computer is van jou. |
| Licentie | GPL-3.0 | Altijd gratis en open. |

## Hoe zit BugOS in elkaar? (het huis)

```
┌─────────────────────────────────────────────────────────┐
│  🐞 BugOS-jas (van ons)                                 │
│  Startmenu · Taakbalk · Stijl · BugOS Welkom · Winkel   │
│  Game-modus · Ontwikkelaarsmodus · Lichte stand         │
│  .exe openen · .rpm/.deb installeren · Updates-knop     │
├─────────────────────────────────────────────────────────┤
│  🧱 KDE Plasma (de motor)                               │
│  Vensters · Wifi · Bluetooth · Bestanden (Dolphin)      │
│  Schijfbeheer (KDE Partition Manager) · Geluid          │
├─────────────────────────────────────────────────────────┤
│  🏠 Aurora / Fedora Atomic (de fundering)               │
│  Drivers · Codecs (films/muziek) · Nvidia · Updates     │
│  met een "terug-knop"                                   │
└─────────────────────────────────────────────────────────┘
```

## Hoe komt een update bij de gebruiker? (de bakkerij)

1. Wij veranderen iets in deze repo.
2. GitHub bakt automatisch een nieuwe BugOS. Dat gebeurt ook elke nacht, zodat beveiligingsupdates van Fedora meekomen.
3. De computer van de gebruiker haalt die op de achtergrond op.
4. Bij de volgende keer opstarten draait de nieuwe versie.
5. Problemen? Dan kies je in het opstartmenu de vorige versie, en alles is weer zoals gisteren.

## Wat zit er nu al in (versie 0.2)

### Apps die je ziet

| App in het startmenu | Bestand | Wat het doet |
|---|---|---|
| BugOS Welkom | `bugos-welkom` | Het eerste scherm: taal, wifi, licht of donker, updates, gamen of programmeren, en bestanden van Windows terugzetten. |
| Instellingen | `bugos-instellingen` | Grote tegels met een zoekbalk: wifi, bluetooth, geluid, scherm, printers, updates, schijven en meer. Plus een pagina met aan/uit-knoppen en "Over deze computer". |
| Er werkt iets niet | `bugos-hulp` | Controleert internet, wifi, bluetooth, geluid, printer, opslag en updates. Bij elk probleem staat een knop "Repareer". |
| Back-up | `bugos-backup` | Je bestanden met één knop naar een USB-schijf, en ook weer terug. Er wordt nooit iets weggegooid. |
| Bestanden van Windows | `bugos-overstap` | Zet de bestanden, bladwijzers en achtergrond terug die je met BugOS Overstap van Windows hebt meegenomen. |
| Game-modus aan/uit | `bugos-spelmodus` | Volle kracht, meldingen stil en een FPS-teller. |
| BugOS Winkel, Bestanden, Schijven | (KDE) | KDE-programma's met een simpele BugOS-naam. |

### Wat op de achtergrond gebeurt

| Onderdeel | Bestand | Wat het doet |
|---|---|---|
| Windows-programma's | `bugos-exe` | Dubbelklik op een `.exe` start hem via Wine. Bestaat er een betere versie in de Winkel, dan wordt die eerst aangeboden. |
| Downloads van websites | `bugos-pakket` | Dubbelklik op een `.rpm` of `.deb`: eerst kijkt hij in de Winkel, anders installeert hij het veilig in een doosje. |
| Updates | `bugos-updates` | Vanzelf of zelf; nu updaten of terug naar de vorige versie. |
| Update-melding | `bugos-updatecheck` | Bij "zelf updaten" krijg je één keer per dag een melding met een knop "Nu updaten". |
| Ontwikkelaarsmodus | `bugos-ontwikkelaar` | VS Code, containers en een dev-doosje met programmeertalen. |
| Lichte stand | `bugos-lichte-stand` | Zet vanzelf de zware effecten uit op oude pc's. |
| Eerste start | `bugos-eerste-start` | Zet LibreOffice, VLC en Steam klaar. |
| Vertalingen | `vertalingen/*.json` | Elke taal kan erbij zonder code te schrijven (zie [VERTALEN.md](VERTALEN.md)). |
| Stijl | `look-and-feel`, `color-schemes` | Taakbalk onderaan, BugOS-kleuren, logo, achtergrond en vaste favorieten in het startmenu. |

### Voor Windows (`windows-overstap/`)

**BugOS Overstap** werkt in vier stappen:

1. Controleren: kan deze pc BugOS aan? Het kijkt naar 64-bit, geheugen, UEFI, ruimte, BitLocker en Nvidia.
2. Meenemen: documenten, foto's, muziek, video's, bureaublad, downloads, bladwijzers en achtergrond gaan naar een USB-schijf.
3. Ruimte maken: Windows wordt kleiner gemaakt, zodat BugOS ernaast past.
4. USB-stick maken: het BugOS .iso-bestand gaat op een USB-stick.

### De bakkerij (`.github/workflows/`)

| Workflow | Wat het doet |
|---|---|
| `build.yml` | Bouwt BugOS (gewoon en Nvidia), bij elke verandering en elke nacht. |
| `iso.yml` | Maakt op verzoek een ISO voor de USB-stick. |
| `windows-overstap.yml` | Controleert het Windows-programma op een echte Windows-computer en pakt het in. Bij een versie-tag (zoals `v0.2`) maakt hij er een download van. |
| `website.yml` | Zet de website (`website/`) online via GitHub Pages. |

## Het stappenplan

### Fase 1: Fundering ✅
- [x] Plan op papier
- [x] BugOS wordt automatisch gebouwd, in een gewone en een Nvidia-versie
- [x] Een ISO voor de USB-stick op verzoek
- [x] De eerste eigen BugOS-onderdelen

### Fase 2: De eigen jas 🟡
- [x] **BugOS Instellingen** met grote tegels en een zoekbalk
- [x] Een update-melding voor wie "zelf" kiest
- [x] De Winkel heet "BugOS Winkel" en Dolphin heet "Bestanden"
- [x] Vaste favorieten in het startmenu
- [ ] **Eigen startmenu** als Plasma-onderdeel (QML). Eerst testen op een echte BugOS-pc. Tot die tijd gebruiken we het KDE-startmenu met BugOS-instellingen.
- [ ] **Snelmenu** rechtsonder in BugOS-stijl. KDE heeft dit al, wij passen het later aan.
- [ ] De BugOS Winkel echt in eigen stijl, met veilige en geteste apps vooraan

### Fase 3: Overstappen 🟡
- [x] **Windows-overstap**: pc-controle, bestanden meenemen, ruimte maken en de USB-stick schrijven
- [x] In BugOS: de bestanden van Windows terugzetten met één knop
- [ ] Het installatieprogramma (Anaconda) in BugOS-stijl
- [ ] Een plek om het ISO-bestand te downloaden. GitHub staat maar 2 GB per bestand toe en de ISO is groter, dus we hebben iets als Cloudflare R2 of SourceForge nodig.
- [ ] Het Windows-programma ondertekenen, zodat Windows geen waarschuwing geeft

### Fase 4: Oppoetsen 🟡
- [x] Hulp-app "Er werkt iets niet"
- [x] Back-up met één knop
- [x] Vertalen zonder programmeren (woordenboekjes per taal)
- [x] Eigen website met een downloadknop
- [ ] Vrijwilligers vinden voor vertalingen
- [ ] Een eigen domeinnaam voor de website

## Dingen om op te letten

- **Nvidia:** we gebruiken de "open" Nvidia-driver. Die werkt op kaarten vanaf ongeveer 2018 (RTX 20-serie en nieuwer, GTX 16-serie). Voor oudere Nvidia-kaarten moeten we later iets regelen.
- **Oude pc's:** BugOS heeft een 64-bit computer nodig met minstens 4 GB geheugen. Héél oude pc's (uit de tijd van Windows XP) gaan niet.
- **Windows-programma's:** niet alles werkt via Wine. Anti-cheat in sommige online games en zware programma's zoals Adobe en de nieuwste Office werken vaak niet. Daarom legt BugOS altijd uit wat het alternatief is.
- **Aurora als fundering:** dat is het snelst en het meest betrouwbaar. Ooit kunnen we overstappen naar een "kalere" fundering (`kinoite-main`) als we meer zelf willen doen.

## Woordenlijst

| Woord | Betekent |
|---|---|
| Distro | Een "smaak" van Linux. BugOS is een distro. |
| Image | Eén compleet pakketje van het hele systeem. |
| Container / doosje | Een afgesloten ruimte waarin een programma draait zonder het systeem te kunnen breken. |
| Flatpak | De manier waarop de Winkel apps installeert. |
| Wine / Proton | De "vertaler" waardoor Windows-programma's en -games werken. |
| KDE Plasma | Het bureaublad (de motor) waar onze BugOS-jas omheen zit. |
| ISO | Het bestand dat je op een USB-stick zet om BugOS te installeren. |
