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

## Skipped

## For you
- The user said (2026-11-08): real-PC tests (below) come once an improve round finds nothing more; the GitHub
  settings (signing key, default branch, private reporting) and the merge are theirs; no merge before the real-PC test.
- U010: test changing your password once as a family member who is not an administrator, on a real BugOS PC
  (tested here with real PAM in the Fedora 44 image, not on hardware).
- U002, U004, U012: test once on a real PC: log in without a password after a restart; move files to a USB stick and
  check them on another computer.
- From the first round, still open (improve-2026-11-07.md "For you"): A032 signing key, default branch main,
  private vulnerability reporting, merge and build once.

## Found on the way
- "Log in without a password" still asks through pkexec (org.bugos.login.policy, auth_admin_keep): a family member
  who is not an administrator cannot switch it; that is on purpose (it changes how the whole PC logs in).
- The 117 texts built with f-strings cannot be translated to other languages yet (docs/TRANSLATING.md explains how).
- KDE's Settings quick tiles in bugos-settings get their screen-reader names from the label next to them (U016's
  fallback); explicit names there would be cleaner.
