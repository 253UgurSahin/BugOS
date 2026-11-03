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
    toolTipSubText: nederlands ? "Wifi, geluid, bluetooth en meer" : "Wi-Fi, sound, Bluetooth and more"
    Plasmoid.icon: "preferences-system"

    P5Support.DataSource {
        id: opdracht
        engine: "executable"
        connectedSources: []
        onNewData: (bron, data) => {
            if (bron.indexOf("bugos-start-data") === 0 && data["exit code"] === 0 && data["stdout"]) {
                try { root.status = JSON.parse(data["stdout"]) } catch (e) { console.warn("BugOS snelmenu:", e) }
            }
            disconnectSource(bron)
        }
    }
    function voerUit(cmd) { opdracht.connectSource(cmd) }

    Component.onCompleted: voerUit("bugos-start-data --snel")
    onExpandedChanged: if (expanded) voerUit("bugos-start-data --snel")
    Timer { interval: 5000; repeat: true; running: root.expanded; onTriggered: root.voerUit("bugos-start-data --snel") }

    compactRepresentation: MouseArea {
        id: knop
        hoverEnabled: true
        activeFocusOnTab: true
        Accessible.name: root.toolTipMainText
        Accessible.role: Accessible.Button
        onClicked: root.expanded = !root.expanded
        Keys.onReturnPressed: root.expanded = !root.expanded
        Keys.onEnterPressed: root.expanded = !root.expanded
        Keys.onSpacePressed: root.expanded = !root.expanded
        Layout.minimumWidth: Kirigami.Units.iconSizes.medium
        Layout.minimumHeight: Kirigami.Units.iconSizes.medium
        // Eigen BugOS-icoon: twee schuifjes
        Kirigami.Icon {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.smallSpacing
            source: Qt.resolvedUrl("../icons/bugos-snelmenu.svg")
            isMask: true
            color: Kirigami.Theme.textColor
            active: knop.containsMouse || root.expanded || knop.activeFocus
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
            property bool wit: false
            source: naam
            isMask: wit
            color: "white"
        }
        onZet: (wat, waarde) => root.voerUit("bugos-start-data --zet " + wat + " " + waarde)
        onOpen: wat => {
            // "instellingen" = de startpagina van BugOS Instellingen, anders één pagina (wifi, geluid, ...)
            root.voerUit(wat === "instellingen" ? "bugos-instellingen" : "bugos-instellingen " + wat)
            root.expanded = false
        }
    }
}
