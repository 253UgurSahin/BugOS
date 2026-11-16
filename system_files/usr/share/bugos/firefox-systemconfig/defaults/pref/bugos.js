// BugOS: de instellingen van BugOS voor Firefox (de Flatpak van Flathub, org.mozilla.firefox).
//
// Hoe Firefox dit bestand vindt: de Flatpak-versie ziet /etc van de computer niet (geen /etc/firefox), maar leest
// wel de uitbreiding 'org.mozilla.firefox.systemconfig', die in de doos op /app/etc/firefox komt. Daarin leest hij
// policies/policies.json en de standaardinstellingen in defaults/pref/*.js. Op de computer staat die uitbreiding in
// /var/lib/flatpak/extension/org.mozilla.firefox.systemconfig/x86_64/stable; BugOS zet daar een verwijzing naar
// deze map neer (/usr/lib/tmpfiles.d/bugos-firefox.conf). Bronnen (nagekeken 2026-11-16):
//   https://firefox-admin-docs.mozilla.org/guides/policies-configuration/  (de uitbreiding en het pad op de computer)
//   https://bugzilla.mozilla.org/show_bug.cgi?id=1814897  (defaults/pref in die uitbreiding, sinds Firefox 115)
//   https://bugzilla.mozilla.org/show_bug.cgi?id=1795998  (een verwijzing vanaf dat pad is de bedoelde manier)
//
// pref() zet een STANDAARD: wie in Firefox zelf iets anders kiest, houdt zijn eigen keuze.
// Bewust geen policies.json: de Flatpak heeft zelf al een policies.json (die het bijwerken door Firefox zelf uitzet,
// want Flathub werkt hem bij), en een tweede zou die kunnen vervangen.

// Firefox krijgt dezelfde vensterbalk als alle andere vensters (geen eigen knoppen in de tabbalk), zodat het één
// geheel blijft met BugOS. Zo stond het ook bij de Firefox die vroeger in BugOS zelf zat (distribution.ini).
pref("browser.tabs.inTitlebar", 0);
// Beginnen op de gewone startpagina van Firefox (niet op een pagina van een andere distributie).
pref("browser.startup.homepage", "about:home");
