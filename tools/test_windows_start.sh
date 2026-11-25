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
# Sinds 'bestanden slimmer' staat de grootte eerst in $nodig (die noemt de melding ook), daarna de vergelijking.
# Sinds het werk naast het venster loopt (runspace), komen vrij en al via $Mee mee.
controle 'grep -q "\$nodig = Get-MeeneemGrootte" <<<"$PS" && grep -q "\$Mee.Vrij + \$Mee.Al -lt \$nodig" <<<"$PS"' "U286: nog een keer klikken telt wat er al op de schijf staat"
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
# U535: naast BugOS gaat Windows 'Snel opstarten' uit (anders blijft de Windows-schijf half in slaap: bestanden kwijt).
controle 'grep -A6 "function Set-KlokUtc" <<<"$PS" | grep -q "HiberbootEnabled.*-Value 0"' \
    "U535: de Windows-tool zet 'Snel opstarten' uit (de Windows-schijf blijft niet half in slaap)"
# U536: publiceren kan alleen met de bouw 'latest' (geen ISO die pc's voor altijd op een testbranch zet).
controle 'grep -q "\[ \"\$PUBLICEREN\" = true \] && \[ \"\$TAG\" != latest \]" "$ROOT/.github/workflows/iso.yml"' \
    "U536: een ISO publiceren kan alleen van 'latest'"
# Een echte USB-stick blijft na Clear-Disk MBR: Initialize-Disk alleen als hij echt leeg (RAW) is, anders
# 'The disk has already been initialized' (gevonden op een echte stick; de nep-schijf in de zelftest wordt wel RAW).
controle 'grep -A20 "function Clear-Stick" <<<"$PS" | grep -B1 "Initialize-Disk" | grep -q "if (\$stijl -eq .RAW.)"' \
    "Switch: een USB-stick die na het wissen MBR blijft, wordt niet opnieuw geinitialiseerd"
# Windows 11 opent een .bat in Terminal; daar verbergt -WindowStyle Hidden niets. Via conhost --headless en start.
controle 'tr -d "\r" <"$ROOT/windows-switch/Start BugOS Switch.bat" | grep -q "^ *start \"\" \"%SystemRoot%.System32.conhost.exe\" --headless powershell.exe"' \
    "Switch: het startbestand laat geen zwart venster openstaan (conhost --headless)"
# [math]::Max(1, $groot) kiest in PowerShell de Int32-versie: met BugOS (meer dan 2 GB) ging de stick stuk.
controle '! grep -nE "\[math\]::M(in|ax)\([0-9]+, *\\\$(teller|groot|grootte|totaal|kanWeg|squash|efiBytes)" <<<"$PS" && grep -q "\[math\]::Max(\[int64\]1, \[int64\]\$teller.Totaal)" <<<"$PS"' \
    "Switch: rekenen met de grootte van BugOS (meer dan 2 GB) gaat niet in een Int32"
echo "$fouten fout(en)."
[ "$fouten" -eq 0 ]
