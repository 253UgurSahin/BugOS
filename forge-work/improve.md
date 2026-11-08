# Improve: BugOS
Date: 2026-11-07   Branch: ccr-5bd1cae9-pccs3q   Started from: main at 4b393b7 (+ audit report 44bc1f7)
Picked: A030, A031, A033, A035, then "Alles" with A034 confirmed as "Alles opsplitsen".
The user said: "A030 (Recommended),A031 (Recommended),A033 (Recommended),A035,Alles", then for A034 "Alles opsplitsen".
Tests after /forge-test: 20 checks passed, 0 failed (tools/test_edges.py added); website e2e 13 of 13 passed.
Tests before: 17 passed, 1 failed (the design makers; my first count said 18 passed because the test
script hid that failure, see A036). After: 19 passed, 0 failed (one new test, test_windows_start).
Security (forge-secure scanners: secretscan, codecheck, deps, trackers): PASS, no findings.
Fixed: A030, A031, A033, A034, A035, plus A036 (found on the way). For you: A032.
Secrets before: none (secretscan found nothing).
All changes: git diff 44bc1f7 ccr-5bd1cae9-pccs3q

Branch note: forge normally works on a new forge/improve-<date> branch. This session may only push to
ccr-5bd1cae9-pccs3q, so the work is there. Merging into main is your step.

## To do
(nothing left)

## Fixed
### A030 [high] Double-clicking "Start BugOS Switch.bat" does nothing on Windows
where:  windows-switch/Start BugOS Switch.bat:3
why:    the start file opened BugOS-Overstap.ps1, renamed to BugOS-Switch.ps1; the hidden window showed no error
fix:    it opens BugOS-Switch.ps1; tools/test_windows_start.sh checks every script a .bat opens exists (in build.yml)
effort: S
commit: 1011af6 fix(A030): the Windows start file opens BugOS-Switch.ps1 again
test:   tools/test_windows_start.sh (failed before the fix, passes now)
verify: on Windows, unzip BugOS-Switch.zip and double-click "Start BugOS Switch.bat": the window opens

### A031 [high] Fedora security updates no longer reach BugOS computers by themselves
where:  .github/workflows/build.yml:9-17; docs/PLAN.md
why:    builds ran only by hand, so Fedora's fixes stopped at GitHub
fix:    a weekly schedule (Monday 03:17 UTC) next to "Run workflow"; push/PR builds stay off, so no mail per change.
        The comment says how to get mail only for failed runs. PLAN.md says "once a week" now.
effort: S
commit: b3da5ca fix(A031): build BugOS by itself once a week again
test:   YAML checked: on = workflow_dispatch + schedule. A real scheduled run can only be seen on GitHub.
verify: after the next Monday, Actions > "BugOS bouwen" shows a run started by "schedule"

### A033 [medium] Files saved with the older Windows switch tool are not found
where:  system_files/usr/bin/bugos-switch:29-75
why:    only BugOS-Switch/bugos-switch.json was searched; the old tool wrote BugOS-Overstap/bugos-overstap.json
fix:    it looks for both folder names and reads both info files
effort: S
commit: e93a4fd fix(A033): bugos-switch also finds files saved by the older Windows tool
test:   tools/test_backup.py, "vindt de map van de nieuwe ... en de oude Windows-versie" (failed before, passes now)
verify: a USB drive with a BugOS-Overstap folder shows up in "Files from Windows"

### A035 [low] Build inputs go straight into a shell command
where:  .github/workflows/iso.yml:78-90, :200-210
why:    the free-text tag was pasted into the script, so a strange value could run commands on the build machine
fix:    variant and tag come in through env:, and a tag that is not a valid image tag stops the run
effort: S
commit: 08a8c95 fix(A035): ISO build reads its inputs through env and checks the tag
test:   the check accepts "latest" and "claude-fix-x" and refuses "x;id" and "$(id)" (checked here in bash)
verify: start "BugOS ISO maken" with tag "latest": it runs as before

