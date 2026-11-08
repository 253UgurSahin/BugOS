# Security check
Date: 2026-11-08
Verdict: FAIL
Counts: 0 critical, 1 high, 1 medium, 1 low

Project: BugOS at commit c3b4ecf (branch ccr-5bd1cae9-pccs3q). A bootable Fedora Atomic image (Containerfile,
bootc), its own apps (Python/Qt, bash), Plasma menus (QML), a Windows tool (PowerShell), GitHub Actions and a
static website. No accounts, no server, no payments, no database.

## What was checked
- secretscan (8,680 files, no findings), codecheck (92 files, no findings), deps (e2e/package-lock.json with
  npm audit: no findings), trackers (117 files, no third-party services), AVG/GDPR checklist
- Opt-outs: no file uses `forge:allow`
- Framework checks: containers (Containerfile), static site (website/). Skipped: Laravel, Django, Next.js,
  Stripe (not used)
- Also, because this is an operating system: the parts that run as administrator (polkit rules and actions,
  the pkexec helpers bugos-login and bugos-updates, the systemd services), the update chain (signing, the
  weekly build) and the GitHub Actions workflows (pinning, permissions, inputs). The image itself was built and
  tested in /forge-test (tools/test_image.sh: 73 checks pass, bootc container lint passes).

## Findings
### X001 [high] The build sends the whole repo to the builder, because there is no .dockerignore
where: (missing) .dockerignore next to Containerfile
why:   forge's container rule: .git, forge-work/ and any file of secrets must be kept out of the build. Today
       nothing leaks: the Containerfile only copies build_files/ and system_files/, through a stage that is not
       part of the image. But the builder still gets everything (the git history, forge's reports, e2e/node_modules),
       and one future `COPY . .` would put them in every BugOS computer.
fix:   add a .dockerignore that leaves out everything except Containerfile, build_files/ and system_files/
effort: S

### X002 [medium] The Windows tool's release step uses an action by a tag that can move
where: .github/workflows/windows-switch.yml:109 (softprops/action-gh-release@v2)
why:   this step runs with `contents: write` and publishes BugOS-Switch.zip, which people run as administrator
       on Windows. A tag like @v2 can be pointed at other code by whoever controls that repo; iso.yml already pins
       the same action to a fixed commit.
fix:   pin it to the same commit as iso.yml: softprops/action-gh-release@3bb12739c298aeb8a4eeaf626c5b8d85266b0e65 # v2.6.2
effort: S

### X003 [low] The website has no Content-Security-Policy
where: website/index.html (no CSP meta tag); the site is served by GitHub Pages, which sets no CSP header
why:   a CSP limits the damage if a script ever gets onto the page. The site has no forms, no user content and
       no third-party scripts, so the risk is small. Its two scripts and its styles are inline, so a strict
       policy needs hashes for them.
fix:   add a `<meta http-equiv="Content-Security-Policy">` with default-src 'self', the hashes of the two inline
       scripts, style-src 'self' 'unsafe-inline' (inline styles) and img-src 'self' data:; let tools/website/build.py
       compute the script hashes
effort: M

## Seen and fine
- No secrets in the repo or the workflows; the signing key and passwords are GitHub secrets (SIGNING_SECRET,
  SIGNING_PASSWORD), and GITHUB_TOKEN is only piped into `podman login --password-stdin`.
- The pkexec helpers check their input: bugos-login only accepts a real user name (`^[a-z_][a-z0-9_-]{0,31}$`
  and `id`), bugos-updates only takes fixed words. Both polkit actions ask for an administrator password
  (auth_admin_keep).
- The polkit rule lets an active local administrator (group wheel) open internal drives without a password,
  like Windows; formatting still asks. This is a deliberate choice, written in the rule.
- The quick menu and start menu quote what they pass to the shell (A029); the ISO workflow checks its tag (A035).
- Third-party actions are pinned to a commit, apart from X002; actions/* (GitHub's own) use major tags.
- Container rules: the image runs as root by design (it is an operating system, bootc needs it), so there is no
  USER line; the base image is pinned to Fedora 44, not `latest`; no secret in any ARG or ENV.
- AVG/GDPR: BugOS and its website collect nothing: no accounts, no analytics, no trackers, no cookies (the website
  says so too). The Windows tool writes the user's name and computer name only to their own USB drive.
  Export, deletion, retention, processors and DPAs: not applicable, as no personal data reaches the project.

## Not checked
- semgrep is not installed. With your go: `pip install semgrep`, then `semgrep scan --config p/default --metrics=off .`
- pip-audit, composer: no Python or PHP lockfiles to check (Python packages come from Fedora).
- Live website headers (https://253ugursahin.github.io/BugOS/): the network of this session refuses github.io,
  so headers.py could not run. Passive only in any case (not in forge-work/scope.json).
- The update signature check itself: no signing key yet (A032, for you), so `ostree-image-signed` was not tried.
- Git history not scanned for secrets (no gitleaks here).
- Breach plan: who answers if someone reports a security problem? There is no SECURITY.md. A question for you,
  not a finding.

## Accepted risks
None.
