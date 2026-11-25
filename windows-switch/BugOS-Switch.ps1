#Requires -Version 5.1
<#
.SYNOPSIS
    BugOS Switch - van Windows naar BugOS, in vier simpele stappen.

.DESCRIPTION
    Jip-en-Janneke:
      1. Controleren  - kan deze computer BugOS draaien?
      2. USB-stick    - BugOS op een USB-stick zetten (die blijft bruikbaar in
                        Windows: een exFAT-schijf BUGOS, zie 4b hieronder).
      3. Meenemen     - je documenten, foto's, muziek, video's, bureaublad,
                        downloads, bladwijzers en achtergrond naar een USB-schijf
                        (ook de BugOS-stick), plus je instellingen, de NAMEN van
                        je wifi-netwerken, je netwerkprinters en een lijstje van
                        je programma's (formaat 2, zie FORMAT.md). Nooit
                        wachtwoorden.
      4. Waar komt BugOS? - in plaats van Windows, ernaast (dan maakt deze stap
                        Windows wat kleiner) of op een andere schijf.
    In de code heten de pagina's nog naar hun oude plek (2 meenemen, 3 ruimte, 4 stick); de volgorde staat
    bij Toon-Pagina.

    Starten: dubbelklik op "Start BugOS Switch.bat".

    Licentie: PolyForm Noncommercial 1.0.0 (zie LICENSE en NOTICE.md). Onderdeel van BugOS.
#>

