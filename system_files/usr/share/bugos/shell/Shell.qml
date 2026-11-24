// BugOS-schil (bugos-shell): taakbalk, startmenu, snelmenu, klok met kalender, achtergrond en meldingen, zonder Plasma.
// Zie docs/STANDALONE.md (fase 1). Het startmenu en het snelmenu zijn dezelfde StartMenu.qml en QuickMenu.qml als in de
// Plasma-versie; alleen de lijm eromheen is nieuw. Gegevens komen, net als daar, van bugos-start-data.
//
// Van bugos-shell (C++) krijgt deze QML:
//   opdracht   voerUit([argv], sleutel) -> klaar(sleutel, code, uitvoer), start([argv]): zonder shell, dus veilig
//   schil      laag(venster, soort, marge), heeftLagen(), en de signalen startmenu() (Meta-toets) en bureaublad()
//   meldingen  lijst (de kaartjes), sluit(id), actie(id, sleutel): de meldingendienst org.freedesktop.Notifications
//   achtergrondMap  de map met images/ en images_dark/ (de BugOS-achtergrond)
import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
import QtCore
import "../../plasma/plasmoids/org.bugos.startmenu/contents/ui" as SM
import "../../plasma/plasmoids/org.bugos.quickmenu/contents/ui" as QM

