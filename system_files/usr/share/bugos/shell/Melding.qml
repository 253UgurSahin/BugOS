// Eén melding als kaartje rechtsonder: pictogram, kop, tekst, de knoppen van de app, en een kruisje.
// Klikken op het kaartje zelf is de 'standaard'-actie van de app (als hij die heeft), anders sluit het.
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: kaart
    property var melding: ({})
    property var o
    property bool toonTijd: false   // in het meldingencentrum: hoe laat de melding kwam
    signal dicht()
    signal actie(string sleutel)

    implicitHeight: inhoud.implicitHeight + 28
    radius: 12
    color: o.vlak
    border.color: melding.dringend ? o.accent : o.rand
    Accessible.role: Accessible.AlertMessage
    Accessible.name: (melding.kop || "") + ". " + (melding.tekst || "")

    MouseArea {
        anchors.fill: parent
        onClicked: kaart.melding.standaard ? kaart.actie("default") : kaart.dicht()
    }

    RowLayout {
        id: inhoud
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.margins: 14
        spacing: 12

        Image {
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: 32
            Layout.preferredHeight: 32
            visible: (kaart.melding.icoon || "") !== ""
            source: visible ? "image://icon/" + kaart.melding.icoon : ""
            sourceSize.width: 64
            sourceSize.height: 64
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4
            Text {
                Layout.fillWidth: true
                text: [kaart.melding.app || "", kaart.toonTijd ? (kaart.melding.tijd || "") : ""].filter(x => x !== "").join(" · ")
                visible: text !== ""
                color: kaart.o.tekst2
                font.pixelSize: 11
                elide: Text.ElideRight
                textFormat: Text.PlainText
            }
            Text {
                Layout.fillWidth: true
                text: kaart.melding.kop || ""
                color: kaart.o.tekst
                font.pixelSize: 14
                font.bold: true
                wrapMode: Text.Wrap
                textFormat: Text.PlainText
            }
            Text {
                Layout.fillWidth: true
                text: kaart.melding.tekst || ""
                visible: text !== ""
                color: kaart.o.tekst2
                font.pixelSize: 13
                wrapMode: Text.Wrap
                maximumLineCount: 5
                elide: Text.ElideRight
                // De specificatie staat een beetje opmaak toe (<b>, <i>, <a>); StyledText toont alleen dat soort, geen
                // plaatjes van internet of andere HTML.
                textFormat: Text.StyledText
            }
            Flow {
                Layout.fillWidth: true
                spacing: 8
                visible: (kaart.melding.knoppen || []).length > 0
                Repeater {
                    model: kaart.melding.knoppen || []
                    Rectangle {
                        width: knopTekst.implicitWidth + 24
                        height: 30
                        radius: 8
                        color: knopMuis.containsMouse ? kaart.o.knopHover : kaart.o.knop
                        Text { id: knopTekst; anchors.centerIn: parent; text: modelData.tekst; color: kaart.o.tekst; font.pixelSize: 13 }
                        MouseArea { id: knopMuis; anchors.fill: parent; hoverEnabled: true; onClicked: kaart.actie(modelData.sleutel) }
                    }
                }
            }
        }
        Text {
            Layout.alignment: Qt.AlignTop
            text: "✕"
            color: kaart.o.tekst2
            font.pixelSize: 14
            Accessible.role: Accessible.Button
            Accessible.name: "Sluiten"
            MouseArea { anchors.fill: parent; anchors.margins: -8; onClicked: kaart.dicht() }
        }
    }
}
