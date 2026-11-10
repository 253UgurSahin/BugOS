"""Bestandssoorten: welke familie (kleur, tekentje) en welk labeltje elke naam krijgt (voor places.py)."""

from __future__ import annotations

import ast
import re

from tokens import SYSTEM, TINTEN


# ---------------------------------------------------------------- bestandssoorten ---

def _soorten_uit_bestanden() -> dict[str, tuple[str, str]]:
    """SOORTEN uit Bestanden (extensie -> (kleur, tekentje)), zodat Dolphin en Bestanden gelijk blijven."""
    bron = SYSTEM / "usr" / "lib" / "bugos" / "python" / "bugos_files_plekken.py"
    try:
        boom = ast.parse(bron.read_text(encoding="utf-8"))
        for knoop in boom.body:
            if isinstance(knoop, ast.Assign) and any(isinstance(d, ast.Name) and d.id == "SOORTEN"
                                                     for d in knoop.targets):
                return ast.literal_eval(knoop.value)
    except (OSError, SyntaxError, ValueError):
        pass
    return {}


SOORTEN = _soorten_uit_bestanden()


def _soort(ext: str, kleur: str, teken: str) -> tuple[str, str]:
    return SOORTEN.get(ext, (kleur, teken))


# familie -> (kleur, tekentje). Tekentje: 'tekst' en 'tabel' zijn regeltjes, de rest een lijnicoon.
# 'doos' tekent Bestanden als de mapomtrek ('map'); dat doen we hier ook.
FAMILIES = {
    "pdf": _soort("pdf", "#D3263A", "tekst"),
    "doc": _soort("docx", TINTEN["blauw"], "tekst"),
    "sheet": _soort("xlsx", TINTEN["groen"], "tabel"),
    "slides": _soort("pptx", TINTEN["oranje"], "tekst"),
    "txt": _soort("txt", TINTEN["grijs"], "tekst"),
    "archive": _soort("zip", TINTEN["grijs"], "doos"),
    "exe": _soort("exe", TINTEN["paars"], "doos"),
    "audio": _soort("mp3", TINTEN["roze"], "muziek"),
    "video": _soort("mp4", TINTEN["turkoois"], "film"),
    "image": (TINTEN["geel"], "foto"),
    "code": (TINTEN["grijs"], "code"),
    "web": (TINTEN["blauw"], "wereld"),
    "key": (TINTEN["grijs"], "slot"),
    "font": (TINTEN["grijs"], "letter"),
    "mail": (TINTEN["blauw"], "envelop"),
    "contact": (TINTEN["blauw"], "persoon"),
    "calendar": (TINTEN["oranje"], "kalender"),
    "db": (TINTEN["grijs"], "opslag"),
    "torrent": (TINTEN["grijs"], "download"),
    "game": (TINTEN["paars"], "spel"),
    "unknown": ("#8A8F9A", "tekst"),   # zoals Bestanden een onbekend bestand tekent
}


