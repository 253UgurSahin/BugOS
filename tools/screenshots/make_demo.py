#!/usr/bin/env python3
"""Maak voorbeeldbestanden voor de foto's van de verkenner (tools/screenshots/demo/).

Echte, kleine documenten met een voorbeeldplaatje erin, zodat de verkenner
laat zien hoe je bestanden er in BugOS uitzien. Gebruik:
    python3 tools/screenshots/make_demo.py
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
    odf("Bugie's recipes.odt", "text", pagina("Bugie's apple pie", [
        "For a 24 cm pie", "", "300 g self-raising flour", "200 g butter",
        "150 g sugar", "1 egg", "1.5 kg apples", "Cinnamon and raisins", "",
        "  Preheat the oven to 175 degrees.", "  Bake for about an hour."]), "Bugie's apple pie")
    odf("Shopping list.odt", "text", pagina("Shopping", [
        "[x]  Bread", "[x]  Milk", "[  ]  Cheese", "[  ]  Apples", "[  ]  Coffee",
        "[  ]  Flowers for Sanne"]), "Shopping")
    odf("Birthdays.ods", "spreadsheet", pagina("Birthdays", [
        "Sanne|14 March", "Daan|2 June", "Uncle Henk|19 August", "Aunt Ria|3 October",
        "Bugie|11 December"], tabel=True), "Birthdays")
    brief = pagina("Town council", ["To: R. de Vries", "Subject: your application", "",
                                    "Dear R. de Vries,", "", "  This letter confirms",
                                    "  your application for a new", "  parking permit.", "",
                                    "Kind regards,", "Citizen Services"])
    brief.save(UIT / "Letter from the council.pdf", "PDF", resolution=72)
    print("demo-bestanden gemaakt in", UIT)


if __name__ == "__main__":
    main()
