// BugOS: eigen regels in het rechtermuismenu van het bureaublad ("Scherminstellingen", "Achtergrond wijzigen"),
// zoals Windows 11 ("Beeldscherminstellingen", "Aan persoonlijke voorkeur aanpassen").
// De bouw (build_files/style.sh, functie bureaubladmenu) zet dit bestand naast de mapweergave van KDE
// (org.kde.desktopcontainment, als BugosBureaubladActies.qml) en laat FolderViewLayer.qml het laden.
// De taakbalk zelf doet er niets mee; het staat hier alleen omdat het bij de BugOS-onderdelen hoort.
import QtQuick
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support

QtObject {
    id: bugos
    readonly property bool nederlands: Qt.locale().name.indexOf("nl") === 0
    function tr(nl, en) { return nederlands ? nl : en }
    // Via bugos-start-data (zoals het startmenu): Instellingen start los van Plasma.
    property P5Support.DataSource opdracht: P5Support.DataSource {
        engine: "executable"
        connectedSources: []
        onNewData: (bron, data) => disconnectSource(bron)
    }
    function voerUit(cmd) { opdracht.connectSource(cmd) }
    property list<QtObject> acties: [
        PlasmaCore.Action {
            text: bugos.tr("Scherminstellingen", "Display settings")
            icon.name: "preferences-desktop-display"
            onTriggered: bugos.voerUit("bugos-start-data --start instelling:scherm")
        },
        PlasmaCore.Action {
            text: bugos.tr("Achtergrond wijzigen", "Change background")
            icon.name: "preferences-desktop-wallpaper"
            onTriggered: bugos.voerUit("bugos-start-data --start instelling:uiterlijk")
        }
    ]
}
