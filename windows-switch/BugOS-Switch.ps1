#Requires -Version 5.1
<#
.SYNOPSIS
    BugOS Overstap - van Windows naar BugOS, in vier simpele stappen.

.DESCRIPTION
    Jip-en-Janneke:
      1. Controleren  - kan deze computer BugOS draaien?
      2. Meenemen     - je documenten, foto's, muziek, video's, bureaublad,
                        downloads, bladwijzers en achtergrond naar een USB-schijf.
      3. Ruimte maken - (alleen als je BugOS naast Windows wilt) Windows een
                        beetje kleiner maken zodat BugOS ernaast past.
      4. USB-stick    - de BugOS-installatie op een USB-stick zetten.

    Starten: dubbelklik op "Start BugOS Switch.bat".

    Licentie: GPL-3.0-or-later. Onderdeel van BugOS.
#>

param(
    # Alleen intern gebruikt: dezelfde stap opnieuw starten als beheerder.
    [ValidateSet('', 'Krimp', 'Usb', 'Foto')] [string] $Taak = '',
    [int] $KrimpGB = 0,
    [string] $IsoPad = '',
    [int] $SchijfNummer = -1,
    # Welke schijf het precies moet zijn (gekozen in stap 4): na eruit halen/insteken kan een andere hetzelfde nummer krijgen (U370).
    [string] $SchijfId = '',
    # Taal kiezen (nl of en). Leeg = de taal van Windows.
    [ValidateSet('', 'nl', 'en')] [string] $Taal = '',
    # Alleen voor de bouwstraat: plaatjes van elke pagina maken.
    [string] $FotoMap = '',
    [double] $FotoSchaal = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

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
    [void][System.Windows.Forms.MessageBox]::Show($tekst, 'BugOS Overstap', 'OK', $soort)
}

function Vraag([string] $tekst) {
    [System.Windows.Forms.MessageBox]::Show($tekst, 'BugOS Overstap', 'YesNo', 'Warning') -eq 'Yes'
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

function Get-MeeneemGrootte {
    $totaal = 0L
    foreach ($m in $script:Mappen) {
        $pad = Get-BekendeMap $m.Sleutel
        if ($pad -and (Test-Path $pad)) {
            $som = (Get-ChildItem -LiteralPath $pad -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
            if ($som) { $totaal += $som }
        }
    }
    return $totaal
}

function Invoke-Meenemen([string] $doelSchijf, [scriptblock] $Voortgang) {
    $doel = Join-Path $doelSchijf 'BugOS-Switch'
    New-Item -ItemType Directory -Force -Path $doel | Out-Null
    $stap = 0
    $aantal = $script:Mappen.Count + 2
    # Mappen waar een paar bestanden niet mee konden (open in een programma, groter dan 4 GB op FAT32, alleen in
    # OneDrive): de rest gaat gewoon door (U094).
    $script:Deels = @()
    foreach ($m in $script:Mappen) {
        $stap++
        $bron = Get-BekendeMap $m.Sleutel
        & $Voortgang ([int](100 * $stap / $aantal)) (T "Kopiëren: $($m.Naam)..." "Copying: $($m.Naam)...")
        if ($bron -and (Test-Path $bron)) {
            # /E alle submappen, /R:1 /W:1 niet eindeloos wachten, /XJ geen snelkoppel-lussen,
            # /XF geen Windows-hulpbestanden (die zie je anders in elke map in BugOS) (U096).
            $null = robocopy $bron (Join-Path $doel $m.Naam) /E /R:1 /W:1 /XJ /NFL /NDL /NJH /NJS /NP /XF desktop.ini Thumbs.db
            # robocopy: 8 = een paar bestanden niet, 16 = helemaal mislukt (bijv. de schijf is weg).
            if ($LASTEXITCODE -ge 16) { throw (T "Kopiëren van $($m.Naam) lukte niet." "Copying $($m.Naam) failed.") }
            if ($LASTEXITCODE -ge 8) { $script:Deels += $m.Naam }
        }
    }

    # Bladwijzers van Chrome, Edge en Brave (allemaal hetzelfde JSON-formaat).
    $stap++
    & $Voortgang ([int](100 * $stap / $aantal)) (T 'Bladwijzers meenemen...' 'Taking bookmarks...')
    $bw = Join-Path $doel 'Bladwijzers'
    New-Item -ItemType Directory -Force -Path $bw | Out-Null
    $browsers = @{
        'Chrome' = "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Bookmarks"
        'Edge'   = "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Bookmarks"
        'Brave'  = "$env:LOCALAPPDATA\BraveSoftware\Brave-Browser\User Data\Default\Bookmarks"
    }
    foreach ($b in $browsers.GetEnumerator()) {
        if (Test-Path $b.Value) { Copy-Item -LiteralPath $b.Value -Destination (Join-Path $bw "$($b.Key).json") -Force }
    }
    # Firefox: de nieuwste automatische bladwijzer-back-up.
    Get-ChildItem "$env:APPDATA\Mozilla\Firefox\Profiles\*\bookmarkbackups\*.jsonlz4" -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1 |
        ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $bw 'Firefox.jsonlz4') -Force }

    # De bureaubladachtergrond, zodat BugOS meteen vertrouwd voelt.
    $stap++
    & $Voortgang ([int](100 * $stap / $aantal)) (T 'Achtergrond meenemen...' 'Taking wallpaper...')
    $achtergrond = "$env:APPDATA\Microsoft\Windows\Themes\TranscodedWallpaper"
    if (Test-Path $achtergrond) { Copy-Item -LiteralPath $achtergrond -Destination (Join-Path $doel 'achtergrond.jpg') -Force }

    $info = [ordered]@{
        versie     = 1
        gemaakt    = (Get-Date).ToString('s')
        gebruiker  = $env:USERNAME
        computer   = $env:COMPUTERNAME
        taal       = (Get-Culture).Name
        mappen     = @($script:Mappen | ForEach-Object { $_.Naam })
        deels      = @($script:Deels)
    }
    $info | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $doel 'bugos-switch.json') -Encoding UTF8
    & $Voortgang 100 (T 'Klaar!' 'Done!')
}

