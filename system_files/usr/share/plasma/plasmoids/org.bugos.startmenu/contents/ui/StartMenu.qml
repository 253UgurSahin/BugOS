// BugOS startmenu - het menu zelf.
//
// Jip-en-Janneke: bovenaan een begroeting en een grote zoekbalk, daaronder je
// vastgezette apps en je laatst geopende bestanden. "Alle apps" laat alles
// zien, op onderwerp. Onderaan: jij, Instellingen en de aan/uit-knoppen.
//
// Dit bestand gebruikt alleen gewone QtQuick, zodat het ook buiten Plasma
// getest kan worden. main.qml koppelt het aan de taakbalk.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: menu
    // 'Grote letters' (KDE: 10 punten gewoon, 12 groot): de letters hier groeien mee (U067).
    // In Plasma zet main.qml dit via Kirigami.Theme (dat verandert meteen mee, Qt.application.font niet) (U084).
    property real schaal: Qt.application.font.pointSize > 0
        ? Math.min(1.5, Math.max(1, Qt.application.font.pointSize / 10)) : 1

    // Gegevens van bugos-start-data (apps, favorieten, recent, gebruiker).
    property var gegevens: ({ apps: [], favorieten: [], recent: [], gebruiker: { naam: "" } })
    property bool nederlands: true
    // Hoe een pictogram getekend wordt (in Plasma: Kirigami.Icon).
    property Component icoonTekenaar: Image {
        property string naam: ""
        source: naam === "" ? "" : (naam.indexOf("/") === 0 ? "file://" + naam : "image://icon/" + naam)
        sourceSize.width: width
        sourceSize.height: height
        fillMode: Image.PreserveAspectFit
    }

    signal start(string pad)
    signal openBestand(string pad)
    signal aanUit(string actie)
    signal sluiten()

    // Huisstijl
    readonly property bool donker: palette.window.hslLightness < 0.5
    readonly property Design o: Design { donker: menu.donker }   // zelfde kleuren en maten als de BugOS-apps
    readonly property color rood: o.accent
    readonly property color tekst: palette.windowText
    readonly property color tekst2: o.tekst2
    readonly property color vlak: o.knop          // knoppen, net als in de apps
    readonly property color zweef: o.knopHover    // aanwijzen
    readonly property color lijnkleur: o.rand
    readonly property string display: o.kopLetter

    readonly property bool alleApps: stapel.currentIndex === 1
    property string zoekTekst: zoeksleutel(zoekveld.text.trim())
    property string datumTekst: datum()

    function tr(nl, en) { return nederlands ? nl : en }
    // Kleine letters zonder accenten: 'izleyici' vindt 'İzleyici', 'cafe' vindt 'café' (zoals bugos-start-data) (U268)
    // Precies dezelfde regel als bugos-start-data (U280): NFKD, kleine letters, accenten weg, ß wordt ss, ς wordt σ
    function zoeksleutel(t) {
        return String(t).normalize("NFKD").toLowerCase().replace(/[\u0300-\u036f]/g, "").replace(/ß/g, "ss").replace(/ς/g, "σ")
    }
    function groet() {
        const uur = new Date().getHours()
        if (uur < 6) return tr("Goedenacht", "Good night")
        if (uur < 12) return tr("Goedemorgen", "Good morning")
        if (uur < 18) return tr("Goedemiddag", "Good afternoon")
        return tr("Goedenavond", "Good evening")
    }
    function voornaam() {
        const n = (gegevens.gebruiker && gegevens.gebruiker.naam) ? gegevens.gebruiker.naam : ""
        return n.split(" ")[0]
    }
    function datum() {
        return new Date().toLocaleDateString(Qt.locale(nederlands ? "nl_NL" : Qt.locale().name), "dddd d MMMM")
    }
    // Zoeken vindt apps én de pagina's van Instellingen (soort "instelling").
    // Beste eerst (Enter opent de eerste): de naam begint ermee, dan een woord in de naam, dan ergens in de naam,
    // dan alleen in de zoekwoorden. Bij gelijke stand eerst BugOS zelf en de pagina's van Instellingen (U098).
    function score(a, woorden) {
        const naam = zoeksleutel(a.naam).replace(/-/g, "")   // "Wi-Fi" telt als "wifi"
        const eerste = woorden[0].replace(/-/g, "")
        let s = naam.indexOf(zoekTekst.replace(/-/g, "")) === 0 ? 0
            : naam.split(/[\s\-()]+/).some(d => d.indexOf(eerste) === 0) ? 1
            : naam.indexOf(eerste) >= 0 ? 2 : 3
        const eigen = a.soort === "instelling" || String(a.id || "").indexOf("bugos-") === 0
        return s * 2 + (eigen ? 0 : 1)
    }
    function gevonden() {
        if (zoekTekst === "") return []
        const woorden = zoekTekst.split(/\s+/)
        return gegevens.apps.filter(a => woorden.every(w => (a.zoek || zoeksleutel(a.naam)).indexOf(w) >= 0))
            .map((a, i) => ({ a: a, s: score(a, woorden), i: i }))
            .sort((x, y) => x.s - y.s || x.i - y.i)
            .map(x => x.a)
    }
    // "Alle apps" laat alleen echte programma's zien.
    function alleAppsLijst() {
        return gegevens.apps.filter(a => a.soort !== "instelling").slice()
            .sort((a, b) => a.groep === b.groep ? a.naam.localeCompare(b.naam) : a.groep.localeCompare(b.groep))
    }
    // Typ je verder terwijl de lijst de focus heeft, dan gaat de tekst gewoon in het zoekveld.
    function naarZoekveld(e) {
        // Sneltoetsen (Ctrl+A, Alt+…) zijn geen zoektekst (U223)
        if (e.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))
            return
        if (e.key === Qt.Key_Backspace) {
            zoekveld.forceActiveFocus()
            zoekveld.text = zoekveld.text.slice(0, -1)
            e.accepted = true
        } else if (e.text.length > 0 && e.text.trim() !== "" && e.key !== Qt.Key_Return && e.key !== Qt.Key_Enter) {
            zoekveld.forceActiveFocus()
            zoekveld.text += e.text
            e.accepted = true
        }
    }
    function openEerste() {
        const lijst = gevonden()
        if (lijst.length > 0) { start(lijst[0].pad); sluiten() }
    }
    function terugNaarBegin() {
        zoekveld.text = ""
        stapel.currentIndex = 0
        datumTekst = datum()
        // Elke keer bovenaan beginnen: anders bleef de beginpagina gescrold staan en was de bovenste rij
        // vastgezette apps half weg ('LibreOffice Writer' afgeknipt) (A-05, VM-test).
        begin.contentY = 0
        alleLijst.positionViewAtBeginning()
        zoekveld.forceActiveFocus()
    }

    implicitWidth: 660
    // Hoogte van de pop-up (A-05/A-06, VM-test). Vroeger zo hoog als de beginpagina nodig had, met 420 als minimum.
    // In de VM werd de pop-up dan maar ~450 px: 'Recent geopend' viel onder de rand en 'Alle apps' liet ~3 regels zien.
    // Nu, zoals het startmenu van Windows 11, een vaste ruime hoogte die bij beginpagina, 'Alle apps' en zoeken
    // gelijk blijft (geen menu dat verspringt als je van pagina wisselt): vasteHoogte. Is de inhoud hoger (grote
    // letters), dan groeit hij mee, maar nooit hoger dan maxHoogte: main.qml zet die naar het scherm, zodat het
    // menu op 1280x800 boven de taakbalk past. Past het dan nog niet, dan scrolt de beginpagina (met een zichtbare
    // schuifbalk).
    property int maxHoogte: 680
    readonly property int vasteHoogte: 640
    implicitHeight: Math.min(maxHoogte, Math.max(vasteHoogte, gewensteHoogte))
    // Wat de beginpagina helemaal nodig heeft (vastgezet + recent), om te kunnen groeien bij grote letters.
    readonly property int gewensteHoogte: 22 * 2 + kopRij.implicitHeight + zoekveld.implicitHeight
        + beginKolom.implicitHeight + 1 + onderRij.implicitHeight + 16 * 4
    color: palette.window
    SystemPalette { id: palette; colorGroup: SystemPalette.Active }

    Keys.onEscapePressed: sluiten()
    // Typen zoekt altijd, waar de focus ook staat (zoals het startmenu van Windows) (U205).
    Keys.onPressed: event => menu.naarZoekveld(event)

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 22
        spacing: 16

        // --------------------------------------------------- begroeting ---
        RowLayout {
            id: kopRij
            Layout.fillWidth: true
            spacing: 12
            Label {
                text: menu.groet() + (menu.voornaam() ? ", " + menu.voornaam() : "")
                font.family: menu.display
                font.pixelSize: Math.round(o.letterKop * menu.schaal)   // compact, zoals Windows 11
                font.weight: Font.DemiBold
                color: menu.tekst
                Layout.fillWidth: true
                elide: Text.ElideRight
            }
            Label {
                text: menu.datumTekst
                color: menu.tekst2
                font.pixelSize: Math.round(12 * menu.schaal)
            }
        }

        // ----------------------------------------------------- zoekbalk ---
        TextField {
            id: zoekveld
            objectName: "zoekveld"
            Layout.fillWidth: true
            Layout.preferredHeight: Math.round(40 * menu.schaal)
            font.pixelSize: Math.round(14 * menu.schaal)
            leftPadding: 42
            color: menu.tekst
            placeholderText: menu.tr("Zoek een app of instelling…", "Search for an app or setting…")
            placeholderTextColor: menu.tekst2
            focus: true
            Accessible.name: placeholderText
            onAccepted: menu.openEerste()
            // Terug in het zoekveld: de markering weer op de eerste, die Enter opent (U349)
            onActiveFocusChanged: if (activeFocus && zoekLijst.count > 0) zoekLijst.currentIndex = 0
            Keys.onDownPressed: event => {
                if (zoekLijst.visible && zoekLijst.count > 0) { zoekLijst.currentIndex = 0; zoekLijst.forceActiveFocus() }
                else event.accepted = false
            }
            background: Rectangle {
                radius: menu.o.rKnop
                color: menu.o.vlak
                border.width: zoekveld.activeFocus ? 2 : 1
                border.color: zoekveld.activeFocus ? menu.rood : menu.lijnkleur
            }
            Loader {
                x: 14
                anchors.verticalCenter: parent.verticalCenter
                width: 18
                height: 18
                sourceComponent: menu.icoonTekenaar
                onLoaded: item.naam = "edit-find"
                opacity: 0.6
            }
        }

        // ------------------------------------------------- zoekresultaat ---
        ListView {
            id: zoekLijst
            objectName: "zoekLijst"
            visible: menu.zoekTekst !== ""
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 2
            model: menu.zoekTekst !== "" ? menu.gevonden() : []
            keyNavigationEnabled: true
            Keys.onPressed: event => {
                if (event.key === Qt.Key_Up && currentIndex <= 0) { zoekveld.forceActiveFocus(); event.accepted = true }
                else menu.naarZoekveld(event)
            }
            delegate: AppRegel {
                width: zoekLijst.width
                app: modelData
                gemarkeerd: ListView.isCurrentItem
            }
            // Meer treffers dan er passen ('LibreOffice': Writer stond onderaan buiten beeld): laat het zien (A-06).
            ScrollBar.vertical: ScrollBar { policy: zoekLijst.contentHeight > zoekLijst.height ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff }
            Label {
                anchors.centerIn: parent
                visible: zoekLijst.count === 0
                text: menu.tr("Niks gevonden. Probeer een ander woord.", "Nothing found. Try another word.")
                color: menu.tekst2
                font.pixelSize: Math.round(15 * menu.schaal)
            }
        }

        // -------------------------------------- begin / alle apps (stapel) ---
        StackLayout {
            id: stapel
            objectName: "stapel"
            visible: menu.zoekTekst === ""
            Layout.fillWidth: true
            Layout.fillHeight: true

            // Begin: vastgezet + recent (scrolt als het niet past, drukt nooit iets plat)
            Flickable {
                id: begin
                clip: true
                contentWidth: width
                contentHeight: beginKolom.implicitHeight
                boundsBehavior: Flickable.StopAtBounds
                // Altijd zichtbaar als er meer is dan past: 'AsNeeded' toont hem pas tijdens het scrollen, en dan zag
                // je niet dat er onder 'Vastgezet' nog 'Recent geopend' stond (A-05, VM-test).
                ScrollBar.vertical: ScrollBar { policy: begin.contentHeight > begin.height ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff }
                ColumnLayout {
                    id: beginKolom
                    width: begin.width
                    spacing: 10
                    RowLayout {
                        Layout.fillWidth: true
                        Kopje { text: menu.tr("Vastgezet", "Pinned"); Layout.fillWidth: true }
                        PilKnop {
                            tekst: menu.tr("Alle apps", "All apps")
                            pijl: "›"
                            // Daarna de focus op de lijst (niet op deze knop, die nu niet meer te zien is) (U204).
                            onGeklikt: { stapel.currentIndex = 1; alleLijst.currentIndex = 0; alleLijst.forceActiveFocus() }
                        }
                    }
                    GridLayout {
                        Layout.fillWidth: true
                        columns: 6   // zoals Windows 11: meer apps per rij, kleinere tegels
                        rowSpacing: 4
                        columnSpacing: 4
                        Repeater {
                            model: menu.gegevens.favorieten
                            delegate: AppTegel {
                                app: modelData
                                Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.minimumWidth: 0
                                Layout.minimumHeight: implicitHeight
                            }
                        }
                    }
                    Kopje {
                        text: menu.tr("Recent geopend", "Recently opened")
                        Layout.topMargin: 10
                        visible: menu.gegevens.recent.length > 0
                    }
                    GridLayout {
                        Layout.fillWidth: true
                        columns: 2
                        rowSpacing: 2
                        columnSpacing: 8
                        Repeater {
                            model: menu.gegevens.recent.slice(0, 6)
                            delegate: BestandRegel {
                                bestand: modelData
                                Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.minimumWidth: 0
                                Layout.minimumHeight: implicitHeight
                            }
                        }
                    }
                }
            }

            // Alle apps, per onderwerp
            ColumnLayout {
                spacing: 8
                RowLayout {
                    Layout.fillWidth: true
                    PilKnop {
                        tekst: menu.tr("Terug", "Back")
                        pijl: "‹"
                        pijlVoor: true
                        onGeklikt: { stapel.currentIndex = 0; zoekveld.forceActiveFocus() }   // (U204)
                    }
                    Kopje { text: menu.tr("Alle apps", "All apps"); Layout.fillWidth: true; Layout.leftMargin: 6 }
                }
                ListView {
                    id: alleLijst
                    objectName: "alleLijst"
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 2
                    keyNavigationEnabled: true
                    model: menu.alleAppsLijst()
                    section.property: "groep"
                    section.delegate: Label {
                        required property string section
                        text: section.toUpperCase()
                        color: menu.tekst2
                        font.pixelSize: Math.round(12 * menu.schaal)
                        font.weight: Font.DemiBold
                        font.letterSpacing: 0.8
                        topPadding: 12
                        bottomPadding: 4
                        leftPadding: 8
                    }
                    delegate: AppRegel { width: alleLijst.width; app: modelData; gemarkeerd: ListView.isCurrentItem && alleLijst.activeFocus }
                    // Een lange lijst: de schuifbalk altijd laten zien, dan weet je dat er meer is (A-06, VM-test).
                    ScrollBar.vertical: ScrollBar { policy: alleLijst.contentHeight > alleLijst.height ? ScrollBar.AlwaysOn : ScrollBar.AlwaysOff }
                }
            }
        }

        // --------------------------------------------------- onderbalk ---
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: menu.lijnkleur
        }
        RowLayout {
            id: onderRij
            Layout.fillWidth: true
            spacing: 8
            // Jij (foto/letter en naam) als één knop: opent Instellingen > Account (de pagina 'inloggen': naam,
            // foto en wachtwoord), zoals de accountknop van Windows 11. Vroeger deed een klik hierop niets (A-17).
            AbstractButton {
                id: ikKnop
                objectName: "ikKnop"
                Layout.fillWidth: true
                implicitHeight: 40
                hoverEnabled: true
                Accessible.name: menu.tr("Account-instellingen", "Account settings")
                ToolTip.visible: hovered
                ToolTip.text: Accessible.name
                onClicked: { menu.start("instelling:inloggen"); menu.sluiten() }
                Keys.onReturnPressed: clicked()
                Keys.onEnterPressed: clicked()
                background: Rectangle {
                    radius: menu.o.rKnop
                    color: ikKnop.hovered || ikKnop.activeFocus ? menu.zweef : "transparent"
                    border.width: ikKnop.activeFocus ? 2 : 0   // ook met het toetsenbord goed te zien (U135)
                    border.color: menu.rood
                }
                contentItem: RowLayout {
                    spacing: 8
                    Rectangle {
                        id: avatar
                        width: 32; height: 32; radius: 16
                        readonly property string foto: (menu.gegevens.gebruiker && menu.gegevens.gebruiker.foto) ? menu.gegevens.gebruiker.foto : ""
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: menu.o.verloopBegin }
                            GradientStop { position: 1.0; color: menu.o.verloopEind }
                        }
                        Label {
                            anchors.centerIn: parent
                            visible: fotoBeeld.status !== Image.Ready
                            text: ((menu.gegevens.gebruiker && menu.gegevens.gebruiker.naam) || "?").charAt(0).toUpperCase()
                            color: "white"
                            font.family: menu.display
                            font.weight: Font.DemiBold
                            font.pixelSize: Math.round(14 * menu.schaal)
                        }
                        // Eigen foto (als die er is): in een rond venstertje
                        Item {
                            anchors.fill: parent
                            clip: true
                            visible: fotoBeeld.status === Image.Ready
                            Image {
                                id: fotoBeeld
                                anchors.fill: parent
                                // De tijd erachter: een nieuwe foto onder dezelfde naam wordt dan echt opnieuw geladen (U112).
                                source: avatar.foto === "" ? "" : "file://" + avatar.foto + "?" + (menu.gegevens.gebruiker.foto_tijd || 0)
                                cache: false
                                fillMode: Image.PreserveAspectCrop
                                sourceSize.width: 76
                                sourceSize.height: 76
                                asynchronous: true
                            }
                        }
                        Rectangle { anchors.fill: parent; radius: 19; color: "transparent"; border.width: 1; border.color: menu.lijnkleur }
                    }
                    Label {
                        text: (menu.gegevens.gebruiker && menu.gegevens.gebruiker.naam) || ""
                        color: menu.tekst
                        font.pixelSize: Math.round(14 * menu.schaal)
                        font.weight: Font.Medium
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }
                }
            }
            OnderKnop { icoon: "configure"; tekst: menu.tr("Instellingen", "Settings"); onGeklikt: { menu.start("/usr/share/applications/bugos-settings.desktop"); menu.sluiten() } }
            OnderKnop { icoon: "system-lock-screen"; tekst: menu.tr("Vergrendelen", "Lock"); onGeklikt: { menu.aanUit("slot"); menu.sluiten() } }
            OnderKnop { icoon: "system-log-out"; tekst: menu.tr("Afmelden", "Log out"); onGeklikt: { menu.aanUit("uitloggen"); menu.sluiten() } }
            OnderKnop { icoon: "system-reboot"; tekst: menu.tr("Opnieuw opstarten", "Restart"); onGeklikt: { menu.aanUit("herstarten"); menu.sluiten() } }
            OnderKnop { icoon: "system-shutdown"; tekst: menu.tr("Uitzetten", "Shut down"); rood: true; onGeklikt: { menu.aanUit("uitzetten"); menu.sluiten() } }
        }
    }

    // ---------------------------------------------------- bouwsteentjes ---

    component Kopje: Label {
        color: menu.tekst
        font.pixelSize: Math.round(15 * menu.schaal)
        font.weight: Font.DemiBold
    }

    component PilKnop: AbstractButton {
        id: pil
        property string tekst
        property string pijl: "›"
        property bool pijlVoor: false
        signal geklikt()
        implicitHeight: 32
        implicitWidth: rij.implicitWidth + 24
        hoverEnabled: true
        onClicked: geklikt()
        Keys.onReturnPressed: clicked()
        Keys.onEnterPressed: clicked()
        Accessible.name: tekst
        background: Rectangle {
            radius: menu.o.rKnop
            color: pil.hovered || pil.activeFocus ? menu.zweef : menu.vlak
            border.width: pil.activeFocus ? 2 : 0   // ook met het toetsenbord goed te zien (U135)
            border.color: menu.rood
        }
        contentItem: Row {
            id: rij
            spacing: 6
            leftPadding: 12
            Label { visible: pil.pijlVoor; text: pil.pijl; color: menu.tekst; font.pixelSize: Math.round(15 * menu.schaal); anchors.verticalCenter: parent.verticalCenter }
            Label { text: pil.tekst; color: menu.tekst; font.pixelSize: Math.round(13 * menu.schaal); font.weight: Font.Medium; anchors.verticalCenter: parent.verticalCenter }
            Label { visible: !pil.pijlVoor; text: pil.pijl; color: menu.tekst; font.pixelSize: Math.round(15 * menu.schaal); anchors.verticalCenter: parent.verticalCenter }
        }
    }

    component AppTegel: AbstractButton {
        id: tegel
        property var app
        implicitHeight: Math.round(82 * menu.schaal)
        hoverEnabled: true
        Accessible.name: app.naam
        onClicked: { menu.start(app.pad); menu.sluiten() }
        Keys.onReturnPressed: clicked()
        Keys.onEnterPressed: clicked()
        background: Rectangle {
            radius: menu.o.rKnop
            color: tegel.hovered || tegel.activeFocus ? menu.zweef : "transparent"
            border.width: tegel.activeFocus ? 2 : 0   // ook met het toetsenbord goed te zien (U135)
            border.color: menu.rood
        }
        contentItem: ColumnLayout {
            spacing: 6
            Loader {
                Layout.alignment: Qt.AlignHCenter
                Layout.topMargin: 8
                Layout.preferredWidth: Math.round(34 * menu.schaal)
                Layout.preferredHeight: Math.round(34 * menu.schaal)
                sourceComponent: menu.icoonTekenaar
                onLoaded: item.naam = Qt.binding(() => tegel.app.icoon)
                scale: tegel.pressed ? 0.92 : 1.0
                Behavior on scale { NumberAnimation { duration: 90 } }
            }
            Label {
                text: tegel.app.naam
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                maximumLineCount: 2
                elide: Text.ElideRight
                color: menu.tekst
                font.pixelSize: Math.round(12 * menu.schaal)
            }
        }
    }

    component AppRegel: AbstractButton {
        id: regel
        property var app
        property bool gemarkeerd: false
        // 48 (was 54): iets compacter, zodat 'Alle apps' en de zoekresultaten meer regels tegelijk tonen (A-06).
        // Past nog steeds: een pictogram van 32 en twee regels tekst (14 + 12 px).
        implicitHeight: Math.round(48 * menu.schaal)
        hoverEnabled: true
        Accessible.name: app.naam
        onClicked: { menu.start(app.pad); menu.sluiten() }
        Keys.onReturnPressed: clicked()
        Keys.onEnterPressed: clicked()
        // Met Tab naar een regel: dan wordt die ook de gekozen regel, zodat wat oplicht ook is wat Enter opent (U149).
        onActiveFocusChanged: if (activeFocus && ListView.view) {
            const i = ListView.view.indexAt(x + 1, y + 1)
            if (i >= 0) ListView.view.currentIndex = i
        }
        background: Rectangle {
            radius: menu.o.rKnop
            color: regel.hovered || regel.gemarkeerd || regel.activeFocus ? menu.zweef : "transparent"
            border.width: regel.activeFocus ? 2 : 0
            border.color: menu.rood
        }
        contentItem: RowLayout {
            spacing: 12
            Loader {
                Layout.leftMargin: 10
                Layout.preferredWidth: 32
                Layout.preferredHeight: 32
                sourceComponent: menu.icoonTekenaar
                onLoaded: item.naam = Qt.binding(() => regel.app.icoon)
            }
            ColumnLayout {
                spacing: 0
                Layout.fillWidth: true
                Label { text: regel.app.naam; color: menu.tekst; font.pixelSize: Math.round(14 * menu.schaal); font.weight: Font.Medium; elide: Text.ElideRight; Layout.fillWidth: true }
                Label {
                    text: regel.app.uitleg || ""
                    visible: text !== ""
                    color: menu.tekst2
                    font.pixelSize: Math.round(12 * menu.schaal)
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
            }
        }
    }

    component BestandRegel: AbstractButton {
        id: bregel
        property var bestand
        implicitHeight: 50
        hoverEnabled: true
        Accessible.name: bestand.naam
        onClicked: { menu.openBestand(bestand.pad); menu.sluiten() }
        Keys.onReturnPressed: clicked()
        Keys.onEnterPressed: clicked()
        background: Rectangle {
            radius: menu.o.rKnop
            color: bregel.hovered || bregel.activeFocus ? menu.zweef : "transparent"   // ook zichtbaar met het toetsenbord
            border.width: bregel.activeFocus ? 2 : 0   // ook met het toetsenbord goed te zien (U135)
            border.color: menu.rood
        }
        contentItem: RowLayout {
            spacing: 10
            Rectangle {
                Layout.leftMargin: 8
                width: 34; height: 34; radius: 10
                color: menu.vlak
                Loader {
                    anchors.centerIn: parent
                    width: 22; height: 22
                    sourceComponent: menu.icoonTekenaar
                    onLoaded: item.naam = "text-x-generic"
                }
            }
            ColumnLayout {
                spacing: 0
                Layout.fillWidth: true
                Label { text: bregel.bestand.naam; color: menu.tekst; font.pixelSize: Math.round(13 * menu.schaal); elide: Text.ElideMiddle; Layout.fillWidth: true }
                Label { text: bregel.bestand.map; color: menu.tekst2; font.pixelSize: Math.round(12 * menu.schaal); elide: Text.ElideMiddle; Layout.fillWidth: true }
            }
        }
    }

    component OnderKnop: AbstractButton {
        id: knop
        property string icoon
        property string tekst
        property bool rood: false
        signal geklikt()
        implicitWidth: 40
        implicitHeight: 40
        hoverEnabled: true
        Accessible.name: tekst
        ToolTip.visible: hovered
        ToolTip.text: tekst
        onClicked: geklikt()
        Keys.onReturnPressed: clicked()
        Keys.onEnterPressed: clicked()
        background: Rectangle {
            radius: 20
            color: knop.hovered || knop.activeFocus ? (knop.rood ? menu.rood : menu.zweef) : menu.vlak
            border.width: knop.activeFocus ? 2 : 0   // ook met het toetsenbord goed te zien (U135)
            border.color: menu.rood
        }
        contentItem: Item {
            Loader {
                anchors.centerIn: parent
                width: 20; height: 20
                sourceComponent: menu.icoonTekenaar
                onLoaded: item.naam = knop.icoon
            }
        }
    }

    Component.onCompleted: zoekveld.forceActiveFocus()
}
