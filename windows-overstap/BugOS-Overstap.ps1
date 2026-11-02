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

    Starten: dubbelklik op "Start BugOS Overstap.bat".

    Licentie: GPL-3.0-or-later. Onderdeel van BugOS.
#>

param(
    # Alleen intern gebruikt: dezelfde stap opnieuw starten als beheerder.
    [ValidateSet('', 'Krimp', 'Usb')] [string] $Taak = '',
    [int] $KrimpGB = 0,
    [string] $IsoPad = '',
    [int] $SchijfNummer = -1
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

# ------------------------------------------------------------------ taal --
$script:NL = (Get-Culture).TwoLetterISOLanguageName -eq 'nl'
function T([string] $nl, [string] $en) { if ($script:NL) { $nl } else { $en } }

$Rood = [System.Drawing.Color]::FromArgb(217, 58, 58)
$Inkt = [System.Drawing.Color]::FromArgb(31, 35, 40)
$Grijs = [System.Drawing.Color]::FromArgb(94, 102, 112)

function Test-Beheerder {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    (New-Object Security.Principal.WindowsPrincipal $id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Start-AlsBeheerder([string[]] $Argumenten) {
    $pad = $PSCommandPath
    $alles = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$pad`"") + $Argumenten
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
    if ($gpu -match 'NVIDIA') {
        Voeg (T 'Videokaart' 'Graphics') $true (T "Nvidia gevonden ($gpu). Kies de versie 'bugos-nvidia'." "Nvidia found ($gpu). Choose the 'bugos-nvidia' version.") $true
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
    $doel = Join-Path $doelSchijf 'BugOS-Overstap'
    New-Item -ItemType Directory -Force -Path $doel | Out-Null
    $stap = 0
    $aantal = $script:Mappen.Count + 2
    foreach ($m in $script:Mappen) {
        $stap++
        $bron = Get-BekendeMap $m.Sleutel
        & $Voortgang ([int](100 * $stap / $aantal)) (T "Kopiëren: $($m.Naam)..." "Copying: $($m.Naam)...")
        if ($bron -and (Test-Path $bron)) {
            # /E alle submappen, /R:1 /W:1 niet eindeloos wachten, /XJ geen snelkoppel-lussen.
            $null = robocopy $bron (Join-Path $doel $m.Naam) /E /R:1 /W:1 /XJ /NFL /NDL /NJH /NJS /NP
            if ($LASTEXITCODE -ge 8) { throw (T "Kopiëren van $($m.Naam) lukte niet." "Copying $($m.Naam) failed.") }
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
    }
    $info | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $doel 'bugos-overstap.json') -Encoding UTF8
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

function Get-UsbSchijven {
    Get-Disk | Where-Object { $_.BusType -eq 'USB' -and $_.Size -gt 4GB -and -not $_.IsBoot -and -not $_.IsSystem }
}

function Write-IsoNaarSchijf([string] $iso, [int] $nummer, [scriptblock] $Voortgang) {
    $schijf = Get-Disk -Number $nummer
    if ($schijf.BusType -ne 'USB' -or $schijf.IsBoot -or $schijf.IsSystem) {
        throw (T 'Veiligheidsstop: dit is geen USB-stick.' 'Safety stop: this is not a USB stick.')
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

# ==================================================== beheerder-taken =====
# Het programma start zichzelf opnieuw als beheerder voor stap 3 en 4.

if ($Taak -eq 'Krimp') {
    try { Invoke-Krimp $KrimpGB; exit 0 } catch { Toon ((T 'Ruimte maken lukte niet: ' 'Making space failed: ') + $_.Exception.Message) 'Error'; exit 1 }
}
if ($Taak -eq 'Usb') {
    $form = New-Object System.Windows.Forms.Form
    $form.Text = 'BugOS Overstap'; $form.Width = 520; $form.Height = 180; $form.StartPosition = 'CenterScreen'
    $lbl = New-Object System.Windows.Forms.Label; $lbl.SetBounds(20, 20, 470, 30); $form.Controls.Add($lbl)
    $bar = New-Object System.Windows.Forms.ProgressBar; $bar.SetBounds(20, 60, 470, 28); $form.Controls.Add($bar)
    $form.Show(); [System.Windows.Forms.Application]::DoEvents()
    try {
        Write-IsoNaarSchijf $IsoPad $SchijfNummer { param($p, $t) $bar.Value = [math]::Min(100, $p); $lbl.Text = $t; [System.Windows.Forms.Application]::DoEvents() }
        $form.Close(); exit 0
    } catch {
        $form.Close(); Toon ((T 'De USB-stick maken lukte niet: ' 'Making the USB stick failed: ') + $_.Exception.Message) 'Error'; exit 1
    }
}

# ================================================================ VENSTER ==

$form = New-Object System.Windows.Forms.Form
$form.Text = 'BugOS Overstap'
$form.ClientSize = New-Object System.Drawing.Size(760, 560)
$form.StartPosition = 'CenterScreen'
$form.FormBorderStyle = 'FixedSingle'
$form.MaximizeBox = $false
$form.BackColor = [System.Drawing.Color]::White
$form.Font = New-Object System.Drawing.Font('Segoe UI', 11)

$kop = New-Object System.Windows.Forms.Label
$kop.SetBounds(32, 24, 700, 44)
$kop.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 20)
$kop.ForeColor = $Inkt
$form.Controls.Add($kop)

$stapLabel = New-Object System.Windows.Forms.Label
$stapLabel.SetBounds(32, 70, 700, 24)
$stapLabel.ForeColor = $Rood
$stapLabel.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 10)
$form.Controls.Add($stapLabel)

$vlak = New-Object System.Windows.Forms.Panel
$vlak.SetBounds(32, 100, 696, 380)
$form.Controls.Add($vlak)

$terug = New-Object System.Windows.Forms.Button
$terug.SetBounds(32, 500, 140, 40); $terug.Text = (T 'Terug' 'Back')
$form.Controls.Add($terug)

$verder = New-Object System.Windows.Forms.Button
$verder.SetBounds(588, 500, 140, 40); $verder.Text = (T 'Volgende' 'Next')
$verder.BackColor = $Rood; $verder.ForeColor = [System.Drawing.Color]::White; $verder.FlatStyle = 'Flat'
$verder.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 11)
$form.Controls.Add($verder)
$form.AcceptButton = $verder

function Nieuw-Label([string] $tekst, [int] $y, [int] $h = 28, $kleur = $null) {
    $l = New-Object System.Windows.Forms.Label
    $l.SetBounds(0, $y, 690, $h); $l.Text = $tekst
    if ($kleur) { $l.ForeColor = $kleur }
    $vlak.Controls.Add($l); return $l
}

function Nieuw-Knop([string] $tekst, [int] $x, [int] $y, [int] $b = 240) {
    $k = New-Object System.Windows.Forms.Button
    $k.SetBounds($x, $y, $b, 40); $k.Text = $tekst
    $vlak.Controls.Add($k); return $k
}

$script:Pagina = 0
$script:W = @{}   # knoppen en vakjes die een klik later nog nodig heeft
$Paginas = @()

# --- Pagina 0: welkom -------------------------------------------------------
$Paginas += {
    $kop.Text = (T 'Welkom bij de BugOS Overstap' 'Welcome to BugOS Overstap')
    Nieuw-Label (T "Dit programma helpt je om over te stappen van Windows naar BugOS. In vier stappen:`n`n  1.  Kijken of je computer BugOS aankan`n  2.  Je bestanden meenemen naar een USB-schijf`n  3.  Ruimte maken om BugOS naast Windows te zetten (mag je overslaan)`n  4.  De BugOS-installatie op een USB-stick zetten`n`nEr gebeurt niks zonder dat jij op een knop drukt." "This program helps you move from Windows to BugOS. In four steps:`n`n  1.  Check whether your computer can run BugOS`n  2.  Take your files to a USB drive`n  3.  Make space to put BugOS next to Windows (optional)`n  4.  Put the BugOS installer on a USB stick`n`nNothing happens until you press a button.") 0 260 | Out-Null
}

# --- Pagina 1: controle -----------------------------------------------------
$Paginas += {
    $kop.Text = (T 'Kan mijn computer BugOS aan?' 'Can my computer run BugOS?')
    $y = 0
    foreach ($r in (Get-Controle)) {
        $teken = if (-not $r.Ok) { '✖' } elseif ($r.Waarschuwing) { '!' } else { '✔' }
        $kleur = if (-not $r.Ok) { $Rood } elseif ($r.Waarschuwing) { [System.Drawing.Color]::DarkGoldenrod } else { [System.Drawing.Color]::ForestGreen }
        $l = Nieuw-Label "$teken  $($r.Naam)" $y 24 $kleur
        $l.Font = New-Object System.Drawing.Font('Segoe UI Semibold', 11)
        Nieuw-Label $r.Tekst ($y + 24) 40 $Grijs | Out-Null
        $y += 66
    }
}

# --- Pagina 2: meenemen -----------------------------------------------------
$Paginas += {
    $kop.Text = (T 'Je bestanden meenemen' 'Take your files with you')
    $groot = [math]::Round((Get-MeeneemGrootte) / 1GB, 1)
    Nieuw-Label (T "Je documenten, foto's, muziek, video's, bureaublad, downloads, bladwijzers en achtergrond ($groot GB) gaan naar een USB-schijf. In BugOS zet je ze terug met één klik.`nDit is ook meteen een back-up!" "Your documents, photos, music, videos, desktop, downloads, bookmarks and wallpaper ($groot GB) go to a USB drive. In BugOS you put them back with one click.`nThis is also a backup!") 0 90 | Out-Null
    Nieuw-Label (T 'Kies de USB-schijf:' 'Choose the USB drive:') 100 | Out-Null
    $script:W.schijf = New-Object System.Windows.Forms.ComboBox
    $lijst = $script:W.schijf
    $lijst.DropDownStyle = 'DropDownList'; $lijst.SetBounds(0, 130, 440, 32)
    $vlak.Controls.Add($lijst)
    Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DriveType -in 2, 3 -and $_.DeviceID -ne 'C:' } | ForEach-Object {
        [void]$lijst.Items.Add("$($_.DeviceID)  $($_.VolumeName)  ($([math]::Round($_.FreeSpace / 1GB)) GB $(T 'vrij' 'free'))")
    }
    if ($lijst.Items.Count -gt 0) { $lijst.SelectedIndex = 0 }
    $script:W.balk = New-Object System.Windows.Forms.ProgressBar; $script:W.balk.SetBounds(0, 230, 690, 26); $vlak.Controls.Add($script:W.balk)
    $script:W.status = Nieuw-Label '' 262 50 $Grijs
    $script:W.knop = Nieuw-Knop (T 'Bestanden kopiëren' 'Copy files') 0 175
    $script:W.knop.Add_Click({
        $lijst = $script:W.schijf; $balk = $script:W.balk; $status = $script:W.status; $knop = $script:W.knop
        if ($lijst.SelectedIndex -lt 0) { Toon (T 'Steek eerst een USB-schijf in en ga even terug en weer verder.' 'Plug in a USB drive first, then go back and forward again.'); return }
        $letter = ($lijst.SelectedItem -split '\s+')[0] + '\'
        $vrij = (Get-PSDrive $letter.Substring(0, 1)).Free
        if ($vrij -lt (Get-MeeneemGrootte)) { Toon (T 'Er is niet genoeg ruimte op die schijf.' 'Not enough space on that drive.') 'Warning'; return }
        $knop.Enabled = $false; $verder.Enabled = $false
        try {
            Invoke-Meenemen $letter { param($p, $t) $balk.Value = [math]::Min(100, $p); $status.Text = $t; [System.Windows.Forms.Application]::DoEvents() }
            $status.Text = (T 'Klaar! Je bestanden staan in de map BugOS-Overstap op de schijf.' 'Done! Your files are in the BugOS-Overstap folder on the drive.')
        } catch { Toon $_.Exception.Message 'Error'; $status.Text = '' }
        $knop.Enabled = $true; $verder.Enabled = $true
    })
}

# --- Pagina 3: ruimte maken ------------------------------------------------
$Paginas += {
    $kop.Text = (T 'BugOS naast Windows?' 'BugOS next to Windows?')
    Nieuw-Label (T "Wil je Windows houden? Dan maken we Windows een stukje kleiner, zodat BugOS ernaast past. Bij het opstarten kies je dan welke je wilt.`n`nWil je alleen BugOS? Sla deze stap dan over." "Want to keep Windows? Then we make Windows a bit smaller so BugOS fits next to it. When starting the computer you choose which one.`n`nOnly want BugOS? Skip this step.") 0 110 | Out-Null
    $kan = 0
    try { $kan = Get-KrimpMogelijk } catch {
        Nieuw-Label (T 'Ik kon niet uitrekenen hoeveel ruimte er is. Klik met de rechtermuisknop op het programma en kies "Als administrator uitvoeren".' 'I could not work out how much space there is. Right-click the program and choose "Run as administrator".') 120 60 $Rood | Out-Null
        return
    }
    if ($kan -lt 40) {
        Nieuw-Label (T "Er kan maar $kan GB vrijgemaakt worden. BugOS heeft minstens 40 GB nodig. Ruim eerst wat op, of laat BugOS Windows vervangen." "Only $kan GB can be freed. BugOS needs at least 40 GB. Clean up first, or let BugOS replace Windows.") 120 60 $Rood | Out-Null
        return
    }
    Nieuw-Label (T "Hoeveel ruimte krijgt BugOS? (40 tot $kan GB)" "How much space does BugOS get? (40 to $kan GB)") 120 | Out-Null
    $script:W.getal = New-Object System.Windows.Forms.NumericUpDown
    $getal = $script:W.getal
    $getal.SetBounds(0, 150, 120, 32); $getal.Minimum = 40; $getal.Maximum = $kan; $getal.Value = [math]::Min(100, $kan)
    $vlak.Controls.Add($getal)
    Nieuw-Label 'GB' 154 | ForEach-Object { $_.Left = 130; $_.Width = 60 }
    $knop = Nieuw-Knop (T 'Ruimte maken' 'Make space') 0 200
    $knop.Add_Click({
        $getal = $script:W.getal
        if (-not (Vraag (T "Windows wordt $($getal.Value) GB kleiner. Je bestanden blijven gewoon staan.`n`nHeb je een back-up gemaakt (stap 2)? Doorgaan?" "Windows will shrink by $($getal.Value) GB. Your files stay where they are.`n`nDid you make a backup (step 2)? Continue?"))) { return }
        $code = Start-AlsBeheerder @('-Taak', 'Krimp', '-KrimpGB', [string][int]$getal.Value)
        if ($code -eq 0) { Toon (T 'Gelukt! Er is ruimte voor BugOS. Kies straks bij het installeren "Automatisch".' 'Done! There is space for BugOS. When installing, choose "Automatic".') }
    })
}

# --- Pagina 4: USB-stick ----------------------------------------------------
$Paginas += {
    $kop.Text = (T 'De BugOS USB-stick maken' 'Make the BugOS USB stick')
    Nieuw-Label (T "1. Download het BugOS-bestand (.iso). 2. Kies het hieronder. 3. Kies je USB-stick (minstens 8 GB).`nLet op: alles op die USB-stick wordt gewist!" "1. Download the BugOS file (.iso). 2. Choose it below. 3. Choose your USB stick (at least 8 GB).`nNote: everything on that USB stick will be erased!") 0 56 | Out-Null
    $download = Nieuw-Knop (T 'BugOS downloaden' 'Download BugOS') 0 64
    $download.Add_Click({ Start-Process 'https://github.com/253UgurSahin/BugOS/blob/main/docs/TESTEN.md' })
    $script:W.isoLabel = Nieuw-Label (T 'Nog geen bestand gekozen.' 'No file chosen yet.') 120 24 $Grijs
    $kies = Nieuw-Knop (T 'Kies .iso-bestand...' 'Choose .iso file...') 0 148
    $script:IsoGekozen = ''
    $kies.Add_Click({
        $d = New-Object System.Windows.Forms.OpenFileDialog
        $d.Filter = 'BugOS (*.iso)|*.iso'
        $d.InitialDirectory = Get-BekendeMap 'Downloads'
        if ($d.ShowDialog() -eq 'OK') { $script:IsoGekozen = $d.FileName; $script:W.isoLabel.Text = $d.FileName }
    })
    Nieuw-Label (T 'USB-stick:' 'USB stick:') 204 | Out-Null
    $script:W.stick = New-Object System.Windows.Forms.ComboBox
    $lijst = $script:W.stick
    $lijst.DropDownStyle = 'DropDownList'; $lijst.SetBounds(0, 232, 520, 32)
    $vlak.Controls.Add($lijst)
    $script:W.sticks = @(Get-UsbSchijven)
    $sticks = $script:W.sticks
    foreach ($s in $sticks) { [void]$lijst.Items.Add("#$($s.Number)  $($s.FriendlyName)  ($([math]::Round($s.Size / 1GB)) GB)") }
    if ($lijst.Items.Count -gt 0) { $lijst.SelectedIndex = 0 } else { [void]$lijst.Items.Add((T 'Geen USB-stick gevonden. Steek er een in en ga terug en weer verder.' 'No USB stick found. Plug one in, then go back and forward again.')); $lijst.SelectedIndex = 0 }
    $maak = Nieuw-Knop (T 'USB-stick maken' 'Make USB stick') 0 290
    $maak.Add_Click({
        $sticks = $script:W.sticks; $lijst = $script:W.stick
        if (-not $script:IsoGekozen) { Toon (T 'Kies eerst het BugOS .iso-bestand.' 'Choose the BugOS .iso file first.'); return }
        if ($sticks.Count -eq 0) { Toon (T 'Steek eerst een USB-stick in.' 'Plug in a USB stick first.'); return }
        $stick = $sticks[$lijst.SelectedIndex]
        if (-not (Vraag (T "ALLES op '$($stick.FriendlyName)' ($([math]::Round($stick.Size / 1GB)) GB) wordt gewist. Weet je het zeker?" "EVERYTHING on '$($stick.FriendlyName)' ($([math]::Round($stick.Size / 1GB)) GB) will be erased. Are you sure?"))) { return }
        $code = Start-AlsBeheerder @('-Taak', 'Usb', '-IsoPad', "`"$($script:IsoGekozen)`"", '-SchijfNummer', [string]$stick.Number)
        if ($code -eq 0) {
            Toon (T "De USB-stick is klaar! 🎉`n`nZo ga je verder:`n1. Laat de stick erin zitten en start de computer opnieuw op.`n2. Druk tijdens het opstarten op F12, F11, F9 of Esc (verschilt per computer) en kies de USB-stick.`n3. Volg de stappen op het scherm." "The USB stick is ready! 🎉`n`nNext:`n1. Leave the stick in and restart the computer.`n2. While starting, press F12, F11, F9 or Esc (differs per computer) and choose the USB stick.`n3. Follow the steps on screen.")
        }
    })
}

function Toon-Pagina {
    $vlak.Controls.Clear()
    $stapLabel.Text = if ($script:Pagina -eq 0) { '' } else { (T "Stap $($script:Pagina) van 4" "Step $($script:Pagina) of 4") }
    & $Paginas[$script:Pagina]
    $terug.Enabled = $script:Pagina -gt 0
    $verder.Text = if ($script:Pagina -eq $Paginas.Count - 1) { (T 'Sluiten' 'Close') } else { (T 'Volgende' 'Next') }
}

$terug.Add_Click({ if ($script:Pagina -gt 0) { $script:Pagina--; Toon-Pagina } })
$verder.Add_Click({
    if ($script:Pagina -ge $Paginas.Count - 1) { $form.Close() } else { $script:Pagina++; Toon-Pagina }
})

Toon-Pagina
[void]$form.ShowDialog()
