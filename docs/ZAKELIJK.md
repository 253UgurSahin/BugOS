# BugOS voor bedrijven (idee, geparkeerd)

> Status: **geparkeerd** (2026-11-24). Alleen opgeschreven, er is nog niets gebouwd.

Een versie van BugOS voor bedrijven die laptops uitgeven aan honderden mensen, met een uitgebreid beheerscherm.

## Eerst: de licentie

BugOS valt onder PolyForm Noncommercial 1.0.0. Daaronder mag een bedrijf BugOS niet voor zijn werk gebruiken. Een
bedrijfsversie kan dus alleen met een aparte, commerciële licentie (dual licensing: gratis voor thuis, betaald voor
bedrijven). Dat is een keuze van de eigenaar (eventueel met een jurist), los van de code.

## Waarom BugOS hier goed bij past

BugOS is één vast image (bootc / rpm-ostree). Elke laptop draait precies dezelfde versie, een update gaat in één keer en
terugdraaien kan altijd. Voor een vloot laptops is dat precies wat je wilt.

## Onderdelen

| Onderdeel | Wat het doet |
|---|---|
| Eigen variant `bugos-zakelijk` | Naast `main` en `nvidia` in `build.yml`, met een vergrendelde basis. |
| Uitrollen in ringen | Eerst de IT-testgroep, dan pilot, dan iedereen (per ring een eigen image-tag). Terugdraaien voor een hele groep. |
| Inschrijven | USB-stick of netwerkboot (kickstart) met een bedrijfscode; na het installeren meldt de laptop zich vanzelf aan. |
| Beleid | Toegestane apps (Flatpak-lijst), instellingen vastzetten (KDE Kiosk, polkit), USB-sticks (USBGuard), verplichte schijfversleuteling (LUKS + TPM), wifi/VPN-profielen, printers, firewall. |
| Inloggen met bedrijfsaccount | Active Directory / Entra ID (SSSD, realmd) of FreeIPA. |
| Beheerscherm (web) | Alle laptops: versie, updates, schijf, versleuteling, laatst gezien. Groepen, beleid per groep, op afstand vergrendelen of wissen, rapportages. |
| Agent op de laptop | Haalt ondertekend beleid op en rapporteert terug. |

## Beheerscherm: twee wegen

1. **Zelf bouwen**: helemaal in BugOS-stijl, maar veel werk.
2. **Op bestaande open-source bouwen** (aanbevolen om mee te beginnen): FleetDM (osquery) voor het overzicht van
   apparaten, Ansible voor beleid, met een BugOS-schil eromheen.

## Open vragen voor later

- Welk licentiemodel (prijs per laptop, per jaar)?
- Welke accounts gebruiken de bedrijven: Microsoft (Entra/AD), Google Workspace of iets anders?
- Zelf hosten of een dienst van BugOS?
