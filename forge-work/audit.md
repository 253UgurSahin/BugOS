# Audit: BugOS
Date: 2026-11-07   Commit: 4b393b7
Profile: none (detect.py: a Linux system image, not a web app)   Verdict: needs work (0 critical, 3 high, 1 medium, 2 low)
Severity: critical = stop, data or money at risk; high = fix before others use it; medium = fix
soon; low = when convenient. Effort: S = an hour, M = a day, L = more or a decision first.

IDs start at A030: the earlier audit (A001–A029) was never saved in the repo, but its IDs are in the
commit messages on main. New numbers keep them from getting mixed up.

## Summary
BugOS is its own Fedora Atomic system (Kinoite 44 from Universal Blue). It adds a Containerfile, a
build script, its own apps in Python/Qt and bash, Plasma menus in QML, and a Windows switch tool in
PowerShell. The code is in good shape. The scanners found no leaked keys, risky code or trackers, all
18 test suites pass, and the fixes from the previous audit hold. The biggest risks are in delivery,
not in the code. Since yesterday GitHub only builds when started by hand, so Fedora security updates no
longer reach users by themselves. Updates are not checked for a signature yet. And on Windows, the
switch tool's start file opens a file that no longer exists.

## Top 5
1. A030 [high] Double-clicking "Start BugOS Switch.bat" does nothing on Windows (effort S)
2. A031 [high] Fedora security updates no longer reach BugOS computers by themselves (effort S)
3. A032 [high] BugOS computers install updates without checking the signature (effort S, your key)
4. A033 [medium] Files saved with the older Windows switch tool are not found (effort S)
5. A034 [low] Several program files are over 500 lines (effort L, when you change them)

## Numbers
- Fedora Kinoite 44 (ghcr.io/ublue-os/kinoite-main:44 and kinoite-nvidia:44), bootc, KDE Plasma 6, GitHub Actions.
  8,709 files; 59 source files with extensions, 17,797 lines; plus 23 programs without an extension in
  system_files/usr/bin (8,706 lines, read separately).
- Tests: 18 of 18 passed (8 Python, 6 shell, qml-test, test_start_data, shellcheck, py_compile).
  test_backup.py passes once rsync is there (rsync is in packages.txt, so BugOS has it). Its one
  ResourceWarning ("1 uncollectable object at shutdown") comes from Qt objects at exit in the test: dismissed.
- Automatic checks: secretscan, codecheck, trackers: 0 findings. deps.py: no lockfiles, nothing to check.
- Installed only in this cloud container, with your go: PySide6-Essentials, libegl1, libgl1,
  libxkbcommon0, libfontconfig1, rsync. The repo is unchanged apart from this file. The `__pycache__`
  folders the tests made (git ignores them) have been removed again.
- End of life: Fedora 44 is supported until about 2 June 2027 (web search 2026-11-07, isitpatched.com and
  eosl.date; endoflife.date was not reachable from here). That is 7 months away: no finding yet, but
  plan the move to 45 (Containerfile, build.yml and tools/iso-local.sh) for the spring.
- Read in full: polkit rules, systemd units, bugos-login, bugos-updates, bugos-updatecheck,
  bugos-ondertekend, bugos-first-boot, Containerfile, the signing parts of build.sh, build.yml,
  iso.yml, windows-switch.yml, the download and USB parts of BugOS-Switch.ps1, the QML command calls.
  Sampled: bugos-switch, bugos-backup, the pkexec calls in bugos-settings, bugos-welcome and bugos-help.
- AVG/GDPR: BugOS sends nothing to anyone (no trackers, no analytics). The Windows tool writes your user
  name and computer name to bugos-switch.json, but only on your own USB drive: fine.

## Findings
### A030 [high] Double-clicking "Start BugOS Switch.bat" does nothing on Windows
where: windows-switch/Start BugOS Switch.bat:3
why:   the start file still opens `BugOS-Overstap.ps1`, but commit 16a757e renamed that file to
       `BugOS-Switch.ps1`. The window is hidden (`-WindowStyle Hidden`), so people get no error at
       all: nothing happens. This is the first step of the README and of the website.
