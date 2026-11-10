# Security

Found a security problem in BugOS? Thank you for telling us. Please tell us privately first,
so we can fix it before others can use it.

## How to report

Use GitHub's private reporting: open the **Security** tab of this repository and press
**Report a vulnerability**. Only the people who look after BugOS can read it.

Please do not open a public issue for a security problem.

Tell us:

- what the problem is and what someone could do with it;
- which BugOS version (Settings → About this computer, or `rpm-ostree status`) and which variant (normal or Nvidia);
- the steps to see it happen.

## What happens next

- We reply within 7 days.
- We fix it in a new BugOS. Computers with automatic updates get it by themselves; it is active after a restart.
- When the fix is out, we say what it was and thank you by name, if you want that.

## What counts

- BugOS's own programs and settings (`system_files/`), the build (`Containerfile`, `build_files/`),
  the update chain (images on GitHub Packages and their signatures), the Windows tool (`windows-switch/`)
  and the website (`website/`).
- Problems in Fedora, KDE, Universal Blue or an app from Flathub: please report those to them.
  If you are not sure where it belongs, tell us and we will pass it on.
