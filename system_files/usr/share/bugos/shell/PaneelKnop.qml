// Een knop op de taakbalk (Start, snelmenu, klok, ...): een afgerond vlakje dat zacht oplicht bij aanwijzen, iets
// sterker als je erop drukt of als zijn menu open is (zoals Windows 11). Met Enter, spatie of een klik.
import QtQuick

Item {
    id: knop
    property string naam: ""
    property bool actief: false
    property var o
    property color zweef: Qt.rgba(0, 0, 0, 0.05)    // aanwijzen
    property color vol: Qt.rgba(0, 0, 0, 0.08)      // ingedrukt of open
    property real maat: 40
    property real breedte: maat
    signal geklikt()
    default property alias inhoud: vlak.data

    implicitWidth: breedte
    implicitHeight: maat
    width: implicitWidth
    height: implicitHeight
    activeFocusOnTab: true
    Accessible.name: naam
    Accessible.role: Accessible.Button
    Accessible.onPressAction: geklikt()
    Keys.onReturnPressed: geklikt()
    Keys.onEnterPressed: geklikt()
    Keys.onSpacePressed: geklikt()

    Rectangle {
        id: vlak
        anchors.fill: parent
        radius: 6
        color: knop.actief || muis.pressed ? knop.vol : (muis.containsMouse ? knop.zweef : "transparent")
        border.width: knop.activeFocus ? 2 : 0
        border.color: knop.o ? knop.o.accent : "red"
        Behavior on color { ColorAnimation { duration: 90 } }
    }
    MouseArea {
        id: muis
        anchors.fill: parent
        hoverEnabled: true
        onClicked: knop.geklikt()
    }
}
