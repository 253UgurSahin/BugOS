// BugOS snelmenu - de belangrijkste knoppen in één paneel.
//
// Jip-en-Janneke: rechtsonder op de taakbalk. Eén klik en je ziet grote
// knoppen voor wifi, bluetooth, game-modus, donker, niet storen en geluid,
// plus een schuif voor het volume.
// Alleen gewone QtQuick, zodat het buiten Plasma getest kan worden.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: snel

    // Status van "bugos-start-data --snel".
    property var status: ({})
    property bool nederlands: true
    property Component icoonTekenaar: Image {
        property string naam: ""
        source: naam === "" ? "" : "image://icon/" + naam
        sourceSize.width: width
        sourceSize.height: height
    }

    signal zet(string wat, string waarde)
    signal open(string wat)

    // Huisstijl
    readonly property bool donker: palette.window.hslLightness < 0.5
    readonly property color rood: donker ? "#EA3B4B" : "#DE2F3E"
    readonly property color tekst: palette.windowText
    readonly property color tekst2: Qt.rgba(tekst.r, tekst.g, tekst.b, 0.62)
    readonly property color vlak: donker ? Qt.rgba(1, 1, 1, 0.06) : "#FFFFFF"
    readonly property color lijnkleur: Qt.rgba(tekst.r, tekst.g, tekst.b, 0.10)

    function tr(nl, en) { return nederlands ? nl : en }

    implicitWidth: 420
    implicitHeight: kolom.implicitHeight + 44
    color: palette.window
    SystemPalette { id: palette; colorGroup: SystemPalette.Active }

    ColumnLayout {
        id: kolom
        anchors.fill: parent
        anchors.margins: 22
        spacing: 16

        RowLayout {
            Layout.fillWidth: true
            Label {
                text: snel.tr("Snelmenu", "Quick menu")
                font.family: "Funnel Display"
                font.pixelSize: 22
                font.weight: Font.DemiBold
                color: snel.tekst
                Layout.fillWidth: true
            }
            AbstractButton {
                id: tandwiel
                implicitWidth: 36; implicitHeight: 36
                hoverEnabled: true
                Accessible.name: snel.tr("Alle instellingen", "All settings")
                ToolTip.visible: hovered
                ToolTip.text: Accessible.name
                onClicked: snel.open("instellingen")
                background: Rectangle { radius: 18; color: tandwiel.hovered ? Qt.rgba(snel.tekst.r, snel.tekst.g, snel.tekst.b, 0.08) : "transparent" }
                contentItem: Item {
                    Loader { anchors.centerIn: parent; width: 20; height: 20; sourceComponent: snel.icoonTekenaar; onLoaded: item.naam = "configure" }
                }
            }
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 3
            rowSpacing: 10
            columnSpacing: 10
            SnelKnop { wat: "wifi"; icoon: "network-wireless"; tekst: "Wifi"; extra: "kcm_networkmanagement" }
            SnelKnop { wat: "bluetooth"; icoon: "network-bluetooth"; tekst: "Bluetooth"; extra: "kcm_bluetooth" }
            SnelKnop { wat: "spel"; icoon: "input-gamepad"; tekst: snel.tr("Game-modus", "Game mode") }
            SnelKnop { wat: "donker"; icoon: "contrast"; tekst: snel.tr("Donker", "Dark") }
            SnelKnop { wat: "niet_storen"; icoon: "notifications-disabled"; tekst: snel.tr("Niet storen", "Do not disturb") }
            SnelKnop { wat: "stil"; icoon: "audio-volume-muted"; tekst: snel.tr("Geluid uit", "Mute") }
        }

        // Volume
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 64
            radius: 18
            color: snel.vlak
            border.width: snel.donker ? 0 : 1
            border.color: snel.lijnkleur
            visible: snel.status.volume !== null && snel.status.volume !== undefined
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                spacing: 12
                Loader {
                    Layout.preferredWidth: 22
                    Layout.preferredHeight: 22
                    sourceComponent: snel.icoonTekenaar
                    onLoaded: item.naam = Qt.binding(() => snel.status.stil ? "audio-volume-muted" : "audio-volume-high")
                }
                Slider {
                    id: volume
                    Layout.fillWidth: true
                    from: 0
                    to: 100
                    stepSize: 5
                    value: snel.status.volume || 0
                    Accessible.name: snel.tr("Volume", "Volume")
                    onMoved: verzend.restart()
                    Timer { id: verzend; interval: 150; onTriggered: snel.zet("volume", String(Math.round(volume.value))) }
                    background: Rectangle {
                        x: volume.leftPadding
                        y: volume.topPadding + volume.availableHeight / 2 - height / 2
                        width: volume.availableWidth
                        height: 8
                        radius: 4
                        color: Qt.rgba(snel.tekst.r, snel.tekst.g, snel.tekst.b, 0.12)
                        Rectangle {
                            width: volume.visualPosition * parent.width
                            height: parent.height
                            radius: 4
                            gradient: Gradient {
                                orientation: Gradient.Horizontal
                                GradientStop { position: 0.0; color: "#FF5C50" }
                                GradientStop { position: 1.0; color: snel.rood }
                            }
                        }
                    }
                    handle: Rectangle {
                        x: volume.leftPadding + volume.visualPosition * (volume.availableWidth - width)
                        y: volume.topPadding + volume.availableHeight / 2 - height / 2
                        width: 22; height: 22; radius: 11
                        color: "#FFFFFF"
                        border.width: 1
                        border.color: Qt.rgba(0, 0, 0, 0.12)
                    }
                }
                Label {
                    text: Math.round(volume.value) + "%"
                    color: snel.tekst2
                    font.pixelSize: 13
                    Layout.preferredWidth: 40
                    horizontalAlignment: Text.AlignRight
                }
            }
        }
    }

    component SnelKnop: AbstractButton {
        id: knop
        property string wat
        property string icoon
        property string tekst
        property string extra: ""
        readonly property var stand: snel.status[wat]
        readonly property bool aan: stand === true
        enabled: stand !== null && stand !== undefined
        Layout.fillWidth: true
        Layout.preferredWidth: 1
        implicitHeight: 92
        hoverEnabled: true
        Accessible.name: tekst
        Accessible.checkable: true
        Accessible.checked: aan
        onClicked: snel.zet(wat, aan ? "uit" : "aan")
        onPressAndHold: if (extra !== "") snel.open(extra)
        opacity: enabled ? 1 : 0.45
        background: Rectangle {
            radius: 18
            color: knop.aan ? "transparent" : snel.vlak
            border.width: knop.aan || snel.donker ? 0 : 1
            border.color: snel.lijnkleur
            Rectangle {
                anchors.fill: parent
                radius: 18
                visible: knop.aan
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#FF5C50" }
                    GradientStop { position: 1.0; color: snel.rood }
                }
            }
            Rectangle {
                anchors.fill: parent
                radius: 18
                color: "transparent"
                border.width: knop.activeFocus ? 2 : 0
                border.color: snel.tekst
            }
        }
        contentItem: ColumnLayout {
            spacing: 8
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: 4
                width: 36; height: 36; radius: 18
                color: knop.aan ? Qt.rgba(1, 1, 1, 0.22) : Qt.rgba(snel.tekst.r, snel.tekst.g, snel.tekst.b, 0.07)
                Loader {
                    anchors.centerIn: parent
                    width: 20; height: 20
                    sourceComponent: snel.icoonTekenaar
                    onLoaded: {
                        item.naam = knop.icoon
                        // In Plasma: pictogram wit maken op een rode (aan) knop
                        if (item.hasOwnProperty("wit")) item.wit = Qt.binding(() => knop.aan)
                    }
                }
            }
            Label {
                text: knop.tekst
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
                font.pixelSize: 13
                font.weight: Font.Medium
                color: knop.aan ? "white" : snel.tekst
            }
        }
    }
}
