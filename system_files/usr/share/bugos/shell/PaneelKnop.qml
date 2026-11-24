// Een knop op de taakbalk (Start, snelmenu, klok): een afgeronde vlak dat oplicht bij aanwijzen en als zijn menu open is.
// Met Enter, spatie of een klik.
import QtQuick

Item {
    id: knop
    property string naam: ""
    property bool actief: false
    property var o
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
        radius: 8
        color: knop.actief ? knop.o.knopHover : (muis.containsMouse ? knop.o.knopHover : "transparent")
        border.width: knop.activeFocus ? 2 : 0
        border.color: knop.o.accent
    }
    MouseArea {
        id: muis
        anchors.fill: parent
        hoverEnabled: true
        onClicked: knop.geklikt()
    }
}
