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
│  Bestanden (de verkenner, met grote tegels)             │
├─────────────────────────────────────────────────────────┤
│  🧱 KDE Plasma (de motor)                               │
│  Vensters · Wifi · Bluetooth · Dolphin (gevorderden)    │
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

## Wat zit er nu al in (versie 0.3)

### Apps die je ziet

| App in het startmenu | Bestand | Wat het doet |
|---|---|---|
| BugOS Welkom | `bugos-welkom` | Het eerste scherm: taal, wifi, licht of donker, updates, gamen of programmeren, en bestanden van Windows terugzetten. |
| Instellingen | `bugos-instellingen` | Zoals Instellingen in Windows, maar rustiger. Start: snelle schuifjes (wifi, bluetooth, nachtlicht, donker) en het volume. Eigen pagina's in gewone woorden: Wifi en internet (netwerken, verbinden met wachtwoord), Bluetooth (apparaten verbinden), Printers en scannen (printers, wachtrij, testpagina, scannen), Geluid (volume, welke luidspreker), Scherm (helderheid, nachtlicht, grootte), Energie (zuinig/gebalanceerd/snel, batterij, scherm uit, slaapstand, aan/uit-knop, dichtklappen), Uiterlijk (licht/donker, achtergrond), Meldingen (niet storen, stil bij games, geluidje, proefmelding), Muis en touchpad (snelheid, linkshandig, scrollrichting, tikken, dubbelklik), Makkelijker zien (grote letters, grote aanwijzer, muis schudden, vergrootglas, plaktoetsen, langzame toetsen, schermlezer), Tijd en taal (klok vanzelf gelijk, tijdzone, taal), Inloggen en wachtwoord (naam, wachtwoord wijzigen, inloggen zonder wachtwoord, scherm op slot), Standaardprogramma's (internet, e-mail, foto's, muziek, video's, PDF, tekst), Updates en meer, Over deze computer. Zoeken over alles. Per pagina 'Meer instellingen (voor gevorderden)' naar KDE. |
| Er werkt iets niet | `bugos-hulp` | Controleert internet, wifi, bluetooth, geluid, printer, opslag en updates. Bij elk probleem staat een knop "Repareer". |
| Back-up | `bugos-backup` | Je bestanden met één knop naar een USB-schijf, en ook weer terug. Er wordt nooit iets weggegooid. |
| Bestanden van Windows | `bugos-overstap` | Zet de bestanden, bladwijzers en achtergrond terug die je met BugOS Overstap van Windows hebt meegenomen. |
| Game-modus aan/uit | `bugos-spelmodus` | Volle kracht, meldingen stil en een FPS-teller. |
| BugOS Winkel | `bugos-winkel` | 37 bekende, veilige apps in 10 onderwerpen, installeren met één klik. "Meer apps zoeken" opent de grote KDE-winkel. |
| Startmenu | `org.bugos.startmenu` | De startknop linksonder (het lieveheersbeestje), standaard. Begroeting, grote zoekbalk die apps én de pagina's van Instellingen vindt, vastgezette apps, recente bestanden, alle apps per onderwerp, en onderin Instellingen, Vergrendelen, Afmelden, Herstarten en Uitzetten. Alt+F1 en de Windows-toets openen het. Liever het KDE-menu? Instellingen → Updates en meer → Taakbalk. |
| Snelmenu | `org.bugos.snelmenu` | Naast het systeemvak, standaard. Grote knoppen voor wifi, bluetooth, game-modus, donker, niet storen en geluid uit, plus de volumeschuif; het pijltje bij een knop opent de bijbehorende pagina van Instellingen (bijvoorbeeld een wifi-netwerk kiezen). |
| Uitzetscherm | `uitzetscherm/Logout.qml` | Het scherm bij Uitzetten, Herstarten of Afmelden: grote tegels Slaapstand, Opnieuw opstarten, Uitzetten (rood), Afmelden en een knop "Toch niet". Via het startmenu telt het 30 seconden af en zegt dat in gewone woorden. Komt in het shell-pakket van Plasma én in de BugOS-look-and-feel. |
| Taakbalk klaarzetten | `bugos-paneel` | Zet het BugOS-startmenu en het snelmenu op de taakbalk (`standaard`, één keer na het inloggen, ook voor wie al een taakbalk had), of één van de twee aan/uit (`startmenu|snelmenu aan|uit|status`). "Uit" zet het KDE-menu terug zoals BugOS het had ingesteld. |
| Bestanden | `bugos-bestanden` | De verkenner: grote tegels met voorbeeldjes, links je vaste plekken en USB-sticks. Kies je iets, dan staat onderin wat je ermee kunt (Openen, Kopiëren, Weggooien...). Weggooien gaat eerst naar de prullenbak (met Ongedaan maken); nooit iets overschrijven. **Deze computer**: al je schijven (USB-stick, externe schijf, tweede schijf, Windows-schijf, sd-kaart, cd) met hoeveel ruimte er nog is; openen met één klik (ook op slot: KDE vraagt het wachtwoord) en veilig verwijderen van de hele stick. Per stick of schijf (knop '…'): naam wijzigen, controleren en repareren, leegmaken. Een **nieuwe, lege schijf**: 'In gebruik nemen' (indelen en formatteren, zoals Schijfbeheer in Windows); daarna is hij er altijd. Schijfbeheer (KDE Partition Manager) voor gevorderden. |
| Taakbeheer | `bugos-taakbeheer` | Zoals Taakbeheer in Windows (Ctrl+Shift+Esc), maar simpeler: bovenaan in gewone woorden hoe het gaat (met een tip als het druk is), open programma's met 'Sluiten' (netjes, en geforceerd als hij niet reageert), prestaties met grafiekjes (processor met temperatuur, geheugen, schijf, internet, videokaart) en programma's die meestarten aan/uit. Onderdelen van BugOS zelf kun je niet per ongeluk stoppen. |
| Schijven openen | `bugos-schijven-openen` | Opent na het inloggen de schijven die in de computer zitten, zodat ze er altijd zijn (zoals D: in Windows). Zonder wachtwoord voor beheerders (polkit-regel). |
| Inloggen zonder wachtwoord | `bugos-inloggen` | Zet het inlogscherm (SDDM) op 'vanzelf inloggen' voor één gebruiker, of weer uit. Instellingen roept het aan via pkexec; KDE vraagt één keer je wachtwoord (polkit-actie org.bugos.inloggen). |
| Meer apps, Schijven, Dolphin | (KDE) | KDE-programma's met een simpele BugOS-naam. Dolphin is de verkenner voor gevorderden. |

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
| Stijl | `look-and-feel`, `color-schemes`, `bugos_ui.py` | Taakbalk onderaan, BugOS-kleuren voor licht en donker, de lettertypes, het logo, de achtergrond "Stip", het opstart-, inlog- en vergrendelscherm en vaste favorieten in het startmenu. Alle BugOS-apps gebruiken hetzelfde ontwerp (`bugos_ui.py`). Zie [HUISSTIJL.md](HUISSTIJL.md). |

