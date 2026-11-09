// BugOS snelmenu - de belangrijkste knoppen in één paneel.
//
// Jip-en-Janneke: rechtsonder op de taakbalk. Eén klik en je ziet grote
// knoppen voor wifi, bluetooth, game-modus, donker, niet storen en geluid,
// plus een schuif voor het volume. Het pijltje naast een knop opent de
// bijbehorende pagina van BugOS Instellingen (bijv. een wifi-netwerk kiezen).
// Alleen gewone QtQuick, zodat het buiten Plasma getest kan worden.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: snel
    // 'Grote letters' (KDE: 10 punten gewoon, 12 groot): de letters hier groeien mee (U067).
    readonly property real schaal: Qt.application.font.pointSize > 0
        ? Math.min(2, Math.max(1, Qt.application.font.pointSize / 10)) : 1

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
    signal open(string wat)   // "instellingen" of een pagina: wifi, bluetooth, geluid, meldingen

    // Nog geen status binnen? Dan zeggen we dat, in plaats van grijze knoppen.
    readonly property bool leeg: Object.keys(status).length === 0

    // Huisstijl: dezelfde kleuren en maten als de BugOS-apps (Design.qml wordt gemaakt uit bugos_ui.py)
    readonly property bool donker: palette.window.hslLightness < 0.5
    readonly property Design o: Design { donker: snel.donker }
    readonly property color rood: o.accent
    readonly property color tekst: o.tekst
    readonly property color tekst2: o.tekst2
    readonly property color vlak: o.vlak
    readonly property color vlakZweef: o.vlakHover
    readonly property color lijnkleur: o.rand

    function tr(nl, en) { return nederlands ? nl : en }

    implicitWidth: 420
    implicitHeight: kolom.implicitHeight + 20
    color: palette.window
    SystemPalette { id: palette; colorGroup: SystemPalette.Active }

    ColumnLayout {
        id: kolom
        anchors.fill: parent
        anchors.margins: 10   // de pop-up zelf heeft al 12 px rand
        spacing: 16

        RowLayout {
            Layout.fillWidth: true
            Label {
                text: snel.tr("Snelmenu", "Quick menu")
                font.family: snel.o.kopLetter
                font.pixelSize: Math.round(snel.o.letterKop * snel.schaal)
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
                background: Rectangle { radius: 18; color: tandwiel.hovered ? snel.o.knop : "transparent" }
                contentItem: Item {
                    Loader { anchors.centerIn: parent; width: 20; height: 20; sourceComponent: snel.icoonTekenaar; onLoaded: item.naam = "configure" }
                }
            }
        }
        Label {
            objectName: "evenKijken"
            visible: snel.leeg
            text: snel.tr("Even kijken…", "One moment…")
            color: snel.tekst2
            font.pixelSize: Math.round(snel.o.letterKlein * snel.schaal)
            Layout.topMargin: -8
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 3
            rowSpacing: 10
            columnSpacing: 10
            SnelKnop { wat: "wifi"; icoon: "network-wireless"; tekst: "Wifi"; extra: "wifi" }
            SnelKnop { wat: "bluetooth"; icoon: "network-bluetooth"; tekst: "Bluetooth"; extra: "bluetooth" }
            SnelKnop { wat: "spel"; icoon: "input-gamepad"; tekst: snel.tr("Game-modus", "Game mode") }
            SnelKnop { wat: "donker"; icoon: "contrast"; tekst: snel.tr("Donker", "Dark") }
            SnelKnop { wat: "niet_storen"; icoon: "notifications-disabled"; tekst: snel.tr("Niet storen", "Do not disturb"); extra: "meldingen" }
            SnelKnop { wat: "stil"; icoon: "audio-volume-muted"; tekst: snel.tr("Geluid uit", "Mute") }
        }

        // Volume en (op een laptop) de helderheid van het scherm
        SchuifRij {
            wat: "volume"
            icoon: snel.status.stil ? "audio-volume-muted" : "audio-volume-high"
            naam: snel.tr("Volume", "Volume")
            naar: "geluid"
            meerNaam: snel.tr("Meer over geluid", "More about sound")
        }
        SchuifRij {
            wat: "helderheid"
            icoon: "brightness-high"
            naam: snel.tr("Helderheid", "Brightness")
            naar: "scherm"
            meerNaam: snel.tr("Meer over het scherm", "More about the display")
            minimum: 5
        }

        // Batterij (alleen op een laptop)
        Rectangle {
            objectName: "batterij"
            Layout.fillWidth: true
            implicitHeight: 52
            radius: snel.o.rKaart
            color: snel.vlak
            border.width: 1
            border.color: snel.lijnkleur
            visible: typeof snel.status.batterij === "number"
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                spacing: 12
                Loader {
                    Layout.preferredWidth: 22
                    Layout.preferredHeight: 22
                    sourceComponent: snel.icoonTekenaar
                    onLoaded: item.naam = Qt.binding(() => snel.status.laadt ? "battery-charging" : "battery-good")
                }
                Label {
                    Layout.fillWidth: true
                    text: snel.status.laadt
                          ? snel.tr("Batterij " + snel.status.batterij + "%, wordt opgeladen", "Battery " + snel.status.batterij + "%, charging")
                          : snel.tr("Batterij " + snel.status.batterij + "%", "Battery " + snel.status.batterij + "%")
                    color: snel.tekst
                    font.pixelSize: Math.round(snel.o.letterKlein * snel.schaal)
                    font.weight: Font.Medium
                    elide: Text.ElideRight
                }
                Pijltje { naar: "energie"; Accessible.name: snel.tr("Meer over energie", "More about power") }
            }
        }
    }

    // Een rij met een schuif (volume, helderheid). Verborgen als de computer het niet heeft.
    component SchuifRij: Rectangle {
        id: rij
        property string wat
        property string icoon
        property string naam
        property string naar
        property string meerNaam
        property int minimum: 0
        Layout.fillWidth: true
        implicitHeight: 64
        radius: snel.o.rKaart
        color: snel.vlak
        border.width: 1
        border.color: snel.lijnkleur
        objectName: wat
        visible: typeof snel.status[wat] === "number"
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 16
            anchors.rightMargin: 16
            spacing: 12
            Loader {
                Layout.preferredWidth: 22
                Layout.preferredHeight: 22
                sourceComponent: snel.icoonTekenaar
                onLoaded: item.naam = Qt.binding(() => rij.icoon)
            }
            Slider {
                id: schuif
                Layout.fillWidth: true
                from: rij.minimum
                to: 100
                stepSize: 5
                implicitHeight: 28   // anders 0 hoog in sommige stijlen, en dan kun je er niet op klikken
                Accessible.name: rij.naam
                // Wat je koos, onthouden: bij loslaten zet de status-koppeling de oude waarde even terug,
                // dus daar mogen we niet uit lezen. En de status pas weer overnemen als hij is bijgewerkt.
                property real teSturen: 0
                property bool vasthouden: false
                onMoved: { teSturen = value; vasthouden = true; verzend.restart(); loslaten.restart() }
                Binding { target: schuif; property: "value"; value: snel.status[rij.wat] || 0
                          when: !schuif.pressed && !schuif.vasthouden }
                Timer { id: verzend; interval: 150; onTriggered: snel.zet(rij.wat, String(Math.round(schuif.teSturen))) }
                Timer { id: loslaten; interval: 2500; onTriggered: schuif.vasthouden = false }
                background: Rectangle {
                    x: schuif.leftPadding
                    y: schuif.topPadding + schuif.availableHeight / 2 - height / 2
                    width: schuif.availableWidth
                    height: snel.o.schuifSpoor
                    radius: height / 2
                    color: snel.o.schuifUit
                    Rectangle {
                        width: schuif.visualPosition * parent.width
                        height: parent.height
                        radius: height / 2
                        gradient: Gradient {
                            orientation: Gradient.Horizontal
                            GradientStop { position: 0.0; color: snel.o.verloopBegin }
                            GradientStop { position: 1.0; color: snel.rood }
                        }
                    }
                }
                handle: Rectangle {
                    x: schuif.leftPadding + schuif.visualPosition * (schuif.availableWidth - width)
                    y: schuif.topPadding + schuif.availableHeight / 2 - height / 2
                    width: snel.o.schuifKnop; height: width; radius: width / 2
                    color: "#FFFFFF"
                    border.width: 1
                    border.color: snel.o.randSterk
                }
            }
            Label {
                text: Math.round(schuif.value) + "%"
                color: snel.tekst2
                font.pixelSize: Math.round(snel.o.letterKlein * snel.schaal)
                Layout.preferredWidth: 40
                horizontalAlignment: Text.AlignRight
            }
            Pijltje { naar: rij.naar; Accessible.name: rij.meerNaam }
        }
    }

    // Klein rond pijltje: opent de bijbehorende pagina van Instellingen.
    component Pijltje: AbstractButton {
        id: pijl
        property string naar
        implicitWidth: 28; implicitHeight: 28
        hoverEnabled: true
        Accessible.name: snel.tr("Meer", "More")
        ToolTip.visible: hovered
        ToolTip.text: Accessible.name
        onClicked: snel.open(naar)
        Keys.onReturnPressed: clicked()
        Keys.onEnterPressed: clicked()
        background: Rectangle {
            radius: 14
            color: pijl.hovered || pijl.activeFocus ? snel.o.knopHover : "transparent"
        }
        contentItem: Label {
            text: "›"
            color: snel.tekst2
            font.pixelSize: Math.round(20 * snel.schaal)
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
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
        Keys.onReturnPressed: clicked()
        Keys.onEnterPressed: clicked()
        opacity: enabled ? 1 : 0.45
        scale: pressed ? 0.96 : 1.0
        Behavior on scale { NumberAnimation { duration: 90 } }
        background: Rectangle {
            radius: snel.o.rKaart
            color: knop.aan ? "transparent" : (knop.hovered ? snel.vlakZweef : snel.vlak)
            border.width: knop.aan ? 0 : 1
            border.color: snel.lijnkleur
            Rectangle {
                anchors.fill: parent
                radius: snel.o.rKaart
                visible: knop.aan
                gradient: Gradient {
                    GradientStop { position: 0.0; color: snel.o.verloopBegin }
                    GradientStop { position: 1.0; color: snel.rood }
                }
            }
            Rectangle {
                anchors.fill: parent
                radius: snel.o.rKaart
                color: "transparent"
                border.width: knop.activeFocus ? 2 : 0
                border.color: snel.tekst
            }
            // Pijltje naar de bijbehorende pagina van Instellingen (bijv. een netwerk kiezen)
            Pijltje {
                visible: knop.extra !== ""
                naar: knop.extra
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 6
                Accessible.name: snel.tr("Meer over ", "More about ") + knop.tekst.toLowerCase()
                contentItem: Label {
                    text: "›"
                    color: knop.aan ? "white" : snel.tekst2
                    font.pixelSize: Math.round(20 * snel.schaal)
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
            }
        }
        contentItem: ColumnLayout {
            spacing: 8
            Rectangle {
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: 4
                width: 36; height: 36; radius: 18
                color: knop.aan ? Qt.rgba(1, 1, 1, 0.22) : snel.o.knop
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
                font.pixelSize: Math.round(snel.o.letterKlein * snel.schaal)
                font.weight: Font.Medium
                color: knop.aan ? "white" : snel.tekst
            }
        }
    }
}
