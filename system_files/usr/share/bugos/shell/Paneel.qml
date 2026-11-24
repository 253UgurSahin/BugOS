// De taakbalk van één scherm: Start, de takenlijst, het systeemvak (alleen op het hoofdscherm), het snelmenu, de klok
// en rechts een smal strookje voor 'Bureaublad tonen' (zoals Windows). Rechtermuisknop: op Start de snelle lijst
// (Win+X), op een lege plek Taakbeheer en Bureaublad tonen.
import QtQuick
import QtQuick.Layouts
import QtQuick.Window

LaagVenster {
    id: paneel
    property var r                // Shell.qml (root): menu's, gegevens, kleuren
    property bool hoofd: false    // het hoofdscherm: daar staat het systeemvak
    soort: "paneel"
    meteen: true
    width: screen ? screen.width : 1280
    height: r.paneelHoogte
    color: r.donker ? Qt.rgba(0.11, 0.12, 0.14, 0.92) : Qt.rgba(1, 1, 1, 0.92)

    // x (vanaf links van het scherm) en y (de bovenkant van de taakbalk) van een plek op de taakbalk: voor menu's.
    function plekVan(item, x) { return item.mapToItem(null, x, 0).x }

    Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: paneel.r.o.rand }

    // Rechtermuisknop op een lege plek van de taakbalk.
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.RightButton
        onClicked: mouse => paneel.r.paneelMenu(paneel.screen, mouse.x)
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 8
        anchors.rightMargin: 0
        spacing: 4

        PaneelKnop {
            id: startKnop
            objectName: "startKnop"
            naam: "Start"
            actief: paneel.r.open === "start" && paneel.r.menuScherm === paneel.screen
            o: paneel.r.o
            maat: paneel.r.paneelHoogte - 8
            onGeklikt: paneel.r.toon("start", paneel.screen)
            Image {
                anchors.centerIn: parent
                width: Math.round(parent.width * 0.7)
                height: width
                sourceSize.width: width * 2
                sourceSize.height: height * 2
                source: "image://icon/bugos-logo"
            }
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.RightButton
                onClicked: paneel.r.startKnopMenu(paneel.screen, paneel.plekVan(startKnop, 0))
            }
        }

        Loader {
            id: takenlijst
            objectName: "takenlijst"
            Layout.fillHeight: true
            Layout.alignment: Qt.AlignVCenter
            source: "Takenlijst.qml"
            onLoaded: {
                item.knopMaat = Qt.binding(() => paneel.r.paneelHoogte - 8)
                item.launchers = Qt.binding(() => paneel.r.launchers)
                item.zweefKleur = Qt.binding(() => paneel.r.o.knopHover)
                item.actiefKleur = Qt.binding(() => paneel.r.o.accent)
                item.menuVraag.connect((regels, x, terug) => paneel.r.toonMenu(paneel.screen, paneel.plekVan(item, x),
                                                                                 -1, regels, terug))
                item.vastzetten.connect((url, aan) => paneel.r.zetVast(url, aan))
            }
            onStatusChanged: if (status === Loader.Error)
                console.warn("BugOS-schil: geen takenlijst (org.kde.taskmanager ontbreekt)")
        }

        Item { Layout.fillWidth: true; Layout.fillHeight: true }

        // Het systeemvak: de pictogrammen van apps (Steam, Discord, ...). Alleen op het hoofdscherm.
        Row {
            id: vak
            objectName: "systeemvak"
            visible: paneel.hoofd
            spacing: 2
            Layout.alignment: Qt.AlignVCenter
            Repeater {
                model: paneel.hoofd ? systeemvak : null
                delegate: PaneelKnop {
                    id: vakKnop
                    required property int index
                    required property string titel
                    required property string icoon
                    required property string status
                    required property string uitleg
                    required property bool heeftMenu
                    // Passief (de app heeft niets te melden): niet tonen, zoals Windows dat in het pijltje stopt.
                    visible: status !== "Passive"
                    naam: uitleg !== "" ? uitleg : titel
                    o: paneel.r.o
                    maat: paneel.r.paneelHoogte - 12
                    breedte: 32
                    Image {
                        anchors.centerIn: parent
                        width: 18; height: 18
                        sourceSize.width: 36; sourceSize.height: 36
                        source: vakKnop.icoon
                    }
                    Rectangle {   // de app vraagt aandacht
                        visible: vakKnop.status === "NeedsAttention"
                        width: 6; height: 6; radius: 3
                        anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 4
                        color: paneel.r.o.accent
                    }
                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
                        onClicked: mouse => {
                            const x = paneel.plekVan(vakKnop, 0)
                            const y = (paneel.screen ? paneel.screen.height : 800) - paneel.height
                            if (mouse.button === Qt.MiddleButton)
                                systeemvak.secundair(vakKnop.index, x, y)
                            else if (mouse.button === Qt.LeftButton && systeemvak.activeer(vakKnop.index, x, y))
                                return
                            else
                                paneel.r.vakMenu(paneel.screen, x, vakKnop.index)
                        }
                        onWheel: wheel => systeemvak.scroll(vakKnop.index, wheel.angleDelta.y > 0 ? 1 : -1)
                    }
                }
            }
        }

        // De bel: het meldingencentrum (alleen op het hoofdscherm), met het aantal nieuwe meldingen.
        PaneelKnop {
            id: belKnop
            objectName: "belKnop"
            visible: paneel.hoofd
            naam: meldingen.ongelezen > 0
                  ? paneel.r.tr(meldingen.ongelezen + " nieuwe meldingen", meldingen.ongelezen + " new notifications")
                  : paneel.r.tr("Meldingen", "Notifications")
            actief: paneel.r.open === "meldingen"
            o: paneel.r.o
            maat: paneel.r.paneelHoogte - 8
            onGeklikt: paneel.r.toon("meldingen", paneel.screen)
            // Een belletje van twee vormen (geen pictogramthema nodig).
            Item {
                anchors.centerIn: parent
                width: 18; height: 20
                Rectangle { x: 3; y: 2; width: 12; height: 13; radius: 6; color: "transparent"; border.width: 2; border.color: paneel.r.o.tekst }
                Rectangle { x: 1; y: 12; width: 16; height: 2; radius: 1; color: paneel.r.o.tekst }
                Rectangle { x: 7; y: 16; width: 4; height: 3; radius: 1.5; color: paneel.r.o.tekst }
            }
            Rectangle {
                visible: meldingen.ongelezen > 0
                anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 4
                width: Math.max(16, teller.implicitWidth + 8); height: 16; radius: 8
                color: paneel.r.o.accent
                Text { id: teller; anchors.centerIn: parent; text: meldingen.ongelezen > 9 ? "9+" : meldingen.ongelezen; color: "white"; font.pixelSize: 10; font.bold: true }
            }
        }

        PaneelKnop {
            id: snelKnop
            objectName: "snelKnop"
            naam: paneel.r.tr("Snelmenu", "Quick menu")
            actief: paneel.r.open === "snel" && paneel.r.menuScherm === paneel.screen
            o: paneel.r.o
            maat: paneel.r.paneelHoogte - 8
            onGeklikt: paneel.r.toon("snel", paneel.screen)
            // Twee schuifjes (zoals het snelmenu-pictogram in de Plasma-versie).
            Column {
                anchors.centerIn: parent
                spacing: 5
                Repeater {
                    model: [0.35, 0.65]
                    Item {
                        required property real modelData
                        width: 18; height: 4
                        Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width; height: 2; radius: 1; color: paneel.r.o.tekst }
                        Rectangle { x: parent.width * parent.modelData - 3; anchors.verticalCenter: parent.verticalCenter; width: 6; height: 6; radius: 3; color: paneel.r.o.tekst }
                    }
                }
            }
        }

        PaneelKnop {
            id: klok
            objectName: "klok"
            naam: tijd.text + " " + datum.text
            actief: paneel.r.open === "kalender" && paneel.r.menuScherm === paneel.screen
            o: paneel.r.o
            maat: paneel.r.paneelHoogte - 8
            breedte: Math.max(tijd.implicitWidth, datum.implicitWidth) + 20
            onGeklikt: paneel.r.toon("kalender", paneel.screen)
            property date nu: new Date()
            Timer { interval: 1000; repeat: true; running: true; triggeredOnStart: true; onTriggered: klok.nu = new Date() }
            Column {
                anchors.centerIn: parent
                Text { id: tijd; anchors.right: parent.right; text: Qt.formatTime(klok.nu, "HH:mm"); color: paneel.r.o.tekst; font.pixelSize: Math.round(12 * paneel.r.schaal) }
                Text { id: datum; anchors.right: parent.right; text: Qt.formatDate(klok.nu, "dd-MM-yyyy"); color: paneel.r.o.tekst; font.pixelSize: Math.round(12 * paneel.r.schaal) }
            }
        }

        // Bureaublad tonen: het smalle strookje helemaal rechts, zoals in Windows.
        Rectangle {
            id: bureaubladKnop
            objectName: "bureaubladTonen"
            Layout.fillHeight: true
            Layout.preferredWidth: 10
            color: bureaubladMuis.containsMouse ? paneel.r.o.knopHover : "transparent"
            Rectangle { anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; width: 1; height: parent.height * 0.5; color: paneel.r.o.rand }
            Accessible.role: Accessible.Button
            Accessible.name: paneel.r.tr("Bureaublad tonen", "Show desktop")
            MouseArea { id: bureaubladMuis; anchors.fill: parent; hoverEnabled: true; onClicked: paneel.r.bureaubladWissel() }
        }
    }
}
