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
    // In Plasma zet main.qml dit via Kirigami.Theme (dat verandert meteen mee, Qt.application.font niet) (U084).
    property real schaal: Qt.application.font.pointSize > 0
        ? Math.min(1.5, Math.max(1, Qt.application.font.pointSize / 10)) : 1

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
                // 'Alle instellingen' heet in het startmenu de KDE-app; dit is BugOS Instellingen (U324)
                Accessible.name: snel.tr("Instellingen", "Settings")
                ToolTip.visible: hovered
                ToolTip.text: Accessible.name
                onClicked: snel.open("instellingen")
                Keys.onReturnPressed: clicked()   // ook met Enter, zoals de andere knoppen (U135)
                Keys.onEnterPressed: clicked()
                background: Rectangle {
                    radius: 18
                    color: tandwiel.hovered || tandwiel.activeFocus ? snel.o.knop : "transparent"
                    border.width: tandwiel.activeFocus ? 2 : 0
                    border.color: snel.rood
                }
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
            // kortWaarom/waarom: wat een grijze tegel zegt (A-02). bugos-start-data --snel geeft null als de computer
            // het niet heeft: geen wifi-kaart, geen bluetooth, geen luidspreker.
            SnelKnop {
                wat: "wifi"; icoon: "network-wireless"; tekst: snel.tr("Wifi", "Wi-Fi"); extra: "wifi"
                kortWaarom: snel.tr("Geen wifi", "No Wi-Fi")
                waarom: snel.tr("Deze computer heeft geen wifi. Met een kabel werkt internet gewoon.",
                                "This computer has no Wi-Fi. Internet over a cable still works.")
            }
            SnelKnop {
                wat: "bluetooth"; icoon: "network-bluetooth"; tekst: "Bluetooth"; extra: "bluetooth"
                kortWaarom: snel.tr("Geen bluetooth", "No Bluetooth")
                waarom: snel.tr("Deze computer heeft geen bluetooth.", "This computer has no Bluetooth.")
            }
            SnelKnop { wat: "spel"; icoon: "input-gamepad"; tekst: snel.tr("Game-modus", "Game mode") }
            SnelKnop { wat: "donker"; icoon: "contrast"; tekst: snel.tr("Donker", "Dark") }
            SnelKnop { wat: "niet_storen"; icoon: "notifications-disabled"; tekst: snel.tr("Niet storen", "Do not disturb"); extra: "meldingen" }
            SnelKnop {
                wat: "stil"; icoon: "audio-volume-muted"; tekst: snel.tr("Geluid uit", "Mute")
                kortWaarom: snel.tr("Geen geluid", "No sound")
                waarom: snel.tr("Er is geen luidspreker of koptelefoon gevonden.", "No speaker or headphones were found.")
            }
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
                wheelEnabled: true   // ook met het scrollwieltje, zoals het volume van KDE (U348)
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
                Layout.preferredWidth: Math.round(44 * snel.schaal)
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
            border.width: pijl.activeFocus ? 2 : 0   // (U135)
            border.color: snel.rood
        }
        contentItem: Label {
            text: "›"
            color: snel.tekst2
            font.pixelSize: Math.round(20 * snel.schaal)
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

    // Een tegel van het snelmenu (wifi, bluetooth, game-modus, ...): klik = aan/uit.
    //
    // A-02 (VM-test): het pijltje (›) zat vroeger in de 'background' van de tegel. Dat ligt ONDER de knop, dus de klik
    // ging naar de tegel zelf: het pijltje van 'Niet storen' zette niet storen aan in plaats van Instellingen te
    // openen. En stond de tegel uit (geen wifi-kaart: status null), dan erfde het pijltje 'enabled: false' en deed
    // het niets. Daarom is de tegel nu een gewoon Item met twee broertjes: de knop (de hele tegel) en het pijltje
    // erboven. Het pijltje werkt ook als de tegel grijs is: Instellingen > Wifi legt dan uit wat er aan de hand is.
    // Een grijze tegel zegt nu ook waarom: een korte regel op de tegel ('Geen wifi') en een uitleg bij het aanwijzen
    // ('Deze computer heeft geen wifi'), want een grijze knop zonder reden lijkt kapot.
    component SnelKnop: Item {
        id: vak
        property string wat
        property string icoon
        property string tekst
        property string extra: ""
        // Waarom de tegel grijs is: kort op de tegel en een hele zin bij het aanwijzen.
        property string kortWaarom: snel.tr("Niet beschikbaar", "Not available")
        property string waarom: snel.tr("Dit kan op deze computer niet.", "This is not available on this computer.")
        readonly property var stand: snel.status[wat]
        readonly property bool aan: stand === true
        // null of ontbrekend = deze computer heeft het niet (bijv. geen wifi-kaart, geen geluid)
        readonly property bool beschikbaar: stand !== null && stand !== undefined
        // Alleen 'niet beschikbaar' zeggen als de status er al is; daarvoor staat er 'Even kijken…' bovenaan.
        readonly property bool zonder: !snel.leeg && !beschikbaar
        objectName: "tegel-" + wat
        Layout.fillWidth: true
        Layout.preferredWidth: 1
        implicitHeight: 92

        // Aanwijzen werkt ook op een uitgeschakelde knop niet; een HoverHandler op het Item zelf wel.
        HoverHandler { id: zweven }
        ToolTip.visible: vak.zonder && zweven.hovered && !pijl.hovered
        ToolTip.text: vak.waarom
        ToolTip.delay: 300

        AbstractButton {
            id: knop
            objectName: "knop-" + vak.wat
            anchors.fill: parent
            enabled: vak.beschikbaar
            hoverEnabled: true
            Accessible.name: vak.tekst
            Accessible.description: vak.zonder ? vak.waarom : ""
            Accessible.checkable: true
            Accessible.checked: vak.aan
            onClicked: snel.zet(vak.wat, vak.aan ? "uit" : "aan")
            Keys.onReturnPressed: clicked()
            Keys.onEnterPressed: clicked()
            opacity: enabled ? 1 : 0.45
            scale: pressed ? 0.96 : 1.0
            Behavior on scale { NumberAnimation { duration: 90 } }
            background: Rectangle {
                radius: snel.o.rKaart
                color: vak.aan ? "transparent" : (knop.hovered ? snel.vlakZweef : snel.vlak)
                border.width: vak.aan ? 0 : 1
                border.color: snel.lijnkleur
                Rectangle {
                    anchors.fill: parent
                    radius: snel.o.rKaart
                    visible: vak.aan
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
            }
            contentItem: ColumnLayout {
                spacing: vak.zonder ? 4 : 8
                Rectangle {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.topMargin: 4
                    width: 36; height: 36; radius: 18
                    color: vak.aan ? Qt.rgba(1, 1, 1, 0.22) : snel.o.knop
                    Loader {
                        anchors.centerIn: parent
                        width: 20; height: 20
                        sourceComponent: snel.icoonTekenaar
                        onLoaded: {
                            item.naam = vak.icoon
                            // In Plasma: pictogram wit maken op een rode (aan) knop
                            if (item.hasOwnProperty("wit")) item.wit = Qt.binding(() => vak.aan)
                        }
                    }
                }
                Label {
                    text: vak.tekst
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideRight
                    font.pixelSize: Math.round(snel.o.letterKlein * snel.schaal)
                    font.weight: Font.Medium
                    color: vak.aan ? "white" : snel.tekst
                }
                // De reden onder de naam, alleen bij een grijze tegel ('Geen wifi').
                Label {
                    objectName: "waarom-" + vak.wat
                    visible: vak.zonder
                    text: vak.kortWaarom
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideRight
                    font.pixelSize: Math.round(11 * snel.schaal)
                    color: snel.tekst2
                }
            }
        }

        // Pijltje naar de bijbehorende pagina van Instellingen (bijv. een netwerk kiezen). Boven de knop (later in de
        // lijst = erbovenop), dus de klik komt hier en niet bij de tegel. Niet grijs met de tegel mee.
        Pijltje {
            id: pijl
            objectName: "pijl-" + vak.wat
            visible: vak.extra !== ""
            enabled: !snel.leeg
            naar: vak.extra
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.margins: 6
            Accessible.name: snel.tr("Meer over ", "More about ") + vak.tekst.toLowerCase()
            contentItem: Label {
                text: "›"
                color: vak.aan ? "white" : snel.tekst2
                font.pixelSize: Math.round(20 * snel.schaal)
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }
    }
}
