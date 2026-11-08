# Improve: BugOS (the OS itself)
Date: 2026-11-08   Branch: ccr-5bd1cae9-pccs3q   Started from: ccr-5bd1cae9-pccs3q at d285f6c
Picked: U001-U031 (all). The user said: "/forge-improve bugos os, niet dewebsite of eromheen echt het os gedeelte", then "fix alles"
Tests before: 20 passed, 0 failed (build.yml check job, run here).
Secrets before: none (secretscan: no findings).
All changes: git diff d285f6c ccr-5bd1cae9-pccs3q

Where the list comes from: a read-only review of the OS part only (system scripts and services, the apps, Settings,
menus and the installer), 2026-11-08. Facts were checked in the real Fedora 44 base image where possible
(no sddm but Plasma Login Manager; no qdbus6 but qdbus-qt6).
The branch note of the first round still applies: this session may only push to ccr-5bd1cae9-pccs3q, so the work is
there (and in pull request #2).

## To do
### High
U001 Screen off "Never" still turns the screen off after 30 s and dims at once.
  where: system_files/usr/lib/bugos/python/bugos_config_scherm.py:296-297 (zet_scherm_uit_na), reader scherm_uit_na
  why: writes TurnOffDisplayIdleTimeoutSec=0 / DimDisplayIdleTimeoutSec=0 but leaves TurnOffDisplayWhenIdle and
  DimDisplayWhenIdle at default true; powerdevil 6.5 then uses max(0, 30s) and dims at 0s.
  fix: for 0 write TurnOffDisplayWhenIdle=false and DimDisplayWhenIdle=false; for other values set them true; read them back.
U002 "Log in without a password" does nothing on Fedora 44, but the switch shows on.
  where: system_files/usr/bin/bugos-login:10 (BESTAND=/etc/sddm.conf.d/...), bugos_config_account.py:126 (SDDM_BESTANDEN)
  fix: write /etc/plasmalogin.conf.d/50-bugos-login.conf ([Autologin] User= Session= Relogin=false) when
  /usr/lib/plasmalogin exists, else the SDDM path; readers check both. Also: user-name regex rejects valid names
  like jan.jansen (allow dots, keep it strict and `id`-checked).
U003 Copying/moving a folder to a USB stick copies NOTHING if one file is refused.
  where: system_files/usr/lib/bugos/python/bugos_files_acties.py:166-173 (kopieer_een), :212 (Klus, fout = str(e))
  why: copytree raises shutil.Error for one bad name (':' '?' '*' on FAT/exFAT, EINVAL), then ruim_op deletes the
  whole temp folder; the user sees a raw Python list. Also copy2/copystat chmod fails with EPERM on vfat/exfat for
  modes it cannot store, so a 0600 file or 0700 folder fails entirely.
  fix: a copy function that copies data + mtime and ignores EPERM/ENOTSUP from chmod/copystat; for bad names keep
  the rest of the folder and say plainly which files could not go and why (like Backup does), no raw list.
  Keep A011's promise: never leave a half folder pretending to be complete (the folder is complete except the
  named files, and the message says so). Repro scripts: scratchpad/review-apps/repro_folder_copy.py, repro_vfat_chmod.py
U004 Move to a USB stick deletes the originals before the data is really on the stick.
  where: bugos_files_acties.py:163-180 (cross-drive branch of kopieer_een)
  fix: before deleting the source of a cross-drive move, fsync the copied files and their folder (or os.sync() /
  syncfs on the target once per job) and show "Writing to the stick..." while it runs.

### Medium
U005 "Update now" says "Update done" even when the system update failed.
  where: system_files/usr/bin/bugos-updates:47-48 (nu); bugos-updatecheck:38
  fix: rpm-ostree upgrade || fout=1; still run flatpak update; exit "${fout:-0}". Same for terug (rollback).
U006 "Update now" and "Back to the previous version" in Settings give no feedback (output to /dev/null); a
  cancelled pkexec on the auto/manual switch leaves the switch flipped.
  where: bugos_settings_systeem.py:96, :99 (start(...)), bugos_base.py:62-65
  fix: run them through QProcess (not on the GUI thread) and show done + "restart" or the error; re-read the
  switch state after pkexec ends. Depends on U005's exit codes.
