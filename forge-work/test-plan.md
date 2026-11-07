# Test plan: BugOS

Build: 2c653c9  Date: 2026-11-07  Profile: none (a Linux system image; website: static)  PWA: no
Runs against: the BugOS apps in this container (Qt offscreen, fake programs, temporary folders) and the
website at http://localhost:8080 (`python3 -m http.server 8080 --directory website`). scope.py: exit 0 (localhost)

## How to run

- Unit and integration tests, the same as build.yml's "controle" job, from the repo root:
  `QT_QPA_PLATFORM=offscreen python3 tools/test_<name>.py` and `bash tools/test_<name>.sh`
  (needs PySide6-Essentials, rsync, shellcheck, and libegl1 libgl1 libxkbcommon0 libfontconfig1).
  The design check: run every maker (build.yml lists them); `git status` must stay empty.
- End to end, the website: start the server above, then from e2e/:
  `npm ci && FORGE_BASE_URL=http://localhost:8080 npx playwright test`. No accounts, so no E2E_PASSWORD
  and nothing skipped. The site has no rate limits.

## Cases

Flows: F01 website · F02 start the Windows switch · F03 files from Windows · F04 backup and restore ·
F05 Files · F06 Settings · F07 Task Manager · F08 "Something is not working" · F09 start menu and
quick menu · F10 updates and builds · F11 signed updates · F12 app icons · F13 Windows programs ·
F14 everything loads · F15 ISO build · F16 install a .rpm or .deb · F17 game mode, light mode, taskbar,
log out.

