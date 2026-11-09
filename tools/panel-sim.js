// Een nagebootst Plasma-paneel om de JavaScript van bugos-panel te testen (alleen voor tools/test_panel.sh).
// Zoals Plasma: addWidget() zet een widget achteraan; widget.index = n zet hem op plek n (U259).
"use strict";
const fs = require("fs");
const js = fs.readFileSync(process.argv[2], "utf8");
const begin = process.argv[3].split(",");
let id = 1;
const lijst = [];
function maak(type) {
    const cfg = {};
    if (type === "org.kde.plasma.icontasks" && process.env.LAUNCHERS) cfg.launchers = process.env.LAUNCHERS.split(",");
    const w = { id: id++, type, cfg, currentConfigGroup: [], writeConfig(k, v) { cfg[k] = v; },
        readConfig(k, s) { return k in cfg ? cfg[k] : s; }, remove() { lijst.splice(lijst.indexOf(w), 1); } };
    Object.defineProperty(w, "index", {
        get() { return lijst.indexOf(w); },
        set(n) { lijst.splice(lijst.indexOf(w), 1); lijst.splice(n, 0, w); },
    });
    return w;
}
for (const t of begin) lijst.push(maak(t));
const paneel = { widgets: () => lijst.slice(), addWidget(t) { const w = maak(t); lijst.push(w); return w; },
    currentConfigGroup: [], readConfig(_k, s) { return s; }, writeConfig() {}, reloadConfig() {} };
global.panels = () => [paneel];
global.print = () => {};
new Function(js + "\n" + process.argv[4])();
console.log(lijst.map((w) => w.type).join(","));
const taken = lijst.find((w) => w.type === "org.kde.plasma.icontasks");
if (taken && taken.cfg.launchers) console.log(taken.cfg.launchers.join(","));