fix:   change it to `"%~dp0BugOS-Switch.ps1"`, and add a step to windows-switch.yml that checks every
       `.ps1` the `.bat` names actually exists
effort: S

### A031 [high] Fedora security updates no longer reach BugOS computers by themselves
where: .github/workflows/build.yml:9-17 (since commit 4b393b7); docs/PLAN.md:57, :112, :164
why:   BugOS computers update from the BugOS image in GitHub Packages. That image now only gets built
       when someone presses "Run workflow", so fixes from Fedora and Universal Blue (kernel, browser,
       openssl) stop at GitHub until then. PLAN.md still promises "every night".
fix:   turn the `schedule` back on (once a week is enough to start). Stop the mails in your GitHub
       settings instead (Notifications > Actions > "Only notify for failed workflows"). Update PLAN.md.
effort: S

### A032 [high] BugOS computers install updates without checking the signature
where: system_files/etc/pki/containers/bugos.pub is missing; build_files/build.sh:176-196
why:   without the public key, build.sh sets `ostree-unverified-registry`. If someone gets write access
       to your GitHub Packages (a leaked token, a stolen account), every BugOS computer installs their
       image as the new system. The code for signing is ready (A002); only the key is missing.
fix:   follow docs/ONDERTEKENEN.md steps 1–4: `cosign generate-key-pair`, add SIGNING_SECRET and
       SIGNING_PASSWORD in GitHub, build once, then commit `cosign.pub` as bugos.pub. This is your step:
       forge never makes or touches your private key.
effort: S

### A033 [medium] Files saved with the older Windows switch tool are not found
where: system_files/usr/bin/bugos-switch:29, :56, :63; tools/test_backup.py:79
why:   the Windows tool used to save files to the folder `BugOS-Overstap` with `bugos-overstap.json`.
       After the rename, bugos-switch only looks for `BugOS-Switch/bugos-switch.json`. Someone who
       saved with the old zip sees "nothing found", even though their files are on the drive. The test
       still uses the old folder name but hands the folder over directly, so it does not catch this.
       (tools/screenshots/studio.py:40 already accepts both names.)
fix:   look for both names, as studio.py does; test the search itself with an old-name folder
effort: S

### A034 [low] Several program files are over 500 lines
where: system_files/usr/bin/bugos-files (2,155), bugos-settings (1,645), bugos-task-manager (707),
       bugos-welcome (522); system_files/usr/lib/bugos/python/bugos_ui.py (1,496), bugos_config.py
       (1,381), bugos_tasks.py (511); tools/icons/places.py (1,169), tools/plasma/surfaces.py (1,010),
       tools/kvantum/make.py (1,003), tools/icons/status.py (966), tools/plasma/buttons.py (740),
       build_files/build.sh (535)
why:   long files are hard to read, test and change without breaking something else
fix:   split each one by job (for example bugos-files: copying, drives, trash) the next time you change it
effort: L

### A035 [low] Build inputs go straight into a shell command
where: .github/workflows/iso.yml:82, :84, :201
why:   `${{ inputs.tag }}` and `${{ inputs.variant }}` are pasted into the script, so a strange value can
       run commands on the build machine. Only people with write access can start this, so the risk is small.
fix:   pass them through `env:` (TAG: ${{ inputs.tag }}) and use "$TAG" in the script
effort: S

## Not checked
- Git history not scanned for secrets (no gitleaks here); secretscan only checked the current files
- deps.py: no lockfiles. Python packages come from Fedora; PySide6 in CI is not pinned to a version
- The image build itself (podman build, bootc container lint) and ISO builds: they need a big runner
- BugOS-Switch.ps1 on real Windows; its CI (windows-switch.yml) only runs by hand, so it did not run now
- The running system (menus, apps, installer): that is /forge-inspect