### Voor Windows (`windows-overstap/`)

**BugOS Overstap** heeft dezelfde look als BugOS (donkere zijbalk met de stappen, rode knoppen) en werkt in vier stappen:

1. Controleren: kan deze pc BugOS aan? Het kijkt naar 64-bit, geheugen, UEFI, ruimte, BitLocker en Nvidia.
2. Meenemen: documenten, foto's, muziek, video's, bureaublad, downloads, bladwijzers en achtergrond gaan naar een USB-schijf.
3. Ruimte maken: Windows wordt kleiner gemaakt, zodat BugOS ernaast past.
4. USB-stick maken: BugOS wordt vanzelf gedownload (de goede versie voor jouw videokaart), gecontroleerd en op de USB-stick gezet.

### De bakkerij (`.github/workflows/`)

| Workflow | Wat het doet |
|---|---|
| `build.yml` | Bouwt BugOS (gewoon en Nvidia), bij elke verandering en elke nacht. |
| `iso.yml` | Maakt op verzoek een USB-stick (ISO). Standaard is dat de "probeer eerst"-stick met het nieuwe installatieprogramma. Op verzoek zet hij de ISO in stukjes van minder dan 2 GB in een GitHub Release. |
| `windows-overstap.yml` | Controleert het Windows-programma op een echte Windows-computer en pakt het in. Bij een versie-tag (zoals `v0.2`) maakt hij er een download van. |
| `website.yml` | Zet de website (`website/`) online via GitHub Pages. Staat voorlopig op handmatig. |

## Het stappenplan

### Fase 1: Fundering ✅
- [x] Plan op papier
- [x] BugOS wordt automatisch gebouwd, in een gewone en een Nvidia-versie
- [x] Een ISO voor de USB-stick op verzoek
- [x] De eerste eigen BugOS-onderdelen

### Fase 2: De eigen jas ✅
- [x] **BugOS Instellingen** met grote tegels en een zoekbalk
- [x] Een update-melding voor wie "zelf" kiest
- [x] **BugOS Winkel** in eigen stijl, met veilige en geteste apps vooraan
- [x] Vaste favorieten in het startmenu
- [x] **Eigen startmenu**, standaard op de taakbalk (het KDE-menu blijft te kiezen in Instellingen)
- [x] **Snelmenu** in BugOS-stijl, standaard naast het systeemvak

