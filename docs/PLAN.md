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

## Wat zit er nu al in (versie 0.1)

| Onderdeel | Bestand | Wat het doet |
|---|---|---|
| Bouwrecept | `Containerfile`, `build_files/` | Maakt BugOS van Aurora, met onze spullen erin. |
| BugOS Welkom | `bugos-welkom` | Het eerste scherm: taal, wifi, licht/donker, updates en gamen/programmeren. |
| Windows-programma's | `bugos-exe` | Dubbelklik op een `.exe`. Biedt eerst een betere BugOS-versie aan als die er is. |
| Downloads | `bugos-pakket` | Dubbelklik op een `.rpm` of `.deb`. Eerst kijkt hij in de Winkel, anders zet hij het veilig in een doosje. |
| Updates | `bugos-updates` | Kies "vanzelf" of "zelf". Kan ook "nu" updaten of "terug" naar de vorige versie. |
| Game-modus | `bugos-spelmodus` | Volle kracht, meldingen stil en een FPS-teller. |
| Ontwikkelaarsmodus | `bugos-ontwikkelaar` | VS Code, containers en een dev-doosje met programmeertalen. |
| Lichte stand | `bugos-lichte-stand` | Zet vanzelf de zware effecten uit op oude pc's. |
| Eerste start | `bugos-eerste-start` | Zet LibreOffice, VLC (en zo nodig Steam) klaar. |
| Stijl | `look-and-feel`, `color-schemes` | Taakbalk onderaan, BugOS-kleuren, logo en achtergrond. |
| Bakkerij | `.github/workflows/` | Bouwt BugOS (gewoon en Nvidia) en maakt op verzoek een ISO voor de USB-stick. |

## Het stappenplan

### Fase 1: Fundering ✅ (nu)
- [x] Plan op papier
- [x] BugOS wordt automatisch gebouwd, in een gewone en een Nvidia-versie
- [x] Een ISO voor de USB-stick op verzoek
- [x] De eerste eigen BugOS-onderdelen (zie de tabel hierboven)
- [ ] **Jij:** de eerste versie proberen in een virtuele pc (zie [TESTEN.md](TESTEN.md))

### Fase 2: De eigen jas
- [ ] **BugOS Instellingen**: één simpele app met grote tegels (Wifi, Bluetooth, Scherm, Geluid, Updates, Game-modus, Ontwikkelaarsmodus). Achter "Meer..." zit de volledige KDE-instellingen.
- [ ] **Eigen startmenu**: grote zoekbalk, vastgemaakte apps en recente bestanden.
- [ ] **Snelmenu** rechtsonder: wifi, bluetooth, volume, helderheid en game-modus in één paneel.
- [ ] **BugOS Winkel**: Discover met BugOS-uiterlijk, en alleen veilige en geteste apps vooraan.
- [ ] Een update-melding in BugOS-stijl voor wie "zelf" kiest.

### Fase 3: Overstappen
- [ ] **Windows-overstap**: een Windows-programma dat de USB-stick maakt en je foto's, documenten en browserbladwijzers meeneemt.
- [ ] Een installatieprogramma in BugOS-stijl met simpele vragen.
- [ ] Naast Windows installeren met één knop ("Verdeel mijn schijf").

### Fase 4: Oppoetsen
- [ ] Hulp-app "Er werkt iets niet": controleert wifi, geluid en printer en lost het zelf op.
- [ ] Back-up met één knop naar een USB-schijf.
- [ ] Een vertaal-community voor alle talen.
- [ ] Een eigen website met een downloadknop.

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
