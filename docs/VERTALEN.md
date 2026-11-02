# 🌍 BugOS vertalen

BugOS moet in **elke taal** werken. KDE (de motor) is al in meer dan 50 talen vertaald.
Onze eigen BugOS-schermen staan in het Nederlands en Engels. Voor alle andere talen hebben we jouw hulp nodig.

## Hoe werkt het?

In de code staat elke tekst twee keer: `t("Nederlands", "English")`.
Voor andere talen kijkt BugOS in een woordenboekje: `system_files/usr/share/bugos/vertalingen/<taal>.json`.

Zo'n woordenboekje ziet er zo uit:

```json
{
  "Settings": "Einstellungen",
  "Something is not working": "Etwas funktioniert nicht"
}
```

Links staat de Engelse tekst, rechts de vertaling. Ontbreekt een vertaling, dan laat BugOS de Engelse tekst zien.

## Zelf een taal toevoegen

1. Maak een kopie van `sjabloon.json` en noem hem naar je taal. Gebruik de code van twee letters: `de.json` (Duits), `tr.json` (Turks), `fr.json` (Frans), enzovoort.
2. Vul rechts de vertalingen in.
3. Stuur hem in via GitHub (een Pull Request), of mail hem naar de makers.

Tekst die tussen `{` en `}` staat, of een `\n` (nieuwe regel), laat je precies zo staan.

## Voor de makers: het sjabloon bijwerken

Na het toevoegen van nieuwe teksten draai je:

```bash
python3 tools/vertalingen-verzamelen.py
```

Om een bestaande taal bij te werken (vertalingen blijven bewaard):

```bash
python3 tools/vertalingen-verzamelen.py de
```

Let op: teksten met een getal erin (zoals "Nog 12 GB vrij") worden nog niet vertaald. Die blijven voorlopig Engels.