| case | flow | type | steps | expected | auto | result |
| --- | --- | --- | --- | --- | --- | --- |
| F01-H1 | website | happy | open the home page (light) | heading, Download, no console errors or broken files, axe WCAG 2.2 AA clean | e2e | fail B004 (B001 fixed) |
| F01-H2 | | happy: dark | the same with the computer in dark mode | axe clean | e2e | fail B004 (B001, B002 fixed) |
| F01-H3 | | happy: images | scroll to the end | every visible image loaded, every image has alt | e2e | pass |
| F01-H4 | | happy: after scrolling | scroll through, then scan (light and dark) | axe clean apart from B004's scroll text | e2e | pass (B005 fixed) |
| F01-E1 | | edge: links | every #link | goes to a part that exists | e2e | pass |
| F01-E2 | | edge: theme remembered | light/dark button, reload | dark stays, screenshots swap, axe clean | e2e | fail B004 |
| F01-E3 | | edge: 390px | phone width, menu open and close | no sideways scroll, menu works, axe clean | e2e | fail B004 (B003 fixed) |
| F01-E4 | | edge: keyboard only | Tab, Enter, Space | menu and buttons reachable, focus visible, questions open | e2e | pass |
| F01-E5 | | edge: slider | arrow keys on the light/dark slider | value changes | e2e | pass |
| F01-E6 | | edge: demo undo | "Pretend something goes wrong", "Pick yesterday" | "One more time", axe clean | e2e | fail B004 |
| F01-E7 | | edge: full motion | scroll through without reduced motion | no errors | e2e | pass |
| F01-N1 | | negative: storage blocked | private window, storage throws | page and theme button work | e2e | pass |
| F01-N2 | | negative: wrong address | /this-page-does-not-exist | 404 | e2e | pass |
| F01-M1 | | manual: text on the big photo | look at the top of the page in light and dark | menu, heading, Download and the four facts easy to read | manual | for you |
| F02-H1 | Windows switch start (A030) | happy | the .bat opens a script | the script it names exists | unit | pass (test_windows_start) |
| F02-M1 | | manual | on Windows: unzip, double-click "Start BugOS Switch.bat" | the BugOS Switch window opens | manual | for you |
| F03-H1 | files from Windows | happy | restore Documents and Pictures, bookmarks, wallpaper | on the right place, nothing overwritten | unit | pass (test_backup) |
| F03-E1 | | edge: old tool (A033) | a drive with BugOS-Overstap/bugos-overstap.json | found and read | unit | pass (test_backup) |
| F03-E2 | | edge: strange names | accents, emoji, 75 characters | all come over | unit | pass (test_edges) |
| F03-E3 | | edge: HTML in a bookmark | `<script>` in a name, `&` and `"` in an address | written safely | unit | pass (test_edges) |
| F03-N1 | | negative: one folder fails | rsync 23 on Documents | the rest comes over, a message | unit | pass (test_backup) |
| F04-H1 | backup and restore | happy | make a backup, restore it | files back, free space counted right | unit | pass (test_backup) |
| F04-E1 | | edge: strange names | accents, emoji, 75 characters | backed up and restored with their own names | unit | pass (test_edges) |
| F04-E2 | | edge: other computer or user name | restore from user@old-laptop | backup found | unit | pass (test_backup) |
| F05-H1 | Files | happy | trash and restore, copy, move, empty trash | nothing lost, nothing overwritten | unit | pass (test_files) |
| F05-E1 | | edge: strange names | accents, emoji, 75 characters | trash, restore, copy, "(2)" names work | unit | pass (test_edges) |
| F05-E2 | | edge: copy fails halfway, other drive, broken links | | no half folders, links to the trash | unit | pass (test_files) |
| F05-N1 | | negative: erase a drive | only removable drives offer "Erase everything" | | unit | pass (test_files) |
| F06-H1 | Settings | happy | every page opens; wifi, bluetooth, sound, screen read right | | unit | pass (test_settings) |
| F06-E1 | | edge: commands it runs | login, updates, power profile | the right command, password asked | unit | pass (test_settings) |
| F07-H1 | Task Manager | happy | measure, group, start-up apps, close | protected parts cannot be closed | unit | pass (test_task_manager) |
| F08-H1 | Something is not working | happy | checks and repairs in the background | no freeze, no "printer ready" without a printer | unit | pass (test_help) |
| F09-H1 | start menu, quick menu | happy | apps, search settings, quick menu state; menus load | | unit | pass (test_start_data, qml-test) |
| F10-H1 | updates and builds (A031) | happy | build.yml | weekly schedule and by hand; build after the check; every test runs | unit | pass (test_edges) |
| F10-M1 | | manual | after a Monday: Actions > BugOS bouwen | a run started by "schedule", green | manual | for you |
| F11-H1 | signed updates | happy | a PC without checks moves once; others are left alone | | unit | pass (test_signed) |
| F11-M1 | | manual (A032) | add the key, build, update a PC | `rpm-ostree status` shows ostree-image-signed | manual | for you |
| F12-H1 | app icons (A036) | happy | every Icon= of a BugOS .desktop file | the icon exists in the theme | unit | pass (test_edges) |
| F13-H1 | Windows programs (A036) | happy | the colour files bugos-exe reads | licht.reg and donker.reg exist | unit | pass (test_edges) |
| F13-E1 | | edge: strange names, Wine fails | | no command runs, a clear stop | unit | pass (test_exe) |
| F14-H1 | everything loads (A034) | happy | load every Python program and shared module | no import errors | unit | pass (test_edges) |
| F15-N1 | ISO build (A035) | negative | tags "x;id", "$(id)", "a b", backticks | refused; "latest" and branch names work | unit | pass (test_edges) |
| F16-N1 | install .rpm/.deb | negative | strange file names | nothing runs | unit | pass (test_package) |
| F17-H1 | game mode, light mode, taskbar, log out | happy | on twice then off; off restores; retry; buttons per situation | | unit | pass (test_game_mode, test_light_mode, test_panel, test_logout) |
| M01 | install | manual | build the image, make the ISO, install in a VM and on a real PC | BugOS starts, app icons show, apps open | manual | for you |
| M02 | screen reader | manual | Orca on BugOS: Files, Settings, Welcome | every button and row is read out | manual | for you |

auto: `e2e` (a Playwright spec), `unit` (the project's own tests in tools/) or `manual`. result: `pass`,
`fail B004` (the bug in bugs.md) or `for you` (manual, waiting for you).

## Not tested

- The image build (podman build, bootc container lint) and the ISO: they need a big runner and the base
  image. The first build after merging is the test for the build.sh split and the renamed icons.
- Real hardware, Nvidia and Secure Boot, a real Windows PC, a screen reader: see the manual cases.
- The apps' look on screen: tools/screenshots/studio.py made pixel-identical screenshots before and after
  the A034 split (forge-work/improve.md); no new screenshots in this round.
- Firefox and Safari for the website: only Chromium is installed here.

## Result

Cases: 46 in the plan. 40 run automatically (13 e2e, 27 unit): 35 passed, 5 failed (all B004), 0 skipped. 6 manual cases are for you.
Behind the unit cases: 400 checks in 16 test files, all passed, plus shellcheck, the compile check,
the makers and the GTK check.
Bugs (the counts `../forge-test/bugs.py` prints): 0 critical, 0 high, 2 medium, 3 low;
1 open (B004, low), 4 fixed, 0 wontfix.
`python3 ../forge-test/bugs.py forge-work/bugs.md`: exit 0.
