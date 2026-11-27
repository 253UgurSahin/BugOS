# Programma's van buiten de Winkel

De Winkel blijft de beste plek voor apps: die krijgen vanzelf updates. Maar mensen downloaden ook programma's van een
website. Dit is wat BugOS dan doet (gebouwd 2026-11-24).

## Linux-programma's van een website

| Bestand | Dubbelklik doet | Programma |
|---|---|---|
| `.AppImage` | Vraagt: **Installeren** (in je startmenu, met eigen naam en pictogram), **Alleen openen**, of **In quarantaine proberen** | `bugos-appimage` |
| `.run` (installatiescript) | Uitleg, en dan openen in een terminal (je ziet wat het doet, kunt antwoorden) | `bugos-appimage` |
| `.rpm`, `.deb` | Eerst de Winkel; anders in een eigen "doosje" (distrobox) | `bugos-package` (was er al) |

- Een geïnstalleerde AppImage staat in `~/.local/share/bugos/appimages/`. Uit je home wordt hij verplaatst, van een
  USB-stick gekopieerd. Een nieuwere versie van hetzelfde programma vervangt de oude.
- Naam, pictogram en vensterklasse komen uit het programma zelf (`--appimage-extract`, zonder FUSE).
- Zonder FUSE 2 (`libfuse.so.2`) start BugOS hem uitgepakt (`APPIMAGE_EXTRACT_AND_RUN=1`). `fuse-libs` zit in het image.
- Weghalen: **Instellingen > Geïnstalleerde apps** (daar staan ze tussen de andere apps), of `bugos-appimage verwijder <id>`.

## Windows-programma's

- **Dubbelklik** op `.exe`, `.msi`, `.lnk` (snelkoppeling) of `.bat`/`.cmd` (eerst een vraag: een script kan
  bestanden veranderen) opent het met Wine (`bugos-exe`, zoals eerst).
- **Microsoft Office**: `OfficeSetup.exe` en de installatie van 365 worden herkend. Office 365, 2019 en nieuwer
  werken niet goed met Wine (installeren, activeren en inloggen lopen vast). BugOS biedt dan **Microsoft 365 in je
  startmenu** aan: Word, Excel, PowerPoint, Outlook en OneDrive als web-apps, elk in een eigen venster (de echte Office
  in je browser, gratis met een Microsoft-account). Nee kiezen probeert het installatieprogramma toch.
- **Start een programma meteen niet**, dan vraagt BugOS of je onderdelen van Microsoft wilt toevoegen.
- **Welkom** > "Wat ga je doen?" heeft de schakelaar **Ik gebruik Microsoft Office**: dan staat Microsoft 365 meteen in het startmenu.
- **Windows-programma's** (in het startmenu, en in Instellingen > Geïnstalleerde apps) = `bugos-windows`:
  - je Windows-programma's, met **Verwijderen** (hun eigen verwijderprogramma, zoals in Windows);
  - **Onderdelen van Microsoft**: Visual C++ 2015-2022, .NET Framework 4.8, .NET Desktop Runtime 8,
    Microsoft-lettertypen, DirectX 9, Visual Basic 6 (via `winetricks -q`, dat ze bij Microsoft haalt);
  - de schakelaar **Microsoft 365 in je startmenu**;
  - **C:-schijf openen** en **Opnieuw beginnen** (een lege Windows-map; de oude blijft bewaard).
- `bugos-webapp <https-adres>` opent een web-app in de browser die je in Welkom koos als die een app-venster kan (Edge,
  Chrome, Chromium, Brave), anders een andere geïnstalleerde die het kan, en anders gewoon in de browser.

## Android-apps

Zie `docs/STANDALONE.md`, "Android-apps": `.apk` met dubbelklik, F-Droid, elke app een eigen venster.

## Eerlijk over de grenzen

- Niet elk Windows-programma werkt met Wine. Spellen gaan meestal beter via Steam (Proton).
- Programma's met anti-cheat, stuurprogramma's (drivers) of diepe Windows-koppelingen werken niet.
- Een AppImage of `.run` van een website krijgt geen updates via BugOS: dat doet het programma zelf (of niet).
- Getest met nagemaakte programma's (`tools/test_programmas.py`, `tools/test_exe.sh`), nog niet op een echte computer.
