// Een venster van de schil (paneel, menu, melding, achtergrond). bugos-shell zet het met layer-shell op zijn plek
// (schil.laag) vóór het getoond wordt; zonder layer-shell (tests) is het een gewoon venster zonder rand.
import QtQuick
import QtQuick.Window

Window {
    id: venster
    // paneel, links, rechts, melding, achtergrond of vangnet (zie Schil::laag in shell/src/schil.h)
    property string soort: "paneel"
    property int marge: 0
    // Meteen tonen (paneel, achtergrond) of pas als het nodig is (menu's, meldingen).
    property bool meteen: false
    readonly property bool lagen: schil.heeftLagen()

    color: "transparent"
    flags: Qt.FramelessWindowHint | (soort === "links" || soort === "rechts" || soort === "melding"
                                     ? Qt.WindowStaysOnTopHint : 0)
    visible: false

    Component.onCompleted: {
        schil.laag(venster, soort, marge)
        if (meteen)
            venster.visible = true
    }
}
