// BugOS bureaublad-indeling
// Taakbalk onderaan, startknop links, klok en pictogrammen rechts.
// Net als je gewend bent - maar dan in BugOS-stijl.

var panel = new Panel;
panel.location = "bottom";
panel.height = 2 * Math.floor(gridUnit * 2.6 / 2);
panel.hiding = "none";
panel.floating = true;

// Startknop met het BugOS-logo.
var start = panel.addWidget("org.kde.plasma.kickoff");
start.currentConfigGroup = ["General"];
start.writeConfig("icon", "bugos-logo");
start.writeConfig("favoritesDisplay", 0);
start.writeConfig("applicationsDisplay", 1);
start.writeConfig("showActionButtonCaptions", true);
start.currentConfigGroup = ["Shortcuts"];
start.writeConfig("global", "Alt+F1");


// Vastgezette programma's en open vensters.
var taken = panel.addWidget("org.kde.plasma.icontasks");
taken.currentConfigGroup = ["General"];
taken.writeConfig("launchers", [
    "applications:org.kde.dolphin.desktop",
    "applications:org.mozilla.firefox.desktop",
    "applications:bugos-winkel.desktop",
    "applications:bugos-instellingen.desktop"
]);

panel.addWidget("org.kde.plasma.marginsseparator");
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
    d.writeConfig("Image", "file:///usr/share/wallpapers/bugos/contents/images/3840x2160.svg");
}
