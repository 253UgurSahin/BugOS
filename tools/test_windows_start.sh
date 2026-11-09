#!/usr/bin/bash
# Test van de Windows-overstap: elk startbestand (.bat) opent een script dat echt bestaat.
# Na een hernoeming opende "Start BugOS Switch.bat" nog het oude BugOS-Overstap.ps1, en omdat
# het venster verborgen is, gebeurde er dan helemaal niets (A030).
#
# Gebruik:  bash tools/test_windows_start.sh
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fouten=0
aantal=0

for bat in "$ROOT"/windows-switch/*.bat; do
    # Elke "%~dp0naam.ps1" in het startbestand moet naast het startbestand staan.
    while IFS= read -r naam; do
        aantal=$((aantal + 1))
        if [ -f "$ROOT/windows-switch/$naam" ]; then
            echo "OK    $(basename "$bat") opent $naam"
        else
            echo "FOUT  $(basename "$bat") opent $naam, maar dat bestand bestaat niet"
            fouten=$((fouten + 1))
        fi
    done < <(tr -d '\r' <"$bat" | grep -o '%~dp0[^"]*\.ps1' | sed 's/^%~dp0//')
done

if [ "$aantal" -eq 0 ]; then
    echo "FOUT  geen startbestand gevonden dat een .ps1 opent"
    fouten=$((fouten + 1))
fi
# U284-U288: stap 2 alleen USB-schijven; ruimte telt wat er al staat; de juiste installatiekeuze; een halve download
# wordt opgeruimd; een volle schijf wordt zo genoemd. (Alleen het script lezen: PowerShell draait hier niet.)
PS="$(tr -d '\r' <"$ROOT/windows-switch/BugOS-Switch.ps1")"
controle() { if eval "$1"; then echo "OK    $2"; else echo "FOUT  $2"; fouten=$((fouten + 1)); fi; }
controle 'grep -q "DriveType -eq 3 -and (Test-UsbLetter" <<<"$PS" && ! grep -q "DriveType -in 2, 3" <<<"$PS"' \
    "U284: stap 2 biedt geen schijf in de computer (D:) aan als back-upplek"
controle 'grep -q "\$vrij + \$al -lt (Get-MeeneemGrootte)" <<<"$PS"' "U286: nog een keer klikken telt wat er al op de schijf staat"
controle '! grep -q "choose \"Automatic\"" <<<"$PS" && grep -q "Share disk with other operating systems" <<<"$PS"' \
    "U285: na 'Ruimte maken' noemt hij de keuze die het installatieprogramma echt heeft"
controle 'grep -q "if (-not \$gelukt) { Remove-Item -LiteralPath \$doel" <<<"$PS"' "U287: een halve download wordt opgeruimd"
controle 'grep -q "Get-Disk -ErrorAction Stop).BusType" <<<"$PS" && grep -q "MediaType)\" -like .External\*" <<<"$PS"' \
    "U296: een snelle USB-SSD (meldt zich als SCSI) staat toch in de lijst van stap 2"
controle 'grep -q "InnerException.Message" <<<"$PS"' "U298: een mislukte download zegt de echte reden erbij"
controle 'grep -q "De schijf is vol geraakt" <<<"$PS"' "U288: een stick die vol raakt, wordt zo genoemd"
controle 'grep -q "\$(\$schijf.UniqueId)\" -ne \$id" <<<"$PS" && grep -q "SchijfId., \"" <<<"$PS"' \
    "U370: stap 4 wist alleen de USB-stick die je koos (niet een andere die intussen hetzelfde nummer kreeg)"
# U396: alleen GTX 16 / RTX / MX 450+ krijgen de Nvidia-versie; een GTX 1060 of GT 1030 de gewone.
NV="$(python3 - "$ROOT/windows-switch/BugOS-Switch.ps1" <<'PY'
import re, sys
s = open(sys.argv[1], encoding="utf-8-sig").read()
f = s[s.index("function Test-NieuweNvidia"):s.index("function Get-IsoSoort")]
pat = re.findall(r"-match '([^']+)'", f)   # (-notmatch 'NVIDIA' telt niet mee)
assert "-split ',\\s*'" in f, "per kaart"
def nieuw(g): return any("NVIDIA" in n.upper() and any(re.search(p, n, re.I) for p in pat) for n in re.split(r",\s*", g))
uit = {g: nieuw(g) for g in ("NVIDIA GeForce GTX 1060 6GB", "NVIDIA GeForce GT 1030", "NVIDIA GeForce MX350",
                              "NVIDIA GeForce RTX 3060", "NVIDIA GeForce GTX 1650", "NVIDIA GeForce MX450",
                              "NVIDIA T500", "NVIDIA T2000", "Intel(R) Arc(TM) A770 Graphics, NVIDIA GeForce GTX 1060")}
print("ok" if list(uit.values()) == [False, False, False, True, True, True, True, True, False] else uit)
PY
)"
controle '[ "$NV" = ok ] && grep -q "if (Test-NieuweNvidia \$gpu) { .nvidia. }" <<<"$PS" && grep -q "Name) -join .\\(, \\). *$" <<<"$(grep -A1 "function Get-IsoSoort" <<<"$PS")"' \
    "U396/U408: alleen GTX 16, RTX en MX 450+ krijgen de Nvidia-versie; oudere kaarten de gewone ($NV)"
# U446: ruimte maken voor BugOS naast Windows zet de klok van Windows op UTC (anders 1-2 uur verschil na elke wissel).
controle 'grep -A2 "Invoke-Krimp \$KrimpGB\s*$" <<<"$PS" | grep -q "Set-KlokUtc" && grep -A2 "Write-IsoNaarSchijf \$IsoPad" <<<"$PS" | grep -q "Set-KlokUtc" && grep -A2 "function Set-KlokUtc" <<<"$PS" | grep -q "RealTimeIsUniversal.*-Value 1 -Type DWord"' \
    "U446/U453: naast Windows loopt de klok niet verkeerd (Windows op UTC, bij ruimte maken en bij de USB-stick)"
echo "$fouten fout(en)."
[ "$fouten" -eq 0 ]