// Houder (een QtObject) en geen Item: vensters in een Item worden niet zelf getoond.
Houder {
    id: root

    readonly property bool nederlands: Qt.locale().name.indexOf("nl") === 0
    function tr(nl, en) { return nederlands ? nl : en }
    // Licht of donker volgt het palet van het systeem (bugos-theme zet dat; Qt werkt het meteen bij).
    readonly property SystemPalette systeemPalet: SystemPalette {}
    readonly property bool donker: systeemPalet.window.hslLightness < 0.5
    readonly property SM.Design o: SM.Design { donker: root.donker }
    readonly property real schaal: Qt.application.font.pointSize > 0
        ? Math.min(1.5, Math.max(1, Qt.application.font.pointSize / 10)) : 1
    readonly property int paneelHoogte: Math.round(48 * schaal)

    // ------------------------------------------------------------------------------------- gegevens
    property var gegevens: ({ apps: [], favorieten: [], recent: [], gebruiker: { naam: "" }, taakbalk_kan: false })
    property var snelStatus: ({})
    property string browser: ""
    readonly property var launchers: {
        const lijst = ["applications:bugos-files.desktop"]
        if (browser !== "")
            lijst.push("applications:" + browser + ".desktop")
        lijst.push("applications:bugos-store.desktop", "applications:bugos-settings.desktop")
        return lijst
    }

    Connections {
        target: opdracht
        function onKlaar(sleutel, code, uitvoer) {
            if (code !== 0 || uitvoer === "")
                return
            try {
                if (sleutel === "gegevens") {
                    const g = JSON.parse(uitvoer)
                    // 'Vastmaken aan taakbalk' komt in fase 2 (de vastgezette apps van de schil zelf).
                    g.taakbalk_kan = false
                    root.gegevens = g
                } else if (sleutel === "snel") {
                    root.snelStatus = JSON.parse(uitvoer)
                }
            } catch (e) {
                console.warn("BugOS-schil:", sleutel, e)
            }
        }
    }
    function startData(args, sleutel) { opdracht.voerUit(["bugos-start-data"].concat(args), sleutel || "") }

    function leesBrowser() {
        // De browser die je in Welkom koos (bugos-browser): ~/.config/bugos/browser.
        const pad = StandardPaths.writableLocation(StandardPaths.GenericConfigLocation) + "/bugos/browser"
        const xhr = new XMLHttpRequest()
        xhr.onreadystatechange = () => {
            if (xhr.readyState === XMLHttpRequest.DONE) {
                const id = (xhr.responseText || "").split("\n")[0].trim()
                root.browser = /^[A-Za-z_][A-Za-z0-9_-]*(\.[A-Za-z0-9_-]+)+$/.test(id) ? id : "org.mozilla.firefox"
            }
        }
        xhr.open("GET", pad)
        xhr.send()
    }

    Component.onCompleted: {
        startData([], "gegevens")
        leesBrowser()
    }

    // ------------------------------------------------------------------------------------- menu's open en dicht
    property string open: ""   // "start", "snel", "kalender" of ""
    function toon(wat) {
        open = (open === wat) ? "" : wat
        if (open === "start") {
            startData([], "gegevens")
            startMenu.terugNaarBegin()
        } else if (open === "snel") {
            startData(["--snel"], "snel")
        }
    }
    function sluitAlles() { open = "" }

    Connections {
        target: schil
        function onStartmenu() { root.toon("start") }
    }
    Timer {   // het snelmenu bijwerken zolang het open is (zoals in Plasma)
        interval: 5000; repeat: true; running: root.open === "snel"
        onTriggered: root.startData(["--snel"], "snel")
    }

    // ------------------------------------------------------------------------------------- achtergrond
    LaagVenster {
        id: achtergrond
        soort: "achtergrond"
        meteen: true
        width: Screen.width
        height: Screen.height
        color: root.donker ? "#111216" : "#F6F5F5"
        Image {
            anchors.fill: parent
            source: "file://" + achtergrondMap + "/" + (root.donker ? "images_dark" : "images") + "/3840x2160.jpg"
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            sourceSize.width: Screen.width
        }
    }

    // ------------------------------------------------------------------------------------- vangnet
    // Een klik naast een open menu sluit het (een doorzichtige laag eronder, over het hele scherm).
    LaagVenster {
        id: vangnet
        soort: "vangnet"
        width: Screen.width
        height: Screen.height
        color: "#01000000"
        visible: root.open !== ""
        MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onPressed: root.sluitAlles() }
    }

    // ------------------------------------------------------------------------------------- de taakbalk
    LaagVenster {
        id: paneel
        objectName: "paneel"
        soort: "paneel"
        meteen: true
        width: Screen.width
        height: root.paneelHoogte
        color: root.donker ? Qt.rgba(0.11, 0.12, 0.14, 0.92) : Qt.rgba(1, 1, 1, 0.92)

        Rectangle { anchors.top: parent.top; width: parent.width; height: 1; color: root.o.rand }

        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 8
            anchors.rightMargin: 8
            spacing: 4

            PaneelKnop {
                id: startKnop
                objectName: "startKnop"
                naam: "Start"
                actief: root.open === "start"
                o: root.o
                maat: root.paneelHoogte - 8
                onGeklikt: root.toon("start")
                Image {
                    anchors.centerIn: parent
                    width: Math.round(parent.width * 0.7)
                    height: width
                    sourceSize.width: width * 2
                    sourceSize.height: height * 2
                    source: "image://icon/bugos-logo"
                }
            }

            Loader {
                id: takenlijst
                objectName: "takenlijst"
                Layout.fillHeight: true
                Layout.alignment: Qt.AlignVCenter
                source: "Takenlijst.qml"
                onLoaded: {
                    item.knopMaat = Qt.binding(() => root.paneelHoogte - 8)
                    item.launchers = Qt.binding(() => root.launchers)
                    item.zweefKleur = Qt.binding(() => root.o.knopHover)
                    item.actiefKleur = Qt.binding(() => root.o.accent)
                }
                onStatusChanged: if (status === Loader.Error)
                    console.warn("BugOS-schil: geen takenlijst (org.kde.taskmanager ontbreekt)")
            }

            Item { Layout.fillWidth: true }

            PaneelKnop {
                id: snelKnop
                objectName: "snelKnop"
                naam: root.tr("Snelmenu", "Quick menu")
                actief: root.open === "snel"
                o: root.o
                maat: root.paneelHoogte - 8
                onGeklikt: root.toon("snel")
                // Twee schuifjes (zoals het snelmenu-pictogram in de Plasma-versie).
                Column {
                    anchors.centerIn: parent
                    spacing: 5
                    Repeater {
                        model: [0.35, 0.65]
                        Item {
                            width: 18; height: 4
                            Rectangle { anchors.verticalCenter: parent.verticalCenter; width: parent.width; height: 2; radius: 1; color: root.o.tekst }
                            Rectangle { x: parent.width * modelData - 3; anchors.verticalCenter: parent.verticalCenter; width: 6; height: 6; radius: 3; color: root.o.tekst }
                        }
                    }
                }
            }

            PaneelKnop {
                id: klok
                objectName: "klok"
                naam: tijd.text + " " + datum.text
                actief: root.open === "kalender"
                o: root.o
                maat: root.paneelHoogte - 8
                breedte: Math.max(tijd.implicitWidth, datum.implicitWidth) + 20
                onGeklikt: root.toon("kalender")
                property date nu: new Date()
                Timer { interval: 1000; repeat: true; running: true; triggeredOnStart: true; onTriggered: klok.nu = new Date() }
                Column {
                    anchors.centerIn: parent
                    Text { id: tijd; anchors.right: parent.right; text: Qt.formatTime(klok.nu, "HH:mm"); color: root.o.tekst; font.pixelSize: Math.round(12 * root.schaal) }
                    Text { id: datum; anchors.right: parent.right; text: Qt.formatDate(klok.nu, "dd-MM-yyyy"); color: root.o.tekst; font.pixelSize: Math.round(12 * root.schaal) }
                }
            }
        }
    }

    // ------------------------------------------------------------------------------------- startmenu
    LaagVenster {
        id: startVenster
        objectName: "startVenster"
        soort: "links"
        marge: 8
        width: startMenu.implicitWidth
        height: startMenu.implicitHeight
        visible: root.open === "start"
        onVisibleChanged: if (visible) requestActivate()

        SM.StartMenu {
            id: startMenu
            anchors.fill: parent
            schaal: root.schaal
            maxHoogte: Screen.height > 0 ? Math.max(420, Math.min(720, Screen.height - root.paneelHoogte - 72)) : 680
            gegevens: root.gegevens
            nederlands: root.nederlands
            radius: 12
            border.color: root.o.rand
            onStart: pad => { root.startData(["--start", pad]); root.sluitAlles() }
            onOpenBestand: pad => { root.startData(["--open", pad]); root.sluitAlles() }
            onAanUit: actie => { root.startData(["--aan-uit", actie]); root.sluitAlles() }
            onAppActie: (pad, actie) => root.startData(["--actie", pad, actie])
            onVastzetten: (id, aan) => root.startData([aan ? "--vastzetten" : "--losmaken", id], "gegevens")
            onVerwijderApp: flatpak => root.startData(["--verwijder", flatpak])
            onQuarantaine: pad => root.startData(["--quarantaine", pad])
            onSluiten: root.sluitAlles()
        }
        Shortcut { sequence: "Escape"; onActivated: root.sluitAlles() }
    }

    // ------------------------------------------------------------------------------------- snelmenu
    LaagVenster {
        id: snelVenster
        objectName: "snelVenster"
        soort: "rechts"
        marge: 8
        width: Math.round(snelMenu.implicitWidth)
        height: Math.round(snelMenu.implicitHeight)
        visible: root.open === "snel"
        onVisibleChanged: if (visible) requestActivate()

        QM.QuickMenu {
            id: snelMenu
            anchors.fill: parent
            schaal: root.schaal
            status: root.snelStatus
            nederlands: root.nederlands
            radius: 12
            border.color: root.o.rand
            onZet: (wat, waarde) => root.startData(["--zet", wat, waarde], "snel")
            onOpen: wat => {
                root.startData(["--start", "instelling:" + (wat === "instellingen" ? "start" : wat)])
                root.sluitAlles()
            }
        }
        Shortcut { sequence: "Escape"; onActivated: root.sluitAlles() }
    }

    // ------------------------------------------------------------------------------------- kalender
    LaagVenster {
        id: kalenderVenster
        objectName: "kalenderVenster"
        soort: "rechts"
        marge: 8
        width: 340
        height: kalender.implicitHeight + 32
        visible: root.open === "kalender"
        onVisibleChanged: if (visible) { kalender.maand = new Date().getMonth(); kalender.jaar = new Date().getFullYear() }

        Rectangle {
            anchors.fill: parent
            radius: 12
            color: root.o.vlak
            border.color: root.o.rand
            ColumnLayout {
                id: kalender
                property int maand: new Date().getMonth()
                property int jaar: new Date().getFullYear()
                anchors.fill: parent
                anchors.margins: 16
                spacing: 8
                RowLayout {
                    Text {
                        Layout.fillWidth: true
                        text: Qt.locale().standaloneMonthName(kalender.maand) + " " + kalender.jaar
                        color: root.o.tekst
                        font.pixelSize: 16
                        font.bold: true
                    }
                    PaneelKnop {
                        naam: root.tr("Vorige maand", "Previous month"); o: root.o; maat: 30
                        onGeklikt: { if (kalender.maand === 0) { kalender.maand = 11; kalender.jaar-- } else kalender.maand-- }
                        Text { anchors.centerIn: parent; text: "‹"; color: root.o.tekst; font.pixelSize: 18 }
                    }
                    PaneelKnop {
                        naam: root.tr("Volgende maand", "Next month"); o: root.o; maat: 30
                        onGeklikt: { if (kalender.maand === 11) { kalender.maand = 0; kalender.jaar++ } else kalender.maand++ }
                        Text { anchors.centerIn: parent; text: "›"; color: root.o.tekst; font.pixelSize: 18 }
                    }
                }
                DayOfWeekRow {
                    Layout.fillWidth: true
                    locale: Qt.locale()
                    delegate: Text { text: shortName; color: root.o.tekst2; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 12 }
                }
                MonthGrid {
                    id: maandRooster
                    Layout.fillWidth: true
                    month: kalender.maand
                    year: kalender.jaar
                    locale: Qt.locale()
                    delegate: Rectangle {
                        required property var model
                        implicitWidth: 38
                        implicitHeight: 34
                        radius: 17
                        color: model.today ? root.o.accent : "transparent"
                        Text {
                            anchors.centerIn: parent
                            text: model.day
                            color: model.today ? "white" : (model.month === kalender.maand ? root.o.tekst : root.o.tekst3)
                            font.pixelSize: 13
                        }
                    }
                }
            }
        }
        Shortcut { sequence: "Escape"; onActivated: root.sluitAlles() }
    }

    // ------------------------------------------------------------------------------------- meldingen
    LaagVenster {
        id: meldingVenster
        objectName: "meldingVenster"
        soort: "melding"
        marge: 12
        width: 380
        height: Math.max(1, kaartjes.implicitHeight)
        visible: meldingen.lijst.length > 0

        Column {
            id: kaartjes
            width: parent.width
            spacing: 8
            Repeater {
                model: meldingen.lijst
                delegate: Melding {
                    width: kaartjes.width
                    melding: modelData
                    o: root.o
                    onDicht: meldingen.sluit(modelData.id)
                    onActie: sleutel => meldingen.actie(modelData.id, sleutel)
                }
            }
        }
    }
}