### A036 [high] Every build failed, 10 BugOS app icons were missing and Windows programs lost their colours (found on the way)
where:  tools/{icons,kvantum,plasma,gtk,konsole,wine,brand}/*.py; system_files/usr/share/icons/BugOS/apps/scalable;
        system_files/usr/share/bugos/wine
why:    the English rename moved tools/ontwerp, icons/basis.py, the icon lists and brand/merk.py, but the makers
        still imported the old names. So build.yml's check step failed, and the build job needs it. The committed
        output was out of step too: the .desktop files ask for bugos-files, bugos-settings and so on, but the
        icons were still called bugos-bestanden etc.; bugos-exe reads wine/licht.reg and donker.reg, but the repo
        had light.reg and dark.reg.
fix:    the makers import the new names, and their output (renamed icons, licht/donker.reg) is committed
effort: S
commit: c79fe69 fix(A036): the design makers run again, and app icons and Wine colours are back
test:   every maker runs and exits 0, and running them again changes nothing (the "makers" check)
verify: on BugOS, the start menu shows the BugOS icons for Files, Settings, Store and the rest
why fixed without asking: A034 splits these makers, and that cannot be checked while they do not run. A031's
        weekly build would also fail on it.

### A034 [low] Several program files are over 500 lines
where:  the 13 files in audit.md
why:    long files are hard to read, test and change without breaking something else
fix:    each split by job, the code moved as-is (only imports, short docstrings and pointer comments are new).
        Old module names stay the way in, so other code and the tests import the same names as before.
        Biggest code file now: bugos_widgets.py, 414 lines.
effort: L
commits:
  600b2e2 build.sh -> build.sh 79, system.sh 236, style.sh 238
  cc63b01 bugos-files 2,155 -> 66 + nine bugos_files_*.py (158-354)
  94a71c4 bugos_config.py 1,381 -> 114 + five bugos_config_*.py (200-345)
  93fa5f8 bugos-settings 1,645 -> 195 + seven bugos_settings_*.py (152-306)
  28fea61 bugos_ui.py 1,496 -> 411 + bugos_base, bugos_widgets, bugos_pages, bugos_shell (85-414)
  741c8e7 bugos_tasks.py 511 -> 355 + bugos_desktop.py 172
  0d0550d bugos-task-manager 707 -> 438 + bugos_tasks_ui.py 286
  f079f4a bugos-welcome 522 -> 432 + bugos_welcome_panel.py 101
  db33462 tools/icons/places.py 1,169 -> six files (121-388)
  affe877 tools/icons/status.py 966 -> four files (135-377)
  c6284bb tools/plasma/surfaces.py 1,010 -> five files (164-287)
  ed014bb tools/plasma/buttons.py 740 -> four files (68-298)
  8126747 tools/kvantum/make.py 1,003 -> six files (57-303)
test:   all 19 checks pass after each step. Tests that swap a function (bugos_config.draai, VOORBEELD,
        _accounts_dbus, bugos_ui.uitvoeren) still reach the moved code: the new modules look these up through
        the old module. Checked line by line: every line of each old file is in the new files.
        Studio screenshots of every app (light and dark) are pixel-identical before and after; the generated
        icons and themes are byte-identical (8,524 files hashed, also for --alleen and --controleer).
verify: build an image and open each BugOS app once (Files, Settings, Task Manager, Welcome, Help)

## Skipped
(none)

## For you
- A032: updates are still installed without a signature check until you add the key. Follow
  docs/ONDERTEKENEN.md steps 1-4: `cosign generate-key-pair`, put SIGNING_SECRET and SIGNING_PASSWORD in
  GitHub (Settings > Secrets and variables > Actions), build once, then commit cosign.pub as
  system_files/etc/pki/containers/bugos.pub. Keep cosign.key safe; forge never touches it.
- A031: GitHub only runs a schedule on the default branch. If that is not main yet, set it
  (Settings > General > Default branch; also a todo in docs/PLAN.md). Too much mail: Settings > Notifications >
  Actions > "Only notify for failed workflows".
- Merge ccr-5bd1cae9-pccs3q into main when you are happy with it, then start "BugOS bouwen" once by hand.

## Found on the way
- B001 fixed in 04e18fb, see bugs.md
- B002 fixed in b2237c7, see bugs.md
- B003 fixed in 4c4ffbf, see bugs.md
- B005 fixed in 2c653c9, see bugs.md
- B004 fixed in 8780e30 (your option 1), see bugs.md
- B006 fixed in 3e39404 (a side effect of the A033 fix: a stick with both folders showed twice), see bugs.md
- B007 fixed in 85233e4, see bugs.md
- The real image was built and tested here (tools/test_image.sh, 73 checks, all pass; bootc container lint passes). See test-plan.md, F18.
- The image build was run here later, in /forge-test: build.sh with system.sh and style.sh works, the renamed icons are in place (test-plan.md, F18).
- tools/screenshots/studio.py: the welcome scene sometimes crashes on exit ("pure virtual method called"),
  before and after these changes; its run function never closes the window, so a thread is still alive.
- Settings demo mode: the Wi-Fi card says "Not connected" because the demo network is "Home" but the sample list says "Thuis".
- tools/icons/places*.py comments still say teken_map/SOORTEN are "in bugos-files"; they now live in
  bugos_files_tegels.py and bugos_files_plekken.py.
- bugos_files_computer.py, toon_ruimte: `hol=pad == "vrij"` can never be true (dead code, already so before).
- tools/icons/base.py imports ROOD_VERLOOP without using it; tools/kvantum/kvconfig.py sets `naam` and never uses it.
- The new submodules (bugos_widgets, bugos_config_netwerk and so on) only work when imported through their
  parent module (bugos_ui, bugos_config); their docstrings say so. Nothing imports them another way.
