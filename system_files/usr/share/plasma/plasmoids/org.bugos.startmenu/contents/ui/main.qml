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
    toolTipMainText: "Start"
    toolTipSubText: nederlands ? "Apps, bestanden en aan/uit" : "Apps, files and power"
    Plasmoid.icon: "bugos-logo"

    // Een opdracht uitvoeren en (optioneel) het antwoord lezen.
    P5Support.DataSource {
        id: opdracht
        engine: "executable"
        connectedSources: []
        onNewData: (bron, data) => {
            if (bron === "bugos-start-data") {
                if (data["exit code"] === 0 && data["stdout"]) {
                    try { root.gegevens = JSON.parse(data["stdout"]) } catch (e) { console.warn("BugOS startmenu:", e) }
                } else {
                    console.warn("BugOS startmenu: bugos-start-data gaf niets terug", data["stderr"] || "")
                }
            }
            disconnectSource(bron)
        }
    }
    function voerUit(cmd) { opdracht.connectSource(cmd) }
    function aanhalen(tekst) { return "'" + String(tekst).replace(/'/g, "'\\''") + "'" }

    onExpandedChanged: if (root.expanded) voerUit("bugos-start-data")
    Component.onCompleted: voerUit("bugos-start-data")

    // Rechtermuisknop op Start: de snelle lijst van Windows (Win+X), met Taakbeheer.
    // De eigen regels van Plasma (aanpassen, verwijderen) staan er niet onder: taakbalk en bureaublad staan op
    // slot (bugos-panel, functie slot). Voor gevorderden: 'bugos-panel bewerken aan'.
    function tr(nl, en) { return nederlands ? nl : en }
    function startApp(desktop) { voerUit("bugos-start-data --start " + aanhalen("/usr/share/applications/" + desktop)) }
    Plasmoid.contextualActions: [
        PlasmaCore.Action {
            text: root.tr("Taakbeheer", "Task Manager")
            icon.name: "bugos-task-manager"
            onTriggered: root.startApp("bugos-task-manager.desktop")
        },
        PlasmaCore.Action {
            text: root.tr("Instellingen", "Settings")
            icon.name: "bugos-settings"
            onTriggered: root.startApp("bugos-settings.desktop")
        },
        PlasmaCore.Action {
            text: root.tr("Bestanden", "Files")
            icon.name: "bugos-files"
            onTriggered: root.startApp("bugos-files.desktop")
        },
        PlasmaCore.Action {
            text: root.tr("Terminal", "Terminal")
            icon.name: "utilities-terminal"
            onTriggered: root.startApp("org.kde.konsole.desktop")
        },
        PlasmaCore.Action {
            text: root.tr("Er werkt iets niet", "Something is not working")
            icon.name: "bugos-help"
            onTriggered: root.startApp("bugos-help.desktop")
        }
    ]

    compactRepresentation: MouseArea {
        id: knop
        hoverEnabled: true
        activeFocusOnTab: true
        Accessible.name: "Start"
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
        // Even groot als de app-tegels ernaast (die tekent de takenlijst op ~32 px).
        // Zonder roundToIconSize: false rondt Kirigami de ~28 px ruimte af naar 22,
        // en dan wordt het lieveheersbeestje maar 16 x 20 px: veel kleiner dan de tegels.
        Kirigami.Icon {
            anchors.centerIn: parent
            readonly property int maat: Math.min(Kirigami.Units.iconSizes.medium, parent.width, parent.height)
            width: maat
            height: maat
            roundToIconSize: false
            source: "bugos-logo"
            active: knop.containsMouse || root.expanded || knop.activeFocus
        }
    }

    fullRepresentation: StartMenu {
        id: menu
        schaal: Kirigami.Theme.defaultFont.pointSize > 0
            ? Math.min(1.5, Math.max(1, Kirigami.Theme.defaultFont.pointSize / 10)) : 1
        // Verhouding zoals het startmenu van Windows 11: breed, en zo hoog als de inhoud (tussen 24 en 34 regels).
        Layout.preferredWidth: Kirigami.Units.gridUnit * 36
        Layout.preferredHeight: implicitHeight
        Layout.minimumWidth: Kirigami.Units.gridUnit * 24
        Layout.minimumHeight: 420
        gegevens: root.gegevens
        nederlands: root.nederlands
        color: "transparent"
        icoonTekenaar: Kirigami.Icon {
            property string naam: ""
            source: naam
            roundToIconSize: false   // de gevraagde maat (46) en niet afronden naar 32
        }
        onStart: pad => root.voerUit("bugos-start-data --start " + root.aanhalen(pad))
        onOpenBestand: pad => root.voerUit("bugos-start-data --open " + root.aanhalen(pad))
        onAanUit: actie => root.voerUit("bugos-start-data --aan-uit " + root.aanhalen(actie))
        onSluiten: root.expanded = false
        Connections {
            target: root
            function onExpandedChanged() { if (root.expanded) menu.terugNaarBegin() }
        }
    }
}