U007 Developer mode says ON even when setting it up failed.
  where: system_files/usr/bin/bugos-developer:25-37 (every step >/dev/null, unconditional touch "$MARKER")
  fix: check distrobox create/enter and the flatpak install; on failure fout "Are you online?" and no marker.
U008 Command output is parsed in the user's language: Dutch quick-menu Wi-Fi tile always off and cannot turn
  Wi-Fi off; Help says "Wi-Fi is off" in Dutch; Printers empty in German/French/Spanish/Italian.
  where: system_files/usr/bin/bugos-start-data:323, :339 (`nmcli radio wifi` without -t); system_files/usr/bin/bugos-help:73;
  bugos_config.py:39 (draai has no LC_ALL=C), bugos_config_meldingen.py:222 (lees_lpstat); bugos-start-data's draai.
  fix: every helper that runs a command whose output is parsed sets env LC_ALL=C (draai in bugos_config, bugos-start-data,
  bugos-help); use `nmcli -t -f WIFI radio`. Repro: scratchpad/review-settings/repro_nl_wifi.py, repro_lpstat_de.py
U009 Night light does nothing until the next login.
  where: bugos_config_scherm.py:166 (zet_nachtlicht: kwriteconfig6 without --notify)
  fix: use _c.kde_schrijf("kwinrc","NightColor","Active",...) which adds --notify.
U010 A non-admin user cannot change their own password (AccountsService SetPassword needs auth_admin).
  where: bugos_config_account.py:216, bugos_settings_account.py:209-216
  fix: for non-admins use PAM `passwd` with old+new password on stdin (no command-line secrets); at least say
  clearly when an administrator is needed.
U011 A Wi-Fi network whose saved password changed can never be reconnected from BugOS.
  where: bugos_settings_netwerk.py:85, bugos_config_netwerk.py:93-99 (draai drops stderr)
  fix: when connecting to a known network fails, ask for the password and use `nmcli --ask connection up id <naam>`
  (password via stdin, never argv) or delete+recreate the profile.
U012 Backup (and Switch after restore) says "You can unplug it now" while data may still be in the write cache.
  where: system_files/usr/bin/bugos-backup:347 (rsync_maak, klaar); bugos-switch
  fix: rsync --fsync (rsync 3.2.7 has it) or a `sync -f <target>` step before "Done".
U013 Store says Firefox and Steam (system RPMs) are not installed and offers a second copy.
  where: system_files/usr/bin/bugos-store:44-50 (geinstalleerd only reads flatpak list), :104
  fix: treat an app as installed when its .desktop exists in the app dirs (or the binary exists); Open then
  launches it with gtk-launch/kioclient instead of flatpak run.
