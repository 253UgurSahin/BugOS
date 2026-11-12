// BugOS klok - de klok rechts op de taakbalk.
//
// Waarom een eigen klok: de klok van KDE tekent de datum altijd kleiner dan de tijd, en maakt beide zo
// groot als de taakbalk hoog is. In Windows 11 staan tijd en datum klein en even groot onder elkaar; zo
// doet BugOS het ook. Klik erop voor een kalender (die van KDE, in een eigen bestand: lukt die niet, dan
// blijft de klok gewoon werken).
// Rechtermuisknop: "Datum en tijd aanpassen" en "Meldingsinstellingen", zoals Windows 11 (de taakbalk staat op slot,
// dus zonder deze regels was er helemaal geen menu).

import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    property date nu: new Date()
    readonly property bool nederlands: Qt.locale().name.indexOf("nl") === 0
    function tr(nl, en) { return nederlands ? nl : en }

    // Elke seconde kijken (goedkoop), zodat de minuut op tijd verspringt, ook na slaapstand.
    Timer {
        interval: 1000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.nu = new Date()
    }

    // Een pagina van Instellingen los starten, via dezelfde helper als het startmenu (bugos-start-data).
    P5Support.DataSource {
        id: opdracht
        engine: "executable"
        connectedSources: []
        onNewData: (bron, data) => disconnectSource(bron)
    }
    function voerUit(cmd) { opdracht.connectSource(cmd) }

    Plasmoid.contextualActions: [
        PlasmaCore.Action {
            text: root.tr("Datum en tijd aanpassen", "Adjust date and time")
            icon.name: "preferences-system-time"
            onTriggered: root.voerUit("bugos-start-data --start instelling:tijd")
        },
        PlasmaCore.Action {
            text: root.tr("Meldingsinstellingen", "Notification settings")
            icon.name: "preferences-desktop-notification"
            onTriggered: root.voerUit("bugos-start-data --start instelling:meldingen")
        }
    ]

    preferredRepresentation: compactRepresentation
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    toolTipMainText: Qt.formatDate(root.nu, Qt.locale().dateFormat(Locale.LongFormat))
    toolTipSubText: ""

    compactRepresentation: MouseArea {
        id: knop
        hoverEnabled: true
        activeFocusOnTab: true
        Accessible.name: tijd.text + ", " + datum.text
        Accessible.role: Accessible.Button
        // Zelfde truc als het startmenu: bij indrukken sluit Plasma een open kalender al (U203).
        property bool wasOpen: false
        onPressed: wasOpen = root.expanded
        onClicked: root.expanded = !wasOpen
        Layout.minimumWidth: kolom.implicitWidth + Kirigami.Units.largeSpacing
        Layout.preferredWidth: Layout.minimumWidth
        Layout.fillHeight: true

        Rectangle {
            anchors.fill: parent
            anchors.margins: 3
            radius: 6
            color: Kirigami.Theme.textColor
            opacity: knop.containsMouse || root.expanded ? 0.08 : 0
        }
        ColumnLayout {
            id: kolom
            anchors.centerIn: parent
            spacing: 0
            // Even groot, zoals Windows 11 (12 px bij 100%; groeit mee met de schaal van het scherm).
            QQC2.Label {
                id: tijd
                Layout.alignment: Qt.AlignRight
                text: Qt.formatTime(root.nu, Qt.locale().timeFormat(Locale.ShortFormat))
                color: Kirigami.Theme.textColor
                font.pixelSize: 12
            }
            QQC2.Label {
                id: datum
                Layout.alignment: Qt.AlignRight
                text: Qt.formatDate(root.nu, Qt.locale().dateFormat(Locale.ShortFormat))
                color: Kirigami.Theme.textColor
                font.pixelSize: 12
            }
        }
    }

    fullRepresentation: Item {
        Layout.preferredWidth: Kirigami.Units.gridUnit * 20
        Layout.preferredHeight: Kirigami.Units.gridUnit * 21
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.smallSpacing
            QQC2.Label {
                text: Qt.formatDate(root.nu, Qt.locale().dateFormat(Locale.LongFormat))
                font.pixelSize: 18
                font.weight: Font.DemiBold
                color: Kirigami.Theme.textColor
                Layout.fillWidth: true
                elide: Text.ElideRight
            }
            Loader {
                Layout.fillWidth: true
                Layout.fillHeight: true
                active: root.expanded
                source: "Kalender.qml"
            }
        }
    }
}
