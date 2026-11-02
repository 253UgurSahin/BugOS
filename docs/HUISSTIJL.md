<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="../branding/logo/bugos-logo-wit.svg">
    <img src="../branding/logo/bugos-logo.svg" width="320" alt="BugOS">
  </picture>
</p>

# De BugOS-huisstijl

> Zo ziet BugOS eruit, en waarom. Voor iedereen die iets voor BugOS maakt:
> een app, een plaatje, de website of een presentatie.

## In het kort

1. **Rustig en duidelijk.** Veel ruimte, grote knoppen, gewone woorden.
2. **Eén rode knop per scherm.** Rood is voor het belangrijkste: daar moet je op drukken.
3. **Altijd licht én donker.** Alles wat we maken, werkt in allebei.
4. **Praat zoals tegen oma.** Korte zinnen, "je" en "jij", geen moeilijke woorden.

## Het logo

<p>
  <img src="../branding/logo/bugos-merk.svg" width="96" alt="Het BugOS-beestje">
  &nbsp;&nbsp;
  <img src="../branding/logo/bugos-icoon.svg" width="96" alt="Het BugOS-app-icoon, donker">
  &nbsp;&nbsp;
  <img src="../branding/logo/bugos-icoon-licht.svg" width="96" alt="Het BugOS-app-icoon, licht">
  &nbsp;&nbsp;
  <img src="beelden/merk-op-donker.svg" width="96" alt="Het BugOS-beestje voor een donkere achtergrond, met een licht kopje">
</p>

Ons logo is een **lieveheersbeestje**, gemaakt van simpele vormen:
twee rode vleugels met een smalle spleet ertussen, een zwarte kop met twee witte vlekjes
(net als bij een echt lieveheersbeestje) en twee zwarte stippen op elke vleugel.

**Waarom een lieveheersbeestje?** In computertaal is een *bug* een foutje.
Een lieveheersbeestje is het vriendelijkste beestje dat er is, en het eet de echte
beestjes op. Zo is BugOS ook: het ruimt de problemen voor je op.

### Welk bestand gebruik ik?

Alle bestanden staan in [`branding/logo/`](../branding/logo/) (en als PNG in [`branding/png/`](../branding/png/)).

| Bestand | Wanneer |
|---|---|
| `bugos-logo.svg` | Beestje met het woord BugOS, op een lichte achtergrond. **Dit is het gewone logo.** |
| `bugos-logo-wit.svg` | Hetzelfde, op een donkere achtergrond of een foto. Het kopje is dan licht, zodat het niet verdwijnt. |
| `bugos-merk.svg` | Alleen het beestje, in kleur. Als er weinig ruimte is. |
| `bugos-merk-donker.svg` | Alleen het beestje, op een donkere achtergrond (licht kopje met donkere oogjes). |
| `bugos-merk-systeem.svg` | Binnen BugOS zelf: het kopje kleurt mee met licht en donker. |
| `bugos-merk-inkt.svg`, `-wit`, `-rood` | In één kleur, bijvoorbeeld voor een stempel, sticker of laser. |
| `bugos-icoon.svg` | App-icoon: het beestje op een donkere, ronde tegel. |
| `bugos-icoon-licht.svg` | App-icoon op een lichte tegel. |
| `bugos-woordmerk.svg`, `-wit` | Alleen het woord BugOS. |

### Regels voor het logo

- **Ruimte eromheen:** houd rondom minstens de breedte van de kop van het beestje vrij.
- **Op donker:** gebruik altijd een variant voor donker (`-donker` of `-wit`). Het gewone beestje heeft een zwart kopje, en dat verdwijnt op een donkere achtergrond.
- **Niet te klein:** het beestje minstens 16 beeldpunten, het logo met woord minstens 96 beeldpunten breed.
- **Niet doen:** uitrekken of platdrukken, draaien, andere kleuren geven, een schaduw of rand eromheen,
  of het woord BugOS in een ander lettertype zetten.

## Kleuren

<img src="../branding/kleuren.svg" width="760" alt="De BugOS-kleuren voor licht en donker, met hun kleurcodes">

- **Rood is spaarzaam.** Gebruik het voor de belangrijkste knop, iets wat gekozen is, en het logo. Niet voor grote vlakken tekst.
- **Grijs is een beetje warm.** Onze grijzen hebben een heel klein beetje rood erin. Nooit puur grijs.
- **Goed, let op en fout** zijn alleen voor meldingen (groen, oranje en rood), altijd samen met een teken (✓, !, ✕) en tekst. Kleur alleen is niet genoeg: niet iedereen ziet kleuren goed.
- **Het logo** gebruikt een verloop van koraal naar rood: `#FF5C50` → `#E52F3E` (linkervleugel) en `#EE3F49` → `#C41D3A` (rechtervleugel), met inkt `#16171C`.

