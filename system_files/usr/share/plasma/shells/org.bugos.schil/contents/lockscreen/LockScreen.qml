// BugOS vergrendelscherm (fase 3 van de eigen schil, docs/STANDALONE.md).
//
// Wat je ziet is van BugOS; de beveiliging blijft van KDE. kscreenlocker_greet laadt dit bestand (het shell-pakket
// org.bugos.schil, gekozen met PLASMA_DEFAULT_SHELL in bugos-sessie) en geeft het mee (nagekeken in kscreenlocker
// Plasma/6.5, greeter/greeterapp.cpp en pamauthenticators.h):
//   authenticator            startAuthenticating(), respond(wachtwoord), signalen succeeded() en failed(soort),
//                            eigenschappen prompt, infoMessage, errorMessage, hadPrompt, busy
//   kscreenlocker_userName   je gebruikersnaam
//   kscreenlocker_userImage  je foto (pad), of leeg
// en leest/verbindt op dit wortel-item: locked, viewVisible, suspendToRamSupported, suspendToDiskSupported,
// suspendToRam(), suspendToDisk(). Ontgrendelen = Qt.quit() na een gelukt wachtwoord (zo doet KDE het ook).
//
// Lukt het laden van dit bestand niet, dan valt kscreenlocker zelf terug op zijn eigen noodscherm: je wordt nooit
// buitengesloten. Alleen gewone QtQuick (geen KDE-onderdelen), zodat het ook buiten de greeter te testen is
// (tools/test_lockscreen.py). Uitproberen zonder echt te vergrendelen:
//   /usr/libexec/kscreenlocker_greet --testing --shell org.bugos.schil
import QtQuick
import QtQuick.Layouts
import QtQuick.Window

