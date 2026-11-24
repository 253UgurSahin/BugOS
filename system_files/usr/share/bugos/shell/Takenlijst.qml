// De takenlijst op de taakbalk: vastgezette apps en open vensters, één knop per app (zoals Windows 11).
// Fase 1 (docs/STANDALONE.md): via libtaskmanager (org.kde.taskmanager), dat de vensterlijst van KWin leest.
// bugos-shell mag die lijst lezen (X-KDE-Wayland-Interfaces in bugos-shell.desktop). Shell.qml laadt dit bestand met
// een Loader: is de module er niet (een test), dan blijft de takenlijst gewoon leeg.
import QtQuick
import QtQuick.Layouts
import org.kde.taskmanager as TaskManager
import org.kde.kirigami as Kirigami

Row {
    id: lijst
    property var launchers: []
    property real knopMaat: 40
    property color zweefKleur: "#22000000"
    property color actiefKleur: "#DE2F3E"
    spacing: 4

    TaskManager.TasksModel {
        id: taken
        groupMode: TaskManager.TasksModel.GroupApplications
        sortMode: TaskManager.TasksModel.SortManual
        separateLaunchers: false
        launchInPlace: true
        launcherList: lijst.launchers
        filterByVirtualDesktop: true
    }

    Repeater {
        model: taken
        delegate: MouseArea {
            id: knop
            width: lijst.knopMaat
            height: lijst.knopMaat
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton | Qt.MiddleButton
            Accessible.name: model.display || ""
            Accessible.role: Accessible.Button
            onClicked: mouse => {
                const index = taken.makeModelIndex(model.index)
                if (mouse.button === Qt.MiddleButton || model.IsLauncher)
                    taken.requestNewInstance(index)
                else if (model.IsActive)
                    taken.requestToggleMinimized(index)
                else
                    taken.requestActivate(index)
            }

            Rectangle {
                anchors.fill: parent
                radius: 8
                color: knop.containsMouse ? lijst.zweefKleur : "transparent"
            }
            Kirigami.Icon {
                anchors.centerIn: parent
                width: Math.round(lijst.knopMaat * 0.7)
                height: width
                source: model.decoration
                roundToIconSize: false
            }
            // Het streepje onder een open app: breder en rood voor het venster dat nu voor is.
            Rectangle {
                visible: !model.IsLauncher
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 1
                width: model.IsActive ? 16 : 6
                height: 3
                radius: 1.5
                color: model.IsActive ? lijst.actiefKleur : "#8A8F9A"
                Behavior on width { NumberAnimation { duration: 120 } }
            }
        }
    }
}
