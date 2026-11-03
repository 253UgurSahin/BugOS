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
panel.addWidget("org.kde.plasma.systemtray");
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
