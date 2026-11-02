// BugOS snelmenu - de belangrijkste knoppen in één paneel.
//
// Jip-en-Janneke: rechtsonder op de taakbalk. Eén klik en je ziet grote
// knoppen voor wifi, bluetooth, game-modus, donker, niet storen en het volume.
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

    readonly property color rood: "#D93A3A"
    function tr(nl, en) { return nederlands ? nl : en }

    implicitWidth: 400
    implicitHeight: kolom.implicitHeight + 40
    color: palette.window
    SystemPalette { id: palette; colorGroup: SystemPalette.Active }

    ColumnLayout {
        id: kolom
        anchors.fill: parent
        anchors.margins: 20
        spacing: 14

        GridLayout {
            Layout.fillWidth: true
            columns: 3
            rowSpacing: 10
            columnSpacing: 10
            SnelKnop { wat: "wifi"; icoon: "network-wireless"; tekst: "Wifi"; extra: "kcm_networkmanagement" }
            SnelKnop { wat: "bluetooth"; icoon: "preferences-system-bluetooth"; tekst: "Bluetooth"; extra: "kcm_bluetooth" }
            SnelKnop { wat: "spel"; icoon: "input-gaming"; tekst: snel.tr("Game-modus", "Game mode") }
            SnelKnop { wat: "donker"; icoon: "weather-clear-night"; tekst: snel.tr("Donker", "Dark") }
            SnelKnop { wat: "niet_storen"; icoon: "notifications-disabled"; tekst: snel.tr("Niet storen", "Do not disturb") }
            SnelKnop { wat: "stil"; icoon: "audio-volume-muted"; tekst: snel.tr("Geluid uit", "Mute") }
        }

        RowLayout {
            Layout.fillWidth: true
            visible: snel.status.volume !== null && snel.status.volume !== undefined
            spacing: 10
            Loader {
                Layout.preferredWidth: 24
                Layout.preferredHeight: 24
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
            }
            Label { text: Math.round(volume.value) + "%"; Layout.preferredWidth: 44; horizontalAlignment: Text.AlignRight }
        }

        Button {
            Layout.fillWidth: true
            text: snel.tr("Alle instellingen", "All settings")
            onClicked: snel.open("instellingen")
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
        implicitHeight: 84
        hoverEnabled: true
        Accessible.name: tekst
        Accessible.checkable: true
        Accessible.checked: aan
        onClicked: snel.zet(wat, aan ? "uit" : "aan")
        onPressAndHold: if (extra !== "") snel.open(extra)
        opacity: enabled ? 1 : 0.4
        background: Rectangle {
            radius: 16
            color: knop.aan ? snel.rood : (knop.hovered ? Qt.rgba(palette.text.r, palette.text.g, palette.text.b, 0.10) : Qt.rgba(palette.text.r, palette.text.g, palette.text.b, 0.05))
            border.width: knop.activeFocus ? 2 : 0
            border.color: snel.rood
        }
        contentItem: ColumnLayout {
            spacing: 6
            Loader {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 28
                Layout.preferredHeight: 28
                sourceComponent: snel.icoonTekenaar
                onLoaded: item.naam = knop.icoon
            }
            Label {
                text: knop.tekst
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
                font.pixelSize: 13
                color: knop.aan ? "white" : palette.text
            }
        }
    }
}
