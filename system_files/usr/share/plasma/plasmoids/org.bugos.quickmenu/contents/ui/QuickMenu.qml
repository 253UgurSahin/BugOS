// BugOS snelmenu - de belangrijkste knoppen in één paneel (rechtsonder op de taakbalk).
//
// Zoals de snelle instellingen van Windows 11: bovenaan knoppen (wifi, bluetooth, niet storen, nachtlampje, donker,
// game-modus) met de naam eronder, daaronder schuiven voor het volume en (op een laptop) de helderheid, en onderaan
// een balk met de batterij, het potlood (kies welke knoppen je ziet) en het tandwiel (Instellingen).
// Het pijltje (›) rechts in een knop opent de bijbehorende pagina van BugOS Instellingen (bijv. een wifi-netwerk
// kiezen); op het luidsprekertje klikken zet het geluid uit of aan.
// Alleen gewone QtQuick, zodat het buiten Plasma getest kan worden. De schil (Shell.qml) en Plasma (main.qml) gebruiken
// allebei dit bestand.

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
    // Een pictogram: in de schil een Image (image://icon), in Plasma een Kirigami.Icon. 'wit' = wit maken (op een
    // rode knop die aan staat).
    property Component icoonTekenaar: Image {
        property string naam: ""
        property bool wit: false
        // '?wit': de schil (bugos-shell, Pictogram in main.cpp) kleurt het pictogram dan wit, zonder shader.
        source: naam === "" ? "" : "image://icon/" + naam + (wit ? "?wit" : "")
        sourceSize.width: width * 2
        sourceSize.height: height * 2
    }

    signal zet(string wat, string waarde)
    signal open(string wat)   // "instellingen" of een pagina: wifi, bluetooth, geluid, meldingen, scherm, energie

    // Nog geen status binnen? Dan zeggen we dat, in plaats van grijze knoppen.
    readonly property bool leeg: Object.keys(status).length === 0

    // Aanpassen (het potlood): alle knoppen staan er, een klik verbergt of toont er een.
    property bool bewerken: false
    // Wat je net koos, tot bugos-start-data het terugmeldt (anders sprong een knop even terug).
    property var verborgenNu: null
    readonly property var verborgen: verborgenNu !== null ? verborgenNu : alsLijst(status.verborgen)
    onStatusChanged: if (verborgenNu !== null && alsLijst(status.verborgen).join(",") === verborgenNu.join(","))
                         verborgenNu = null
    // Een lijst uit de status (JSON: een echte lijst; uit C++/Python: een QVariantList); iets anders telt als leeg.
    function alsLijst(x) { return x && typeof x !== "string" && typeof x.length === "number" ? Array.from(x) : [] }
    function isVerborgen(wat) { return verborgen.indexOf(wat) >= 0 }
    function wisselVerborgen(wat) {
        const lijst = verborgen.filter(x => x !== wat)
        if (!isVerborgen(wat))
            lijst.push(wat)
        verborgenNu = lijst
        zet("verborgen", lijst.join(","))
    }
    // Dicht en weer open: niet meer in de aanpasstand.
    onVisibleChanged: if (!visible) bewerken = false

    // Huisstijl: dezelfde kleuren en maten als de BugOS-apps (Design.qml wordt gemaakt uit bugos_ui.py)
    readonly property bool donker: palette.window.hslLightness < 0.5
    readonly property Design o: Design { donker: snel.donker }
    readonly property color rood: o.accent
    readonly property color tekst: o.tekst
    readonly property color tekst2: o.tekst2

    function tr(nl, en) { return nederlands ? nl : en }

    readonly property int binnen: 16          // de rand binnenin
    readonly property int knopHoogte: 44      // de knoppen bovenaan (Windows 11: ook zo'n 44-48)
    implicitWidth: Math.round(360 + 60 * (schaal - 1))
    implicitHeight: kolom.implicitHeight
    color: palette.window
    SystemPalette { id: palette; colorGroup: SystemPalette.Active }

    ColumnLayout {
        id: kolom
        anchors.fill: parent
        spacing: 0

        ColumnLayout {
            Layout.fillWidth: true
            Layout.margins: snel.binnen
            Layout.bottomMargin: 12
            spacing: 14

            // Alleen tijdens het aanpassen: wat je nu kunt doen.
            Label {
                objectName: "aanpasUitleg"
                visible: snel.bewerken
                Layout.fillWidth: true
                text: snel.tr("Klik op een knop om hem te verbergen of terug te zetten.",
                              "Click a button to hide it or bring it back.")
                wrapMode: Text.WordWrap
                color: snel.tekst2
                font.pixelSize: Math.round(snel.o.letterKlein * snel.schaal)
            }

            GridLayout {
                id: tegels
                Layout.fillWidth: true
                columns: 3
                rowSpacing: 12
                columnSpacing: 8
                // kortWaarom/waarom: wat een grijze knop zegt (A-02). bugos-start-data --snel geeft null als de computer
                // het niet heeft: geen wifi-kaart, geen bluetooth.
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
                SnelKnop { wat: "niet_storen"; icoon: "notifications-disabled"; tekst: snel.tr("Niet storen", "Do not disturb"); extra: "meldingen" }
                SnelKnop { wat: "nachtlicht"; icoon: "night-light"; tekst: snel.tr("Nachtlampje", "Night light"); extra: "scherm" }
                SnelKnop { wat: "donker"; icoon: "contrast"; tekst: snel.tr("Donker", "Dark") }
                SnelKnop { wat: "spel"; icoon: "input-gamepad"; tekst: snel.tr("Game-modus", "Game mode") }
            }

            // Alles verborgen: zeg hoe je ze terugkrijgt.
            Label {
                objectName: "allesVerborgen"
                visible: !snel.bewerken && !snel.leeg && snel.verborgen.length >= 6
                Layout.fillWidth: true
                text: snel.tr("Je hebt alle knoppen verborgen. Met het potlood hieronder zet je ze terug.",
                              "You hid all buttons. Use the pencil below to bring them back.")
                wrapMode: Text.WordWrap
                color: snel.tekst2
                font.pixelSize: Math.round(snel.o.letterKlein * snel.schaal)
            }

            // Volume en (op een laptop) de helderheid van het scherm
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                visible: !snel.bewerken
                SchuifRij {
                    wat: "volume"
                    icoon: snel.status.stil ? "audio-volume-muted"
                         : (snel.status.volume || 0) < 34 ? "audio-volume-low"
                         : (snel.status.volume || 0) < 67 ? "audio-volume-medium" : "audio-volume-high"
                    naam: snel.tr("Volume", "Volume")
                    naar: "geluid"
                    meerNaam: snel.tr("Meer over geluid", "More about sound")
                    // Op het luidsprekertje klikken: geluid uit of weer aan (zoals Windows).
                    knopNaam: snel.status.stil ? snel.tr("Geluid aan", "Unmute") : snel.tr("Geluid uit", "Mute")
                    onIcoonGeklikt: snel.zet("stil", snel.status.stil ? "uit" : "aan")
                }
                SchuifRij {
                    wat: "helderheid"
                    icoon: "brightness-high"
                    naam: snel.tr("Helderheid", "Brightness")
                    naar: "scherm"
                    meerNaam: snel.tr("Meer over het scherm", "More about the display")
                    minimum: 5
                }
            }
        }

        // De balk onderaan: batterij links, potlood en tandwiel rechts.
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 1
            color: snel.o.rand
        }
        RowLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 8
            Layout.rightMargin: 8
            Layout.topMargin: 6
            Layout.bottomMargin: 6
            spacing: 4

            Label {
                objectName: "evenKijken"
                visible: snel.leeg
                Layout.leftMargin: 8
                text: snel.tr("Even kijken…", "One moment…")
                color: snel.tekst2
                font.pixelSize: Math.round(snel.o.letterKlein * snel.schaal)
            }

            // Batterij (alleen op een laptop): klikken opent Instellingen > Energie.
            AbstractButton {
                id: batterij
                objectName: "batterij"
                visible: typeof snel.status.batterij === "number"
                hoverEnabled: true
                implicitHeight: 36
                implicitWidth: batterijRij.implicitWidth + 20
                readonly property int procent: snel.status.batterij || 0
                Accessible.name: snel.status.laadt
                      ? snel.tr("Batterij " + procent + "%, wordt opgeladen", "Battery " + procent + "%, charging")
                      : snel.tr("Batterij " + procent + "%", "Battery " + procent + "%")
                ToolTip.visible: hovered
                ToolTip.text: snel.tr("Energie-instellingen", "Power settings")
                ToolTip.delay: 500
                onClicked: snel.open("energie")
                Keys.onReturnPressed: clicked()
                Keys.onEnterPressed: clicked()
                background: Rectangle {
                    radius: 8
                    color: batterij.hovered || batterij.activeFocus ? snel.o.knopHover : "transparent"
                    border.width: batterij.activeFocus ? 2 : 0
                    border.color: snel.rood
                }
                contentItem: Item {
                    RowLayout {
                        id: batterijRij
                        anchors.centerIn: parent
                        spacing: 8
                        Loader {
                            Layout.preferredWidth: 18
                            Layout.preferredHeight: 18
                            sourceComponent: snel.icoonTekenaar
                            onLoaded: item.naam = Qt.binding(() => snel.batterijIcoon(batterij.procent, snel.status.laadt === true))
                        }
                        Label {
                            text: snel.status.laadt ? snel.tr(batterij.procent + "% · wordt opgeladen", batterij.procent + "% · charging")
                                                    : batterij.procent + "%"
                            color: snel.tekst
                            font.pixelSize: Math.round(snel.o.letterKlein * snel.schaal)
                        }
                    }
                }
            }

            Item { Layout.fillWidth: true }

            // Het potlood: kies welke knoppen je ziet. Tijdens het aanpassen staat er 'Klaar'.
            AbstractButton {
                id: potlood
                objectName: "aanpassen"
                visible: !snel.leeg
                hoverEnabled: true
                implicitHeight: 36
                implicitWidth: snel.bewerken ? klaarTekst.implicitWidth + 28 : 36
                Accessible.name: snel.bewerken ? snel.tr("Klaar met aanpassen", "Done editing")
                                               : snel.tr("Snelmenu aanpassen", "Edit quick menu")
                ToolTip.visible: hovered && !snel.bewerken
                ToolTip.text: Accessible.name
                ToolTip.delay: 500
                onClicked: snel.bewerken = !snel.bewerken
                Keys.onReturnPressed: clicked()
                Keys.onEnterPressed: clicked()
                background: Rectangle {
                    radius: 8
                    color: snel.bewerken ? snel.rood
                         : (potlood.hovered || potlood.activeFocus ? snel.o.knopHover : "transparent")
                    border.width: potlood.activeFocus ? 2 : 0
                    border.color: snel.bewerken ? snel.tekst : snel.rood
                }
                contentItem: Item {
                    Loader {
                        visible: !snel.bewerken
                        anchors.centerIn: parent
                        width: 18; height: 18
                        sourceComponent: snel.icoonTekenaar
                        onLoaded: item.naam = "document-edit"
                    }
                    Label {
                        id: klaarTekst
                        visible: snel.bewerken
                        anchors.centerIn: parent
                        text: snel.tr("Klaar", "Done")
                        color: "white"
                        font.pixelSize: Math.round(snel.o.letterKlein * snel.schaal)
                        font.weight: Font.DemiBold
                    }
                }
            }

            AbstractButton {
                id: tandwiel
                objectName: "tandwiel"
                implicitWidth: 36; implicitHeight: 36
                hoverEnabled: true
                // 'Alle instellingen' heet in het startmenu de KDE-app; dit is BugOS Instellingen (U324)
                Accessible.name: snel.tr("Instellingen", "Settings")
                ToolTip.visible: hovered
                ToolTip.text: Accessible.name
                ToolTip.delay: 500
                onClicked: snel.open("instellingen")
                Keys.onReturnPressed: clicked()   // ook met Enter, zoals de andere knoppen (U135)
                Keys.onEnterPressed: clicked()
                background: Rectangle {
                    radius: 8
                    color: tandwiel.hovered || tandwiel.activeFocus ? snel.o.knopHover : "transparent"
                    border.width: tandwiel.activeFocus ? 2 : 0
                    border.color: snel.rood
                }
                contentItem: Item {
                    Loader { anchors.centerIn: parent; width: 18; height: 18; sourceComponent: snel.icoonTekenaar; onLoaded: item.naam = "configure" }
                }
            }
        }
    }

    // Het pictogram van de batterij bij een percentage (de namen van het pictogramthema: battery-040, -charging).
    function batterijIcoon(procent, laadt) {
        const stap = Math.max(0, Math.min(100, Math.round(procent / 20) * 20))
        const naam = "battery-" + ("00" + stap).slice(-3)
        return laadt ? naam + "-charging" : naam
    }

    // Een rij met een schuif (volume, helderheid). Verborgen als de computer het niet heeft.
    component SchuifRij: RowLayout {
        id: rij
        property string wat
        property string icoon
        property string naam
        property string naar
        property string meerNaam
        property string knopNaam: ""     // leeg: het pictogram is geen knop
        property int minimum: 0
        signal icoonGeklikt()
        Layout.fillWidth: true
        objectName: wat
        visible: typeof snel.status[wat] === "number"
        spacing: 6

        AbstractButton {
            id: icoonKnop
            implicitWidth: 36; implicitHeight: 36
            enabled: rij.knopNaam !== ""
            hoverEnabled: true
            Accessible.name: rij.knopNaam !== "" ? rij.knopNaam : rij.naam
            ToolTip.visible: hovered && rij.knopNaam !== ""
            ToolTip.text: rij.knopNaam
            ToolTip.delay: 500
            onClicked: rij.icoonGeklikt()
            Keys.onReturnPressed: clicked()
            Keys.onEnterPressed: clicked()
            background: Rectangle {
                radius: 8
                color: icoonKnop.enabled && (icoonKnop.hovered || icoonKnop.activeFocus) ? snel.o.knopHover : "transparent"
                border.width: icoonKnop.activeFocus ? 2 : 0
                border.color: snel.rood
            }
            contentItem: Item {
                Loader {
                    anchors.centerIn: parent
                    width: 20; height: 20
                    sourceComponent: snel.icoonTekenaar
                    onLoaded: item.naam = Qt.binding(() => rij.icoon)
                }
            }
        }
        Slider {
            id: schuif
            Layout.fillWidth: true
            from: rij.minimum
            to: 100
            stepSize: 5
            wheelEnabled: true   // ook met het scrollwieltje, zoals het volume van KDE (U348)
            implicitHeight: 32   // anders 0 hoog in sommige stijlen, en dan kun je er niet op klikken
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
                height: 4
                radius: 2
                color: snel.donker ? Qt.rgba(1, 1, 1, 0.22) : Qt.rgba(0, 0, 0, 0.18)
                Rectangle {
                    width: schuif.handle.x - schuif.leftPadding + schuif.handle.width / 2
                    height: parent.height
                    radius: 2
                    color: snel.rood
                }
            }
            handle: Rectangle {
                x: schuif.leftPadding + schuif.visualPosition * (schuif.availableWidth - width)
                y: schuif.topPadding + schuif.availableHeight / 2 - height / 2
                width: 18; height: 18; radius: 9
                color: snel.donker ? "#3A3E48" : "#FFFFFF"
                border.width: 1
                border.color: snel.o.randSterk
                // De stip in het midden wordt groter als je de schuif vastpakt of aanwijst (zoals Windows 11).
                Rectangle {
                    anchors.centerIn: parent
                    width: schuif.pressed ? 12 : (schuif.hovered || schuif.activeFocus ? 10 : 8)
                    height: width; radius: width / 2
                    color: snel.rood
                    Behavior on width { NumberAnimation { duration: 90 } }
                }
            }
        }
        Label {
            text: Math.round(schuif.value) + "%"
            color: snel.tekst2
            font.pixelSize: Math.round(snel.o.letterKlein * snel.schaal)
            Layout.preferredWidth: Math.round(36 * snel.schaal)
            horizontalAlignment: Text.AlignRight
        }
        Pijltje { naar: rij.naar; Accessible.name: rij.meerNaam; kleur: snel.tekst2 }
    }

    // Klein pijltje (›): opent de bijbehorende pagina van Instellingen.
    component Pijltje: AbstractButton {
        id: pijl
        property string naar
        property color kleur: snel.tekst2
        property color zweef: snel.o.knopHover
        implicitWidth: 30; implicitHeight: 30
        hoverEnabled: true
        Accessible.name: snel.tr("Meer", "More")
        ToolTip.visible: hovered
        ToolTip.text: Accessible.name
        ToolTip.delay: 500
        onClicked: snel.open(naar)
        Keys.onReturnPressed: clicked()
        Keys.onEnterPressed: clicked()
        background: Rectangle {
            radius: 8
            color: pijl.hovered || pijl.activeFocus ? pijl.zweef : "transparent"
            border.width: pijl.activeFocus ? 2 : 0   // (U135)
            border.color: snel.rood
        }
        contentItem: Label {
            text: "›"
            color: pijl.kleur
            font.pixelSize: Math.round(18 * snel.schaal)
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }
    }

    // Een knop van het snelmenu (wifi, bluetooth, game-modus, ...): klik = aan/uit; de naam staat eronder.
    //
    // A-02 (VM-test): het pijltje (›) zat vroeger in de 'background' van de knop. Dat ligt ONDER de knop, dus de klik
    // ging naar de knop zelf: het pijltje van 'Niet storen' zette niet storen aan in plaats van Instellingen te
    // openen. En stond de knop uit (geen wifi-kaart: status null), dan erfde het pijltje 'enabled: false' en deed
    // het niets. Daarom zijn de knop (links) en het pijltje (rechts) twee broertjes naast elkaar, zoals de gedeelde
    // knoppen van Windows 11. Het pijltje werkt ook als de knop grijs is: Instellingen > Wifi legt dan uit wat er is.
    // Een grijze knop zegt ook waarom: eronder 'Geen wifi' in plaats van de naam, en een uitleg bij het aanwijzen.
    component SnelKnop: Item {
        id: vak
        property string wat
        property string icoon
        property string tekst
        property string extra: ""
        // Waarom de knop grijs is: kort eronder en een hele zin bij het aanwijzen.
        property string kortWaarom: snel.tr("Niet beschikbaar", "Not available")
        property string waarom: snel.tr("Dit kan op deze computer niet.", "This is not available on this computer.")
        readonly property var stand: snel.status[wat]
        readonly property bool aan: stand === true && !snel.bewerken
        // null of ontbrekend = deze computer heeft het niet (bijv. geen wifi-kaart)
        readonly property bool beschikbaar: stand !== null && stand !== undefined
        // Alleen 'niet beschikbaar' zeggen als de status er al is; daarvoor staat er 'Even kijken…' onderaan.
        readonly property bool zonder: !snel.leeg && !beschikbaar
        readonly property bool verborgen: snel.isVerborgen(wat)
        objectName: "tegel-" + wat
        visible: snel.bewerken || !verborgen
        Layout.fillWidth: true
        Layout.preferredWidth: 1
        implicitHeight: snel.knopHoogte + 6 + naamTekst.implicitHeight

        // Aanwijzen werkt ook op een uitgeschakelde knop niet; een HoverHandler op het Item zelf wel.
        HoverHandler { id: zweven }
        ToolTip.visible: vak.zonder && !snel.bewerken && zweven.hovered && !pijl.hovered
        ToolTip.text: vak.waarom
        ToolTip.delay: 300

        // De knop zelf: een afgerond vlak; rood als hij aan staat.
        Rectangle {
            id: vlak
            width: parent.width
            height: snel.knopHoogte
            radius: 10
            opacity: snel.bewerken ? (vak.verborgen ? 0.45 : 1) : (vak.beschikbaar || snel.leeg ? 1 : 0.5)
            color: vak.aan ? (knop.hovered || pijl.hovered ? snel.o.accentHover : snel.rood)
                 : (knop.hovered ? snel.o.knopHover : snel.o.knop)
            border.width: vak.aan ? 0 : 1
            border.color: snel.donker ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(0, 0, 0, 0.06)
            Behavior on color { ColorAnimation { duration: 120 } }

            // Het streepje tussen de knop en het pijltje
            Rectangle {
                visible: pijl.visible
                x: knop.width
                anchors.verticalCenter: parent.verticalCenter
                width: 1
                height: parent.height - 16
                color: vak.aan ? Qt.rgba(1, 1, 1, 0.35) : (snel.donker ? Qt.rgba(1, 1, 1, 0.12) : Qt.rgba(0, 0, 0, 0.12))
            }
        }

        AbstractButton {
            id: knop
            objectName: "knop-" + vak.wat
            width: pijl.visible ? vlak.width - pijl.width : vlak.width
            height: vlak.height
            enabled: vak.beschikbaar || snel.bewerken
            hoverEnabled: true
            Accessible.name: snel.bewerken ? (vak.verborgen ? snel.tr("Tonen: ", "Show: ") : snel.tr("Verbergen: ", "Hide: ")) + vak.tekst
                                           : vak.tekst
            Accessible.description: vak.zonder ? vak.waarom : ""
            Accessible.checkable: !snel.bewerken
            Accessible.checked: vak.aan
            onClicked: snel.bewerken ? snel.wisselVerborgen(vak.wat) : snel.zet(vak.wat, vak.aan ? "uit" : "aan")
            Keys.onReturnPressed: clicked()
            Keys.onEnterPressed: clicked()
            scale: pressed ? 0.96 : 1.0
            Behavior on scale { NumberAnimation { duration: 90 } }
            background: Rectangle {
                radius: 10
                color: "transparent"
                border.width: knop.activeFocus ? 2 : 0
                border.color: vak.aan ? "white" : snel.rood
            }
            contentItem: Item {
                Loader {
                    anchors.centerIn: parent
                    opacity: vlak.opacity
                    width: 20; height: 20
                    sourceComponent: snel.icoonTekenaar
                    onLoaded: {
                        item.naam = vak.icoon
                        // Wit op een rode (aan) knop
                        if (item.hasOwnProperty("wit")) item.wit = Qt.binding(() => vak.aan)
                    }
                }
            }
        }

        // Pijltje naar de bijbehorende pagina van Instellingen (bijv. een netwerk kiezen). Naast de knop, dus de klik
        // komt hier en niet bij de knop. Niet grijs met de knop mee (A-02).
        Pijltje {
            id: pijl
            objectName: "pijl-" + vak.wat
            visible: vak.extra !== "" && !snel.bewerken
            enabled: !snel.leeg
            naar: vak.extra
            x: vlak.width - width - 2
            y: (vlak.height - height) / 2
            height: vlak.height - 4
            width: 30
            kleur: vak.aan ? "white" : snel.tekst2
            zweef: vak.aan ? Qt.rgba(1, 1, 1, 0.18) : snel.o.knopHover
            Accessible.name: snel.tr("Meer over ", "More about ") + vak.tekst.toLowerCase()
        }

        // Tijdens het aanpassen: een rondje met − (verbergen) of + (terugzetten).
        Rectangle {
            visible: snel.bewerken
            width: 20; height: 20; radius: 10
            x: vlak.width - width / 2 - 4
            y: -6
            color: vak.verborgen ? snel.rood : snel.o.vlak
            border.width: 1
            border.color: vak.verborgen ? snel.rood : snel.o.randSterk
            Label {
                anchors.centerIn: parent
                anchors.verticalCenterOffset: -1
                text: vak.verborgen ? "+" : "−"
                color: vak.verborgen ? "white" : snel.tekst
                font.pixelSize: Math.round(14 * snel.schaal)
                font.weight: Font.DemiBold
            }
        }

        // De naam onder de knop; bij een grijze knop de reden ('Geen wifi').
        Label {
            id: naamTekst
            visible: !vak.zonder || snel.bewerken
            y: snel.knopHoogte + 6
            width: parent.width
            text: vak.tekst
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            font.pixelSize: Math.round(12 * snel.schaal)
            color: snel.bewerken && vak.verborgen ? snel.tekst2 : snel.tekst
        }
        Label {
            objectName: "waarom-" + vak.wat
            visible: vak.zonder && !snel.bewerken
            y: snel.knopHoogte + 6
            width: parent.width
            text: vak.kortWaarom
            horizontalAlignment: Text.AlignHCenter
            elide: Text.ElideRight
            font.pixelSize: Math.round(12 * snel.schaal)
            color: snel.tekst2
        }
    }
}
