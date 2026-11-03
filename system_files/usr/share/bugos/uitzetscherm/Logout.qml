// BugOS uitzetscherm (Logout.qml)
//
// Jip-en-Janneke: het donkere scherm dat je ziet als je op "Uitzetten",
// "Opnieuw opstarten" of "Afmelden" drukt. Grote tegels, één rode (Uitzetten)
// en onderaan "Toch niet". Kom je met een keuze uit het startmenu, dan telt
// het scherm 30 seconden af en zegt dat in gewone woorden.
//
// Plasma 6 laadt dit bestand in de "greeter" (ksmserver-logout-greeter) en
// geeft het deze gegevens mee (contextproperties uit C++): sdtype,
// ShutdownType, maysd, canLogout, spdMethods, softwareUpdatePending en
// rebootToFirmwareSetup (die twee bestaan niet in elke versie) en, bij oudere
// versies, screenGeometry. Het scherm meldt de keuze terug met de signalen
// hieronder. build.sh zet dit bestand op de plekken waar Plasma het zoekt.
//
// Alleen gewone QtQuick, geen KDE-onderdelen: zo kan het ook buiten Plasma
// getest worden (tools/test_uitzetscherm.py).

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

Item {
    id: root
    // Zo groot als het scherm: met screenGeometry (oud) of zonder (nieuw).
    width: typeof screenGeometry !== "undefined" ? screenGeometry.width : Screen.width
    height: typeof screenGeometry !== "undefined" ? screenGeometry.height : Screen.height

    // Hiermee meldt het scherm wat de gebruiker koos; de greeter luistert.
    signal logoutRequested()
    signal haltRequested()
    signal haltUpdateRequested()
    signal suspendRequested(int spdMethod)   // 2 = slaapstand, 4 = sluimerstand
    signal rebootRequested()
    signal rebootRequested2(int opt)
    signal rebootUpdateRequested()
    signal cancelRequested()
    signal lockScreenRequested()
    signal cancelSoftwareUpdateRequested()

    // Taal: Nederlands als de computer op Nederlands staat, anders Engels.
    property bool nederlands: Qt.locale().name.indexOf("nl") === 0
    function tr(nl, en) { return nederlands ? nl : en }

    // Het logo mag ontbreken: dan zie je het gewoon niet.
    property url logo: "file:///usr/share/bugos/logo-donker.svg"

    // Wat is er gevraagd? Alles laten zien (Default) of één ding bevestigen.
    readonly property bool toonAlles: sdtype === ShutdownType.ShutdownTypeDefault
    readonly property bool uitzetten: sdtype === ShutdownType.ShutdownTypeHalt
    readonly property bool herstarten: sdtype === ShutdownType.ShutdownTypeReboot
    readonly property bool afmelden: !toonAlles && !uitzetten && !herstarten   // None (en al het andere)
    // Staat er een update klaar? (Deze eigenschap bestaat niet in elke versie.)
    readonly property bool updateKlaar: typeof softwareUpdatePending !== "undefined" && softwareUpdatePending === true
    // Welke knop begint met de focus, zodat Enter meteen bevestigt.
    readonly property bool focusHerstart: maysd && herstarten
    readonly property bool focusUit: maysd && (uitzetten || toonAlles)
    readonly property bool focusAfmelden: canLogout && (afmelden || (toonAlles && !maysd))

    // Aftellen: na 30 seconden gebeurt het vanzelf, tenzij de gebruiker iets doet.
    property int wachttijd: 30
    property int resterend: wachttijd
    property bool gestopt: false
    property bool klaar: false   // pas als alles staat, telt een aanraking als "iets doen"
    function stopAftellen() { if (klaar) gestopt = true }
    function doeHetVanzelf() {
        if (uitzetten) { if (updateKlaar) haltUpdateRequested(); else haltRequested() }
        else if (herstarten) { if (updateKlaar) rebootUpdateRequested(); else rebootRequested() }
        else logoutRequested()
    }
    Component.onCompleted: klaar = true

    // Een BugOS-lijnicoon (24 x 24, lijn van 2, ronde uiteinden) als plaatje, zonder los bestand.
    function icoon(paden) {
        return "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' "
            + "stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>" + paden + "</svg>"
    }
    // Pijltjes gaan naar de volgende zichtbare knop (en aan het eind weer rond).
    function buur(van, stap) {
        const knoppen = [knopSlaap, knopHerstart, knopUit, knopAfmelden, knopAnnuleren]
        const n = knoppen.length
        for (let k = 1; k < n; k++) {
            const knop = knoppen[(((knoppen.indexOf(van) + stap * k) % n) + n) % n]
            if (knop.visible) return knop
        }
        return van
    }

    Timer {
        id: aftellen
        objectName: "aftellen"
        running: !root.toonAlles && !root.gestopt
        repeat: true
        interval: 1000
        onTriggered: {
            root.resterend--
            if (root.resterend <= 0) { root.gestopt = true; root.doeHetVanzelf() }
        }
    }

    // Escape, of een klik naast de knoppen: toch niet.
    Shortcut { sequence: "Escape"; onActivated: root.cancelRequested() }
    Keys.onEscapePressed: root.cancelRequested()
    Rectangle { anchors.fill: parent; color: "#0E0F13"; opacity: 0.86 }
    MouseArea { anchors.fill: parent; onClicked: root.cancelRequested() }

    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(root.width - 48, 920)
        spacing: 0

        Image {
            source: root.logo
            visible: status === Image.Ready
            sourceSize: Qt.size(72, 72)
            Layout.alignment: Qt.AlignHCenter
            Layout.bottomMargin: 24
        }
        Text {
            objectName: "kop"
            text: root.toonAlles ? root.tr("Wat wil je doen?", "What do you want to do?")
                : root.uitzetten ? root.tr("Computer uitzetten?", "Shut down the computer?")
                : root.herstarten ? root.tr("Opnieuw opstarten?", "Restart?")
                : root.tr("Afmelden?", "Log out?")
            font.family: "Funnel Display"
            font.pixelSize: 36
            font.weight: Font.DemiBold
            color: "white"
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
        }
        Text {
            objectName: "uitleg"
            text: root.toonAlles ? root.tr("Kies wat je wilt. Je bestanden zijn bewaard.", "Choose what you want. Your files are saved.")
                : root.gestopt ? root.tr("Weet je het zeker? Druk dan op de knop.", "Are you sure? Then press the button.")
                : root.resterend === 1 ? root.tr("Over 1 seconde gebeurt het vanzelf.", "It happens by itself in 1 second.")
                : root.tr("Over %1 seconden gebeurt het vanzelf.", "It happens by itself in %1 seconds.").arg(root.resterend)
            font.family: "Inter"
            font.pixelSize: 17
            color: Qt.rgba(1, 1, 1, 0.75)
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.WordWrap
            Layout.fillWidth: true
            Layout.topMargin: 10
        }

        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 40
            spacing: 16
            Tegel {
                id: knopSlaap
                objectName: "knop_slaap"
                text: root.tr("Slaapstand", "Sleep")
                paden: "<path d='M19.5 14.6A8 8 0 1 1 9.4 4.5a6.4 6.4 0 0 0 10.1 10.1z'/>"
                visible: spdMethods.SuspendState === true && root.toonAlles
                onClicked: root.suspendRequested(2)
            }
            Tegel {
                id: knopHerstart
                objectName: "knop_herstart"
                text: root.updateKlaar ? root.tr("Opnieuw opstarten voor de update", "Restart for the update")
                                       : root.tr("Opnieuw opstarten", "Restart")
                paden: "<path d='M19.5 12a7.5 7.5 0 1 1-2.2-5.3M19.5 4v4.5H15'/>"
                visible: maysd && (root.herstarten || root.toonAlles)
                focus: root.focusHerstart
                onClicked: root.updateKlaar ? root.rebootUpdateRequested() : root.rebootRequested()
            }
            Tegel {
                id: knopUit
                objectName: "knop_uit"
                rood: true   // de enige rode knop: hier moet je op drukken
                text: root.updateKlaar ? root.tr("Uitzetten na de update", "Shut down after the update")
                                       : root.tr("Uitzetten", "Shut down")
                paden: "<path d='M12 3.5v8'/><path d='M6.6 6.8a7.5 7.5 0 1 0 10.8 0'/>"
                visible: maysd && (root.uitzetten || root.toonAlles)
                focus: root.focusUit
                onClicked: root.updateKlaar ? root.haltUpdateRequested() : root.haltRequested()
            }
            Tegel {
                id: knopAfmelden
                objectName: "knop_afmelden"
                text: root.tr("Afmelden", "Log out")
                paden: "<path d='M13.5 4.5H7A1.5 1.5 0 0 0 5.5 6v12A1.5 1.5 0 0 0 7 19.5h6.5'/><path d='m16 8.5 3.5 3.5-3.5 3.5M9.5 12h10'/>"
                visible: canLogout && (root.afmelden || root.toonAlles)
                focus: root.focusAfmelden
                onClicked: root.logoutRequested()
            }
        }

        // "Toch niet": een witte pil onder de tegels.
        AbstractButton {
            id: knopAnnuleren
            objectName: "knop_annuleren"
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 36
            text: root.tr("Toch niet", "Cancel")
            Accessible.name: text
            hoverEnabled: true
            focusPolicy: Qt.StrongFocus
            focus: !(root.focusHerstart || root.focusUit || root.focusAfmelden)
            leftPadding: 28
            rightPadding: 28
            topPadding: 11
            bottomPadding: 11
            onClicked: root.cancelRequested()
            onHoveredChanged: if (hovered) root.stopAftellen()
            onFocusChanged: root.stopAftellen()
            Keys.onPressed: root.stopAftellen()
            Keys.onReturnPressed: clicked()
            Keys.onEnterPressed: clicked()
            KeyNavigation.left: root.buur(knopAnnuleren, -1)
            KeyNavigation.right: root.buur(knopAnnuleren, 1)
            KeyNavigation.up: root.buur(knopAnnuleren, -1)
            background: Rectangle {
                radius: height / 2
                color: Qt.rgba(1, 1, 1, knopAnnuleren.hovered || knopAnnuleren.down ? 0.14 : 0)
                border.width: knopAnnuleren.activeFocus ? 2 : 1
                border.color: Qt.rgba(1, 1, 1, knopAnnuleren.activeFocus ? 1 : 0.7)
            }
            contentItem: Text {
                text: knopAnnuleren.text
                font.family: "Inter"
                font.pixelSize: 15
                font.weight: Font.Medium
                color: "white"
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
        }
        Text {
            text: root.tr("Of druk op Esc", "Or press Esc")
            font.family: "Inter"
            font.pixelSize: 13
            color: Qt.rgba(1, 1, 1, 0.55)
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: 10
        }
    }

    // Een grote tegel: icoon boven, woord onder. rood = de ene rode hoofdknop.
    component Tegel: AbstractButton {
        id: tegel
        property string paden: ""   // de lijnen van het icoon (SVG-paden, 24 x 24)
        property bool rood: false
        implicitWidth: 168
        implicitHeight: 124
        hoverEnabled: true
        focusPolicy: Qt.StrongFocus
        Accessible.name: text
        scale: down ? 0.96 : 1
        Behavior on scale { NumberAnimation { duration: 90 } }
        // Zodra de gebruiker iets doet (aanwijzen, focus, een toets), stopt het aftellen.
        onHoveredChanged: if (hovered) root.stopAftellen()
        onFocusChanged: root.stopAftellen()
        Keys.onPressed: root.stopAftellen()
        Keys.onReturnPressed: clicked()
        Keys.onEnterPressed: clicked()
        KeyNavigation.left: root.buur(tegel, -1)
        KeyNavigation.right: root.buur(tegel, 1)
        KeyNavigation.down: knopAnnuleren
        background: Rectangle {
            radius: 18
            color: tegel.rood ? (tegel.hovered || tegel.down ? "#EA3B4B" : "#DE2F3E")
                              : Qt.rgba(1, 1, 1, tegel.hovered || tegel.down ? 0.14 : 0.08)
            border.width: tegel.activeFocus ? 2 : 0
            border.color: "white"
            Behavior on color { ColorAnimation { duration: 120 } }
        }
        contentItem: Item {
            Column {
                anchors.centerIn: parent
                width: parent.width
                spacing: 12
                Image {
                    objectName: "icoon"
                    anchors.horizontalCenter: parent.horizontalCenter
                    width: 28
                    height: 28
                    sourceSize: Qt.size(28, 28)
                    source: root.icoon(tegel.paden)
                }
                Text {
                    width: parent.width
                    text: tegel.text
                    font.family: "Inter"
                    font.pixelSize: 15
                    font.weight: Font.Medium
                    color: "white"
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                }
            }
        }
    }
}
