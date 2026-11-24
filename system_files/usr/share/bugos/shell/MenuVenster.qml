// Een los menu (rechtermuisknop op de taakbalk, Start, een app, het systeemvak of het bureaublad), in de BugOS-stijl.
//
//   menu.openOp(scherm, x, y, regels, terug)
//     x, y    waar (vanaf linksboven van het scherm); past het daar niet, dan schuift het naar binnen
//     regels  [{ tekst, icoon, aan (kan nu), scheiding, vink ("checkmark"/"radio"), gevinkt, kinderen: [...] }]
//     terug   function(regel): wat er gebeurt als je een regel kiest
// Submenu's staan ingesprongen eronder (geen tweede venster). Pijltjes, Enter en Escape werken.
import QtQuick
import QtQuick.Window

LaagVenster {
    id: menu
    soort: "menu"
    property var o
    property real onderRand: 56          // de ruimte die de taakbalk onderaan inneemt (plus wat lucht)
    property var platteRegels: []
    property var terug: null
    property int gekozen: -1
    signal dicht()

    width: 280
    height: Math.min(kolom.implicitHeight + 12, (screen ? screen.height : 800) - onderRand - 16)

    function plat(regels, diepte, uit) {
        for (let i = 0; i < regels.length; i++) {
            const r = regels[i]
            uit.push(Object.assign({}, r, { diepte: diepte, kopje: (r.kinderen || []).length > 0 }))
            if ((r.kinderen || []).length > 0)
                plat(r.kinderen, diepte + 1, uit)
        }
        return uit
    }

    function openOp(scherm, x, y, regels, terugFunctie) {
        visible = false
        wasActief = false
        if (scherm)
            screen = scherm
        platteRegels = plat(regels || [], 0, [])
        kolom.forceLayout()   // de hoogte van de nieuwe regels nu al weten (anders past hij niet boven de taakbalk)
        terug = terugFunctie
        gekozen = -1
        const sb = scherm ? scherm.width : 1280
        const sh = scherm ? scherm.height : 800
        const h = Math.min(kolom.implicitHeight + 12, sh - onderRand - 16)
        const px = Math.max(8, Math.min(x, sb - width - 8))
        const py = Math.max(8, Math.min(y, sh - onderRand - h - 8))
        schil.plaats(menu, px, py)
        visible = true
        requestActivate()
        lijst.forceActiveFocus()
    }
    function sluit() {
        if (visible) {
            visible = false
            dicht()
        }
    }
    function kies(i) {
        const r = platteRegels[i]
        if (!r || r.scheiding || r.kopje || r.aan === false)
            return
        const f = terug
        sluit()
        if (f)
            f(r)
    }
    function volgende(stap) {
        let i = gekozen
        for (let n = 0; n < platteRegels.length; n++) {
            i = (i + stap + platteRegels.length) % platteRegels.length
            const r = platteRegels[i]
            if (!r.scheiding && !r.kopje && r.aan !== false) {
                gekozen = i
                return
            }
        }
    }

    // Dicht als je ergens anders klikt (het menu verliest de focus). Maar alleen als het sinds het openen echt actief
    // was: het 'niet meer actief' van de vorige keer komt soms pas binnen als het menu al opnieuw open is.
    property bool wasActief: false
    onActiveChanged: {
        if (active)
            wasActief = true
        else if (wasActief && visible)
            sluit()
    }

    Rectangle {
        anchors.fill: parent
        radius: 10
        color: menu.o.vlak
        border.color: menu.o.rand
        clip: true

        Flickable {
            id: lijst
            anchors.fill: parent
            anchors.margins: 6
            contentHeight: kolom.implicitHeight
            boundsBehavior: Flickable.StopAtBounds
            focus: true
            Keys.onUpPressed: menu.volgende(-1)
            Keys.onDownPressed: menu.volgende(1)
            Keys.onReturnPressed: menu.kies(menu.gekozen)
            Keys.onEnterPressed: menu.kies(menu.gekozen)
            Keys.onSpacePressed: menu.kies(menu.gekozen)
            Keys.onEscapePressed: menu.sluit()

            Column {
                id: kolom
                width: lijst.width
                Repeater {
                    model: menu.platteRegels
                    delegate: Item {
                        id: regel
                        required property var modelData
                        required property int index
                        width: kolom.width
                        height: modelData.scheiding ? 9 : 34
                        Accessible.role: modelData.scheiding ? Accessible.Separator : Accessible.MenuItem
                        Accessible.name: modelData.tekst || ""

                        Rectangle {
                            visible: regel.modelData.scheiding === true
                            anchors.verticalCenter: parent.verticalCenter
                            x: 8; width: parent.width - 16; height: 1
                            color: menu.o.rand
                        }
                        Rectangle {
                            visible: !regel.modelData.scheiding
                            anchors.fill: parent
                            radius: 6
                            color: (muis.containsMouse || menu.gekozen === regel.index) && !regel.modelData.kopje
                                   && regel.modelData.aan !== false ? menu.o.knopHover : "transparent"
                        }
                        Image {
                            id: plaatje
                            visible: !regel.modelData.scheiding && (regel.modelData.icoon || "") !== ""
                            x: 10 + 14 * regel.modelData.diepte
                            anchors.verticalCenter: parent.verticalCenter
                            width: 18; height: 18
                            sourceSize.width: 36; sourceSize.height: 36
                            source: visible ? "image://icon/" + regel.modelData.icoon : ""
                            opacity: regel.modelData.aan === false ? 0.45 : 1
                        }
                        Text {
                            visible: !regel.modelData.scheiding
                            anchors.verticalCenter: parent.verticalCenter
                            x: 10 + 14 * regel.modelData.diepte + 26
                            width: parent.width - x - 30
                            text: regel.modelData.tekst || ""
                            elide: Text.ElideRight
                            textFormat: Text.PlainText
                            color: regel.modelData.kopje ? menu.o.tekst2 : menu.o.tekst
                            opacity: regel.modelData.aan === false ? 0.45 : 1
                            font.pixelSize: 14
                            font.bold: regel.modelData.kopje === true
                        }
                        Text {
                            visible: regel.modelData.gevinkt === true
                            anchors.right: parent.right
                            anchors.rightMargin: 10
                            anchors.verticalCenter: parent.verticalCenter
                            text: regel.modelData.vink === "radio" ? "●" : "✓"
                            color: menu.o.accent
                            font.pixelSize: 14
                        }
                        MouseArea {
                            id: muis
                            anchors.fill: parent
                            hoverEnabled: true
                            enabled: !regel.modelData.scheiding
                            onEntered: menu.gekozen = regel.index
                            onClicked: menu.kies(regel.index)
                        }
                    }
                }
            }
        }
    }
}
