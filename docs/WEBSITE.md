# The BugOS website

The website is the `website/` folder: plain HTML, pictures and fonts. No PHP, no database and no
build step on the server, so it works on any web host, including cheap shared hosting.

| Address | Language |
|---|---|
| `/` (`index.html`) | English, the default |
| `/nl.html` (also `/nl`) | Dutch |

Every page has a language button in the top bar and the language links at the bottom.

## Changing the website

Never edit `website/*.html` or `website/.htaccess` by hand: they are built.

| File | What it is |
|---|---|
| `tools/website/page.html` | The page itself, in English |
| `tools/website/nl.json` | The Dutch translation: pairs of [English piece, Dutch piece] |
| `tools/website/site.json` | Settings: the address, the folder on the server, https, the BugOS version |
| `tools/website/htaccess` | The template for `website/.htaccess` |
| `tools/website/404.html` | The "page not found" page |

Then build:

```bash
python3 tools/website/build.py          # builds website/: index.html, nl.html, .htaccess, 404.html, robots.txt, ...
python3 tools/website/og.py             # optional: new share picture (og.png) and README banner
```

The build stops when a Dutch piece no longer matches the English page, or when an English sentence
is left untranslated on the Dutch page, and says which one. CI (`build.yml`) checks that `website/`
is built from the latest sources.

**A new BugOS version?** Change `"versie"` in `site.json` and build. The label at the top, the
"What's new" section and the "still in development" line follow.

**Another language?** Add it to `TALEN` in `build.py` and make `tools/website/<code>.json` like `nl.json`.

## The download buttons (SourceForge)

GitHub allows at most 2 GB per file, and the ISO is about 6 GB. On GitHub it is therefore in pieces
(BugOS Switch glues them together). For the "Download (.iso)" buttons, `iso.yml` also puts the whole
ISO in one piece on [SourceForge](https://sourceforge.net) (free for open source, no size limit,
mirrors all over the world), under a fixed name:

| Button | File on SourceForge |
|---|---|
| BugOS | `bugos/BugOS.iso` (+ `BugOS.iso.sha256`) |
| BugOS for Nvidia | `bugos-nvidia/BugOS-Nvidia.iso` (+ `BugOS-Nvidia.iso.sha256`) |
| BugOS Switch | not on SourceForge: `releases/latest/download/BugOS-Switch.zip` on GitHub |

Every new ISO replaces the file with the same name, so the buttons never change. (A mirror can
serve the previous ISO for a short while after an upload.)

**Set up once:**

1. Make a free account on sourceforge.net and a project named `bugos` (Create → "Create a Project").
   A different name? Put it in `"sourceforge"` in `tools/website/site.json` and build the site again.
2. On your own computer, make an SSH key just for this: `ssh-keygen -t ed25519 -f bugos-sf -N ""`.
   Add `bugos-sf.pub` to SourceForge: Account Settings → SSH Settings.
3. In GitHub (Settings → Secrets and variables → Actions):
   - secret `SF_SSH_KEY`: the whole content of the private key `bugos-sf`
   - variable `SF_USER`: your SourceForge user name
   - variable `SF_PROJECT`: `bugos`
4. Run Actions → **BugOS ISO maken** with "publiceren" on, once for `bugos` and once for `bugos-nvidia`.
   The run summary shows the SourceForge link. Without the secrets the run still works, but only
   puts the pieces on GitHub, and says so with a warning.

**BugOS Switch:** the button downloads `BugOS-Switch.zip` from the newest normal (not pre-) release.
Make it by pushing a tag like `v0.4` and running Actions → **Windows-overstap** on that tag.

## Putting it on a shared host (cPanel, DirectAdmin, Plesk, ...)

1. In `tools/website/site.json`, fill in:
   - `"url"`: the full address with `/` at the end, for example `"https://bugos.example/"`.
     It gives the share picture a full address and adds `sitemap.xml` and the canonical links.
     (Empty works too; then those are left out.)
   - `"pad"`: `"/"` when the site is in the main folder of the domain (`public_html`),
     or `"/bugos/"` when it is in a subfolder.
   - `"https": true` once the host has a certificate (almost every host has free Let's Encrypt).
     It sends every visitor to `https://` and turns on HSTS.
2. Build: `python3 tools/website/build.py`, and commit the result.
3. Upload the **contents** of `website/` (not the folder itself) to the web folder of the host,
   usually `public_html/`. Include `.htaccess`: some FTP programs hide files that start with a dot.
   - **By hand:** Actions → **Website naar webhost** → Run workflow. Download the `bugos-website`
     zip at the bottom of the run, then in the File Manager of your host: Upload → Extract.
   - **Automatically:** add the secrets `FTP_SERVER`, `FTP_USERNAME` and `FTP_PASSWORD`
     (Settings → Secrets and variables → Actions), and optionally the variables `FTP_MAP`
     (default `public_html/`) and `FTP_PROTOCOL` (`ftps`, the default, or `sftp`).
     Then run **Website naar webhost** with "uploaden" on. It only adds and replaces files;
     it never deletes anything on the host.

### What the `.htaccess` does

- `index.html` is the start page, and `/index.html` is sent to `/`; `/nl` goes to `/nl.html`.
- An unknown address shows `404.html` (with status 404). It has no pictures or fonts of its own,
  so it looks right at any depth.
- No folder listings, and hidden files (`.git`, `.env`) and source files (`.md`, `.py`, `.json`) are refused.
- Security headers: `nosniff`, no framing by other sites, a strict referrer policy, no camera,
  microphone or location. The full Content-Security-Policy is a `<meta>` tag in each page,
  with the fingerprints of its own scripts, so it also works on hosts that ignore `.htaccess`.
- Pages are always fresh; pictures stay in the browser for 7 days, fonts for a year.
- Pages, SVG and the manifest are sent compressed (gzip).

Every part is wrapped in `<IfModule>`, so a host without one of those modules skips it instead of
breaking the site. Tested with Apache 2.4 (main folder and subfolder, http and https behind a proxy).

**nginx or LiteSpeed?** LiteSpeed reads `.htaccess` like Apache. nginx ignores it: the site still
works, only the extras above are missing (ask your host to set the 404 page to `/404.html`).

### Other places

- **GitHub Pages:** Actions → **Website** → Run workflow (see `website.yml`). Pages ignores `.htaccess`.
- **On your own computer:** `python3 -m http.server 8080 --directory website`, then open
  http://localhost:8080.

## Testing

```bash
python3 -m http.server 8080 --directory website &
cd e2e && npm ci && npx playwright test --trace off
```

The tests check both languages in light and dark (including an accessibility scan), the phone
width, the keyboard, the demo buttons, the language switch and the files a host needs.

## Privacy

The site loads nothing from other servers: fonts, pictures and scripts are all in `website/`.
No cookies, no analytics. The only thing it remembers is your light/dark choice, in your own browser.
