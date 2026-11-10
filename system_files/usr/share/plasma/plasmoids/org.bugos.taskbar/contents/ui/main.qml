// BugOS taakbalkruimte - de lege ruimte op de taakbalk, met een Windows-menu.
//
// Waarom dit bestaat: in Windows klik je met de rechtermuisknop op een leeg stuk
// taakbalk en kies je "Taakbeheer". In Plasma hoort dat lege stuk bij de
// takenlijst van KDE (icontasks), en dat menu kunnen we niet uitbreiden: de QML
// van de takenlijst zit sinds Plasma 6.8 ingebakken in het programma.
// Daarom vult dit onderdeel de lege ruimte tussen de apps en het systeemvak.
// De takenlijst rekt dan niet meer uit (icontasks: fill = false), dus een klik
// rechts op "niets" komt hier terecht.
//
// Het onderdeel tekent zelf niets: het is alleen ruimte met een menu.
// Plasma zet onder onze twee regels vanzelf zijn eigen keuzes (taakbalk aanpassen,
// widgets toevoegen); die laten we staan voor wie meer wil.

import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    readonly property bool nederlands: Qt.locale().name.indexOf("nl") === 0
    // Liggende taakbalk (de standaard): in de breedte uitrekken. Staande taakbalk: in de hoogte.
    readonly property bool liggend: Plasmoid.formFactor !== PlasmaCore.Types.Vertical

    function tr(nl, en) { return nederlands ? nl : en }

    // Geen eigen achtergrond en geen aparte pop-up: alleen ruimte.
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    // Zeg tegen het paneel dat we de vrije ruimte mogen opvullen (zoals de KDE-spacer).
    Plasmoid.constraintHints: Plasmoid.CanFillArea
    preferredRepresentation: fullRepresentation

    // Uitrekken in de richting van de taakbalk; de andere kant volgt het paneel.
    // Altijd minstens een duimbreed: ook met veel open vensters blijft er een leeg stuk om rechts op te klikken
    // (anders kromp hij naar 0 en kon je Taakbeheer niet meer vanaf de taakbalk openen).
    readonly property int minimaal: Kirigami.Units.gridUnit * 3
    Layout.fillWidth: liggend
    Layout.fillHeight: !liggend
    Layout.minimumWidth: liggend ? minimaal : -1
    Layout.minimumHeight: liggend ? -1 : minimaal

    // Een programma los starten, via dezelfde helper als het startmenu
    // (bugos-start-data --start kent .desktop-bestanden en 'instelling:<pagina>').
    P5Support.DataSource {
        id: opdracht
        engine: "executable"
        connectedSources: []
        // Het antwoord interesseert ons niet; meteen loslaten zodat dezelfde
        // opdracht een volgende keer opnieuw kan.
        onNewData: (bron, data) => disconnectSource(bron)
    }
    function voerUit(cmd) { opdracht.connectSource(cmd) }

    // De regels in het rechtermuismenu, in de volgorde van Windows 11.
    Plasmoid.contextualActions: [
        PlasmaCore.Action {
            text: root.tr("Taakbeheer", "Task Manager")
            icon.name: "bugos-task-manager"
            onTriggered: root.voerUit("bugos-start-data --start /usr/share/applications/bugos-task-manager.desktop")
        },
        PlasmaCore.Action {
            text: root.tr("Taakbalkinstellingen", "Taskbar settings")
            icon.name: "configure"
            // De taakbalk-schakelaars staan in Instellingen op de pagina "Uiterlijk".
            onTriggered: root.voerUit("bugos-start-data --start instelling:uiterlijk")
        }
    ]

    // Doorzichtige ruimte. Het item moet er wel zijn, anders krijgt het paneel geen maat.
    fullRepresentation: Item {
        Layout.fillWidth: root.liggend
        Layout.fillHeight: !root.liggend
        Layout.minimumWidth: root.liggend ? root.minimaal : -1
        Layout.minimumHeight: root.liggend ? -1 : root.minimaal
    }
}
