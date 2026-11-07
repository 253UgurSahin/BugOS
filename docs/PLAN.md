# 🐞 The BugOS blueprint

> Explained as simply as possible. If Bugie doesn't get it, we write it again.

## What is BugOS?

BugOS is a free operating system for your computer, just like Windows.
It is made for **everyone**:

- 🐞 **Bugie** should be able to use it without help.
- 🎮 **Gamers** should be able to play well on it.
- 🛠️ **Developers** should enjoy working on it.

The most important idea: **BugOS can't break.**

## The choices we made together

| Topic | What we chose | Why, in plain words |
|---|---|---|
| Foundation | Fedora Atomic: its own system on Universal Blue's `kinoite-main` (plain Fedora Kinoite with codecs and drivers), just like Bazzite. The Nvidia version uses `kinoite-nvidia`. | The system is made of "unbreakable glass". Every update is a complete new version. Something goes wrong? Then you pick the previous version when the computer starts. |
| Shell | Our own BugOS coat on the KDE engine | KDE already handles windows, Wi-Fi, Bluetooth and screens well. We make the start menu, the taskbar, the style and our own BugOS apps. |
| Look | Our own BugOS style, light or dark | Buttons are where you know them from Windows, but it looks different. You choose light or dark yourself. |
| Updates | Automatic by default, with a switch for "I'll do it myself" | Bugie doesn't have to do anything. Anyone who wants to choose can. |
| Programs | The BugOS Store, plus double-clicking downloads | Just like your phone, and also just like Windows. |
| Windows programs | Double-click an `.exe` and it starts through Wine | If it doesn't work, BugOS explains what you can use instead. |
| Gamers | Steam and Proton, game mode, controllers and Nvidia | Play without hassle. |
| Developers | Developer mode switch, containers, VS Code and programming languages | Everything is ready with one click, and Bugie never sees any of it. |
| Languages | English by default; our own screens in English and Dutch | Every other language can be added with translation files. KDE itself already speaks 50+ languages. |
| Installing | USB stick, also next to Windows, plus a Windows switching program | Switching should be easy. |
| Computers | Normal PCs and laptops, Nvidia, old PCs (with light mode) | Light mode turns on by itself on slow computers. |
| Privacy | No account and no data collection | Your computer belongs to you. |
| License | GPL-3.0 | Always free and open. |

## How is BugOS put together? (the house)

```
┌─────────────────────────────────────────────────────────┐
│  🐞 BugOS coat (ours)                                   │
│  Start menu · Taskbar · Style · BugOS Welcome · Store   │
│  Game mode · Developer mode · Light mode                │
│  Open .exe · Install .rpm/.deb · Updates button         │
│  Files (the file explorer, with big tiles)              │
├─────────────────────────────────────────────────────────┤
│  🧱 KDE Plasma (the engine)                             │
│  App windows · Wi-Fi · Bluetooth · Dolphin (advanced)   │
│  Disk management (KDE Partition Manager) · Sound        │
├─────────────────────────────────────────────────────────┤
│  🏠 Fedora Kinoite / kinoite-main (the foundation)      │
│  Drivers · Codecs (movies/music) · Nvidia · Updates     │
│  with an "undo button"                                  │
└─────────────────────────────────────────────────────────┘
```

## How does an update reach the user? (the bakery)

1. We change something in this repo.
2. GitHub automatically bakes a new BugOS. This also happens every night, so security updates from Fedora come along.
3. The user's computer fetches it in the background.
4. The next time the computer starts, the new version runs.
5. Problems? Then you pick the previous version in the startup menu, and everything is back to how it was yesterday.

## What is already in it (version 0.3)

### Apps you can see