# Namen met een eigen labeltje: naam -> (familie, label).
LABELS = {
    "application-pdf": ("pdf", "PDF"), "application-postscript": ("pdf", "PS"), "viewpdf": ("pdf", "PDF"),
    "viewps": ("pdf", "PS"), "application-x-gzpostscript": ("pdf", "PS"), "viewdvi": ("pdf", "DVI"),
    "application-x-bzdvi": ("pdf", "DVI"), "application-x-gzdvi": ("pdf", "DVI"), "image-vnd.djvu": ("pdf", "DJVU"),
    "application-x-chm": ("pdf", "CHM"),
    "application-msword": ("doc", "DOC"), "application-vnd.ms-word": ("doc", "DOC"),
    "application-vnd.openxmlformats-officedocument.wordprocessingml.document": ("doc", "DOCX"),
    "application-vnd.oasis.opendocument.text": ("doc", "ODT"), "application-rtf": ("doc", "RTF"),
    "text-rtf": ("doc", "RTF"), "application-epub+zip": ("doc", "EPUB"), "x-office-document": ("doc", None),
    "application-vnd.ms-excel": ("sheet", "XLS"),
    "application-vnd.openxmlformats-officedocument.spreadsheetml.sheet": ("sheet", "XLSX"),
    "application-vnd.oasis.opendocument.spreadsheet": ("sheet", "ODS"), "text-csv": ("sheet", "CSV"),
    "x-office-spreadsheet": ("sheet", None),
    "application-vnd.ms-powerpoint": ("slides", "PPT"),
    "application-vnd.openxmlformats-officedocument.presentationml.presentation": ("slides", "PPTX"),
    "application-vnd.oasis.opendocument.presentation": ("slides", "ODP"), "x-office-presentation": ("slides", None),
    "text-plain": ("txt", "TXT"), "text-x-generic": ("txt", None), "text-markdown": ("txt", "MD"),
    "text-x-markdown": ("txt", "MD"), "text-x-log": ("txt", "LOG"),
    "application-zip": ("archive", "ZIP"), "application-x-7z-compressed": ("archive", "7Z"),
    "application-x-rar": ("archive", "RAR"), "application-vnd.rar": ("archive", "RAR"),
    "application-x-tar": ("archive", "TAR"), "application-x-compressed-tar": ("archive", "GZ"),
    "application-gzip": ("archive", "GZ"), "application-x-gzip": ("archive", "GZ"),
    "application-x-bzip-compressed-tar": ("archive", "BZ"), "application-x-bzip": ("archive", "BZ"),
    "application-x-xz-compressed-tar": ("archive", "XZ"), "application-x-xz": ("archive", "XZ"),
    "application-zstd": ("archive", "ZST"), "application-x-zstd-compressed-tar": ("archive", "ZST"),
    "application-x-cd-image": ("archive", "ISO"), "application-x-iso": ("archive", "ISO"),
    "application-vnd.efi.iso": ("archive", "ISO"), "application-x-compressed-iso": ("archive", "ISO"),
    "package-x-generic": ("archive", None),
    "application-x-ms-dos-executable": ("exe", "EXE"), "application-x-msdownload": ("exe", "EXE"),
    "application-x-msi": ("exe", "MSI"), "application-x-executable": ("exe", None),
    "application-x-rpm": ("exe", "RPM"), "application-x-source-rpm": ("exe", "RPM"),
    "application-x-deb": ("exe", "DEB"), "application-vnd.debian.binary-package": ("exe", "DEB"),
    "application-vnd.appimage": ("exe", "APP"), "application-x-iso9660-appimage": ("exe", "APP"),
    "application-vnd.flatpak.ref": ("exe", "APP"), "application-vnd.flatpak": ("exe", "APP"),
    "application-vnd.flatpak.repo": ("exe", None), "application-vnd.android.package-archive": ("exe", "APK"),
    "android-package-archive": ("exe", "APK"),
    "audio-mpeg": ("audio", "MP3"), "audio-mp3": ("audio", "MP3"), "audio-x-mpeg": ("audio", "MP3"),
    "audio-flac": ("audio", "FLAC"), "audio-x-flac": ("audio", "FLAC"), "audio-ogg": ("audio", "OGG"),
    "audio-x-vorbis+ogg": ("audio", "OGG"), "audio-x-wav": ("audio", "WAV"), "audio-vnd.wave": ("audio", "WAV"),
    "audio-mp4": ("audio", "M4A"), "audio-x-m4a": ("audio", "M4A"), "audio-x-opus+ogg": ("audio", "OPUS"),
    "audio-x-generic": ("audio", None),
    "video-mp4": ("video", "MP4"), "video-x-matroska": ("video", "MKV"), "video-webm": ("video", "WEBM"),
    "video-x-msvideo": ("video", "AVI"), "video-quicktime": ("video", "MOV"), "video-x-generic": ("video", None),
    "image-png": ("image", "PNG"), "image-jpeg": ("image", "JPG"), "image-gif": ("image", "GIF"),
    "image-svg+xml": ("image", "SVG"), "image-svg+xml-compressed": ("image", "SVG"), "image-webp": ("image", "WEBP"),
    "image-bmp": ("image", "BMP"), "image-tiff": ("image", "TIF"), "image-heif": ("image", "HEIC"),
    "image-avif": ("image", "AVIF"), "image-x-xcf": ("image", "XCF"), "image-vnd.microsoft.icon": ("image", "ICO"),
    "image-x-icon": ("image", "ICO"), "image-x-generic": ("image", None),
    "text-html": ("web", "HTML"), "application-xhtml+xml": ("web", "HTML"),
    "text-css": ("code", "CSS"), "text-javascript": ("code", "JS"), "application-javascript": ("code", "JS"),
    "application-x-javascript": ("code", "JS"), "text-x-javascript": ("code", "JS"), "application-json": ("code", "JSON"),
    "application-xml": ("code", "XML"), "text-xml": ("code", "XML"), "text-x-python": ("code", "PY"),
    "text-x-python3": ("code", "PY"), "application-x-shellscript": ("code", "SH"), "text-x-shellscript": ("code", "SH"),
    "text-x-script": ("code", None), "text-x-csrc": ("code", "C"), "text-x-chdr": ("code", "H"),
    "text-x-c++src": ("code", "CPP"), "text-x-java": ("code", "JAVA"), "text-x-go": ("code", "GO"),
    "text-rust": ("code", "RS"), "text-x-rust": ("code", "RS"), "application-sql": ("code", "SQL"),
    "text-x-sql": ("code", "SQL"), "application-toml": ("code", "TOML"),
    "font-ttf": ("font", "TTF"), "application-x-font-ttf": ("font", "TTF"), "font-otf": ("font", "OTF"),
    "application-x-font-otf": ("font", "OTF"),
    "text-calendar": ("calendar", "ICS"), "text-vcalendar": ("calendar", "ICS"), "text-x-vcard": ("contact", "VCF"),
    "text-directory": ("contact", "VCF"),
    "unknown": ("unknown", None), "application-octet-stream": ("unknown", None),
    # Office-bestanden die mensen van Windows meenemen
    "application-msonenote": ("doc", "ONE"), "application-vnd.ms-publisher": ("doc", "PUB"),
    "vnd.ms-publisher": ("doc", "PUB"), "application-vnd.ms-infopath": ("doc", None),
    "application-msoutlook": ("mail", None), "application-vnd.google-earth.kml+xml": ("web", "KML"),
}


