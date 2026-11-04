# 🌍 Translating BugOS

BugOS should work in **every language**. KDE (the engine) is already translated into more than 50 languages.
Our own BugOS screens are in English and Dutch. For all other languages we need your help.

## How does it work?

In the code, every text is written twice, in Dutch and in English: `t("Nederlands", "English")`.
English is the default. For other languages BugOS looks in a little dictionary: `system_files/usr/share/bugos/vertalingen/<taal>.json`.

This is what such a little dictionary looks like:

```json
{
  "Settings": "Einstellungen",
  "Something is not working": "Etwas funktioniert nicht"
}
```

On the left is the English text, on the right the translation. If a translation is missing, BugOS shows the English text.

## Add a language yourself

1. Make a copy of `sjabloon.json` and name it after your language. Use the two-letter code: `de.json` (German), `tr.json` (Turkish), `fr.json` (French), and so on.
2. Fill in the translations on the right.
3. Send it in through GitHub (a Pull Request), or email it to the makers.

Text between `{` and `}`, or a `\n` (new line), you leave exactly as it is.

## For the makers: updating the template

After adding new texts, run:

```bash
python3 tools/vertalingen-verzamelen.py
```

To update an existing language (translations that are already there are kept):

```bash
python3 tools/vertalingen-verzamelen.py de
```

Note: texts with a number in them (like "12 GB free") are not translated yet. For now they stay in English.
