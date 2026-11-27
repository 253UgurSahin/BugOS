// De takenlijst op de taakbalk: vastgezette apps en open vensters, één knop per app (zoals Windows 11).
// Fase 1-2 (docs/STANDALONE.md): via libtaskmanager (org.kde.taskmanager), dat de vensterlijst van KWin leest.
// bugos-shell mag die lijst lezen (X-KDE-Wayland-Interfaces in bugos-shell.desktop). Paneel.qml laadt dit bestand met
// een Loader: is de module er niet (een test), dan blijft de takenlijst gewoon leeg.
//
// Rechtermuisknop op een app: Nieuw venster, Vastmaken aan / Losmaken van taakbalk, Venster sluiten. Het menu zelf
// tekent de schil (menuVraag); vastzetten bewaart de schil in ~/.config/bugos/taakbalk.
import QtQuick
import QtQuick.Layouts
import org.kde.taskmanager as TaskManager
import org.kde.kirigami as Kirigami

Row {
    id: lijst
    property var launchers: []
    property real knopMaat: 40
    property color zweefKleur: "#0D000000"
    property color actiefVlak: "#14000000"   // de knop van het venster dat nu voor is
    property color actiefKleur: "#DE2F3E"
    readonly property bool nederlands: Qt.locale().name.indexOf("nl") === 0
    function tr(nl, en) { return nederlands ? nl : en }
    signal menuVraag(var regels, real x, var terug)
    signal vastzetten(string url, bool aan)
    spacing: 4

    // 'file:///usr/share/applications/x.desktop' of 'applications:x.desktop' -> 'applications:x.desktop'
    function launcherNaam(url) {
        const s = String(url || "")
        if (s.indexOf("applications:") === 0)
            return s
        const i = s.lastIndexOf("/")
        return s.endsWith(".desktop") && i >= 0 ? "applications:" + s.substring(i + 1) : s
    }

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
            required property var model
            required property int index
            width: lijst.knopMaat
            height: lijst.knopMaat
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton | Qt.MiddleButton | Qt.RightButton
            Accessible.name: model.display || ""
            Accessible.role: Accessible.Button
            onClicked: mouse => {
                const index = taken.makeModelIndex(knop.index)
                if (mouse.button === Qt.RightButton) {
                    lijst.openMenu(knop, index)
                } else if (mouse.button === Qt.MiddleButton || knop.model.IsLauncher) {
                    taken.requestNewInstance(index)
                } else if (knop.model.IsActive) {
                    taken.requestToggleMinimized(index)
                } else {
                    taken.requestActivate(index)
                }
            }

            Rectangle {
                anchors.fill: parent
                radius: 6
                color: knop.pressed || (knop.model.IsActive && !knop.model.IsLauncher) ? lijst.actiefVlak
                     : knop.containsMouse ? lijst.zweefKleur : "transparent"
                Behavior on color { ColorAnimation { duration: 90 } }
            }
            Kirigami.Icon {
                anchors.centerIn: parent
                width: Math.round(lijst.knopMaat * 0.6)   // 24 px op een gewone taakbalk, zoals Windows 11
                height: width
                source: knop.model.decoration
                roundToIconSize: false
            }
            // Het streepje onder een open app: breder en rood voor het venster dat nu voor is.
            Rectangle {
                visible: !knop.model.IsLauncher
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.bottom: parent.bottom
                anchors.bottomMargin: 1
                width: knop.model.IsActive ? 16 : 6
                height: 3
                radius: 1.5
                color: knop.model.IsActive ? lijst.actiefKleur : "#8A8F9A"
                Behavior on width { NumberAnimation { duration: 120 } }
            }
        }
    }

    function openMenu(knop, index) {
        const url = launcherNaam(knop.model.LauncherUrlWithoutIcon)
        const vast = lijst.launchers.indexOf(url) >= 0
        const regels = [{ tekst: knop.model.display || "", kinderen: [] }]
        regels[0].aan = false
        const acties = []
        acties.push({ tekst: lijst.tr("Nieuw venster", "New window"), icoon: "window-new", doe: "nieuw" })
        if (url !== "")
            acties.push(vast ? { tekst: lijst.tr("Losmaken van taakbalk", "Unpin from taskbar"), icoon: "window-unpin", doe: "los" }
                             : { tekst: lijst.tr("Vastmaken aan taakbalk", "Pin to taskbar"), icoon: "window-pin", doe: "vast" })
        if (!knop.model.IsLauncher) {
            acties.push({ scheiding: true })
            acties.push({ tekst: (knop.model.ChildCount || 0) > 1 ? lijst.tr("Alle vensters sluiten", "Close all windows")
                                                                : lijst.tr("Venster sluiten", "Close window"),
                          icoon: "window-close", doe: "sluit" })
        }
        lijst.menuVraag(regels.concat([{ scheiding: true }]).concat(acties), knop.x, regel => {
            if (regel.doe === "nieuw")
                taken.requestNewInstance(index)
            else if (regel.doe === "vast" || regel.doe === "los")
                lijst.vastzetten(url, regel.doe === "vast")
            else if (regel.doe === "sluit")
                taken.requestClose(index)
        })
    }
}
