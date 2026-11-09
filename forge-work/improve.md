# Improve: BugOS (the OS itself)
Date: 2026-11-08   Branch: ccr-5bd1cae9-pccs3q   Started from: ccr-5bd1cae9-pccs3q at d285f6c
Picked: U001-U031 (all). The user said: "/forge-improve bugos os, niet dewebsite of eromheen echt het os gedeelte", then "fix alles"
Tests before: 20 passed, 0 failed (build.yml check job, run here); after: 23 passed, 0 failed (3 new test files: test_os_system.sh, test_os_settings.py, test_os_apps.py). 31 fixed, 0 skipped.
In the built image (kinoite-main:44 + all fixes, built here): bootc container lint passes; tools/test_image.sh 75 of 75
checks pass, including the three new OS test files run on Fedora 44 itself; 16 app screenshots (8 apps, light and dark)
open without errors. Security (forge-secure scanners): PASS, 0 findings.
Secrets before: none (secretscan: no findings).
All changes: git diff d285f6c ccr-5bd1cae9-pccs3q

Where the list comes from: a read-only review of the OS part only (system scripts and services, the apps, Settings,
menus and the installer), 2026-11-08. Facts were checked in the real Fedora 44 base image where possible
(no sddm but Plasma Login Manager; no qdbus6 but qdbus-qt6).
The branch note of the first round still applies: this session may only push to ccr-5bd1cae9-pccs3q, so the work is
there (and in pull request #2).

## To do
(nothing left: all 31 fixed)

## Fixed
### U001 [high] Screen off "Never" still turns the screen off after 30 s and dims at once.
  where: system_files/usr/lib/bugos/python/bugos_config_scherm.py:296-297 (zet_scherm_uit_na), reader scherm_uit_na
  why: writes TurnOffDisplayIdleTimeoutSec=0 / DimDisplayIdleTimeoutSec=0 but leaves TurnOffDisplayWhenIdle and
  DimDisplayWhenIdle at default true; powerdevil 6.5 then uses max(0, 30s) and dims at 0s.
  fix: for 0 write TurnOffDisplayWhenIdle=false and DimDisplayWhenIdle=false; for other values set them true; read them back.
  commit: f5ee399 "Screen off: Never" now really keeps the screen on, without dimming
  commit: 435ad3f a 'Never' saved by an older BugOS is repaired when Settings reads it
  test:   tools/test_os_settings.py
  note:   also: a "Never" saved by an older BugOS is written the right way when Settings reads it.

### U002 [high] "Log in without a password" does nothing on Fedora 44, but the switch shows on.
  where: system_files/usr/bin/bugos-login:10 (BESTAND=/etc/sddm.conf.d/...), bugos_config_account.py:126 (SDDM_BESTANDEN)
  fix: write /etc/plasmalogin.conf.d/50-bugos-login.conf ([Autologin] User= Session= Relogin=false) when
  /usr/lib/plasmalogin exists, else the SDDM path; readers check both. Also: user-name regex rejects valid names
  like jan.jansen (allow dots, keep it strict and `id`-checked).
  commit: c99a92a "Log in without a password" works on Fedora 44 (Plasma Login)
  test:   tools/test_os_settings.py

### U003 [high] Copying/moving a folder to a USB stick copies NOTHING if one file is refused.
  where: system_files/usr/lib/bugos/python/bugos_files_acties.py:166-173 (kopieer_een), :212 (Klus, fout = str(e))
  why: copytree raises shutil.Error for one bad name (':' '?' '*' on FAT/exFAT, EINVAL), then ruim_op deletes the
  whole temp folder; the user sees a raw Python list. Also copy2/copystat chmod fails with EPERM on vfat/exfat for
  modes it cannot store, so a 0600 file or 0700 folder fails entirely.
  fix: a copy function that copies data + mtime and ignores EPERM/ENOTSUP from chmod/copystat; for bad names keep
  the rest of the folder and say plainly which files could not go and why (like Backup does), no raw list.
  Keep A011's promise: never leave a half folder pretending to be complete (the folder is complete except the
  named files, and the message says so). (The reviewer reproduced it with a fake EINVAL and a fake vfat chmod.)
  commit: 59ac3e6 copying a folder to a USB stick keeps going when one file has a name the stick refuses
  test:   tools/test_os_apps.py
  note:   files the stick cannot store (a name with : ? * ", over 4 GB on FAT, links, permissions) stay behind and are named in plain words; real failures (disk full, unplugged) still remove the half copy (A011).

### U004 [high] Move to a USB stick deletes the originals before the data is really on the stick.
  where: bugos_files_acties.py:163-180 (cross-drive branch of kopieer_een)
  fix: before deleting the source of a cross-drive move, fsync the copied files and their folder (or os.sync() /
  syncfs on the target once per job) and show "Writing to the stick..." while it runs.
  
  ### Medium
  commit: 80979d1 moving files to a USB stick only removes the originals once they are really written to it
  test:   tools/test_os_apps.py

### U005 [medium] "Update now" says "Update done" even when the system update failed.
  where: system_files/usr/bin/bugos-updates:47-48 (nu); bugos-updatecheck:38
  fix: rpm-ostree upgrade || fout=1; still run flatpak update; exit "${fout:-0}". Same for terug (rollback).
  commit: d696aa9 "Update now" no longer says "Update done" when the system update failed
  test:   tools/test_os_system.sh

### U006 [medium] "Update now" and "Back to the previous version" in Settings give no feedback (output to /dev/null); a
  cancelled pkexec on the auto/manual switch leaves the switch flipped.
  where: bugos_settings_systeem.py:96, :99 (start(...)), bugos_base.py:62-65
  fix: run them through QProcess (not on the GUI thread) and show done + "restart" or the error; re-read the
  switch state after pkexec ends. Depends on U005's exit codes.
  commit: fef326b "Update now" and "Back to the previous version" say whether it worked
  commit: fb90817 closing Settings during an update waits for it instead of stopping it
  test:   tools/test_os_settings.py
  note:   also: closing Settings while it updates now waits and then closes (the update runs in Settings since this fix).

### U007 [medium] Developer mode says ON even when setting it up failed.
  where: system_files/usr/bin/bugos-developer:25-37 (every step >/dev/null, unconditional touch "$MARKER")
  fix: check distrobox create/enter and the flatpak install; on failure fout "Are you online?" and no marker.
  commit: aefd270 developer mode no longer says ON when setting it up failed
  test:   tools/test_os_system.sh

### U008 [medium] Command output is parsed in the user's language: Dutch quick-menu Wi-Fi tile always off and cannot turn
  Wi-Fi off; Help says "Wi-Fi is off" in Dutch; Printers empty in German/French/Spanish/Italian.
  where: system_files/usr/bin/bugos-start-data:323, :339 (`nmcli radio wifi` without -t); system_files/usr/bin/bugos-help:73;
  bugos_config.py:39 (draai has no LC_ALL=C), bugos_config_meldingen.py:222 (lees_lpstat); bugos-start-data's draai.
  fix: every helper that runs a command whose output is parsed sets env LC_ALL=C (draai in bugos_config, bugos-start-data,
  bugos-help); use `nmcli -t -f WIFI radio`. 
  commit: 0b82a23 Help no longer says "Wi-Fi is off" on a Dutch (or German...) system
  commit: c3d1b27 Wi-Fi tile works in Dutch and printers show in German, French and other languages
  test:   tools/test_os_settings.py, tools/test_os_system.sh

### U009 [medium] Night light does nothing until the next login.
  where: bugos_config_scherm.py:166 (zet_nachtlicht: kwriteconfig6 without --notify)
  fix: use _c.kde_schrijf("kwinrc","NightColor","Active",...) which adds --notify.
  commit: c487feb Night light switches on and off at once, not after the next login
  test:   tools/test_os_settings.py

### U010 [medium] A non-admin user cannot change their own password (AccountsService SetPassword needs auth_admin).
  where: bugos_config_account.py:216, bugos_settings_account.py:209-216
  fix: for non-admins use PAM `passwd` with old+new password on stdin (no command-line secrets); at least say
  clearly when an administrator is needed.
  commit: d9ebb7f Users who are not an administrator can change their own password
  test:   tools/test_os_settings.py (fake passwd) + a real PAM run in the Fedora 44 image as a non-admin user

### U011 [medium] A Wi-Fi network whose saved password changed can never be reconnected from BugOS.
  where: bugos_settings_netwerk.py:85, bugos_config_netwerk.py:93-99 (draai drops stderr)
  fix: when connecting to a known network fails, ask for the password and use `nmcli --ask connection up id <naam>`
  (password via stdin, never argv) or delete+recreate the profile.
  commit: 21e7a6f A saved Wi-Fi network whose password changed asks for the new password
  test:   tools/test_os_settings.py

### U012 [medium] Backup (and Switch after restore) says "You can unplug it now" while data may still be in the write cache.
  where: system_files/usr/bin/bugos-backup:347 (rsync_maak, klaar); bugos-switch
  fix: rsync --fsync (rsync 3.2.7 has it) or a `sync -f <target>` step before "Done".
  commit: c9139d6 Backup only says "You can unplug it now" after everything is really written to the drive
  test:   tools/test_os_apps.py

### U013 [medium] Store says Firefox and Steam (system RPMs) are not installed and offers a second copy.
  where: system_files/usr/bin/bugos-store:44-50 (geinstalleerd only reads flatpak list), :104
  fix: treat an app as installed when its .desktop exists in the app dirs (or the binary exists); Open then
  launches it with gtk-launch/kioclient instead of flatpak run.
  commit: f1a4614 the Store shows Firefox and Steam as installed when they come with BugOS itself
  test:   tools/test_os_apps.py

### U014 [medium] Backup window freezes after "Make backup" on large folders.
  where: bugos-backup:373 (ruimte_genoeg on the GUI thread, walk at :139-160)
  fix: run ruimte_genoeg in a QThread (like Help's Klusje), show "Checking space...".
  commit: e5d1829 the Backup window no longer freezes while it checks whether everything fits
  test:   tools/test_os_apps.py

### U015 [medium] Closing Backup or Switch during a backup/restore silently aborts it.
  where: bugos-backup:236 (no closeEvent; QProcess(self) at :275); bugos-switch (Overstap)
  fix: closeEvent that asks/waits while the process runs, like Files' sluit_na_klus.
  commit: 227fc7c closing Backup or Switch while it copies asks first instead of silently stopping
  test:   tools/test_os_apps.py

### U016 [medium] Screen readers hear no names: Settings switches (Schuif) and clickable rows (Rij), drive cards and Welcome
  choices (KeuzeKaart).
  where: bugos_widgets.py:402 (KeuzeKaart), :252 (Schuif); bugos_shell.py:56-70 (Rij); bugos_pages.py:48 (SchijfKiezer)
  fix: setAccessibleName/Description from the visible title/text (and update when it changes); rows that are
  clickable get a button role. 
  commit: 6c0b103 screen readers now hear the names of switches, clickable rows, drive cards and Welcome choices
  test:   tools/test_os_apps.py

### U017 [medium] Game mode's FPS counter only appears after logging in again, and stays after game mode is off.
  where: system_files/usr/bin/bugos-game-mode:31-32, :45-46 (MANGOHUD=1 via environment.d only)
  fix: MANGOHUD=1 always in the session env, and switch the overlay on/off in ~/.config/MangoHud/MangoHud.conf
  (no_display), which MangoHud re-reads; or else say clearly "after logging in again".
  commit: f0e7b2e game mode says honestly that the FPS counter needs a new login
  test:   tools/test_os_system.sh
  note:   first the honest message ("after you log in again"); then, as the user asked ("instelbaar maken"),
          a choice in Settings: "FPS counter ready at once" (commit 6d3f8e7 feat(U017)). On: MangoHud always runs
          hidden with BugOS's own MangoHud file and game mode shows/hides the counter at once. Off (default): as before.

### U018 [medium] qdbus6 does not exist on Fedora 44: Help's "Restart now" button does nothing; light mode does not reload KWin.
  where: system_files/usr/bin/bugos-help:177 (start("qdbus6",...)); bugos-light-mode:58, :88
  fix: use qdbus-qt6 or gdbus (bugos-start-data and bugos-panel already fall back to gdbus); one shared way.
  commit: ac793f9 Help's "Restart now" button works again and light mode reloads KWin
  test:   tools/test_os_system.sh

### U019 [medium] Translations to other languages cannot work: template.json is stale (195 of 471 strings) and
  tools/collect-translations.py writes to share/bugos/vertalingen/sjabloon.json, the apps read share/bugos/translations/.
  where: tools/collect-translations.py:22, :33, :58; system_files/usr/share/bugos/translations/template.json
  fix: DOEL = share/bugos/translations, name template.json, regenerate. f-string t() calls (112) cannot be
  translated: note it in docs/TRANSLATING.md (converting them is out of scope unless small).
  
  ### Low
  commit: fda0abf the translation template is complete again and lands where the apps look for it
  test:   tools/test_os_apps.py

### U020 [low] First boot offline keeps the system in "starting" (oneshot with Restart=on-failure, WantedBy=multi-user.target).
  where: system_files/usr/lib/systemd/system/bugos-first-boot.service
  fix: not block boot: e.g. a timer that retries (OnBootSec / OnUnitInactiveSec) with the condition file, or Type=exec.
  commit: 3b3db4e a first start without internet no longer keeps the system "starting"
  test:   tools/test_os_system.sh

### U021 [low] Daily app-update and update-check timers slip by days on laptops that sleep (OnUnitInactiveSec/OnUnitActiveSec).
  where: bugos-update-apps.timer, user bugos-updatecheck.timer
  fix: OnCalendar=daily + Persistent=true, keep RandomizedDelaySec.
  commit: 7e97bfe daily app updates and update checks really happen daily on laptops that sleep
  test:   tools/test_os_system.sh

### U022 [low] BugOS ignores KDE's language choice (LANGUAGE): KDE in Dutch, BugOS in English.
  where: system_files/usr/share/bugos/lib.sh:6; the Python t() language detection (bugos_base.py TAAL)
  fix: look at the first entry of $LANGUAGE first, then LC_ALL, LC_MESSAGES, LANG (bash and Python alike).
  commit: 719588b BugOS follows the language chosen in KDE (LANGUAGE)
  commit: d3290e7 app names in Task Manager follow KDE's language choice too
  commit: dc1e573 the start and quick menu follow KDE's language choice too
  test:   tools/test_os_system.sh, tools/test_os_settings.py, tools/test_edges.py
  note:   lib.sh, bugos_base, bugos-start-data and bugos_desktop all use the same rule now (LANGUAGE first, except for locale C).

### U023 [low] Light mode switches itself on for ordinary 6-8 GB PCs (MemTotal < 6000000 kB).
  where: system_files/usr/bin/bugos-light-mode:32
  fix: lower to ~5000000 kB (or round to whole GB first).
  commit: c8e6288 light mode no longer switches itself on for ordinary 6 GB PCs
  test:   tools/test_os_system.sh

### U024 [low] After "Back to the previous version", the daily check says a new version is ready.
  where: system_files/usr/bin/bugos-updatecheck:15 (deployments[0].booted == false)
  fix: only say "update ready" when deployments[0] is newer (timestamp/version) than the booted one; otherwise neutral.
  commit: 240df20 after going back to the previous version, BugOS no longer says an update is ready
  test:   tools/test_os_system.sh

### U025 [low] Settings opened from the quick menu belongs to plasmashell (P5Support executable engine): it can be killed with
  the applet, and a second click does nothing.
  where: system_files/usr/share/plasma/plasmoids/org.bugos.quickmenu/contents/ui/main.qml:86
  fix: launch through `bugos-start-data --start instelling:<page>` (detaches with setsid), as the start menu does.
  commit: 1bbe8a2 Settings opened from the quick menu opens on every click and stays open
  test:   tools/test_os_settings.py

### U026 [low] A Bluetooth device can only be "forgotten" while connected.
  where: bugos_settings_netwerk.py:160-167
  fix: a "..." menu with Forget on rows that are not connected too.
  commit: 987a088 A Bluetooth device can be forgotten even when it is not connected
  test:   tools/test_os_settings.py

### U027 [low] The live USB mixes languages: Dutch-only GRUB entries, English-only install error dialog (+ MOK/Nvidia dialogs).
  where: iso_live/src/iso.yaml:6,9; iso_live/src/build.sh:234-238 and the dialogs below
  fix: bilingual entries and messages (English first, Dutch after, as elsewhere on the stick).
  commit: 438b639 The live USB speaks English and Dutch everywhere
  test:   tools/test_os_settings.py + shellcheck

### U028 [low] Files says "Drag something here", but dropping does nothing.
  where: bugos_files_venster.py:145 (DragOnly), :245
  fix: accept drops (DragDrop + dropEvent -> Klus copy, or move with Shift) — or, if that grows past S/M, change the text.
  commit: 99b8edc dropping files on a Files window copies them there, as "Drag something here" promised
  test:   tools/test_os_apps.py

### U029 [low] Renaming Foto.JPG to Foto.jpg on a FAT/exFAT stick is refused as "already exists".
  where: bugos_files_bewerken.py:155
  fix: skip the exists check when os.path.samefile(old, new).
  commit: ab656db renaming Foto.JPG to Foto.jpg on a USB stick works instead of saying "already exists"
  test:   tools/test_os_apps.py

### U030 [low] Sizes use a decimal comma in English ("3,2 GB").
  where: bugos_drives.py:24 (mooie_maat)
  fix: comma only for Dutch (TAAL == "nl").
  commit: bf82787 sizes show "3.2 GB" in English (the decimal comma is only for Dutch)
  test:   tools/test_os_apps.py

### U031 [low] Search does nothing when Files is started with a relative folder (bugos-files Documents).
  where: system_files/usr/bin/bugos-files:47 (start_pad without resolve)
  fix: Path(a).expanduser().resolve().
  commit: c36ff6c search works when Files is started with a relative folder (bugos-files Documents)
  test:   tools/test_os_apps.py

## Round 3 (2026-11-08, while the user slept: "B, ga ik doen pas als je in een improve ronde niks meer vind")
A new read-only review of the OS part, now including this round's fixes, found 11 more. All fixed, with a test that
failed first. Tests after: 23 passed, 0 failed (here).

### U032 [medium] Turning "FPS counter ready at once" off showed MangoHud's full overlay in every game until the next login
  commit: 6ba5c9d fix(U032, U035)   test: tools/test_os_system.sh
### U033 [medium] "Back to the previous version" was undone by automatic updates within the hour
  commit: a310cf9 fix(U033, U034, U036)   test: tools/test_os_system.sh, tools/test_os_settings.py
  note: "Back" now turns automatic updates off and says so; Settings shows it and re-reads the switch.
### U034 [low] Pressing "Back" twice went forward again
  commit: a310cf9   test: tools/test_os_system.sh
### U035 [low] With "FPS counter ready at once" on, your own MangoHud.conf layout was ignored
  commit: 6ba5c9d   test: tools/test_os_system.sh
### U036 [low] A switch finishing during "Update now" let Settings close and stop the update (found while fixing U033)
  commit: a310cf9   test: tools/test_os_settings.py
### U037 [medium] Moving a folder to a FAT/exFAT stick could lose files whose names differ only in capitals
  commit: 43ee3e6   test: tools/test_os_apps.py (with a stand-in for a case-insensitive drive; a real FAT stick is for you)
### U038 [medium] After "Finish first", a failure closed the window, so the error was never seen (Backup, Switch, Files)
  commit: 20d5164   test: tools/test_os_apps.py
### U039 [low] Screen readers read the row title instead of a button's own text (a side effect of U016)
  commit: b3c2dab   test: tools/test_os_apps.py
### U040 [low] A folder with subfolders still failed completely on a stick that refuses folder rights
  commit: 526a793   test: tools/test_os_apps.py
### U041 [low] "Update now" said "up to date" while an update waited for a restart; "Back" with no older version said "Are you online?"
  commit: 594010d   test: tools/test_os_system.sh, tools/test_os_settings.py
### U042 [low] The new texts were missing from the translation template
  commit: 59dab47   test: tools/test_edges.py now fails when the template is behind

## Round 4 (2026-11-09)
The same review again, on the code with round 3 in it, found 6 more. All fixed, each with a test that failed first.
Tests after: 23 passed, 0 failed (here).

### U043 [medium] "Back" always failed while an update waited for a restart ("Are you online?")
  commit: d50af57   test: tools/test_os_system.sh   note: the staged update is removed first (rpm-ostree cleanup -p)
### U044 [medium] After going back and restarting, "Back" went forward again to the version you left
  commit: d50af57   test: tools/test_os_system.sh
### U045 [low] A normal "Update now" said "A new BugOS is already waiting"
  commit: d50af57   test: tools/test_os_system.sh
### U046 [medium] Closing Settings during an update hid how it ended (restart, updates off, or an error)
  commit: 835006d   test: tools/test_os_settings.py   note: success: a desktop notification, then close; failure: stays open
### U047 [low] In Files, the error after "close when done" vanished after 12 seconds
  commit: 257e8f1   test: tools/test_os_apps.py
### U048 [medium] A backup to a FAT/exFAT drive lost one of two names that differ only in capitals, and said "safe"
  commit: 5d8da04   test: tools/test_os_apps.py (a stand-in for a case-insensitive drive; real FAT stick: for you)

## Round 5 (2026-11-09)
Found 4, all small and all in code added in rounds 3-4. All fixed with a test that failed first. Tests after: 23 passed.

### U049 [low] After turning the FPS option off, game mode said "FPS counter in games" but left it hidden in that session
  commit: 2d386ba   test: tools/test_os_system.sh
### U050 [low] "Update now" after a not-yet-restarted "Back" said "up to date", yet the restart still went back
  commit: c4427ea   test: tools/test_os_system.sh   note: Update now now undoes such a waiting Back first
### U051 [low] On a FAT/exFAT backup drive, a photo already in the backup could be replaced by its capitals twin
  commit: f6e67d8   test: tools/test_os_apps.py
### U052 [medium] Closing the Store during an install broke the install off without a message
  commit: f73aa93   test: tools/test_os_apps.py

## Round 6 (2026-11-09)
Settings, menus and installer: nothing found. System and apps: 2 small ones, plus 1 from a reviewer's "unsure" list that
was easy to make right. All fixed with a test that failed first. Tests after: 23 passed.

### U053 [low] A backed-up photo could still be replaced by a capitals twin when its folder also got a capitals twin (gap in U051)
  commit: 9a084e2   test: tools/test_os_apps.py
### U054 [low] Game mode off said nothing about the FPS counter staying until a new login, in one rare order of switches
  commit: ac2eadd   test: tools/test_os_system.sh
### U055 [low] "Update now" without internet undid a waiting "Back" before the update failed
  commit: 89ba7ef   test: tools/test_os_system.sh

## Round 7 (2026-11-09)
The reviewers looked on purpose at parts that had been read less (light mode, packages, drives, the Store as a
non-admin, the quick menu sliders, Bluetooth, screen readers). They found 9; all fixed with a test that failed first.
Tests after: 24 passed (here).

### U056 [low] Turning light mode off turned file search (Baloo) on even when you had it off
  commit: e487175   test: tools/test_light_mode.sh (its fake balooctl6 now behaves like the real one)
### U057 [medium] Opening a .rpm/.deb on a Dutch (German, Turkish...) system claimed it was "also in the BugOS Store"
  commit: 64a6e11   test: tools/test_package.sh
### U058 [medium] Erasing, setting up or renaming a USB stick with a name of 12-15 characters failed every time (exFAT allows 11)
  commit: fe3d55f   test: tools/test_files.py
### U059 [medium] A family member who is not an administrator could not install from the Store ("Are you online?")
  commit: 3bbaa0e   test: tools/test_os_apps.py
### U060 [medium] The volume and brightness sliders in the quick menu sent the old value back (a click, a quick drag, arrow keys)
  commit: 707367d   test: tools/test_menus.py (new, also in CI and the image test)
### U061 [low] On a PC without Bluetooth, the quick menu and Settings waited 5 seconds per question
  commit: 3a8d0ac   test: tools/test_start_data.py, tools/test_os_settings.py
### U062 [low] Screen readers did not say which row a slider or a choice button belongs to
  commit: 0bd53c0   test: tools/test_os_apps.py
### U063 [low] The background names in Appearance were always Dutch
  commit: 395486a   test: tools/test_os_settings.py
### U064 [low] Recent files in the start menu did not show the keyboard focus
  commit: b3edfcf   test: tools/test_menus.py

## Round 8 (2026-11-09)
Three reviewers (settings, system scripts, apps) read the parts that are used least, against the real KDE Plasma 6.8
sources. They found 13; all fixed, each with a test that failed first. Tests after: 20 test files passed (here);
the image test of round 7 (build11, Fedora 44 Kinoite) passed with 0 errors.

### U065 [medium] "Big mouse pointer" did nothing, and the switch turned itself off again
  commit: 72e84d4   test: tools/test_os_settings.py (plasma-apply-cursortheme ignores --size when the theme is already set)
### U066 [medium] The "Screen reader" switch did nothing on Plasma 6.8 (Orca is started by the kded module now)
  commit: 72e84d4   test: tools/test_os_settings.py
### U067 [medium] "Big letters" did not make the text bigger in BugOS's own apps, the start menu, quick menu or logout screen
  commit: d9029e0   test: tools/test_os_apps.py
### U068 [low] After changing the time zone, the clock in Settings kept showing the old time
  commit: e2c1142   test: tools/test_os_settings.py
### U069 [low] Searching in English ("night light", "screen reader", "about") found nothing; no "About this computer" in the start menu
  commit: f7a918b   test: tools/test_os_settings.py, tools/test_start_data.py
### U070 [low] Cancelling the password for "Set the time automatically" (or a failing display size) left the switch wrong
  commit: e2c1142   test: tools/test_os_settings.py
### U071 [medium] After game mode, notifications could stay muted for good (an expired "do not disturb" counted all day)
  commit: 43f357d   test: tools/test_os_system.sh
### U072 [low] Settings and the quick menu misread KDE's "do not disturb until" (seconds like 7.913, a time zone at the end)
  commit: 43f357d   test: tools/test_settings.py, tools/test_start_data.py
### U073 [low] "BugOS start menu is on" was shown when there was no KDE start button (or system tray) to replace
  commit: baeae9f   test: tools/test_panel.sh
### U074 [low] Welcome: Next, Back, Next started developer mode, light mode and Steam again; switching off after did nothing
  commit: ddf5d19   test: tools/test_os_apps.py
### U075 [low] A startup app that is off for the whole computer (Hidden=true) could not be turned on, yet it said it would start
  commit: b7b1f39   test: tools/test_task_manager.py
### U076 [low] A file with a very long name (246-255 bytes) could not be deleted at all
  commit: e9e0065   test: tools/test_os_apps.py
### U077 [low] "Free up space > Empty the trash" on This computer jumped to the Trash page, and Back skipped This computer
  commit: 808ddfa   test: tools/test_files.py

## Round 9 (2026-11-09)
Three reviewers: one checked the round-8 fixes for regressions (it found 4: U083-U086), one read Backup, Switch,
Store and Windows programs, one read first boot, updates, the live USB, Help, the logout screen and the build
(against the real Fedora 44 Kinoite base image). 19 found; all fixed, each with a test that failed first.
Tests after: 20 test files passed (here); the image test of round 8 (build12) passed with 0 errors.

### U078 [medium] A stick pulled out during Switch or a Backup restore said "a few files could not be copied, everything else is there"
  commit: 2e1cc8c   test: tools/test_backup.py
### U079 [medium] A full computer (or drive) during restore was reported as "Is the drive still plugged in?"
  commit: 2e1cc8c   test: tools/test_backup.py (a check of free space before restoring is not added; see Skipped)
### U080 [low] The drive card in Backup never showed "already has a backup" or the new free space
  commit: 17df51b   test: tools/test_os_apps.py
### U081 [low] Store: "My apps" only appeared after restarting the Store
  commit: 7648cab   test: tools/test_os_apps.py
### U082 [low] Cancelling a Windows installer said it "does not work on BugOS"
  commit: 3ed4699   test: tools/test_exe.sh
### U083 [medium] (regression of U073) "Quick menu on" without a system tray still did nothing: Plasma joins print() output ("00")
  commit: 0a81f44   test: tools/test_panel.sh (the fake plasmashell now answers like the real one)
### U084 [low] (from U067) The start menu and quick menu only grew with "Big letters" after logging in again
  commit: ef2ac3b   test: tools/test_menus.py
### U085 [low] (from U067) Fixed-size spots clipped text with big letters ("100%", the Processor column, file tiles, Welcome tiles)
  commit: 2f0e2ba   test: tools/test_os_apps.py
### U086 [low] (from U076) The trash in Files showed the name inside the trash, not the real name
  commit: ecdc3e3   test: tools/test_os_apps.py
### U087 [medium] Turning automatic updates off did not stop the daily app updates (Universal Blue's flatpak-system-update.timer)
  commit: 6826a2e   test: tools/test_os_system.sh, tools/test_image.sh
### U088 [medium] Logout screen with two monitors: after "stop" on one screen, the other still shut the PC down
  commit: 9a63354   test: tools/test_logout.py
### U089 [low] App updates also ran over a phone hotspot (metered connection)
  commit: 6826a2e   test: tools/test_os_system.sh
### U090 [low] Help said "Not connected" when NetworkManager had not checked yet ("unknown")
  commit: 513d4fe   test: tools/test_help.py
### U091 [low] Help checked again too soon after "Reconnect" or "Turn Wi-Fi on" and said "Not connected"
  commit: 513d4fe   test: tools/test_help.py
### U092 [low] Help said "Everything is up to date" without looking online
  commit: 513d4fe   test: tools/test_help.py
### U093 [low] On the live USB, Settings offered update buttons that cannot work there
  commit: 970bca6   test: tools/test_os_settings.py
### U094 [medium] Windows side of Switch: one locked or too-big file stopped the whole copy, and BugOS then did not see the stick
  commit: 708e5ff   test: tools/test_os_apps.py (static; the Windows CI parses and runs the script)
### U095 [medium] Windows side of Switch: step 4 could erase the stick that holds your files from step 2
  commit: 708e5ff   test: tools/test_os_apps.py (static)
### U096 [low] desktop.ini and Thumbs.db came along into every folder on BugOS
  commit: 708e5ff   test: tools/test_os_apps.py (static)

## Round 10 (2026-11-09)
Three reviewers: one checked the round-9 fixes (it found the quick menu did not load at all since the English
rename, U099, plus U100-U102), one walked through everyday tasks end to end (Files, Settings, start and quick
menu), one looked at robustness and local security (it was stopped early by the model's safety filter after its
first finding, U097; that part of the review is not finished). 18 found; all fixed with a test that failed first.
Tests after: 20 test files passed (here). The image test could not be built this round: the network proxy of this
environment refused the Fedora mirrors (403), three times; the last image test (round 8) passed with 0 errors.

### U097 [high] Restoring a backup used folder types from a file on the stick unchecked (they went to xdg-user-dir)
  commit: a646bc6   test: tools/test_backup.py
### U098 [medium] Start menu: typing a word and pressing Enter opened the wrong app ("settings" opened KDE's All settings)
  commit: 8639b3e   test: tools/test_menus.py
### U099 [critical] The quick menu on the taskbar did not load at all: main.qml still said "Snelmenu" after the rename
  commit: a8ed793   test: tools/test_menus.py (checks every QML type in the plasmoids exists)
### U100 [low] Help sent people to the Store for updates (it cannot update); it now opens Settings > Updates
  commit: 58c75d2   test: tools/test_help.py
### U101 [low] Universal Blue's per-user app updates (a user timer) still ran after "update myself"
  commit: fbd406e   test: tools/test_os_system.sh, tools/test_image.sh
### U102 [low] (from U080) The drive card took away keyboard focus when only its text changed
  commit: 4f1c34a   test: tools/test_os_apps.py
### U103 [medium] Files: "drive is full" named only the last file and hid how many were missing
  commit: dc333a8   test: tools/test_os_apps.py
### U104 [medium] Files: a long copy could not be stopped, and the only ways out left a hidden half copy for good
  commit: dc333a8   test: tools/test_os_apps.py
### U105 [low] Files: copying FROM a stick said "Writing to the stick… Do not unplug it yet"
  commit: dc333a8   test: tools/test_os_apps.py
### U106 [low] Files: "Done" even when every file got "(2)" after the name because it already existed
  commit: dc333a8   test: tools/test_os_apps.py
### U107 [low] Files: after cut and paste the clipboard was wiped, even if you had copied something else meanwhile
  commit: dc333a8   test: tools/test_os_apps.py
### U108 [low] Files: deleting a big folder on a stick froze the window
  commit: f342c75   test: tools/test_os_apps.py
### U109 [low] Settings: no way to join a hidden Wi-Fi network
  commit: 8a5db9a   test: tools/test_os_settings.py
### U110 [low] Settings: a failed open network asked "Is the password right?"
  commit: 8a5db9a   test: tools/test_os_settings.py
### U111 [low] A PC without Wi-Fi showed a Wi-Fi tile and switch that did nothing
  commit: 8a5db9a   test: tools/test_os_settings.py, tools/test_start_data.py
### U112 [low] Start menu: a new user picture only showed after logging in again
  commit: cec84bb   test: tools/test_start_data.py
### U113 [low] Start menu "Recently opened" missed the files of Store apps (Flatpak)
  commit: cec84bb   test: tools/test_start_data.py
### U114 [low] Settings > Appearance > "Choose your own photo" opened in Home instead of your Pictures folder
  commit: cec84bb   test: tools/test_os_settings.py

## Round 11 (2026-11-09)
Three reviewers: one checked the round-10 fixes (9 found: U115-U123, U117), one walked light/dark, game mode,
light and developer mode, Welcome, the taskbar and Task Manager (9: U124-U132), one checked language and
accessibility (6: U133-U138). 24 found; all fixed, each with a test that failed first. Tests after: 20 test files
passed (here). The image build was blocked again by the network proxy (Fedora mirrors refused, 403).

### U115 [medium] (from U104) Stop did not stop a single big file, and a move then deleted the original anyway
  commit: 2a20ffd   test: tools/test_os_apps.py
### U116 [medium] (from U104) Pressing Stop hid "do not unplug" while the copy was still writing
  commit: 2a20ffd   test: tools/test_os_apps.py
### U117 [medium] (from U101) Per-user apps (VS Code, Discover --user) never got updates; the timer now follows "Automatic updates"
  commit: e097bff   test: tools/test_os_system.sh, tools/test_image.sh
### U118 [low] (from U108) Finishing a delete on a stick threw away your folder, selection and search
  commit: 2a20ffd   test: tools/test_os_apps.py
### U119 [low] (from U108) Delete: asked "Really delete?" then did nothing while busy; mixed selections lost Undo
  commit: 2a20ffd   test: tools/test_os_apps.py
### U120 [low] (from U107) "Paste" stayed after the cut files were pasted in another window
  commit: 2a20ffd   test: tools/test_os_apps.py
### U121 [low] (from U105) Moving between two internal disks said "Do not unplug the stick"
  commit: 2a20ffd   (message only)
### U122 [low] (from U104) Stop after the copy had already finished said "Stopped"; an earlier error was lost
  commit: 2a20ffd   test: tools/test_os_apps.py
### U123 [low] (from U111) The quick menu hid the Wi-Fi tile when nmcli did not answer yet (Settings did not)
  commit: 2a20ffd   test: tools/test_start_data.py
### U124 [medium] Game mode turned a timed "Do not disturb" (1 hour) into "forever"
  commit: 8400b58   test: tools/test_game_mode.sh
### U125 [medium] Task Manager listed apps under whoever started them (Settings as "part of BugOS", the Store as "Welcome")
  commit: 34c6ff6   test: tools/test_task_manager.py
### U126 [low] Settings > Updates and more: switches were fire-and-forget and never re-read (wrong after a failure)
  commit: 493d781 (+ flock in 8400b58)   test: tools/test_os_settings.py
### U127 [low] Turning game mode or light mode off while already off changed your own settings
  commit: 8400b58   test: tools/test_game_mode.sh, tools/test_light_mode.sh
### U128 [low] The quick menu's Dark tile flipped back after a tap (bugos-theme was still running)
  commit: b2ee102   test: tools/test_start_data.py
### U129 [low] Welcome: the update choice counted as done even when the password was cancelled
  commit: b2ee102   test: tools/test_os_apps.py
### U130 [low] Welcome: "I'm going to play games" did nothing with a Flatpak Steam, yet said it was set up
  commit: b2ee102   test: tools/test_os_apps.py
### U131 [low] Choosing a BugOS background stopped it following light/dark, with no way back
  commit: 7b92469   test: tools/test_os_settings.py
### U132 [low] Light/dark did not reach installed Windows programs; a Welcome tip named a page that does not exist
  commit: b954990, b2ee102   test: tools/test_os_system.sh
### U133 [medium] Settings pages were cut off on the right with no way to scroll; the window could be taller than the screen
  commit: 88a1f9d   test: tools/test_os_settings.py
### U134 [medium] No visible keyboard focus on round buttons, outlined buttons and sliders
  commit: b302e17   test: tools/test_os_apps.py
### U135 [low] Weak focus in the start and quick menu; Enter did nothing on the quick menu's gear
  commit: b302e17   test: tools/test_menus.py
### U136 [low] The Settings sidebar names were cut off with big letters
  commit: 88a1f9d   test: tools/test_os_settings.py
### U137 [low] Small grey, green and orange text was below 4.5:1 contrast on the light theme
  commit: 28ff16a   test: tools/test_os_apps.py
### U138 [low] Language leftovers: the Help report title, "idle sent", Uitloggen/Afmelden and Herstarten/Opnieuw opstarten
  commit: 04a2513   test: tools/test_os_apps.py

## Round 12 (2026-11-09)
Three reviewers: the round-11 fixes (7 found: U143-U148), the Settings pages in depth (11: U153-U163), and the
taskbar, start menu, Backup/Switch windows and drives (8: U139-U142, U149-U152). 26 found; 23 fixed, each with a
test that failed first; 3 not done (see Skipped). Tests after: 20 test files passed (here).

### U139 [high] Backup and Switch never saw a USB stick that was just plugged in (KDE does not mount it by itself)
  commit: 20a239f   test: tools/test_files.py
### U140 [medium] Backup and Switch said "Done! Your files are back" when nothing was restored (stick pulled during the question)
  commit: 4c5e854   test: tools/test_os_apps.py
### U141 [medium] A failed rename or repair left the drive closed; a failed repair advised erasing a healthy drive
  commit: 3de8662   test: tools/test_files.py
### U142 [medium] Laptops with eMMC showed two fake "SD card (4.2 MB)" drives; internal eMMC was called an SD card
  commit: 20a239f   test: tools/test_files.py
### U143 [medium] (from U124) Game mode off turned "do not disturb" back on after you had switched it off yourself
  commit: 71cb369   test: tools/test_game_mode.sh
### U144 [low] (from U115) Copying a FIFO hung forever; Stop inside a folder still waited for the current big file
  commit: 71cb369   test: tools/test_os_apps.py
### U145 [low] (from U116) "Stopping… do not unplug the stick" also for copies between internal disks
  commit: 71cb369   (message only)
### U146 [low] (from U125) A program name systemd does not allow made the launch fail silently
  commit: 71cb369   test: tools/test_task_manager.py
### U148 [low] (from U132) Light/dark could pop up Wine's "updating" window after a Wine update; parallel Wine runs
  commit: 71cb369   test: tools/test_os_system.sh (runs where wine.inf exists, e.g. the image test)
### U149 [low] Start menu: the highlighted row was not the one Enter opened (Tab through All apps or search results)
  commit: a976129   test: tools/test_menus.py
### U150 [low] Switch used Windows folder names in Dutch sentences; a partial restore blamed stick problems
  commit: d2eeaef   test: tools/test_os_apps.py
### U151 [low] Erasing an SD card named it "USB stick"
  commit: d2eeaef
### U152 [low] The Backup progress bar jumped back to 0 for every folder
  commit: d2eeaef   test: tools/test_os_apps.py
### U153 [medium] "Tap to click" never appeared on a real touchpad (KWin has no supportsTapToClick)
  commit: e3cb465   test: tools/test_settings.py
### U155 [low] Power: "on battery" while plugged in at a charge limit; batteries not named BAT* were not seen
  commit: 29eb356   test: tools/test_os_settings.py
### U156 [low] A failed power-profile change left the wrong card highlighted
  commit: 29eb356   test: tools/test_os_settings.py
### U157 [low] A PC without Bluetooth showed a Bluetooth tile and switch that waited 8 s and did nothing
  commit: 29eb356   test: tools/test_os_settings.py
### U158 [low] "Clear the queue" silently did nothing for a non-administrator (cancel -a); it counted other users' jobs
  commit: bb72666   test: tools/test_os_settings.py
### U159 [low] Skanpage installed from the Store (Flatpak) was not found: "No scanning program" and a loop to the Store
  commit: bb72666   test: tools/test_os_settings.py
### U160 [low] The touchpad text for natural scrolling described the switch backwards
  commit: bb72666
### U162 [low] Searching "microphone" led to the Sound page, which has nothing for microphones
  commit: bb72666
### U163 [low] (open) The Default programs menu and "Test notification" do short work on the window's thread (see Skipped)

## Round 13 (2026-11-09)
Three reviewers: the round-12 fixes (6 found: U164-U169), Files previews, the Store and Help (8: U170-U177), and a
new user's first day (5: U178-U182). 19 found; all fixed, each with a test that failed first (two text-only).
Tests after: 20 test files passed (here).

### U164 [medium] (from U139) Backup/Switch mounted again a drive you had just closed ("Safely remove"), every 3 s
  commit: cdb6f0e   test: tools/test_files.py
### U165 [medium] (from U157) Bluetooth switched off by airplane mode or an Fn key could not be turned back on
  commit: cdb6f0e   test: tools/test_os_settings.py
### U166 [low] (from U162) Searching "microphone" found nothing; the Sound page now says where to set it
  commit: cdb6f0e
### U167 [low] (from U152) The Backup bar sat at 85% while writing to the drive
  commit: cdb6f0e
### U168 [low] (from U144) Folder copies lost the kernel's fast copy (copy_file_range, reflink on btrfs)
  commit: cdb6f0e   test: tools/test_os_apps.py (copy tests)
### U169 [low] (from U148) A quick light-dark-light could leave the Windows programs dark; a stuck Wine held the lock
  commit: cdb6f0e   test: tools/test_os_system.sh
### U170 [medium] Files kept 512 px photo previews without a limit: a big photo folder took gigabytes of memory
  commit: 906facd   test: tools/test_os_apps.py
### U171 [medium] Files: leaving a folder did not cancel its queued previews; the next folder waited
  commit: 906facd   test: tools/test_os_apps.py
### U172 [low] Files: PDFs and videos never got a preview of their own
  commit: 906facd   test: tools/test_os_apps.py (PDF; video where ffmpegthumbnailer exists)
### U173 [medium] Store/Windows programs: WhatsApp pointed to an app Flathub has delisted; now ZapZap
  commit: 63d6523   test: tools/test_os_apps.py
### U174 [low] Help on a PC without Wi-Fi said "Choose your Wi-Fi" instead of "Is the cable plugged in?"
  commit: 63d6523   test: tools/test_help.py
### U175 [low] The calculator was called "Rekenmachine" in the English Store
  commit: 63d6523   test: tools/test_os_apps.py
### U176 [low] The real installer names of Telegram, Epic and GOG Galaxy were not recognised
  commit: 63d6523   test: tools/test_os_apps.py
### U177 [low] Help checked the printing service again before the password was typed
  commit: 63d6523   test: tools/test_os_apps.py
### U178 [medium] "I choose when" users often got no update notification (checked before Plasma and Wi-Fi), or in the old language
  commit: ffa22c6   test: tools/test_os_system.sh
### U179 [low] Welcome showed "older computer" off while light mode had just turned itself on
  commit: 7a0df2f   test: tools/test_os_apps.py
### U180 [low] First boot downloaded LibreOffice, VLC (and Steam) over a phone hotspot
  commit: 7a0df2f   test: tools/test_os_system.sh
### U181 [low] Welcome said "Steam is ready" when it was not (yet)
  commit: 7a0df2f   test: tools/test_os_apps.py
### U182 [low] Finishing Welcome while the password window was open threw the update choice away
  commit: 7a0df2f

## Round 14 (2026-11-09)
Three reviewers: the round-13 fixes (9 found), a top-to-bottom sweep of every shell script (4), and of the shared
Python building blocks (4). Two were found twice. 15 fixed, each with a test that failed first; 1 left for you
(U196). Tests after: 20 test files passed (here).

### U183 [medium] (from U164) A stick pulled out and plugged in again was never opened while Backup/Switch stayed open
  commit: 82098cc   test: tools/test_files.py
### U184 [low] A switch set back within its 170 ms slide stayed drawn in the old position
  commit: 82098cc   test: tools/test_os_apps.py
### U185 [low] Backup showed "0 GB free" on a small stick with 450 MB free, and GiB instead of GB like Files
  commit: 82098cc   test: tools/test_os_apps.py
### U186 [low] Task Manager > Startup: a failed change kept the switch in the new position
  commit: 82098cc   test: tools/test_os_apps.py
### U187 [high] (from U178) The update check's 20-minute limit also covered "Update now": a slow update was cut off and asked again
  commit: d1d1792   test: tools/test_os_system.sh
### U188 [low] (from U165) A Bluetooth rfkill entry without a real adapter brought back a dead Bluetooth tile
  commit: e9d4f30   test: tools/test_os_settings.py
### U189 [low] (from U179) In Welcome a switch that was already on could be turned off, but nothing happened
  commit: e9d4f30   test: tools/test_os_apps.py
### U190 [low] (from U176) "tsetup" matched ChatGPTSetup.exe and MinecraftSetup.exe as Telegram
  commit: e9d4f30   test: tools/test_exe.sh
### U191 [low] (from U177) Closing Help with the password prompt open froze for 25 s and could abort
  commit: e9d4f30
### U192 [low] (from U178) The update check retried every 30 minutes forever when only the registry failed
  commit: d1d1792   test: tools/test_os_system.sh
### U193 [low] (from U182) Next and Back stayed clickable while Welcome waited for the password
  commit: e9d4f30
### U194 [low] Cancelling the password after "Update now" in the notification said "The update did not work"
  commit: d1d1792   test: tools/test_os_system.sh
### U195 [low] A .rpm/.deb without a start-menu entry still said "is now in your start menu"
  commit: e9d4f30   test: tools/test_package.sh
### U197 [low] (from U172) PDF and video previews were made again on every visit; stale previews were not detected
  commit: ecf799a   test: tools/test_os_apps.py
### U196 [low] (open, see For you) Switching to signed updates (bugos-ondertekend) removes the previous version

## Round 15 (2026-11-09)
Three reviewers: the round-14 fixes (5 found: U198-U202), a top-to-bottom sweep of every QML file (4: U203-U206),
and of the app programs themselves (7: U207-U213). 16 found; all fixed, each with a test that failed first.
Tests after: 20 test files passed (here).

### U198 [high] (from U195) Installing a .rpm/.deb said "Done" when the install had failed
  commit: d485274   test: tools/test_package.sh
### U199 [medium] (from U191) Closing Help during a check left it running invisibly until logout
  commit: d485274   test: tools/test_os_apps.py (static)
### U200 [medium] (from U183) A stick you closed yourself was mounted again (size differs open/closed; an empty lsblk wiped the list)
  commit: d485274   test: tools/test_files.py
### U201 [low] (from U197) Saved previews were readable by other users; writers shared one temporary file name
  commit: d485274   test: tools/test_os_apps.py
### U202 [low] (from U187) The update check could hang forever on skopeo
  commit: d485274   test: tools/test_os_apps.py (static)
### U203 [medium] Clicking Start (or the quick-menu button) again closed the menu and opened it straight away
  commit: b98d9c6   test: tools/test_menus.py
### U204 [low] After "All apps" or "Back" with the keyboard, the focus was on a hidden button
  commit: b98d9c6   test: tools/test_menus.py
### U205 [low] Typing in the start menu only searched when the search field had focus
  commit: b98d9c6   test: tools/test_menus.py
### U206 [low] The quick menu said "Wifi" in English
  commit: b98d9c6   test: tools/test_menus.py
### U207 [medium] Closing Files during "Set up", "Erase", "Rename" or "Repair" of a drive stopped the job halfway
  commit: 92ecd28   test: tools/test_files.py
### U208 [low] A second start of an app opened a second window (two "Update now", two installs at once)
  commit: c5dc16b   test: tools/test_os_apps.py
### U209 [low] (from U175) The Store still said "Rekenmachine" in English while installing and searching
  commit: 6e099b4   test: tools/test_os_apps.py
### U210 [low] Names from outside (Wi-Fi networks, files) could show as HTML; "&" in a folder name became a shortcut
  commit: 6e099b4   test: tools/test_os_apps.py
### U211 [low] Backup stayed on "Checking whether everything fits" forever when its folder could not be made
  commit: 6e099b4   test: tools/test_backup.py
### U212 [low] Closing Welcome (X) or Settings with the password prompt open threw the update choice away
  commit: 6e099b4   test: tools/test_os_apps.py
### U213 [low] Welcome said "Language: Nederlands" on a system with LANG=C (English)
  commit: 6e099b4

## Round 16 (2026-11-09)
Two reviewers: the round-15 fixes (7 found plus one minor: U214, U217-U223; U215/U216 not used), and a fresh trace of a user's first month
(open a photo or PDF, plug in a phone, print, pair headphones, install an app, make a backup) (4 found plus 3 unsure,
U224-U230). 15 found; 14 fixed, each with a test that failed first; U230 skipped (below). Tests after: 20 test files passed (here).

### U214 [medium] (from U200) A stick pulled out and put back was never mounted again on a PC with only the BugOS disk
  commit: 5284e79   test: tools/test_files.py
### U217 [medium] (from U208) A second start un-maximized a maximized window
  commit: f836c1e   test: tools/test_os_apps.py
### U218 [medium] (from U208) On Wayland the open window probably did not come forward (no activation token)
  commit: f836c1e   test: tools/test_os_apps.py (the token is passed on; check on a real Plasma 6.8 PC)
### U219 [low, security] (from U208) Another account could take the app's address in the shared /tmp
  commit: f836c1e   test: tools/test_os_apps.py
### U220 [low] (from U208) A hung or closing first window swallowed a new start
  commit: f836c1e   test: tools/test_os_apps.py
### U221 [medium] (from U208, U199) A window you opened again closed by itself when its job finished
  commit: f836c1e   test: tools/test_os_apps.py
### U222 [low] (from U208) The Store and Task Manager ignored what a second start asked for (appstream://, --zoek, --prestaties)
  commit: f836c1e   test: tools/test_os_apps.py
### U223 [low] (from U205) Ctrl+A in the start menu typed into the search field
  commit: 99b88dc   test: tools/test_menus.py
### U224 [high] No program opened photos or PDFs after installing; the Store had no photo viewer
  commit: f1110e0   test: tools/test_os_system.sh
### U225 [low] A phone or camera (MTP/PTP) could not open in Files (no kio-fuse)
  commit: eae2492   test: tools/test_os_system.sh (check with a phone on a real PC)
### U226 [medium] Backup offered a disk inside the computer as backup place (and could preselect it)
  commit: 9438d74   test: tools/test_backup.py
### U227 [low] Settings stayed stale after pairing headphones, adding a printer or installing an app
  commit: 389a370   test: tools/test_os_settings.py
### U228 [low] The backup folder changed name on another network (DHCP host name), so a full new copy began
  commit: c867332   test: tools/test_backup.py
### U229 [low] Choosing English in Europe gave US dates and Letter paper (now en_IE, or your English region)
  commit: c59ed71   test: tools/test_settings.py

## Round 17 (2026-11-09)
Two reviewers: the round-16 fixes (6 found, 2 unsure: U231-U234, U239, U240), and a fresh trace of the system
lifecycle (build, install, updates, rollback, signed switch, a second user, laptop life, full disk, wrong clock): no
high or medium defect, 3 low plus 1 text item (U235-U238) and 2 unsure. 12 found; 8 fixed, each with a test that
failed first; 4 skipped or for you (below). Tests after: 20 test files passed (here).

### U231 [medium] (from U226) An old backup on a disk inside the computer could no longer be restored
  commit: 34ab626   test: tools/test_backup.py
### U232 [low] (from U229) English in a non-euro country (Poland, Turkey…) gave the euro; now that country's paper, sizes and money
  commit: 6c9acc6   test: tools/test_settings.py
### U233 [low] (from U221) Store, Backup and Switch still promised to close by themselves after you opened them again
  commit: d86fc49   test: tools/test_os_apps.py (static)
### U234 [low] (from U221) Backup: closed while counting and opened again gave a false "not enough space"
  commit: d86fc49   test: tools/test_os_apps.py
### U235 [low] On battery, Settings showed the mains times for screen off and sleep (KDE uses shorter ones)
  commit: 6614cd3   test: tools/test_os_settings.py
### U236 [low] The switch to signed updates kept the boot "starting" while downloading, also over a hotspot
  commit: b30b1f8   test: tools/test_os_system.sh
### U237 [low] "1.5 GB" with a point in Dutch (Help: disk almost full; Backup: not enough space)
  commit: 2896c3f   test: tools/test_help.py, tools/test_os_apps.py
### U238 [low] "Updates yourself via the BugOS Store" (the Store cannot update; U100)
  commit: 2896c3f

## Round 18 (2026-11-09)
Two reviewers: the round-17 fixes (2 found, 1 incomplete, 4 unsure: U241-U243), and the robustness/privacy pass
that stopped early in round 10 (polkit, root helpers, files BugOS creates, privacy, outside input, CI): nothing
critical, high or medium; 6 low plus 4 unsure (U244-U251, U252-U254). 14 found; 11 fixed, each with a test that
failed first; 3 skipped or for you (below). Tests after: 20 test files passed (here).

### U241 [medium] (from U221/U233) Backup/Switch: "Stop now", then opened again: stuck on "Stopping…", and the next job stopped after one folder
  commit: 407fa9e   test: tools/test_os_apps.py
### U242 [low] (from U232) English outside the euro countries got US dates (now en_IE dates with your own paper and money)
  commit: a061f5e   test: tools/test_settings.py
### U243 [low] (from U235) On battery the sleep choice showed 15 min (KDE: 10 min); a charger with a charge limit counted as battery
  commit: a061f5e   test: tools/test_os_settings.py
### U244 [low, privacy] A deleted file left its preview (with its name) in ~/.cache/thumbnails
  commit: 796e30a   test: tools/test_files.py
### U245 [low] Installing a .rpm/.deb promised a "safe box"; the box protects BugOS, not your files
  commit: 969c3fa   test: tools/test_package.sh
### U246 [low, hardening] pkexec started a program found on the user's PATH (Help: systemctl; bugos-updates "$0")
  commit: 969c3fa   test: tools/test_os_apps.py
### U247 [low] With umask 077 the update choice and auto-login file were unreadable; auto-login accepted root
  commit: 969c3fa, e144f6a   test: tools/test_os_system.sh, tools/test_os_settings.py
### U248 [low, CI] build.yml had no default read-only permissions
  commit: 969c3fa   test: tools/test_edges.py
### U249 [low, CI] screenshots.yml and windows-switch.yml put inputs/ref names straight into commands
  commit: 969c3fa   test: tools/test_edges.py
### U250 [low, privacy] Fedora's weekly countme ping was still on ("BugOS collects nothing")
  commit: 969c3fa   test: tools/test_os_system.sh, tools/test_image.sh (in the image)
### U251 [low] A file name like "<h1>…" could format or hide the text of the .exe/.rpm question (kdialog)
  commit: 969c3fa   test: tools/test_exe.sh

## Round 19 (2026-11-09)
Two reviewers: the round-18 fixes (2 found plus 5 unsure: U255-U258), and a fresh sweep of look and feel, gaming and
developer tools (1 medium, 4 low, 3 unsure: U259-U264). 10 fixed, each with a test that failed first; 3 skipped
(below). Tests after: 20 test files passed (here).

### U255 [low, privacy] (from U244) Emptying the trash left previews made of the file inside the trash
  commit: 0e0b3d1   test: tools/test_files.py
### U256 [low] (from U244) Emptying a big trash froze the window much longer (thousands of needless deletes)
  commit: 0e0b3d1   test: tools/test_files.py
### U257 [low] (from U242) English in the US or Canada gave en_IE (now en_US / en_CA)
  commit: 627f506   test: tools/test_settings.py
### U258 [low] (from U247) Auto-login accepted uid 65534 (nobody) and system users above UID_MAX
  commit: 627f506   test: tools/test_os_system.sh
### U259 [medium] Swapping a taskbar widget (start menu, quick menu, taskbar space) put it at the far right end
  commit: 82a3472   test: tools/test_panel.sh (simulated panel, tools/panel-sim.js; check on a real Plasma 6.8 PC)
### U260 [low] Game mode from the quick menu was killed after 5 s, leaving "Full power" half on
  commit: 80b63ac   test: tools/test_start_data.py
### U261 [low] Light mode off did not bring animations back until the next login (no --notify)
  commit: feead40   test: tools/test_light_mode.sh
### U262 [low] Developer mode could run twice at once (Welcome and Settings): "did not work"
  commit: feead40   test: tools/test_os_system.sh
### U263 [low] The dev box used fedora-toolbox:latest (now the same Fedora version as BugOS)
  commit: feead40   test: tools/test_os_system.sh
### U264 [low] No FPS counter in games from the Store (Flatpak): MangoHud for Flatpak was not installed
  commit: 5fbec4e   test: tools/test_os_system.sh

## Round 20 (2026-11-09)
Two reviewers: the round-19 fixes (2 found plus 4 unsure: U269, U270), and a fresh sweep of languages and
accessibility (6 found plus 3 unsure: U268, U271-U276). 8 fixed, each with a test that failed first; U276 documented;
3 skipped (below). Tests after: 20 test files passed (here).

### U268 [low-medium] Search missed the Turkish İ and accented names (also NFD names from a Mac): start menu, Files, Store, Settings
  commit: 1e6c9f1   test: tools/test_start_data.py, tools/test_menus.py, tools/test_os_apps.py
### U269 [medium] (from U256) Emptying a trash with many items read the whole thumbnail cache once per item (10 s instead of 0.06 s)
  commit: cc40c0a   test: tools/test_files.py
### U270 [medium] (from U262) The developer-mode lock was passed on to the running dev box, so "off" could wait forever
  commit: 6776304   test: tools/test_os_system.sh
### U271 [low-medium] No visible keyboard focus on choice buttons, wallpapers, the Files path and the storage legend
  commit: 75206dd   test: tools/test_os_apps.py
### U272 [low-medium] The Files path bar squeezed names until unreadable ("ocumen"); now elided with the full name as tip
  commit: dab1e23   test: tools/test_os_apps.py
### U273 [low] Contrast below 4.5:1 on dark main buttons, selected sidebar items, dark placeholders; the off-switch track was 1.5:1
  commit: 66656db   test: tools/test_os_apps.py. Also regenerated the design files: icons, Kvantum and colour schemes
  still had the colours from before U137, so the CI step "Ontwerptaal is bijgewerkt" would have failed.
### U274 [low] Screen readers heard the drive rows in Files > This computer as "panel", not as buttons
  commit: 63f2b9c   test: tools/test_os_apps.py
### U275 [low] An Arabic Qt translation flipped the (Dutch/English) BugOS windows to right-to-left
  commit: 2fbf06e   test: tools/test_os_apps.py
### U276 [low, latent] The menus, taskbar and .desktop names cannot use the translation dictionaries yet
  commit: e5c547c   documented in docs/TRANSLATING.md (making them translatable is M)

## Round 21 (2026-11-09)
Two reviewers: the round-20 fixes (4 found plus 5 unsure: U280-U283), and a fresh sweep of the live USB/installer,
the Windows switch tool, and Help/Task Manager (8 found plus 8 unsure: U284-U291). 12 fixed, each with a test that
failed first; the rest skipped or for you (below). Tests after: 20 test files passed (here). The Windows tool is
checked by reading the script only (no PowerShell here); the Windows CI runs it.

### U280 [medium-low] (from U268) Start menu: ß, Greek ς and kana no longer matched (QML and Python built the key differently)
  commit: dcc5715   test: tools/test_menus.py, tools/test_start_data.py
### U281 [low] (from U272) An elided crumb gave screen readers the shortened name; "…" had no name
  commit: fc2f403   test: tools/test_os_apps.py
### U282 [low] (from U273) The "busy" banner (Backup) kept accent on accent_zacht (3.9:1)
  commit: fc2f403   test: tools/test_os_apps.py
### U283 [low] (from U273) The Plasma theme's off-switch kept the old 1.5:1 track
  commit: fc2f403   test: tools/test_os_apps.py (switch.svg regenerated)
### U284 [medium] Windows step 2 offered a D: inside the laptop as backup place, and selected it first
  commit: 184b3cd   test: tools/test_windows_start.sh (script check; try once on a real Windows PC)
### U285 [low] After "Make space" it said to choose "Automatic"; the installer says "Share disk with other operating systems"
  commit: 184b3cd   test: tools/test_windows_start.sh
### U286 [low-medium] "Click again" after a partial copy said "not enough space" (what was already copied did not count)
  commit: 184b3cd   test: tools/test_windows_start.sh
### U287 [low] A failed ISO download left a broken file, a raw .NET error, and blocked a retry on a tight disk
  commit: 184b3cd   test: tools/test_windows_start.sh
### U288 [low] A stick that got full during step 2 was explained as "files open in a program"
  commit: 184b3cd   test: tools/test_windows_start.sh
### U289 [medium] Nvidia + Secure Boot: the MOK screen timed out after 10 s, and the text never said "press a key"
  commit: fea0ea4, 953bf17   test: tools/test_os_settings.py (the U027 test caught double quotes that broke the yad command)
### U290 [low] Help said "No Bluetooth found" when Bluetooth was off by airplane mode; the repair did not wait for the adapter
  commit: 05eb8c2   test: tools/test_help.py
### U291 [low] Help's "Show what takes up space" opened Dolphin instead of BugOS Files
  commit: 05eb8c2   test: tools/test_help.py

## Round 22 (2026-11-09)
Two reviewers: the round-21 fixes (3 found plus 3 unsure: U296-U299), and a fresh sweep of upgrading a machine that
has been in use for months, including /etc merges and rollback (4 found plus 3 unsure: U300-U303). 9 fixed (including U239
from the Skipped list), each with a test that failed first. Tests after: 20 test files passed (here).

Note: `main` (the tree before the English rename) was built and pushed as an image on 2026-11-03, so "main image
→ this branch" is a real upgrade path (U302). Earlier rounds said no image had been released; that was not right.

### U296 [medium] (from U284) Fast USB SSDs (UAS, they report SCSI) disappeared from the Windows tool's step 2
  commit: b64e260   test: tools/test_windows_start.sh
### U297 [low, latent] (from U290) Help imported bugos_config_netwerk directly, leaving bugos_config half loaded
  commit: b64e260   test: tools/test_help.py
### U298 [low] (from U287) Every download error was explained as "the connection dropped"; now with the real reason
  commit: b64e260   test: tools/test_windows_start.sh
### U299 [low] The red error text on its pink background was 4.36:1 (light)
  commit: b64e260   test: tools/test_os_apps.py (design files regenerated)
### U300 [medium] "Back to the previous version" wrote "update myself" into the /etc of the version you left; the older
version still said "automatic" and staged the newer one again within an hour (U033 one boot later)
  commit: b02c7a8   test: tools/test_os_system.sh. The choice now also lives in /var/lib/bugos
  (shared by all versions), and every update service (system, apps, per-user apps) checks it with ExecCondition.
### U301 [low-medium] After a renamed timer, "update myself" quietly turned app updates back on (the /etc merge adds the new symlink)
  commit: same as U300   test: tools/test_os_system.sh
### U302 [medium, machines on a pre-rename image] Renamed ids were not migrated: broken quick-menu widget, pinned taskbar
apps gone, dark mode showing as light (BugOSDonker), FPS counter stuck on
  commit: b87b83f   test: tools/test_panel.sh (simulated panel), tools/test_os_system.sh
### U239 [low] (was skipped in round 17) PCs whose first boot had already finished never got Gwenview and Okular
  commit: 4c764a2   test: tools/test_os_system.sh (main's image exists, so such PCs can exist)
### U303 [low] After switching to signed updates and going back, the PC stayed on unverified updates for good
  commit: 9b932d6   test: tools/test_signed.sh

## Skipped
- U147: a mask left by the round-10 image is not migrated; that image was never released (nothing was merged).
- U154: two screens with different sizes get one size; a per-screen choice is a bigger change (M).
- U161: a printer queue stopped by CUPS has no "Start again" button (needs admin rights); the advanced page can.
- U163: two small blocking calls in Settings (usually well under a second).
- U230 (round 16): "Show in folder" in Firefox and notifications opens Dolphin, not Files. Files would have to
  provide org.freedesktop.FileManager1 on D-Bus next to Dolphin's own service (M; needs a real Plasma session to test).
- U240 (round 17, unsure): the daily `flatpak uninstall --unused` as root may remove a runtime that only another
  account's own (--user) app needs. BugOS installs apps system-wide; only Discover --user installs are exposed.
- U252 (round 18, unsure): Language change removes paper/money/measurement choices you made yourself in KDE's
  Region page (BugOS cannot tell them apart from the ones it set). Low.
- U253 (round 18, unsure): `flatpak override --user` lets every Flatpak app read ~/.config/kdeglobals (for the BugOS
  colours); that file can hold recent file-dialog places. Many KDE apps on Flathub already have this access.
- U265 (round 19, unsure): VS Code is the Flatpak, so its built-in terminal does not see the "dev" box; a
  terminal profile with `flatpak-spawn --host distrobox enter dev` would help beginners (M, needs a real PC).
- U266 (round 19, unsure): with "I choose when" for updates, bugos-flatpak-style only runs at first boot, so a new
  KDE runtime branch falls back to the stock style (cosmetic).
- U267 (round 19, unsure): with "FPS counter ready at once", MANGOHUD_CONFIGFILE points into ~/.config/bugos, which
  the Steam Flatpak cannot read; MangoHud may then show its default overlay.
- U277 (round 20, unsure): the start-menu date uses KDE's language (a German user sees "Montag 9 November" next to
  "Good morning"); arguably by design.
- U278 (round 20, unsure): Task Manager, its Startup list and the Notifications app list sort by code point (Ä, Ş and
  Cyrillic names in odd places). Cosmetic.
- U279 (round 20, unsure): game mode from the quick menu can briefly flip back to "off" while the script still runs
  (the same accepted pattern as dark mode, U128).
- U292 (round 21, unsure): the Windows tool's Get-PartitionSupportedSize / Get-Disk may refuse a non-elevated user;
  try steps 3 and 4 once from the .bat as a normal user (see For you).
- U293 (round 21, unsure): the Windows tool counts sizes on the window's thread (big photo libraries freeze it for a
  while), and robocopy downloads OneDrive cloud-only files first.
- U294 (round 21, unsure): the kickstart sets `keyboard us`; check on a real install that AZERTY/QWERTZ users can
  pick their layout in the live installer.
- U295 (round 21, unsure): Task Manager runs nvidia-smi on every refresh while open (may keep an Optimus GPU awake).
- U304 (round 22, confirmed in round 23): an older version you roll back to does not have the U300 conditions. That
  includes the released `main` image: on a PC upgraded from main, "back" goes to main, whose own /etc and timers still
  say "automatic", so it stages the new version again after about an hour. Only fixable by writing into the rollback
  deployment's own /etc (needs a writable /sysroot; M, test on a real PC), or by not going back to main.
- U305 (round 22, unsure): whether Plasma's scripting `widget.type` still reports "org.bugos.snelmenu" for a widget
  whose plugin is missing (U302 relies on it); check once on a real PC that had the old image.
- U306 (round 22, unsure): light mode switched on automatically by a pre-rename image below 6,000,000 kB is not
  re-checked against U023's newer threshold.
- U079 (part): a free-space check before restoring (Switch, Backup). The full disk is now named clearly and
  a retry skips what is already there; counting first would also have to honour --ignore-existing/--update.

## For you
- The user said (2026-11-08): real-PC tests (below) come once an improve round finds nothing more; the GitHub
  settings (signing key, default branch, private reporting) and the merge are theirs; no merge before the real-PC test.
- U010: test changing your password once as a family member who is not an administrator, on a real BugOS PC
  (tested here with real PAM in the Fedora 44 image, not on hardware).
- U002, U004, U012: test once on a real PC: log in without a password after a restart; move files to a USB stick and
  check them on another computer.
- U065, U066, U067: on a real PC with Plasma 6.8, turn on Big mouse pointer, Screen reader (Orca speaks) and Big
  letters, and look at Settings, Files and the start menu (checked here against the KDE sources, not on a screen).
- U088, U094, U095: on a real PC, try the logout screen with two monitors, and the Windows Switch tool (an open
  Outlook file in Documents; one USB stick for both step 2 and step 4).
- U099: the quick menu did not load on the taskbar since 5 Nov; check once on a real PC that it now opens.
- Round 10's robustness/security review was stopped early by the model's safety filter; if you want that part
  finished, it needs a new session or another model (it only got as far as U097).
- U125: on a real PC, open Settings from the quick menu and check Task Manager lists it as "Settings" (closable).
- U133-U137: try Settings with only the keyboard (Tab, Enter, Escape) and with "Big letters" on.
- U218 (round 17): BugOS's own start/quick menus launch through Plasma's "executable" engine, which passes no
  activation token. On a real Plasma 6.8 PC, check that opening Settings from the quick menu while it is already
  open brings it to the front (not only a blinking taskbar button). If not, the menus must launch via Plasma (M).
- U254 (round 18): the base image is pinned to the tag kinoite-main:44 (weekly updates by choice). If you want,
  add a `cosign verify` of Universal Blue's signature before building (S-M).
- U292/U294 (round 21): on a real PC, run the Windows tool once as a normal (not administrator) user, and do one
  real install with a non-US keyboard.
- U196: before you add the signing key (A032), bugos-ondertekend should change the origin in place
  (bootc switch --mutate-in-place) instead of rpm-ostree rebase; a rebase to the same image removes the older
  version, so "Back to the previous version" has nothing to go back to on that first signed boot.
- From the first round, still open (improve-2026-11-07.md "For you"): A032 signing key, default branch main,
  private vulnerability reporting, merge and build once.

## Found on the way
- Round 8, not fixed (unsure or a missing feature, not a bug): pinning apps in the start menu has no button; choosing
  a language also sets the date format (en_US for English); a new folder named "." or ".." gets an odd name; the trash
  shows the name inside the trash, not the original; emptying a huge trash runs in the window's thread; NTFS repair
  needs ntfsprogs (not in packages.txt); bugos-developer has no lock against two runs at once (Welcome no longer does it).
- "Log in without a password" still asks through pkexec (org.bugos.login.policy, auth_admin_keep): a family member
  who is not an administrator cannot switch it; that is on purpose (it changes how the whole PC logs in).
- The 117 texts built with f-strings cannot be translated to other languages yet (docs/TRANSLATING.md explains how).
- KDE's Settings quick tiles in bugos-settings get their screen-reader names from the label next to them (U016's
  fallback); explicit names there would be cleaner.
