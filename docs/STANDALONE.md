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
| Systeemvak (StatusNotifierItem: Steam, Discord ...) | Eigen systeemvak: host, en zelf de watcher als kded er niet is; menu's via dbusmenu | 2 |
| Pictogrammen op het bureaublad | Eigen bureaublad: je bureaubladmap als pictogrammen, met een menu | 2 |
| Meerdere schermen | Taakbalk en bureaublad per scherm; menu's op het scherm waar je klikte | 2 |
| Rechtermuisknopmenu's van de taakbalk | Start (Win+X), een app (Nieuw venster, Vastmaken, Sluiten), een lege plek, het bureaublad | 2 |
| Vastgezette apps op de taakbalk | `~/.config/bugos/taakbalk`, vanuit het startmenu en de takenlijst | 2 |
| Achtergrond (plasma-apply-wallpaperimage) | `~/.config/bugos/achtergrond` (Instellingen schrijft het), licht/donker uit een pakket | 2 |
| Vergrendelscherm (wat je ziet) | Eigen scherm in het shell-pakket `org.bugos.schil`; het wachtwoord controleert kscreenlocker (PAM) | 3 |
| Schermmelding bij volume- en helderheidstoetsen (OSD, in plasmashell) | `org.kde.osdService` in `bugos-shell` | 3 |
| Meldingengeschiedenis (in plasmashell) | Meldingencentrum achter de bel op de taakbalk | 3 |
| Afmelden, opnieuw opstarten, uitzetten (wat je ziet) | Het BugOS-uitzetscherm (`Logout.qml`, was er al) | (al klaar) |
| Inlogscherm | Plasma Login Manager heeft zijn scherm vast in het programma: alleen de achtergrond is van BugOS. Een eigen inlogscherm vraagt een andere inlogbeheerder (zie hieronder) | open |
| Sessie (startplasma, ksmserver) | Blijft voorlopig: onzichtbaar loodgieterswerk; pas nodig als plasma-workspace uit het image gaat | 4 |
| Takenlijst (libtaskmanager uit plasma-workspace) | Eigen Wayland-client (plasma-window-management) | 4 |
| plasma-workspace en Plasma-pakketten | Uit het image | 4 |

## Fases

1. **Proefsessie** (gebouwd 2026-11-24): `bugos-shell` met paneel, startmenu, snelmenu, klok, takenlijst, achtergrond en meldingen.
   Kies op het inlogscherm **"BugOS (nieuwe schil, proef)"**. De gewone sessie blijft precies zoals hij was, dus er
   gaat niets stuk.
2. **Compleet voor elke dag** (gebouwd 2026-11-24): systeemvak, bureaubladpictogrammen, meerdere schermen,
   rechtermuisknopmenu's, vastmaken aan de taakbalk, Bureaublad tonen, je eigen achtergrond.
   Nog open voor een volgende ronde: de meldingengeschiedenis (de bel), uitleg bij het aanwijzen van een pictogram
   in het systeemvak, Alt+F1 (de Meta-toets werkt al; Win+D doet KWin zelf), slepen op het bureaublad.
3. **Eigen sessie** (gebouwd 2026-11-24): het BugOS-vergrendelscherm, de schermmelding bij de volume- en
   helderheidstoetsen, en het meldingencentrum (de bel). Wat je bij afmelden en uitzetten ziet, was al van BugOS.
   - Vergrendelscherm: `bugos-sessie` zet `PLASMA_DEFAULT_SHELL=org.bugos.schil`; kscreenlocker (via KWin) laadt dan
     `/usr/share/plasma/shells/org.bugos.schil/contents/lockscreen/LockScreen.qml`. De gewone sessie haalt die variabele
     weg (`/etc/xdg/plasma-workspace/env/bugos-schil.sh`). Lukt het laden niet, dan toont kscreenlocker zijn eigen
     noodscherm (nagekeken in kscreenlocker Plasma/6.5): niemand wordt buitengesloten.
     Veilig proberen zonder te vergrendelen: `/usr/libexec/kscreenlocker_greet --testing --shell org.bugos.schil`.
   - Bewust niet in fase 3: de sessie zelf (startplasma) en de takenlijst-client. Die zie je niet, en ze zijn pas
     nodig als plasma-workspace uit het image gaat (fase 4). Ze nu vervangen zou alleen risico geven.
   - Het inlogscherm: zie "Open keuze" hieronder.
4. **De nieuwe schil wordt de standaard**, en de Plasma-pakketten gaan uit het image.

Elke fase eindigt met een werkende computer: de proefsessie blijft naast de gewone bestaan tot fase 4.

## Open keuze: het inlogscherm

Fedora 44 gebruikt Plasma Login Manager. Het scherm daarvan zit vast in het programma (Main.qml in de qrc, nagekeken in
plasma-login-manager); alleen de achtergrond is in te stellen, en die is al van BugOS. Een eigen inlogscherm kan op twee
manieren:
1. **Overstappen op SDDM** met een eigen BugOS-thema (SDDM heeft een gedocumenteerde manier om een QML-thema te maken). Raakt het
   inloggen van iedereen, dus eerst als proef.
2. **Wachten** tot Plasma Login Manager thema's ondersteunt, en tot die tijd alleen de BugOS-achtergrond.

## Android-apps

Komt los hiervan: Waydroid (Android in een container, elke app in een eigen venster), met dubbelklik op een `.apk`,
Android-apps in het startmenu, en F-Droid of Aurora Store. Google Play mag niet worden meegeleverd.
