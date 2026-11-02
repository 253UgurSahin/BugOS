// BugOS startmenu - koppeling met de taakbalk van Plasma.
// Het eigenlijke menu staat in StartMenu.qml.

import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    property var gegevens: ({ apps: [], favorieten: [], recent: [], gebruiker: { naam: "" } })
    readonly property bool nederlands: Qt.locale().name.indexOf("nl") === 0

    preferredRepresentation: compactRepresentation
    toolTipMainText: nederlands ? "Start" : "Start"
    toolTipSubText: nederlands ? "Apps, bestanden en aan/uit" : "Apps, files and power"
    Plasmoid.icon: "bugos-logo"

    // Een opdracht uitvoeren en (optioneel) het antwoord lezen.
    P5Support.DataSource {
        id: opdracht
        engine: "executable"
        connectedSources: []
        onNewData: (bron, data) => {
            if (bron === "bugos-start-data") {
                try { root.gegevens = JSON.parse(data["stdout"]) } catch (e) { console.warn("BugOS startmenu:", e) }
            }
            disconnectSource(bron)
        }
    }
    function voerUit(cmd) { opdracht.connectSource(cmd) }
    function aanhalen(tekst) { return "'" + String(tekst).replace(/'/g, "'\\''") + "'" }

    onExpandedChanged: if (expanded) voerUit("bugos-start-data")
    Component.onCompleted: voerUit("bugos-start-data")

    compactRepresentation: MouseArea {
        id: knop
        hoverEnabled: true
        onClicked: root.expanded = !root.expanded
        Layout.minimumWidth: Kirigami.Units.iconSizes.medium
        Kirigami.Icon {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.smallSpacing
            source: "bugos-logo"
            active: knop.containsMouse || root.expanded
        }
    }

    fullRepresentation: StartMenu {
        id: menu
        Layout.preferredWidth: Kirigami.Units.gridUnit * 36
        Layout.preferredHeight: Kirigami.Units.gridUnit * 34
        Layout.minimumWidth: Kirigami.Units.gridUnit * 24
        Layout.minimumHeight: Kirigami.Units.gridUnit * 24
        gegevens: root.gegevens
        nederlands: root.nederlands
        color: "transparent"
        icoonTekenaar: Kirigami.Icon {
            property string naam: ""
            source: naam
        }
        onStart: pad => root.voerUit("bugos-start-data --start " + root.aanhalen(pad))
        onOpenBestand: pad => root.voerUit("bugos-start-data --open " + root.aanhalen(pad))
        onAanUit: actie => root.voerUit("bugos-start-data --aan-uit " + actie)
        onSluiten: root.expanded = false
        Connections {
            target: root
            function onExpandedChanged() { if (root.expanded) menu.terugNaarBegin() }
        }
    }
}