# Alle andere bestandssoorten die Breeze kent: die krijgen ook het BugOS-papiertje (anders
# kiest KDE de Breeze-versie). Ingedeeld met de regels in _familie().
BREEZE_SOORTEN = """
    android-package-archive application-atom+xml application-certificate application-dicom application-epub+zip
    application-gzip application-illustrator application-javascript application-json application-mathml+xml
    application-msword application-msword-template application-octet-stream application-ogg application-pdf
    application-pgp application-pgp-encrypted application-pgp-keys application-pgp-signature application-pkcs12
    application-pkcs7-mime application-pkcs7-signature application-pkix-cerl application-pkix-cert application-postscript
    application-relaxng application-rss+xml application-rtf application-sql application-sxw
    application-toml application-vnd.android.app-bundle application-vnd.android.package-archive application-vnd.appimage
    application-vnd.debian.binary-package application-vnd.efi.iso application-vnd.flatpak.ref application-vnd.iccprofile
    application-vnd.kde.kleopatra.keygroup application-vnd.ms-access application-vnd.ms-excel
    application-vnd.ms-excel.addin.macroenabled.12 application-vnd.ms-excel.sheet.binary.macroenabled.12
    application-vnd.ms-excel.sheet.macroenabled.12 application-vnd.ms-excel.template.macroenabled.12
    application-vnd.ms-powerpoint application-vnd.ms-powerpoint.addin.macroenabled.12
    application-vnd.ms-powerpoint.presentation.macroenabled.12 application-vnd.ms-powerpoint.slide.macroenabled.12
    application-vnd.ms-powerpoint.slideshow.macroenabled.12 application-vnd.ms-powerpoint.template.macroenabled.12
    application-vnd.ms-word application-vnd.ms-word.document.macroenabled.12 application-vnd.ms-word.template.macroenabled.12
    application-vnd.oasis.opendocument.chart application-vnd.oasis.opendocument.database
    application-vnd.oasis.opendocument.draw.template application-vnd.oasis.opendocument.drawing
    application-vnd.oasis.opendocument.drawing.template application-vnd.oasis.opendocument.formula
    application-vnd.oasis.opendocument.formula-template application-vnd.oasis.opendocument.graphics
    application-vnd.oasis.opendocument.image application-vnd.oasis.opendocument.presentation
    application-vnd.oasis.opendocument.presentation-template application-vnd.oasis.opendocument.spreadsheet
    application-vnd.oasis.opendocument.spreadsheet-template application-vnd.oasis.opendocument.text
    application-vnd.oasis.opendocument.text-master application-vnd.oasis.opendocument.text-template
    application-vnd.oasis.opendocument.web-template application-vnd.openofficeorg.extension
    application-vnd.openxmlformats-officedocument.spreadsheetml.sheet
    application-vnd.openxmlformats-officedocument.wordprocessingml.document application-vnd.rar
    application-vnd.rn-realmedia application-vnd.scribus application-vnd.snap application-vnd.sqlite3
    application-vnd.squashfs application-vnd.stardivision.calc application-vnd.stardivision.draw
    application-vnd.stardivision.mail application-vnd.stardivision.math application-vnd.sun.xml.calc
    application-vnd.sun.xml.calc.template application-vnd.sun.xml.draw application-vnd.sun.xml.draw.template
    application-vnd.sun.xml.impress application-vnd.sun.xml.impress.template application-vnd.sun.xml.math
    application-vnd.sun.xml.writer application-vnd.sun.xml.writer.global application-vnd.sun.xml.writer.template
    application-vnd.visio application-vnd.wordperfect application-wps-office.doc application-wps-office.docx
    application-wps-office.dot application-wps-office.dotx application-wps-office.pot application-wps-office.potx
    application-wps-office.ppt application-wps-office.pptx application-wps-office.xls application-wps-office.xlsx
    application-wps-office.xlt application-wps-office.xltx application-x-7z-compressed application-x-abiword
    application-x-ace application-x-apple-diskimage application-x-applix-spreadsheet application-x-applix-word
    application-x-ar application-x-arc application-x-archive application-x-arj application-x-audacity-project
    application-x-awk application-x-bittorrent application-x-blender application-x-bzdvi
    application-x-bzip application-x-bzip-compressed-tar application-x-cd-image application-x-cda application-x-chm
    application-x-compress application-x-compressed-iso application-x-compressed-tar application-x-core application-x-cpio
    application-x-cue application-x-deb application-x-designer application-x-desktop application-x-executable
    application-x-executable-script application-x-fictionbook+xml application-x-flash-video application-x-font-afm
    application-x-font-bdf application-x-font-otf application-x-font-pcf application-x-font-snf application-x-font-ttf
    application-x-font-ttx application-x-font-type1 application-x-gdscript application-x-gettext-translation
    application-x-gnumeric application-x-gzdvi application-x-gzip application-x-gzpostscript application-x-iso
    application-x-iso9660-appimage application-x-jar application-x-java application-x-java-applet
    application-x-java-archive application-x-javascript application-x-kdenlive application-x-kdenlivetitle
    application-x-kmymoney application-x-krita application-x-kword application-x-lha application-x-lzma-compressed-tar
    application-x-lzop application-x-m4 application-x-mimearchive application-x-mplayer2 application-x-ms-dos-executable
    application-x-ms-shortcut application-x-ms-wim application-x-msdownload application-x-mswinurl application-x-mswrite
    application-x-object application-x-openvpn-profile application-x-cisco-vpn-settings application-x-pak
    application-x-partial-download application-x-pem-key application-x-perl application-x-php application-x-pkcs12
    application-x-pkcs7-certificates application-x-plasma application-x-python-bytecode application-x-qemu-disk
    application-x-quattropro application-x-rar application-x-raw-disk-image application-x-rpm application-x-ruby
    application-x-sami application-x-sharedlib application-x-shellscript application-x-shockwave-flash application-x-siag
    application-x-source-rpm application-x-sqlite2 application-x-sqlite3 application-x-srt application-x-subrip
    application-x-tar application-x-tarz application-x-theme application-x-trash application-x-troff-man
    application-x-tzo application-x-vdi-disk application-x-wmf application-x-x509-ca-cert application-x-x509-user-cert
    application-x-xliff application-x-xpinstall application-x-xz-compressed-tar application-x-xz-pkg application-x-zerosize
    application-x-zip-compressed-fb2 application-x-zoo application-xhtml+xml application-xml application-xsd
    application-xslt+xml application-zip audio-ac3 audio-flac audio-midi audio-mp2 audio-mp3 audio-mp4 audio-mpeg
    audio-ogg audio-prs.sid audio-vn.rn-realmedia audio-vnd.rn-realvideo audio-vnd.wave audio-x-adpcm audio-x-aiff
    audio-x-flac audio-x-flac+ogg audio-x-generic audio-x-monkey audio-x-mp2 audio-x-mpeg audio-x-speex+ogg
    audio-x-vorbis+ogg audio-x-wav audiobook encrypted font-otf font-ttf fonts-package image-bmp image-gif image-ico
    image-jpeg image-jpeg2000 image-png image-svg+xml image-svg+xml-compressed image-tiff image-vnd.dgn image-vnd.djvu
    image-vnd.dwg image-vnd.microsoft.icon image-x-adobe-dng image-x-compressed-xcf image-x-emf image-x-eps
    image-x-generic image-x-ico image-x-icon image-x-krita image-x-portable-bitmap image-x-psd image-x-svg+xml
    image-x-tga image-x-vnd.trolltech.qpicture image-x-win-bitmap image-x-win-bmp image-x-wmf image-x-xcf image-x-xfig
    libreoffice-database libreoffice-drawing libreoffice-drawing-template libreoffice-extension libreoffice-formula
    libreoffice-master-document libreoffice-oasis-database libreoffice-oasis-drawing libreoffice-oasis-drawing-template
    libreoffice-oasis-formula libreoffice-oasis-master-document libreoffice-oasis-presentation
    libreoffice-oasis-presentation-template libreoffice-oasis-spreadsheet libreoffice-oasis-spreadsheet-template
    libreoffice-oasis-text libreoffice-oasis-text-template libreoffice-oasis-web-template libreoffice-presentation
    libreoffice-presentation-template libreoffice-spreadsheet libreoffice-spreadsheet-template libreoffice-text
    libreoffice-text-template message message-news message-partial message-rfc822 message-x-gnu-rmail odf
    package-x-generic podcast text-calendar text-csharp text-css text-csv text-directory text-dockerfile text-enriched
    text-html text-javascript text-markdown text-plain text-rdf text-rdf+xml text-rtf text-rust text-sgml text-troff
    text-vcalendar text-vnd.abc text-vnd.trolltech.linguist text-vnd.typst text-vnd.wap.wml text-vtt text-wiki
    text-x-adasrc text-x-authors text-x-bibtex text-x-c++hdr text-x-c++src text-x-changelog text-x-chdr text-x-cmake
    text-x-copying text-x-credits text-x-csharp text-x-csrc text-x-dtd text-x-generic text-x-gettext-translation
    text-x-go text-x-haskell text-x-hex text-x-install text-x-java text-x-java-source text-x-javascript
    text-x-katefilelist text-x-kotlin text-x-ldif text-x-lilypond text-x-log text-x-lua text-x-makefile text-x-markdown
    text-x-microdvd text-x-mpsub text-x-nfo text-x-nim text-x-objchdr text-x-objcsrc text-x-opml text-x-opml+xml
    text-x-pascal text-x-patch text-x-plain text-x-po text-x-python text-x-python2 text-x-python3 text-x-qml text-x-r
    text-x-readme text-x-rpm-spec text-x-rust text-x-sass text-x-scala text-x-script text-x-scss text-x-shellscript
    text-x-sql text-x-ssa text-x-subviewer text-x-tcl text-x-tex text-x-texinfo text-x-vcard text-x-xslfo text-xml
    unknown video-mlt-playlist video-mp2t video-mp4 video-vnd.rn-realvideo video-webm video-x-anim video-x-flic
    video-x-flv video-x-generic video-x-matroska video-x-mng video-x-ms-wmp video-x-ms-wmv video-x-msvideo
    video-x-ogm+ogg video-x-theora+ogg video-x-wmv viewbib viewdvi viewhtml viewpdf viewps virtualbox-hdd virtualbox-ova
    virtualbox-ovf virtualbox-vbox virtualbox-vbox-extpack virtualbox-vdi virtualbox-vhd virtualbox-vmdk
    x-mail-distribution-list x-media-podcast x-office-address-book x-office-calendar x-office-contact x-office-document
    x-office-drawing x-office-presentation x-office-spreadsheet
""".split() + """
    apple-vnd.apple.pkpasses application-mac-binhex40 application-msonenote application-msoutlook
    application-vnd.apple.pkpass application-vnd.apple.pkpasses application-vnd.google-earth.kml+xml
    application-vnd.ms-infopath application-vnd.ms-publisher application-vnd.nintendo.snes.rom
    application-vnd.nokia.xml.qt.resource application-x-egon application-x-gameboy-rom application-x-gamecube-rom
    application-x-gba-rom application-x-godot-project application-x-godot-resource application-x-godot-scene
    application-x-godot-shader application-x-it87 application-x-k3b application-x-kcsrc application-x-kexi-connectiondata
    application-x-kexiproject-shortcut application-x-kexiproject-sqlite application-x-kexiproject-sqlite2
    application-x-kexiproject-sqlite3 application-x-kformula application-x-kgetlist application-x-kontour
    application-x-kplato application-x-kvtml application-x-labplot2 application-x-lyx application-x-macbinary
    application-x-marble application-x-n64-rom application-x-nes-rom application-x-nintendo-ds-rom application-x-nzb
    application-x-qet-element application-x-qet-project application-x-rdata application-x-root application-x-sif
    application-x-skg application-x-skgc application-x-srtrip application-x-tgif application-xmind text-fortran
    text-vnd.kde.kcrash-report text-x-apport text-x-fortran text-xmcd uri-mms uri-mmst uri-pnm uri-rtspt uri-rtspu
    video-vivo video-wavelet video-x-google-vlc-plugin video-x-javafx vnd.ms-publisher x-kde-nsplugin-generated
""".split()   # de rest van Breeze (zonder de kapotte namen in Breeze zelf, zoals "none")


