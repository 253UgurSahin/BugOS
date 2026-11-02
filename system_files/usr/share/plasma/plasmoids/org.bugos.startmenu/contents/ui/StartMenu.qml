// BugOS startmenu - het menu zelf.
//
// Jip-en-Janneke: bovenaan een grote zoekbalk, daaronder je vastgezette apps
// en je laatst geopende bestanden. "Alle apps" laat alles zien, op onderwerp.
// Onderaan: je naam, Instellingen en de aan/uit-knoppen.
//
// Dit bestand gebruikt alleen gewone QtQuick, zodat het ook buiten Plasma
// getest kan worden. main.qml koppelt het aan de taakbalk.

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Rectangle {
    id: menu

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

    readonly property color rood: "#D93A3A"
    readonly property bool alleApps: stapel.currentIndex === 1
    property string zoekTekst: zoekveld.text.trim().toLowerCase()

    function tr(nl, en) { return nederlands ? nl : en }
    function gevonden() {
        if (zoekTekst === "") return []
        const woorden = zoekTekst.split(/\s+/)
        return gegevens.apps.filter(a => woorden.every(w => (a.zoek || a.naam.toLowerCase()).indexOf(w) >= 0))
    }
    function openEerste() {
        const lijst = gevonden()
        if (lijst.length > 0) { start(lijst[0].pad); sluiten() }
    }
    function terugNaarBegin() {
        zoekveld.text = ""
        stapel.currentIndex = 0
        zoekveld.forceActiveFocus()
    }

    implicitWidth: 640
    implicitHeight: 620
    color: palette.window
    SystemPalette { id: palette; colorGroup: SystemPalette.Active }

    Keys.onEscapePressed: sluiten()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 20
        spacing: 16

        // ---------------------------------------------------- zoekbalk ---
        TextField {
            id: zoekveld
            Layout.fillWidth: true
            Layout.preferredHeight: 48
            font.pixelSize: 17
            leftPadding: 16
            placeholderText: menu.tr("Zoek een app of instelling...", "Search for an app or setting...")
            focus: true
            Accessible.name: placeholderText
            onAccepted: menu.openEerste()
            Keys.onDownPressed: zoekLijst.forceActiveFocus()
            background: Rectangle {
                radius: 24
                color: palette.base
                border.width: zoekveld.activeFocus ? 2 : 1
                border.color: zoekveld.activeFocus ? menu.rood : Qt.rgba(palette.text.r, palette.text.g, palette.text.b, 0.2)
            }
        }

        // ------------------------------------------------- zoekresultaat ---
        ListView {
            id: zoekLijst
            visible: menu.zoekTekst !== ""
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 2
            model: menu.zoekTekst !== "" ? menu.gevonden() : []
            keyNavigationEnabled: true
            delegate: AppRegel {
                width: zoekLijst.width
                app: modelData
                gemarkeerd: ListView.isCurrentItem
            }
            Label {
                anchors.centerIn: parent
                visible: zoekLijst.count === 0
                text: menu.tr("Niks gevonden. Probeer een ander woord.", "Nothing found. Try another word.")
                opacity: 0.7
                font.pixelSize: 15
            }
        }

        // -------------------------------------- begin / alle apps (stapel) ---
        StackLayout {
            id: stapel
            objectName: "stapel"
            visible: menu.zoekTekst === ""
            Layout.fillWidth: true
            Layout.fillHeight: true

            // Begin: vastgezet + recent
            ColumnLayout {
                spacing: 12
                RowLayout {
                    Layout.fillWidth: true
                    Label { text: menu.tr("Vastgezet", "Pinned"); font.pixelSize: 15; font.bold: true; Layout.fillWidth: true }
                    Button {
                        text: menu.tr("Alle apps  ›", "All apps  ›")
                        flat: true
                        onClicked: stapel.currentIndex = 1
                    }
                }
                GridLayout {
                    Layout.fillWidth: true
                    columns: 4
                    rowSpacing: 4
                    columnSpacing: 4
                    Repeater {
                        model: menu.gegevens.favorieten
                        delegate: AppTegel { app: modelData; Layout.fillWidth: true; Layout.preferredWidth: 1; Layout.minimumWidth: 0 }
                    }
                }
                Label {
                    text: menu.tr("Recent geopend", "Recently opened")
                    font.pixelSize: 15
                    font.bold: true
                    Layout.topMargin: 8
                    visible: menu.gegevens.recent.length > 0
                }
                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    rowSpacing: 2
                    columnSpacing: 8
                    Repeater {
                        model: menu.gegevens.recent
                        delegate: BestandRegel { bestand: modelData; Layout.fillWidth: true }
                    }
                }
                Item { Layout.fillHeight: true }
            }

            // Alle apps, per onderwerp
            ColumnLayout {
                spacing: 8
                RowLayout {
                    Layout.fillWidth: true
                    Button { text: menu.tr("‹  Terug", "‹  Back"); flat: true; onClicked: stapel.currentIndex = 0 }
                    Label { text: menu.tr("Alle apps", "All apps"); font.pixelSize: 15; font.bold: true; Layout.fillWidth: true }
                }
                ListView {
                    id: alleLijst
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    spacing: 2
                    model: menu.gegevens.apps.slice().sort((a, b) => a.groep === b.groep ? a.naam.localeCompare(b.naam) : a.groep.localeCompare(b.groep))
                    section.property: "groep"
                    section.delegate: Label {
                        required property string section
                        text: section
                        font.bold: true
                        opacity: 0.7
                        topPadding: 10
                        bottomPadding: 4
                    }
                    delegate: AppRegel { width: alleLijst.width; app: modelData }
                    ScrollBar.vertical: ScrollBar {}
                }
            }
        }

        // --------------------------------------------------- onderbalk ---
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Qt.rgba(palette.text.r, palette.text.g, palette.text.b, 0.15)
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            Rectangle {
                width: 36; height: 36; radius: 18
                color: menu.rood
                Label {
                    anchors.centerIn: parent
                    text: (menu.gegevens.gebruiker.naam || "?").charAt(0).toUpperCase()
                    color: "white"
                    font.bold: true
                    font.pixelSize: 16
                }
            }
            Label {
                text: menu.gegevens.gebruiker.naam || ""
                font.pixelSize: 14
                Layout.fillWidth: true
                elide: Text.ElideRight
            }
            OnderKnop { icoon: "preferences-system"; tekst: menu.tr("Instellingen", "Settings"); onGeklikt: { menu.start("/usr/share/applications/bugos-instellingen.desktop"); menu.sluiten() } }
            OnderKnop { icoon: "system-lock-screen"; tekst: menu.tr("Vergrendelen", "Lock"); onGeklikt: { menu.aanUit("slot"); menu.sluiten() } }
            OnderKnop { icoon: "system-log-out"; tekst: menu.tr("Uitloggen", "Log out"); onGeklikt: { menu.aanUit("uitloggen"); menu.sluiten() } }
            OnderKnop { icoon: "system-reboot"; tekst: menu.tr("Herstarten", "Restart"); onGeklikt: { menu.aanUit("herstarten"); menu.sluiten() } }
            OnderKnop { icoon: "system-shutdown"; tekst: menu.tr("Uitzetten", "Shut down"); onGeklikt: { menu.aanUit("uitzetten"); menu.sluiten() } }
        }
    }

    // ---------------------------------------------------- bouwsteentjes ---

    component AppTegel: AbstractButton {
        id: tegel
        property var app
        implicitHeight: 96
        hoverEnabled: true
        Accessible.name: app.naam
        onClicked: { menu.start(app.pad); menu.sluiten() }
        background: Rectangle {
            radius: 12
            color: tegel.hovered || tegel.activeFocus ? Qt.rgba(0.85, 0.23, 0.23, 0.12) : "transparent"
        }
        contentItem: ColumnLayout {
            spacing: 6
            Loader {
                Layout.alignment: Qt.AlignHCenter
                Layout.preferredWidth: 44
                Layout.preferredHeight: 44
                sourceComponent: menu.icoonTekenaar
                onLoaded: item.naam = Qt.binding(() => tegel.app.icoon)
            }
            Label {
                text: tegel.app.naam
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignHCenter
                elide: Text.ElideRight
                font.pixelSize: 13
            }
        }
    }

    component AppRegel: AbstractButton {
        id: regel
        property var app
        property bool gemarkeerd: false
        implicitHeight: 52
        hoverEnabled: true
        Accessible.name: app.naam
        onClicked: { menu.start(app.pad); menu.sluiten() }
        Keys.onReturnPressed: clicked()
        background: Rectangle {
            radius: 10
            color: regel.hovered || regel.gemarkeerd ? Qt.rgba(0.85, 0.23, 0.23, 0.12) : "transparent"
        }
        contentItem: RowLayout {
            spacing: 12
            Loader {
                Layout.leftMargin: 8
                Layout.preferredWidth: 32
                Layout.preferredHeight: 32
                sourceComponent: menu.icoonTekenaar
                onLoaded: item.naam = Qt.binding(() => regel.app.icoon)
            }
            ColumnLayout {
                spacing: 0
                Layout.fillWidth: true
                Label { text: regel.app.naam; font.pixelSize: 14; elide: Text.ElideRight; Layout.fillWidth: true }
                Label {
                    text: regel.app.uitleg || ""
                    visible: text !== ""
                    opacity: 0.65
                    font.pixelSize: 12
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
            }
        }
    }

    component BestandRegel: AbstractButton {
        id: bregel
        property var bestand
        implicitHeight: 48
        hoverEnabled: true
        Accessible.name: bestand.naam
        onClicked: { menu.openBestand(bestand.pad); menu.sluiten() }
        background: Rectangle {
            radius: 10
            color: bregel.hovered ? Qt.rgba(0.85, 0.23, 0.23, 0.12) : "transparent"
        }
        contentItem: RowLayout {
            spacing: 10
            Loader {
                Layout.leftMargin: 6
                Layout.preferredWidth: 28
                Layout.preferredHeight: 28
                sourceComponent: menu.icoonTekenaar
                onLoaded: item.naam = "text-x-generic"
            }
            ColumnLayout {
                spacing: 0
                Layout.fillWidth: true
                Label { text: bregel.bestand.naam; font.pixelSize: 13; elide: Text.ElideMiddle; Layout.fillWidth: true }
                Label { text: bregel.bestand.map; font.pixelSize: 11; opacity: 0.6; elide: Text.ElideMiddle; Layout.fillWidth: true }
            }
        }
    }

    component OnderKnop: AbstractButton {
        id: knop
        property string icoon
        property string tekst
        signal geklikt()
        implicitWidth: 40
        implicitHeight: 40
        hoverEnabled: true
        Accessible.name: tekst
        ToolTip.visible: hovered
        ToolTip.text: tekst
        onClicked: geklikt()
        background: Rectangle {
            radius: 20
            color: knop.hovered || knop.activeFocus ? Qt.rgba(0.85, 0.23, 0.23, 0.15) : "transparent"
        }
        contentItem: Loader {
            sourceComponent: menu.icoonTekenaar
            onLoaded: item.naam = knop.icoon
        }
    }

    Component.onCompleted: zoekveld.forceActiveFocus()
}