Item {
    id: root

    // Deze namen zoekt kscreenlocker op dit item (niet hernoemen).
    property bool locked: false
    property bool viewVisible: false
    property bool suspendToRamSupported: false
    property bool suspendToDiskSupported: false
    signal suspendToRam()
    signal suspendToDisk()

    implicitWidth: 800
    implicitHeight: 600

    readonly property bool nederlands: Qt.locale().name.indexOf("nl") === 0
    function tr(nl, en) { return nederlands ? nl : en }
    readonly property real schaal: Qt.application.font.pointSize > 0
        ? Math.min(1.5, Math.max(1, Qt.application.font.pointSize / 10)) : 1

    // Twee standen, zoals Windows: eerst alleen de klok; een toets of een klik toont je naam en het wachtwoordveld.
    property bool invoer: false
    property string melding: ""
    property bool zonderWachtwoord: false   // ontgrendeld zonder wachtwoord (bijv. vingerafdruk): nog één klik
    property date nu: new Date()

    function toonInvoer() {
        if (!invoer) {
            invoer = true
            authenticator.startAuthenticating()
        }
        wegTimer.restart()
        veld.forceActiveFocus()
    }
    function verberg() {
        invoer = false
        veld.text = ""
        melding = ""
        root.forceActiveFocus()   // anders gaat de volgende toets nergens heen (het veld is weg)
    }
    function probeer() {
        if (veld.text === "" || wachten.running)
            return
        authenticator.respond(veld.text)
    }

    Component.onCompleted: authenticator.startAuthenticating()

    Connections {
        target: authenticator
        function onFailed(soort) {
            if (soort != 0)   // een andere manier (vingerafdruk, smartcard) die niet lukte: niets zeggen
                return
            root.melding = root.tr("Het wachtwoord klopt niet. Probeer het nog eens.",
                                   "That password is not right. Please try again.")
            veld.text = ""
            schud.start()
            wachten.restart()   // even wachten, zoals KDE (en dan opnieuw beginnen)
        }
        function onSucceeded() {
            if (authenticator.hadPrompt)
                Qt.quit()
            else
                root.zonderWachtwoord = true
        }
        function onInfoMessageChanged() { if (authenticator.infoMessage) root.melding = authenticator.infoMessage }
        function onErrorMessageChanged() { if (authenticator.errorMessage) root.melding = authenticator.errorMessage }
        function onPromptForSecretChanged() { veld.forceActiveFocus() }
    }

    Timer {
        id: wachten
        interval: 3000
        onTriggered: authenticator.startAuthenticating()
    }
    Timer {   // niets gedaan en niets getypt: terug naar alleen de klok
        id: wegTimer
        interval: 30000
        onTriggered: if (veld.text === "") root.verberg()
    }
    Timer {
        interval: 1000; repeat: true; running: true; triggeredOnStart: true
        onTriggered: root.nu = new Date()
    }

    // ------------------------------------------------------------------------------------- achtergrond
    Rectangle { anchors.fill: parent; color: "#0E0F13" }
    Image {
        anchors.fill: parent
        source: "file:///usr/share/wallpapers/bugos/contents/images_dark/3840x2160.jpg"
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        sourceSize.width: root.width
    }
    Rectangle {
        anchors.fill: parent
        color: "black"
        opacity: root.invoer || root.zonderWachtwoord ? 0.55 : 0.2
        Behavior on opacity { NumberAnimation { duration: 250 } }
    }

    MouseArea {
        anchors.fill: parent
        hoverEnabled: false
        onPressed: root.toonInvoer()
    }

    focus: true
    Keys.onPressed: event => {
        if (event.key === Qt.Key_Escape) {
            root.verberg()
            event.accepted = true
            return
        }
        if (!root.invoer) {
            root.toonInvoer()
            // Begin je meteen te typen, dan gaat die eerste letter niet verloren.
            if (event.text.length === 1 && event.text >= " ")
                veld.text += event.text
            event.accepted = true
        }
    }

    // ------------------------------------------------------------------------------------- de klok (zonder invoer)
    Column {
        id: grooteKlok
        objectName: "grooteKlok"
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.leftMargin: Math.round(parent.width * 0.06)
        anchors.bottomMargin: Math.round(parent.height * 0.1)
        opacity: root.invoer || root.zonderWachtwoord ? 0 : 1
        visible: opacity > 0
        Behavior on opacity { NumberAnimation { duration: 200 } }
        Text {
            text: Qt.formatTime(root.nu, "HH:mm")
            color: "white"
            font.pixelSize: Math.round(96 * root.schaal)
            font.weight: Font.Light
            style: Text.Raised; styleColor: Qt.rgba(0, 0, 0, 0.3)
        }
        Text {
            text: root.nu.toLocaleDateString(Qt.locale(), "dddd d MMMM")
            color: "white"
            font.pixelSize: Math.round(26 * root.schaal)
            style: Text.Raised; styleColor: Qt.rgba(0, 0, 0, 0.3)
        }
        Item { width: 1; height: 24 }
        Text {
            text: root.tr("Druk op een toets of klik om te ontgrendelen", "Press a key or click to unlock")
            color: Qt.rgba(1, 1, 1, 0.8)
            font.pixelSize: Math.round(15 * root.schaal)
        }
    }

    // ------------------------------------------------------------------------------------- naam en wachtwoord
    ColumnLayout {
        id: blok
        objectName: "invoerBlok"
        anchors.centerIn: parent
        width: Math.min(parent.width - 48, 380)
        spacing: 16
        opacity: root.invoer || root.zonderWachtwoord ? 1 : 0
        visible: opacity > 0
        enabled: visible
        Behavior on opacity { NumberAnimation { duration: 200 } }

        // Je foto, of de eerste letter van je naam in een rode cirkel.
        Rectangle {
            Layout.alignment: Qt.AlignHCenter
            width: 112; height: 112; radius: 56
            color: "#DE2F3E"
            clip: true
            Text {
                anchors.centerIn: parent
                visible: foto.status !== Image.Ready
                text: (kscreenlocker_userName || "?").charAt(0).toUpperCase()
                color: "white"
                font.pixelSize: 48
                font.bold: true
            }
            Image {
                id: foto
                anchors.fill: parent
                source: kscreenlocker_userImage ? "file://" + kscreenlocker_userImage : ""
                fillMode: Image.PreserveAspectCrop
                sourceSize.width: 224
            }
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            text: kscreenlocker_userName || ""
            color: "white"
            font.pixelSize: Math.round(24 * root.schaal)
            font.bold: true
            textFormat: Text.PlainText
        }

        // Het wachtwoordveld (of, na een vingerafdruk, één knop).
        Rectangle {
            id: veldVlak
            visible: !root.zonderWachtwoord
            Layout.fillWidth: true
            Layout.preferredHeight: Math.round(48 * root.schaal)
            radius: 10
            color: Qt.rgba(1, 1, 1, 0.92)
            border.width: veld.activeFocus ? 2 : 0
            border.color: "#DE2F3E"
            transform: Translate { id: schuif }

            TextInput {
                id: veld
                objectName: "wachtwoord"
                anchors.left: parent.left
                anchors.right: kijk.left
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: 16
                anchors.rightMargin: 8
                echoMode: kijk.aan ? TextInput.Normal : TextInput.Password
                passwordCharacter: "●"
                color: "#16171C"
                font.pixelSize: Math.round(17 * root.schaal)
                clip: true
                enabled: !wachten.running
                Accessible.name: root.tr("Wachtwoord", "Password")
                Accessible.role: Accessible.EditableText
                Accessible.passwordEdit: true
                onTextChanged: wegTimer.restart()
                Keys.onReturnPressed: root.probeer()
                Keys.onEnterPressed: root.probeer()
                Keys.onEscapePressed: root.verberg()
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: veld.text === ""
                    text: wachten.running ? root.tr("Even wachten…", "Please wait…") : root.tr("Wachtwoord", "Password")
                    color: "#6B7080"
                    font.pixelSize: veld.font.pixelSize
                }
            }
            // Het wachtwoord even laten zien (en weer verbergen).
            Rectangle {
                id: kijk
                property bool aan: false
                anchors.right: gaan.left
                anchors.verticalCenter: parent.verticalCenter
                anchors.rightMargin: 4
                width: 36; height: 36; radius: 8
                color: kijkMuis.containsMouse ? "#EEEAEA" : "transparent"
                Accessible.role: Accessible.CheckBox
                Accessible.name: root.tr("Wachtwoord tonen", "Show password")
                Accessible.checked: aan
                Text { anchors.centerIn: parent; text: kijk.aan ? "◡" : "◉"; color: "#5D6270"; font.pixelSize: 16 }
                MouseArea { id: kijkMuis; anchors.fill: parent; hoverEnabled: true; onClicked: { kijk.aan = !kijk.aan; veld.forceActiveFocus() } }
            }
            Rectangle {
                id: gaan
                objectName: "ontgrendelKnop"
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.rightMargin: 6
                width: 36; height: 36; radius: 8
                color: veld.text !== "" ? "#DE2F3E" : "#D5D0D0"
                Accessible.role: Accessible.Button
                Accessible.name: root.tr("Ontgrendelen", "Unlock")
                Text { anchors.centerIn: parent; text: "→"; color: "white"; font.pixelSize: 18; font.bold: true }
                MouseArea { anchors.fill: parent; onClicked: root.probeer() }
            }

            SequentialAnimation {
                id: schud
                NumberAnimation { target: schuif; property: "x"; to: -12; duration: 50 }
                NumberAnimation { target: schuif; property: "x"; to: 12; duration: 70 }
                NumberAnimation { target: schuif; property: "x"; to: -8; duration: 60 }
                NumberAnimation { target: schuif; property: "x"; to: 0; duration: 50 }
            }
        }

        Rectangle {
            id: zonderKnop
            objectName: "zonderWachtwoordKnop"
            visible: root.zonderWachtwoord
            Layout.fillWidth: true
            Layout.preferredHeight: Math.round(48 * root.schaal)
            radius: 10
            color: "#DE2F3E"
            Accessible.role: Accessible.Button
            Accessible.name: root.tr("Ontgrendelen", "Unlock")
            Text { anchors.centerIn: parent; text: root.tr("Ontgrendelen", "Unlock"); color: "white"; font.pixelSize: 17; font.bold: true }
            MouseArea { anchors.fill: parent; onClicked: Qt.quit() }
        }

        Text {
            id: meldingTekst
            objectName: "melding"
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            text: root.melding
            visible: text !== ""
            color: "white"
            font.pixelSize: Math.round(15 * root.schaal)
            textFormat: Text.PlainText
            Accessible.role: Accessible.AlertMessage
        }
    }

    // ------------------------------------------------------------------------------------- slaapstand
    Rectangle {
        objectName: "slaapKnop"
        visible: root.suspendToRamSupported && (root.invoer || root.zonderWachtwoord)
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 32
        width: slaapTekst.implicitWidth + 32
        height: 44
        radius: 10
        color: slaapMuis.containsMouse ? Qt.rgba(1, 1, 1, 0.25) : Qt.rgba(1, 1, 1, 0.12)
        Accessible.role: Accessible.Button
        Accessible.name: slaapTekst.text
        Text { id: slaapTekst; anchors.centerIn: parent; text: root.tr("Slaapstand", "Sleep"); color: "white"; font.pixelSize: 15 }
        MouseArea { id: slaapMuis; anchors.fill: parent; hoverEnabled: true; onClicked: { root.verberg(); root.suspendToRam() } }
    }
}