### Fase 3: Overstappen ✅ (het ondertekenen wacht op de manager)
- [x] **Windows-overstap**: pc-controle, bestanden meenemen, ruimte maken, BugOS downloaden en de USB-stick schrijven
- [x] In BugOS: de bestanden van Windows terugzetten met één knop
- [x] **"Probeer eerst"-USB-stick** met het nieuwe installatieprogramma (Anaconda WebUI). Het stelt weinig vragen, waarschuwt bij BitLocker en legt bij Nvidia het blauwe sleutel-scherm uit.
- [x] **De stick ís BugOS**: BugOS zit zelf op de stick en installeert zonder internet. Geen Aurora- of Fedora-namen of -logo's meer op de stick, in het installatieprogramma en in het geïnstalleerde systeem (welkomstscherm, terminal, inlogscherm, "Over dit systeem", startmenu, winkel). De stick start in het Nederlands.
- [x] Een downloadplek voor de ISO: GitHub Releases, in stukjes van minder dan 2 GB. BugOS Overstap plakt ze vanzelf aan elkaar.
- [ ] **Het Windows-programma ondertekenen**, zodat Windows geen waarschuwing geeft. Dit kost normaal geld (een certificaat). Voor open-source projecten kan het gratis via [SignPath Foundation](https://signpath.org). Aanvragen moet de eigenaar van de repo doen, dus **dit is een taak voor de manager**.

### Fase 4: Oppoetsen ✅ (op de punten voor de manager na)
- [x] Hulp-app "Er werkt iets niet"
- [x] Back-up met één knop
- [x] Vertalen zonder programmeren (woordenboekjes per taal)
- [x] Eigen website met een downloadknop (staat klaar, maar is nog niet online)
- [ ] Vrijwilligers vinden voor vertalingen (**manager**)
- [ ] Een eigen domeinnaam voor de website (**manager**)

### Fase 5: Nieuw design ✅
- [x] **Nieuw logo**: een lieveheersbeestje van simpele vormen, in kleur, één kleur en als app-icoon
- [x] **Nieuwe achtergrond "Stip"**, licht en donker
- [x] **Huisstijl** op papier: logo, kleuren, letters, vormen en hoe we praten ([HUISSTIJL.md](HUISSTIJL.md))
- [x] **Alle BugOS-apps** opnieuw ontworpen, in licht en donker: Welkom, Instellingen, Winkel, Er werkt iets niet, Back-up, Bestanden van Windows en de "probeer eerst"-stick
- [x] **Bureaublad**: nieuwe kleuren, eigen lettertypes, startmenu en snelmenu, opstartscherm, inlog- en vergrendelscherm, opstartlogo
- [x] **Nieuwe website** met echte schermafbeeldingen, een probeer-het-zelf voor "terug naar gisteren" en een licht/donker-schuif
- [x] **BugOS Overstap** (Windows) in de nieuwe stijl, scherp op schermen van 125% en 150%
- [x] **Premium-ronde:** eigen BugOS-lijniconen, rustigere apps (alleen problemen krijgen kleur), en een website die het verhaal vertelt: waarom een lieveheersbeestje, de oma-test en een dag in huis

### Voor de manager: wat er nodig is om BugOS uit te delen
- [ ] De **repo** en de **pakketten** (`bugos`, `bugos-nvidia`) op **openbaar** zetten. Zonder dat:
  - kan BugOS Overstap BugOS niet downloaden,
  - en krijgen geïnstalleerde computers geen updates.
  - (Installeren vanaf de "probeer eerst"-stick werkt wél: BugOS zit zelf op de stick.)
- [ ] In **Settings** de standaard-branch op `main` zetten. Dan draait de nachtelijke bouw (met beveiligingsupdates) op `main`.
- [ ] Ondertekenen via SignPath, vrijwilligers en een domeinnaam (zie hierboven).

### Daarna: testen op echte computers
- [ ] De "probeer eerst"-stick op een echte pc proberen
- [x] Startmenu en snelmenu standaard (getest buiten Plasma: tools/qml-test.py, tools/test_start_data.py, tools/test_uitzetscherm.py)
- [ ] Startmenu, snelmenu en uitzetscherm op een echte pc nalopen (Windows-toets, wifi kiezen, uitzetten) — zie TESTEN.md
- [ ] Bureaublad-foto's uit het echte beeld: de fotoronde (`tools/fotos/bureaublad.sh`) start KWin en plasmashell in de container, maar de bouwcomputer heeft geen grafische kaart; de laatste stap (KWin's software-tekenaar) is nog niet bevestigd. Tot dan: foto's uit de fotostudio.
- [ ] BugOS Overstap op een echte Windows-pc proberen (stap 3 en 4 eerst op een reserve-pc)

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
