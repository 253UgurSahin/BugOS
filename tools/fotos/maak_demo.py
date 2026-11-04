#!/usr/bin/env python3
"""Maak voorbeeldbestanden voor de foto's van de verkenner (tools/fotos/demo/).

Echte, kleine documenten met een voorbeeldplaatje erin, zodat de verkenner
laat zien hoe je bestanden er in BugOS uitzien. Gebruik:
    python3 tools/fotos/maak_demo.py
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HIER = Path(__file__).resolve().parent
UIT = HIER / "demo"
LETTER = HIER.parent.parent / "system_files" / "usr" / "share" / "fonts" / "bugos" / "InterVariable.ttf"
INKT, GRIJS, ROOD = (22, 23, 28), (120, 124, 134), (222, 47, 62)


def letter(px: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(LETTER), px)


def pagina(titel: str, regels: list[str], b: int = 420, h: int = 594, tabel: bool = False) -> Image.Image:
    """Een A4-pagina als plaatje (voor het voorbeeld in de verkenner)."""
    im = Image.new("RGB", (b, h), "white")
    d = ImageDraw.Draw(im)
    d.text((40, 44), titel, font=letter(26), fill=INKT)
    d.rectangle((40, 86, 92, 90), fill=ROOD)
    y = 116
    if tabel:
        for i, r in enumerate(regels):
            kleur = (246, 245, 245) if i % 2 == 0 else (255, 255, 255)
            d.rectangle((40, y - 6, b - 40, y + 22), fill=kleur)
            naam, datum = r.split("|")
            d.text((50, y), naam, font=letter(15), fill=INKT)
            d.text((b - 140, y), datum, font=letter(15), fill=GRIJS)
            y += 30
    else:
        for r in regels:
            d.text((40, y), r, font=letter(15), fill=INKT if not r.startswith("  ") else GRIJS)
            y += 28
    return im


def odf(naam: str, soort: str, plaatje: Image.Image, tekst: str) -> None:
    """Een klein, geldig OpenDocument-bestand met een voorbeeldplaatje erin."""
    mime = {"text": "application/vnd.oasis.opendocument.text",
            "spreadsheet": "application/vnd.oasis.opendocument.spreadsheet"}[soort]
    duim = plaatje.copy()
    duim.thumbnail((181, 256))
    png = io.BytesIO()
    duim.save(png, "PNG")
    if soort == "text":
        lichaam = f"<office:text><text:p>{tekst}</text:p></office:text>"
    else:
        lichaam = ("<office:spreadsheet><table:table table:name=\"Blad1\"><table:table-row><table:table-cell>"
                   f"<text:p>{tekst}</text:p></table:table-cell></table:table-row></table:table></office:spreadsheet>")
    content = ('<?xml version="1.0" encoding="UTF-8"?>'
               '<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" '
               'xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" '
               'xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" office:version="1.3">'
               f"<office:body>{lichaam}</office:body></office:document-content>")
    manifest = ('<?xml version="1.0" encoding="UTF-8"?>'
                '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.3">'
                f'<manifest:file-entry manifest:full-path="/" manifest:media-type="{mime}"/>'
                '<manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>'
                '<manifest:file-entry manifest:full-path="Thumbnails/thumbnail.png" manifest:media-type="image/png"/>'
                "</manifest:manifest>")
    with zipfile.ZipFile(UIT / naam, "w") as z:
        z.writestr(zipfile.ZipInfo("mimetype"), mime, compress_type=zipfile.ZIP_STORED)
        z.writestr("content.xml", content, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("META-INF/manifest.xml", manifest, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr("Thumbnails/thumbnail.png", png.getvalue(), compress_type=zipfile.ZIP_DEFLATED)


def main() -> None:
    UIT.mkdir(exist_ok=True)
    odf("Recepten Bugie.odt", "text", pagina("Appeltaart van Bugie", [
        "Voor een taart van 24 cm", "", "300 gram zelfrijzend bakmeel", "200 gram roomboter",
        "150 gram suiker", "1 ei", "1,5 kilo appels (goudrenet)", "Kaneel en rozijnen", "",
        "  Oven voorverwarmen op 175 graden.", "  Bakken in ongeveer een uur."]), "Appeltaart van Bugie")
    odf("Boodschappenlijst.odt", "text", pagina("Boodschappen", [
        "[x]  Brood", "[x]  Melk", "[  ]  Kaas", "[  ]  Appels (goudrenet)", "[  ]  Koffie",
        "[  ]  Bloemen voor Sanne"]), "Boodschappen")
    odf("Verjaardagen.ods", "spreadsheet", pagina("Verjaardagen", [
        "Sanne|14 maart", "Daan|2 juni", "Opa Henk|19 augustus", "Tante Ria|3 oktober",
        "Bugie|11 december"], tabel=True), "Verjaardagen")
    brief = pagina("Gemeente", ["Aan: mevrouw R. de Vries", "Betreft: uw aanvraag", "",
                                "Geachte mevrouw De Vries,", "", "  Hierbij ontvangt u de bevestiging",
                                "  van uw aanvraag voor een nieuwe", "  parkeervergunning.", "",
                                "Met vriendelijke groet,", "Team Burgerzaken"])
    brief.save(UIT / "Brief gemeente.pdf", "PDF", resolution=72)
    print("demo-bestanden gemaakt in", UIT)


if __name__ == "__main__":
    main()