# (familie, regel) op volgorde: de eerste die past wint.
_REGELS = [
    ("pdf", r"^(viewpdf|viewps|viewdvi|application-x-(gz|bz)(dvi|postscript)|image-vnd\.djvu|application-x-chm)$"),
    ("game", r"(-rom$|\.rom$)"),
    ("db", r"kexi"),
    ("mail", r"msoutlook"),
    ("web", r"(google-earth|x-marble)"),
    ("torrent", r"(x-nzb$|kgetlist)"),
    ("archive", r"(binhex|macbinary)"),
    ("txt", r"(kcrash-report|x-apport$|^text-xmcd$)"),
    ("video", r"^uri-(mms|mmst|pnm|rtspt|rtspu)$"),
    ("code", r"(godot|qt\.resource|x-kcsrc$|fortran)"),
    ("doc", r"(msonenote|ms-publisher|ms-infopath|x-lyx$|kformula)"),
    ("txt", r"^(text-x-(plain|readme|authors|changelog|copying|credits|install|nfo|hex|bibtex|tex|texinfo|ssa|microdvd|"
            r"mpsub|subviewer|po|gettext-translation)|text-(enriched|troff|wiki|vtt)|viewbib|application-x-"
            r"(troff-man|subrip|srt|sami|gettext-translation|xliff))$"),
    ("doc", r"(msword|ms-word|wordprocessingml|opendocument\.(text|formula|web)|libreoffice(-oasis)?-(text|formula|"
            r"master-document|web)|sun\.xml\.(writer|math)|stardivision\.(mail|math)|wps-office\.do|x-abiword|x-kword|"
            r"wordperfect|x-mswrite|application-sxw|applix-word|fictionbook|fb2|^odf$)"),
    ("sheet", r"(ms-excel|spreadsheetml|opendocument\.(spreadsheet|chart)|libreoffice(-oasis)?-spreadsheet|"
              r"sun\.xml\.calc|stardivision\.calc|wps-office\.xl|x-gnumeric|applix-spreadsheet|quattropro|x-siag|"
              r"x-kmymoney)"),
    ("slides", r"(ms-powerpoint|presentationml|opendocument\.presentation|libreoffice(-oasis)?-presentation|"
               r"sun\.xml\.impress|wps-office\.p)"),
    ("db", r"(sqlite|opendocument\.database|libreoffice(-oasis)?-database|ms-access)"),
    ("image", r"^(image-|application-(vnd\.oasis\.opendocument\.(graphics|drawing|draw|image)|vnd\.sun\.xml\.draw|"
              r"vnd\.stardivision\.draw|illustrator|x-krita|vnd\.visio|dicom|vnd\.scribus|x-wmf|vnd\.iccprofile|"
              r"x-blender)|libreoffice(-oasis)?-drawing|x-office-drawing)"),
    ("audio", r"^(audio-|audiobook$|podcast$|x-media-podcast$|application-(ogg|x-audacity-project|x-cda))"),
    ("video", r"^(video-|application-(x-flash-video|x-shockwave-flash|vnd\.rn-realmedia|x-mplayer2|x-kdenlive))"),
    ("key", r"(pgp|pkcs|pkix|pem-key|x509|certificate|^encrypted$|openvpn|cisco-vpn|kleopatra)"),
    ("font", r"(^font-|x-font-|^fonts-package$)"),
    ("mail", r"(^message|mail-distribution)"),
    ("contact", r"(vcard|^text-directory$|x-office-contact|x-office-address-book|ldif)"),
    ("calendar", r"(calendar)"),
    ("torrent", r"(bittorrent|partial-download)"),
    ("exe", r"(rpm|debian|x-deb$|flatpak|vnd\.snap|appimage|android|xpinstall|x-plasma$|openofficeorg\.extension|"
            r"libreoffice-extension|executable|ms-dos|msdownload|x-msi$|sharedlib|x-object$|x-core$|ms-shortcut|"
            r"x-desktop$|java-applet|x-java$)"),
    ("archive", r"(zip|tar|rar|7z|gzip|bzip|x-xz|lzma|lzop|compress|x-ace$|x-ar$|x-arc$|archive|x-arj$|cpio|x-lha$|"
                r"x-zoo$|x-tzo$|squashfs|ms-wim|x-pak$|x-jar$|cd-image|x-iso$|\.iso$|diskimage|raw-disk|qemu-disk|vdi-disk|"
                r"virtualbox|x-cue$|x-theme$)"),
    ("web", r"^(viewhtml|application-x-mswinurl)$"),
    ("code", r"^(text-|application-(x-)?(javascript|json|xml|xsd|xslt|relaxng|toml|sql|atom|rss|mathml|php|ruby|perl|"
             r"awk|m4|gdscript|shellscript|executable-script|python-bytecode|designer|kdenlivetitle))"),
]


