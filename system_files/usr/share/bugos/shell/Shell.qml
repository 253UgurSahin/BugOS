// BugOS-schil (bugos-shell): taakbalk, startmenu, snelmenu, systeemvak, klok met kalender, bureaublad en meldingen,
// zonder Plasma. Zie docs/STANDALONE.md (fase 1 en 2). Het startmenu en het snelmenu zijn dezelfde StartMenu.qml en
// QuickMenu.qml als in de Plasma-versie; alleen de lijm eromheen is nieuw. Gegevens komen van bugos-start-data.
//
// Van bugos-shell (C++) krijgt deze QML:
//   opdracht      voerUit([argv], sleutel) -> klaar(sleutel, code, uitvoer), start([argv]): zonder shell, dus veilig
//   schil         laag(venster, soort, marge), plaats(venster, x, y), heeftLagen(), bureaubladTonen(aan),
//                 en de signalen startmenu() (Meta-toets) en bureaublad()
//   meldingen     lijst (de kaartjes), sluit(id), actie(id, sleutel): de meldingendienst org.freedesktop.Notifications
//   instellingen  lees(naam), bewaar(naam, tekst), veranderd(naam), achtergrondBeeld(donker), bureaubladMap
//   systeemvak    een lijst (titel, icoon, status, uitleg, heeftMenu) met activeer/menu/menuKlik/contextMenu/...
//
// Per scherm een taakbalk en een bureaublad (Instantiator over Qt.application.screens). De menu's gaan open op het
// scherm waar je klikte (menuScherm); de Meta-toets opent het startmenu op het hoofdscherm.
import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts
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
    readonly property var hoofdScherm: Qt.application.screens.length > 0 ? Qt.application.screens[0] : null
    property var hoofdPaneel: null       // de taakbalk van het hoofdscherm (voor de test)
    readonly property int aantalPanelen: panelen.count
    readonly property int aantalBureaubladen: bureaubladen.count

    // ------------------------------------------------------------------------------------- instellingen
    property string browser: ""
    property var vastgezet: null         // de vastgezette apps (~/.config/bugos/taakbalk), null: de standaard
    property string achtergrondBeeld: instellingen.achtergrondBeeld(donker)
    onDonkerChanged: achtergrondBeeld = instellingen.achtergrondBeeld(donker)

    readonly property var launchers: {
        if (vastgezet !== null)
            return vastgezet
        const lijst = ["applications:bugos-files.desktop"]
        if (browser !== "")
            lijst.push("applications:" + browser + ".desktop")
        lijst.push("applications:bugos-store.desktop", "applications:bugos-settings.desktop")
        return lijst
    }
    readonly property var appIdVorm: /^[A-Za-z_][A-Za-z0-9_-]*(\.[A-Za-z0-9_-]+)+$/

    function leesInstellingen() {
        const id = instellingen.lees("browser").split("\n")[0].trim()
        browser = appIdVorm.test(id) ? id : "org.mozilla.firefox"
        const tekst = instellingen.lees("taakbalk")
        let lijst = null
        try {
            const l = tekst !== "" ? JSON.parse(tekst) : null
            if (Array.isArray(l))
                lijst = l.filter(x => typeof x === "string" && /^applications:[A-Za-z0-9_.+-]+\.desktop$/.test(x))
        } catch (e) {
            console.warn("BugOS-schil: taakbalk-instelling onleesbaar", e)
        }
        vastgezet = lijst
        achtergrondBeeld = instellingen.achtergrondBeeld(donker)
    }
    Connections {
        target: instellingen
        function onVeranderd(naam) {
            if (naam === "browser" || naam === "taakbalk" || naam === "achtergrond")
                root.leesInstellingen()
        }
    }

    // Vastmaken aan / losmaken van de taakbalk (startmenu en rechtermuisknop op een app).
    function zetVast(url, aan) {
        const lijst = launchers.slice()
        const i = lijst.indexOf(url)
        if (aan && i < 0)
            lijst.push(url)
        else if (!aan && i >= 0)
            lijst.splice(i, 1)
        else
            return
        vastgezet = lijst
        instellingen.bewaar("taakbalk", JSON.stringify(lijst))
        gegevens = metTaakbalk(gegevens)
    }
    // In de gegevens van het startmenu: welke apps op de taakbalk staan (dan zegt het menu 'Losmaken van taakbalk').
    function metTaakbalk(g) {
        const kopie = Object.assign({}, g)
        kopie.taakbalk_kan = true
        const op = a => Object.assign({}, a, { op_taakbalk: launchers.indexOf("applications:" + a.id) >= 0 })
        kopie.apps = (g.apps || []).map(op)
        kopie.favorieten = (g.favorieten || []).map(op)
        return kopie
    }

    // ------------------------------------------------------------------------------------- gegevens
    property var gegevens: ({ apps: [], favorieten: [], recent: [], gebruiker: { naam: "" }, taakbalk_kan: false })
    property var snelStatus: ({})

    Connections {
        target: opdracht
        function onKlaar(sleutel, code, uitvoer) {
            if (code !== 0 || uitvoer === "")
                return
            try {
                if (sleutel === "gegevens")
                    root.gegevens = root.metTaakbalk(JSON.parse(uitvoer))
                else if (sleutel === "snel")
                    root.snelStatus = JSON.parse(uitvoer)
            } catch (e) {
                console.warn("BugOS-schil:", sleutel, e)
            }
        }
    }
    function startData(args, sleutel) { opdracht.voerUit(["bugos-start-data"].concat(args), sleutel || "") }

    Component.onCompleted: {
        leesInstellingen()
        startData([], "gegevens")
    }

    // ------------------------------------------------------------------------------------- menu's open en dicht
    property string open: ""        // "start", "snel", "kalender", "menu" of ""
    property var menuScherm: hoofdScherm
    function toon(wat, scherm) {
        const zelfde = open === wat && (!scherm || scherm === menuScherm)
        sluitAlles()
        if (zelfde)
            return
        menuScherm = scherm || hoofdScherm
        open = wat
        if (wat === "start") {
            startData([], "gegevens")
            startMenu.terugNaarBegin()
        } else if (wat === "snel") {
            startData(["--snel"], "snel")
        }
    }
    function sluitAlles() {
        open = ""
        losMenu.sluit()
    }

    // Een los menu: x vanaf links van het scherm; y = -1: net boven de taakbalk.
    function toonMenu(scherm, x, y, regels, terug) {
        sluitAlles()
        menuScherm = scherm || hoofdScherm
        open = "menu"
        losMenu.openOp(menuScherm, x, y < 0 ? 100000 : y, regels, terug)
    }

    function startApp(desktop) { startData(["--start", "/usr/share/applications/" + desktop]) }
    function instelling(pagina) { startData(["--start", "instelling:" + pagina]) }

    // Rechtermuisknop op Start: de snelle lijst van Windows (Win+X).
    function startKnopMenu(scherm, x) {
        toonMenu(scherm, x, -1, [
            { tekst: tr("Taakbeheer", "Task Manager"), icoon: "bugos-task-manager", doe: () => startApp("bugos-task-manager.desktop") },
            { tekst: tr("Instellingen", "Settings"), icoon: "bugos-settings", doe: () => startApp("bugos-settings.desktop") },
            { tekst: tr("Bestanden", "Files"), icoon: "bugos-files", doe: () => startApp("bugos-files.desktop") },
            { tekst: tr("Terminal", "Terminal"), icoon: "utilities-terminal", doe: () => startApp("org.kde.konsole.desktop") },
            { tekst: tr("Er werkt iets niet", "Something is not working"), icoon: "bugos-help", doe: () => startApp("bugos-help.desktop") },
            { scheiding: true },
            { tekst: tr("Vergrendelen", "Lock"), icoon: "system-lock-screen", doe: () => startData(["--aan-uit", "slot"]) },
            { tekst: tr("Afmelden", "Sign out"), icoon: "system-log-out", doe: () => startData(["--aan-uit", "uitloggen"]) },
            { tekst: tr("Opnieuw opstarten", "Restart"), icoon: "system-reboot", doe: () => startData(["--aan-uit", "herstarten"]) },
            { tekst: tr("Uitzetten", "Shut down"), icoon: "system-shutdown", doe: () => startData(["--aan-uit", "uitzetten"]) }
        ], r => r.doe())
    }
    // Rechtermuisknop op een lege plek van de taakbalk.
    function paneelMenu(scherm, x) {
        toonMenu(scherm, x, -1, [
            { tekst: tr("Taakbeheer", "Task Manager"), icoon: "bugos-task-manager", doe: () => startApp("bugos-task-manager.desktop") },
            { tekst: tr("Bureaublad tonen", "Show desktop"), icoon: "user-desktop", doe: () => bureaubladWissel() },
            { scheiding: true },
            { tekst: tr("Instellingen voor de taakbalk", "Taskbar settings"), icoon: "configure", doe: () => instelling("uiterlijk") }
        ], r => r.doe())
    }
    // Rechtermuisknop op een pictogram in het systeemvak (of links, als de app alleen een menu heeft).
    function vakMenu(scherm, x, rij) {
        const regels = systeemvak.menu(rij)
        if (regels.length === 0) {
            // Geen menu via D-Bus: de app tekent zijn eigen menu.
            systeemvak.contextMenu(rij, x, (scherm ? scherm.height : 800) - paneelHoogte)
            return
        }
        toonMenu(scherm, x, -1, regels, r => systeemvak.menuKlik(rij, r.id))
    }
    // Rechtermuisknop op het bureaublad (pad leeg) of op een bestand erop.
    function bureaubladMenu(scherm, x, y, pad) {
        if (pad === "") {
            toonMenu(scherm, x, y, [
                { tekst: tr("Achtergrond wijzigen", "Change background"), icoon: "preferences-desktop-wallpaper", doe: () => instelling("uiterlijk") },
                { tekst: tr("Beeldscherm", "Display"), icoon: "video-display", doe: () => instelling("scherm") },
                { scheiding: true },
                { tekst: tr("Bureaubladmap openen", "Open desktop folder"), icoon: "folder", doe: () => opdracht.start(["bugos-files", instellingen.bureaubladMap]) }
            ], r => r.doe())
            return
        }
        const klein = pad.toLowerCase()
        const programma = [".exe", ".msi", ".appimage", ".desktop"].some(e => klein.endsWith(e))
        const regels = [{ tekst: tr("Openen", "Open"), icoon: "document-open", doe: () => openBestand(pad) }]
        if (programma)
            regels.push({ tekst: tr("Openen in quarantaine", "Open in quarantine"), icoon: "security-medium",
                          doe: () => opdracht.start(["bugos-quarantaine", "--venster", pad]) })
        regels.push({ tekst: tr("Tonen in Bestanden", "Show in Files"), icoon: "folder-open",
                      doe: () => opdracht.start(["bugos-files", pad.substring(0, pad.lastIndexOf("/"))]) })
        regels.push({ scheiding: true })
        regels.push({ tekst: tr("Weggooien", "Delete"), icoon: "edit-delete", doe: () => opdracht.start(["gio", "trash", pad]) })
        toonMenu(scherm, x, y, regels, r => r.doe())
    }
    // Dubbelklik op het bureaublad: een starter start de app, de rest opent met de standaard-app.
    function openBestand(pad) {
        startData([pad.endsWith(".desktop") ? "--start" : "--open", pad])
    }

    property bool bureaubladGetoond: false
    function bureaubladWissel() {
        bureaubladGetoond = !bureaubladGetoond
        schil.bureaubladTonen(bureaubladGetoond)
    }

    Connections {
        target: schil
        function onStartmenu() { root.toon("start", root.hoofdScherm) }
        function onBureaublad(tonen) { root.bureaubladGetoond = tonen }
    }
    Timer {   // het snelmenu bijwerken zolang het open is (zoals in Plasma)
        interval: 5000; repeat: true; running: root.open === "snel"
        onTriggered: root.startData(["--snel"], "snel")
    }

    // ------------------------------------------------------------------------------------- per scherm
    property Instantiator bureaubladen: Instantiator {
        model: Qt.application.screens
        delegate: Bureaublad {
            required property var modelData
            r: root
            screen: modelData
            hoofd: modelData === root.hoofdScherm
        }
    }

    // Een klik naast een open menu sluit het (een doorzichtige laag eronder, over het hele scherm van dat menu).
    property LaagVenster vangnet: LaagVenster {
        objectName: "vangnet"
        soort: "vangnet"
        screen: root.menuScherm
        width: screen ? screen.width : 1280
        height: screen ? screen.height : 800
        color: "#01000000"
        visible: root.open !== ""
        MouseArea { anchors.fill: parent; acceptedButtons: Qt.AllButtons; onPressed: root.sluitAlles() }
    }

    property Instantiator panelen: Instantiator {
        model: Qt.application.screens
        delegate: Paneel {
            required property var modelData
            r: root
            screen: modelData
            hoofd: modelData === root.hoofdScherm
            objectName: hoofd ? "paneel" : "paneel-extra"
            Component.onCompleted: if (hoofd) root.hoofdPaneel = this
        }
    }

    // ------------------------------------------------------------------------------------- los menu
    property MenuVenster losMenu: MenuVenster {
        objectName: "losMenu"
        o: root.o
        onderRand: root.paneelHoogte + 8
        onDicht: if (root.open === "menu") root.open = ""
    }

    // ------------------------------------------------------------------------------------- startmenu
    property LaagVenster startVenster: LaagVenster {
        objectName: "startVenster"
        soort: "links"
        marge: 8
        screen: root.menuScherm
        width: startMenu.implicitWidth
        height: startMenu.implicitHeight
        visible: root.open === "start"
        onVisibleChanged: if (visible) requestActivate()

        SM.StartMenu {
            id: startMenu
            anchors.fill: parent
            schaal: root.schaal
            maxHoogte: root.menuScherm && root.menuScherm.height > 0
                       ? Math.max(420, Math.min(720, root.menuScherm.height - root.paneelHoogte - 72)) : 680
            gegevens: root.gegevens
            nederlands: root.nederlands
            radius: 12
            border.color: root.o.rand
            onStart: pad => { root.startData(["--start", pad]); root.sluitAlles() }
            onOpenBestand: pad => { root.startData(["--open", pad]); root.sluitAlles() }
            onAanUit: actie => { root.startData(["--aan-uit", actie]); root.sluitAlles() }
            onAppActie: (pad, actie) => root.startData(["--actie", pad, actie])
            onVastzetten: (id, aan) => root.startData([aan ? "--vastzetten" : "--losmaken", id], "gegevens")
            onTaakbalk: (id, aan) => root.zetVast("applications:" + id, aan)
            onVerwijderApp: flatpak => root.startData(["--verwijder", flatpak])
            onQuarantaine: pad => root.startData(["--quarantaine", pad])
            onSluiten: root.sluitAlles()
        }
        Shortcut { sequence: "Escape"; onActivated: root.sluitAlles() }
    }

    // ------------------------------------------------------------------------------------- snelmenu
    property LaagVenster snelVenster: LaagVenster {
        objectName: "snelVenster"
        soort: "rechts"
        marge: 8
        screen: root.menuScherm
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
                root.instelling(wat === "instellingen" ? "start" : wat)
                root.sluitAlles()
            }
        }
        Shortcut { sequence: "Escape"; onActivated: root.sluitAlles() }
    }

    // ------------------------------------------------------------------------------------- kalender
    property LaagVenster kalenderVenster: LaagVenster {
        objectName: "kalenderVenster"
        soort: "rechts"
        marge: 8
        screen: root.menuScherm
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
                    delegate: Text { required property string shortName; text: shortName; color: root.o.tekst2; horizontalAlignment: Text.AlignHCenter; font.pixelSize: 12 }
                }
                MonthGrid {
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
                            text: parent.model.day
                            color: parent.model.today ? "white" : (parent.model.month === kalender.maand ? root.o.tekst : root.o.tekst3)
                            font.pixelSize: 13
                        }
                    }
                }
            }
        }
        Shortcut { sequence: "Escape"; onActivated: root.sluitAlles() }
    }

    // ------------------------------------------------------------------------------------- meldingen
    property LaagVenster meldingVenster: LaagVenster {
        objectName: "meldingVenster"
        soort: "melding"
        marge: 12
        screen: root.hoofdScherm
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
                    required property var modelData
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
