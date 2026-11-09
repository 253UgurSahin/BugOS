// Een nagebootst Plasma-paneel om de JavaScript van bugos-panel te testen (alleen voor tools/test_panel.sh).
// Zoals Plasma: addWidget() zet een widget achteraan; widget.index = n zet hem op plek n (U259).
"use strict";
const fs = require("fs");
const js = fs.readFileSync(process.argv[2], "utf8");
const begin = process.argv[3].split(",");
let id = 1;
const lijst = [];
function maak(type) {
    const w = { id: id++, type, currentConfigGroup: [], writeConfig() {}, readConfig(_k, s) { return s; },
        remove() { lijst.splice(lijst.indexOf(w), 1); } };
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
