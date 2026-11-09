// Gemaakt door tools/design/make_qml.py uit bugos_ui.py (KLEUREN, MATEN).
// Niet met de hand aanpassen: verander bugos_ui.py en draai de maker opnieuw.
import QtQuick

QtObject {
    property bool donker: false

    readonly property color achter: donker ? "#111216" : "#F6F5F5"
    readonly property color zijbalk: donker ? "#111216" : "#F6F5F5"
    readonly property color vlak: donker ? "#1C1E24" : "#FFFFFF"
    readonly property color vlakHover: donker ? "#22252C" : "#FBF9F9"
    readonly property color rand: donker ? "#2B2E36" : "#E6E2E2"
    readonly property color randSterk: donker ? "#3A3E48" : "#D5D0D0"
    readonly property color tekst: donker ? "#EDEEF1" : "#16171C"
    readonly property color tekst2: donker ? "#A3A8B4" : "#5D6270"
    readonly property color tekst3: donker ? "#7C828E" : "#6B7080"   // 4,5:1 op licht (U137)
    readonly property color accent: donker ? "#EA3B4B" : "#DE2F3E"
    readonly property color accentHover: donker ? "#F25262" : "#C82434"
    readonly property color accentTekst: donker ? "#FFFFFF" : "#FFFFFF"
    readonly property color accentZacht: donker ? "#3A1C22" : "#FDE9E9"
    readonly property color accentLijn: donker ? "#6A2A33" : "#F3B7BB"
    readonly property color goed: donker ? "#3FD17F" : "#0E7A48"
    readonly property color goedZacht: donker ? "#13291D" : "#E3F5EC"
    readonly property color letOp: donker ? "#F2B544" : "#8F5600"
    readonly property color letOpZacht: donker ? "#2F2612" : "#FFF3DC"
    readonly property color fout: donker ? "#FF6B70" : "#D3263A"
    readonly property color foutZacht: donker ? "#36181C" : "#FDE8EA"
    readonly property color knop: donker ? "#262930" : "#F1EEEE"
    readonly property color knopHover: donker ? "#2F333B" : "#E8E4E4"
    readonly property color schuifUit: donker ? "#3A3E48" : "#D9D4D4"
    readonly property color mapVoor: donker ? "#67404A" : "#EFC3C7"
    readonly property color mapAchter: donker ? "#7C4F59" : "#DDA2A8"
    readonly property color mapTeken: donker ? "#F5DCE0" : "#8C3A43"
    readonly property color verloopBegin: donker ? "#FF5C50" : "#FF5C50"
    readonly property color verloopEind: donker ? "#EA3B4B" : "#DE2F3E"

    readonly property int rKnop: 12     // knoppen, velden, regels
    readonly property int rKaart: 16    // kaarten en tegels
    readonly property int rGroot: 22    // pop-ups en panelen
    readonly property int schuifSpoor: 8
    readonly property int schuifKnop: 22
    readonly property int knopHoogte: 40
    readonly property int veldHoogte: 44
    readonly property int regelHoogte: 48
    readonly property int rondeKnop: 36

    readonly property int letterKlein: 13
    readonly property int letterTekst: 14
    readonly property int letterRij: 15
    readonly property int letterKop: 20
    readonly property int letterHeld: 26
    readonly property string letter: "Inter"
    readonly property string kopLetter: "Funnel Display"
}
