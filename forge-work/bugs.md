# Bugs

## B001 [medium] [fixed] Small grey text on the website is too faint to read well
case: F01-H1, F01-H2   screen: website home   build: 18ce410   browser: Chromium, 1440px wide, light and dark
steps: open the website; look at the notes under the pictures, the table headings in "What do you need", and the footer
expected: at least 4.5:1 contrast for normal text (WCAG 2.2 AA)
actual: 2.98:1 (light) and 4.04:1 (dark) for the notes and table headings, 3.24:1 and 4.2:1 in the footer; 20 elements in light, 10 in dark. The colour is --tekst3 (#8A8F9A light, #6E737D dark) in tools/website/page.html
evidence: e2e/f01-website.spec.ts "F01-H1" and "F01-H2" (axe: color-contrast)
fixed in: 04e18fb

## B002 [medium] [fixed] In dark mode the white text on the red Download buttons is too faint
case: F01-H2, F01-E2   screen: website home   build: 18ce410   browser: Chromium, 1440px wide, dark
steps: open the website with the computer in dark mode (or press the light/dark button); look at "Download"
expected: at least 4.5:1 contrast for the button text
actual: white on #F04452 is 3.71:1 (in light mode, white on #DE2F3E is 4.58:1 and passes)
evidence: e2e/f01-website.spec.ts "F01-H2" (axe: color-contrast, .knop-rood)
fixed in: b2237c7

## B003 [low] [fixed] At phone width the terminal picture scrolls sideways, but not with the keyboard
case: F01-E3   screen: website, "Sanne starts coding"   build: 18ce410   browser: Chromium, 390px wide
steps: open the website at 390px wide; scroll to the terminal; try to reach it with Tab
expected: content that scrolls can be reached and scrolled with the keyboard (or does not need to scroll)
actual: the terminal (role="img") is wider than the screen and scrolls sideways with a finger only; Tab skips it
evidence: e2e/f01-website.spec.ts "F01-E3" (axe: scrollable-region-focusable, .terminal)
fixed in: 4c4ffbf

## B004 [low] [fixed] Text that fills in while you scroll is grey and hard to read until you reach it
case: F01-H1, F01-E3, F01-E6   screen: website, "The story" and "A day at home"   build: 18ce410   browser: Chromium, 390px and 1440px
steps: open the website; look at the words of the story and the moments of "A day at home" that are not the current one
expected: readable text (4.5:1), also for people who turned off animations
actual: the moments not yet reached are 1.6:1 (light) and 1.78:1 (dark), their headings 2.1:1 and 2.6:1; the story words 1.6:1 until scrolled past. With "reduce motion" on, the moments still start grey
evidence: e2e/f01-website.spec.ts "F01-H1" and "F01-E3" (axe: color-contrast, .moment and .w)
fixed in: 8780e30
the user chose: "B004 fix it 1" (option 1: the text not yet reached becomes a readable grey instead of faded)

## B005 [low] [fixed] The comment lines in the terminal picture are too faint
case: F01-H1, F01-H2   screen: website, "Sanne starts coding" (desktop width)   build: b2237c7   browser: Chromium, 1440px wide, light and dark
steps: open the website at desktop width; scroll to "Sanne starts coding"; look at the grey "#" lines in the terminal
expected: at least 4.5:1 contrast: on the desktop stage the terminal is text for screen readers too (the copy drops role="img")
actual: #6B707A on #0B0B0D is 3.95:1
evidence: an axe scan after scrolling through the whole page (color-contrast, .terminal .c), in F01-H1 and F01-H2 once B004 is out of the way
fixed in: 2c653c9

## B006 [medium] [fixed] A USB stick used with both versions of the Windows switch shows up twice
case: F03-E4   screen: Your files from Windows (bugos-switch)   build: 074a3df (built image)   browser: - (Qt app in the BugOS image, 780px)
steps: plug in a drive that has both BugOS-Switch and BugOS-Overstap (the tool was used before and after the rename); open "Your files from Windows"
expected: the drive once, with the newest folder
actual: two identical rows "Bugie's USB stick, From Bugie on LIVING-ROOM-PC"; caused by the A033 fix (3e39404 fixes it)
evidence: photo studio inside the built image (switch-licht.png); tools/test_edges.py "een stick met beide mappen staat er één keer"
fixed in: 3e39404

## B007 [low] [fixed] In sample mode, Settings says Wi-Fi is "Not connected"
case: F06-E2   screen: Settings, home page (sample mode, used for the website screenshots)   build: 074a3df (built image)   browser: - (Qt app in the BugOS image, 1120px)
steps: start Settings in sample mode (the photo studio does this); look at the Wi-Fi card
expected: "Connected to Home", as the sample data says
actual: "Not connected": the sample data says Home, the sample network list still said Thuis
evidence: photo studio inside the built image (settings-donker.png); tools/test_edges.py "wifi is verbonden met 'Home' uit de lijst"
fixed in: 85233e4

## To check
- The numbered dots in the logo drawing (.opbouw .nr): checked after scrolling the whole page; axe finds no problem there.
- The text on top of the big photo at the top (menu, heading, "Download", the four facts): axe cannot work out the contrast over a picture. Check by eye in light and dark (see test-plan.md, manual).
- bootc container lint gives 2 warnings (no failures): /run/setrans has content, and /var/lib/samba/winbindd_privileged has no tmpfiles.d entry. Both come from Fedora packages, not from BugOS's own files. Check whether a newer base image still has them.
