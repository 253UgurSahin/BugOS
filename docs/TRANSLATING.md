# 🌍 Translating BugOS

BugOS should work in **every language**. KDE (the engine) is already translated into more than 50 languages.
Our own BugOS screens are in English and Dutch. For all other languages we need your help.

## How does it work?

In the code, every text is written twice, in Dutch and in English: `t("Nederlands", "English")`.
English is the default. For other languages BugOS looks in a little dictionary: `system_files/usr/share/bugos/translations/<taal>.json`.

This is what such a little dictionary looks like:

```json
{
  "Settings": "Einstellungen",
  "Something is not working": "Etwas funktioniert nicht"
}
```

On the left is the English text, on the right the translation. If a translation is missing, BugOS shows the English text.

## Add a language yourself

1. Make a copy of `template.json` and name it after your language. Use the two-letter code: `de.json` (German), `tr.json` (Turkish), `fr.json` (French), and so on.
2. Fill in the translations on the right.
3. Send it in through GitHub (a Pull Request), or email it to the makers.

Text between `{` and `}`, or a `\n` (new line), you leave exactly as it is.

## For the makers: updating the template

After adding new texts, run:

```bash
python3 tools/collect-translations.py
```

To update an existing language (translations that are already there are kept):

```bash
python3 tools/collect-translations.py de
```

The script writes to `system_files/usr/share/bugos/translations/`, the same folder the apps read from.
Run it again after merging new screens, so `template.json` has every text.

### What cannot be translated yet

Texts with a changing part in them are written as an f-string, like `t(f"{n} GB vrij", f"{n} GB free")`.
The English text is different every time, so it cannot be looked up in a dictionary: these texts stay in
English for now. The script skips them and tells you how many there are (about 115 at the moment).

To make such a text translatable, write it with a placeholder and fill it in afterwards:
`t("{n} GB vrij", "{n} GB free").format(n=n)`. Then `"{n} GB free"` lands in `template.json`, and the
translator keeps `{n}` exactly as it is.

The start menu, the quick menu and the taskbar (QML), the start-menu helper `bugos-start-data` and the
names of the BugOS programs in their `.desktop` files do not read these dictionaries yet: they only know
Dutch and English. With a `de.json`, the BugOS apps become German, but those parts stay English for now
(U276). `collect-translations.py` does not collect their texts either.
