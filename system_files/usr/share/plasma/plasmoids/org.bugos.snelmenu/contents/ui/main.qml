// BugOS snelmenu - koppeling met de taakbalk van Plasma.
// Het eigenlijke paneel staat in Snelmenu.qml.

import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    property var status: ({})
    readonly property bool nederlands: Qt.locale().name.indexOf("nl") === 0

    preferredRepresentation: compactRepresentation
    toolTipMainText: nederlands ? "Snelmenu" : "Quick menu"
    toolTipSubText: nederlands ? "Wifi, bluetooth, game-modus en meer" : "Wi-Fi, Bluetooth, game mode and more"
    Plasmoid.icon: "configure"

    P5Support.DataSource {
        id: opdracht
        engine: "executable"
        connectedSources: []
        onNewData: (bron, data) => {
            try { root.status = JSON.parse(data["stdout"]) } catch (e) { }
            disconnectSource(bron)
        }
    }
    function voerUit(cmd) { opdracht.connectSource(cmd) }

    onExpandedChanged: if (expanded) voerUit("bugos-start-data --snel")
    Timer { interval: 5000; repeat: true; running: root.expanded; onTriggered: root.voerUit("bugos-start-data --snel") }

    compactRepresentation: MouseArea {
        id: knop
        hoverEnabled: true
        onClicked: root.expanded = !root.expanded
        Kirigami.Icon {
            anchors.fill: parent
            source: "configure"
            active: knop.containsMouse || root.expanded
        }
    }

    fullRepresentation: Snelmenu {
        Layout.preferredWidth: Kirigami.Units.gridUnit * 22
        Layout.preferredHeight: implicitHeight
        color: "transparent"
        status: root.status
        nederlands: root.nederlands
        icoonTekenaar: Kirigami.Icon {
            property string naam: ""
            source: naam
        }
        onZet: (wat, waarde) => root.voerUit("bugos-start-data --zet " + wat + " " + waarde)
        onOpen: wat => {
            if (wat === "instellingen") root.voerUit("bugos-instellingen")
            else root.voerUit("systemsettings " + wat)
            root.expanded = false
        }
    }
}
