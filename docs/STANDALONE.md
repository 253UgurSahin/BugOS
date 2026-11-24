# BugOS op eigen benen: de eigen schil (weg A)

> Gekozen door de eigenaar op 2026-11-24: **weg A**. BugOS krijgt een volledig eigen schil (alles wat je ziet en
> aanraakt). KWin blijft alleen de onzichtbare motor die vensters op het scherm tekent. Plasma gaat er helemaal uit.

## Waarom weg A

| Weg | Wat | Werk |
|---|---|---|
| **A. Eigen schil** (gekozen) | Plasma eruit, een eigen BugOS-schil: taakbalk, startmenu, snelmenu, meldingen, bureaublad, systeemvak, vergrendel- en inlogscherm. KWin blijft als motor. | Maanden |
| B. Eigen motor erbij | Daarna ook een eigen compositor (op wlroots of Smithay, zoals COSMIC). | Een jaar of meer |
| C. Alles vanaf nul | Ook alles eronder zelf. | Niet realistisch |

Voor de gebruiker is weg A al "helemaal BugOS": niets van KDE is nog te zien. Bijna elk eigen bureaublad gebruikt een
bestaande motor. Weg B blijft later mogelijk, omdat de schil met gewone Wayland-protocollen praat.

## Hoe de schil in elkaar zit

- **`bugos-shell`**: een klein C++-programma (Qt 6) dat de QML van de schil laadt. C++ en geen Python, omdat KWin de
  vensterlijst (`org_kde_plasma_window_management`) alleen geeft aan een programma dat het herkent aan zijn eigen
  uitvoerbare bestand (`X-KDE-Wayland-Interfaces` in `bugos-shell.desktop`). Een Python-script is voor KWin gewoon
  `python3`.
- **De QML** staat in `/usr/share/bugos/shell/`. Het startmenu en het snelmenu zijn **dezelfde** `StartMenu.qml` en
  `QuickMenu.qml` als in de Plasma-versie: alleen de dunne lijm eromheen is nieuw.
- **De gegevens** komen, net als nu, van `bugos-start-data` (apps, favorieten, snelmenu-status).
- **Vensters op het scherm**: via layer-shell (`org.kde.layershell` van layer-shell-qt): de taakbalk onderaan met
  gereserveerde ruimte, menu's erboven, de achtergrond eronder.

## Wat vervangt wat

| Plasma-onderdeel | BugOS-vervanger | Fase |
|---|---|---|
| plasmashell: taakbalk en paneel | `bugos-shell` paneel | 1 |
| Startmenu-plasmoid (Plasma-lijm) | Paneel + `StartMenu.qml` | 1 |
| Snelmenu-plasmoid | Paneel + `QuickMenu.qml` | 1 |
| Klok-plasmoid | Klok in het paneel, kalender als pop-up | 1 |
| Takenlijst (icontasks) | Eigen takenlijst (fase 1 via libtaskmanager, later eigen Wayland-client) | 1, 3 |
| Bureaublad-achtergrond | Achtergrondvenster (layer-shell, onderste laag) | 1 |
| Meldingen (in plasmashell) | Eigen meldingendienst `org.freedesktop.Notifications` in `bugos-shell` | 1 |
| Meta-toets opent het startmenu | `org.kde.plasmashell /PlasmaShell activateLauncherMenu`, door `bugos-shell` zelf | 1 |
| Systeemvak (StatusNotifierItem: Steam, Discord ...) | Eigen systeemvak (StatusNotifierWatcher + host) | 2 |
| Pictogrammen op het bureaublad | Eigen bureaublad (Bestanden-onderdelen) | 2 |
| Meerdere schermen | Paneel en achtergrond per scherm | 2 |
| Vergrendelscherm (kscreenlocker-greeter) | Eigen greeter-thema of eigen vergrendelscherm | 3 |
| Inlogscherm (plasma-login/SDDM-thema) | Eigen inlogscherm | 3 |
| Sessie (startplasma, ksmserver) | `bugos-sessie` (systemd user-units, eigen afmelden) | 3 |
| plasma-workspace en Plasma-pakketten | Uit het image | 4 |

## Fases

1. **Proefsessie** (nu): `bugos-shell` met paneel, startmenu, snelmenu, klok, takenlijst, achtergrond en meldingen.
   Kies op het inlogscherm **"BugOS (nieuwe schil, proef)"**. De gewone sessie blijft precies zoals hij was, dus er
   gaat niets stuk.
2. **Compleet voor elke dag**: systeemvak, bureaubladpictogrammen, meerdere schermen, sneltoetsen (Alt+F1, Win+D),
   rechtermuisknopmenu's van de taakbalk, ontwerp afmaken.
3. **Eigen sessie**: eigen vergrendel- en inlogscherm, eigen sessiebeheer en afmelden, eigen takenlijst-client.
4. **De nieuwe schil wordt de standaard**, en de Plasma-pakketten gaan uit het image.

Elke fase eindigt met een werkende computer: de proefsessie blijft naast de gewone bestaan tot fase 4.

## Android-apps

Komt los hiervan: Waydroid (Android in een container, elke app in een eigen venster), met dubbelklik op een `.apk`,
Android-apps in het startmenu, en F-Droid of Aurora Store. Google Play mag niet worden meegeleverd.