# ======================================================== 3. RUIMTE MAKEN ==

function Get-KrimpMogelijk {
    $part = Get-Partition -DriveLetter C
    $grens = Get-PartitionSupportedSize -DriveLetter C
    $kanWeg = [math]::Floor(($part.Size - $grens.SizeMin) / 1GB) - 10   # 10 GB marge voor Windows
    return [math]::Max(0, $kanWeg)
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

    & $Voortgang 100 (T 'Controleren of alles goed is overgekomen...' 'Checking that everything arrived correctly...')
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
    $balk.Tag = @{ Waarde = 0.0 }
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

if ($Taak -eq 'Krimp') {
    try {
        Invoke-Krimp $KrimpGB
        Set-KlokUtc
        exit 0
    } catch { Toon ((T 'Ruimte maken lukte niet: ' 'Making space failed: ') + $_.Exception.Message) 'Error'; exit 1 }
}
if ($Taak -eq 'Usb') {
    Maak-Letters
    $form = New-Object System.Windows.Forms.Form
    $form.Text = 'BugOS Overstap'
    $form.AutoScaleMode = 'None'
    $form.Font = $script:LetterGewoon
    $form.ClientSize = New-Object System.Drawing.Size((Px 540), (Px 160))
    $form.StartPosition = 'CenterScreen'
    $form.FormBorderStyle = 'FixedSingle'
    $form.MaximizeBox = $false; $form.MinimizeBox = $false
    $form.BackColor = $Wit
    try { $form.Icon = [System.Drawing.Icon]::FromHandle(([System.Drawing.Bitmap]$script:IcoonBeeld).GetHicon()) } catch { Write-Verbose 'Geen icoon.' }
    $kopje = New-Object System.Windows.Forms.Label
    Plaats $kopje 32 26 476 32
    $kopje.Font = $script:LetterTitel; $kopje.ForeColor = $Inkt
    $kopje.Text = (T 'De USB-stick wordt gemaakt' 'Making the USB stick')
    $form.Controls.Add($kopje)
    $lbl = New-Object System.Windows.Forms.Label
    Plaats $lbl 32 64 476 26
    $lbl.ForeColor = $Grijs
    $form.Controls.Add($lbl)
    $bar = Nieuw-Balk 32 108 476 $form
    $form.Show(); [System.Windows.Forms.Application]::DoEvents()
    try {
        Write-IsoNaarSchijf $IsoPad $SchijfNummer { param($p, $t) Zet-Balk $bar $p; $lbl.Text = $t; [System.Windows.Forms.Application]::DoEvents() } $SchijfId
        Set-KlokUtc
        $form.Close(); exit 0
    } catch {
        $form.Close(); Toon ((T 'De USB-stick maken lukte niet: ' 'Making the USB stick failed: ') + $_.Exception.Message) 'Error'; exit 1
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
$form.Text = 'BugOS Overstap'
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

function Teken-Zijbalk($zij, $e) {
    $g = $e.Graphics
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.DrawImage($script:ZijBeeld, 0, 0, $zij.Width, $zij.Height)
    $g.DrawImage($script:LogoBeeld, (Fx 28), (Fx 32), (Fx 118), (Fx 32))

    $namen = @((T 'Welkom' 'Welcome'), (T 'Controleren' 'Check'), (T 'Bestanden meenemen' 'Take your files'), (T 'Ruimte maken' 'Make space'), (T 'USB-stick maken' 'Make USB stick'))
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
    $vak = New-Object System.Drawing.Rectangle((Px 28), (Px 486), (Px 190), (Px 50))
    [System.Windows.Forms.TextRenderer]::DrawText($g, (T 'Er gebeurt niks zonder dat jij op een knop drukt.' 'Nothing happens until you press a button.'), $script:LetterNoot, $vak, (Kleur '#A6ABB6'), [System.Windows.Forms.TextFormatFlags]'WordBreak, NoPadding')
}

function Meet-Hoogte([string] $tekst, $letter, [double] $breedte) {
    $maat = [System.Windows.Forms.TextRenderer]::MeasureText($tekst, $letter, (New-Object System.Drawing.Size((Px $breedte), 0)), [System.Windows.Forms.TextFormatFlags]'WordBreak')
    [math]::Ceiling($maat.Height / $script:Schaal)
}

function Nieuw-Label([string] $tekst, [double] $y, [double] $h = 0, $kleur = $null, [switch] $Vet) {
    $l = New-Object System.Windows.Forms.Label
    $l.Font = if ($Vet) { $script:LetterVet } else { $script:LetterGewoon }
    $l.ForeColor = if ($kleur) { $kleur } else { $Inkt }
    if ($h -le 0) { $h = (Meet-Hoogte $tekst $l.Font $script:Breedte) + 4 }
    Plaats $l 0 $y $script:Breedte $h
    $l.Text = $tekst
    $vlak.Controls.Add($l)
    return $l
}

# Een stuk tekst; geeft terug waar het ophoudt.
function Nieuw-Tekst([string] $tekst, [double] $y, $kleur = $null, [switch] $Vet) {
    $l = Nieuw-Label $tekst $y 0 $kleur -Vet:$Vet
    return $y + [math]::Ceiling($l.Height / $script:Schaal)
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
    $kop.Text = (T 'Welkom bij de BugOS Overstap' 'Welcome to BugOS Overstap')
    $y = Nieuw-Tekst (T 'Dit programma helpt je om over te stappen van Windows naar BugOS. Het gaat in vier stappen:' 'This program helps you move from Windows to BugOS. It takes four steps:') 0
    $y += 14
    $y += (Nieuw-Rij 'nummer' (T 'Controleren' 'Check') (T 'Kijken of je computer BugOS aankan.' 'See whether your computer can run BugOS.') $y '1') + 10
    $y += (Nieuw-Rij 'nummer' (T 'Bestanden meenemen' 'Take your files') (T "Je foto's, documenten en meer naar een USB-schijf zetten." 'Put your photos, documents and more on a USB drive.') $y '2') + 10
    $y += (Nieuw-Rij 'nummer' (T 'Ruimte maken' 'Make space') (T 'BugOS naast Windows zetten. Deze stap mag je overslaan.' 'Put BugOS next to Windows. You may skip this step.') $y '3') + 10
    [void](Nieuw-Rij 'nummer' (T 'USB-stick maken' 'Make the USB stick') (T 'De BugOS-installatie op een USB-stick zetten.' 'Put the BugOS installer on a USB stick.') $y '4')
}

# --- Pagina 1: controle -----------------------------------------------------
$Paginas += {
    $kop.Text = (T 'Kan mijn computer BugOS aan?' 'Can my computer run BugOS?')
    $y = 0
    foreach ($r in (Get-Controle)) {
        $soort = if (-not $r.Ok) { 'fout' } elseif ($r.Waarschuwing) { 'let_op' } else { 'goed' }
        $y += (Nieuw-Rij $soort $r.Naam $r.Tekst $y) + 10
    }
}

# --- Pagina 2: meenemen -----------------------------------------------------
$Paginas += {
    $kop.Text = (T 'Je bestanden meenemen' 'Take your files with you')
    $groot = [math]::Round((Get-MeeneemGrootte) / 1GB, 1)
    $y = Nieuw-Tekst (T "Je documenten, foto's, muziek, video's, bureaublad, downloads, bladwijzers en achtergrond ($groot GB) gaan naar een USB-schijf. In BugOS zet je ze terug met één klik. Dit is ook meteen een back-up! Gebruik een andere schijf dan de USB-stick voor BugOS (stap 4): die wordt gewist." "Your documents, photos, music, videos, desktop, downloads, bookmarks and wallpaper ($groot GB) go to a USB drive. In BugOS you put them back with one click. This is also a backup! Use a different drive than the USB stick for BugOS (step 4): that one is erased.") 0
    $y = Nieuw-Tekst (T 'Kies de USB-schijf:' 'Choose the USB drive:') ($y + 16) -Vet
    $script:W.schijf = Nieuw-Lijst ($y + 4) 400
    $lijst = $script:W.schijf
    # Alleen schijven die je eruit haalt: een D:-schijf in de laptop gaat mee de prullenbak in als je straks
    # bij het installeren de hele schijf kiest (U284). Een vaste (type 3) schijf telt alleen als hij via USB hangt.
    Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DeviceID -ne 'C:' -and ($_.DriveType -eq 2 -or ($_.DriveType -eq 3 -and (Test-UsbLetter $_))) } | ForEach-Object {
        [void]$lijst.Items.Add("$($_.DeviceID)  $($_.VolumeName)  ($([math]::Round($_.FreeSpace / 1GB)) GB $(T 'vrij' 'free'))")
    }
    if ($lijst.Items.Count -gt 0) { $lijst.SelectedIndex = 0 }
    $script:W.knop = Nieuw-Knop (T 'Bestanden kopiëren' 'Copy files') 0 ($y + 52) 220 'hoofd'
    $script:W.balk = Nieuw-Balk 0 ($y + 114) ($script:Breedte - 4) $vlak
    $script:W.status = Nieuw-Label '' ($y + 134) 48 $Grijs
    $script:W.knop.Add_Click({
        $lijst = $script:W.schijf; $balk = $script:W.balk; $status = $script:W.status; $knop = $script:W.knop
        if ($lijst.SelectedIndex -lt 0) { Toon (T 'Steek eerst een USB-schijf in en ga even terug en weer verder.' 'Plug in a USB drive first, then go back and forward again.'); return }
        $letter = ($lijst.SelectedItem -split '\s+')[0] + '\'
        $vrij = (Get-PSDrive $letter.Substring(0, 1)).Free
        # Wat er al in BugOS-Switch staat (een eerdere keer), hoeft er niet nog een keer bij (U286).
        $al = 0L
        if (Test-Path -LiteralPath "$($letter)BugOS-Switch") { $al = [int64](Get-ChildItem -LiteralPath "$($letter)BugOS-Switch" -Recurse -File -Force -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum }
        if ($vrij + $al -lt (Get-MeeneemGrootte)) { Toon (T 'Er is niet genoeg ruimte op die schijf.' 'Not enough space on that drive.') 'Warning'; return }
        $knop.Enabled = $false; $verder.Enabled = $false
        try {
            Invoke-Meenemen $letter { param($p, $t) Zet-Balk $balk $p; $status.Text = $t; [System.Windows.Forms.Application]::DoEvents() }
            $nogVrij = (Get-PSDrive $letter.Substring(0, 1)).Free
            if ($script:Deels.Count -gt 0 -and $nogVrij -lt 64MB) {
                # Vol geraakt (kleine bestanden nemen op een grote stick meer ruimte in dan ze groot zijn) (U288).
                $status.Text = (T 'De schijf is vol geraakt: niet alles kon mee. Gebruik een grotere schijf, of maak ruimte op deze en klik nog een keer.' 'The drive got full: not everything could be copied. Use a bigger drive, or make room on this one and click again.')
                $status.ForeColor = $Fout
            } elseif ($script:Deels.Count -gt 0) {
                $welke = $script:Deels -join ', '
                $status.Text = (T "Klaar, maar een paar bestanden uit $welke konden niet mee (bijv. open in een programma, groter dan 4 GB, of alleen in OneDrive). Sluit je programma's en klik nog een keer: wat er al staat, gaat sneller." "Done, but a few files from $welke could not be copied (e.g. open in a program, larger than 4 GB, or only in OneDrive). Close your programs and click again: what is already there goes faster.")
                $status.ForeColor = $Grijs
            } else {
                $status.Text = (T 'Klaar! Je bestanden staan in de map BugOS-Switch op de schijf.' 'Done! Your files are in the BugOS-Switch folder on the drive.')
                $status.ForeColor = $Goed
            }
        } catch { Toon $_.Exception.Message 'Error'; $status.Text = '' }
        $knop.Enabled = $true; $verder.Enabled = $true
    })
}

# --- Pagina 3: ruimte maken ------------------------------------------------
$Paginas += {
    $kop.Text = (T 'BugOS naast Windows?' 'BugOS next to Windows?')
    $y = Nieuw-Tekst (T "Wil je Windows houden? Dan maken we Windows een stukje kleiner, zodat BugOS ernaast past. Bij het opstarten kies je dan welke je wilt. Wil je alleen BugOS? Sla deze stap dan over." "Want to keep Windows? Then we make Windows a bit smaller so BugOS fits next to it. When starting the computer you choose which one. Only want BugOS? Skip this step.") 0
    $kan = 0
    try { $kan = Get-KrimpMogelijk } catch {
        [void](Nieuw-Rij 'let_op' (T 'Ik heb even je hulp nodig' 'I need your help') (T 'Ik kon niet uitrekenen hoeveel ruimte er is. Klik met de rechtermuisknop op het programma en kies "Als administrator uitvoeren".' 'I could not work out how much space there is. Right-click the program and choose "Run as administrator".') ($y + 18))
        return
    }
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
    $knop = Nieuw-Knop (T 'Ruimte maken' 'Make space') 0 ($y + 58) 220 'hoofd'
    $knop.Add_Click({
        $getal = $script:W.getal
        if (-not (Vraag (T "Windows wordt $($getal.Value) GB kleiner. Je bestanden blijven gewoon staan.`n`nHeb je een back-up gemaakt (stap 2)? Doorgaan?" "Windows will shrink by $($getal.Value) GB. Your files stay where they are.`n`nDid you make a backup (step 2)? Continue?"))) { return }
        $code = Start-AlsBeheerder @('-Taak', 'Krimp', '-KrimpGB', [string][int]$getal.Value)
        if ($code -eq 0) { Toon (T 'Gelukt! Er is ruimte voor BugOS. Kies straks bij het installeren "De schijf delen met Windows of een ander systeem" (niet "De hele schijf gebruiken": dan gaat Windows weg).' 'Done! There is space for BugOS. When installing, choose "Share disk with other operating systems" (not "Use entire disk": that removes Windows).') }
    })
}

# --- Pagina 4: USB-stick ----------------------------------------------------
$Paginas += {
    $kop.Text = (T 'De BugOS USB-stick maken' 'Make the BugOS USB stick')
    $y = Nieuw-Tekst (T "Druk op 'BugOS downloaden' of kies zelf een .iso-bestand. Kies daarna je USB-stick (minstens 8 GB)." "Press 'Download BugOS' or choose an .iso file yourself. Then choose your USB stick (at least 8 GB).") 0
    $y = Nieuw-Tekst (T 'Let op: alles op die USB-stick wordt gewist!' 'Note: everything on that USB stick will be erased!') ($y + 2) $Fout -Vet
    $download = Nieuw-Knop (T 'BugOS downloaden' 'Download BugOS') 0 ($y + 14) 200 'hoofd'
    $kies = Nieuw-Knop (T 'Kies .iso-bestand...' 'Choose .iso file...') 212 ($y + 14) 200
    $script:W.isoLabel = Nieuw-Label (T 'Nog geen bestand gekozen.' 'No file chosen yet.') ($y + 64) 26 $Grijs
    $script:W.downloadBalk = Nieuw-Balk 0 ($y + 94) ($script:Breedte - 4) $vlak
    $script:W.downloadBalk.Visible = $false
    $download.Add_Click({
        $balk = $script:W.downloadBalk; $label = $script:W.isoLabel
        $soort = Get-IsoSoort
        try {
            $label.Text = (T 'BugOS zoeken...' 'Looking for BugOS...'); [System.Windows.Forms.Application]::DoEvents()
            $gevonden = Get-IsoInfo $soort
        } catch { $gevonden = $null }
        if (-not $gevonden) {
            $label.Text = (T 'Nog geen bestand gekozen.' 'No file chosen yet.')
            Toon (T 'Er staat nog geen BugOS klaar om te downloaden. Probeer het later nog eens.' 'There is no BugOS ready to download yet. Please try again later.')
            return
        }
        $groot = [math]::Round((($gevonden.Info.delen | Measure-Object grootte -Sum).Sum) / 1GB, 1)
        $wat = if ($soort -eq 'nvidia') { T 'de versie voor Nvidia-videokaarten' 'the version for Nvidia graphics cards' } else { T 'de gewone versie' 'the normal version' }
        if (-not (Vraag (T "Ik ga $($gevonden.Versie) downloaden ($wat, $groot GB) naar je map Downloads. Dit kan een tijdje duren. Doorgaan?" "I will download $($gevonden.Versie) ($wat, $groot GB) to your Downloads folder. This can take a while. Continue?"))) { $label.Text = (T 'Nog geen bestand gekozen.' 'No file chosen yet.'); return }
        $balk.Visible = $true; $verder.Enabled = $false
        try {
            $pad = Save-BugOSIso $gevonden (Get-BekendeMap 'Downloads') { param($p, $t) Zet-Balk $balk $p; $label.Text = $t; [System.Windows.Forms.Application]::DoEvents() }
            $script:IsoGekozen = $pad
            $label.Text = $pad
        } catch {
            Toon $_.Exception.Message 'Error'
            $label.Text = (T 'Nog geen bestand gekozen.' 'No file chosen yet.')
        }
        $balk.Visible = $false; $verder.Enabled = $true
    })
    $script:IsoGekozen = ''
    $kies.Add_Click({
        $d = New-Object System.Windows.Forms.OpenFileDialog
        $d.Filter = 'BugOS (*.iso)|*.iso'
        $d.InitialDirectory = Get-BekendeMap 'Downloads'
        if ($d.ShowDialog() -eq 'OK') { $script:IsoGekozen = $d.FileName; $script:W.isoLabel.Text = $d.FileName }
    })
    $y = Nieuw-Tekst (T 'Kies je USB-stick:' 'Choose your USB stick:') ($y + 118) -Vet
    $script:W.stick = Nieuw-Lijst ($y + 4) 520
    $lijst = $script:W.stick
    $script:W.sticks = @(Get-UsbSchijven)
    $sticks = $script:W.sticks
    foreach ($s in $sticks) { [void]$lijst.Items.Add("#$($s.Number)  $($s.FriendlyName)  ($([math]::Round($s.Size / 1GB)) GB)") }
    if ($lijst.Items.Count -gt 0) { $lijst.SelectedIndex = 0 } else { [void]$lijst.Items.Add((T 'Geen USB-stick gevonden. Steek er een in en ga terug en weer verder.' 'No USB stick found. Plug one in, then go back and forward again.')); $lijst.SelectedIndex = 0 }
    $maak = Nieuw-Knop (T 'USB-stick maken' 'Make USB stick') 0 ($y + 52) 220 'hoofd'
    $maak.Add_Click({
        $sticks = $script:W.sticks; $lijst = $script:W.stick
        if (-not $script:IsoGekozen) { Toon (T 'Kies eerst het BugOS .iso-bestand.' 'Choose the BugOS .iso file first.'); return }
        if ($sticks.Count -eq 0) { Toon (T 'Steek eerst een USB-stick in.' 'Plug in a USB stick first.'); return }
        $stick = $sticks[$lijst.SelectedIndex]
        # Staan je bestanden uit stap 2 op deze stick? Dan niet wissen: die ben je anders kwijt (U095).
        if (Test-SwitchBestanden $stick.Number) {
            Toon (T "Op '$($stick.FriendlyName)' staan je bestanden uit stap 2 (de map BugOS-Switch). Die zou je kwijtraken. Gebruik een andere USB-stick voor BugOS, of zet je bestanden eerst ergens anders neer." "'$($stick.FriendlyName)' holds your files from step 2 (the BugOS-Switch folder). You would lose them. Use a different USB stick for BugOS, or put your files somewhere else first.") 'Warning'
            return
        }
        if (-not (Vraag (T "ALLES op '$($stick.FriendlyName)' ($([math]::Round($stick.Size / 1GB)) GB) wordt gewist. Weet je het zeker?" "EVERYTHING on '$($stick.FriendlyName)' ($([math]::Round($stick.Size / 1GB)) GB) will be erased. Are you sure?"))) { return }
        $code = Start-AlsBeheerder @('-Taak', 'Usb', '-IsoPad', "`"$($script:IsoGekozen)`"", '-SchijfNummer', [string]$stick.Number, '-SchijfId', "`"$($stick.UniqueId)`"")
        if ($code -eq 0) {
            Toon (T "De USB-stick is klaar!`n`nZo ga je verder:`n1. Laat de stick erin zitten en start de computer opnieuw op.`n2. Druk tijdens het opstarten op F12, F11, F9 of Esc (verschilt per computer) en kies de USB-stick.`n3. Volg de stappen op het scherm." "The USB stick is ready!`n`nNext:`n1. Leave the stick in and restart the computer.`n2. While starting, press F12, F11, F9 or Esc (differs per computer) and choose the USB stick.`n3. Follow the steps on screen.")
        }
    })
}

function Toon-Pagina {
    $vlak.SuspendLayout()
    $vlak.Controls.Clear()
    $vlak.AutoScrollPosition = New-Object System.Drawing.Point(0, 0)
    $stapLabel.Text = if ($script:Pagina -eq 0) { (T 'WELKOM' 'WELCOME') } else { (T "STAP $($script:Pagina) VAN 4" "STEP $($script:Pagina) OF 4") }
    & $Paginas[$script:Pagina]
    $vlak.ResumeLayout()
    $terug.Enabled = $script:Pagina -gt 0
    $laatste = $script:Pagina -eq $Paginas.Count - 1
    $verder.Text = if ($laatste) { (T 'Sluiten' 'Close') } else { (T 'Volgende' 'Next') }
    # Heeft de pagina zelf een rode knop? Dan is 'Volgende' rustig grijs.
    $verder.Tag.Soort = if ($script:Pagina -ge 2) { 'gewoon' } else { 'hoofd' }
    $terug.Invalidate(); $verder.Invalidate(); $zij.Invalidate()
}

$terug.Add_Click({ if ($script:Pagina -gt 0) { $script:Pagina--; Toon-Pagina } })
$verder.Add_Click({
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
    for ($i = 0; $i -lt $Paginas.Count; $i++) {
        $script:Pagina = $i
        Toon-Pagina
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

Toon-Pagina
[void]$form.ShowDialog()
