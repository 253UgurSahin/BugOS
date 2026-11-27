// Het bureaublad van één scherm: de achtergrond (je eigen foto of de BugOS-achtergrond) en, op het hoofdscherm, de
// bestanden uit je bureaubladmap als pictogrammen, van linksboven naar beneden (zoals Windows).
//   dubbelklik: openen (een starter start de app)
//   rechtermuisknop op een pictogram: Openen, Openen in quarantaine (een programma), Tonen in Bestanden, Weggooien
//   rechtermuisknop op het bureaublad: Achtergrond wijzigen, Beeldscherm, Bureaubladmap openen
import QtQuick
import QtQuick.Window
import Qt.labs.folderlistmodel

LaagVenster {
    id: bureaublad
    property var r
    property bool hoofd: false
    objectName: hoofd ? "bureaublad" : "bureaublad-extra"
    soort: "achtergrond"
    meteen: true
    width: screen ? screen.width : 1280
    height: screen ? screen.height : 800
    color: r.donker ? "#111216" : "#F6F5F5"

    Image {
        anchors.fill: parent
        source: bureaublad.r.achtergrondBeeld !== "" ? "file://" + bureaublad.r.achtergrondBeeld : ""
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        sourceSize.width: bureaublad.width
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onClicked: mouse => {
            pictogrammen.currentIndex = -1
            if (mouse.button === Qt.RightButton)
                bureaublad.r.bureaubladMenu(bureaublad.screen, mouse.x, mouse.y, "")
        }
    }

    FolderListModel {
        id: bestanden
        folder: bureaublad.hoofd && instellingen.bureaubladMap !== "" ? "file://" + instellingen.bureaubladMap : ""
        showDirsFirst: true
        showHidden: false
        sortField: FolderListModel.Name
    }

    GridView {
        id: pictogrammen
        objectName: "bureaubladPictogrammen"
        visible: bureaublad.hoofd
        x: 12
        y: 12
        width: parent.width - 24
        height: parent.height - bureaublad.r.paneelHoogte - 24
        flow: GridView.FlowTopToBottom
        cellWidth: 100
        cellHeight: 104
        interactive: false
        currentIndex: -1
        model: bestanden
        delegate: Item {
            id: pictogram
            required property int index
            required property string fileName
            required property string filePath
            required property bool fileIsDir
            width: 96
            height: 100
            readonly property bool gekozen: pictogrammen.currentIndex === index
            readonly property string naam: fileName.endsWith(".desktop") ? fileName.slice(0, -8) : fileName
            Accessible.role: Accessible.ListItem
            Accessible.name: naam

            Rectangle {
                anchors.fill: parent
                radius: 8
                color: pictogram.gekozen ? Qt.rgba(0.87, 0.18, 0.24, 0.35)
                                         : (muis.containsMouse ? Qt.rgba(1, 1, 1, 0.18) : "transparent")
            }
            Image {
                id: plaatje
                anchors.horizontalCenter: parent.horizontalCenter
                y: 6
                width: 48; height: 48
                sourceSize.width: 96; sourceSize.height: 96
                source: "image://icon/bestand:" + pictogram.filePath
            }
            Text {
                anchors.top: plaatje.bottom
                anchors.topMargin: 4
                anchors.horizontalCenter: parent.horizontalCenter
                width: parent.width - 8
                horizontalAlignment: Text.AlignHCenter
                text: pictogram.naam
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
                color: "white"
                style: Text.Outline
                styleColor: Qt.rgba(0, 0, 0, 0.55)
                font.pixelSize: 12
            }
            MouseArea {
                id: muis
                anchors.fill: parent
                hoverEnabled: true
                acceptedButtons: Qt.LeftButton | Qt.RightButton
                onClicked: mouse => {
                    pictogrammen.currentIndex = pictogram.index
                    if (mouse.button === Qt.RightButton)
                        bureaublad.r.bureaubladMenu(bureaublad.screen, pictogram.x + mouse.x + 12,
                                                    pictogram.y + mouse.y + 12, pictogram.filePath)
                }
                onDoubleClicked: bureaublad.r.openBestand(pictogram.filePath)
            }
        }
    }
}
