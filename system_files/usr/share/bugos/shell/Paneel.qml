// De taakbalk van één scherm: Start en de takenlijst (links of in het midden), en rechts het systeemvak (alleen op het
// hoofdscherm), één knop met de icoontjes van internet, geluid en batterij (het snelmenu, zoals in Windows 11), de klok,
// de bel en een smal strookje voor 'Bureaublad tonen'. Rechtermuisknop: op Start de snelle lijst (Win+X), op een lege
// plek Taakbeheer en Bureaublad tonen.
//
// Grootte (klein, normaal, groot) en waar de knoppen staan (links of in het midden): Instellingen > Uiterlijk >
// Taakbalk (root.taakbalkStijl).
import QtQuick
import QtQuick.Window

LaagVenster {
    id: paneel
    property var r                // Shell.qml (root): menu's, gegevens, kleuren
    property bool hoofd: false    // het hoofdscherm: daar staan het systeemvak en de bel
    soort: "paneel"
    meteen: true
    width: screen ? screen.width : 1280
    height: r.paneelHoogte
    color: r.donker ? Qt.rgba(0.086, 0.094, 0.114, 0.96) : Qt.rgba(0.965, 0.961, 0.961, 0.96)

    // Maten die met de grootte van de taakbalk meegaan.
    readonly property int knopMaat: height - 8
    readonly property int icoon: Math.round(knopMaat * 0.6)      // 24 px bij een gewone taakbalk (Windows 11)
    readonly property bool midden: r.taakbalkStijl.uitlijning === "midden"
    readonly property var status: r.trayStatus
    // Aanwijzen en 'open': een zacht grijs vlakje over de taakbalk heen (zoals Windows 11), geen harde kleur.
    readonly property color zweefKleur: r.donker ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(0, 0, 0, 0.05)
    readonly property color actiefVlak: r.donker ? Qt.rgba(1, 1, 1, 0.12) : Qt.rgba(0, 0, 0, 0.08)

    // x (vanaf links van het scherm) van een plek op de taakbalk: voor menu's.
    function plekVan(item, x) { return item.mapToItem(null, x, 0).x }

    Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: paneel.r.o.rand }

    // Rechtermuisknop op een lege plek van de taakbalk.
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.RightButton
        onClicked: mouse => paneel.r.paneelMenu(paneel.screen, mouse.x)
    }

    // ------------------------------------------------------------------------- Start en de takenlijst
    Row {
        id: links
        objectName: "links"
        // In het midden van het scherm (Windows 11), maar nooit over de knoppen rechts heen.
        x: paneel.midden ? Math.max(8, Math.min(Math.round((paneel.width - width) / 2), rechts.x - width - 8)) : 8
        anchors.verticalCenter: parent.verticalCenter
        spacing: 4
        Behavior on x { enabled: paneel.visible; NumberAnimation { duration: 150; easing.type: Easing.OutCubic } }

        PaneelKnop {
            id: startKnop
            objectName: "startKnop"
            naam: "Start"
            actief: paneel.r.open === "start" && paneel.r.menuScherm === paneel.screen
            o: paneel.r.o
            zweef: paneel.zweefKleur
            vol: paneel.actiefVlak
            maat: paneel.knopMaat
            onGeklikt: paneel.r.toon("start", paneel.screen)
            Image {
                anchors.centerIn: parent
                width: paneel.icoon
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
            height: paneel.knopMaat
            source: "Takenlijst.qml"
            onLoaded: {
                item.knopMaat = Qt.binding(() => paneel.knopMaat)
                item.launchers = Qt.binding(() => paneel.r.launchers)
                item.zweefKleur = Qt.binding(() => paneel.zweefKleur)
                item.actiefVlak = Qt.binding(() => paneel.actiefVlak)
                item.actiefKleur = Qt.binding(() => paneel.r.o.accent)
                item.menuVraag.connect((regels, x, terug) => paneel.r.toonMenu(paneel.screen, paneel.plekVan(item, x),
                                                                                 -1, regels, terug))
                item.vastzetten.connect((url, aan) => paneel.r.zetVast(url, aan))
            }
            onStatusChanged: if (status === Loader.Error)
                console.warn("BugOS-schil: geen takenlijst (org.kde.taskmanager ontbreekt)")
        }
    }

    // ------------------------------------------------------------------------- rechts
    Row {
        id: rechts
        objectName: "rechts"
        anchors.right: parent.right
        height: parent.height
        spacing: 2

        // Het systeemvak: de pictogrammen van apps (Steam, Discord, ...). Alleen op het hoofdscherm.
        Row {
            id: vak
            objectName: "systeemvak"
            visible: paneel.hoofd
            anchors.verticalCenter: parent.verticalCenter
            spacing: 0
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
                    zweef: paneel.zweefKleur
            vol: paneel.actiefVlak
                    maat: paneel.knopMaat
                    breedte: Math.round(paneel.knopMaat * 0.75)
                    Image {
                        anchors.centerIn: parent
                        width: 16; height: 16
                        sourceSize.width: 32; sourceSize.height: 32
                        source: vakKnop.icoon
                    }
                    Rectangle {   // de app vraagt aandacht
                        visible: vakKnop.status === "NeedsAttention"
                        width: 6; height: 6; radius: 3
                        anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 6
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

        // Het snelmenu: één knop met de icoontjes van internet, geluid en (op een laptop) de batterij.
        PaneelKnop {
            id: snelKnop
            objectName: "snelKnop"
            anchors.verticalCenter: parent.verticalCenter
            naam: paneel.r.tr("Snelmenu", "Quick menu") + (statusTekst !== "" ? ": " + statusTekst : "")
            actief: paneel.r.open === "snel" && paneel.r.menuScherm === paneel.screen
            o: paneel.r.o
            zweef: paneel.zweefKleur
            vol: paneel.actiefVlak
            maat: paneel.knopMaat
            breedte: icoontjes.implicitWidth + 20
            onGeklikt: paneel.r.toon("snel", paneel.screen)
            // Scrollen op de knop: het volume harder of zachter (zoals Windows).
            WheelHandler {
                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                onWheel: event => {
                    const v = paneel.status.volume
                    if (typeof v !== "number")
                        return
                    const nieuw = Math.max(0, Math.min(100, v + (event.angleDelta.y > 0 ? 5 : -5)))
                    paneel.r.trayStatus = Object.assign({}, paneel.status, { volume: nieuw })
                    paneel.r.startData(["--zet", "volume", String(nieuw)], "snel")
                }
            }
            readonly property string internetIcoon: {
                const s = paneel.status
                if (s.internet === "kabel") return "network-wired-activated"
                if (s.internet === "wifi") return "network-wireless"
                if (s.internet === "geen") return s.wifi === true ? "network-wireless-disconnected" : "network-offline"
                return s.wifi === true ? "network-wireless" : "network-wired"
            }
            readonly property string geluidIcoon: {
                const v = paneel.status.volume
                if (typeof v !== "number") return ""
                if (paneel.status.stil === true || v === 0) return "audio-volume-muted"
                return v < 34 ? "audio-volume-low" : v < 67 ? "audio-volume-medium" : "audio-volume-high"
            }
            readonly property string batterijIcoon: {
                const b = paneel.status.batterij
                if (typeof b !== "number") return ""
                const stap = Math.max(0, Math.min(100, Math.round(b / 20) * 20))
                return "battery-" + ("00" + stap).slice(-3) + (paneel.status.laadt === true ? "-charging" : "")
            }
            readonly property string statusTekst: {
                const s = paneel.status, delen = []
                if (s.internet === "kabel") delen.push(paneel.r.tr("internet via de kabel", "internet over cable"))
                else if (s.internet === "wifi") delen.push(paneel.r.tr("internet via wifi", "internet over Wi-Fi"))
                else if (s.internet === "geen") delen.push(paneel.r.tr("geen internet", "no internet"))
                if (typeof s.volume === "number")
                    delen.push(s.stil === true ? paneel.r.tr("geluid uit", "muted") : paneel.r.tr("volume ", "volume ") + s.volume + "%")
                if (typeof s.batterij === "number")
                    delen.push(paneel.r.tr("batterij ", "battery ") + s.batterij + "%")
                return delen.join(", ")
            }
            Row {
                id: icoontjes
                anchors.centerIn: parent
                spacing: 10
                Repeater {
                    model: [snelKnop.internetIcoon, snelKnop.geluidIcoon, snelKnop.batterijIcoon].filter(n => n !== "")
                    Image {
                        required property string modelData
                        width: 16; height: 16
                        sourceSize.width: 32; sourceSize.height: 32
                        source: "image://icon/" + modelData
                    }
                }
            }
        }

        PaneelKnop {
            id: klok
            objectName: "klok"
            anchors.verticalCenter: parent.verticalCenter
            naam: tijd.text + " " + datum.text
            actief: paneel.r.open === "kalender" && paneel.r.menuScherm === paneel.screen
            o: paneel.r.o
            zweef: paneel.zweefKleur
            vol: paneel.actiefVlak
            maat: paneel.knopMaat
            breedte: Math.max(tijd.implicitWidth, datum.implicitWidth) + 20
            onGeklikt: paneel.r.toon("kalender", paneel.screen)
            property date nu: new Date()
            Timer { interval: 1000; repeat: true; running: true; triggeredOnStart: true; onTriggered: klok.nu = new Date() }
            Column {
                anchors.centerIn: parent
                spacing: 1
                Text { id: tijd; anchors.right: parent.right; text: Qt.formatTime(klok.nu, "HH:mm"); color: paneel.r.o.tekst; font.pixelSize: Math.round(12 * paneel.r.schaal) }
                Text { id: datum; anchors.right: parent.right; text: Qt.formatDate(klok.nu, "dd-MM-yyyy"); color: paneel.r.o.tekst; font.pixelSize: Math.round(12 * paneel.r.schaal) }
            }
        }

        // De bel: het meldingencentrum (alleen op het hoofdscherm), met het aantal nieuwe meldingen.
        PaneelKnop {
            id: belKnop
            objectName: "belKnop"
            anchors.verticalCenter: parent.verticalCenter
            visible: paneel.hoofd
            naam: meldingen.ongelezen > 0
                  ? paneel.r.tr(meldingen.ongelezen + " nieuwe meldingen", meldingen.ongelezen + " new notifications")
                  : paneel.r.tr("Meldingen", "Notifications")
            actief: paneel.r.open === "meldingen"
            o: paneel.r.o
            zweef: paneel.zweefKleur
            vol: paneel.actiefVlak
            maat: paneel.knopMaat
            breedte: Math.round(paneel.knopMaat * 0.9)
            onGeklikt: paneel.r.toon("meldingen", paneel.screen)
            // Een belletje van een paar vormen (geen pictogramthema nodig). Niet storen aan: doorgestreept.
            Item {
                anchors.centerIn: parent
                width: 16; height: 17
                Rectangle { x: 2.5; y: 1.5; width: 11; height: 11; radius: 5.5; color: "transparent"; border.width: 1.5; border.color: paneel.r.o.tekst }
                Rectangle { x: 1; y: 10; width: 14; height: 1.5; radius: 0.75; color: paneel.r.o.tekst }
                Rectangle { x: 6; y: 13.5; width: 4; height: 2.5; radius: 1.25; color: paneel.r.o.tekst }
                Rectangle {
                    visible: paneel.r.snelStatus.niet_storen === true
                    anchors.centerIn: parent
                    width: 20; height: 1.5; radius: 0.75; rotation: 45
                    color: paneel.r.o.tekst
                }
            }
            Rectangle {
                visible: meldingen.ongelezen > 0
                anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 3
                width: Math.max(16, teller.implicitWidth + 8); height: 16; radius: 8
                color: paneel.r.o.accent
                Text { id: teller; anchors.centerIn: parent; text: meldingen.ongelezen > 9 ? "9+" : meldingen.ongelezen; color: "white"; font.pixelSize: 10; font.bold: true }
            }
        }

        // Bureaublad tonen: het smalle strookje helemaal rechts, zoals in Windows.
        Rectangle {
            id: bureaubladKnop
            objectName: "bureaubladTonen"
            height: parent.height
            width: 10
            color: bureaubladMuis.containsMouse ? paneel.zweefKleur : "transparent"
            Rectangle { anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; width: 1; height: parent.height * 0.4; color: paneel.r.o.rand }
            Accessible.role: Accessible.Button
            Accessible.name: paneel.r.tr("Bureaublad tonen", "Show desktop")
            MouseArea { id: bureaubladMuis; anchors.fill: parent; hoverEnabled: true; onClicked: paneel.r.bureaubladWissel() }
        }
    }
}
