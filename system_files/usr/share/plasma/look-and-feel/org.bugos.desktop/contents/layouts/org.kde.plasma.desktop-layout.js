// BugOS bureaublad-indeling
// Taakbalk onderaan, startknop links, klok en pictogrammen rechts.
// Net als je gewend bent - maar dan in BugOS-stijl.

var panel = new Panel;
panel.location = "bottom";
panel.height = 2 * Math.floor(gridUnit * 2.6 / 2);
panel.hiding = "none";
panel.floating = true;

// Startknop: het BugOS-startmenu (het lieveheersbeestje). Alt+F1 opent het ook;
// de Windows-toets werkt via Plasma zelf (het menu meldt zich als startmenu).
var start = panel.addWidget("org.bugos.startmenu");
start.currentConfigGroup = ["Shortcuts"];
start.writeConfig("global", "Alt+F1");

// Vastgezette programma's en open vensters.
var taken = panel.addWidget("org.kde.plasma.icontasks");
taken.currentConfigGroup = ["General"];
taken.writeConfig("launchers", [
    "applications:bugos-bestanden.desktop",
    "applications:org.mozilla.firefox.desktop",
    "applications:bugos-winkel.desktop",
    "applications:bugos-instellingen.desktop"
]);

panel.addWidget("org.kde.plasma.marginsseparator");
// Snelmenu: grote knoppen voor wifi, bluetooth, geluid, donker en niet storen.
panel.addWidget("org.bugos.snelmenu");
var vakje = panel.addWidget("org.kde.plasma.systemtray");
// Het snelmenu doet geluid, wifi, bluetooth, helderheid en batterij al. De KDE-
// pictogrammen daarvoor (en een paar die je bijna nooit nodig hebt) verbergen we;
// ze blijven op de achtergrond werken (volumetoetsen, melding bij lege batterij).
// Dezelfde lijst staat in bugos-paneel (voor wie al een taakbalk had).
// Plasma 6: de lijst hoort bij het systeemvak zelf ([General] hiddenItems).
vakje.currentConfigGroup = ["General"];
vakje.writeConfig("hiddenItems", ["org.kde.plasma.volume", "org.kde.plasma.networkmanagement",
    "org.kde.plasma.bluetooth", "org.kde.plasma.battery", "org.kde.plasma.brightness", "org.kde.kscreen",
    "org.kde.plasma.clipboard", "org.kde.plasma.keyboardlayout", "org.kde.plasma.keyboardindicator",
    "org.kde.plasma.manage-inputmethod", "org.kde.plasma.printmanager", "org.kde.kdeconnect",
    "org.kde.plasma.weather"]);
var klok = panel.addWidget("org.kde.plasma.digitalclock");
klok.currentConfigGroup = ["Appearance"];
klok.writeConfig("showDate", true);
klok.writeConfig("dateFormat", "shortDate");
panel.addWidget("org.kde.plasma.showdesktop");

// Achtergrond van het bureaublad.
var bureaubladen = desktopsForActivity(currentActivity());
for (var i = 0; i < bureaubladen.length; i++) {
    var d = bureaubladen[i];
    d.wallpaperPlugin = "org.kde.image";
    d.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    d.writeConfig("Image", "file:///usr/share/wallpapers/bugos/");
}
