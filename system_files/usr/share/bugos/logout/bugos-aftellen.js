// Gedeeld tussen de uitzetschermen op elk beeldscherm (KDE maakt er één per scherm, met dezelfde QML-motor):
// doe je iets op het ene scherm, dan stopt het aftellen overal, en gebeurt het uitzetten maar één keer (U088).
.pragma library

var gestopt = false
var gedaan = false
var schermen = []

function meld(stop) {
    schermen.push(stop)
    if (gestopt) stop()
}

function stopOveral() {
    gestopt = true
    for (var i = 0; i < schermen.length; i++) {
        try { schermen[i]() } catch (e) { /* dat scherm is al weg */ }
    }
}

function eenKeer() {
    if (gedaan) return false
    gedaan = true
    return true
}
