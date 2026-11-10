// BugOS snelmenu - koppeling met de taakbalk van Plasma.
// Het eigenlijke paneel staat in QuickMenu.qml.

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
    // De opdracht gaat via een shell: zet elke waarde tussen enkele aanhalingstekens (zoals het startmenu).
    function aanhalen(tekst) { return "'" + String(tekst).replace(/'/g, "'\\''") + "'" }

    Component.onCompleted: voerUit("bugos-start-data --snel")
    onExpandedChanged: if (expanded) voerUit("bugos-start-data --snel")
    Timer { interval: 5000; repeat: true; running: root.expanded; onTriggered: root.voerUit("bugos-start-data --snel") }

    compactRepresentation: MouseArea {
        id: knop
        hoverEnabled: true
        activeFocusOnTab: true
        Accessible.name: root.toolTipMainText
        Accessible.role: Accessible.Button
        // Bij het indrukken sluit Plasma een open menu al (de focus gaat weg): onthoud hoe het was, anders gaat het bij
        // het loslaten meteen weer open en kun je het met de knop nooit sluiten (U203).
        property bool wasOpen: false
        onPressed: wasOpen = root.expanded
        onClicked: root.expanded = !wasOpen
        Keys.onReturnPressed: root.expanded = !root.expanded
        Keys.onEnterPressed: root.expanded = !root.expanded
        Keys.onSpacePressed: root.expanded = !root.expanded
        Layout.minimumWidth: Kirigami.Units.iconSizes.medium
        Layout.minimumHeight: Kirigami.Units.iconSizes.medium
        // Eigen BugOS-icoon: twee schuifjes.
        // Precies even groot als de pictogrammen van het systeemvak ernaast (22 px).
        // Vroeger vulde het de ruimte min een marge; Kirigami rondde dat af naar een
        // kleinere maat, waardoor het schuifje maar 14 x 12 px werd naast een bel van 20 x 22.
        Kirigami.Icon {
            anchors.centerIn: parent
            // Zo groot als de pictogrammen in het systeemvak van Windows 11 (16), niet groter dan de rest.
            readonly property int maat: Math.min(Kirigami.Units.iconSizes.small, parent.width, parent.height)
            width: maat
            height: maat
            roundToIconSize: false
            source: Qt.resolvedUrl("../icons/bugos-quickmenu.svg")
            isMask: true
            color: Kirigami.Theme.textColor
            active: knop.containsMouse || root.expanded || knop.activeFocus
        }
    }

    fullRepresentation: QuickMenu {
        schaal: Kirigami.Theme.defaultFont.pointSize > 0
            ? Math.min(1.5, Math.max(1, Kirigami.Theme.defaultFont.pointSize / 10)) : 1
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
            // Wit op een rode (aan) tegel, anders gewoon de tekstkleur (zoals overal).
            color: wit ? "white" : Kirigami.Theme.textColor
        }
        onZet: (wat, waarde) => root.voerUit("bugos-start-data --zet " + root.aanhalen(wat) + " " + root.aanhalen(waarde))
        onOpen: wat => {
            // "instellingen" = de startpagina van BugOS Instellingen, anders één pagina (wifi, geluid, ...).
            // Via bugos-start-data (zoals het startmenu): dat start Instellingen los van Plasma, zodat het
            // niet meegaat als het snelmenu stopt, en een tweede klik ook weer werkt.
            const pagina = wat === "instellingen" ? "" : wat
            root.voerUit("bugos-start-data --start " + root.aanhalen("instelling:" + pagina))
            root.expanded = false
        }
    }
}