U014 Backup window freezes after "Make backup" on large folders.
  where: bugos-backup:373 (ruimte_genoeg on the GUI thread, walk at :139-160)
  fix: run ruimte_genoeg in a QThread (like Help's Klusje), show "Checking space...".
U015 Closing Backup or Switch during a backup/restore silently aborts it.
  where: bugos-backup:236 (no closeEvent; QProcess(self) at :275); bugos-switch (Overstap)
  fix: closeEvent that asks/waits while the process runs, like Files' sluit_na_klus.
U016 Screen readers hear no names: Settings switches (Schuif) and clickable rows (Rij), drive cards and Welcome
  choices (KeuzeKaart).
  where: bugos_widgets.py:402 (KeuzeKaart), :252 (Schuif); bugos_shell.py:56-70 (Rij); bugos_pages.py:48 (SchijfKiezer)
  fix: setAccessibleName/Description from the visible title/text (and update when it changes); rows that are
  clickable get a button role. Repro: scratchpad/review-apps/repro_a11y.py, review-settings/repro_a11y.py
U017 Game mode's FPS counter only appears after logging in again, and stays after game mode is off.
  where: system_files/usr/bin/bugos-game-mode:31-32, :45-46 (MANGOHUD=1 via environment.d only)
  fix: MANGOHUD=1 always in the session env, and switch the overlay on/off in ~/.config/MangoHud/MangoHud.conf
  (no_display), which MangoHud re-reads; or else say clearly "after logging in again".
U018 qdbus6 does not exist on Fedora 44: Help's "Restart now" button does nothing; light mode does not reload KWin.
  where: system_files/usr/bin/bugos-help:177 (start("qdbus6",...)); bugos-light-mode:58, :88
  fix: use qdbus-qt6 or gdbus (bugos-start-data and bugos-panel already fall back to gdbus); one shared way.
U019 Translations to other languages cannot work: template.json is stale (195 of 471 strings) and
  tools/collect-translations.py writes to share/bugos/vertalingen/sjabloon.json, the apps read share/bugos/translations/.
  where: tools/collect-translations.py:22, :33, :58; system_files/usr/share/bugos/translations/template.json
  fix: DOEL = share/bugos/translations, name template.json, regenerate. f-string t() calls (112) cannot be
  translated: note it in docs/TRANSLATING.md (converting them is out of scope unless small).

### Low
U020 First boot offline keeps the system in "starting" (oneshot with Restart=on-failure, WantedBy=multi-user.target).
  where: system_files/usr/lib/systemd/system/bugos-first-boot.service
  fix: not block boot: e.g. a timer that retries (OnBootSec / OnUnitInactiveSec) with the condition file, or Type=exec.
U021 Daily app-update and update-check timers slip by days on laptops that sleep (OnUnitInactiveSec/OnUnitActiveSec).
  where: bugos-update-apps.timer, user bugos-updatecheck.timer
  fix: OnCalendar=daily + Persistent=true, keep RandomizedDelaySec.
U022 BugOS ignores KDE's language choice (LANGUAGE): KDE in Dutch, BugOS in English.
  where: system_files/usr/share/bugos/lib.sh:6; the Python t() language detection (bugos_base.py TAAL)
  fix: look at the first entry of $LANGUAGE first, then LC_ALL, LC_MESSAGES, LANG (bash and Python alike).
U023 Light mode switches itself on for ordinary 6-8 GB PCs (MemTotal < 6000000 kB).
  where: system_files/usr/bin/bugos-light-mode:32
  fix: lower to ~5000000 kB (or round to whole GB first).
U024 After "Back to the previous version", the daily check says a new version is ready.
  where: system_files/usr/bin/bugos-updatecheck:15 (deployments[0].booted == false)
  fix: only say "update ready" when deployments[0] is newer (timestamp/version) than the booted one; otherwise neutral.
U025 Settings opened from the quick menu belongs to plasmashell (P5Support executable engine): it can be killed with
  the applet, and a second click does nothing.
  where: system_files/usr/share/plasma/plasmoids/org.bugos.quickmenu/contents/ui/main.qml:86
  fix: launch through `bugos-start-data --start instelling:<page>` (detaches with setsid), as the start menu does.
U026 A Bluetooth device can only be "forgotten" while connected.
  where: bugos_settings_netwerk.py:160-167
  fix: a "..." menu with Forget on rows that are not connected too.
U027 The live USB mixes languages: Dutch-only GRUB entries, English-only install error dialog (+ MOK/Nvidia dialogs).
  where: iso_live/src/iso.yaml:6,9; iso_live/src/build.sh:234-238 and the dialogs below
  fix: bilingual entries and messages (English first, Dutch after, as elsewhere on the stick).
U028 Files says "Drag something here", but dropping does nothing.
  where: bugos_files_venster.py:145 (DragOnly), :245
  fix: accept drops (DragDrop + dropEvent -> Klus copy, or move with Shift) — or, if that grows past S/M, change the text.
U029 Renaming Foto.JPG to Foto.jpg on a FAT/exFAT stick is refused as "already exists".
  where: bugos_files_bewerken.py:155
  fix: skip the exists check when os.path.samefile(old, new).
U030 Sizes use a decimal comma in English ("3,2 GB").
  where: bugos_drives.py:24 (mooie_maat)
  fix: comma only for Dutch (TAAL == "nl").
U031 Search does nothing when Files is started with a relative folder (bugos-files Documents).
  where: system_files/usr/bin/bugos-files:47 (start_pad without resolve)
  fix: Path(a).expanduser().resolve().

## Fixed

## Skipped

## For you
(from the first round, still open: see improve-2026-11-07.md "For you": A032 signing key, default branch main,
private vulnerability reporting, merge and build once)

## Found on the way
