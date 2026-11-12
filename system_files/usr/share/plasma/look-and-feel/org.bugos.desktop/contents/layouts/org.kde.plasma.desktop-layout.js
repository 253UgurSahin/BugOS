// BugOS bureaublad-indeling
// Taakbalk onderaan, startknop links, klok en pictogrammen rechts.
// Net als je gewend bent - maar dan in BugOS-stijl.

var panel = new Panel;
panel.location = "bottom";
// Zoals Windows 11: een strakke balk over de hele breedte (niet zwevend), ~48 px hoog.
panel.height = 2 * Math.floor(gridUnit * 2.7 / 2);
panel.hiding = "none";
panel.floating = false;

// Startknop: het BugOS-startmenu (het lieveheersbeestje). Alt+F1 opent het ook;
// de Windows-toets werkt via Plasma zelf (het menu meldt zich als startmenu).
var start = panel.addWidget("org.bugos.startmenu");
start.currentConfigGroup = ["Shortcuts"];
start.writeConfig("global", "Alt+F1");

// Vastgezette programma's en open vensters.
var taken = panel.addWidget("org.kde.plasma.icontasks");
taken.currentConfigGroup = ["General"];
taken.writeConfig("launchers", [
    "applications:bugos-files.desktop",
    "applications:org.mozilla.firefox.desktop",
    "applications:bugos-store.desktop",
    "applications:bugos-settings.desktop"
]);
// De takenlijst rekt niet uit: de lege ruimte erachter is van de taakbalkruimte
// hieronder. Zo kom je met de rechtermuisknop op een leeg stuk taakbalk bij
// "Taakbeheer", net als in Windows (het menu van de takenlijst zelf kunnen we niet uitbreiden).
taken.writeConfig("fill", false);

// Lege ruimte tussen de apps en het systeemvak, met Taakbeheer in het rechtermuismenu.
// Vervangt de oude scheidingsruimte (marginsseparator): die vulde ook de ruimte, maar zonder menu.
panel.addWidget("org.bugos.taskbar");
// Snelmenu: grote knoppen voor wifi, bluetooth, geluid, donker en niet storen.
panel.addWidget("org.bugos.quickmenu");
var vakje = panel.addWidget("org.kde.plasma.systemtray");
// Het snelmenu doet geluid, wifi, bluetooth, helderheid en batterij al. De KDE-
// pictogrammen daarvoor (en een paar die je bijna nooit nodig hebt) verbergen we;
// ze blijven op de achtergrond werken (volumetoetsen, melding bij lege batterij).
// Dezelfde lijst staat in bugos-panel (RUSTIG, voor wie al een taakbalk had). De toetsenbordindeling staat er niet
// in: met twee of meer indelingen zie je hem naast de klok, zoals in Windows 11.
// Plasma 6: de lijst hoort bij het systeemvak zelf ([General] hiddenItems).
vakje.currentConfigGroup = ["General"];
vakje.writeConfig("hiddenItems", ["org.kde.plasma.volume", "org.kde.plasma.networkmanagement",
    "org.kde.plasma.bluetooth", "org.kde.plasma.battery", "org.kde.plasma.brightness", "org.kde.kscreen",
    "org.kde.plasma.clipboard", "org.kde.plasma.keyboardindicator",
    "org.kde.plasma.manage-inputmethod", "org.kde.plasma.printmanager", "org.kde.kdeconnect",
    "org.kde.plasma.weather"]);
// De KDE-onderdelen die het snelmenu vervangt staan uit (niet alleen verborgen): hun tandwiel opende KDE. Dezelfde
// lijst staat in bugos-panel (UIT); dat onthoudt ze in bugosOff, zodat ze terugkomen als je het snelmenu uitzet.
// Heeft Plasma de lijst (extraItems) hier nog niet ingevuld, dan doet bugos-panel het bij het eerste inloggen.
var UIT = ["org.kde.plasma.volume", "org.kde.plasma.networkmanagement", "org.kde.plasma.bluetooth",
    "org.kde.plasma.battery", "org.kde.plasma.brightness", "org.kde.plasma.manage-inputmethod",
    "org.kde.kdeconnect", "org.kde.plasma.weather", "org.kde.plasma.vault", "org.kde.kscreen"];
var extra = vakje.readConfig("extraItems", []);
if (typeof extra == "string") extra = extra === "" ? [] : extra.split(",");
if (extra.length > 0) {
    var aan = [], uit = [];
    for (var e = 0; e < extra.length; e++) {
        if (extra[e] === "") continue;
        if (UIT.indexOf(extra[e]) >= 0) uit.push(extra[e]);
        else aan.push(extra[e]);
    }
    vakje.writeConfig("extraItems", aan);
    vakje.writeConfig("bugosOff", uit.length ? uit : [""]);
    vakje.reloadConfig();
}
// De BugOS-klok: klein, tijd en datum onder elkaar en even groot, zoals Windows 11 (de klok van KDE tekent
// de datum kleiner en maakt alles zo groot als de taakbalk).
panel.addWidget("org.bugos.clock");
// Geen groot 'bureaublad tonen'-icoon rechts (Windows 11 heeft daar niets zichtbaars); Windows+D werkt gewoon.

// Achtergrond van het bureaublad.
var bureaubladen = desktopsForActivity(currentActivity());
for (var i = 0; i < bureaubladen.length; i++) {
    var d = bureaubladen[i];
    d.wallpaperPlugin = "org.kde.image";
    d.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    d.writeConfig("Image", "file:///usr/share/wallpapers/bugos/");
}

// Op slot: geen KDE-bewerkmodus per ongeluk en geen KDE-regels in de rechtermuismenu's.
// bugos-panel haalt het slot er even af als het iets verandert (Instellingen > Uiterlijk > Taakbalk), en zet het
// bij elk inloggen opnieuw. Als laatste: een indeling op slot weigert addWidget.
if (typeof __AppInterface != "undefined") __AppInterface.locked = true;
