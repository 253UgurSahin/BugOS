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
| Inlogscherm | Proef: SDDM met het BugOS-thema (`/usr/share/sddm/themes/bugos`), aan met `sudo bugos-inlogscherm sddm`; de standaard blijft Plasma Login | 3 (proef) |
| Sessie (startplasma, ksmserver) | Blijft voorlopig: onzichtbaar loodgieterswerk; pas nodig als plasma-workspace uit het image gaat | 4 |
| Takenlijst (libtaskmanager uit plasma-workspace) | Eigen Wayland-client (plasma-window-management) | 4 |
| plasma-workspace en Plasma-pakketten | Uit het image | 4 |

## Fases

1. **Proefsessie** (gebouwd 2026-11-24): `bugos-shell` met paneel, startmenu, snelmenu, klok, takenlijst, achtergrond en meldingen.
   (Toen een aparte proefsessie; sinds fase 4 de gewone sessie 'BugOS'.)
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
4. **De nieuwe schil is de standaard** (gebouwd 2026-11-24).
   - De gewone sessie (op het inlogscherm 'BugOS') geeft het nieuwe bureaublad: `/etc/xdg/plasma-workspace/env/bugos-schil.sh`
     vraagt `bugos-schil kies` en zet dan `BUGOS_SCHIL=1` en `PLASMA_DEFAULT_SHELL=org.bugos.schil`.
   - Terugweg: de sessie **'BugOS klassiek (Plasma)'** op het inlogscherm, de schakelaar **Instellingen > Uiterlijk >
     Het nieuwe BugOS-bureaublad**, of `bugos-schil klassiek`. Een beheerder kan het voor de hele computer kiezen:
     `echo klassiek | sudo tee /etc/bugos/schil`.
   - Vangnet: start de nieuwe schil binnen anderhalve minuut drie keer (hij loopt steeds vast), dan krijg je voor de rest
     van die sessie het klassieke bureaublad, met een melding (`bugos-schil-of-plasma`).
   - **Bewust niet: de Plasma-pakketten uit het image.** `plasma-workspace` is meer dan Plasma: het bevat ook het
     opstarten van de sessie (startplasma, ksmserver), het afmeldscherm waarin het BugOS-uitzetscherm draait
     (ksmserver-logout-greeter), de takenlijst-bibliotheek die de schil gebruikt (libtaskmanager), het herstellen van
     lettertypes en muis bij het inloggen (kcminit), en de pictogrammen van Windows-programma's in het systeemvak
     (xembedsniproxy). Andere pakketten (powerdevil, plasma-nm, xdg-desktop-portal-kde, kscreenlocker) hangen eraan.
     Het eruit halen betekent die hele laag opnieuw schrijven, zonder het te kunnen testen, en dan verdwijnt ook
     'BugOS klassiek' als terugweg. Het blijft dus, net als KWin, als onzichtbare motor. Pas als het nieuwe bureaublad
     een tijd goed werkt op echte computers, kan een volgende stap (een eigen sessie zonder startplasma, een eigen
     takenlijst-client) de klassieke sessie overbodig maken.

Elke fase eindigt met een werkende computer. Sinds fase 4 is 'BugOS klassiek (Plasma)' de terugweg.

## Het inlogscherm (proef met SDDM)

Fedora 44 gebruikt Plasma Login Manager. Het scherm daarvan zit vast in het programma (Main.qml in de qrc, nagekeken in
plasma-login-manager); alleen de achtergrond is in te stellen. Daarom (keuze van de eigenaar, 2026-11-24): SDDM met een
eigen BugOS-thema, eerst als proef.

- BugOS bevat SDDM (`sddm`, `sddm-wayland-plasma` in packages.txt), maar zet het niet aan: `build.sh` houdt Plasma Login
  als standaard (`systemctl enable --force plasmalogin.service`).
- Proberen: `sudo bugos-inlogscherm sddm` en opnieuw opstarten. Terug: `sudo bugos-inlogscherm plasma`.
  Automatisch inloggen (`bugos-login`) gaat mee.
- Het thema volgt de afspraken uit de broncode van SDDM (GreeterApp.cpp, GreeterProxy.h, UserModel, SessionModel).
  Lukt het laden niet, dan toont SDDM zijn ingebouwde scherm: inloggen kan dan nog steeds.
- Start SDDM helemaal niet, dan zet het vangnet (`sddm.service.d/50-bugos-vangnet.conf` met OnFailure=
  `bugos-inlogscherm-terug.service`) vanzelf Plasma Login terug en start het.
- Kun je niet inloggen terwijl SDDM wel draait: Ctrl+Alt+F3, inloggen, `sudo bugos-inlogscherm plasma`. Terug naar een
  vorige BugOS bij het opstarten helpt hier niet: de keuze staat in /etc.
- Veilig bekijken zonder iets te veranderen: `sddm-greeter-qt6 --test-mode --theme /usr/share/sddm/themes/bugos`.
- Werkt de proef goed (inloggen, automatisch inloggen, de proefsessie kiezen), dan wordt SDDM de standaard.

## Android-apps (gebouwd 2026-11-24)

Waydroid: een echt Android (LineageOS, zonder Google) in een container. Elke app krijgt een eigen venster en komt in
het startmenu, zoals een gewone app.

- **Android-apps** in het startmenu (`bugos-android`), ook via Instellingen > Apps en gamen > Geïnstalleerde apps.
  - Nog niet klaar: één knop, **Android klaarzetten**. Dat is ongeveer 1 GB downloaden, en het vraagt één keer je
    wachtwoord (`pkexec /usr/libexec/bugos-android-root klaarzetten`, polkit `org.bugos.android`).
  - Klaar: **Appwinkel F-Droid installeren**, **Een .apk-bestand installeren…**, Android starten of stoppen, en
    **Android verwijderen** (alle Android-apps en hun gegevens weg).
- **Dubbelklik op een `.apk`** opent Android-apps en installeert de app, na een vraag. Is Android nog niet klaar, dan
  zet BugOS het eerst klaar en installeert daarna meteen die app.
- Wat klaarzetten doet (als beheerder): `waydroid init -s VANILLA` (zonder Google), elke app een eigen venster
  (`persist.waydroid.multi_windows=true` in `/var/lib/waydroid/waydroid.cfg`), de firewall laat het netwerk van
  Android door (`waydroid0` in de zone `trusted`), en `waydroid-container.service` aan. In het image staat die dienst
  uit (`build.sh`) tot je Android klaarzet.
- Terminal: `bugos-android status | klaarzetten | installeer <apk> | fdroid | start | stop | verwijderen`.
- De logica staat in `bugos_android.py`. `tools/test_android.py` test alles met een nagemaakte Waydroid.

Eerlijk over de grenzen:
- **Geen Google Play.** Dat mag BugOS niet meeleveren. Apps komen uit F-Droid of als `.apk`. Apps die Google nodig
  hebben (sommige bank-apps, apps met Google-inlog of -meldingen) werken niet.
- **Apps die alleen voor telefoonprocessors (ARM) gemaakt zijn, werken niet** op een gewone pc. Het meeste uit
  F-Droid werkt wel.
- **Nvidia:** Android tekent dan zonder videokaart. Dat is trager, maar het werkt.
- Nog niet getest op een echte computer (hier alleen met een nagemaakte Waydroid). Waydroid heeft de binder van de
  kernel nodig; die zit in de kernel van Fedora.
