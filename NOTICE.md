# Licenses in BugOS

## BugOS's own work: free to use, not for commercial use

Everything the BugOS project made itself (the apps, scripts, themes, logo, wallpapers, website and documentation in
this repository) is licensed under the **PolyForm Noncommercial License 1.0.0** ([`LICENSE`](LICENSE)).

Required Notice: Copyright 2026 Ugur Sahin (https://github.com/253UgurSahin/BugOS)

In plain words:

- **Allowed:** using BugOS at home, at school, in a library or at a non-profit; reading the source code, changing it and
  sharing your changes (with this license and the notice above), for any noncommercial purpose.
- **Not allowed:** using BugOS's own work to make money: selling it, putting it on computers you sell, offering it as a
  paid service, or using it inside a business. Want to use it commercially? Ask: open an issue on GitHub.

The source code stays open for everyone to read. Because commercial use is not allowed, BugOS's own work is
"source-available" and not "open source" in the strict sense of the Open Source Initiative.

**Earlier versions:** versions published before this change (up to and including commit `43d54db`, November 2026)
were licensed under GPL-3.0-or-later. Whoever got a copy of those under the GPL keeps the GPL rights for that copy.

## Work by others: their own licenses

BugOS is built on the work of others. Those parts keep their own licenses, and the license above does not change them:

| What | License |
|---|---|
| Everything in the BugOS system image that comes from Fedora Kinoite, KDE Plasma, Universal Blue, the Linux kernel, Wine, Flathub apps and other packages | Their own licenses (mostly GPL, LGPL, MIT and similar). They can be found inside BugOS in `/usr/share/licenses` and with `rpm -qi <package>`. |
| The fonts in `branding/fonts/`, `system_files/usr/share/fonts/bugos/` and `website/fonts/` (Funnel Display, Atkinson Hyperlegible Next, Inter, JetBrains Mono) | SIL Open Font License 1.1 (the `OFL-*.txt` next to each font) |
| `iso_live/src/build.sh` follows the example of Titanoboa (Universal Blue) | Apache-2.0 for the parts taken from that example |
| `system_files/usr/share/bugos/windows-tijdzones.json` (Windows time zone names from Unicode CLDR) | Unicode License V3 |

## Contributing

By sending a contribution (code, a translation, a picture), you agree that it is licensed under the same terms as
BugOS's own work, and that the BugOS project may also license it under other terms in the future.

This is not legal advice.