param(
    # Alleen intern gebruikt: dezelfde stap opnieuw starten als beheerder.
    [ValidateSet('', 'Krimp', 'Usb', 'Herstel', 'Foto', 'Zelftest')] [string] $Taak = '',
    [int] $KrimpGB = 0,
    [string] $IsoPad = '',
    [int] $SchijfNummer = -1,
    # Welke schijf het precies moet zijn (gekozen in stap 4): na eruit halen/insteken kan een andere hetzelfde nummer krijgen (U370).
    [string] $SchijfId = '',
    # Hoe de stick gemaakt wordt: 'bruikbaar' (exFAT, blijft bruikbaar in Windows) of 'heel' (de ISO rauw, oude manier).
    [ValidateSet('bruikbaar', 'heel')] [string] $Manier = 'bruikbaar',
    # Waar een beheerder-taak zijn voortgang neerzet (het hoofdvenster leest het; zo blijft dat venster bewegen).
    [string] $VoortgangBestand = '',
    # Alleen voor de zelftest op GitHub: ook een nep-schijf uit een bestand (VHD) mag, nooit een echte vaste schijf.
    [switch] $TestSchijf,
    # Taal kiezen (nl of en). Leeg = de taal van Windows.
    [ValidateSet('', 'nl', 'en')] [string] $Taal = '',
    # Alleen voor de bouwstraat: plaatjes van elke pagina maken.
    [string] $FotoMap = '',
    [double] $FotoSchaal = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# Welke versie dit is: staat in de titelbalk en onderin de zijbalk, zodat je ziet of je de nieuwste hebt.
$script:Versie = '2026.11.25-14'

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()
# In de zelftest (GitHub): een fout in het venster (bijv. in het klokje) moet een echte fout zijn, geen foutvenster
# waar niemand op klikt (dan bleef de zelftest een kwartier hangen).
try { if ((Test-Path variable:Taak) -and $Taak -eq 'Zelftest') { [System.Windows.Forms.Application]::SetUnhandledExceptionMode('ThrowException') } } catch { Write-Verbose 'Kan niet meer (er is al een venster).' }

# ------------------------------------------------------------------ taal --
$script:NL = (Get-Culture).TwoLetterISOLanguageName -eq 'nl'
if ((Test-Path variable:Taal) -and $Taal) { $script:NL = $Taal -eq 'nl' }
function T([string] $nl, [string] $en) { if ($script:NL) { $nl } else { $en } }

function Test-Beheerder {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    (New-Object Security.Principal.WindowsPrincipal $id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Start-AlsBeheerder([string[]] $Argumenten) {
    $pad = $PSCommandPath
    $alles = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$pad`"") + $Argumenten
    if ((Test-Path variable:Taal) -and $Taal) { $alles += @('-Taal', $Taal) }
    try {
        $p = Start-Process -FilePath 'powershell.exe' -ArgumentList $alles -Verb RunAs -PassThru -Wait
        return $p.ExitCode
    } catch {
        # Bijvoorbeeld: de gebruiker drukte op 'Nee' bij de beheerder-vraag.
        return -1
    }
}

function Toon([string] $tekst, [string] $soort = 'Information') {
    # In de zelftest (GitHub) klikt niemand: dan alleen opschrijven, nooit een venster dat blijft wachten.
    if ((Test-Path variable:Taak) -and $Taak -eq 'Zelftest') { Write-Host "MELDING ($soort): $tekst"; return }
    [void][System.Windows.Forms.MessageBox]::Show($tekst, 'BugOS Switch', 'OK', $soort)
}

function Vraag([string] $tekst) {
    if ((Test-Path variable:Taak) -and $Taak -eq 'Zelftest') { Write-Host "VRAAG (nee): $tekst"; return $false }
    [System.Windows.Forms.MessageBox]::Show($tekst, 'BugOS Switch', 'YesNo', 'Warning') -eq 'Yes'
}

# ============================================================ 1. CONTROLE ==

function Get-Controle {
    $uitslag = New-Object System.Collections.Generic.List[object]
    function Voeg([string] $naam, [bool] $ok, [string] $tekst, [bool] $waarschuwing = $false) {
        $uitslag.Add([pscustomobject]@{ Naam = $naam; Ok = $ok; Tekst = $tekst; Waarschuwing = $waarschuwing })
    }

    $is64 = [Environment]::Is64BitOperatingSystem
    Voeg (T '64-bit' '64-bit') $is64 ($(if ($is64) { T 'Je computer is 64-bit. Goed!' 'Your computer is 64-bit. Good!' } else { T 'BugOS heeft een 64-bit computer nodig.' 'BugOS needs a 64-bit computer.' }))

    $gb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
    if ($gb -ge 6) { Voeg (T 'Geheugen' 'Memory') $true (T "$gb GB. Ruim genoeg." "$gb GB. Plenty.") }
    elseif ($gb -ge 4) { Voeg (T 'Geheugen' 'Memory') $true (T "$gb GB. Dat werkt; BugOS zet de lichte stand aan." "$gb GB. That works; BugOS will turn on light mode.") $true }
    else { Voeg (T 'Geheugen' 'Memory') $false (T "$gb GB. BugOS heeft minstens 4 GB nodig." "$gb GB. BugOS needs at least 4 GB.") }

    $uefi = $env:firmware_type
    if (-not $uefi) { try { $null = Confirm-SecureBootUEFI; $uefi = 'UEFI' } catch [System.PlatformNotSupportedException] { $uefi = 'Legacy' } catch { $uefi = 'UEFI' } }
    Voeg 'UEFI' ($uefi -eq 'UEFI') ($(if ($uefi -eq 'UEFI') { T 'Je computer start op de moderne manier (UEFI). Goed!' 'Your computer boots the modern way (UEFI). Good!' } else { T 'Je computer start op de oude manier (Legacy/BIOS). Zet UEFI aan in het opstartmenu van je computer.' 'Your computer uses the old boot mode (Legacy/BIOS). Turn on UEFI in your computer''s firmware menu.' }))

    $vrij = [math]::Round((Get-PSDrive C).Free / 1GB)
    if ($vrij -ge 80) { Voeg (T 'Ruimte op C:' 'Space on C:') $true (T "$vrij GB vrij. Genoeg om BugOS naast Windows te zetten." "$vrij GB free. Enough to put BugOS next to Windows.") }
    else { Voeg (T 'Ruimte op C:' 'Space on C:') $true (T "$vrij GB vrij. Te weinig om naast Windows te zetten (80 GB nodig), maar BugOS kan Windows wel vervangen." "$vrij GB free. Too little to install next to Windows (80 GB needed), but BugOS can replace Windows.") $true }

    try {
        $bl = (New-Object -ComObject Shell.Application).NameSpace('C:').Self.ExtendedProperty('System.Volume.BitLockerProtection')
        if ($bl -in 1, 3, 5) {
            Voeg 'BitLocker' $true (T 'C: is versleuteld met BitLocker. Schrijf je herstelsleutel op (account.microsoft.com/devices/recoverykey) voordat je verder gaat!' 'C: is encrypted with BitLocker. Write down your recovery key (account.microsoft.com/devices/recoverykey) before you continue!') $true
        }
    } catch { }

    $gpu = (Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join ', '
    if (Test-NieuweNvidia $gpu) {
        Voeg (T 'Videokaart' 'Graphics') $true (T "Nvidia gevonden ($gpu). Kies de versie 'bugos-nvidia'." "Nvidia found ($gpu). Choose the 'bugos-nvidia' version.") $true
    } elseif ($gpu -match 'NVIDIA') {
        # Ouder dan GTX 16 / RTX: het Nvidia-stuurprogramma van BugOS kent die niet; de gewone versie werkt wel (U396).
        Voeg (T 'Videokaart' 'Graphics') $true (T "Een oudere Nvidia-kaart ($gpu). Kies de gewone versie 'bugos': de Nvidia-versie werkt alleen met GTX 16 en RTX." "An older Nvidia card ($gpu). Choose the normal 'bugos' version: the Nvidia version only works with GTX 16 and RTX.")
    } else {
        Voeg (T 'Videokaart' 'Graphics') $true (T "$gpu. Kies de gewone versie 'bugos'." "$gpu. Choose the normal 'bugos' version.")
    }
    return $uitslag
}

# =========================================================== 2. MEENEMEN ==

function Get-BekendeMap([string] $naam) {
    switch ($naam) {
        'Downloads' {
            try { return (New-Object -ComObject Shell.Application).NameSpace('shell:Downloads').Self.Path } catch { return (Join-Path $env:USERPROFILE 'Downloads') }
        }
        default { return [Environment]::GetFolderPath($naam) }
    }
}

$script:Mappen = @(
    @{ Sleutel = 'MyDocuments'; Naam = 'Documents' },
    @{ Sleutel = 'MyPictures'; Naam = 'Pictures' },
    @{ Sleutel = 'MyMusic'; Naam = 'Music' },
    @{ Sleutel = 'MyVideos'; Naam = 'Videos' },
    @{ Sleutel = 'Desktop'; Naam = 'Desktop' },
    @{ Sleutel = 'Downloads'; Naam = 'Downloads' }
)

function Get-MapGrootte([string] $pad, [string[]] $ZonderMappen = @()) {
    # Hoeveel bytes er in een map staan (alle submappen). Mappen met een naam uit -ZonderMappen tellen niet mee
    # (bijvoorbeeld 'ImapMail' van Thunderbird: die gaat niet mee). Bestanden die alleen in OneDrive staan, tellen
    # niet mee als je die niet mee wilt ($script:CloudMee uit): die worden dan ook niet gekopieerd.
    if (-not $pad -or -not (Test-Path -LiteralPath $pad)) { return 0L }
    $bestanden = Get-ChildItem -LiteralPath $pad -Recurse -File -Force -ErrorAction SilentlyContinue
    if ($ZonderMappen.Count -gt 0) {
        $bestanden = $bestanden | Where-Object {
            $rel = $_.FullName.Substring($pad.Length).TrimStart('\')
            -not ($ZonderMappen | Where-Object { $rel -like "$_\*" })
        }
    }
    if (-not $script:CloudMee) { $bestanden = $bestanden | Where-Object { -not (Test-AlleenInCloud $_) } }
    $som = ($bestanden | Measure-Object Length -Sum).Sum
    if ($som) { return [int64]$som } else { return 0L }
}

function Get-MeeneemGrootte {
    # Alles wat naar de schijf gaat, opgeteld: de zes vaste mappen, de extra mappen die je koos, je lettertypen,
    # je Thunderbird (zonder ImapMail, die haalt Thunderbird opnieuw op) en Outlook-mailbestanden buiten Documenten.
    # Zo kunnen we VOORAF zeggen of het past (E: 'vooraf zeggen hoeveel er meegaat').
    $totaal = 0L
    foreach ($m in $script:Mappen) { $totaal += Get-MapGrootte (Get-BekendeMap $m.Sleutel) }
    foreach ($e in $script:ExtraMappen) { $totaal += Get-MapGrootte $e }
    foreach ($f in @(Get-Lettertypen)) { $totaal += $f.Length }
    $tb = Get-ThunderbirdProfiel
    if ($tb) { $totaal += Get-MapGrootte $tb.Pad -ZonderMappen $script:ThunderbirdNietMee }
    foreach ($p in @(Get-OutlookBestanden)) { $totaal += $p.Length }
    return $totaal
}

# ------------------------------------------- meenemen: bestanden slimmer (E) --

function Test-AlleenInCloud($bestand) {
    # Staat dit bestand alleen in OneDrive (in de cloud, niet echt op deze computer)? Windows geeft zo'n bestand
    # (een 'placeholder' van Files On-Demand) het kenmerk RECALL_ON_DATA_ACCESS (0x400000) of RECALL_ON_OPEN
    # (0x40000), en voor oude programma's ook OFFLINE (0x1000). Zie de Microsoft-documentatie over
    # 'File attribute constants' (learn.microsoft.com/windows/win32/fileio/file-attribute-constants).
    # Let op: op de testcomputer van BugOS stond geen OneDrive; dit is getest met nep-kenmerken, niet met echte.
    $a = [int64]$bestand.Attributes
    return (($a -band 0x400000) -ne 0) -or (($a -band 0x40000) -ne 0) -or (($a -band 0x1000) -ne 0)
}

function Get-CloudBestanden {
    # Hoeveel bestanden in de mappen die meegaan alleen in OneDrive staan, hoe groot samen, en een paar namen als
    # voorbeeld. Die moeten eerst gedownload worden (dat doet Windows vanzelf als we ze kopiëren, maar dat kan lang
    # duren en vraagt internet), of ze blijven in OneDrive: dan kun je ze in BugOS via onedrive.live.com openen.
    $aantal = 0; $bytes = 0L
    $voorbeelden = New-Object System.Collections.Generic.List[string]
    $bronnen = @($script:Mappen | ForEach-Object { Get-BekendeMap $_.Sleutel }) + @($script:ExtraMappen)
    foreach ($pad in $bronnen) {
        if (-not $pad -or -not (Test-Path -LiteralPath $pad)) { continue }
        foreach ($f in @(Get-ChildItem -LiteralPath $pad -Recurse -File -Force -ErrorAction SilentlyContinue)) {
            if (-not (Test-AlleenInCloud $f)) { continue }
            $aantal++; $bytes += $f.Length
            if ($voorbeelden.Count -lt 8) { $voorbeelden.Add($f.Name) }
        }
    }
    return [pscustomobject]@{ Aantal = $aantal; Bytes = $bytes; Voorbeelden = $voorbeelden.ToArray() }
}

function Get-Lettertypen {
    # De lettertypen die JIJ installeerde (per gebruiker), alleen echte lettertypebestanden.
    if (-not (Test-Path -LiteralPath $script:LettertypeMap)) { return @() }
    return @(Get-ChildItem -LiteralPath $script:LettertypeMap -File -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in @('.ttf', '.otf', '.ttc', '.otc') })
}

# Uit het Thunderbird-profiel gaat niet mee: ImapMail (een kopie van de mail op de server, die haalt Thunderbird
# opnieuw op; kan vele GB zijn) en wat Thunderbird zelf opnieuw maakt. Wachtwoorden en cookies staan in de /XF-lijst
# van Copy-ThunderbirdProfiel (net als bij Firefox: de regel van de eigenaar).
$script:ThunderbirdNietMee = @('ImapMail', 'cache2', 'startupCache', 'shader-cache', 'crashes', 'minidumps', 'saved-telemetry-pings', 'datareporting', 'sessionstore-backups')

function Get-ThunderbirdProfiel {
    # Het standaardprofiel van Thunderbird, of $null als Thunderbird er niet is.
    try { return @(Get-FirefoxProfielen -Map $script:ThunderbirdMap | Where-Object { $_.Standaard }) | Select-Object -First 1 }
    catch { return $null }
}

function Copy-ThunderbirdProfiel([string] $bron, [string] $doel) {
    # Je Thunderbird: accounts, mappen op deze computer ('Lokale mappen', POP-mail), adresboek, filters en
    # instellingen. NOOIT de wachtwoorden (logins.json, key4.db): in BugOS vraagt Thunderbird ze één keer.
    $xf = @('logins.json', 'logins-backup.json', 'logins.db', 'logins.db-wal', 'logins.db-shm', 'key4.db', 'key3.db', 'signons.sqlite', 'cookies.sqlite*', 'sessionstore*', 'parent.lock', '.parentlock', 'lock')
    $argumenten = @($bron, $doel, '/E', '/R:1', '/W:1', '/XJ', '/NFL', '/NDL', '/NJH', '/NJS', '/NP', '/XF') + $xf + @('/XD') + $script:ThunderbirdNietMee
    $null = & robocopy @argumenten
    if ($LASTEXITCODE -ge 16) { throw (T 'Thunderbird kopiëren lukte niet.' 'Copying Thunderbird failed.') }
}

function Get-OutlookBestanden {
    # Outlook-mailbestanden (.pst) die NIET al in Documenten staan (die gaan daar al mee). .ost-bestanden laten we
    # liggen: dat is alleen een kopie van wat op de server staat.
    if (-not (Test-Path -LiteralPath $script:OutlookMap)) { return @() }
    return @(Get-ChildItem -LiteralPath $script:OutlookMap -Filter '*.pst' -File -Force -ErrorAction SilentlyContinue)
}

function Test-ExtraMap([string] $pad, [string] $doelSchijf = '') {
    # Mag deze map mee als extra map? Geeft '' (ja) of de reden (nee), in gewone woorden.
    # Niet: iets dat niet bestaat, een hele schijf (C:\ of D:\: kies een map ERIN, anders sleep je ook Windows
    # of programma's mee), de mappen van Windows zelf, een map die al meegaat (of erin zit), de USB-schijf zelf.
    if (-not $pad -or -not (Test-Path -LiteralPath $pad -PathType Container)) { return (T 'Die map bestaat niet.' 'That folder does not exist.') }
    $vol = [System.IO.Path]::GetFullPath($pad).TrimEnd('\')
    if ($vol -match '^[A-Za-z]:$') { return (T 'Kies een map op die schijf, niet de hele schijf.' 'Choose a folder on that drive, not the whole drive.') }
    if ($doelSchijf -and $vol.StartsWith($doelSchijf.TrimEnd('\'), [StringComparison]::OrdinalIgnoreCase)) {
        return (T 'Die map staat op de USB-schijf zelf.' 'That folder is on the USB drive itself.')
    }
    foreach ($systeem in @($env:windir, $env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:ProgramData, $env:APPDATA, $env:LOCALAPPDATA)) {
        if ($systeem -and ($vol + '\').StartsWith($systeem.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase)) {
            return (T 'Dat is een map van Windows of van je programma''s. Die werkt niet op BugOS.' 'That is a folder of Windows or your programs. It does not work on BugOS.')
        }
    }
    foreach ($al in @($script:Mappen | ForEach-Object { Get-BekendeMap $_.Sleutel }) + @($script:ExtraMappen)) {
        if (-not $al) { continue }
        $alVol = [System.IO.Path]::GetFullPath($al).TrimEnd('\')
        if (($vol + '\').StartsWith($alVol + '\', [StringComparison]::OrdinalIgnoreCase)) { return (T 'Die map gaat al mee.' 'That folder already goes along.') }
        if (($alVol + '\').StartsWith($vol + '\', [StringComparison]::OrdinalIgnoreCase)) {
            return (T 'In die map zit een map die al meegaat. Kies een map die er niet omheen zit.' 'That folder contains a folder that already goes along. Choose one that does not.')
        }
    }
    return ''
}

function Get-ExtraNaam([string] $pad, [System.Collections.Generic.HashSet[string]] $gebruikt) {
    # De naam van een extra map op de schijf (Extra\<naam>): de mapnaam, en bij twee dezelfde (D:\Foto's en
    # E:\Foto's) 'Foto's (2)'. Tekens die op een FAT32-stick of in BugOS lastig zijn, worden een _.
    $naam = (Split-Path $pad -Leaf) -replace '[<>:"/\\|?*\x00-\x1f]', '_'
    if (-not $naam) { $naam = 'Map' }
    $kandidaat = $naam; $n = 2
    while ($gebruikt.Contains($kandidaat)) { $kandidaat = "$naam ($n)"; $n++ }
    [void]$gebruikt.Add($kandidaat)
    return $kandidaat
}

function Get-TeGrootVoorFat32 {
    # FAT32 (veel USB-sticks) kan geen bestanden van 4 GB of groter bewaren. Welke van de bestanden die meegaan zijn
    # dat? Dan kunnen we het VOORAF zeggen in plaats van halverwege.
    $grens = 4GB - 1
    $uit = New-Object System.Collections.Generic.List[object]
    $bronnen = @($script:Mappen | ForEach-Object { Get-BekendeMap $_.Sleutel }) + @($script:ExtraMappen)
    foreach ($pad in $bronnen) {
        if (-not $pad -or -not (Test-Path -LiteralPath $pad)) { continue }
        foreach ($f in @(Get-ChildItem -LiteralPath $pad -Recurse -File -Force -ErrorAction SilentlyContinue)) {
            if ($f.Length -gt $grens -and -not ((-not $script:CloudMee) -and (Test-AlleenInCloud $f))) { $uit.Add($f) }
        }
    }
    foreach ($p in @(Get-OutlookBestanden)) { if ($p.Length -gt $grens) { $uit.Add($p) } }
    return $uit.ToArray()
}

# ------------------------------------------------- meenemen: formaat 2 --
# Wat er naast de bestanden mee gaat (zie windows-switch/FORMAT.md, het contract met BugOS). Elke Get-* hieronder
# leest alleen (niets wordt veranderd) en is los te proberen. Regel van de eigenaar: NOOIT een wachtwoord op de schijf
# (geen wifi-sleutels, geen browser-wachtwoorden of cookies). Programma's worden alleen opgesomd: BugOS stelt voor,
# installeert nooit zelf.

# Waar de browsers hun gegevens bewaren. Script-variabelen, zodat een test ze naar een nep-map kan laten wijzen.
$script:ChromiumMappen = [ordered]@{
    'Chrome' = "$env:LOCALAPPDATA\Google\Chrome\User Data"
    'Edge'   = "$env:LOCALAPPDATA\Microsoft\Edge\User Data"
    'Brave'  = "$env:LOCALAPPDATA\BraveSoftware\Brave-Browser\User Data"
}
$script:FirefoxMap = "$env:APPDATA\Mozilla\Firefox"
# Mappen in het Firefox-profiel die groter zijn dan dit, blijven thuis (meestal 'storage' van websites): die maken
# de schijf vol en BugOS heeft ze niet nodig. We zeggen wel welke het waren.
$script:FirefoxGrens = 300MB
$script:FirefoxOverslagen = @()
# Thunderbird bewaart zijn profielen op dezelfde manier als Firefox (profiles.ini met [Profile..] en [Install..]),
# alleen in een andere map. Daarom leest Get-FirefoxProfielen ook die van Thunderbird (parameter -Map).
$script:ThunderbirdMap = "$env:APPDATA\Thunderbird"
# Lettertypen die je zelf installeerde, staan sinds Windows 10 (1809) per gebruiker hier. Die van Windows zelf
# (C:\Windows\Fonts) nemen we NIET mee: die zijn van Microsoft en mogen niet zomaar naar een andere computer.
$script:LettertypeMap = "$env:LOCALAPPDATA\Microsoft\Windows\Fonts"
# Outlook bewaart losse mailbestanden (.pst) in Documenten\Outlook-bestanden (gaat al mee met Documenten) of hier.
$script:OutlookMap = "$env:LOCALAPPDATA\Microsoft\Outlook"
# Extra mappen die je zelf kiest (bijvoorbeeld op D:), bovenop de vaste zes. Volle paden.
$script:ExtraMappen = New-Object System.Collections.Generic.List[string]
# Bestanden die alleen in OneDrive (de cloud) staan, en of je die mee wilt (eerst downloaden) of niet.
$script:Cloud = $null
$script:CloudMee = $true

function Get-Waarde($obj, [string] $naam) {
    # Een eigenschap lezen die er misschien niet is. Met Set-StrictMode geeft $obj.Naam anders een fout als de
    # eigenschap ontbreekt (bijv. een registersleutel zonder DisplayName).
    if ($null -eq $obj) { return $null }
    $eig = $obj.PSObject.Properties[$naam]
    if ($eig) { return $eig.Value }
    return $null
}

function Get-SchermSchaal {
    # De schaal van het hoofdscherm in procent (100, 125, 150...). Alleen juist als het programma 'DPI-bewust' is:
    # anders zegt Windows altijd 96 dpi. Dat zetten we hier (nog een keer) aan; twee keer kan geen kwaad.
    # Het is de schaal van het scherm waarop Windows bij het aanmelden begon (zo werkt 'system DPI').
    try { if ('BugOS.Dpi' -as [type]) { [void][BugOS.Dpi]::SetProcessDPIAware() } } catch { Write-Verbose 'Niet DPI-bewust.' }
    $g = [System.Drawing.Graphics]::FromHwnd([IntPtr]::Zero)
    try { return [int][math]::Round($g.DpiX * 100.0 / 96.0) } finally { $g.Dispose() }
}

function Get-Toetsenborden([object[]] $talen) {
    # De toetsenbordindelingen (KLID, 8 hexadecimale tekens) in de volgorde van Windows.
    # Eerst uit de taallijst: elke 'InputMethodTip' is 'taal:KLID', bijv. '0409:00020409' (VS-internationaal).
    # Een IME (Japans, Chinees) is '{guid}{guid}': die heeft geen KLID en slaan we over.
    $klids = New-Object System.Collections.Generic.List[string]
    foreach ($taal in @($talen)) {
        foreach ($tip in @(Get-Waarde $taal 'InputMethodTips')) {
            if ("$tip" -match '^[0-9A-Fa-f]{4}:([0-9A-Fa-f]{8})$') {
                $k = $Matches[1].ToUpperInvariant()
                if (-not $klids.Contains($k)) { $klids.Add($k) }
            }
        }
    }
    if ($klids.Count -eq 0) {
        # Reserve: HKCU\Keyboard Layout\Preload (1, 2, 3...). Een waarde als 'd0010409' is een verwijzing die in
        # 'Substitutes' naar de echte KLID wijst.
        $voor = Get-ItemProperty 'HKCU:\Keyboard Layout\Preload' -ErrorAction SilentlyContinue
        $vervang = Get-ItemProperty 'HKCU:\Keyboard Layout\Substitutes' -ErrorAction SilentlyContinue
        if ($voor) {
            $namen = @($voor.PSObject.Properties | Where-Object { $_.Name -match '^\d+$' } | Sort-Object { [int]$_.Name })
            foreach ($n in $namen) {
                $k = "$($n.Value)"
                $echt = Get-Waarde $vervang $k
                if ($echt) { $k = "$echt" }
                if ($k -match '^[0-9A-Fa-f]{8}$') {
                    $k = $k.ToUpperInvariant()
                    if (-not $klids.Contains($k)) { $klids.Add($k) }
                }
            }
        }
    }
    return $klids.ToArray()
}

function Get-Instellingen {
    # Taal, notatie, tijdzone, toetsenbord, donker/licht, muis en schaal. Wat niet te lezen is, laten we weg:
    # BugOS slaat een ontbrekend onderdeel dan over (FORMAT.md).
    $uit = [ordered]@{}
    $talen = @()
    # Get-WinUserLanguageList geeft de hele lijst als één object (een List<>) terug; ForEach-Object pakt hem uit tot
    # losse talen, anders zou $talen[0] de lijst zelf zijn en geen taal.
    try { $talen = @(Get-WinUserLanguageList -ErrorAction Stop | ForEach-Object { $_ }) } catch { Write-Verbose 'Geen taallijst.' }
    # De weergavetaal: de eerste taal in de lijst van Windows (Instellingen > Tijd en taal).
    if ($talen.Count -gt 0 -and (Get-Waarde $talen[0] 'LanguageTag')) { $uit.taal = "$($talen[0].LanguageTag)" }
    else { try { $uit.taal = (Get-UICulture).Name } catch { Write-Verbose 'Geen weergavetaal.' } }
    # De notatie (datum, getallen, valuta) staat los van de taal: iemand kan Engels lezen met een Nederlandse notatie.
    try { $uit.notatie = (Get-Culture).Name } catch { Write-Verbose 'Geen notatie.' }
    # De Windows-naam van de tijdzone (bijv. 'W. Europe Standard Time'); BugOS zet die om naar Europe/Amsterdam enz.
    try { $uit.tijdzone = [System.TimeZoneInfo]::Local.Id } catch { Write-Verbose 'Geen tijdzone.' }
    try {
        $klids = @(Get-Toetsenborden $talen)
        if ($klids.Count -gt 0) { $uit.toetsenborden = @($klids) }
    } catch { Write-Verbose 'Geen toetsenborden.' }
    # Donker of licht: AppsUseLightTheme = 0 betekent donker. Ontbreekt de waarde, dan zeggen we niets (geen gok).
    $thema = Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize' -ErrorAction SilentlyContinue
    $licht = Get-Waarde $thema 'AppsUseLightTheme'
    if ($null -ne $licht) { $uit.donker = ([int]$licht -eq 0) }
    # De muis. Het register bewaart deze waarden als tekst ("1", "10", "3").
    $muis = [ordered]@{}
    $m = Get-ItemProperty 'HKCU:\Control Panel\Mouse' -ErrorAction SilentlyContinue
    $wissel = Get-Waarde $m 'SwapMouseButtons'
    if ($null -ne $wissel) { $muis.linkshandig = ("$wissel" -eq '1') }
    $snel = 0
    if ([int]::TryParse("$(Get-Waarde $m 'MouseSensitivity')", [ref]$snel) -and $snel -ge 1 -and $snel -le 20) { $muis.snelheid = $snel }
    $bureau = Get-ItemProperty 'HKCU:\Control Panel\Desktop' -ErrorAction SilentlyContinue
    $regels = 0
    # -1 betekent in Windows 'een heel scherm per keer': dat kent BugOS niet als getal, dus dan laten we het weg.
    if ([int]::TryParse("$(Get-Waarde $bureau 'WheelScrollLines')", [ref]$regels) -and $regels -ge 1) { $muis.scrollregels = $regels }
    if ($muis.Count -gt 0) { $uit.muis = $muis }
    try { $uit.schaal = Get-SchermSchaal } catch { Write-Verbose 'Geen schaal.' }
    return $uit
}

function Get-XmlTekst([xml] $doc, [string] $naam) {
    # De tekst van het eerste element met deze naam, waar ook in het bestand. Met local-name(), zodat de
    # namespaces van Microsoft (v1, v3, v4) niet in de weg zitten.
    $knoop = $doc.SelectSingleNode("//*[local-name()='$naam']")
    if ($knoop) { return $knoop.InnerText }
    return $null
}

function Get-WifiBeveiliging([string] $auth, [string] $oneX) {
    # De 'authentication' uit het profiel in woorden die mensen (en BugOS) kennen. 'Enterprise' = school- of
    # werknetwerk met een eigen inlog (802.1X): BugOS zegt dan "log één keer in".
    $soort = switch ($auth) {
        'open'       { 'Open' }
        'shared'     { 'WEP' }
        'WPA'        { 'WPA-Enterprise' }
        'WPAPSK'     { 'WPA-Personal' }
        'WPA2'       { 'WPA2-Enterprise' }
        'WPA2PSK'    { 'WPA2-Personal' }
        'WPA3'       { 'WPA3-Enterprise' }
        'WPA3ENT'    { 'WPA3-Enterprise' }
        'WPA3ENT192' { 'WPA3-Enterprise' }
        'WPA3SAE'    { 'WPA3-Personal' }
        'OWE'        { 'OWE' }
        default      { if ($auth) { $auth } else { 'Onbekend' } }
    }
    # Een 'open' netwerk met 802.1X (oude WEP-schoolnetwerken) is toch een inlog-netwerk.
    if ($oneX -eq 'true' -and $soort -notlike '*Enterprise') { $soort = "$soort-Enterprise" }
    return $soort
}

function Get-WifiNetwerken {
    # De opgeslagen wifi-netwerken: naam, beveiliging en of het netwerk verborgen is. NOOIT de sleutel.
    # Hoe: 'netsh wlan export profile' ZONDER key=clear. Dat geeft XML-bestanden waarin de sleutel versleuteld staat
    # (alleen deze Windows kan hem lezen). We lezen er alleen naam en soort uit, in een eigen tijdelijke map op deze
    # pc (nooit op de USB-schijf), en gooien die map daarna meteen weg.
    # Waarom XML en niet de tekst van 'netsh wlan show profile': die tekst is vertaald (Nederlands, Engels, Duits...)
    # en dus lastig te lezen; de XML is overal hetzelfde.
    $netwerken = New-Object System.Collections.Generic.List[object]
    $gezien = @{}
    $tijdelijk = Join-Path ([System.IO.Path]::GetTempPath()) ('bugos-wifi-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path $tijdelijk | Out-Null
    try {
        # 1. Alles in één keer.
        $null = & netsh.exe wlan export profile "folder=$tijdelijk"
        # 2. Daarnaast elk profiel apart, in een eigen submap. Sommige Windows-versies geven elk bestand dezelfde naam
        #    (bijv. 'WiFi-.xml'), zodat stap 1 bij meer netwerken er maar één overhoudt. De namen komen uit
        #    'netsh wlan show profiles': in elke taal zijn dat regels '    <iets>  : <naam>'. Een naam met
        #    vreemde tekens kan hier verminkt zijn; die zit dan nog wel in stap 1.
        $lijst = @(& netsh.exe wlan show profiles)
        $nr = 0
        foreach ($regel in $lijst) {
            if ("$regel" -match '^\s+\S.*?\s:\s(.+?)\s*$') {
                $nr++
                $sub = Join-Path $tijdelijk "$nr"
                New-Item -ItemType Directory -Force -Path $sub | Out-Null
                $null = & netsh.exe wlan export profile "name=$($Matches[1])" "folder=$sub"
            }
        }
        foreach ($bestand in @(Get-ChildItem -LiteralPath $tijdelijk -Recurse -File -Filter '*.xml' -ErrorAction SilentlyContinue)) {
            try {
                [xml] $doc = Get-Content -LiteralPath $bestand.FullName -Raw -Encoding UTF8
                $profiel = Get-XmlTekst $doc 'name'
                # De naam van het netwerk zelf (SSID). Die kan anders zijn dan de profielnaam, en BugOS heeft de
                # SSID nodig om het netwerk te vinden. Ontbreekt hij, dan uit de hex-vorm, en anders de profielnaam.
                $ssidKnoop = $doc.SelectSingleNode("//*[local-name()='SSIDConfig']/*[local-name()='SSID']")
                $ssid = $null
                if ($ssidKnoop) {
                    $n = $ssidKnoop.SelectSingleNode("*[local-name()='name']")
                    if ($n -and $n.InnerText) { $ssid = $n.InnerText }
                    else {
                        $h = $ssidKnoop.SelectSingleNode("*[local-name()='hex']")
                        if ($h -and $h.InnerText -match '^([0-9A-Fa-f]{2})+$') {
                            $bytes = [byte[]]@(for ($i = 0; $i -lt $h.InnerText.Length; $i += 2) { [Convert]::ToByte($h.InnerText.Substring($i, 2), 16) })
                            $ssid = [System.Text.Encoding]::UTF8.GetString($bytes)
                        }
                    }
                }
                if (-not $ssid) { $ssid = $profiel }
                if (-not $ssid -or $gezien.ContainsKey($ssid)) { continue }
                $gezien[$ssid] = $true
                $netwerken.Add([ordered]@{
                    naam        = $ssid
                    beveiliging = Get-WifiBeveiliging (Get-XmlTekst $doc 'authentication') (Get-XmlTekst $doc 'useOneX')
                    verborgen   = ((Get-XmlTekst $doc 'nonBroadcast') -eq 'true')
                })
            } catch { Write-Verbose "Wifi-profiel niet te lezen: $($bestand.Name)" }
        }
    } finally {
        # Weg met de tijdelijke XML-bestanden (daar staat de versleutelde sleutel in), wat er ook gebeurde.
        Remove-Item -LiteralPath $tijdelijk -Recurse -Force -ErrorAction SilentlyContinue
    }
    return $netwerken.ToArray()
}

function Get-NetwerkPrinters {
    # Alleen printers op het netwerk (met een IP-adres of hostnaam). Een USB-printer vindt BugOS zelf als je hem
    # insteekt; 'Microsoft Print to PDF' en dergelijke hebben geen adres en vallen zo vanzelf af.
    $uit = New-Object System.Collections.Generic.List[object]
    # De standaardprinter: Get-Printer weet dat niet, WMI wel.
    $standaard = @{}
    try { foreach ($w in @(Get-CimInstance Win32_Printer -ErrorAction Stop)) { $standaard["$($w.Name)"] = [bool]$w.Default } } catch { Write-Verbose 'Geen standaardprinter bekend.' }
    foreach ($p in @(Get-Printer -ErrorAction Stop)) {
        $adres = $null
        if ("$($p.Type)" -eq 'Connection') {
            # Gedeeld via een andere pc of printserver (\\server\printer): het adres is die server.
            $adres = "$(Get-Waarde $p 'ComputerName')".Trim('\')
        } else {
            $poort = Get-PrinterPort -Name $p.PortName -ErrorAction SilentlyContinue
            $host_ = "$(Get-Waarde $poort 'PrinterHostAddress')"
            if ($host_) { $adres = $host_ }
            elseif ("$($p.PortName)" -match '^(https?|ipp)://') {
                # Een internetpoort (IPP): het adres zit in de URL.
                try { $adres = ([uri]"$($p.PortName)").Host } catch { Write-Verbose 'Geen URL.' }
            } elseif ("$($p.PortName)" -match '(?<![\d.])((\d{1,3}\.){3}\d{1,3})(?![\d.])') {
                # Een TCP/IP-poort waarvan Windows alleen de naam weet, zoals 'IP_192.168.1.40'. Geen \b: '_' telt
                # als letter, dus tussen 'IP_' en het adres zit voor de regex geen woordgrens.
                $adres = $Matches[1]
            }
        }
        if (-not $adres) { continue }
        $uit.Add([ordered]@{ naam = "$($p.Name)"; adres = $adres; standaard = [bool]$standaard["$($p.Name)"] })
    }
    return $uit.ToArray()
}

function Get-Programmas {
    # De geïnstalleerde programma's uit de Uninstall-sleutels (64-bit, 32-bit en alleen-voor-deze-gebruiker), zoals
    # 'Apps en onderdelen' ze laat zien. Weg: systeemonderdelen, updates/hotfixes, stuurprogramma's en lege namen.
    # BugOS gebruikt de lijst alleen om apps uit de Store VOOR TE STELLEN (de keuze van de eigenaar).
    $sleutels = @(
        'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
        'HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*'
    )
    $gezien = @{}
    $uit = New-Object System.Collections.Generic.List[object]
    foreach ($sleutel in $sleutels) {
        foreach ($s in @(Get-ItemProperty -Path $sleutel -ErrorAction SilentlyContinue)) {
            $naam = "$(Get-Waarde $s 'DisplayName')".Trim()
            if (-not $naam) { continue }
            if ("$(Get-Waarde $s 'SystemComponent')" -eq '1') { continue }
            # Een update hangt onder een 'ouder' (ParentKeyName) of heeft een ReleaseType.
            if (Get-Waarde $s 'ParentKeyName') { continue }
            if ("$(Get-Waarde $s 'ReleaseType')" -match 'Update|Hotfix|Service Pack') { continue }
            if ($naam -match '\bKB\d{6,}\b' -or $naam -match '^(Security )?Update for|^Hotfix for') { continue }
            # Stuurprogramma's (Windows Driver Package, '... Driver', Nederlandse Windows: 'stuurprogramma').
            if ($naam -match '(?i)\bdrivers?\b|stuurprogramma|Treiber|Windows Driver Package') { continue }
            # Dubbelen (hetzelfde programma als 32- en 64-bit, of machine en gebruiker): één keer.
            $k = $naam.ToLowerInvariant()
            if ($gezien.ContainsKey($k)) { continue }
            $gezien[$k] = $true
            $uit.Add([ordered]@{ naam = $naam; uitgever = "$(Get-Waarde $s 'Publisher')".Trim(); versie = "$(Get-Waarde $s 'DisplayVersion')".Trim() })
        }
    }
    return @($uit | Sort-Object { $_.naam })
}

function Get-ChromiumProfielen {
    # Alle profielen van Chrome, Edge en Brave die bladwijzers hebben. 'Local State' (JSON) somt de profielen op met
    # hun naam ("Persoon 1", "Werk"). We lezen dat met de JavaScriptSerializer van .NET: ConvertFrom-Json van
    # PowerShell 5.1 struikelt over sleutels die alleen in hoofdletters verschillen, en die komen in dat bestand voor.
    Add-Type -AssemblyName System.Web.Extensions
    $uit = New-Object System.Collections.Generic.List[object]
    foreach ($b in $script:ChromiumMappen.GetEnumerator()) {
        $basis = $b.Value
        if (-not (Test-Path -LiteralPath $basis)) { continue }
        $profielen = [ordered]@{}
        try {
            $lezer = New-Object System.Web.Script.Serialization.JavaScriptSerializer
            $lezer.MaxJsonLength = [int]::MaxValue
            $staat = $lezer.DeserializeObject([System.IO.File]::ReadAllText((Join-Path $basis 'Local State')))
            $cache = $staat['profile']['info_cache']
            foreach ($map in $cache.Keys) {
                $info = $cache[$map]
                $profielen[$map] = if ($info -is [System.Collections.IDictionary] -and $info.ContainsKey('name')) { "$($info['name'])" } else { $map }
            }
        } catch { Write-Verbose "Local State van $($b.Key) niet te lezen." }
        if ($profielen.Count -eq 0) {
            # Reserve: de mappen 'Default' en 'Profile 1', 'Profile 2'... (zonder naam: dan de mapnaam).
            foreach ($d in @(Get-ChildItem -LiteralPath $basis -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -eq 'Default' -or $_.Name -match '^Profile \d+$' })) {
                $profielen[$d.Name] = $d.Name
            }
        }
        foreach ($p in $profielen.GetEnumerator()) {
            $bestand = Join-Path (Join-Path $basis $p.Key) 'Bookmarks'
            if (-not (Test-Path -LiteralPath $bestand)) { continue }
            $uit.Add([pscustomobject]@{ Browser = $b.Key; Profiel = $p.Key; Naam = $p.Value; Bestand = $bestand })
        }
    }
    return $uit.ToArray()
}

function Get-FirefoxProfielen([string] $Map = $script:FirefoxMap) {
    # Alle Firefox-profielen uit profiles.ini, met de nieuwste bladwijzer-back-up (Firefox maakt die zelf elke dag,
    # als .jsonlz4) en welk profiel het standaardprofiel is. Met -Map $script:ThunderbirdMap: die van Thunderbird
    # (zelfde opbouw; daar is geen bladwijzer-back-up, dus Backup blijft leeg).
    $uit = New-Object System.Collections.Generic.List[object]
    $ini = Join-Path $Map 'profiles.ini'
    if (-not (Test-Path -LiteralPath $ini)) { return $uit.ToArray() }
    # profiles.ini in stukken [Kopje] met sleutel=waarde.
    $stukken = New-Object System.Collections.Generic.List[object]
    $huidig = $null
    foreach ($regel in (Get-Content -LiteralPath $ini -Encoding UTF8)) {
        if ($regel -match '^\s*\[(.+)\]\s*$') { $huidig = @{ '_kop' = $Matches[1] }; $stukken.Add($huidig) }
        elseif ($huidig -and $regel -match '^\s*([^=;#]+?)\s*=\s*(.*?)\s*$') { $huidig[$Matches[1]] = $Matches[2] }
    }
    # Nieuwe Firefox: het standaardprofiel staat bij [Install...] (per installatie). Oude Firefox: Default=1 bij het
    # profiel zelf. De eerste wint.
    $installStandaard = $null
    foreach ($s in $stukken) { if ($s['_kop'] -like 'Install*' -and $s['Default']) { $installStandaard = $s['Default']; break } }
    $profielen = @($stukken | Where-Object { $_['_kop'] -like 'Profile*' -and $_['Path'] })
    foreach ($s in $profielen) {
        $pad = if ($s['IsRelative'] -eq '1') { Join-Path $Map ($s['Path'] -replace '/', '\') } else { $s['Path'] }
        if (-not (Test-Path -LiteralPath $pad)) { continue }
        if ($installStandaard) { $isStandaard = ($s['Path'] -eq $installStandaard) }
        else { $isStandaard = ($s['Default'] -eq '1') -or ($profielen.Count -eq 1) }
        $backup = Get-ChildItem -LiteralPath (Join-Path $pad 'bookmarkbackups') -Filter '*.jsonlz4' -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
        $uit.Add([pscustomobject]@{
            Profiel   = Split-Path $pad -Leaf
            Naam      = if ($s['Name']) { $s['Name'] } else { Split-Path $pad -Leaf }
            Pad       = $pad
            Standaard = [bool]$isStandaard
            Backup    = if ($backup) { $backup.FullName } else { $null }
        })
    }
    return $uit.ToArray()
}

function Copy-FirefoxProfiel([string] $bron, [string] $doel) {
    # Het Firefox-profiel meenemen (geschiedenis, bladwijzers, extensies, instellingen), maar ZONDER wachtwoorden,
    # cookies en open tabbladen (die laatste bevatten inlog-sessies). Geeft de namen terug van mappen die te groot
    # waren en thuis bleven.
    $grootTeVeel = New-Object System.Collections.Generic.List[string]
    $xd = New-Object System.Collections.Generic.List[string]
    # Rommel en privé-dingen die BugOS niet nodig heeft: de cache, sessies (inlog!), crashrapporten en telemetrie.
    foreach ($n in @('cache2', 'startupCache', 'shader-cache', 'sessionstore-backups', 'crashes', 'minidumps', 'saved-telemetry-pings', 'datareporting')) { $xd.Add($n) }
    foreach ($map in @(Get-ChildItem -LiteralPath $bron -Directory -Force -ErrorAction SilentlyContinue)) {
        if ($xd.Contains($map.Name)) { continue }
        $som = (Get-ChildItem -LiteralPath $map.FullName -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
        if ($som -and $som -gt $script:FirefoxGrens) { $xd.Add($map.FullName); $grootTeVeel.Add($map.Name) }
    }
    # /XF: wachtwoorden (logins*.json, key4.db, key3.db, signons.sqlite), cookies, open tabbladen en de slotjes van
    # een draaiende Firefox. robocopy kijkt naar de bestandsnaam op elke diepte.
    $xf = @('logins.json', 'logins-backup.json', 'logins.db', 'logins.db-wal', 'logins.db-shm', 'key4.db', 'key3.db', 'signons.sqlite', 'cookies.sqlite*', 'sessionstore*', 'parent.lock', '.parentlock', 'lock')
    $argumenten = @($bron, $doel, '/E', '/R:1', '/W:1', '/XJ', '/NFL', '/NDL', '/NJH', '/NJS', '/NP', '/XF') + $xf + @('/XD') + $xd.ToArray()
    $null = & robocopy @argumenten
    if ($LASTEXITCODE -ge 16) { throw (T 'Het Firefox-profiel kopiëren lukte niet.' 'Copying the Firefox profile failed.') }
    return $grootTeVeel.ToArray()
}

function Invoke-Meenemen([string] $doelSchijf, [scriptblock] $Voortgang) {
    $doel = Join-Path $doelSchijf 'BugOS-Switch'
    New-Item -ItemType Directory -Force -Path $doel | Out-Null
    $stap = 0
    # De mappen, en daarna: extra mappen, lettertypen, e-mail, bladwijzers, het Firefox-profiel, de achtergrond, en
    # instellingen/wifi/printers/programma's.
    $aantal = $script:Mappen.Count + 7
    # Mappen waar een paar bestanden niet mee konden (open in een programma, groter dan 4 GB op FAT32, alleen in
    # OneDrive): de rest gaat gewoon door (U094).
    $script:Deels = @()
    # Wil je de bestanden die alleen in OneDrive staan niet mee (eerst downloaden duurt lang), dan slaat robocopy
    # bestanden met het kenmerk OFFLINE over (/XA:O). Windows geeft dat kenmerk aan OneDrive-bestanden die alleen in
    # de cloud staan. Wat er overblijft, staat in bugos-switch.json (cloud), zodat BugOS het kan zeggen.
    $cloudArg = @()
    if (-not $script:CloudMee) { $cloudArg = @('/XA:O') }
    foreach ($m in $script:Mappen) {
        $stap++
        $bron = Get-BekendeMap $m.Sleutel
        & $Voortgang ([int](100 * $stap / $aantal)) (T "Kopiëren: $($m.Naam)..." "Copying: $($m.Naam)...")
        if ($bron -and (Test-Path $bron)) {
            # /E alle submappen, /R:1 /W:1 niet eindeloos wachten, /XJ geen snelkoppel-lussen,
            # /XF geen Windows-hulpbestanden (die zie je anders in elke map in BugOS) (U096).
            $null = robocopy $bron (Join-Path $doel $m.Naam) /E /R:1 /W:1 /XJ /NFL /NDL /NJH /NJS /NP @cloudArg /XF desktop.ini Thumbs.db
            # robocopy: 8 = een paar bestanden niet, 16 = helemaal mislukt (bijv. de schijf is weg).
            if ($LASTEXITCODE -ge 16) { throw (T "Kopiëren van $($m.Naam) lukte niet." "Copying $($m.Naam) failed.") }
            if ($LASTEXITCODE -ge 8) { $script:Deels += $m.Naam }
        }
    }

    # Extra mappen die je zelf koos (bijvoorbeeld D:\Foto's), elk in Extra\<naam>. Een vorige keer kan andere
    # extra mappen hebben gehad: die blijven op de schijf staan, maar BugOS kijkt alleen naar wat in de JSON staat.
    $stap++
    & $Voortgang ([int](100 * $stap / $aantal)) (T 'Kopiëren: je andere mappen...' 'Copying: your other folders...')
    $extra = New-Object System.Collections.Generic.List[object]
    $gebruikt = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    foreach ($e in $script:ExtraMappen) {
        if (-not (Test-Path -LiteralPath $e)) { continue }
        $naam = Get-ExtraNaam $e $gebruikt
        $null = robocopy $e (Join-Path (Join-Path $doel 'Extra') $naam) /E /R:1 /W:1 /XJ /NFL /NDL /NJH /NJS /NP @cloudArg /XF desktop.ini Thumbs.db
        if ($LASTEXITCODE -ge 16) { throw (T "Kopiëren van $naam lukte niet." "Copying $naam failed.") }
        if ($LASTEXITCODE -ge 8) { $script:Deels += $naam }
        $extra.Add([ordered]@{ naam = $naam; map = "Extra/$naam"; van = $e })
    }

    # Je eigen lettertypen (alleen die jij installeerde, niet die van Windows).
    $stap++
    & $Voortgang ([int](100 * $stap / $aantal)) (T 'Lettertypen meenemen...' 'Taking fonts...')
    $letters = @(Get-Lettertypen)
    if ($letters.Count -gt 0) {
        $lmap = Join-Path $doel 'Lettertypen'
        New-Item -ItemType Directory -Force -Path $lmap | Out-Null
        foreach ($f in $letters) { Copy-Item -LiteralPath $f.FullName -Destination (Join-Path $lmap $f.Name) -Force -ErrorAction SilentlyContinue }
    }

    # E-mail: je Thunderbird (zonder wachtwoorden), en Outlook-mailbestanden (.pst) die niet al in Documenten staan.
    $stap++
    & $Voortgang ([int](100 * $stap / $aantal)) (T 'E-mail meenemen...' 'Taking e-mail...')
    $tbProfiel = $null
    $tb = Get-ThunderbirdProfiel
    if ($tb) {
        try {
            Copy-ThunderbirdProfiel $tb.Pad (Join-Path (Join-Path $doel 'Thunderbird') $tb.Profiel)
            $tbProfiel = "Thunderbird/$($tb.Profiel)"
        } catch { Write-Verbose 'Thunderbird niet gekopieerd.' }
    }
    $pst = New-Object System.Collections.Generic.List[string]
    $outlook = @(Get-OutlookBestanden)
    if ($outlook.Count -gt 0) {
        $omap = Join-Path $doel 'Outlook'
        New-Item -ItemType Directory -Force -Path $omap | Out-Null
        foreach ($p in $outlook) {
            # Een .pst die open is in Outlook, kan niet gekopieerd worden: dan staat hij niet in de lijst.
            try { Copy-Item -LiteralPath $p.FullName -Destination (Join-Path $omap $p.Name) -Force; $pst.Add("Outlook/$($p.Name)") }
            catch { $script:Deels += 'Outlook' }
        }
    }
    # De .pst-bestanden die al met Documenten meegingen, ook noemen: BugOS legt dan uit hoe je ze opent.
    $docs = Get-BekendeMap 'MyDocuments'
    if ($docs -and (Test-Path -LiteralPath $docs)) {
        foreach ($p in @(Get-ChildItem -LiteralPath $docs -Filter '*.pst' -Recurse -File -Force -ErrorAction SilentlyContinue)) {
            $pst.Add('Documents/' + ($p.FullName.Substring($docs.TrimEnd('\').Length + 1) -replace '\\', '/'))
        }
    }

    # Bladwijzers van ALLE profielen van Chrome, Edge en Brave (allemaal hetzelfde JSON-formaat), als
    # Bladwijzers/<Browser>-<Profiel>.json, en van Firefox de nieuwste back-up per profiel (FORMAT.md).
    $stap++
    & $Voortgang ([int](100 * $stap / $aantal)) (T 'Bladwijzers meenemen...' 'Taking bookmarks...')
    $bw = Join-Path $doel 'Bladwijzers'
    New-Item -ItemType Directory -Force -Path $bw | Out-Null
    # Namen van versie 1 (één bestand per browser) van een eerdere keer weghalen: anders zou BugOS die bladwijzers
    # twee keer binnenhalen (oud en nieuw naast elkaar).
    foreach ($oud in @('Chrome.json', 'Edge.json', 'Brave.json', 'Firefox.jsonlz4')) {
        Remove-Item -LiteralPath (Join-Path $bw $oud) -Force -ErrorAction SilentlyContinue
    }
    $browsers = New-Object System.Collections.Generic.List[object]
    try {
        foreach ($p in @(Get-ChromiumProfielen)) {
            $bestand = "$($p.Browser)-$($p.Profiel).json"
            Copy-Item -LiteralPath $p.Bestand -Destination (Join-Path $bw $bestand) -Force
            $browsers.Add([ordered]@{ browser = $p.Browser; profiel = $p.Profiel; naam = $p.Naam; bladwijzers = "Bladwijzers/$bestand" })
        }
    } catch { Write-Verbose 'Bladwijzers van Chrome/Edge/Brave niet (allemaal) gelukt.' }
    $firefox = @()
    try { $firefox = @(Get-FirefoxProfielen) } catch { Write-Verbose 'Firefox-profielen niet te lezen.' }
    foreach ($p in $firefox) {
        if (-not $p.Backup) { continue }
        try {
            $bestand = "Firefox-$($p.Profiel).jsonlz4"
            Copy-Item -LiteralPath $p.Backup -Destination (Join-Path $bw $bestand) -Force
            $browsers.Add([ordered]@{ browser = 'Firefox'; profiel = $p.Profiel; naam = $p.Naam; bladwijzers = "Bladwijzers/$bestand" })
        } catch { Write-Verbose "Bladwijzers van Firefox-profiel $($p.Profiel) niet gelukt." }
    }

    # Het standaardprofiel van Firefox (alleen als Windows Firefox heeft), zonder wachtwoorden en cookies.
    $stap++
    & $Voortgang ([int](100 * $stap / $aantal)) (T 'Firefox meenemen...' 'Taking Firefox...')
    $script:FirefoxOverslagen = @()
    $firefoxProfiel = $null
    $standaard = @($firefox | Where-Object { $_.Standaard }) | Select-Object -First 1
    if ($standaard) {
        try {
            $script:FirefoxOverslagen = @(Copy-FirefoxProfiel $standaard.Pad (Join-Path (Join-Path $doel 'Firefox') $standaard.Profiel))
            $firefoxProfiel = "Firefox/$($standaard.Profiel)"
        } catch { Write-Verbose 'Firefox-profiel niet gekopieerd.' }
    }

    # De bureaubladachtergrond, zodat BugOS meteen vertrouwd voelt.
    $stap++
    & $Voortgang ([int](100 * $stap / $aantal)) (T 'Achtergrond meenemen...' 'Taking wallpaper...')
    $achtergrond = "$env:APPDATA\Microsoft\Windows\Themes\TranscodedWallpaper"
    if (Test-Path $achtergrond) { Copy-Item -LiteralPath $achtergrond -Destination (Join-Path $doel 'achtergrond.jpg') -Force }

    # Instellingen, wifi-namen, netwerkprinters en het lijstje programma's. Elk onderdeel apart: lukt er één niet
    # (bijv. geen wifi-kaart, of de printerdienst staat uit), dan laten we alleen dat veld weg.
    $stap++
    & $Voortgang ([int](100 * $stap / $aantal)) (T 'Instellingen, wifi-namen, printers en programma''s...' 'Settings, Wi-Fi names, printers and programs...')
    $instellingen = $null; $wifi = $null; $printers = $null; $programmas = $null
    try { $instellingen = Get-Instellingen } catch { Write-Verbose 'Instellingen niet te lezen.' }
    try { $wifi = @(Get-WifiNetwerken) } catch { Write-Verbose 'Wifi niet te lezen.' }
    try { $printers = @(Get-NetwerkPrinters) } catch { Write-Verbose 'Printers niet te lezen.' }
    try { $programmas = @(Get-Programmas) } catch { Write-Verbose 'Programma''s niet te lezen.' }

    # Versie 2. De velden van versie 1 blijven precies zo, zodat een oude BugOS de schijf nog kan lezen.
    $info = [ordered]@{
        versie     = 2
        gemaakt    = (Get-Date).ToString('s')
        gebruiker  = $env:USERNAME
        computer   = $env:COMPUTERNAME
        taal       = (Get-Culture).Name
        mappen     = @($script:Mappen | ForEach-Object { $_.Naam })
        deels      = @($script:Deels)
    }
    # De nieuwe velden alleen als ze gelezen konden worden: een ontbrekend veld betekent voor BugOS "sla over en zeg
    # het". @() om de lijsten, zodat één wifi-netwerk toch een lijst blijft (en geen los object) in de JSON.
    if ($instellingen -and $instellingen.Count -gt 0) { $info.instellingen = $instellingen }
    if ($null -ne $wifi) { $info.wifi = @($wifi) }
    if ($null -ne $printers) { $info.printers = @($printers) }
    if ($null -ne $programmas) { $info.programmas = @($programmas) }
    $info.browsers = @($browsers.ToArray())
    if ($firefoxProfiel) { $info.firefox_profiel = $firefoxProfiel }
    # Bestanden slimmer (E). Elk veld alleen als er iets is: een ontbrekend veld = 'niets van dit soort'.
    if ($extra.Count -gt 0) { $info.extra = @($extra.ToArray()) }
    if ($letters.Count -gt 0) { $info.lettertypen = [ordered]@{ map = 'Lettertypen'; aantal = $letters.Count } }
    if ($tbProfiel) { $info.thunderbird_profiel = $tbProfiel }
    if ($pst.Count -gt 0) { $info.outlook = [ordered]@{ pst = @($pst.ToArray()) } }
    if ($script:Cloud -and $script:Cloud.Aantal -gt 0) {
        $info.cloud = [ordered]@{
            aantal      = $script:Cloud.Aantal
            bytes       = $script:Cloud.Bytes
            voorbeelden = @($script:Cloud.Voorbeelden)
            meegenomen  = [bool]$script:CloudMee
        }
    }
    # -Depth: standaard stopt ConvertTo-Json na 2 lagen, en de muis-instellingen zitten op laag 3.
    $info | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $doel 'bugos-switch.json') -Encoding UTF8
    & $Voortgang 100 (T 'Klaar!' 'Done!')
}

# ======================================================== 3. RUIMTE MAKEN ==

function Get-KrimpMogelijk {
    $part = Get-Partition -DriveLetter C
    $grens = Get-PartitionSupportedSize -DriveLetter C
    $kanWeg = [math]::Floor(($part.Size - $grens.SizeMin) / 1GB) - 10   # 10 GB marge voor Windows
    return [math]::Max(0.0, [double]$kanWeg)
}

function Invoke-Krimp([int] $gb) {
    $part = Get-Partition -DriveLetter C
    $nieuw = $part.Size - ([int64]$gb * 1GB)
    Resize-Partition -DriveLetter C -Size $nieuw
}

# ========================================================== 4. USB-STICK ==

function Test-UsbLetter([object] $logisch) {
    # Hangt deze schijfletter aan een USB-schijf? Eerst zoals stap 4 (Get-Disk: BusType USB, ook voor snelle
    # USB-SSD's die zich als SCSI melden) (U296); lukt dat niet (geen beheerdersrechten), dan via WMI (U284).
    try {
        $bus = (Get-Partition -DriveLetter $logisch.DeviceID.Substring(0, 1) -ErrorAction Stop | Get-Disk -ErrorAction Stop).BusType
        if ("$bus" -eq 'USB') { return $true }
        if ($bus) { return $false }
    } catch { }
    try {
        foreach ($deel in @(Get-CimAssociatedInstance -InputObject $logisch -ResultClassName Win32_DiskPartition -ErrorAction Stop)) {
            foreach ($schijf in @(Get-CimAssociatedInstance -InputObject $deel -ResultClassName Win32_DiskDrive -ErrorAction Stop)) {
                if ($schijf.InterfaceType -eq 'USB' -or "$($schijf.PNPDeviceID)" -like 'USBSTOR*' -or "$($schijf.MediaType)" -like 'External*') { return $true }
            }
        }
    } catch { }
    return $false
}

function Get-UsbSchijven {
    Get-Disk | Where-Object { $_.BusType -eq 'USB' -and $_.Size -gt 7GB -and -not $_.IsBoot -and -not $_.IsSystem }
}

function Test-SwitchBestanden([int] $nummer) {
    # Heeft een partitie op deze schijf de map BugOS-Switch met bugos-switch.json (uit stap 2)?
    foreach ($p in @(Get-Partition -DiskNumber $nummer -ErrorAction SilentlyContinue)) {
        if ("$($p.DriveLetter)" -match '^[A-Za-z]$' -and (Test-Path -LiteralPath "$($p.DriveLetter):\BugOS-Switch\bugos-switch.json")) { return $true }
    }
    return $false
}

function Write-IsoNaarSchijf([string] $iso, [int] $nummer, [scriptblock] $Voortgang, [string] $id = '') {
    $schijf = Get-Disk -Number $nummer
    if ($schijf.BusType -ne 'USB' -or $schijf.IsBoot -or $schijf.IsSystem) {
        throw (T 'Veiligheidsstop: dit is geen USB-stick.' 'Safety stop: this is not a USB stick.')
    }
    if ($id -and "$($schijf.UniqueId)" -ne $id) {
        throw (T 'Veiligheidsstop: dit is niet meer de USB-stick die je koos. Kies hem opnieuw.' 'Safety stop: this is no longer the USB stick you chose. Choose it again.')
    }
    $grootte = (Get-Item -LiteralPath $iso).Length
    if ($grootte -gt $schijf.Size) { throw (T 'De USB-stick is te klein.' 'The USB stick is too small.') }

    # Alles van de stick halen, zodat Windows hem niet meer vasthoudt.
    & $Voortgang 0 (T 'USB-stick leegmaken...' 'Erasing USB stick...')
    Clear-Disk -Number $nummer -RemoveData -RemoveOEM -Confirm:$false
    Start-Sleep -Seconds 2

    $blok = 4MB
    $buffer = New-Object byte[] $blok
    $bronStroom = [System.IO.File]::OpenRead($iso)
    $uit = New-Object System.IO.FileStream("\\.\PhysicalDrive$nummer", [System.IO.FileMode]::Open, [System.IO.FileAccess]::Write, [System.IO.FileShare]::ReadWrite, $blok, [System.IO.FileOptions]::WriteThrough)
    try {
        $geschreven = 0L
        while (($n = $bronStroom.Read($buffer, 0, $blok)) -gt 0) {
            if ($n % 512 -ne 0) {
                # Schijven willen hele sectoren: het laatste stukje aanvullen met nullen.
                $vol = [int]([math]::Ceiling($n / 512) * 512)
                [Array]::Clear($buffer, $n, $vol - $n)
                $n = $vol
            }
            $uit.Write($buffer, 0, $n)
            $geschreven += $n
            & $Voortgang ([int](100 * $geschreven / $grootte)) (T "Schrijven: $([math]::Round($geschreven / 1GB, 1)) van $([math]::Round($grootte / 1GB, 1)) GB" "Writing: $([math]::Round($geschreven / 1GB, 1)) of $([math]::Round($grootte / 1GB, 1)) GB")
        }
        $uit.Flush()
    } finally {
        $uit.Dispose()
        $bronStroom.Dispose()
    }
    Update-HostStorageCache -ErrorAction SilentlyContinue
}

# ------------------------------------------------- 4b. een stick die in Windows bruikbaar blijft --
# Vroeger schreven we de ISO 'rauw' op de stick. Dan zag Windows drie rare stukken (een ISO-deel, een opstartdeel en
# een leeg deel) en was de rest van de stick niet meer te gebruiken. Nu doen we het zoals Ventoy:
#   - deel 1: een gewone exFAT-schijf met de naam BUGOS. Windows ziet hem gewoon, met de rest van de ruimte vrij voor
#     je eigen bestanden. Hierop staat BugOS zelf (LiveOS\squashfs.img, groter dan 4 GB: daarom exFAT, geen FAT32).
#   - deel 2: een klein opstartdeel (FAT32, type EF). Daar start de computer van (shim, grub, kernel, initrd). Windows
#     laat een deel van type EF niet zien, dus je merkt er niets van.
# grub start BugOS met root=live:LABEL=BUGOS. Dat kan alleen als de ISO exFAT kan lezen: zo'n ISO heeft het merkteken
# bugos.stick=2 in grub.cfg (iso_live/src/build.sh). Een oudere ISO zonder merkteken gaat op de oude manier.
#
# De ISO lezen we zelf (ISO 9660), zonder hem in Windows te openen: de BugOS-ISO heeft geen Windows-namen (Joliet) en
# een bestand van meer dan 4 GB in stukken ('multi-extent'). Windows laat zo'n ISO niet altijd goed zien.

$script:StickLabel = 'BUGOS'
$script:EfiLabel = 'BUGOS-EFI'
$script:StickMerk = 'bugos.stick=2'

function Get-IsoNaam([byte[]] $data, [int] $i, [int] $len, [int] $naamLen) {
    # De echte naam uit Rock Ridge (NM), anders de ISO-naam zonder ';1' in kleine letters.
    $su = $i + 33 + $naamLen
    if ($naamLen % 2 -eq 0) { $su++ }
    $eind = $i + $len
    $rr = ''
    while ($su + 4 -le $eind) {
        $sig = [System.Text.Encoding]::ASCII.GetString($data, $su, 2)
        $elen = [int]$data[$su + 2]
        if ($elen -lt 4 -or $su + $elen -gt $eind) { break }
        if ($sig -eq 'NM' -and $elen -gt 5) { $rr += [System.Text.Encoding]::UTF8.GetString($data, $su + 5, $elen - 5) }
        $su += $elen
    }
    if ($rr) { return $rr }
    $naam = [System.Text.Encoding]::ASCII.GetString($data, $i + 33, $naamLen)
    return (($naam -replace ';\d+$', '').TrimEnd('.')).ToLowerInvariant()
}

function Read-IsoMap([string] $iso) {
    # Alle bestanden in de ISO: pad ('LiveOS/squashfs.img', hoofdletters tellen niet) -> stukken (begin, lengte) in bytes.
    $s = [System.IO.File]::Open($iso, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    try {
        $sector = New-Object byte[] 2048
        $pvd = $null
        for ($lba = 16; $lba -lt 64; $lba++) {
            [void]$s.Seek([int64]$lba * 2048, [System.IO.SeekOrigin]::Begin)
            if ($s.Read($sector, 0, 2048) -ne 2048) { break }
            if ([System.Text.Encoding]::ASCII.GetString($sector, 1, 5) -ne 'CD001') { break }
            if ($sector[0] -eq 1) { $pvd = $sector.Clone(); break }
            if ($sector[0] -eq 255) { break }
        }
        if ($null -eq $pvd) { throw (T 'Dit is geen BugOS-bestand (geen ISO).' 'This is not a BugOS file (not an ISO).') }
        $label = [System.Text.Encoding]::ASCII.GetString($pvd, 40, 32).Trim()
        $bestanden = @{}
        $rij = New-Object 'System.Collections.Generic.Queue[object]'
        $rij.Enqueue(@('', [BitConverter]::ToUInt32($pvd, 158), [BitConverter]::ToUInt32($pvd, 166)))
        $gezien = New-Object 'System.Collections.Generic.HashSet[uint32]'
        while ($rij.Count -gt 0) {
            $map = $rij.Dequeue()
            $pad = [string]$map[0]; $plek = [uint32]$map[1]; $lengte = [int]$map[2]
            if (-not $gezien.Add($plek) -or $lengte -le 0 -or $lengte -gt 64MB) { continue }
            $data = New-Object byte[] $lengte
            [void]$s.Seek([int64]$plek * 2048, [System.IO.SeekOrigin]::Begin)
            $gelezen = 0
            while ($gelezen -lt $lengte) {
                $n = $s.Read($data, $gelezen, $lengte - $gelezen)
                if ($n -le 0) { break }
                $gelezen += $n
            }
            $i = 0
            while ($i -lt $lengte) {
                $len = [int]$data[$i]
                if ($len -eq 0) { $i = ([int][math]::Floor($i / 2048) + 1) * 2048; continue }
                if ($len -lt 34 -or $i + $len -gt $lengte) { break }
                $naamLen = [int]$data[$i + 32]
                # \0 en \1 zijn 'deze map' en 'de map erboven'.
                if (-not ($naamLen -eq 1 -and $data[$i + 33] -le 1)) {
                    $naam = Get-IsoNaam $data $i $len $naamLen
                    $volledig = if ($pad) { "$pad/$naam" } else { $naam }
                    $extPlek = [BitConverter]::ToUInt32($data, $i + 2)
                    $extLen = [BitConverter]::ToUInt32($data, $i + 10)
                    if (([int]$data[$i + 25] -band 2) -ne 0) {
                        $rij.Enqueue(@($volledig, $extPlek, $extLen))
                    } else {
                        # Een bestand van meer dan 4 GB staat er meerdere keren, elk met het volgende stuk.
                        if (-not $bestanden.ContainsKey($volledig)) { $bestanden[$volledig] = New-Object 'System.Collections.Generic.List[object]' }
                        $bestanden[$volledig].Add(@(([int64]$extPlek * 2048), [int64]$extLen))
                    }
                }
                $i += $len
            }
        }
        return [pscustomobject]@{ Label = $label; Bestanden = $bestanden; Pad = $iso }
    } finally { $s.Dispose() }
}

function Get-IsoGrootte($kaart, [string] $naam) {
    $som = 0L
    foreach ($stuk in $kaart.Bestanden[$naam]) { $som += [int64]$stuk[1] }
    return $som
}

function Read-IsoBytes($kaart, [string] $naam) {
    $uit = New-Object System.IO.MemoryStream
    $in = [System.IO.File]::Open($kaart.Pad, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    try {
        foreach ($stuk in $kaart.Bestanden[$naam]) {
            $buf = New-Object byte[] ([int]$stuk[1])
            [void]$in.Seek([int64]$stuk[0], [System.IO.SeekOrigin]::Begin)
            $gelezen = 0
            while ($gelezen -lt $buf.Length) { $n = $in.Read($buf, $gelezen, $buf.Length - $gelezen); if ($n -le 0) { break }; $gelezen += $n }
            $uit.Write($buf, 0, $gelezen)
        }
        return $uit.ToArray()
    } finally { $in.Dispose(); $uit.Dispose() }
}

function Copy-UitIso($kaart, [string] $naam, [string] $doel, [hashtable] $teller, [scriptblock] $Voortgang) {
    # Let op: BugOS is groter dan 2 GB. Max met een klein getal (1) eerst kiest in PowerShell de Int32-versie en gaat dan stuk
    # ('Value was either too large or too small for an Int32'): rekenen met [int64] (gevonden op een echte stick).
    # Eén bestand uit de ISO naar de stick, met voortgang over het geheel ($teller.Klaar van $teller.Totaal).
    if (-not $kaart.Bestanden.ContainsKey($naam)) { throw ((T 'Er ontbreekt iets in het BugOS-bestand: ' 'Something is missing in the BugOS file: ') + $naam) }
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $doel) | Out-Null
    $in = [System.IO.File]::Open($kaart.Pad, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    $uit = New-Object System.IO.FileStream($doel, [System.IO.FileMode]::Create, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None, 4MB)
    $buffer = New-Object byte[] (4MB)
    try {
        foreach ($stuk in $kaart.Bestanden[$naam]) {
            [void]$in.Seek([int64]$stuk[0], [System.IO.SeekOrigin]::Begin)
            $rest = [int64]$stuk[1]
            while ($rest -gt 0) {
                $n = $in.Read($buffer, 0, [int][math]::Min([int64]$buffer.Length, $rest))
                if ($n -le 0) { throw (T 'Het BugOS-bestand is niet compleet. Download het opnieuw.' 'The BugOS file is incomplete. Download it again.') }
                $uit.Write($buffer, 0, $n)
                $rest -= $n
                $teller.Klaar += $n
                if ($Voortgang -and ([DateTime]::Now - $teller.Laatste).TotalMilliseconds -gt 250) {
                    $teller.Laatste = [DateTime]::Now
                    & $Voortgang ([int](100 * $teller.Klaar / [math]::Max([int64]1, [int64]$teller.Totaal))) (T "BugOS op de stick zetten: $([math]::Round($teller.Klaar / 1GB, 1)) van $([math]::Round($teller.Totaal / 1GB, 1)) GB" "Putting BugOS on the stick: $([math]::Round($teller.Klaar / 1GB, 1)) of $([math]::Round($teller.Totaal / 1GB, 1)) GB")
                }
            }
        }
        $uit.Flush($true)
    } finally { $uit.Dispose(); $in.Dispose() }
}

function ConvertTo-StickGrub([string] $tekst) {
    # De grub.cfg van de ISO, maar voor de stick: BugOS zelf op de exFAT-schijf BUGOS, en grub zoekt de kernel op het
    # opstartdeel BUGOS-EFI (niet op de ISO, die er niet is).
    $t = $tekst -replace 'root=live:CDLABEL=\S+', "root=live:LABEL=$($script:StickLabel)"
    $t = [regex]::Replace($t, "(search\b[^\r\n]*?\s(?:-l|--label)\s+)(['""]?)[^'""\s]+\2", "`$1'$($script:EfiLabel)'")
    return $t
}

function Get-IsoStickInfo([string] $iso) {
    # Kan deze ISO op een stick die in Windows bruikbaar blijft? Alleen met het merkteken en alle bestanden.
    $kaart = Read-IsoMap $iso
    $nodig = @('LiveOS/squashfs.img', 'images/pxeboot/vmlinuz', 'images/pxeboot/initrd.img', 'EFI/BOOT/BOOTX64.EFI')
    $mist = @($nodig | Where-Object { -not $kaart.Bestanden.ContainsKey($_) })
    $grub = @($kaart.Bestanden.Keys | Where-Object { $_ -like 'EFI/*/grub.cfg' })
    $merk = $false
    foreach ($g in $grub) {
        if ([System.Text.Encoding]::UTF8.GetString((Read-IsoBytes $kaart $g)) -match [regex]::Escape($script:StickMerk)) { $merk = $true }
    }
    $groot = 0L
    foreach ($n in $kaart.Bestanden.Keys) { $groot += Get-IsoGrootte $kaart $n }
    return [pscustomobject]@{ Kaart = $kaart; Bruikbaar = ($mist.Count -eq 0 -and $merk -and $grub.Count -gt 0); Mist = $mist; Grub = $grub; Grootte = $groot }
}

function Test-StickSchijf($schijf, [string] $id = '', [switch] $Test) {
    # Alleen een USB-stick (en in de zelftest op GitHub een nep-schijf uit een bestand), nooit de schijf van Windows.
    $bus = "$($schijf.BusType)"
    $mag = $bus -eq 'USB' -or ($Test -and $bus -eq 'File Backed Virtual')
    if (-not $mag -or $schijf.IsBoot -or $schijf.IsSystem) {
        throw (T 'Veiligheidsstop: dit is geen USB-stick.' 'Safety stop: this is not a USB stick.')
    }
    if ($id -and "$($schijf.UniqueId)" -ne $id) {
        throw (T 'Veiligheidsstop: dit is niet meer de USB-stick die je koos. Kies hem opnieuw.' 'Safety stop: this is no longer the USB stick you chose. Choose it again.')
    }
}

function Clear-Stick([int] $nummer) {
    # Alles van de stick af en een nieuwe, lege indeling (MBR: oudere Windows en elke computer kunnen dat lezen).
    $schijf = Get-Disk -Number $nummer
    if ($schijf.IsOffline) { Set-Disk -Number $nummer -IsOffline $false }
    if ($schijf.IsReadOnly) { Set-Disk -Number $nummer -IsReadOnly $false }
    if ("$($schijf.PartitionStyle)" -ne 'RAW') { Clear-Disk -Number $nummer -RemoveData -RemoveOEM -Confirm:$false }
    Start-Sleep -Milliseconds 800
    # Een echte USB-stick (verwisselbaar) wordt na Clear-Disk niet 'leeg' (RAW): Windows houdt hem als MBR. Dan is
    # Initialize-Disk fout ('The disk has already been initialized'). Alleen initialiseren als hij echt leeg is.
    $schijf = Get-Disk -Number $nummer
    $stijl = "$($schijf.PartitionStyle)"
    if ($stijl -eq 'RAW') {
        Initialize-Disk -Number $nummer -PartitionStyle MBR
    } elseif ($stijl -ne 'MBR') {
        Set-Disk -Number $nummer -PartitionStyle MBR
    }
    # Wat er nog aan delen staat (dat zou niet moeten), ook weg.
    foreach ($deel in @(Get-Partition -DiskNumber $nummer -ErrorAction SilentlyContinue)) {
        Remove-Partition -DiskNumber $nummer -PartitionNumber $deel.PartitionNumber -Confirm:$false -ErrorAction SilentlyContinue
    }
}

function Get-Letter([int] $nummer, [int] $deel) {
    # Een stationsletter voor een deel, pas NA het formatteren (anders vraagt Windows 'Wil je deze schijf formatteren?').
    $p = Get-Partition -DiskNumber $nummer -PartitionNumber $deel
    if (-not ("$($p.DriveLetter)" -match '^[A-Za-z]$')) {
        Add-PartitionAccessPath -DiskNumber $nummer -PartitionNumber $deel -AssignDriveLetter
    }
    for ($i = 0; $i -lt 40; $i++) {
        $letter = "$((Get-Partition -DiskNumber $nummer -PartitionNumber $deel).DriveLetter)"
        if ($letter -match '^[A-Za-z]$' -and (Test-Path -LiteralPath "$($letter):\")) { return "$($letter):\" }
        Start-Sleep -Milliseconds 250
    }
    throw (T 'Windows gaf de USB-stick geen stationsletter. Haal hem eruit, steek hem er weer in en probeer het opnieuw.' 'Windows did not give the USB stick a drive letter. Unplug it, plug it in again and try again.')
}

function Write-BugOSStick([string] $iso, [int] $nummer, [scriptblock] $Voortgang, [string] $id = '', [switch] $Test) {
    & $Voortgang -1 (T 'Het BugOS-bestand nakijken...' 'Checking the BugOS file...')
    $info = Get-IsoStickInfo $iso
    if (-not $info.Bruikbaar) { throw (T 'Deze BugOS-versie kan nog niet op een stick die bruikbaar blijft. Download de nieuwste BugOS.' 'This BugOS version cannot go on a stick that stays usable yet. Download the newest BugOS.') }
    $kaart = $info.Kaart
    $schijf = Get-Disk -Number $nummer
    Test-StickSchijf $schijf $id -Test:$Test

    # Wat er op het opstartdeel komt: de map EFI (shim, grub, MokManager) en de kernel met zijn initrd.
    $opEfi = @($kaart.Bestanden.Keys | Where-Object { $_ -like 'EFI/*' }) + @('images/pxeboot/vmlinuz', 'images/pxeboot/initrd.img')
    $efiBytes = 0L
    foreach ($n in $opEfi) { $efiBytes += Get-IsoGrootte $kaart $n }
    $efiMB = [int64][math]::Max(256.0, [math]::Ceiling(($efiBytes * 1.15 + 32MB) / 64MB) * 64)
    $squash = Get-IsoGrootte $kaart 'LiveOS/squashfs.img'
    if ($squash + $efiMB * 1MB + 256MB -gt $schijf.Size) { throw (T 'De USB-stick is te klein.' 'The USB stick is too small.') }

    & $Voortgang -1 (T 'USB-stick leegmaken...' 'Erasing USB stick...')
    Clear-Stick $nummer
    $schijf = Get-Disk -Number $nummer
    $dataBytes = [int64]$schijf.Size - $efiMB * 1MB - 8MB
    $dataBytes -= $dataBytes % 1MB
    # Eerst het grote deel (ouder Windows liet op een stick alleen het eerste deel zien), dan het opstartdeel.
    $data = New-Partition -DiskNumber $nummer -Size $dataBytes
    $efi = New-Partition -DiskNumber $nummer -UseMaximumSize -MbrType FAT32
    & $Voortgang -1 (T 'USB-stick klaarmaken...' 'Preparing the USB stick...')
    Format-Volume -Partition $data -FileSystem exFAT -NewFileSystemLabel $script:StickLabel -Confirm:$false | Out-Null
    Format-Volume -Partition $efi -FileSystem FAT32 -NewFileSystemLabel $script:EfiLabel -Confirm:$false | Out-Null
    $dataLetter = Get-Letter $nummer $data.PartitionNumber
    $efiLetter = Get-Letter $nummer $efi.PartitionNumber

    $teller = @{ Klaar = 0L; Totaal = ($squash + $efiBytes); Laatste = [DateTime]::MinValue }
    foreach ($n in $opEfi) {
        Copy-UitIso $kaart $n (Join-Path $efiLetter ($n -replace '/', '\')) $teller $Voortgang
    }
    # grub.cfg: voor de stick (BugOS op BUGOS, de kernel op BUGOS-EFI). Zonder BOM: dat leest grub niet.
    $zonderBom = New-Object System.Text.UTF8Encoding($false)
    foreach ($g in $info.Grub) {
        $tekst = ConvertTo-StickGrub ([System.Text.Encoding]::UTF8.GetString((Read-IsoBytes $kaart $g)))
        [System.IO.File]::WriteAllText((Join-Path $efiLetter ($g -replace '/', '\')), $tekst, $zonderBom)
    }
    Copy-UitIso $kaart 'LiveOS/squashfs.img' (Join-Path $dataLetter 'LiveOS\squashfs.img') $teller $Voortgang
    $uitleg = (T "Dit is je BugOS-stick.`r`n`r`nStart je computer van deze stick om BugOS te proberen of te installeren.`r`nJe kunt er gewoon ook je eigen bestanden op zetten. Laat alleen de map LiveOS staan.`r`n`r`nWil je de stick weer helemaal leeg? Gebruik 'Stick weer gewoon maken' in BugOS Switch.`r`n" "This is your BugOS stick.`r`n`r`nStart your computer from this stick to try or install BugOS.`r`nYou can also put your own files on it. Just leave the LiveOS folder alone.`r`n`r`nWant the stick completely empty again? Use 'Make stick normal again' in BugOS Switch.`r`n")
    [System.IO.File]::WriteAllText((Join-Path $dataLetter (T 'Over deze BugOS-stick.txt' 'About this BugOS stick.txt')), $uitleg, [System.Text.Encoding]::UTF8)

    & $Voortgang -1 (T 'Afronden...' 'Finishing...')
    # Het opstartdeel verbergen: type EF (EFI). Windows laat zo'n deel niet zien; de computer start er juist van.
    Remove-PartitionAccessPath -DiskNumber $nummer -PartitionNumber $efi.PartitionNumber -AccessPath $efiLetter -ErrorAction SilentlyContinue
    try {
        Set-Partition -DiskNumber $nummer -PartitionNumber $efi.PartitionNumber -MbrType 0xEF
    } catch {
        $opdracht = "select disk $nummer`r`nselect partition $($efi.PartitionNumber)`r`nset id=EF override`r`n"
        $bestand = Join-Path $env:TEMP 'bugos-switch-diskpart.txt'
        [System.IO.File]::WriteAllText($bestand, $opdracht, [System.Text.Encoding]::ASCII)
        $null = & diskpart.exe /s $bestand
        Remove-Item -LiteralPath $bestand -Force -ErrorAction SilentlyContinue
    }
    Update-HostStorageCache -ErrorAction SilentlyContinue
    & $Voortgang 100 (T 'Klaar.' 'Done.')
    return $dataLetter
}

function Reset-Stick([int] $nummer, [scriptblock] $Voortgang, [string] $id = '', [switch] $Test) {
    # 'Stick weer gewoon maken': alles eraf en één gewone schijf, zoals een nieuwe stick. Tot 32 GB FAT32 (dat lezen ook
    # tv's en autoradio's), groter exFAT.
    $schijf = Get-Disk -Number $nummer
    Test-StickSchijf $schijf $id -Test:$Test
    & $Voortgang -1 (T 'USB-stick leegmaken...' 'Erasing USB stick...')
    Clear-Stick $nummer
    $deel = New-Partition -DiskNumber $nummer -UseMaximumSize
    $soort = if ($schijf.Size -le 32GB) { 'FAT32' } else { 'exFAT' }
    & $Voortgang -1 (T 'USB-stick klaarmaken...' 'Preparing the USB stick...')
    Format-Volume -Partition $deel -FileSystem $soort -NewFileSystemLabel 'USB-STICK' -Confirm:$false | Out-Null
    $letter = Get-Letter $nummer $deel.PartitionNumber
    Update-HostStorageCache -ErrorAction SilentlyContinue
    & $Voortgang 100 (T 'Klaar.' 'Done.')
    return $letter
}

# ========================================================== DOWNLOADEN ==

$script:Repo = '253UgurSahin/BugOS'

function Test-NieuweNvidia([string] $gpu) {
    # Het Nvidia-stuurprogramma van BugOS (de 'open' versie) werkt alleen met GTX 16, RTX, MX 450 en nieuwer, en de
    # zakelijke T- en A-kaarten van die tijd. Oudere GeForce-kaarten (GTX 10, 9, 7, GT 710/1030, MX 110-350) niet (U396).
    # Per kaart kijken: een Intel Arc A770 naast een oude GTX 1060 is geen nieuwe Nvidia (U408).
    foreach ($naam in ($gpu -split ',\s*')) {
        if ($naam -notmatch 'NVIDIA') { continue }
        if ($naam -match 'RTX' -or $naam -match 'GTX\s*16\d\d' -or $naam -match 'MX\s*(4[5-9]\d|[5-9]\d\d)' -or
            $naam -match '\bT(400|500|550|600|1000|1200|2000)\b' -or $naam -match '\bA\d{3,4}\b') { return $true }
    }
    return $false
}

function Get-IsoSoort {
    $gpu = (Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name) -join ', '
    if (Test-NieuweNvidia $gpu) { 'nvidia' } else { 'main' }
}

function Get-IsoInfo([string] $soort) {
    # Zoek de nieuwste ISO-release van deze soort (tag: iso-<soort>-<datum>-<nr>).
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $releases = Invoke-RestMethod -UseBasicParsing -Uri "https://api.github.com/repos/$($script:Repo)/releases?per_page=50" -Headers @{ 'User-Agent' = 'BugOS-Switch' }
    $rel = $releases | Where-Object { $_.tag_name -like "iso-$soort-*" } | Sort-Object { [datetime]$_.published_at } -Descending | Select-Object -First 1
    if (-not $rel) { return $null }
    $jsonAsset = $rel.assets | Where-Object { $_.name -eq 'bugos-iso.json' } | Select-Object -First 1
    if (-not $jsonAsset) { return $null }
    $info = Invoke-RestMethod -UseBasicParsing -Uri $jsonAsset.browser_download_url -Headers @{ 'User-Agent' = 'BugOS-Switch' }
    $urls = @{}
    foreach ($a in $rel.assets) { $urls[$a.name] = $a.browser_download_url }
    [pscustomobject]@{ Info = $info; Urls = $urls; Versie = $rel.name }
}

function Save-BugOSIso([object] $gevonden, [string] $map, [scriptblock] $Voortgang) {
    Add-Type -AssemblyName System.Net.Http
    $info = $gevonden.Info
    $doel = Join-Path $map $info.naam
    $totaal = [int64](($info.delen | Measure-Object grootte -Sum).Sum)
    $vrij = (Get-PSDrive (Split-Path $map -Qualifier).TrimEnd(':')).Free
    # Een half bestand van een eerdere poging wordt overschreven: die ruimte telt mee (U287).
    if (Test-Path -LiteralPath $doel) { $vrij += (Get-Item -LiteralPath $doel).Length }
    if ($vrij -lt $totaal + 1GB) { throw (T "Te weinig ruimte: er is $([math]::Round($totaal / 1GB, 1)) GB nodig." "Not enough space: $([math]::Round($totaal / 1GB, 1)) GB is needed.") }

    $client = New-Object System.Net.Http.HttpClient
    $client.Timeout = [TimeSpan]::FromHours(6)
    $client.DefaultRequestHeaders.UserAgent.ParseAdd('BugOS-Switch')
    $uit = [System.IO.File]::Create($doel)
    $buffer = New-Object byte[] (1MB)
    $klaar = 0L
    $laatste = [DateTime]::MinValue
    $gelukt = $false
    try {
        foreach ($deel in $info.delen) {
            # Alle stukjes worden direct achter elkaar in één bestand geschreven.
            $antwoord = $client.GetAsync($gevonden.Urls[$deel.bestand], [System.Net.Http.HttpCompletionOption]::ResponseHeadersRead).Result
            [void]$antwoord.EnsureSuccessStatusCode()
            $stroom = $antwoord.Content.ReadAsStreamAsync().Result
            try {
                while (($n = $stroom.Read($buffer, 0, $buffer.Length)) -gt 0) {
                    $uit.Write($buffer, 0, $n)
                    $klaar += $n
                    if (([DateTime]::Now - $laatste).TotalMilliseconds -gt 300) {
                        $laatste = [DateTime]::Now
                        & $Voortgang ([int](100 * $klaar / $totaal)) (T "Downloaden: $([math]::Round($klaar / 1GB, 1)) van $([math]::Round($totaal / 1GB, 1)) GB" "Downloading: $([math]::Round($klaar / 1GB, 1)) of $([math]::Round($totaal / 1GB, 1)) GB")
                    }
                }
            } finally { $stroom.Dispose() }
        }
        $gelukt = $true
    } catch {
        # Een halve download is niets waard: weg ermee, en een gewone uitleg in plaats van een .NET-fout (U287).
        # Met de echte reden erachter (bijv. 'schijf vol', of GitHub weigert even): 'opnieuw proberen' helpt niet altijd (U298).
        $reden = if ($_.Exception.InnerException) { $_.Exception.InnerException.Message } else { $_.Exception.Message }
        throw ((T 'Het downloaden is gestopt. Is de verbinding weggevallen, of is de schijf vol? Probeer het opnieuw.' 'The download stopped. Did the connection drop, or is the disk full? Please try again.') + "`n`n($reden)")
    } finally {
        $uit.Dispose()
        $client.Dispose()
        if (-not $gelukt) { Remove-Item -LiteralPath $doel -Force -ErrorAction SilentlyContinue }
    }

    & $Voortgang -1 (T 'Controleren of alles goed is overgekomen...' 'Checking that everything arrived correctly...')
    $hash = (Get-FileHash -LiteralPath $doel -Algorithm SHA256).Hash
    if ($hash -ne $info.sha256.ToUpper()) {
        Remove-Item -LiteralPath $doel -Force
        throw (T 'Het bestand is beschadigd overgekomen. Probeer het opnieuw.' 'The file arrived damaged. Please try again.')
    }
    return $doel
}

# ============================================================= HUISSTIJL ==
# Kleuren, letters en plaatjes van BugOS, zodat dit venster eruitziet als de
# rest van BugOS. We schalen alles zelf, zodat het scherp blijft op schermen
# die op 125% of 150% staan (anders rekt Windows het venster wazig op).

try {
    Add-Type -Namespace BugOS -Name Dpi -MemberDefinition '[DllImport("user32.dll")] public static extern bool SetProcessDPIAware();' -ErrorAction Stop
    [void][BugOS.Dpi]::SetProcessDPIAware()
} catch { Write-Verbose 'Scherp schalen lukt hier niet; het venster wordt dan iets waziger.' }

$script:Schaal = 1.0
try {
    $scherm = [System.Drawing.Graphics]::FromHwnd([IntPtr]::Zero)
    $script:Schaal = [math]::Max(1.0, $scherm.DpiX / 96.0)
    $scherm.Dispose()
} catch { $script:Schaal = 1.0 }

function Px([double] $v) { [int][math]::Round($v * $script:Schaal) }
function Fx([double] $v) { [single]($v * $script:Schaal) }
function Punt([double] $x, [double] $y) { New-Object System.Drawing.PointF((Fx $x), (Fx $y)) }
function Plaats($c, [double] $x, [double] $y, [double] $b, [double] $h) { $c.SetBounds((Px $x), (Px $y), (Px $b), (Px $h)) }
function Kleur([string] $hex) { [System.Drawing.ColorTranslator]::FromHtml($hex) }

$Rood = Kleur '#DE2F3E'
$RoodBoven = Kleur '#C82434'
$RoodDruk = Kleur '#A8153A'
$RoodUit = Kleur '#F0A2A9'
$RoodZacht = Kleur '#FDE9E9'
$RoodTekst = Kleur '#C1222F'
$Koraal = Kleur '#FF5C50'
$Inkt = Kleur '#16171C'
$Grijs = Kleur '#5D6270'
$Grijs3 = Kleur '#8A8F9A'
$Lijn = Kleur '#E6E2E2'
$KnopVlak = Kleur '#F1EEEE'
$KnopBoven = Kleur '#E8E4E4'
$Goed = Kleur '#14965A'
$LetOp = Kleur '#B86E00'
$Fout = Kleur '#D3263A'
$Wit = [System.Drawing.Color]::White

# Letters in beeldpunten, zelf geschaald (zie boven).
function Letter([double] $pt, [switch] $Vet) {
    $naam = if ($Vet) { 'Segoe UI Semibold' } else { 'Segoe UI' }
    New-Object System.Drawing.Font($naam, [single]($pt * 96.0 / 72.0 * $script:Schaal), [System.Drawing.GraphicsUnit]::Pixel)
}

function Maak-Letters {
    $script:LetterGewoon = Letter 11
    $script:LetterVet = Letter 11 -Vet
    $script:LetterKlein = Letter 10
    $script:LetterKnop = Letter 10.5 -Vet
    $script:LetterStap = Letter 10.5
    $script:LetterStapNu = Letter 10.5 -Vet
    $script:LetterNoot = Letter 9
    $script:LetterOog = Letter 9 -Vet
    $script:LetterKop = Letter 20 -Vet
    $script:LetterTitel = Letter 14 -Vet
}

function Lees-Beeld([string] $tekst) {
    $bytes = [Convert]::FromBase64String(($tekst -replace '\s', ''))
    [System.Drawing.Image]::FromStream((New-Object System.IO.MemoryStream(, $bytes)))
}

function Zet-Dubbel($c) {
    # Niet knipperen bij het tekenen.
    try { $c.GetType().GetProperty('DoubleBuffered', [System.Reflection.BindingFlags]'NonPublic, Instance').SetValue($c, $true, $null) } catch { Write-Verbose 'Geen dubbele buffer.' }
}

function Rond-Pad([double] $x, [double] $y, [double] $b, [double] $h, [double] $straal) {
    $pad = New-Object System.Drawing.Drawing2D.GraphicsPath
    $d = [single]($straal * 2)
    $pad.AddArc([single]$x, [single]$y, $d, $d, [single]180, [single]90)
    $pad.AddArc([single]($x + $b - $d), [single]$y, $d, $d, [single]270, [single]90)
    $pad.AddArc([single]($x + $b - $d), [single]($y + $h - $d), $d, $d, [single]0, [single]90)
    $pad.AddArc([single]$x, [single]($y + $h - $d), $d, $d, [single]90, [single]90)
    $pad.CloseFigure()
    $pad
}

function Nieuwe-Pen($kleur, [double] $dikte) {
    $pen = New-Object System.Drawing.Pen($kleur, (Fx $dikte))
    $pen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $pen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
    $pen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
    $pen
}

function Toont-Focus($c) {
    # Alleen een focusrand als iemand met het toetsenbord werkt (net als Windows zelf).
    try { [bool]$c.GetType().GetProperty('ShowFocusCues', [System.Reflection.BindingFlags]'NonPublic, Instance').GetValue($c, $null) } catch { $false }
}

# --- knoppen: rond, rood (hoofd) of lichtgrijs (gewoon) ------------------------
function Nieuw-Knop([string] $tekst, [double] $x, [double] $y, [double] $b = 240, [string] $soort = 'gewoon', $ouder = $null) {
    if (-not $ouder) { $ouder = $vlak }
    $k = New-Object System.Windows.Forms.Button
    Plaats $k $x $y $b 42
    $k.Text = $tekst
    $k.Font = $script:LetterKnop
    $k.FlatStyle = 'Flat'
    $k.FlatAppearance.BorderSize = 0
    $k.Cursor = [System.Windows.Forms.Cursors]::Hand
    $k.Tag = @{ Soort = $soort; Boven = $false; Druk = $false }
    $k.Add_MouseEnter({ $this.Tag.Boven = $true; $this.Invalidate() })
    $k.Add_MouseLeave({ $this.Tag.Boven = $false; $this.Tag.Druk = $false; $this.Invalidate() })
    $k.Add_MouseDown({ $this.Tag.Druk = $true; $this.Invalidate() })
    $k.Add_MouseUp({ $this.Tag.Druk = $false; $this.Invalidate() })
    $k.Add_Paint({ param($s, $e) Teken-Knop $s $e })
    $ouder.Controls.Add($k)
    return $k
}

function Teken-Knop($k, $e) {
    $g = $e.Graphics
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.Clear($k.Parent.BackColor)
    $hoofd = $k.Tag.Soort -eq 'hoofd'
    if (-not $k.Enabled) {
        $vul = if ($hoofd) { $RoodUit } else { $KnopVlak }
        $tekstKleur = if ($hoofd) { $Wit } else { $Grijs3 }
    } elseif ($k.Tag.Druk) {
        $vul = if ($hoofd) { $RoodDruk } else { $Lijn }
        $tekstKleur = if ($hoofd) { $Wit } else { $Inkt }
    } elseif ($k.Tag.Boven) {
        $vul = if ($hoofd) { $RoodBoven } else { $KnopBoven }
        $tekstKleur = if ($hoofd) { $Wit } else { $Inkt }
    } else {
        $vul = if ($hoofd) { $Rood } else { $KnopVlak }
        $tekstKleur = if ($hoofd) { $Wit } else { $Inkt }
    }
    $pad = Rond-Pad 0.5 0.5 ($k.Width - 1) ($k.Height - 1) (Fx 12)
    $kwast = New-Object System.Drawing.SolidBrush($vul)
    $g.FillPath($kwast, $pad)
    $kwast.Dispose(); $pad.Dispose()
    if ($k.Focused -and (Toont-Focus $k)) {
        $pen = New-Object System.Drawing.Pen($Inkt, (Fx 2))
        $ring = Rond-Pad (Fx 1) (Fx 1) ($k.Width - (Fx 2) - 1) ($k.Height - (Fx 2) - 1) (Fx 11)
        $g.DrawPath($pen, $ring)
        $pen.Dispose(); $ring.Dispose()
    }
    $vlag = [System.Windows.Forms.TextFormatFlags]'HorizontalCenter, VerticalCenter, SingleLine, EndEllipsis'
    [System.Windows.Forms.TextRenderer]::DrawText($g, $k.Text, $k.Font, $k.ClientRectangle, $tekstKleur, $vlag)
}

# --- voortgangsbalk: rond, met een rood verloop ---------------------------------
function Nieuw-Balk([double] $x, [double] $y, [double] $b, $ouder) {
    $balk = New-Object System.Windows.Forms.Panel
    Plaats $balk $x $y $b 12
    # Bezig: geen procent bekend (bijv. 'kijken wat er mee gaat'): dan schuift er een stukje heen en weer (Fase 0..1).
    $balk.Tag = @{ Waarde = 0.0; Bezig = $false; Fase = 0.0 }
    Zet-Dubbel $balk
    $balk.Add_Paint({ param($s, $e) Teken-Balk $s $e })
    $ouder.Controls.Add($balk)
    return $balk
}

function Zet-Balk($balk, [double] $waarde) {
    $balk.Tag.Waarde = [math]::Max(0.0, [math]::Min(100.0, $waarde))
    $balk.Invalidate()
    $balk.Update()
}

function Teken-Balk($balk, $e) {
    $g = $e.Graphics
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.Clear($balk.Parent.BackColor)
    $b = $balk.Width - 1; $h = $balk.Height - 1
    $spoor = Rond-Pad 0 0 $b $h ($h / 2)
    $kwast = New-Object System.Drawing.SolidBrush($KnopVlak)
    $g.FillPath($kwast, $spoor)
    $kwast.Dispose(); $spoor.Dispose()
    if ($balk.Tag.Bezig) {
        # Een stukje van een kwart dat van links naar rechts loopt: er gebeurt iets, ook al weten we niet hoeveel.
        $stuk = [math]::Max($h * 3, $b * 0.25)
        $x = ($b + $stuk) * $balk.Tag.Fase - $stuk
        $links = [math]::Max(0.0, $x); $rechts = [math]::Min([double]$b, $x + $stuk)
        if ($rechts - $links -ge $h) {
            $vak = New-Object System.Drawing.RectangleF([single]$links, 0, [single]($rechts - $links), [single]$h)
            $verloop = New-Object System.Drawing.Drawing2D.LinearGradientBrush($vak, $Koraal, $Rood, [single]0)
            $deel = Rond-Pad $links 0 ($rechts - $links) $h ($h / 2)
            $g.FillPath($verloop, $deel)
            $verloop.Dispose(); $deel.Dispose()
        }
        return
    }
    $vol = $b * $balk.Tag.Waarde / 100.0
    if ($vol -ge $h) {
        $vak = New-Object System.Drawing.RectangleF(0, 0, [single]$vol, [single]$h)
        $verloop = New-Object System.Drawing.Drawing2D.LinearGradientBrush($vak, $Koraal, $Rood, [single]0)
        $stuk = Rond-Pad 0 0 $vol $h ($h / 2)
        $g.FillPath($verloop, $stuk)
        $verloop.Dispose(); $stuk.Dispose()
    }
}

# --- plaatjes (in het script zelf, zodat één bestand genoeg is) ----------------
$script:IcoonBeeld = Lees-Beeld @'
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
'@

$script:LogoBeeld = Lees-Beeld @'
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
SUVORK5CYII=
'@

$script:ZijBeeld = Lees-Beeld @'
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
j3Mlr1LRzZtXBKO341CTXdqTsfrsvqz09jOX7OUcuBtxMlrZLlXov7Z07DLO7r1PEw68U/1mtZitZqtZitYi2bLbI9H7L4Xs+HW4
uS710uWP/Vf3meZmpWWquCzlJpJebPf0YeOEwNWGhtXBR9X1Kct1NNPB4+2dz/Slhitka7XoYbXuYx6GbLdLc590tzXdLQtwfA/8
lx+jDNZ1p89n/Vav7L5l96m3JlLldR7D2fwHuHAKoyjlbb+LZ6vZfJZG2x6Gizr0Mtr0OLe7uvS6zGSRltZhukarZas590i0YZMt
0j3fsXwn3ThT4jbDK7Eru5/lr6frv+h5Hg3DZcX47Tg8n2bfNY10gt/4+Z9XUIwgoxSUUskl0Rjz56nWL+Px7vaqNFWhrWQuRyWu
6YlSFNDZleXJFLW0x0/KNj30PT4erscDVV/jBZnnKa+2xtVW/NNJ/qeom/I+uzflniY/OTPYZbH5mmwyWMrG+TNYzdwCrnx9t7Wk
IZL1f9I59jO7wGrs+FSte9k2/ktP5GV1E+Lj25Z/jfPZmS1mq1mO1ozj1Mma1mK1vVmqxlcDR71xfD09HNN+i1f7Ftua49spjPt6
vB0e68Moo6xgs/Xd/UrY+pqseepktZz7e9cZjNRjte5iuehrtZhueheOXNs9n8N7z7QVyks4Up2v5aL6nsbGcX2Uw3Jw6/Fta2z5
V6R/t/Q7Fr0MOS7yen4fH04pf37ZLpGG5mu56mC5+ZETmx3y3PU+xmC5MFiOITT5rZdnDP8AxW/1/Y8lYpTmoRWcpPJLxZ9OwWEj
geF0YOP/AKoKLfi+v1zM+bLWOkeNh2z7foWPQx2s1Wsw3M546s2S576nPulua7pbisDgp8T4xh8DXnnbNJvwju3+mZfenPlu3T2v
sRwt4bg8uIWR/FxTzj5QW36vN/oenaZeuqFNMKqoqMIRUYxXRLRA0efll2u3o8fH1xkKaFSzHyQmS1M7W+OJLQZMZk8iOVlGun5Z
4RX2nFlLpCLl9vud2xnN4FWn7xc14QT+p0p75n1+Xy/LPHx1x/8ArNZ4GOxmqx7syWZaiGbLa9Gz12Eq7DhuHq6xgs/Xdnlaqu3x
1NK155pfU9lZvoVzvxHX4GP/AGyZbXoY7Wa7WYbWVjrzZbWdH2ap5+JXXvauGS9W/wCEzmW7HpPZujk4RO5722N5+S0/kjO/ieJh
25p/nt0LHuY7Xqa7TFa9zKPWzY7XqzBc3r1Nlr3KcPw/vnG8Nh2s4ysTl6LV/sXnqbclxuVmMe1wGG9z4Ph8NlrGC5vV6v6sra9z
Za9zFd1OTe3vXGYySfTFc2mc659Ddc/A5173Lxycjb7NYP332npbjnChO6Xy2+rR9Bs6nnfYnCcnDcTjpLvWz7OL/wBY/wBv6Hob
Tl5ct5OrxsOvHv8AbHa9DBczbczn3PcrDNhueuZ6v2B4bzTxPFbI7fg1N/rJ/sjyNrbeUU228kvFn1zg3DlwvgOFwX5oQXO/GT1b
/VmfPlrHX7PHw7Z7/TW4lJLIa1oUkjitejMSJLQU0x010Kcpna3xxLyYZDOUOXIjadPzLwavk4RGX+cpS+32NFngWwlfY8Mor2ar
WZWw+w+9vy7HHrhIyW/MyWmuwx2loyzaOCV9pxyDy0rjKf0y+56Wzqcf2bqztxN2WyjBfv8Awdie2plnfb0/Dx1xb/bJa9zFabLf
MxW7CLZsdzyzPa4Cl4bg+Gpy1Vaz9Xr9zx9VPvGPpo6zmo/qz3diS0W3QpyX4jr/AOOw/wC2THbpoYbjdd1MFuzKR2ZxhuZ1PZPD
uzi12Ja0qryXrJ/wmcq96M9T7J4fs+CWX5a22v8ARafyOS6wR4nH25p/nt1bTDczdat2YLjmj1eRgv6nMve7OjdsU4XhPfvaHB4V
rOM7E5ei1f0Rfeptx5423UfQOF4P3DgOFwuWThWub/s9X9WWtzNlmufQx27M4d7u3p3HU1GC97nOvbyZ0Lupzb9S8c2cbPZbAf8A
Ie1mHjKOddL7afpHZfrkfVWvM8l7AYDk4fiuIzjrbNVwf+sd/q/oewa8ji58t5OvxsNY7/ZTQuWiHS2EzRha68cSGs2RkMyDIptt
ovLUnl0L5eQZEbTp/9k=
'@

# ==================================================== beheerder-taken =====
# Het programma start zichzelf opnieuw als beheerder voor stap 3 en 4.

# Windows en BugOS naast elkaar: Windows houdt de klok van de pc in de lokale tijd, BugOS (zoals Linux) in UTC. Dan loopt
# na elke wissel de klok aan een kant 1 of 2 uur verkeerd. Windows ook UTC laten gebruiken (U446). Bij 'Ruimte maken' en
# bij het maken van de USB-stick (die stap doet iedereen, ook wie BugOS op een tweede schijf zet) (U453).
# Onschuldig als Windows later alleen draait (Windows 10/11 kunnen dit gewoon).
function Set-KlokUtc {
    try { Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\TimeZoneInformation' -Name 'RealTimeIsUniversal' -Value 1 -Type DWord -ErrorAction Stop } catch { Write-Verbose 'Klok niet op UTC gezet.' }
    # Windows 'Snel opstarten' uit: dan laat 'Afsluiten' de Windows-schijf half in slaap achter. BugOS opent die schijf, en
    # wat je daar neerzet, kan bij de volgende Windows-start verdwijnen of de schijf beschadigen (U535).
    try { Set-ItemProperty -Path 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Power' -Name 'HiberbootEnabled' -Value 0 -Type DWord -ErrorAction Stop } catch { Write-Verbose 'Snel opstarten niet uitgezet.' }
}

function Schrijf-Voortgang([string] $pad, [hashtable] $staat) {
    # Voortgang voor het hoofdvenster: eerst een tijdelijk bestand, dan in één keer op zijn plek (nooit half te lezen).
    if (-not $pad) { return }
    try {
        [System.IO.File]::WriteAllText("$pad.tmp", ($staat | ConvertTo-Json -Compress), [System.Text.Encoding]::UTF8)
        Move-Item -LiteralPath "$pad.tmp" -Destination $pad -Force
    } catch { Write-Verbose 'Voortgang niet geschreven.' }
}

if ($Taak -in 'Krimp', 'Usb', 'Herstel') {
    # Een beheerder-taak draait onzichtbaar; het hoofdvenster laat de voortgang zien (uit $VoortgangBestand).
    $script:LaatsteMelding = [DateTime]::MinValue
    $script:LaatsteStap = ''
    $melden = {
        param($p, $t)
        if ($t) { $script:LaatsteStap = $t }
        if (([DateTime]::Now - $script:LaatsteMelding).TotalMilliseconds -ge 200 -or $p -ge 100) {
            $script:LaatsteMelding = [DateTime]::Now
            Schrijf-Voortgang $VoortgangBestand @{ p = $p; t = $t }
        }
    }
    # Terwijl de stick wordt leeggemaakt en ingedeeld, ziet Windows heel even een deel zonder bestandssysteem en vraagt
    # dan 'Je moet de schijf formatteren. Wil je dat?'. Die vraag komt van de dienst ShellHWDetection (automatisch
    # afspelen): die zetten we zolang even stil, en daarna weer aan.
    $hwStil = $false
    if ($Taak -in 'Usb', 'Herstel') {
        try {
            $hw = Get-Service -Name 'ShellHWDetection' -ErrorAction Stop
            if ($hw.Status -eq 'Running') { Stop-Service -Name 'ShellHWDetection' -Force -ErrorAction Stop; $hwStil = $true }
        } catch { Write-Verbose 'Automatisch afspelen niet stilgezet.' }
    }
    try {
        switch ($Taak) {
            'Krimp' {
                & $melden -1 (T 'Windows kleiner maken... Dit kan een paar minuten duren.' 'Shrinking Windows... This can take a few minutes.')
                Invoke-Krimp $KrimpGB
                Set-KlokUtc
            }
            'Usb' {
                if ($Manier -eq 'heel') { Write-IsoNaarSchijf $IsoPad $SchijfNummer $melden $SchijfId }
                else { [void](Write-BugOSStick $IsoPad $SchijfNummer $melden $SchijfId -Test:$TestSchijf) }
                Set-KlokUtc
            }
            'Herstel' { [void](Reset-Stick $SchijfNummer $melden $SchijfId -Test:$TestSchijf) }
        }
        Schrijf-Voortgang $VoortgangBestand @{ p = 100; t = ''; klaar = $true }
        exit 0
    } catch {
        # Waar het misging (de stap en de regel), zodat we het kunnen vinden als het op een echte stick misgaat.
        $fout = $_.Exception.Message
        if ($script:LaatsteStap) { $fout += "`n" + (T 'Bij: ' 'During: ') + $script:LaatsteStap }
        $fout += " (r. $($_.InvocationInfo.ScriptLineNumber))"
        if ($VoortgangBestand) { Schrijf-Voortgang $VoortgangBestand @{ p = 0; t = ''; fout = $fout; klaar = $true } }
        else { Toon $fout 'Error' }
        exit 1
    } finally {
        if ($hwStil) { try { Start-Service -Name 'ShellHWDetection' -ErrorAction Stop } catch { Write-Verbose 'Automatisch afspelen niet weer aangezet.' } }
    }
}

# ================================================================ VENSTER ==
# Links een donkere zijbalk met het logo en de stappen, rechts de inhoud.

if ($Taak -eq 'Foto' -and $FotoSchaal -gt 0) {
    $script:Schaal = $FotoSchaal
} else {
    # Past het venster niet op het scherm? Dan alles iets kleiner maken.
    $werk = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
    $past = [math]::Min(($werk.Width - 40) / 880.0, ($werk.Height - 70) / 560.0)
    if ($script:Schaal -gt $past) { $script:Schaal = [math]::Max(1.0, $past) }
}
Maak-Letters
$script:Breedte = 548   # breedte van de inhoud (zonder schaal)

$form = New-Object System.Windows.Forms.Form
$form.Text = "BugOS Switch $($script:Versie)"
$form.AutoScaleMode = 'None'
$form.Font = $script:LetterGewoon
$form.ClientSize = New-Object System.Drawing.Size((Px 880), (Px 560))
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedSingle'
$form.MaximizeBox = $false
$form.BackColor = $Wit
$form.ForeColor = $Inkt
try { $form.Icon = [System.Drawing.Icon]::FromHandle(([System.Drawing.Bitmap]$script:IcoonBeeld).GetHicon()) } catch { Write-Verbose 'Geen icoon.' }

$zij = New-Object System.Windows.Forms.Panel
Plaats $zij 0 0 240 560
$zij.BackColor = $Inkt
Zet-Dubbel $zij
$zij.Add_Paint({ param($s, $e) Teken-Zijbalk $s $e })
$form.Controls.Add($zij)

$stapLabel = New-Object System.Windows.Forms.Label
Plaats $stapLabel 280 36 560 20
$stapLabel.ForeColor = $Rood
$stapLabel.Font = $script:LetterOog
$form.Controls.Add($stapLabel)

$kop = New-Object System.Windows.Forms.Label
Plaats $kop 280 58 560 44
$kop.Font = $script:LetterKop
$kop.ForeColor = $Inkt
$form.Controls.Add($kop)

$vlak = New-Object System.Windows.Forms.Panel
Plaats $vlak 280 116 568 352
$vlak.AutoScroll = $true
$form.Controls.Add($vlak)

$streep = New-Object System.Windows.Forms.Panel
Plaats $streep 240 484 640 1
$streep.BackColor = $Lijn
$form.Controls.Add($streep)

$terug = Nieuw-Knop (T 'Terug' 'Back') 280 501 130 'gewoon' $form
$verder = Nieuw-Knop (T 'Volgende' 'Next') 710 501 130 'hoofd' $form
$form.AcceptButton = $verder

# ============================================================ ACHTERGROND ==
# Het venster liep vast: alles (kijken wat er mee gaat, kopiëren, downloaden, controleren, de stick maken) gebeurde in
# het venster zelf. Dan tekent Windows het niet meer en zegt het 'Reageert niet'. Nu loopt zwaar werk ernaast:
#   - Start-Werk: in een eigen 'runspace' (een tweede PowerShell in hetzelfde programma), met de functies hierboven;
#   - Start-BeheerderTaak: als beheerder (stap 3 en 4), onzichtbaar; die schrijft zijn voortgang in een bestand.
# Een klokje kijkt elke 0,12 seconde hoe ver het is: de balk beweegt (ook als we niet weten hoeveel procent), de tekst
# zegt wat er gebeurt, en Terug/Volgende staan uit zolang er iets loopt dat je niet mag onderbreken.

$script:Werken = New-Object System.Collections.ArrayList
$script:InTik = $false
$script:PaginaTeller = 0
$script:FunctieTekst = ''
$script:WerkKlok = New-Object System.Windows.Forms.Timer
$script:WerkKlok.Interval = 120
$script:WerkKlok.Add_Tick({ Verwerk-Werken })

function Get-FunctieTekst {
    # De functies van dit programma (alles tussen Set-StrictMode en de beheerder-taken), voor in de runspace. De
    # eindmarkering staat hier niet letterlijk: dan zou deze regel zelf als einde gevonden worden.
    if (-not $script:FunctieTekst) {
        $code = [System.IO.File]::ReadAllText($PSCommandPath, [System.Text.Encoding]::UTF8)
        $eind = '# ' + ('=' * 52) + ' beheerder' + '-taken'
        $van = $code.IndexOf('Set-StrictMode')
        $script:FunctieTekst = $code.Substring($van, $code.IndexOf($eind) - $van).Replace('[System.Windows.Forms.Application]::EnableVisualStyles()', '')
    }
    return $script:FunctieTekst
}

function Test-Bezig {
    $lijst = $script:Werken.ToArray()
    for ($i = 0; $i -lt $lijst.Length; $i++) { if ($lijst[$i].Blokkeer) { return $true } }
    return $false
}

function Zet-Navigatie {
    $bezig = Test-Bezig
    $terug.Enabled = ($script:Pagina -gt 0) -and -not $bezig
    $verder.Enabled = -not $bezig
    $terug.Invalidate(); $verder.Invalidate()
}

function Start-Werk([scriptblock] $Werk, [hashtable] $Mee = @{}, [scriptblock] $Klaar, $Balk = $null, $Label = $null,
                    [string] $Tekst = '', [switch] $Blokkeer, [string[]] $TerugVars = @()) {
    # $Werk draait in de runspace; daar heet wat je meegeeft $Mee. Klaar krijgt de staat: .Uitkomst, .Fout, .Terug.
    # Zonder -Blokkeer mag je weg van de pagina: dan wordt Klaar niet meer aangeroepen (de pagina is er niet meer).
    $staat = [hashtable]::Synchronized(@{ Procent = -1; Tekst = $Tekst; Klaar = $false; Fout = $null; Uitkomst = $null
                                          Terug = @{}; TerugNamen = $TerugVars; Werk = $Werk.ToString() })
    $rs = [runspacefactory]::CreateRunspace()
    $rs.ApartmentState = 'STA'   # Shell.Application (de map Downloads, BitLocker) wil STA
    $rs.ThreadOptions = 'ReuseThread'
    $rs.Open()
    $rs.SessionStateProxy.SetVariable('Staat', $staat)
    $rs.SessionStateProxy.SetVariable('Mee', $Mee)
    $rs.SessionStateProxy.SetVariable('BugOSNL', $script:NL)
    $ps = [powershell]::Create()
    $ps.Runspace = $rs
    $start = @'
$script:NL = $BugOSNL
if ($Mee.ContainsKey('ExtraMappen')) { $script:ExtraMappen.Clear(); foreach ($e in $Mee.ExtraMappen) { [void]$script:ExtraMappen.Add($e) } }
if ($Mee.ContainsKey('CloudMee')) { $script:CloudMee = $Mee.CloudMee }
if ($Mee.ContainsKey('Cloud')) { $script:Cloud = $Mee.Cloud }
# (Altijd $Staat['...'] en nooit $Staat.Naam: een gedeelde hashtable met een punt geeft in Windows PowerShell 5.1
# 'Argument types do not match'.)
$Voortgang = { param($p, $t) $Staat['Procent'] = $p; if ($t) { $Staat['Tekst'] = $t } }
try {
    $Staat['Uitkomst'] = & ([scriptblock]::Create($Staat['Werk']))
} catch {
    $Staat['Fout'] = $_.Exception.Message
}
$terugNaar = @{}
foreach ($naam in $Staat['TerugNamen']) { $terugNaar[$naam] = Get-Variable -Name $naam -Scope Global -ValueOnly -ErrorAction SilentlyContinue }
$Staat['Terug'] = $terugNaar
$Staat['Klaar'] = $true
'@
    [void]$ps.AddScript((Get-FunctieTekst) + "`n" + $start)
    $handle = $ps.BeginInvoke()
    [void]$script:Werken.Add(@{ Soort = 'runspace'; Staat = $staat; PS = $ps; RS = $rs; Handle = $handle; Klaar = $Klaar
                         Balk = $Balk; Label = $Label; Blokkeer = [bool]$Blokkeer; Pagina = $script:PaginaTeller })
    if ($Balk) { $Balk.Visible = $true; $Balk.Tag.Bezig = $true }
    if ($Label -and $Tekst) { $Label.Text = $Tekst }
    $script:WerkKlok.Start()
    Zet-Navigatie
}

function Start-BeheerderTaak([string[]] $Argumenten, [scriptblock] $Klaar, $Balk = $null, $Label = $null, [string] $Tekst = '') {
    # Stap 3 en 4 als beheerder: Windows vraagt eerst toestemming. Het proces draait onzichtbaar; het hoofdvenster
    # leest zijn voortgang. Geeft $false als je 'Nee' zei op de vraag van Windows.
    $bestand = Join-Path $env:TEMP ('bugos-switch-' + [guid]::NewGuid().ToString('N') + '.json')
    $alles = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-File', "`"$PSCommandPath`"") + $Argumenten + @('-VoortgangBestand', "`"$bestand`"")
    if ((Test-Path variable:Taal) -and $Taal) { $alles += @('-Taal', $Taal) }
    try {
        if (Test-Beheerder) {
            # Al beheerder (bijv. 'Als administrator uitvoeren'): dan niet nog eens om toestemming vragen.
            $p = Start-Process -FilePath 'powershell.exe' -ArgumentList $alles -WindowStyle Hidden -PassThru
        } else {
            $p = Start-Process -FilePath 'powershell.exe' -ArgumentList $alles -Verb RunAs -WindowStyle Hidden -PassThru
        }
        $null = $p.Handle   # anders kent Windows PowerShell de afsluitcode straks soms niet
    } catch {
        return $false
    }
    [void]$script:Werken.Add(@{ Soort = 'proces'; Proces = $p; Bestand = $bestand; Klaar = $Klaar; Balk = $Balk; Label = $Label
                         Blokkeer = $true; Pagina = $script:PaginaTeller; Laatst = $null })
    if ($Balk) { $Balk.Visible = $true; $Balk.Tag.Bezig = $true }
    if ($Label -and $Tekst) { $Label.Text = $Tekst }
    $script:WerkKlok.Start()
    Zet-Navigatie
    return $true
}

function Lees-Voortgang([string] $bestand) {
    if (-not (Test-Path -LiteralPath $bestand)) { return $null }
    try { return ([System.IO.File]::ReadAllText($bestand, [System.Text.Encoding]::UTF8) | ConvertFrom-Json) } catch { return $null }
}

function Verwerk-Werken {
    # Elke 0,12 seconde: de balk en de tekst bijwerken, en wat klaar is afronden. Niet twee keer tegelijk (een vraag of
    # melding van een Klaar laat het klokje doortikken).
    # (Een 'for' over een kopie, en de foreach/try/finally uit elkaar: Windows PowerShell 5.1 gaf 'Argument types do
    # not match' op 'foreach ($w in @($script:Werken))' binnen try/finally in het klokje.)
    if ($script:InTik) { return }
    $script:InTik = $true
    $lijst = $script:Werken.ToArray()
    for ($i = 0; $i -lt $lijst.Length; $i++) {
        try {
            Verwerk-Een $lijst[$i]
        } catch {
            # Een fout hier mag het venster niet laten hangen. In de zelftest: precies zeggen waar (en dan echt fout).
            if ((Test-Path variable:Taak) -and $Taak -eq 'Zelftest') {
                [Console]::WriteLine("FOUT in het klokje: $($_.Exception.Message)`n$($_.InvocationInfo.PositionMessage)")
                $script:InTik = $false
                throw
            }
            Write-Verbose "Klokje: $($_.Exception.Message)"
        }
    }
    $script:InTik = $false
    if ($script:Werken.Count -eq 0) { $script:WerkKlok.Stop() }
    Zet-Navigatie
}

function Verwerk-Een($w) {
    $p = -1.0; $t = ''; $af = $false
    if ($w.Soort -eq 'runspace') {
        # Met ['...']: een gedeelde (Synchronized) hashtable niet met een punt lezen (Windows PowerShell 5.1).
        $gedeeld = $w.Staat
        $p = [double]$gedeeld['Procent']; $t = [string]$gedeeld['Tekst']
        $af = [bool]$gedeeld['Klaar']
        if (-not $af) { $af = [bool]$w.Handle.IsCompleted }
    } else {
        $v = Lees-Voortgang $w.Bestand
        if ($v) {
            $w.Laatst = $v
            $vp = Get-Waarde $v 'p'
            if ($null -ne $vp) { $p = [double]$vp }
            $t = [string](Get-Waarde $v 't')
        }
        $af = [bool]$w.Proces.HasExited
    }
    if ($w.Balk) {
        if ($p -ge 0) { $w.Balk.Tag.Bezig = $false; Zet-Balk $w.Balk $p }
        else { $w.Balk.Tag.Bezig = $true; $w.Balk.Tag.Fase = ([double]$w.Balk.Tag.Fase + 0.022) % 1.0; $w.Balk.Invalidate() }
    }
    if ($w.Label -and $t) { $w.Label.Text = $t }
    if ($af) {
        [void]$script:Werken.Remove($w)
        Rond-Af $w
    }
}

function Rond-Af($w) {
    if ($w.Balk) { $w.Balk.Tag.Bezig = $false; $w.Balk.Invalidate() }
    if ($w.Soort -eq 'runspace') {
        # Een gewone kopie voor Klaar (daar mag dan gewoon $staat.Fout).
        $gedeeld = $w.Staat
        $staat = @{}
        foreach ($k in @('Procent', 'Tekst', 'Klaar', 'Fout', 'Uitkomst', 'Terug', 'TerugNamen', 'Werk')) { $staat[$k] = $gedeeld[$k] }
        try { [void]$w.PS.EndInvoke($w.Handle) } catch { if (-not $staat['Fout']) { $staat['Fout'] = $_.Exception.Message } }
        if (-not $staat['Klaar'] -and -not $staat['Fout'] -and $w.PS.Streams.Error.Count -gt 0) { $staat['Fout'] = "$($w.PS.Streams.Error[0])" }
        if ($null -eq $staat['Terug']) { $staat['Terug'] = @{} }
        $w.PS.Dispose(); $w.RS.Dispose()
    } else {
        $v = Lees-Voortgang $w.Bestand
        if (-not $v) { $v = $w.Laatst }
        Remove-Item -LiteralPath $w.Bestand, "$($w.Bestand).tmp" -Force -ErrorAction SilentlyContinue
        $code = -1
        try { $code = $w.Proces.ExitCode } catch { $code = -1 }
        # (Niet $fout: zo heet ook de rode kleur, en de Klaar hieronder ziet de namen van deze functie.)
        $foutTekst = [string](Get-Waarde $v 'fout')
        if ($code -ne 0 -and -not $foutTekst) { $foutTekst = T 'Dat lukte niet (de taak stopte zonder uitleg).' 'That did not work (the task stopped without explanation).' }
        $staat = @{ Code = $code; Fout = $foutTekst }
    }
    # Weg van de pagina (alleen bij werk dat je mocht onderbreken): de knoppen van toen zijn er niet meer.
    if (-not $w.Blokkeer -and $w.Pagina -ne $script:PaginaTeller) { return }
    if ($w.Klaar) {
        try { & $w.Klaar $staat } catch { Toon $_.Exception.Message 'Error' }
    }
}

$form.Add_FormClosing({
    param($s, $e)
    if (-not (Test-Bezig)) { return }
    $lijst = $script:Werken.ToArray()
    $proces = $false
    for ($i = 0; $i -lt $lijst.Length; $i++) { if ($lijst[$i].Soort -eq 'proces') { $proces = $true } }
    if ($proces) {
        # De stick wordt gemaakt (of Windows kleiner): halverwege stoppen kan de stick of de schijf beschadigen.
        Toon (T 'Even wachten: dit is nog bezig. Halverwege stoppen kan je USB-stick of schijf beschadigen.' 'Please wait: this is still running. Stopping halfway can damage your USB stick or disk.') 'Warning'
        $e.Cancel = $true
        return
    }
    if (-not (Vraag (T 'Er loopt nog iets (kopiëren of downloaden). Toch stoppen? Wat er al staat, blijft staan.' 'Something is still running (copying or downloading). Stop anyway? What is already there stays.'))) { $e.Cancel = $true; return }
    for ($i = 0; $i -lt $lijst.Length; $i++) { if ($lijst[$i].Soort -eq 'runspace') { try { $lijst[$i].PS.Stop() } catch { Write-Verbose 'Stoppen lukte niet.' } } }
})

function Teken-Zijbalk($zij, $e) {
    $g = $e.Graphics
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.DrawImage($script:ZijBeeld, 0, 0, $zij.Width, $zij.Height)
    $g.DrawImage($script:LogoBeeld, (Fx 28), (Fx 32), (Fx 118), (Fx 32))

    $namen = @((T 'Welkom' 'Welcome'), (T 'Controleren' 'Check'), (T 'USB-stick maken' 'Make USB stick'), (T 'Bestanden meenemen' 'Take your files'), (T 'Waar komt BugOS?' 'Where does BugOS go?'))
    $vlag = [System.Windows.Forms.TextFormatFlags]'VerticalCenter, SingleLine, EndEllipsis, NoPadding'
    for ($i = 0; $i -lt $namen.Count; $i++) {
        $y = 116 + $i * 50
        $klaar = $i -lt $script:Pagina
        $nu = $i -eq $script:Pagina
        if ($nu) {
            $pil = Rond-Pad (Fx 16) (Fx ($y - 8)) (Fx 208) (Fx 42) (Fx 12)
            $kwast = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(34, 255, 255, 255))
            $g.FillPath($kwast, $pil)
            $kwast.Dispose(); $pil.Dispose()
        }
        if ($i -lt $namen.Count - 1) {
            $pen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(70, 255, 255, 255), (Fx 2))
            $g.DrawLine($pen, (Punt 41 ($y + 31)), (Punt 41 ($y + 45)))
            $pen.Dispose()
        }
        if ($klaar) {
            $kwast = New-Object System.Drawing.SolidBrush($Rood)
            $g.FillEllipse($kwast, (Fx 28), (Fx $y), (Fx 26), (Fx 26))
            $kwast.Dispose()
            $pen = Nieuwe-Pen $Wit 2.2
            $g.DrawLines($pen, [System.Drawing.PointF[]]@((Punt 35.5 ($y + 13.5)), (Punt 39.5 ($y + 17.5)), (Punt 46.5 ($y + 9.5))))
            $pen.Dispose()
        } elseif ($nu) {
            $kwast = New-Object System.Drawing.SolidBrush($Wit)
            $g.FillEllipse($kwast, (Fx 28), (Fx $y), (Fx 26), (Fx 26))
            $kwast.Dispose()
            $kwast = New-Object System.Drawing.SolidBrush($Rood)
            $g.FillEllipse($kwast, (Fx 35), (Fx ($y + 7)), (Fx 12), (Fx 12))
            $kwast.Dispose()
        } else {
            $pen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(120, 255, 255, 255), (Fx 1.6))
            $g.DrawEllipse($pen, (Fx 29), (Fx ($y + 1)), (Fx 24), (Fx 24))
            $pen.Dispose()
        }
        $kleur = if ($nu) { $Wit } elseif ($klaar) { Kleur '#D9DBE0' } else { Kleur '#8F95A1' }
        $letter = if ($nu) { $script:LetterStapNu } else { $script:LetterStap }
        $vak = New-Object System.Drawing.Rectangle((Px 64), (Px ($y - 4)), (Px 154), (Px 34))
        [System.Windows.Forms.TextRenderer]::DrawText($g, $namen[$i], $letter, $vak, $kleur, $vlag)
    }
    $vak = New-Object System.Drawing.Rectangle((Px 28), (Px 518), (Px 190), (Px 24))
    [System.Windows.Forms.TextRenderer]::DrawText($g, (T "Versie $($script:Versie)" "Version $($script:Versie)"), $script:LetterNoot, $vak, (Kleur '#A6ABB6'), [System.Windows.Forms.TextFormatFlags]'WordBreak, NoPadding')
}

function Meet-Hoogte([string] $tekst, $letter, [double] $breedte) {
    $maat = [System.Windows.Forms.TextRenderer]::MeasureText($tekst, $letter, (New-Object System.Drawing.Size((Px $breedte), 0)), [System.Windows.Forms.TextFormatFlags]'WordBreak')
    [math]::Ceiling($maat.Height / $script:Schaal)
}

function Nieuw-Label([string] $tekst, [double] $y, [double] $h = 0, $kleur = $null, [switch] $Vet, [switch] $Klein) {
    $l = New-Object System.Windows.Forms.Label
    $l.Font = if ($Vet) { $script:LetterVet } elseif ($Klein) { $script:LetterKlein } else { $script:LetterGewoon }
    $l.ForeColor = if ($kleur) { $kleur } else { $Inkt }
    if ($h -le 0) { $h = (Meet-Hoogte $tekst $l.Font $script:Breedte) + 4 }
    Plaats $l 0 $y $script:Breedte $h
    $l.Text = $tekst
    $vlak.Controls.Add($l)
    return $l
}

# Een stuk tekst; geeft terug waar het ophoudt.
function Nieuw-Tekst([string] $tekst, [double] $y, $kleur = $null, [switch] $Vet, [switch] $Klein) {
    $l = Nieuw-Label $tekst $y 0 $kleur -Vet:$Vet -Klein:$Klein
    return $y + [math]::Ceiling($l.Height / $script:Schaal)
}

# Een genummerd kopje binnen een pagina ('1  Haal BugOS binnen'): zo zie je in welke volgorde je de knoppen gebruikt.
function Nieuw-Stap([string] $nummer, [string] $tekst, [double] $y) {
    $n = New-Object System.Windows.Forms.Label
    $n.Font = $script:LetterVet; $n.ForeColor = $RoodTekst; $n.Text = $nummer
    Plaats $n 0 $y 22 24
    $vlak.Controls.Add($n)
    $l = New-Object System.Windows.Forms.Label
    $l.Font = $script:LetterVet; $l.ForeColor = $Inkt; $l.Text = $tekst
    Plaats $l 22 $y ($script:Breedte - 22) 24
    $vlak.Controls.Add($l)
    return $y + 28
}

# Werk gestart onderaan een lange pagina: even naar beneden schuiven, zodat je de balk en de uitleg ziet.
function Toon-Onderaan($ctl) {
    try { $vlak.ScrollControlIntoView($ctl) } catch { Write-Verbose 'Schuiven lukte niet.' }
}

# Een rij met een rond icoontje (goed / let op / fout / nummer), een kopje en uitleg.
function Nieuw-Rij([string] $soort, [string] $titel, [string] $tekst, [double] $y, [string] $nummer = '') {
    $b = $script:Breedte - 54
    $tekstH = (Meet-Hoogte $tekst $script:LetterKlein $b) + 2
    $h = [math]::Max(42, 27 + $tekstH)
    $rij = New-Object System.Windows.Forms.Panel
    Plaats $rij 0 $y $script:Breedte $h
    $rij.Tag = @{ Soort = $soort; Nummer = $nummer }
    Zet-Dubbel $rij
    $rij.Add_Paint({ param($s, $e) Teken-Rijicoon $s $e })
    $kopje = New-Object System.Windows.Forms.Label
    Plaats $kopje 54 2 $b 24
    $kopje.Font = $script:LetterVet; $kopje.ForeColor = $Inkt; $kopje.Text = $titel
    $rij.Controls.Add($kopje)
    $uitleg = New-Object System.Windows.Forms.Label
    Plaats $uitleg 54 27 $b $tekstH
    $uitleg.Font = $script:LetterKlein; $uitleg.ForeColor = $Grijs; $uitleg.Text = $tekst
    $rij.Controls.Add($uitleg)
    $vlak.Controls.Add($rij)
    return $h
}

function Teken-Rijicoon($rij, $e) {
    $g = $e.Graphics
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $soort = $rij.Tag.Soort
    $kleur = switch ($soort) { 'goed' { $Goed } 'let_op' { $LetOp } 'fout' { $Fout } default { $RoodZacht } }
    $kwast = New-Object System.Drawing.SolidBrush($kleur)
    $g.FillEllipse($kwast, (Fx 2), (Fx 2), (Fx 36), (Fx 36))
    $kwast.Dispose()
    $pen = Nieuwe-Pen $Wit 2.6
    switch ($soort) {
        'goed' { $g.DrawLines($pen, [System.Drawing.PointF[]]@((Punt 12.5 20.5), (Punt 18 26), (Punt 28 15))) }
        'let_op' {
            $g.DrawLine($pen, (Punt 20 11.5), (Punt 20 22))
            $stip = New-Object System.Drawing.SolidBrush($Wit)
            $g.FillEllipse($stip, (Fx 18.2), (Fx 25.4), (Fx 3.6), (Fx 3.6))
            $stip.Dispose()
        }
        'fout' { $g.DrawLine($pen, (Punt 14 14), (Punt 26 26)); $g.DrawLine($pen, (Punt 26 14), (Punt 14 26)) }
        default {
            $vak = New-Object System.Drawing.Rectangle((Px 2), (Px 2), (Px 36), (Px 36))
            [System.Windows.Forms.TextRenderer]::DrawText($g, $rij.Tag.Nummer, $script:LetterVet, $vak, $RoodTekst, [System.Windows.Forms.TextFormatFlags]'HorizontalCenter, VerticalCenter, SingleLine, NoPadding')
        }
    }
    $pen.Dispose()
}

function Nieuw-Lijst([double] $y, [double] $b) {
    $l = New-Object System.Windows.Forms.ComboBox
    $l.DropDownStyle = 'DropDownList'
    $l.Font = $script:LetterGewoon
    Plaats $l 0 $y $b 32
    $vlak.Controls.Add($l)
    return $l
}

$script:Pagina = 0
$script:W = @{}   # knoppen en vakjes die een klik later nog nodig heeft
$Paginas = @()

# --- Pagina 0: welkom -------------------------------------------------------
$Paginas += {
    $kop.Text = (T 'Welkom bij BugOS Switch' 'Welcome to BugOS Switch')
    $y = Nieuw-Tekst (T 'Dit programma helpt je in vier stappen van Windows over te stappen op BugOS:' 'This program helps you move from Windows to BugOS in four steps:') 0
    $y += 14
    $y += (Nieuw-Rij 'nummer' (T 'Controleren' 'Check') (T 'Kan je computer BugOS aan? Dat zie je meteen.' 'Can your computer run BugOS? You see it right away.') $y '1') + 10
    $y += (Nieuw-Rij 'nummer' (T 'USB-stick maken' 'Make the USB stick') (T 'BugOS op een USB-stick van minstens 8 GB. Daarvan start je straks je computer om BugOS te installeren.' 'BugOS on a USB stick of at least 8 GB. You start your computer from it later to install BugOS.') $y '2') + 10
    $y += (Nieuw-Rij 'nummer' (T 'Bestanden meenemen' 'Take your files') (T "Een kopie van je foto's, documenten en meer, die BugOS straks terugzet." 'A copy of your photos, documents and more, which BugOS puts back later.') $y '3') + 10
    [void](Nieuw-Rij 'nummer' (T 'Waar komt BugOS?' 'Where does BugOS go?') (T 'In plaats van Windows, ernaast, of op een andere schijf. Hier lees je wat je bij het installeren kiest.' 'Instead of Windows, next to it, or on another disk. Here you read what to choose when installing.') $y '4')
}

# --- Pagina 1: controle -----------------------------------------------------
$script:ControleUitslag = $null
$Paginas += {
    $kop.Text = (T 'Kan mijn computer BugOS aan?' 'Can my computer run BugOS?')
    function script:Toon-Controle($uitslag) {
        $y = 0
        foreach ($r in @($uitslag)) {
            $soort = if (-not $r.Ok) { 'fout' } elseif ($r.Waarschuwing) { 'let_op' } else { 'goed' }
            $y += (Nieuw-Rij $soort $r.Naam $r.Tekst $y) + 10
        }
    }
    if ($script:ControleUitslag) { Toon-Controle $script:ControleUitslag; return }
    # Kijken duurt een paar seconden (Windows vragen naar geheugen, videokaart, BitLocker): ernaast, met een balk.
    $script:W.controleLabel = Nieuw-Label (T 'Even kijken naar je computer…' 'Looking at your computer…') 0 26 $Grijs
    $script:W.controleBalk = Nieuw-Balk 0 34 ($script:Breedte - 4) $vlak
    Start-Werk -Werk { Get-Controle } -Balk $script:W.controleBalk -Klaar {
        param($staat)
        $script:W.controleLabel.Visible = $false; $script:W.controleBalk.Visible = $false
        if ($staat.Fout) {
            [void](Nieuw-Rij 'fout' (T 'Kijken lukte niet' 'Checking did not work') $staat.Fout 0)
            return
        }
        $script:ControleUitslag = @($staat.Uitkomst)
        Toon-Controle $script:ControleUitslag
    }
}

# --- Pagina 2: meenemen -----------------------------------------------------
$Paginas += {
    $kop.Text = (T 'Je bestanden meenemen' 'Take your files with you')
    # In gewone woorden wat er mee gaat (formaat 2, zie FORMAT.md), en heel duidelijk dat wachtwoorden NOOIT
    # meegaan: dat is de keuze van de eigenaar, en mensen moeten weten dat ze hun wifi-wachtwoord nog één keer nodig
    # hebben. Kort gehouden (de rij 'andere mappen' kwam erbij), zodat de pagina ook op 150% zonder schuifbalk past.
    # Geen woorden met een koppelteken aan het eind van de zin: Windows brak 'wifi-namen' af als 'wifi' + '-namen' (en
    # een koppelteken dat niet afbreekt, U+2011, tekent Windows Forms als 'wifi- namen').
    # De grootte staat in een eigen label: die verandert als je een extra map toevoegt.
    $y = Nieuw-Tekst (T 'Een kopie van je spullen op een USB-schijf. Op deze computer blijft alles staan.' 'A copy of your things on a USB drive. Everything stays on this computer.') 0
    $script:W.groot = Nieuw-Label (T 'Wat gaat er mee (even rekenen…)' 'What goes along (working it out…)') ($y + 8) 24 $null -Vet
    $y = Nieuw-Tekst (T "Documenten, foto's, muziek, video's, bureaublad, downloads, bladwijzers, e-mail, achtergrond, printers en de namen van je wifi. Nooit wachtwoorden." "Documents, photos, music, videos, desktop, downloads, bookmarks, e-mail, wallpaper, printers and your Wi-Fi names. Never passwords.") ($y + 32) $Grijs -Klein
    $y = Nieuw-Stap '1' (T 'Kies waar de kopie heen gaat' 'Choose where the copy goes') ($y + 12)
    $script:W.schijf = Nieuw-Lijst $y 300
    $lijst = $script:W.schijf
    # Alleen schijven die je eruit haalt: een D:-schijf in de laptop gaat mee de prullenbak in als je straks
    # bij het installeren de hele schijf kiest (U284). Een vaste (type 3) schijf telt alleen als hij via USB hangt.
    Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DeviceID -ne 'C:' -and ($_.DriveType -eq 2 -or ($_.DriveType -eq 3 -and (Test-UsbLetter $_))) } | ForEach-Object {
        [void]$lijst.Items.Add("$($_.DeviceID)  $($_.VolumeName)  ($([math]::Round($_.FreeSpace / 1GB)) GB $(T 'vrij' 'free'))")
    }
    if ($lijst.Items.Count -gt 0) { $lijst.SelectedIndex = 0 }
    $noot = Nieuw-Label (T 'Je BugOS-stick (BUGOS) mag ook.' 'Your BugOS stick (BUGOS) is fine too.') ($y + 6) 24 $Grijs -Klein
    $noot.Left = Px 312; $noot.Width = Px ($script:Breedte - 312)
    $script:W.schijfNoot = $noot; $script:W.schijfY = $y
    $y = Nieuw-Stap '2' (T 'Nog een andere map mee? Dat hoeft niet.' 'Another folder too? You do not have to.') ($y + 44)
    # Extra mappen (E): ook iets anders dan de vaste zes, bijvoorbeeld een map op een tweede schijf (D:). Links staat
    # wat je koos, rechts de knop om er een toe te voegen. Kiezen gaat met het gewone mapvenster van Windows.
    # Een LinkLabel: als er extra mappen zijn, staat er een klikbaar '(weghalen)' achter, om de keuze ongedaan te maken.
    $script:W.extra = New-Object System.Windows.Forms.LinkLabel
    $script:W.extra.Font = $script:LetterGewoon
    $script:W.extra.ForeColor = $Grijs
    $script:W.extra.LinkColor = $Inkt
    $script:W.extra.AutoEllipsis = $true
    Plaats $script:W.extra 0 ($y + 10) 300 26
    $vlak.Controls.Add($script:W.extra)
    $script:W.extra.Add_LinkClicked({
        $script:ExtraMappen.Clear()
        Zet-ExtraTekst
    })
    $script:W.extraKnop = Nieuw-Knop (T 'Map toevoegen…' 'Add folder…') 312 $y 220
    $y = Nieuw-Stap '3' (T 'Kopiëren' 'Copy') ($y + 54)
    $script:W.knop = Nieuw-Knop (T 'Bestanden kopiëren' 'Copy files') 0 $y 220 'hoofd'
    # script: zodat de knoppen (die later draaien, buiten deze pagina) de functie ook vinden.
    function script:Zet-ExtraTekst {
        # Wat er in de regel 'andere mappen' staat, en de nieuwe totale grootte bovenaan.
        if ($script:ExtraMappen.Count -eq 0) {
            $script:W.extra.Text = (T 'Bijvoorbeeld een map op een tweede schijf' 'For example a folder on a second drive')
            $script:W.extra.LinkArea = New-Object System.Windows.Forms.LinkArea(0, 0)
        } else {
            $namen = ($script:ExtraMappen | ForEach-Object { Split-Path $_ -Leaf }) -join ', '
            $weg = (T '(weghalen)' '(remove)')
            $tekst = (T "Ook mee: $namen " "Also: $namen ") + $weg
            $script:W.extra.Text = $tekst
            $script:W.extra.LinkArea = New-Object System.Windows.Forms.LinkArea(($tekst.Length - $weg.Length), $weg.Length)
        }
        # De grootte uitrekenen kan bij veel foto's een halve minuut duren: ernaast (het venster blijft bewegen).
        $script:W.groot.Text = (T 'Wat gaat er mee (even rekenen…)' 'What goes along (working it out…)')
        Start-Werk -Werk { Get-MeeneemGrootte } -Mee @{ ExtraMappen = @($script:ExtraMappen); CloudMee = $script:CloudMee } -Klaar {
            param($staat)
            if ($staat.Fout) { $script:W.groot.Text = (T 'Wat gaat er mee' 'What goes along'); return }
            # Met de komma of punt van Windows zelf (0,3 GB in het Nederlands).
            $gb = '{0:0.#}' -f ([int64](@($staat.Uitkomst)[-1]) / 1GB)
            $script:W.groot.Text = (T "Wat gaat er mee ($gb GB)" "What goes along ($gb GB)")
        }
    }
    Zet-ExtraTekst
    $script:W.extraKnop.Add_Click({
        $kies = New-Object System.Windows.Forms.FolderBrowserDialog
        $kies.Description = (T 'Kies een map die ook mee moet naar BugOS' 'Choose a folder that should also go to BugOS')
        $kies.ShowNewFolderButton = $false
        if ($kies.ShowDialog() -ne 'OK') { return }
        $letter = ''
        if ($script:W.schijf.SelectedIndex -ge 0) { $letter = ($script:W.schijf.SelectedItem -split '\s+')[0] + '\' }
        $reden = Test-ExtraMap $kies.SelectedPath $letter
        if ($reden) { Toon $reden 'Warning'; return }
        $script:ExtraMappen.Add([System.IO.Path]::GetFullPath($kies.SelectedPath).TrimEnd('\'))
        Zet-ExtraTekst
    })
    $script:W.balk = Nieuw-Balk 0 ($y + 54) ($script:Breedte - 4) $vlak
    $script:W.balk.Visible = $false
    $script:W.status = Nieuw-Label '' ($y + 70) 66 $Grijs
    if ($script:W.schijf.Items.Count -eq 0) {
        # Een lege lijst zonder uitleg: dan weet je niet wat je moet doen. Zit er wel een USB-stick in, maar zonder
        # schijf die Windows kan openen (net leeggemaakt, of een stick op de oude manier)? Dat zeggen we erbij. De uitleg
        # staat naast het lijstje, waar je kijkt (niet onderaan, buiten beeld).
        $kaal = @(Get-UsbSchijven | Where-Object { @(Get-Partition -DiskNumber $_.Number -ErrorAction SilentlyContinue | Where-Object { "$($_.DriveLetter)" -match '^[A-Za-z]$' }).Count -eq 0 })
        $script:W.schijf.Visible = $false
        $script:W.schijfNoot.ForeColor = $LetOp
        $script:W.schijfNoot.Left = 0; $script:W.schijfNoot.Width = Px $script:Breedte
        $script:W.schijfNoot.Top = Px ($script:W.schijfY + 4); $script:W.schijfNoot.Height = Px 40
        $script:W.schijfNoot.Text = if ($kaal.Count -gt 0) {
            T "'$($kaal[0].FriendlyName)' is leeg. Zet er eerst BugOS op in stap 2." "'$($kaal[0].FriendlyName)' is empty. Put BugOS on it first in step 2."
        } else {
            T 'Geen USB-schijf gevonden. Steek er een in en klik op Terug en weer op Volgende.' 'No USB drive found. Plug one in, then click Back and Next again.'
        }
    }
    $script:W.knop.Add_Click({
        $lijst = $script:W.schijf; $status = $script:W.status
        if ($lijst.SelectedIndex -lt 0) { Toon (T 'Steek eerst een USB-schijf in en ga even terug en weer verder.' 'Plug in a USB drive first, then go back and forward again.'); return }
        $letter = ($lijst.SelectedItem -split '\s+')[0] + '\'
        $status.ForeColor = $Grijs
        Toon-Onderaan $status
        # Stap 1 (ernaast): kijken wat er mee gaat. OneDrive-bestanden tellen, FAT32 en de vrije ruimte.
        Start-Werk -Blokkeer -Balk $script:W.balk -Label $status -Tekst (T 'Even kijken wat er mee gaat…' 'Checking what goes along…') -Mee @{ ExtraMappen = @($script:ExtraMappen); Letter = $letter } -Werk {
            $letter = $Mee.Letter
            $cloud = Get-CloudBestanden
            $fs = ''
            try { $fs = (Get-Volume -DriveLetter $letter.Substring(0, 1) -ErrorAction Stop).FileSystem } catch { $fs = '' }
            $groot4 = @()
            if ($fs -eq 'FAT32') { $groot4 = @(Get-TeGrootVoorFat32 | ForEach-Object { $_.Name }) }
            $al = 0L
            if (Test-Path -LiteralPath "$($letter)BugOS-Switch") { $al = [int64](Get-ChildItem -LiteralPath "$($letter)BugOS-Switch" -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum }
            [pscustomobject]@{ Cloud = $cloud; Fs = $fs; Groot4 = $groot4; Vrij = [int64](Get-PSDrive $letter.Substring(0, 1)).Free; Al = $al }
        } -Klaar {
            param($staat)
            $status = $script:W.status
            if ($staat.Fout) { $script:W.balk.Visible = $false; $status.Text = ''; Toon $staat.Fout 'Error'; return }
            $u = @($staat.Uitkomst)[-1]
            $letter = ($script:W.schijf.SelectedItem -split '\s+')[0] + '\'
            # OneDrive (E): staan er bestanden alleen in de cloud? Vraag het VOORAF: eerst downloaden (kan lang duren en
            # vraagt internet), of laten staan (dan zegt BugOS straks welke het waren).
            $script:Cloud = $u.Cloud
            $script:CloudMee = $true
            if ($script:Cloud.Aantal -gt 0) {
                $cgb = [math]::Round($script:Cloud.Bytes / 1GB, 1)
                $script:CloudMee = Vraag (T "$($script:Cloud.Aantal) bestanden ($cgb GB) staan alleen in OneDrive, niet op deze computer. Zal Windows ze eerst downloaden, zodat ze ook meegaan? Dat kan even duren.`n`nKies je Nee, dan blijven ze in OneDrive. In BugOS open je ze dan via onedrive.live.com." "$($script:Cloud.Aantal) files ($cgb GB) are only in OneDrive, not on this computer. Should Windows download them first, so they come along too? That can take a while.`n`nIf you choose No, they stay in OneDrive. In BugOS you open them at onedrive.live.com.")
            }
            # FAT32 (E): bestanden van 4 GB of groter passen niet op zo'n stick. Zeg het nu, niet halverwege.
            $groot4 = @($u.Groot4)
            if ($u.Fs -eq 'FAT32' -and $groot4.Count -gt 0) {
                $namen = ($groot4 | Select-Object -First 3) -join ', '
                if (-not (Vraag (T "Deze schijf (FAT32) kan geen bestanden van 4 GB of groter bewaren. $($groot4.Count) bestand(en) passen er dus niet op, zoals: $namen.`n`nGebruik je liever een andere schijf (exFAT of NTFS)? Kies dan Nee. Kies Ja om zonder die bestanden door te gaan." "This drive (FAT32) cannot hold files of 4 GB or more. $($groot4.Count) file(s) will not fit, such as: $namen.`n`nWould you rather use another drive (exFAT or NTFS)? Choose No. Choose Yes to continue without those files."))) {
                    $script:W.balk.Visible = $false; $status.Text = ''; return
                }
            }
            $script:W.extraKnop.Enabled = $false; $script:W.knop.Enabled = $false
            # Stap 2 (ernaast): uitrekenen of het past, en dan kopiëren. Wat er al in BugOS-Switch staat (een eerdere
            # keer), hoeft er niet nog een keer bij (U286).
            Start-Werk -Blokkeer -Balk $script:W.balk -Label $status -Tekst (T 'Uitrekenen hoeveel ruimte er nodig is…' 'Working out how much space is needed…') -TerugVars @('Deels', 'FirefoxOverslagen') -Mee @{ ExtraMappen = @($script:ExtraMappen); CloudMee = $script:CloudMee; Cloud = $script:Cloud; Letter = $letter; Vrij = $u.Vrij; Al = $u.Al } -Werk {
                $nodig = Get-MeeneemGrootte
                if ($Mee.Vrij + $Mee.Al -lt $nodig) { return [pscustomobject]@{ TeKlein = $true; Nodig = $nodig; Heb = ($Mee.Vrij + $Mee.Al); NogVrij = 0L } }
                $null = Invoke-Meenemen $Mee.Letter $Voortgang
                [pscustomobject]@{ TeKlein = $false; Nodig = $nodig; Heb = 0L; NogVrij = [int64](Get-PSDrive $Mee.Letter.Substring(0, 1)).Free }
            } -Klaar {
                param($staat)
                $status = $script:W.status
                $script:W.extraKnop.Enabled = $true; $script:W.knop.Enabled = $true
                $script:W.balk.Visible = $false
                if ($staat.Fout) { $status.Text = ''; Toon $staat.Fout 'Error'; return }
                $u = @($staat.Uitkomst)[-1]
                if ($u.TeKlein) {
                    # Precies zeggen hoeveel er nodig is en hoeveel er is, dan weet je hoe groot je andere schijf moet zijn.
                    $status.Text = ''
                    Toon (T "Er is niet genoeg ruimte op die schijf: er moet $([math]::Round($u.Nodig / 1GB, 1)) GB op, en er is $([math]::Round($u.Heb / 1GB, 1)) GB. Gebruik een grotere schijf, of haal een extra map weg." "Not enough space on that drive: $([math]::Round($u.Nodig / 1GB, 1)) GB must go on it, and there is $([math]::Round($u.Heb / 1GB, 1)) GB. Use a bigger drive, or remove an extra folder.") 'Warning'
                    return
                }
                $deels = @($staat.Terug['Deels'] | Where-Object { $_ })
                $firefox = @($staat.Terug['FirefoxOverslagen'] | Where-Object { $_ })
                # Een paar heel grote mappen van Firefox (meestal opslag van websites) bleven thuis: even zeggen.
                $ffTekst = ''
                if ($firefox.Count -gt 0) { $ffTekst = T "Uit Firefox bleven een paar heel grote mappen thuis ($($firefox -join ', ')); websites maken die vanzelf opnieuw." "A few very large Firefox folders stayed behind ($($firefox -join ', ')); websites make them again by themselves." }
                if ($deels.Count -eq 0) {
                    $letter = ($script:W.schijf.SelectedItem -split '\s+')[0]
                    $tekst = T "Ze staan in de map BugOS-Switch op $letter. Op deze computer is niets veranderd.`n`nHaal de schijf er pas uit als je BugOS gaat installeren. In BugOS zet je alles terug met 'Haal alles van je oude pc'." "They are in the BugOS-Switch folder on $letter. Nothing changed on this computer.`n`nKeep the drive until you install BugOS. In BugOS you put everything back with 'Bring everything from your old PC'."
                    if ($ffTekst) { $tekst += "`n`n" + $ffTekst }
                    Toon-Klaar (T 'Je bestanden staan klaar' 'Your files are ready') $tekst (T 'Verder: waar komt BugOS?' 'Next: where does BugOS go?')
                    return
                }
                if ($deels.Count -gt 0 -and $u.NogVrij -lt 64MB) {
                    # Vol geraakt (kleine bestanden nemen op een grote stick meer ruimte in dan ze groot zijn) (U288).
                    $status.Text = (T 'De schijf is vol geraakt: niet alles kon mee. Gebruik een grotere schijf, of maak ruimte op deze en klik nog een keer.' 'The drive got full: not everything could be copied. Use a bigger drive, or make room on this one and click again.')
                    $status.ForeColor = $Fout
                } elseif ($deels.Count -gt 0) {
                    $welke = $deels -join ', '
                    $status.Text = (T "Klaar, maar een paar bestanden uit $welke konden niet mee (bijv. open in een programma, groter dan 4 GB, of alleen in OneDrive). Sluit je programma's en klik nog een keer: wat er al staat, gaat sneller." "Done, but a few files from $welke could not be copied (e.g. open in a program, larger than 4 GB, or only in OneDrive). Close your programs and click again: what is already there goes faster.")
                    $status.ForeColor = $Grijs
                }
                if ($ffTekst) { $status.Text += ' ' + $ffTekst }
            }
        }
    })
}

# --- Pagina 3: ruimte maken ------------------------------------------------
# Waar komt BugOS? De USB-stick is alleen het installatieprogramma: BugOS komt op een schijf. Drie keuzes:
#   - vervang: op de schijf van Windows, die wordt helemaal gewist;
#   - naast:   op dezelfde schijf naast Windows (deze stap maakt Windows kleiner; pas dan rekenen we de ruimte uit);
#   - ander:   op een andere schijf (tweede SSD of externe USB-schijf), Windows blijft onaangeroerd.
# Bij 'vervang' en 'ander' verandert deze stap niets: hij zegt wat je straks bij het installeren kiest.
$script:Plek = ''
$Paginas += {
    $kop.Text = (T 'Waar komt BugOS?' 'Where does BugOS go?')
    $y = Nieuw-Tekst (T 'De USB-stick is alleen het installatieprogramma. Bij het installeren komt BugOS op een schijf. Kies waar:' 'The USB stick is only the installer. When you install, BugOS goes on a disk. Choose where:') 0
    $keuzes = @(
        @('vervang', (T 'In plaats van Windows' 'Instead of Windows'), (T 'Windows gaat weg, met alles erop.' 'Windows goes away, with everything on it.')),
        @('naast', (T 'Naast Windows' 'Next to Windows'), (T 'Allebei op deze computer. Bij het aanzetten kies je.' 'Both on this computer. You choose when it starts.')),
        @('ander', (T 'Op een andere schijf' 'On another disk'), (T 'Een tweede schijf of een externe USB-schijf. Windows blijft.' 'A second disk or an external USB drive. Windows stays.'))
    )
    $y += 10
    foreach ($k in $keuzes) {
        $soort = if ($script:Plek -eq $k[0]) { 'hoofd' } else { 'gewoon' }
        $knop = Nieuw-Knop $k[1] 0 $y 220 $soort
        $knop.Tag.Plek = $k[0]
        $knop.Add_Click({
            if (Test-Bezig) { return }
            $script:Plek = $this.Tag.Plek
            Toon-Pagina
        })
        $uitleg = Nieuw-Label $k[2] ($y + 2) 40 $Grijs -Klein
        $uitleg.Left = Px 232; $uitleg.Width = Px ($script:Breedte - 232)
        $y += 50
    }
    $script:W.y3 = $y + 4
    $opstarten = T 'Start op vanaf de BugOS-stick (toets F12, F11, F9 of Esc bij het aanzetten).' 'Start from the BugOS stick (key F12, F11, F9 or Esc when switching on).'
    switch ($script:Plek) {
        'vervang' {
            [void](Nieuw-Rij 'let_op' (T 'Zo installeer je BugOS in plaats van Windows' 'This is how you install BugOS instead of Windows') (T "1. $opstarten`n2. Kies bij 'Installeren op' de schijf van deze computer en 'De hele schijf gebruiken'.`nAlles op die schijf wordt gewist, ook je bestanden: neem ze eerst mee (stap 3)." "1. $opstarten`n2. At 'Install on', choose the disk of this computer and 'Use the whole disk'.`nEverything on that disk is erased, your files too: take them along first (step 3).") $script:W.y3)
        }
        'naast' { Start-Ruimte }
        'ander' {
            [void](Nieuw-Rij 'goed' (T 'Zo installeer je BugOS op een andere schijf' 'This is how you install BugOS on another disk') (T "1. Sluit de andere schijf aan.`n2. $opstarten`n3. Kies bij 'Installeren op' die schijf en 'De hele schijf gebruiken'.`nWindows blijft zoals het is." "1. Connect the other disk.`n2. $opstarten`n3. At 'Install on', choose that disk and 'Use the whole disk'.`nWindows stays as it is.") $script:W.y3)
        }
    }
}

function Start-Ruimte {
    $y = $script:W.y3
    $script:W.ruimteLabel = Nieuw-Label (T 'Even uitrekenen hoeveel ruimte er is…' 'Working out how much space there is…') ($y + 18) 26 $Grijs
    $script:W.ruimteBalk = Nieuw-Balk 0 ($y + 52) ($script:Breedte - 4) $vlak
    # Windows vragen hoe klein C: kan worden duurt soms een halve minuut: ernaast.
    Start-Werk -Werk { Get-KrimpMogelijk } -Balk $script:W.ruimteBalk -Klaar {
        param($staat)
        $y = $script:W.y3
        $script:W.ruimteLabel.Visible = $false; $script:W.ruimteBalk.Visible = $false
        if ($staat.Fout) {
            [void](Nieuw-Rij 'let_op' (T 'Ik heb even je hulp nodig' 'I need your help') (T 'Ik kon niet uitrekenen hoeveel ruimte er is. Klik met de rechtermuisknop op het programma en kies "Als administrator uitvoeren".' 'I could not work out how much space there is. Right-click the program and choose "Run as administrator".') ($y + 18))
            return
        }
        $kan = [int](@($staat.Uitkomst)[-1])
        if ($kan -lt 40) {
            [void](Nieuw-Rij 'fout' (T 'Niet genoeg ruimte' 'Not enough space') (T "Er kan maar $kan GB vrijgemaakt worden. BugOS heeft minstens 40 GB nodig. Ruim eerst wat op, of laat BugOS Windows vervangen." "Only $kan GB can be freed. BugOS needs at least 40 GB. Clean up first, or let BugOS replace Windows.") ($y + 18))
            return
        }
        $y = Nieuw-Tekst (T "Hoeveel ruimte krijgt BugOS? (40 tot $kan GB)" "How much space does BugOS get? (40 to $kan GB)") ($y + 18) -Vet
        $script:W.getal = New-Object System.Windows.Forms.NumericUpDown
        $getal = $script:W.getal
        $getal.Font = $script:LetterGewoon
        Plaats $getal 0 ($y + 6) 120 32
        $getal.Minimum = 40; $getal.Maximum = $kan; $getal.Value = [math]::Min(100, $kan)
        $vlak.Controls.Add($getal)
        $gb = Nieuw-Label 'GB' ($y + 9) 28 $Grijs
        $gb.Left = Px 130; $gb.Width = Px 60
        $script:W.krimpKnop = Nieuw-Knop (T 'Ruimte maken' 'Make space') 0 ($y + 58) 220 'hoofd'
        $script:W.krimpBalk = Nieuw-Balk 0 ($y + 112) ($script:Breedte - 4) $vlak
        $script:W.krimpBalk.Visible = $false
        $script:W.krimpStatus = Nieuw-Label '' ($y + 128) 110 $Grijs
        $script:W.krimpKnop.Add_Click({
            $getal = $script:W.getal
            if (-not (Vraag (T "Windows wordt $($getal.Value) GB kleiner. Je bestanden blijven gewoon staan.`n`nHeb je je bestanden meegenomen (stap 3)? Doorgaan?" "Windows will shrink by $($getal.Value) GB. Your files stay where they are.`n`nDid you take your files along (step 3)? Continue?"))) { return }
            $script:W.krimpKnop.Enabled = $false
            $gestart = Start-BeheerderTaak @('-Taak', 'Krimp', '-KrimpGB', [string][int]$getal.Value) -Balk $script:W.krimpBalk -Label $script:W.krimpStatus -Tekst (T 'Windows kleiner maken… Dit kan een paar minuten duren.' 'Shrinking Windows… This can take a few minutes.') -Klaar {
                param($r)
                $script:W.krimpKnop.Enabled = $true
                $script:W.krimpBalk.Visible = $false
                if ($r.Code -eq 0) {
                    Toon-Klaar (T 'Er is ruimte voor BugOS' 'There is space for BugOS') (T "Windows is kleiner gemaakt; je bestanden in Windows staan er nog.`n`nZo installeer je BugOS:`n1. Start je computer opnieuw op vanaf de BugOS-stick: druk tijdens het opstarten op F12, F11, F9 of Esc en kies de USB-stick.`n2. Kies bij het installeren `"De schijf delen met Windows of een ander systeem`" (niet `"De hele schijf gebruiken`": dan gaat Windows weg)." "Windows was made smaller; your files in Windows are still there.`n`nThis is how you install BugOS:`n1. Restart your computer from the BugOS stick: while it starts, press F12, F11, F9 or Esc and choose the USB stick.`n2. When installing, choose `"Share disk with other operating systems`" (not `"Use entire disk`": that removes Windows).") (T 'Sluiten' 'Close')
                } else {
                    $script:W.krimpStatus.Text = ''
                    Toon-Fout (T 'Ruimte maken lukte niet' 'Making space did not work') (T 'Windows is niet kleiner gemaakt; er is niets veranderd. Herstart je computer en probeer het nog een keer. Lukt het dan nog niet, kies dan "Op een andere schijf" of "In plaats van Windows".' 'Windows was not made smaller; nothing changed. Restart your computer and try again. If it still does not work, choose "On another disk" or "Instead of Windows".') $r.Fout
                }
            }
            if (-not $gestart) { $script:W.krimpKnop.Enabled = $true }
        })
    }
}

# --- Pagina 4: USB-stick ----------------------------------------------------
$script:IsoGekozen = ''
$script:IsoManier = 'bruikbaar'
$Paginas += {
    $kop.Text = (T 'BugOS op een USB-stick zetten' 'Put BugOS on a USB stick')
    $y = Nieuw-Tekst (T 'Van deze stick start je straks je computer om BugOS te installeren. Je hebt een stick van minstens 8 GB nodig.' 'You start your computer from this stick later to install BugOS. You need a stick of at least 8 GB.') 0
    $y = Nieuw-Stap '1' (T 'Haal BugOS binnen' 'Get BugOS') ($y + 10)
    $download = Nieuw-Knop (T 'BugOS downloaden' 'Download BugOS') 0 $y 200 'hoofd'
    $kies = Nieuw-Knop (T 'Ik heb al een .iso-bestand…' 'I already have an .iso file…') 212 $y 270
    # Twee regels: de naam van het bestand en wat dat betekent voor de stick.
    $script:W.isoLabel = Nieuw-Label (T 'Nog geen BugOS gekozen.' 'No BugOS chosen yet.') ($y + 48) 40 $Grijs -Klein
    # De balk staat op de plek van de tweede regel: die is er pas als het nakijken of downloaden klaar is.
    $script:W.downloadBalk = Nieuw-Balk 0 ($y + 72) ($script:Breedte - 4) $vlak
    $script:W.downloadBalk.Visible = $false
    $script:W.downloadKnop = $download

    function script:Kijk-Iso([string] $pad) {
        # Welke manier past bij deze ISO? Een nieuwe BugOS: een stick die bruikbaar blijft. Een oudere: de oude manier.
        $script:IsoGekozen = ''
        $script:W.isoPad = $pad
        $script:W.isoLabel.ForeColor = $Grijs
        $script:W.isoLabel.Text = (T 'Het bestand nakijken…' 'Checking the file…')
        Start-Werk -Blokkeer -Mee @{ Pad = $pad } -Balk $script:W.downloadBalk -Werk {
            $i = Get-IsoStickInfo $Mee.Pad
            [pscustomobject]@{ Bruikbaar = $i.Bruikbaar; Grootte = $i.Grootte }
        } -Klaar {
            param($staat)
            $script:W.downloadBalk.Visible = $false
            if ($staat.Fout) {
                $script:W.isoLabel.Text = (T 'Nog geen BugOS gekozen.' 'No BugOS chosen yet.')
                $script:W.isoLabel.ForeColor = $Grijs
                Toon ((T 'Dit bestand kan ik niet gebruiken: ' 'I cannot use this file: ') + $staat.Fout) 'Warning'
                return
            }
            $u = @($staat.Uitkomst)[-1]
            $pad = $script:W.isoPad
            $script:IsoGekozen = $pad
            if ($u.Bruikbaar) {
                $script:IsoManier = 'bruikbaar'
                $script:W.isoLabel.Text = (Split-Path -Leaf $pad) + "`n" + (T 'Goed: de stick blijft bruikbaar in Windows (één schijf BUGOS, met ruimte over).' 'Good: the stick stays usable in Windows (one drive BUGOS, with space left).')
                $script:W.isoLabel.ForeColor = $Goed
            } else {
                $script:IsoManier = 'heel'
                $script:W.isoLabel.Text = (Split-Path -Leaf $pad) + "`n" + (T 'Een oudere BugOS: de hele stick wordt voor BugOS gebruikt. Na het installeren maak je hem weer gewoon met de knop hieronder.' 'An older BugOS: the whole stick is used for BugOS. After installing, make it normal again with the button below.')
                $script:W.isoLabel.ForeColor = $LetOp
            }
        }
    }

    $download.Add_Click({
        $label = $script:W.isoLabel
        Start-Werk -Blokkeer -Balk $script:W.downloadBalk -Label $label -Tekst (T 'BugOS zoeken…' 'Looking for BugOS…') -Werk {
            $soort = Get-IsoSoort
            $gevonden = $null
            try { $gevonden = Get-IsoInfo $soort } catch { $gevonden = $null }
            [pscustomobject]@{ Soort = $soort; Gevonden = $gevonden; Map = (Get-BekendeMap 'Downloads') }
        } -Klaar {
            param($staat)
            $label = $script:W.isoLabel
            $u = @($staat.Uitkomst)[-1]
            if ($staat.Fout -or -not $u -or -not $u.Gevonden) {
                $script:W.downloadBalk.Visible = $false
                $label.Text = (T 'Nog geen bestand gekozen.' 'No file chosen yet.')
                Toon (T 'Er staat nog geen BugOS klaar om te downloaden, of er is geen internet. Probeer het later nog eens.' 'There is no BugOS ready to download yet, or there is no internet. Please try again later.')
                return
            }
            $gevonden = $u.Gevonden
            $groot = [math]::Round((($gevonden.Info.delen | Measure-Object grootte -Sum).Sum) / 1GB, 1)
            $wat = if ($u.Soort -eq 'nvidia') { T 'de versie voor Nvidia-videokaarten' 'the version for Nvidia graphics cards' } else { T 'de gewone versie' 'the normal version' }
            if (-not (Vraag (T "Ik ga $($gevonden.Versie) downloaden ($wat, $groot GB) naar je map Downloads. Dit kan een tijdje duren; je kunt intussen gewoon verder met andere dingen. Doorgaan?" "I will download $($gevonden.Versie) ($wat, $groot GB) to your Downloads folder. This can take a while; you can do other things in the meantime. Continue?"))) {
                $script:W.downloadBalk.Visible = $false
                $label.Text = (T 'Nog geen bestand gekozen.' 'No file chosen yet.')
                return
            }
            Start-Werk -Blokkeer -Balk $script:W.downloadBalk -Label $label -Tekst (T 'Downloaden…' 'Downloading…') -Mee @{ Gevonden = $gevonden; Map = $u.Map } -Werk {
                Save-BugOSIso $Mee.Gevonden $Mee.Map $Voortgang
            } -Klaar {
                param($staat)
                $script:W.downloadBalk.Visible = $false
                if ($staat.Fout) {
                    $script:W.isoLabel.Text = (T 'Nog geen BugOS gekozen.' 'No BugOS chosen yet.')
                    $script:W.isoLabel.ForeColor = $Grijs
                    Toon $staat.Fout 'Error'
                    return
                }
                Kijk-Iso ([string](@($staat.Uitkomst)[-1]))
            }
        }
    })
    $kies.Add_Click({
        $d = New-Object System.Windows.Forms.OpenFileDialog
        $d.Filter = 'BugOS (*.iso)|*.iso'
        $d.InitialDirectory = Get-BekendeMap 'Downloads'
        if ($d.ShowDialog() -eq 'OK') { Kijk-Iso $d.FileName }
    })

    $y = Nieuw-Stap '2' (T 'Kies je USB-stick' 'Choose your USB stick') ($y + 96)
    $script:W.stick = Nieuw-Lijst $y 300
    $noot = Nieuw-Label (T 'Alles wat er nu op staat, wordt gewist.' 'Everything on it now gets erased.') ($y + 6) 24 $Grijs -Klein
    $noot.Left = Px 312; $noot.Width = Px ($script:Breedte - 312)
    $y -= 4
    $lijst = $script:W.stick
    $script:W.sticks = @(Get-UsbSchijven)
    $sticks = $script:W.sticks
    foreach ($s in $sticks) { [void]$lijst.Items.Add("#$($s.Number)  $($s.FriendlyName)  ($([math]::Round($s.Size / 1GB)) GB)") }
    if ($lijst.Items.Count -gt 0) { $lijst.SelectedIndex = 0 } else {
        # Geen stick: de uitleg naast het lege lijstje (in het lijstje zelf viel hij er half af).
        $lijst.Visible = $false
        $noot.Text = (T 'Geen USB-stick gevonden. Steek er een in en klik op Terug en weer op Volgende.' 'No USB stick found. Plug one in, then click Back and Next again.')
        $noot.ForeColor = $LetOp
        $noot.Left = 0; $noot.Width = Px $script:Breedte; $noot.Top = Px ($y + 4); $noot.Height = Px 40
    }
    $y = Nieuw-Stap '3' (T 'Zet BugOS op de stick' 'Put BugOS on the stick') ($y + 48)
    $maak = Nieuw-Knop (T 'BugOS op de stick zetten' 'Put BugOS on the stick') 0 $y 260 'hoofd'
    $script:W.stickBalk = Nieuw-Balk 0 ($y + 54) ($script:Breedte - 4) $vlak
    $script:W.stickBalk.Visible = $false
    $script:W.stickStatus = Nieuw-Label (T 'Dit duurt een paar minuten.' 'This takes a few minutes.') ($y + 70) 110 $Grijs
    # Apart en onderaan, zodat je hem niet verwart met de rode knop: BugOS er weer af halen.
    $y = Nieuw-Tekst (T 'Klaar met BugOS installeren en wil je de stick weer helemaal leeg? Of is hij door een oudere versie in stukken verdeeld?' 'Done installing BugOS and want the stick completely empty again? Or did an older version split it into pieces?') ($y + 186) $Grijs -Klein
    $gewoon = Nieuw-Knop (T 'Stick leeg maken…' 'Empty the stick…') 0 ($y + 6) 220

    function script:Get-GekozenStick {
        $sticks = $script:W.sticks
        if ($sticks.Count -eq 0) { Toon (T 'Steek eerst een USB-stick in, en ga dan terug en weer verder.' 'Plug in a USB stick first, then go back and forward again.'); return $null }
        $stick = $sticks[$script:W.stick.SelectedIndex]
        # Staan je bestanden uit stap 3 op deze stick? Dan niet wissen: die ben je anders kwijt (U095).
        if (Test-SwitchBestanden $stick.Number) {
            Toon (T "Op '$($stick.FriendlyName)' staan je bestanden uit stap 3 (de map BugOS-Switch). Die zou je kwijtraken. Zet ze eerst ergens anders neer, of gebruik een andere stick." "'$($stick.FriendlyName)' holds your files from step 3 (the BugOS-Switch folder). You would lose them. Put them somewhere else first, or use a different stick.") 'Warning'
            return $null
        }
        return $stick
    }

    $maak.Add_Click({
        if (-not $script:IsoGekozen) { Toon (T "Haal eerst BugOS binnen (bij 1): druk op 'BugOS downloaden', of kies je .iso-bestand." "Get BugOS first (at 1): press 'Download BugOS', or choose your .iso file."); return }
        $stick = Get-GekozenStick
        if (-not $stick) { return }
        $hoe = if ($script:IsoManier -eq 'bruikbaar') { T 'Daarna is het een BugOS-stick die je in Windows gewoon kunt blijven gebruiken.' 'After that it is a BugOS stick you can keep using in Windows.' } else { T "Let op: dit .iso-bestand is een oudere BugOS. Dan gebruikt BugOS de hele stick, en Windows ziet daarna twee vreemde schijven en vraagt of je ze wilt formatteren (klik dan op Annuleren). Met een nieuwere BugOS blijft de stick gewoon één schijf." "Note: this .iso file is an older BugOS. Then BugOS uses the whole stick, and afterwards Windows sees two odd drives and asks whether to format them (click Cancel). With a newer BugOS the stick stays one normal drive." }
        if (-not (Vraag (T "ALLES op '$($stick.FriendlyName)' ($([math]::Round($stick.Size / 1GB)) GB) wordt gewist. $hoe Doorgaan?" "EVERYTHING on '$($stick.FriendlyName)' ($([math]::Round($stick.Size / 1GB)) GB) will be erased. $hoe Continue?"))) { return }
        $script:W.stickStatus.ForeColor = $Grijs
        Toon-Onderaan $script:W.stickStatus
        $gestart = Start-BeheerderTaak @('-Taak', 'Usb', '-IsoPad', "`"$($script:IsoGekozen)`"", '-SchijfNummer', [string]$stick.Number, '-SchijfId', "`"$($stick.UniqueId)`"", '-Manier', $script:IsoManier) -Balk $script:W.stickBalk -Label $script:W.stickStatus -Tekst (T 'De USB-stick wordt gemaakt…' 'Making the USB stick…') -Klaar {
            param($r)
            $script:W.stickBalk.Visible = $false
            if ($r.Code -ne 0) {
                $script:W.stickStatus.Text = ''
                Toon-Fout (T 'De USB-stick maken lukte niet' 'Making the USB stick did not work') (T 'Haal de stick eruit, steek hem er weer in en probeer het opnieuw. Lukt het dan nog niet, probeer een andere USB-poort of een andere stick.' 'Unplug the stick, plug it in again and try again. If it still does not work, try another USB port or another stick.') $r.Fout
                return
            }
            # Een klaar-scherm in het venster, geen los meldingsvenster erbovenop.
            $tekst = if ($script:IsoManier -eq 'bruikbaar') {
                T "In Windows heet de stick nu BUGOS. Je kunt er ook je eigen bestanden op zetten; laat alleen de map LiveOS staan.`n`nVolgende stap: zet je bestanden erbij. Haal de stick er dus nog niet uit." "In Windows the stick is now called BUGOS. You can put your own files on it too; just leave the LiveOS folder alone.`n`nNext step: add your files. So do not unplug the stick yet."
            } else {
                T "Deze stick is nu helemaal voor BugOS (een oudere BugOS). Zet je bestanden in de volgende stap dus op een andere USB-schijf." "This stick is now completely for BugOS (an older BugOS). So put your files on another USB drive in the next step."
            }
            Toon-Klaar (T 'De USB-stick is klaar' 'The USB stick is ready') $tekst (T 'Verder: bestanden meenemen' 'Next: take your files')
        }
        if (-not $gestart) { $script:W.stickStatus.Text = '' }
    })

    $gewoon.Add_Click({
        # Een stick die BugOS (ook op de oude manier) helemaal had ingenomen, of die je klaar bent: weer één gewone schijf.
        $stick = Get-GekozenStick
        if (-not $stick) { return }
        if (-not (Vraag (T "ALLES op '$($stick.FriendlyName)' ($([math]::Round($stick.Size / 1GB)) GB) wordt gewist, ook BugOS als dat erop staat. Daarna is het weer een gewone, lege USB-stick. Doorgaan?" "EVERYTHING on '$($stick.FriendlyName)' ($([math]::Round($stick.Size / 1GB)) GB) will be erased, including BugOS if it is on it. After that it is a normal, empty USB stick again. Continue?"))) { return }
        $script:W.stickStatus.ForeColor = $Grijs
        Toon-Onderaan $script:W.stickStatus
        $gestart = Start-BeheerderTaak @('-Taak', 'Herstel', '-SchijfNummer', [string]$stick.Number, '-SchijfId', "`"$($stick.UniqueId)`"") -Balk $script:W.stickBalk -Label $script:W.stickStatus -Tekst (T 'De stick wordt weer gewoon gemaakt…' 'Making the stick normal again…') -Klaar {
            param($r)
            $script:W.stickBalk.Visible = $false
            if ($r.Code -ne 0) {
                $script:W.stickStatus.Text = ''
                Toon-Fout (T 'De stick leeg maken lukte niet' 'Emptying the stick did not work') (T 'Haal de stick eruit, steek hem er weer in en probeer het opnieuw.' 'Unplug the stick, plug it in again and try again.') $r.Fout
                return
            }
            Toon-Klaar (T 'De stick is weer leeg' 'The stick is empty again') (T 'Het is weer een gewone USB-stick, zonder BugOS erop. Je kunt hem in Windows gebruiken zoals je wilt.' 'It is a normal USB stick again, without BugOS on it. You can use it in Windows however you like.')
        }
        if (-not $gestart) { $script:W.stickStatus.Text = '' }
    })
}

# De volgorde van de stappen: eerst de stick (die blijft bruikbaar), dan je bestanden (die kunnen op diezelfde stick),
# en als laatste waar BugOS komt (vlak voor het installeren).
$Paginas = @($Paginas[0], $Paginas[1], $Paginas[4], $Paginas[2], $Paginas[3])

function Toon-Pagina {
    $script:PaginaTeller++   # werk van de vorige pagina (dat je mocht onderbreken) vult deze pagina niet meer
    $vlak.SuspendLayout()
    $vlak.Controls.Clear()
    $vlak.AutoScrollPosition = New-Object System.Drawing.Point(0, 0)
    $stapLabel.Text = if ($script:Pagina -eq 0) { (T 'WELKOM' 'WELCOME') } else { (T "STAP $($script:Pagina) VAN 4" "STEP $($script:Pagina) OF 4") }
    & $Paginas[$script:Pagina]
    $vlak.ResumeLayout()
    Zet-Navigatie
    $laatste = $script:Pagina -eq $Paginas.Count - 1
    $verder.Text = if ($laatste) { (T 'Sluiten' 'Close') } else { (T 'Volgende' 'Next') }
    # Heeft de pagina zelf een rode knop? Dan is 'Volgende' rustig grijs.
    $verder.Tag.Soort = if ($script:Pagina -ge 2) { 'gewoon' } else { 'hoofd' }
    $terug.Invalidate(); $verder.Invalidate(); $zij.Invalidate()
}

# Het klaar-scherm: als iets af is (de stick, je bestanden, ruimte maken), maakt de pagina plaats voor een groot vinkje,
# wat er nu is en wat je daarna doet, met een knop naar de volgende stap. 'Nog een keer' tekent de pagina opnieuw.
# Let op: de schakelaar heet niet -Fout: dan zou hij de kleur $Fout verbergen (PowerShell kent geen hoofdletters).
function Toon-Klaar([string] $titel, [string] $tekst, [string] $verderTekst = '', [switch] $Mislukt) {
    $vlak.SuspendLayout()
    $vlak.Controls.Clear()
    $vlak.AutoScrollPosition = New-Object System.Drawing.Point(0, 0)
    $icoon = New-Object System.Windows.Forms.Panel
    Plaats $icoon 0 6 64 64
    Zet-Dubbel $icoon
    $icoon.Tag = [bool]$Mislukt
    $icoon.Add_Paint({
        param($s, $e)
        $g = $e.Graphics
        $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
        $kwast = New-Object System.Drawing.SolidBrush($(if ($s.Tag) { $Fout } else { $Goed }))
        $g.FillEllipse($kwast, (Fx 2), (Fx 2), (Fx 58), (Fx 58))
        $kwast.Dispose()
        $pen = Nieuwe-Pen $Wit 4.2
        if ($s.Tag) {
            $g.DrawLine($pen, (Punt 21 21), (Punt 41 41)); $g.DrawLine($pen, (Punt 41 21), (Punt 21 41))
        } else {
            $g.DrawLines($pen, [System.Drawing.PointF[]]@((Punt 18 32), (Punt 27 41), (Punt 44 22)))
        }
        $pen.Dispose()
    })
    $vlak.Controls.Add($icoon)
    $kopje = New-Object System.Windows.Forms.Label
    $kopje.Font = $script:LetterTitel; $kopje.ForeColor = $Inkt; $kopje.Text = $titel
    Plaats $kopje 84 8 ($script:Breedte - 84) 30
    $vlak.Controls.Add($kopje)
    # De tekst bepaalt zelf zijn hoogte (AutoSize met een maximale breedte): uitrekenen met MeasureText viel op 150%
    # net te klein uit, dan viel de laatste regel weg.
    $uitleg = New-Object System.Windows.Forms.Label
    $uitleg.Font = $script:LetterGewoon; $uitleg.ForeColor = $Grijs
    $uitleg.Location = New-Object System.Drawing.Point((Px 84), (Px 44))
    $uitleg.MaximumSize = New-Object System.Drawing.Size((Px ($script:Breedte - 84)), 0)
    $uitleg.AutoSize = $true
    $uitleg.Text = $tekst
    $vlak.Controls.Add($uitleg)
    $y = 44 + [math]::Ceiling([double]$uitleg.PreferredSize.Height / $script:Schaal) + 16
    if ($verderTekst) {
        $verder2 = Nieuw-Knop $verderTekst 84 $y 260 'hoofd'
        $verder2.Add_Click({
            if ($script:Pagina -ge $Paginas.Count - 1) { $form.Close() } else { $script:Pagina++; Toon-Pagina }
        })
    }
    $opnieuwTekst = if ($Mislukt) { T 'Opnieuw proberen' 'Try again' } else { T 'Nog een keer' 'Again' }
    $opnieuw = Nieuw-Knop $opnieuwTekst $(if ($verderTekst) { 356 } else { 84 }) $y $(if ($Mislukt) { 220 } else { 160 }) $(if ($Mislukt -and -not $verderTekst) { 'hoofd' } else { 'gewoon' })
    $opnieuw.Add_Click({ Toon-Pagina })
    $vlak.ResumeLayout()
}

function Toon-Fout([string] $titel, [string] $watNu, [string] $reden) {
    # Wat er misging in gewone woorden, wat je kunt doen, en de reden van Windows (voor als je hulp vraagt) eronder.
    $tekst = $watNu
    if ($reden) { $tekst += "`n`n" + (T 'Wat Windows zei (handig als je om hulp vraagt): ' 'What Windows said (useful if you ask for help): ') + ($reden -replace '\s*Activity ID:\s*\{[^}]*\}', '').Trim() }
    Toon-Klaar $titel $tekst -Mislukt
}

$terug.Add_Click({ if ($script:Pagina -gt 0 -and -not (Test-Bezig)) { $script:Pagina--; Toon-Pagina } })
$verder.Add_Click({
    if (Test-Bezig) { return }
    if ($script:Pagina -ge $Paginas.Count - 1) { $form.Close() } else { $script:Pagina++; Toon-Pagina }
})

if ($Taak -eq 'Foto') {
    # Alleen voor de bouwstraat op GitHub: van elke pagina een plaatje maken,
    # zodat we het ontwerp kunnen nakijken zonder Windows-computer.
    if (-not $FotoMap) { $FotoMap = Join-Path $env:TEMP 'bugos-switch-fotos' }
    New-Item -ItemType Directory -Force -Path $FotoMap | Out-Null
    $form.StartPosition = 'Manual'
    $form.Location = New-Object System.Drawing.Point(0, 0)
    $form.Show()
    # Ook het klaar-scherm en het foutscherm (die zie je anders alleen na echt werk): als extra plaatjes.
    $extra = @(
        { $script:Pagina = 2; Toon-Pagina; Toon-Klaar (T 'De USB-stick is klaar' 'The USB stick is ready') (T "In Windows heet de stick nu BUGOS. Je kunt er ook je eigen bestanden op zetten; laat alleen de map LiveOS staan.`n`nVolgende stap: zet je bestanden erbij. Haal de stick er dus nog niet uit." "In Windows the stick is now called BUGOS. You can put your own files on it too; just leave the LiveOS folder alone.`n`nNext step: add your files. So do not unplug the stick yet.") (T 'Verder: bestanden meenemen' 'Next: take your files') },
        { $script:Pagina = 2; Toon-Pagina; Toon-Fout (T 'De USB-stick maken lukte niet' 'Making the USB stick did not work') (T 'Haal de stick eruit, steek hem er weer in en probeer het opnieuw. Lukt het dan nog niet, probeer een andere USB-poort of een andere stick.' 'Unplug the stick, plug it in again and try again. If it still does not work, try another USB port or another stick.') 'The disk has already been initialized. Activity ID: {1ba05f16-7cf6-0008-ac5f-b31bf67cdd01}' },
        { $script:Plek = 'vervang'; $script:Pagina = 4; Toon-Pagina },
        { $script:Plek = 'ander'; $script:Pagina = 4; Toon-Pagina }
    )
    for ($i = 0; $i -lt $Paginas.Count + $extra.Count; $i++) {
        if ($i -lt $Paginas.Count) {
            $script:Pagina = $i
            Toon-Pagina
        } else {
            & $extra[$i - $Paginas.Count]
        }
        # Werk ernaast (de controle, de grootte) eerst laten afmaken: anders staat er op het plaatje 'even kijken'.
        $klok = [System.Diagnostics.Stopwatch]::StartNew()
        while ($script:Werken.Count -gt 0 -and $klok.ElapsedMilliseconds -lt 60000) { [System.Windows.Forms.Application]::DoEvents(); Start-Sleep -Milliseconds 20 }
        $form.ActiveControl = $null
        [System.Windows.Forms.Application]::DoEvents()
        $bmp = New-Object System.Drawing.Bitmap((Px 880), (Px 560))
        $gr = [System.Drawing.Graphics]::FromImage($bmp); $gr.Clear($Wit); $gr.Dispose()
        for ($c = $form.Controls.Count - 1; $c -ge 0; $c--) {
            $ctl = $form.Controls[$c]
            if ($ctl.Visible) { $ctl.DrawToBitmap($bmp, $ctl.Bounds) }
        }
        $bmp.Save((Join-Path $FotoMap "overstap-$i.png"), [System.Drawing.Imaging.ImageFormat]::Png)
        $bmp.Dispose()
        try {
            $r = $form.Bounds
            $scherm = New-Object System.Drawing.Bitmap($r.Width, $r.Height)
            $gr = [System.Drawing.Graphics]::FromImage($scherm)
            $gr.CopyFromScreen($r.Location, [System.Drawing.Point]::Empty, $r.Size)
            $gr.Dispose()
            $scherm.Save((Join-Path $FotoMap "scherm-$i.png"), [System.Drawing.Imaging.ImageFormat]::Png)
            $scherm.Dispose()
        } catch { Write-Output "Schermfoto lukte niet: $($_.Exception.Message)" }
    }
    $form.Close()
    exit 0
}


if ($Taak -eq 'Zelftest') {
    # Alleen voor de bouwstraat op GitHub (windows-switch.yml): wat je niet op een plaatje ziet. Het werk loopt NAAST het
    # venster (het venster blijft bewegen), fouten komen netjes terug, de ISO wordt goed gelezen, en (met -IsoPad en
    # -SchijfNummer van een nep-stick uit een bestand) de stick wordt goed gemaakt en weer gewoon gemaakt.
    $script:ZtFouten = 0
    function Klopt([bool] $ok, [string] $wat) {
        # Meteen naar buiten (Console schrijft direct door): zo zie je ook bij een vastloper hoe ver het kwam.
        if ($ok) { [Console]::WriteLine("OK    $wat") } else { [Console]::WriteLine("FOUT  $wat"); $script:ZtFouten++ }
    }
    function Stap([string] $wat) { [Console]::WriteLine("--- $wat") }
    function Wacht-Werk([int] $ms = 120000) {
        $klok = [System.Diagnostics.Stopwatch]::StartNew()
        while ($script:Werken.Count -gt 0 -and $klok.ElapsedMilliseconds -lt $ms) { [System.Windows.Forms.Application]::DoEvents(); Start-Sleep -Milliseconds 15 }
    }
    $script:Zt = @{}

    Stap 'werk naast het venster'
    # 1. Het werk loopt op een andere draad dan het venster, en het venster ziet de voortgang onderweg.
    $label = New-Object System.Windows.Forms.Label
    $balk = Nieuw-Balk 0 0 200 $vlak
    $gezien = New-Object 'System.Collections.Generic.HashSet[string]'
    Start-Werk -Balk $balk -Label $label -Werk {
        for ($i = 1; $i -le 12; $i++) { & $Voortgang ($i * 8) "stap $i"; Start-Sleep -Milliseconds 120 }
        [System.Threading.Thread]::CurrentThread.ManagedThreadId
    } -Klaar { param($staat) $script:Zt.Draad = @($staat.Uitkomst)[-1]; $script:Zt.Fout1 = $staat.Fout }
    $klok = [System.Diagnostics.Stopwatch]::StartNew()
    while ($script:Werken.Count -gt 0 -and $klok.ElapsedMilliseconds -lt 30000) {
        [System.Windows.Forms.Application]::DoEvents(); [void]$gezien.Add($label.Text); Start-Sleep -Milliseconds 15
    }
    Klopt ($script:Zt.Draad -and $script:Zt.Draad -ne [System.Threading.Thread]::CurrentThread.ManagedThreadId -and -not $script:Zt.Fout1) "het werk loopt naast het venster (draad $($script:Zt.Draad))"
    Klopt ($gezien.Count -ge 4) "het venster ziet de voortgang onderweg ($($gezien.Count) verschillende teksten)"

    Stap 'een fout in het werk'
    # 2. Een fout in het werk komt terug als gewone tekst (geen vastgelopen venster).
    Start-Werk -Werk { throw 'kapot met opzet' } -Klaar { param($staat) $script:Zt.Fout2 = $staat.Fout }
    Wacht-Werk
    Klopt ($script:Zt.Fout2 -eq 'kapot met opzet') "een fout komt netjes terug ($($script:Zt.Fout2))"

    Stap 'functies in de runspace'
    # 3. De functies van het programma werken in de runspace, met wat je meegeeft (een extra map).
    $map = Join-Path $env:TEMP ('bugos-zelftest-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force -Path (Join-Path $map 'Extra') | Out-Null
    [System.IO.File]::WriteAllBytes((Join-Path $map 'Extra\een.bin'), (New-Object byte[] 300000))
    $zonder = 0L
    Start-Werk -Werk { Get-MeeneemGrootte } -Klaar { param($staat) $script:Zt.Zonder = [int64](@($staat.Uitkomst)[-1]) }
    Wacht-Werk
    Start-Werk -Mee @{ ExtraMappen = @((Join-Path $map 'Extra')); CloudMee = $true } -Werk { Get-MeeneemGrootte } -Klaar { param($staat) $script:Zt.Met = [int64](@($staat.Uitkomst)[-1]); $script:Zt.Fout3 = $staat.Fout }
    Wacht-Werk
    Klopt (($script:Zt.Met - $script:Zt.Zonder) -eq 300000) "Get-MeeneemGrootte in de runspace telt de extra map mee ($($script:Zt.Zonder) -> $($script:Zt.Met) $($script:Zt.Fout3))"
    Start-Werk -TerugVars @('Deels') -Mee @{ ExtraMappen = @((Join-Path $map 'Extra')); CloudMee = $true; Doel = "$map\" } -Werk {
        $null = Invoke-Meenemen $Mee.Doel $Voortgang
        Test-Path -LiteralPath (Join-Path $Mee.Doel 'BugOS-Switch\bugos-switch.json')
    } -Klaar { param($staat) $script:Zt.Json = @($staat.Uitkomst)[-1]; $script:Zt.Fout4 = $staat.Fout; $script:Zt.Deels = $staat.Terug.ContainsKey('Deels') }
    Wacht-Werk 300000
    Klopt ($script:Zt.Json -eq $true -and $script:Zt.Deels -and -not $script:Zt.Fout4) "Invoke-Meenemen in de runspace: bugos-switch.json staat er, Deels komt terug ($($script:Zt.Fout4))"
    Klopt (Test-Path -LiteralPath (Join-Path $map 'BugOS-Switch\Extra')) 'de extra map is meegekopieerd'

    Stap 'de ISO lezen'
    # 4. De ISO zelf lezen (gemaakt met pycdlib zoals xorriso -R: alleen Rock Ridge-namen, geen Joliet).
    if ($IsoPad) {
        $info = Get-IsoStickInfo $IsoPad
        Klopt ($info.Bruikbaar) "de test-ISO kan op een bruikbare stick (merkteken gevonden; mist: $($info.Mist -join ', '))"
        Klopt ((Get-IsoGrootte $info.Kaart 'LiveOS/squashfs.img') -eq 3000000) 'de grootte van LiveOS/squashfs.img klopt'
        Klopt ($info.Kaart.Bestanden.ContainsKey('liveos/SQUASHFS.IMG')) 'namen: hoofdletters tellen niet'
        $grub = [System.Text.Encoding]::UTF8.GetString((Read-IsoBytes $info.Kaart 'EFI/BOOT/grub.cfg'))
        $om = ConvertTo-StickGrub $grub
        Klopt ($om -match 'root=live:LABEL=BUGOS ' -and $om -match "-l 'BUGOS-EFI'" -and $om -notmatch 'CDLABEL') 'grub.cfg voor de stick: BugOS op BUGOS, de kernel op BUGOS-EFI'
        $oud = Join-Path $env:TEMP 'bugos-zelftest-oud.iso'
        $b = [System.IO.File]::ReadAllBytes($IsoPad)
        $tekst = [System.Text.Encoding]::ASCII.GetString($b)
        # Het merkteken uit élke grub.cfg halen (er zijn er twee: EFI/BOOT en EFI/fedora).
        $plek = $tekst.IndexOf('bugos.stick=2')
        while ($plek -ge 0) {
            foreach ($k in 0..12) { $b[$plek + $k] = [byte][char]'x' }
            $plek = $tekst.IndexOf('bugos.stick=2', $plek + 13)
        }
        [System.IO.File]::WriteAllBytes($oud, $b)
        Klopt (-not (Get-IsoStickInfo $oud).Bruikbaar) 'een ISO zonder merkteken: de oude manier'
        $nep = Join-Path $env:TEMP 'bugos-zelftest-nep.iso'
        [System.IO.File]::WriteAllBytes($nep, (New-Object byte[] 100000))
        $fout = ''
        try { [void](Read-IsoMap $nep) } catch { $fout = $_.Exception.Message }
        Klopt ($fout -ne '') "geen ISO: een gewone foutmelding ($fout)"
    }

    Stap 'de stick op een nep-stick'
    # 5. De stick op een nep-stick (VHD): bruikbaar maken, nakijken, en weer gewoon maken (als beheerder-taak).
    if ($IsoPad -and $SchijfNummer -ge 0) {
        $teksten = New-Object 'System.Collections.Generic.List[string]'
        $letter = Write-BugOSStick $IsoPad $SchijfNummer { param($p, $t) $teksten.Add("$p $t") } '' -Test
        $delen = @(Get-Partition -DiskNumber $SchijfNummer | Sort-Object PartitionNumber)
        Klopt ($delen.Count -eq 2) "twee delen op de stick ($($delen.Count))"
        $vol1 = $delen[0] | Get-Volume
        Klopt ($vol1.FileSystem -eq 'exFAT' -and $vol1.FileSystemLabel -eq 'BUGOS') "deel 1: exFAT met de naam BUGOS ($($vol1.FileSystem) $($vol1.FileSystemLabel))"
        Klopt ([int]$delen[1].MbrType -eq 0xEF -and -not ("$($delen[1].DriveLetter)" -match '[A-Z]')) "deel 2: opstartdeel van type EF, zonder letter ($($delen[1].MbrType))"
        $squash = Join-Path $letter 'LiveOS\squashfs.img'
        Klopt ((Test-Path -LiteralPath $squash) -and (Get-Item -LiteralPath $squash).Length -eq 3000000) 'LiveOS\squashfs.img staat op BUGOS, heel'
        Klopt (Test-Path -LiteralPath (Join-Path $letter 'Over deze BugOS-stick.txt')) 'een uitleg op de stick'
        Klopt (@($teksten | Where-Object { $_ -match '^\d+ BugOS op de stick' }).Count -ge 1) 'voortgang in procenten tijdens het kopiëren'
        # Het opstartdeel even zichtbaar maken om na te kijken.
        Set-Partition -DiskNumber $SchijfNummer -PartitionNumber 2 -MbrType 0x0C
        Add-PartitionAccessPath -DiskNumber $SchijfNummer -PartitionNumber 2 -AssignDriveLetter
        Start-Sleep -Seconds 1
        $efi = "$((Get-Partition -DiskNumber $SchijfNummer -PartitionNumber 2).DriveLetter):\"
        $cfg = [System.IO.File]::ReadAllText((Join-Path $efi 'EFI\BOOT\grub.cfg'))
        Klopt ((Test-Path (Join-Path $efi 'EFI\BOOT\BOOTX64.EFI')) -and (Test-Path (Join-Path $efi 'images\pxeboot\vmlinuz')) -and (Test-Path (Join-Path $efi 'images\pxeboot\initrd.img'))) 'opstartdeel: shim, kernel en initrd'
        Klopt ($cfg -match 'root=live:LABEL=BUGOS ' -and $cfg -match "'BUGOS-EFI'" -and [int][char]$cfg[0] -ne 0xFEFF) 'opstartdeel: grub.cfg voor de stick, zonder BOM'
        Klopt ((Get-Volume -DriveLetter $efi.Substring(0, 1)).FileSystemLabel -eq 'BUGOS-EFI') 'opstartdeel heet BUGOS-EFI'
        Remove-PartitionAccessPath -DiskNumber $SchijfNummer -PartitionNumber 2 -AccessPath $efi
        Stap 'weer gewoon maken (beheerder-taak)'
        # Weer gewoon maken, als beheerder-taak zoals in het venster (voortgang via het bestand, het venster blijft bewegen).
        $disk = Get-Disk -Number $SchijfNummer
        $gestart = Start-BeheerderTaak @('-Taak', 'Herstel', '-SchijfNummer', [string]$SchijfNummer, '-SchijfId', "`"$($disk.UniqueId)`"", '-TestSchijf') -Klaar { param($r) $script:Zt.Herstel = $r }
        Wacht-Werk 180000
        Klopt ($gestart -and $script:Zt.Herstel -and $script:Zt.Herstel.Code -eq 0) "stick weer gewoon maken als beheerder-taak ($($script:Zt.Herstel.Code) $($script:Zt.Herstel.Fout))"
        $na = @(Get-Partition -DiskNumber $SchijfNummer)
        Klopt ($na.Count -eq 1 -and ($na[0] | Get-Volume).FileSystemLabel -eq 'USB-STICK') "daarna: één gewone schijf USB-STICK ($($na.Count))"
        $fout = ''
        try { Test-StickSchijf (Get-Disk -Number $SchijfNummer) } catch { $fout = $_.Exception.Message }
        Klopt ($fout -ne '') 'zonder -Test weigert de Switch een schijf die geen USB-stick is'
        $fout = ''
        $c = Get-Disk | Where-Object { $_.IsBoot } | Select-Object -First 1
        try { Test-StickSchijf $c -Test } catch { $fout = $_.Exception.Message }
        Klopt ($fout -ne '') 'nooit de schijf van Windows, ook niet in de zelftest'
    }
    Remove-Item -LiteralPath $map -Recurse -Force -ErrorAction SilentlyContinue
    [Console]::WriteLine('')
    [Console]::WriteLine("$($script:ZtFouten) fout(en).")
    exit ([int]($script:ZtFouten -gt 0))
}

Toon-Pagina
[void]$form.ShowDialog()
