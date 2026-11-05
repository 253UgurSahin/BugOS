#!/usr/bin/env python3
"""Verzamel alle Engelse teksten uit de BugOS-apps in een vertaal-sjabloon.

Gebruik:  python3 tools/collect-translations.py [taalcode]
  zonder taalcode -> werkt template.json bij
  met taalcode    -> werkt <taalcode>.json bij (bestaande vertalingen blijven staan)

Hoe het werkt: in de code staat overal t("Nederlands", "English").
Dit script zoekt alle Engelse teksten en zet ze in een JSON-bestand:
    { "English text": "" }
Een vertaler vult de lege plekjes in. Klaar!
"""

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRONNEN = ROOT / "system_files" / "usr"
DOEL = BRONNEN / "share" / "bugos" / "vertalingen"


def uit_python(pad: Path) -> set[str]:
    teksten = set()
    try:
        boom = ast.parse(pad.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError):
        return teksten
    for knoop in ast.walk(boom):
        if (isinstance(knoop, ast.Call) and isinstance(knoop.func, ast.Name) and knoop.func.id == "t"
                and len(knoop.args) == 2 and isinstance(knoop.args[1], ast.Constant)
                and isinstance(knoop.args[1].value, str)):
            teksten.add(knoop.args[1].value)
    return teksten


BASH_T = re.compile(r'\bt\s+(?:\\\s*)?"((?:[^"\\$]|\\.)*)"\s+(?:\\\s*)?"((?:[^"\\$]|\\.)*)"')


def uit_bash(pad: Path) -> set[str]:
    tekst = pad.read_text(encoding="utf-8", errors="ignore")
    return {m.group(2) for m in BASH_T.finditer(tekst)}


def main() -> int:
    teksten: set[str] = set()
    for pad in BRONNEN.rglob("*"):
        if not pad.is_file():
            continue
        kop = pad.read_bytes()[:40]
        if pad.suffix == ".py" or kop.startswith(b"#!/usr/bin/python3"):
            teksten |= uit_python(pad)
        elif pad.suffix == ".sh" or kop.startswith(b"#!/usr/bin/bash"):
            teksten |= uit_bash(pad)

    naam = (sys.argv[1] if len(sys.argv) > 1 else "sjabloon") + ".json"
    bestand = DOEL / naam
    oud = {}
    if bestand.exists():
        oud = json.loads(bestand.read_text(encoding="utf-8"))
    nieuw = {k: oud.get(k, "") for k in sorted(teksten)}
    DOEL.mkdir(parents=True, exist_ok=True)
    bestand.write_text(json.dumps(nieuw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    klaar = sum(1 for v in nieuw.values() if v)
    print(f"{bestand.relative_to(ROOT)}: {len(nieuw)} teksten, {klaar} vertaald")
    return 0


if __name__ == "__main__":
    sys.exit(main())