De kleuren staan ook in de code: [`bugos_ui.py`](../system_files/usr/lib/bugos/python/bugos_ui.py) (apps),
[`BugOSLicht.colors`](../system_files/usr/share/color-schemes/BugOSLicht.colors) en
[`BugOSDonker.colors`](../system_files/usr/share/color-schemes/BugOSDonker.colors) (bureaublad).

## Letters

| Lettertype | Waarvoor |
|---|---|
| **Funnel Display** | Koppen en het woord BugOS. Rond en vriendelijk, met karakter. |
| **Inter** | Alle tekst in BugOS zelf: menu's, knoppen en apps. |
| **Atkinson Hyperlegible Next** | Lopende tekst op de website. Speciaal gemaakt om extra goed leesbaar te zijn, ook voor mensen die slecht zien. |
| **JetBrains Mono** | Code en de terminal. |
| Segoe UI | Alleen in BugOS Overstap op Windows (daar hoort het bij Windows zelf). |

Alle lettertypes zijn gratis en open (licentie: SIL Open Font License).
Ze staan in [`branding/lettertypes/`](../branding/lettertypes/) en zitten ook in BugOS zelf.
De website gebruikt eigen kopieën en haalt **niets** bij Google: zo blijft je bezoek privé.

## De achtergrond: "Stip"

<p>
  <img src="../website/assets/stip-licht.webp" width="380" alt="De lichte Stip-achtergrond: ronde lagen van zacht roze naar rood, met één zwarte stip">
  <img src="../website/assets/stip-donker.webp" width="380" alt="De donkere Stip-achtergrond: ronde lagen van diep rood naar koraal, met één zwarte stip">
</p>

Ronde lagen die van licht naar diep rood lopen, met één zwarte stip, zoals de stip op een
lieveheersbeestje. Er is een lichte en een donkere versie; BugOS kiest vanzelf de goede.
De achtergrond komt ook terug in het welkomstscherm, het opstartscherm, het inlogscherm,
BugOS Overstap en op de website.

Opnieuw maken (in 3840 × 2160 en 3840 × 2400):

```bash
node tools/achtergrond/maak.js achtergronden
```

## Vormen

- **Rond, maar niet te rond.** Knoppen 12 beeldpunten, kaarten 16, grote vlakken 22 tot 28.
  Op de website zijn de knoppen helemaal rond.
- **Ruimte:** we gebruiken stapjes van 4: 4, 8, 12, 16, 24, 32, 48.
- **Icoontjes:** in BugOS de iconen van KDE (Breeze). Op de website simpele lijntjes-iconen
  met ronde uiteinden. Een melding krijgt een gekleurd rondje met een wit teken.
- **Geen emoji** in apps en op de website. Wel echte iconen.

## Zo praten we

| Niet zo | Wel zo |
|---|---|
| Er is een fout opgetreden (code 0x80070005). | Dat lukte niet, want je hebt geen toestemming. Druk op "Opnieuw" en kies "Ja" als Windows het vraagt. |
| Rollback naar vorige deployment | Terug naar de versie van gisteren |
| Container | Doosje |
| Flatpak installeren | Installeren |
| OK | Zeg wat er gebeurt: "Bestanden kopiëren", "USB-stick maken" |
| U | Je, jij |

- **Korte zinnen.** Eén ding per zin.
- **Zeg wat er gebeurt** en wat iemand kan doen. Nooit iemand de schuld geven.
- **Vraag het eerst** als er iets weg kan gaan, en zeg dan precies wat: "Alles op de USB-stick wordt gewist."
- **Moeilijk woord nodig?** Leg het meteen uit, tussen haakjes of in een tweede zin.

## Bestanden opnieuw maken

| Wat | Hoe |
|---|---|
| Alle logo's (SVG) | `python3 tools/merk/maak.py` (heeft `uharfbuzz` en `fonttools` nodig) |
| Logo als PNG | `node tools/merk/png.js branding/logo/bugos-icoon.svg branding/png/bugos-icoon-512.png 512` |
| Achtergrond "Stip" | `node tools/achtergrond/maak.js <map>` |
| Kleurenkaart hierboven | `branding/kleuren.svg` (gewoon een SVG; pas de codes aan als de kleuren veranderen) |

De PNG- en achtergrond-hulpjes gebruiken Chromium via [Playwright](https://playwright.dev).
