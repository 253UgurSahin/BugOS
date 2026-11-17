# BugOS Switch: what goes on the USB drive (format version 2)

BugOS Switch (Windows, `BugOS-Switch.ps1`) writes a folder `BugOS-Switch` on the USB drive. BugOS ("Haal alles van
je oude pc", `bugos-switch`) reads it. This file is the contract between the two sides.

**Never on the drive: passwords.** No Wi-Fi keys, no browser passwords (`logins.json`, `key4.db`), no cookies, no
Windows credentials. The owner decided this (2026-11-16). Wi-Fi networks go along by name only; BugOS asks the
password once when the network is in range.

## Folder layout

```
BugOS-Switch/
    bugos-switch.json         the description below (UTF-8)
    Documents/ Pictures/ Music/ Videos/ Desktop/ Downloads/     the user's files (as in version 1)
    Bladwijzers/              bookmarks: <Browser>-<Profile>.json (Chrome/Edge/Brave format), Firefox-<Profile>.jsonlz4
    Firefox/<profile>/        a Firefox profile WITHOUT passwords and cookies (only when Windows had Firefox)
    achtergrond.jpg           the wallpaper (as in version 1)
    Extra/<name>/             extra folders the user picked (for example D:\Photos), one folder each
    Lettertypen/              fonts the user installed (per user, never the fonts of Windows itself)
    Thunderbird/<profile>/    the Thunderbird profile WITHOUT passwords, cookies and ImapMail (only when Windows had it)
    Outlook/                  Outlook mail files (.pst) that were not already in Documents
```

## bugos-switch.json

Version 1 fields stay (`versie`, `gemaakt`, `gebruiker`, `computer`, `taal`, `mappen`, `deels`), so an old BugOS can
still read a new drive. Version 2 sets `"versie": 2` and adds these. Every new field may be missing (an old
Windows, a failed read): BugOS then skips that part and says so.

```json
{
  "versie": 2,
  "instellingen": {
    "taal": "nl-NL",                       // Windows display language (Get-WinUserLanguageList, first)
    "notatie": "nl-NL",                    // regional format (Get-Culture)
    "tijdzone": "W. Europe Standard Time", // Windows time zone id (BugOS maps it to an IANA zone)
    "toetsenborden": ["00020409", "00000413"],  // keyboard layout ids (KLID) in order
    "donker": true,                        // apps in dark mode (AppsUseLightTheme = 0)
    "muis": { "linkshandig": false, "snelheid": 10, "scrollregels": 3 },  // speed 1-20 like Windows
    "schaal": 125                          // display scale in percent of the main screen
  },
  "wifi": [ { "naam": "Thuis-5G", "beveiliging": "WPA2-Personal", "verborgen": false } ],
  "printers": [ { "naam": "HP LaserJet", "adres": "192.168.1.40", "standaard": true } ],
  "programmas": [ { "naam": "Spotify", "uitgever": "Spotify AB", "versie": "1.2.3" } ],
  "browsers": [ { "browser": "Chrome", "profiel": "Default", "naam": "Persoon 1", "bladwijzers": "Bladwijzers/Chrome-Default.json" } ],
  "firefox_profiel": "Firefox/abc123.default-release",
  "extra": [ { "naam": "Foto's 2019", "map": "Extra/Foto's 2019", "van": "D:\\Foto's 2019" } ],
  "lettertypen": { "map": "Lettertypen", "aantal": 3 },
  "thunderbird_profiel": "Thunderbird/abcd.default-release",
  "outlook": { "pst": ["Outlook/thuis.pst", "Documents/Outlook Files/archief.pst"] },
  "cloud": { "aantal": 12, "bytes": 3400000, "voorbeelden": ["foto.jpg"], "meegenomen": false }
}
```

The last five fields came with "bestanden slimmer" (2026-11-16). `versie` stays 2: they are optional like every
other version 2 field, so an older BugOS simply ignores them.

Rules:
- `wifi`: only networks saved for the user (netsh), never the key. Enterprise (802.1X) networks are listed with their
  type, so BugOS can say "school or work network: sign in once".
- `printers`: only network printers (an IP address or host name); local USB printers come back by themselves.
- `programmas`: installed programs from the Uninstall registry keys (machine and user), without system components,
  updates and drivers. BugOS maps them to Store apps with `/usr/share/bugos/overstap-apps.json` and only SUGGESTS them
  (the owner's choice: never install by itself).
- Paths in the JSON are relative to the `BugOS-Switch` folder (except `extra[].van`: where it was on Windows, only
  to show the user).
- `extra`: folders the user added on top of the six. Never a whole drive, a Windows or program folder, or a folder
  that is (or contains) one that already goes along. BugOS puts each in the home folder under its `naam`.
- `lettertypen`: only `.ttf/.otf/.ttc/.otc` from `%LOCALAPPDATA%\Microsoft\Windows\Fonts` (fonts the user
  installed). The fonts of Windows itself are Microsoft's and stay home.
- `thunderbird_profiel`: like the Firefox profile, never passwords (`logins.json`, `key4.db` ...) or cookies.
  `ImapMail` stays home: it is a copy of the mail on the server, Thunderbird fetches it again.
- `outlook.pst`: Outlook data files. BugOS cannot open them by itself; it says where they are and what to do.
- `cloud`: files that were only in OneDrive (Files On-Demand). `meegenomen: true` means Windows downloaded them and
  they are on the drive; `false` means they stayed in OneDrive and BugOS says so (with a few example names).
