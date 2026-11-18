#!/usr/bin/env python3
"""Bouw de website (map website/) uit tools/website/page.html.

Engels is de standaardtaal (website/index.html); de Nederlandse pagina (website/nl.html) komt uit
dezelfde bron met de vertalingen in tools/website/nl.json. Daarnaast maakt hij wat een gewone
webhost (shared hosting met Apache) nodig heeft: .htaccess, 404.html, robots.txt, site.webmanifest
en, als het adres in site.json staat, sitemap.xml.

Vult de plekken in met het echte BugOS-logo (zodat de website altijd hetzelfde
beestje laat zien als BugOS zelf):
  {{MERK:naam}}  -> het beestje; het kopje volgt licht/donker (CSS-variabelen)
  {{OPBOUW}}     -> de opbouwtekening van het logo met hulplijnen en nummers
Gebruik: python3 tools/website/build.py
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

HIER = Path(__file__).resolve().parent
ROOT = HIER.parent.parent
sys.path.insert(0, str(ROOT / "tools" / "brand"))
from mark import CX, CY, HR, HX, HY, R, RAND, STIPPEN, merkteken  # noqa: E402


def merk_variabel(uid: str) -> str:
    """Het merkteken waarvan de kop en de kopvlekjes CSS-variabelen volgen."""
    m = merkteken(uid)
    m = m.replace(f'fill="#16171C" mask="url(#{uid}-kop)"', f'style="fill:var(--merk-kop)" mask="url(#{uid}-kop)"', 1)
    m = m.replace(f'<g fill="#FFFFFF" mask="url(#{uid}-kop)">', f'<g style="fill:var(--merk-oog)" mask="url(#{uid}-kop)">', 1)
    assert "var(--merk-kop)" in m and "var(--merk-oog)" in m
    return m


def merk_svg(uid: str) -> str:
    if uid == "winmerk":  # Windows-titelbalk is altijd licht
        return f'<svg class="m" viewBox="0 0 256 256" aria-hidden="true">{merkteken(uid)}</svg>'
    return f'<svg viewBox="0 0 256 256" aria-hidden="true">{merk_variabel(uid)}</svg>'


def opbouw() -> str:
    """Opbouwtekening: het beestje met de cirkels waarmee het getekend is."""
    hulp = (
        f'<g class="hulp" fill="none" stroke="currentColor" stroke-width=".7">'
        f'<circle cx="{CX}" cy="{CY}" r="{R}" stroke-dasharray="3 3"/>'
        f'<circle cx="{CX}" cy="{CY}" r="{R + RAND}" stroke-dasharray="1 3"/>'
        f'<circle cx="{HX}" cy="{HY}" r="{HR}" stroke-dasharray="3 3"/>'
        f'<path d="M{CX} -18V270" stroke-dasharray="2 4"/>'
        f'<path d="M-28 {CY}H284M60 {HY}H196" stroke-dasharray="1 4"/>'
        f'<path d="M{CX - 5} {CY}h10M{CX} {CY - 5}v10M{HX - 5} {HY}h10M{HX} {HY - 5}v10"/>'
    )
    for x, y, r in STIPPEN:  # hulpcirkels om de stippen
        for sx in (x, 256 - x):
            hulp += f'<circle cx="{sx}" cy="{y}" r="{r + 5}" stroke-dasharray="1 2.5"/>'
    hulp += "</g>"
    maten = (
        '<g class="hulp" fill="currentColor" font-family="JetBrains Mono, monospace" font-size="7.5">'
        f'<text x="{CX + R + 10}" y="{CY - 4}">r 94</text>'
        f'<text x="{HX + HR + 6}" y="{HY - 3}">r 44</text>'
        '</g>'
    )

    def merker(n: int, x: float, y: float, x1: float, y1: float, x2: float, y2: float) -> str:
        return (f'<path d="M{x1} {y1}L{x2} {y2}" stroke="var(--rood)" stroke-width="1" fill="none"/>'
                f'<circle cx="{x}" cy="{y}" r="9.5" fill="var(--rood)"/>'
                f'<text x="{x}" y="{y + 3.4}" text-anchor="middle" font-family="JetBrains Mono, monospace" '
                f'font-size="10" font-weight="600" fill="#fff">{n}</text>')

    merkers = (merker(1, 240, 236, 204, 209, 232, 230)
               + merker(2, 12, 80, 77, 108, 20, 85)
               + merker(3, 210, 0, 160, 28, 202, 5))
    label = ("How the BugOS logo is built: two wings (1), four dots (2) and a head with two "
             "white spots (3), drawn with circles and one straight line.")
    return (f'<svg class="tekening" viewBox="-36 -26 328 312" role="img" aria-label="{label}">'
            f'{merk_variabel("opbouw")}{hulp}{maten}{merkers}</svg>')


def csp(pagina: str) -> str:
    """De Content-Security-Policy: alleen onze eigen scripts (op hun vingerafdruk), stijlen, plaatjes en
    letters van de site zelf, en verder niets. De vingerafdrukken rekenen we hier uit, zodat ze altijd
    kloppen met de scripts in de pagina."""
    scripts = re.findall(r"<script>(.*?)</script>", pagina, flags=re.S)
    assert scripts, "geen scripts gevonden"
    hashes = " ".join("'sha256-" + base64.b64encode(hashlib.sha256(s.encode("utf-8")).digest()).decode() + "'"
                      for s in scripts)
    regels = ["default-src 'none'", f"script-src {hashes}",
              "style-src 'self' 'unsafe-inline'",  # de pagina heeft style="..." op een paar plekken
              "img-src 'self' data:", "font-src 'self'", "manifest-src 'self'",
              "base-uri 'none'", "form-action 'none'", "object-src 'none'"]
    return f'<meta http-equiv="Content-Security-Policy" content="{"; ".join(regels)}">'


# De talen van de site. Engels is de standaard (index.html); elke andere taal is een eigen pagina
# naast index.html (zelfde map, dus dezelfde plaatjes en letters), vertaald met tools/website/<taal>.json.
TALEN = [
    # taal, bestand, adres vanaf de hoofdmap, naam, kort, og:locale
    ("en", "index.html", "", "English", "EN", "en_GB"),
    ("nl", "nl.html", "nl.html", "Nederlands", "NL", "nl_NL"),
]

# Woorden die in elke taal hetzelfde zijn: die hoeven niet vertaald (zie controleer_vertaling).
ZELFDE = {
    "BugOS", "GitHub", "Fedora", "KDE Plasma", "Universal Blue", "64-bit", "UEFI", "Download", "08:30",
    "10:15", "11:30", "13:00", "16:30", "21:00", "€0", "0", "1", "2", "3", "4", "4 GB", "8 GB", "16 GB",
    "40 GB", "Minimum", "Intel, AMD or Nvidia", "Nvidia GTX 16 or RTX", "Back", "Next", "BugOS Switch",
    "BugOS Store", "Steam", "EN", "NL", "English", "Nederlands", ".", "“", "”", "$", "#", "!",
    "BugOS for Nvidia", "Download (.iso)", "BugOS Switch (.zip)", "distrobox enter dev", "code BugOS",
    "git clone https://github.com/253UgurSahin/BugOS", "0 trackers", "trackers", "accounts", "bug", "Computer",
    "computer", "Privacy", "Download (.iso)", "Download BugOS", "BugOS 2026.11.01", "BugOS 2026.11.02",
}


def instellingen() -> dict:
    cfg = json.loads((HIER / "site.json").read_text(encoding="utf-8"))
    url = cfg.get("url", "").strip()
    if url and not url.endswith("/"):
        url += "/"
    pad = cfg.get("pad", "/").strip() or "/"
    pad = "/" + pad.strip("/") + "/" if pad != "/" else "/"
    return {"url": url, "pad": pad, "https": bool(cfg.get("https")), "versie": str(cfg["versie"]),
            "sourceforge": cfg.get("sourceforge", "").strip()}


def downloads(cfg: dict) -> dict[str, str]:
    """De downloadknoppen: rechtstreeks naar de hele ISO op SourceForge (iso.yml zet hem daar onder een vaste
    naam), of, zonder SourceForge-project, naar de releasepagina op GitHub."""
    sf = cfg["sourceforge"]
    if not sf:
        rel = "https://github.com/253UgurSahin/BugOS/releases"
        return {"ISO_BUGOS": rel, "ISO_NVIDIA": rel, "SHA_BUGOS": rel, "SHA_NVIDIA": rel}
    assert re.fullmatch(r"[a-z0-9-]+", sf), "sourceforge in site.json: alleen kleine letters, cijfers en -"
    basis = f"https://sourceforge.net/projects/{sf}/files"
    return {"ISO_BUGOS": f"{basis}/bugos/BugOS.iso/download",
            "ISO_NVIDIA": f"{basis}/bugos-nvidia/BugOS-Nvidia.iso/download",
            "SHA_BUGOS": f"{basis}/bugos/BugOS.iso.sha256/download",
            "SHA_NVIDIA": f"{basis}/bugos-nvidia/BugOS-Nvidia.iso.sha256/download"}


class Teksten(HTMLParser):
    """Alle zichtbare tekst en alle teksten in alt, aria-label, title en data-*-teksten van een pagina."""
    ATTR = ("alt", "aria-label", "title", "content", "data-goed", "data-kapot", "data-gisteren",
            "data-opnieuw", "data-klaar")

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.teksten: list[str] = []
        self._in = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "code"):
            self._in += 1
        for k, v in attrs:
            if not v or k not in self.ATTR:
                continue
            if tag == "meta" and k == "content" and dict(attrs).get("name", dict(attrs).get("property")) not in (
                    "description", "og:title", "og:description"):
                continue
            self.teksten.append(v.strip())

    def handle_endtag(self, tag):
        if tag in ("script", "style", "code"):
            self._in -= 1

    def handle_data(self, data):
        if not self._in and data.strip() and not data.strip().startswith("{{"):
            self.teksten.append(" ".join(data.split()))


def teksten(pagina: str) -> list[str]:
    t = Teksten()
    t.feed(pagina)
    return t.teksten


def vertaal(pagina: str, taal: str) -> str:
    """Vervang elk Engels stuk door de vertaling uit <taal>.json. Elk stuk moet precies zo in de
    pagina staan, anders stopt de bouw (dan is de Engelse tekst veranderd en moet de vertaling mee)."""
    versie = instellingen()["versie"]
    paren = json.loads((HIER / f"{taal}.json").read_text(encoding="utf-8"))["vertalingen"]
    paren = sorted(((en.replace("{v}", versie), nl.replace("{v}", versie)) for en, nl in paren),
                   key=lambda p: -len(p[0]))  # langste eerst, zodat een kort stuk nooit in een langer zit
    ontbreekt = []
    for en, vertaald in paren:
        if en not in pagina:
            ontbreekt.append(en)
            continue
        pagina = pagina.replace(en, vertaald)
    if ontbreekt:
        sys.exit(f"{taal}.json: deze Engelse stukken staan niet (meer) in de pagina:\n  - " + "\n  - ".join(ontbreekt))
    return pagina


def controleer_vertaling(engels: str, vertaald: str, taal: str) -> None:
    """Geen enkele Engelse zin mag onvertaald blijven staan (behalve namen en getallen)."""
    en = set(teksten(engels))
    over = sorted(t for t in teksten(vertaald) if t in en and t not in ZELFDE and re.search(r"[A-Za-z]{2}", t))
    if over:
        sys.exit(f"{taal}.json: nog niet vertaald:\n  - " + "\n  - ".join(over))


def pagina_voor(sjabloon: str, taal: tuple, cfg: dict) -> str:
    code, bestand, adres, naam, kort, locale = taal
    ander = TALEN[1] if code == "en" else TALEN[0]
    rel = lambda t: t[2] or "./"  # noqa: E731  (adres in dezelfde map; "./" is de Engelse hoofdpagina)
    alternatieven = []
    if cfg["url"]:
        alternatieven.append(f'<link rel="canonical" href="{cfg["url"]}{adres}">')
        alternatieven.append(f'<meta property="og:url" content="{cfg["url"]}{adres}">')
    for t in TALEN:
        alternatieven.append(f'<link rel="alternate" hreflang="{t[0]}" href="{cfg["url"]}{t[2] if cfg["url"] else rel(t)}">')
    alternatieven.append(f'<link rel="alternate" hreflang="x-default" href="{cfg["url"] or "./"}">')
    talen = " · ".join(
        f'<span aria-current="page">{t[3]}</span>' if t[0] == code
        else f'<a href="{rel(t)}" hreflang="{t[0]}" lang="{t[0]}">{t[3]}</a>' for t in TALEN)
    hoofd, _, staart = cfg["versie"].partition(".")
    vul = {
        "TAAL": code, "OG_LOCALE": locale, "URL": cfg["url"], "ALTERNATIEVEN": "\n".join(alternatieven),
        "ANDER_PAD": rel(ander), "ANDER_TAAL": ander[0], "ANDER_NAAM": ander[3], "ANDER_KORT": ander[4],
        "TALEN": talen, "VERSIE": cfg["versie"], "VERSIE_KOP": hoofd, "VERSIE_STAART": staart,
        **downloads(cfg),
    }
    return re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: vul[m.group(1)] if m.group(1) in vul else m.group(0), sjabloon)


def htaccess(cfg: dict) -> str:
    if cfg["https"]:
        https = ("  # Always https (the second line keeps hosts behind a proxy from looping)\n"
                 "  RewriteCond %{HTTPS} off\n"
                 "  RewriteCond %{HTTP:X-Forwarded-Proto} !https\n"
                 "  RewriteRule ^ https://%{HTTP_HOST}%{REQUEST_URI} [R=301,L]")
        hsts = '  Header always set Strict-Transport-Security "max-age=31536000" env=HTTPS'
    else:
        https = "  # https: set \"https\": true in tools/website/site.json once your host has a certificate"
        hsts = "  # Strict-Transport-Security: comes with \"https\": true in tools/website/site.json"
    t = (HIER / "htaccess").read_text(encoding="utf-8")
    return t.replace("{{PAD}}", cfg["pad"]).replace("{{HTTPS}}", https).replace("{{HSTS}}", hsts)


def extra_bestanden(cfg: dict) -> dict[str, str]:
    uit = {".htaccess": htaccess(cfg)}
    vier = (HIER / "404.html").read_text(encoding="utf-8")
    uit["404.html"] = vier.replace("{{MERK}}", merk_variabel("niet")).replace("{{PAD}}", cfg["pad"])
    robots = "User-agent: *\nAllow: /\n"
    if cfg["url"]:
        robots += f"\nSitemap: {cfg['url']}sitemap.xml\n"
        regels = []
        for t in TALEN:
            alt = "".join(f'\n    <xhtml:link rel="alternate" hreflang="{a[0]}" href="{cfg["url"]}{a[2]}"/>' for a in TALEN)
            regels.append(f"  <url>\n    <loc>{cfg['url']}{t[2]}</loc>{alt}\n  </url>")
        uit["sitemap.xml"] = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
                              'xmlns:xhtml="http://www.w3.org/1999/xhtml">\n' + "\n".join(regels) + "\n</urlset>\n")
    uit["robots.txt"] = robots
    uit["site.webmanifest"] = json.dumps({
        "name": "BugOS", "short_name": "BugOS",
        "description": "The computer that just works. Free, can't break and collects nothing about you.",
        "start_url": "./", "scope": "./", "display": "browser", "lang": "en",
        "background_color": "#050506", "theme_color": "#050506",
        "icons": [{"src": "favicon.svg", "sizes": "any", "type": "image/svg+xml"},
                  {"src": "apple-touch-icon.png", "sizes": "180x180", "type": "image/png"}],
    }, indent=2, ensure_ascii=False) + "\n"
    return uit


def main() -> int:
    cfg = instellingen()
    bron = (HIER / "page.html").read_text(encoding="utf-8")
    bron = re.sub(r"\{\{MERK:([a-z]+)\}\}", lambda m: merk_svg(m.group(1)), bron)
    bron = bron.replace("{{OPBOUW}}", opbouw())
    site = ROOT / "website"
    engels = ""
    for taal in TALEN:
        uit = pagina_voor(bron, taal, cfg)
        if taal[0] == "en":
            engels = uit
        else:
            uit = vertaal(uit, taal[0])
            controleer_vertaling(engels, uit, taal[0])
        uit = uit.replace("{{CSP}}", csp(uit))
        assert "{{" not in uit, f"er staat nog een lege plek in {taal[1]}"
        (site / taal[1]).write_text(uit, encoding="utf-8")
        print(f"website/{taal[1]} gebouwd")
    for naam, inhoud in extra_bestanden(cfg).items():
        (site / naam).write_text(inhoud, encoding="utf-8")
        print(f"website/{naam} gebouwd")
    if not cfg["url"]:
        stale = site / "sitemap.xml"
        if stale.exists():
            stale.unlink()
    return 0


if __name__ == "__main__":
    sys.exit(main())