| App in the start menu | File | What it does |
|---|---|---|
| BugOS Welcome | `bugos-welcome` | The first screen: language, Wi-Fi, light or dark, updates, gaming or programming, and bringing back files from Windows. |
| Settings | `bugos-settings` | Like Settings in Windows, but calmer. Home: quick toggles (Wi-Fi, Bluetooth, night light, dark) and the volume. Its own pages in plain words: Wi-Fi and internet (networks, connect with a password), Bluetooth (connect devices), Printers and scanning (printers, queue, test page, scanning), Sound (volume, which speaker), Screen (brightness, night light, size), Power (saver/balanced/fast, battery, screen off, sleep, power button, closing the lid), Appearance (light/dark, background), Notifications (do not disturb, quiet during games, sound, test notification), Mouse and touchpad (speed, left-handed, scroll direction, tapping, double-click), Easier to see (large text, large pointer, shake the mouse, magnifier, sticky keys, slow keys, screen reader), Time and language (set the clock automatically, time zone, language), Sign-in and password (name, change password, sign in without a password, lock screen), Default apps (internet, email, photos, music, videos, PDF, text), Updates and more, About this computer. Search across everything. Each page has 'More settings (for advanced users)' that leads to KDE. |
| Something is not working | `bugos-help` | Checks internet, Wi-Fi, Bluetooth, sound, printer, storage and updates. Every problem has a "Fix" button. |
| Backup | `bugos-backup` | Your files to a USB drive with one button, and back again. Nothing is ever thrown away. |
| Files from Windows | `bugos-switch` | Brings back the files, bookmarks and background you took from Windows with BugOS Overstap. |
| Game mode on/off | `bugos-game-mode` | Full power, notifications muted and an FPS counter. |
| BugOS Store | `bugos-store` | 37 well-known, safe apps in 10 topics, install with one click. "Find more apps" opens the big KDE store. |
| Start menu | `org.bugos.startmenu` | The start button at the bottom left (the ladybug), by default. A greeting, a big search bar that finds apps and the pages of Settings, pinned apps, recent files, all apps by topic, and at the bottom Settings, Lock, Sign out, Restart and Shut down. Alt+F1 and the Windows key open it. Prefer the KDE menu? Settings → Updates and more → Taskbar. |
| Quick menu | `org.bugos.quickmenu` | Next to the system tray, by default. Big buttons for Wi-Fi, Bluetooth, game mode, dark, do not disturb and mute, plus sliders for volume and (on a laptop) brightness, and the battery; the little arrow next to a button opens the matching page in Settings (for example to pick a Wi-Fi network). It is the one place for these things: the KDE tray icons that do the same (sound, network, Bluetooth, brightness and battery, clipboard, keyboard layout...) are hidden, but keep working in the background (volume keys, low-battery warnings). |
| Shutdown screen | `logout/Logout.qml` | The screen for Shut down, Restart or Sign out: big tiles for Sleep, Restart, Shut down (red), Sign out and a "Never mind" button. From the start menu it counts down 30 seconds and says so in plain words. It goes into Plasma's shell package and into the BugOS look-and-feel. |
| Set up the taskbar | `bugos-panel` | Puts the BugOS start menu and the quick menu on the taskbar (`standaard`, once after signing in, also for people who already had a taskbar), or turns one of the two on/off (`startmenu|snelmenu aan|uit|status`). `systeemvak rustig|alles` hides or brings back the KDE tray icons the quick menu replaces (turning the quick menu off brings them back). "Off" puts the KDE menu back the way BugOS had set it up. |
| Files | `bugos-files` | The file explorer: big tiles with previews, your usual places and USB sticks on the left. When you pick something, the bottom shows what you can do with it (Open, Copy, Throw away...). Throwing away goes to the trash first (with Undo); nothing is ever overwritten. **This computer**: all your drives (USB stick, external drive, second drive, Windows drive, SD card, CD) with how much space is left; open with one click (also when locked: KDE asks for the password) and safely remove the whole stick. Per stick or drive (the '…' button): rename, check and repair, erase. A **new, empty drive**: 'Start using' (partition and format, like Disk Management in Windows); after that it is always there. Disk management (KDE Partition Manager) for advanced users. |
| Task Manager | `bugos-task-manager` | Like Task Manager in Windows (Ctrl+Shift+Esc), but simpler: at the top, in plain words, how things are going (with a tip when it is busy), open programs with 'Close' (politely, and forced if it doesn't respond), performance with small graphs (processor with temperature, memory, disk, internet, graphics card) and programs that start with the computer on/off. You can't stop parts of BugOS itself by accident. |
| Open drives | `bugos-open-drives` | After signing in, opens the drives inside the computer so they are always there (like D: in Windows). No password needed for administrators (polkit rule). |
| Sign in without a password | `bugos-login` | Sets the sign-in screen (SDDM) to 'sign in automatically' for one user, or turns it off again. Settings calls it through pkexec; KDE asks for your password once (polkit action org.bugos.login). |
| More apps, Disks, Dolphin | (KDE) | KDE programs with a simple BugOS name. Dolphin is the file explorer for advanced users. |

### What happens in the background

| Part | File | What it does |
|---|---|---|
| Windows programs | `bugos-exe` | Double-click an `.exe` and it starts through Wine. If there is a better version in the Store, that is offered first. |
| Downloads from websites | `bugos-package` | Double-click an `.rpm` or `.deb`: it first looks in the Store, otherwise it installs it safely in a little box. |
| Updates | `bugos-updates` | Automatic or by yourself; update now or go back to the previous version. |
| Update notification | `bugos-updatecheck` | With "update myself" you get a notification once a day with an "Update now" button. |
| Developer mode | `bugos-developer` | VS Code, containers and a dev box with programming languages. |
| Light mode | `bugos-light-mode` | Turns off the heavy effects on old PCs by itself. |
| First start | `bugos-first-boot` | Sets up LibreOffice, VLC and Steam. |
| Translations | `vertalingen/*.json` | Any language can be added without writing code (see [TRANSLATING.md](TRANSLATING.md)). |
| Style | `look-and-feel`, `color-schemes`, `bugos_ui.py` | Taskbar at the bottom, BugOS colors for light and dark, the fonts, the logo, the "Stip" background, the boot, sign-in and lock screens, and pinned favorites in the start menu. All BugOS apps use the same design (`bugos_ui.py`). See [BRAND.md](BRAND.md). The window title bar: Breeze border with BugOS colours (no line between bar and window), big round buttons, a red round close button, title on the left. |

### For Windows (`windows-switch/`)

**BugOS Overstap** (the Windows app that helps you switch) has the same look as BugOS (dark sidebar with the steps, red buttons) and works in four steps:

1. Check: can this PC run BugOS? It looks at 64-bit, memory, UEFI, space, BitLocker and Nvidia.
2. Take along: documents, photos, music, videos, desktop, downloads, bookmarks and background go to a USB drive.
3. Make room: Windows is made smaller, so BugOS fits next to it.
4. Make the USB stick: BugOS is downloaded automatically (the right version for your graphics card), checked and put on the USB stick.

### The bakery (`.github/workflows/`)

| Workflow | What it does |
|---|---|
| `build.yml` | Builds BugOS (normal and Nvidia), on every change and every night. |
| `iso.yml` | Makes a USB stick (ISO) on request. By default that is the "try first" stick with the new installer. On request it puts the ISO in pieces of less than 2 GB in a GitHub Release. |
| `windows-switch.yml` | Checks the Windows program on a real Windows computer and packs it. With a version tag (like `v0.2`) it turns it into a download. |
| `website.yml` | Puts the website (`website/`) online through GitHub Pages. Set to manual for now. |

## The roadmap

### Phase 1: Foundation ✅
- [x] Plan on paper
- [x] BugOS is built automatically, in a normal and an Nvidia version
- [x] An ISO for the USB stick on request
- [x] The first BugOS parts of our own

### Phase 2: Our own coat ✅
- [x] **BugOS Settings** with big tiles and a search bar
- [x] An update notification for people who choose "myself"
- [x] **BugOS Store** in our own style, with safe and tested apps up front
- [x] Pinned favorites in the start menu
- [x] **Our own start menu**, on the taskbar by default (the KDE menu can still be chosen in Settings)
- [x] **Quick menu** in BugOS style, next to the system tray by default

### Phase 3: Switching ✅ (signing is waiting on the manager)
- [x] **Windows switch**: PC check, take files along, make room, download BugOS and write the USB stick
- [x] In BugOS: bring back the files from Windows with one button
- [x] **"Try first" USB stick** with the new installer (Anaconda WebUI). It asks few questions, warns about BitLocker and explains the blue key screen for Nvidia.
- [x] **The stick is BugOS**: BugOS itself is on the stick and installs without internet. No more Aurora or Fedora names or logos on the stick, in the installer and in the installed system (welcome screen, terminal, sign-in screen, "About this system", start menu, store). The stick starts in English; you choose your language, keyboard and time zone in the installer (the date and time page is no longer hidden).
- [x] A download place for the ISO: GitHub Releases, in pieces of less than 2 GB. BugOS Overstap glues them back together by itself.
- [ ] **Sign the Windows program**, so Windows doesn't show a warning. This normally costs money (a certificate). For open-source projects it can be free through [SignPath Foundation](https://signpath.org). The owner of the repo has to apply, so **this is a task for the manager**.

### Phase 4: Polishing ✅ (except for the manager's items)
- [x] Help app "Something is not working"
- [x] Backup with one button
- [x] Translating without programming (little dictionaries per language)
- [x] Our own website with a download button (ready, but not online yet)
- [ ] Find volunteers for translations (**manager**)
- [ ] Our own domain name for the website (**manager**)

### Phase 5: New design ✅
- [x] **New logo**: a ladybug made of simple shapes, in color, in one color and as an app icon
- [x] **New background "Stip"**, light and dark
- [x] **Brand style** on paper: logo, colors, fonts, shapes and how we talk ([BRAND.md](BRAND.md))
- [x] **All BugOS apps** redesigned, in light and dark: Welcome, Settings, Store, Something is not working, Backup, Files from Windows and the "try first" stick
- [x] **Desktop**: new colors, our own fonts, start menu and quick menu, boot screen, sign-in and lock screen, boot logo
- [x] **New website** with real screenshots, a try-it-yourself for "back to yesterday" and a light/dark switch
- [x] **BugOS Overstap** (Windows) in the new style, sharp on 125% and 150% screens
- [x] **Premium round:** our own BugOS line icons, calmer apps (only problems get color), and a website that tells the story: why a ladybug, the Bugie test and a day at home

### For the manager: what is needed to hand out BugOS
- [ ] Make the **repo** and the **packages** (`bugos`, `bugos-nvidia`) **public**. Without that:
  - BugOS Overstap can't download BugOS,
  - and installed computers get no updates.
  - (Installing from the "try first" stick does work: BugOS itself is on the stick.)
- [ ] In **Settings**, set the default branch to `main`. Then the nightly build (with security updates) runs on `main`.
- [ ] Signing through SignPath, volunteers and a domain name (see above).

### Next: testing on real computers
- [ ] **Switched to English, new base `kinoite-main`:** the docs and the default language are now English, the word "oma" has been replaced by "Bugie". The image builds (locally with Podman, 2026-11-04: `ID=bugos`, no Aurora left, Discover Flatpak-only, update timers on, `bootc container lint` passes). Not tested yet: the stick (ISO) in a VM, and the English screenshots (run `screenshots.yml` again).
- [ ] **New stick not tested yet** (branch `claude/fix-iso-alleen-bugos`). BugOS now goes on the stick as an OCI folder; unpacking it into the container storage did not work (whiteouts: "open /etc/.wh.bazaar: invalid argument"). Next step: run `tools/iso-local.sh` (or iso.yml), boot the ISO in a VM, install without a network and check the installed system (no Aurora/Fedora; `stat /usr/libexec/utempter/utempter` must be `root:utmp`).
- [ ] Try the "try first" stick on a real PC
- [x] Start menu and quick menu by default (tested outside Plasma: tools/qml-test.py, tools/test_start_data.py, tools/test_logout.py)
- [ ] Check the start menu, quick menu and shutdown screen on a real PC (Windows key, picking Wi-Fi, shutting down) — see TESTING.md
- [ ] Desktop photos from the real screen: the photo round (`tools/screenshots/desktop.sh`) starts KWin and plasmashell in the container, but the build computer has no graphics card; even with KWin's software renderer (KWIN_DRM_DEVICES), KWin 6.8 found no 'render device'. Next step: test on a real PC or a VM with a screen. Until then: photos from the photo studio.
- [ ] Try BugOS Overstap on a real Windows PC (steps 3 and 4 on a spare PC first)

## Things to watch out for

- **Nvidia:** we use the "open" Nvidia driver. It works on cards from about 2018 onwards (RTX 20 series and newer, GTX 16 series). For older Nvidia cards we need to sort something out later.
- **Secure Boot key for Nvidia (MOK):** with Secure Boot on, the installer adds Universal Blue's driver key (pinned and checked with sha256 in `iso_live/src/build.sh`). After the restart a blue "MOK Manager" screen asks for a password, which is always `bugos`. That is on purpose: you type it once, at the computer itself, and only to confirm that key. It does not unlock anything and is not your login password. A random password would be safer in theory, but people can't remember it for one screen. If we ever change this, we generate the password in the installer and show it in the same dialog.
- **Old PCs:** BugOS needs a 64-bit computer with at least 4 GB of memory. Very old PCs (from the Windows XP days) won't work.
- **Windows programs:** not everything works through Wine. Anti-cheat in some online games and heavy programs like Adobe and the newest Office often don't work. That's why BugOS always explains what the alternative is.
- **Its own system on `kinoite-main`:** BugOS no longer builds on Aurora. Just like Bazzite, it builds on Universal Blue's plain base (Fedora Kinoite with codecs and drivers); the Nvidia version uses `kinoite-nvidia`. Because of that, BugOS is also called BugOS on the inside (`ID=bugos`, `ID_LIKE=fedora`) and handles its own updates: `rpm-ostreed-automatic.timer` for the system (staged, active after a restart) and `bugos-update-apps.timer` for the Flatpak apps (daily).

## Glossary

| Word | Means |
|---|---|
| Distro | A "flavor" of Linux. BugOS is a distro. |
| Image | One complete package of the whole system. |
| Container / little box | A closed-off space where a program runs without being able to break the system. |
| Flatpak | The way the Store installs apps. |
| Wine / Proton | The "translator" that makes Windows programs and games work. |
| KDE Plasma | The desktop (the engine) that our BugOS coat sits around. |
| ISO | The file you put on a USB stick to install BugOS. |