# Het labeltje van de andere soorten: de extensie uit shared-mime-info (de eerste *.ext van dat type,
# hoogstens 4 tekens), zoals Bestanden op elk bestand met een extensie het labeltje zet. Eenmalig
# uitgelezen in de testbank en hier vastgelegd, zodat maken op elk systeem hetzelfde oplevert.
# Algemene namen krijgen de bekendste extensie van hun familie: KDE vraagt bijv. voor een .docm
# "application-vnd.ms-word.document.macroEnabled.12" (met hoofdletters, die kan een pictogramnaam niet
# hebben) en valt dan terug op x-office-document.
EXTENSIES = dict(regel.split("=") for regel in """
    application-atom+xml=ATOM application-dicom=DCM application-illustrator=AI application-mac-binhex40=HQX
    application-mathml+xml=MML application-msword-template=DOT application-ogg=OGX application-pgp=PGP
    application-pgp-encrypted=PGP application-pgp-keys=KEY application-pgp-signature=ASC application-pkcs12=P12
    application-pkcs7-mime=P7C application-pkcs7-signature=P7S application-pkix-cert=CER application-relaxng=RNG
    application-rss+xml=RSS application-sxw=SXW application-vnd.iccprofile=ICC application-vnd.ms-access=MDB
    application-vnd.ms-excel.addin.macroenabled.12=XLAM application-vnd.ms-excel.sheet.binary.macroenabled.12=XLSB
    application-vnd.ms-excel.sheet.macroenabled.12=XLSM application-vnd.ms-excel.template.macroenabled.12=XLTM
    application-vnd.ms-powerpoint.addin.macroenabled.12=PPAM
    application-vnd.ms-powerpoint.presentation.macroenabled.12=PPTM
    application-vnd.ms-powerpoint.slide.macroenabled.12=SLDM
    application-vnd.ms-powerpoint.slideshow.macroenabled.12=PPSM
    application-vnd.ms-powerpoint.template.macroenabled.12=POTM
    application-vnd.ms-word.document.macroenabled.12=DOCM application-vnd.ms-word.template.macroenabled.12=DOTM
    application-vnd.nintendo.snes.rom=SFC application-vnd.oasis.opendocument.chart=ODC
    application-vnd.oasis.opendocument.database=ODB application-vnd.oasis.opendocument.formula=ODF
    application-vnd.oasis.opendocument.formula-template=OTF application-vnd.oasis.opendocument.graphics=ODG
    application-vnd.oasis.opendocument.image=ODI application-vnd.oasis.opendocument.presentation-template=OTP
    application-vnd.oasis.opendocument.spreadsheet-template=OTS application-vnd.oasis.opendocument.text-master=ODM
    application-vnd.oasis.opendocument.text-template=OTT application-vnd.oasis.opendocument.web-template=OTH
    application-vnd.openofficeorg.extension=OXT application-vnd.rn-realmedia=RM application-vnd.snap=SNAP
    application-vnd.squashfs=SQSH application-vnd.stardivision.calc=SDC application-vnd.stardivision.draw=SDA
    application-vnd.stardivision.mail=SMD application-vnd.stardivision.math=SMF application-vnd.sun.xml.calc=SXC
    application-vnd.sun.xml.calc.template=STC application-vnd.sun.xml.draw=SXD
    application-vnd.sun.xml.draw.template=STD application-vnd.sun.xml.impress=SXI
    application-vnd.sun.xml.impress.template=STI application-vnd.sun.xml.math=SXM application-vnd.sun.xml.writer=SXW
    application-vnd.sun.xml.writer.global=SXG application-vnd.sun.xml.writer.template=STW application-vnd.visio=VSD
    application-vnd.wordperfect=WP application-wps-office.doc=DOC application-wps-office.docx=DOCX
    application-wps-office.dot=DOT application-wps-office.dotx=DOTX application-wps-office.pot=POT
    application-wps-office.potx=POTX application-wps-office.ppt=PPT application-wps-office.pptx=PPTX
    application-wps-office.xls=XLS application-wps-office.xlsx=XLSX application-wps-office.xlt=XLT
    application-wps-office.xltx=XLTX application-x-abiword=ABW application-x-ace=ACE
    application-x-apple-diskimage=DMG application-x-applix-spreadsheet=AS application-x-applix-word=AW
    application-x-archive=A application-x-arj=ARJ application-x-awk=AWK application-x-cda=CDA
    application-x-cisco-vpn-settings=PCF application-x-compress=Z application-x-cpio=CPIO application-x-cue=CUE
    application-x-designer=UI application-x-egon=EGON application-x-fictionbook+xml=FB2
    application-x-flash-video=FLV application-x-font-afm=AFM application-x-font-bdf=BDF application-x-font-pcf=PCF
    application-x-font-snf=SNF application-x-font-ttx=TTX application-x-font-type1=PFA application-x-gameboy-rom=GB
    application-x-gamecube-rom=ISO application-x-gba-rom=GBA application-x-gdscript=GD
    application-x-gettext-translation=GMO application-x-gnumeric=GNM application-x-godot-resource=RES
    application-x-godot-scene=SCN application-x-it87=IT87 application-x-jar=JAR application-x-java-archive=JAR
    application-x-kexiproject-sqlite=KEXI application-x-kexiproject-sqlite2=KEXI
    application-x-kexiproject-sqlite3=KEXI application-x-kformula=KFO application-x-kgetlist=KGT
    application-x-kmymoney=KMY application-x-kontour=KON application-x-krita=KRA application-x-kword=KWD
    application-x-lha=LHA application-x-lyx=LYX application-x-lzma-compressed-tar=TLZ application-x-lzop=LZO
    application-x-m4=M4 application-x-mimearchive=MHT application-x-mplayer2=WMP application-x-ms-shortcut=LNK
    application-x-ms-wim=WIM application-x-mswinurl=URL application-x-mswrite=WRI application-x-n64-rom=N64
    application-x-nes-rom=NES application-x-nintendo-ds-rom=NDS application-x-nzb=NZB application-x-object=O
    application-x-openvpn-profile=OVPN application-x-pak=PAK application-x-partial-download=PART
    application-x-perl=PL application-x-php=PHP application-x-pkcs12=P12 application-x-pkcs7-certificates=P7B
    application-x-python-bytecode=PYC application-x-qemu-disk=QCOW application-x-quattropro=WB1
    application-x-raw-disk-image=IMG application-x-ruby=RB application-x-sami=SMI application-x-sharedlib=SO
    application-x-shockwave-flash=SWF application-x-siag=SIAG application-x-srt=SRT application-x-subrip=SRT
    application-x-tarz=TAZ application-x-tgif=OBJ application-x-trash=BAK application-x-troff-man=MAN
    application-x-tzo=TZO application-x-vdi-disk=VDI application-x-wmf=WMF application-x-x509-ca-cert=DER
    application-x-xliff=XLF application-x-xpinstall=XPI application-x-zip-compressed-fb2=FB2 application-x-zoo=ZOO
    application-xsd=XSD application-xslt+xml=XSL audio-ac3=AC3 audio-midi=MID audio-mp2=MP2 audio-prs.sid=SID
    audio-x-aiff=AIFF audio-x-flac+ogg=OGA audio-x-mp2=MP2 audio-x-speex+ogg=OGA image-ico=ICO image-jpeg2000=JP2
    image-vnd.dwg=DWG image-x-adobe-dng=DNG image-x-emf=EMF image-x-eps=EPS image-x-ico=ICO
    image-x-portable-bitmap=PBM image-x-psd=PSD image-x-tga=TGA image-x-win-bitmap=CUR image-x-wmf=WMF
    image-x-xfig=FIG libreoffice-database=ODB libreoffice-drawing=ODG libreoffice-drawing-template=OTG
    libreoffice-formula=ODF libreoffice-master-document=ODM libreoffice-oasis-database=ODB
    libreoffice-oasis-drawing=ODG libreoffice-oasis-drawing-template=OTG libreoffice-oasis-formula=ODF
    libreoffice-oasis-master-document=ODM libreoffice-oasis-presentation=ODP
    libreoffice-oasis-presentation-template=OTP libreoffice-oasis-spreadsheet=ODS
    libreoffice-oasis-spreadsheet-template=OTS libreoffice-oasis-text=ODT libreoffice-oasis-text-template=OTT
    libreoffice-oasis-web-template=OTH libreoffice-presentation=ODP libreoffice-presentation-template=OTP
    libreoffice-spreadsheet=ODS libreoffice-spreadsheet-template=OTS libreoffice-text=ODT
    libreoffice-text-template=OTT message-rfc822=EML odf=ODF text-rdf=RDF text-sgml=SGML text-troff=TR
    text-vnd.abc=ABC text-vnd.trolltech.linguist=TS text-vnd.wap.wml=WML text-vtt=VTT text-x-adasrc=ADB
    text-x-bibtex=BIB text-x-c++hdr=HH text-x-csharp=CS text-x-dtd=DTD text-x-fortran=F
    text-x-gettext-translation=PO text-x-haskell=HS text-x-hex=HEX text-x-kotlin=KT text-x-ldif=LDIF
    text-x-lilypond=LY text-x-lua=LUA text-x-makefile=MK text-x-microdvd=SUB text-x-mpsub=SUB text-x-nfo=NFO
    text-x-nim=NIM text-x-objcsrc=M text-x-opml=OPML text-x-opml+xml=OPML text-x-pascal=P text-x-patch=DIFF
    text-x-po=PO text-x-qml=QML text-x-rpm-spec=SPEC text-x-sass=SASS text-x-scala=SC text-x-scss=SCSS
    text-x-ssa=SSA text-x-subviewer=SUB text-x-tcl=TCL text-x-tex=TEX text-x-texinfo=TEXI text-x-xslfo=FO
    video-mp2t=M2T video-vivo=VIV video-vnd.rn-realvideo=RV video-x-flic=FLI video-x-flv=FLV video-x-javafx=FXM
    video-x-mng=MNG video-x-ms-wmp=WMP video-x-ms-wmv=WMV video-x-ogm+ogg=OGM video-x-theora+ogg=OGG
    x-office-document=DOC x-office-spreadsheet=XLS x-office-presentation=PPT application-vnd.ms-infopath=XSN
""".split())


def _familie(naam: str) -> tuple[str, str | None]:
    if naam in LABELS:
        fam, label = LABELS[naam]
        return fam, label or EXTENSIES.get(naam)
    for fam, regel in _REGELS:
        if re.search(regel, naam):
            return fam, EXTENSIES.get(naam)
    return "unknown", EXTENSIES.get(naam)
