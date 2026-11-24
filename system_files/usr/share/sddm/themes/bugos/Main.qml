// BugOS inlogscherm (een thema voor SDDM, fase 3 van docs/STANDALONE.md).
//
// Dezelfde stijl als het BugOS-vergrendelscherm. SDDM controleert het wachtwoord zelf (PAM); dit scherm toont alleen
// en geeft door. SDDM geeft mee (nagekeken in de broncode van SDDM, src/greeter/GreeterApp.cpp en GreeterProxy.h):
//   sddm          login(gebruiker, wachtwoord, sessie), powerOff(), reboot(), suspend(); canPowerOff, canReboot,
//                 canSuspend, hostName; signalen loginFailed(), loginSucceeded(), informationMessage(tekst)
//   userModel     rollen name, realName, icon, needsPassword; lastIndex, lastUser, count
//   sessionModel  rollen name, file, comment; lastIndex, count
//   keyboard      capsLock
//   config        theme.conf ([General] background)
//   primaryScreen dit scherm is het hoofdscherm (alleen daar het inlogvak; op de andere alleen de achtergrond)
// Lukt het laden van dit bestand niet, dan valt SDDM zelf terug op zijn ingebouwde scherm (GreeterApp.cpp): inloggen
// kan dan nog steeds. Alleen gewone QtQuick, zodat het ook buiten SDDM te testen is (tools/test_sddm_thema.py).
// Veilig proberen:  sddm-greeter-qt6 --test-mode --theme /usr/share/sddm/themes/bugos
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: root
    width: 1280
    height: 800
    color: "#0E0F13"

    readonly property bool nederlands: Qt.locale().name.indexOf("nl") === 0
    function tr(nl, en) { return nederlands ? nl : en }
    readonly property bool hoofd: typeof primaryScreen === "undefined" ? true : primaryScreen

    // Wie er inlogt: de laatste gebruiker (of de eerste), en met welke sessie.
    property int gebruiker: userModel.lastIndex >= 0 && userModel.lastIndex < userModel.count ? userModel.lastIndex : 0
    property int sessie: sessionModel.lastIndex >= 0 && sessionModel.lastIndex < sessionModel.count ? sessionModel.lastIndex : 0
    property string melding: ""
    property bool bezig: false
    property date nu: new Date()

    // Gegevens van de gekozen gebruiker en sessie (uit de modellen, via een onzichtbare Repeater).
    property string gebruikerNaam: ""
    property string gebruikerEchteNaam: ""
    property string gebruikerFoto: ""
    property bool wachtwoordNodig: true
    property string sessieNaam: ""
    Repeater {
        model: userModel
        delegate: Item {
            required property int index
            required property string name
            required property string realName
            required property string icon
            required property bool needsPassword
            Component.onCompleted: bijwerken()
            function bijwerken() {
                if (index !== root.gebruiker)
                    return
                root.gebruikerNaam = name
                root.gebruikerEchteNaam = realName
                root.gebruikerFoto = icon
                root.wachtwoordNodig = needsPassword
            }
            Connections { target: root; function onGebruikerChanged() { bijwerken() } }
        }
    }
    Repeater {
        model: sessionModel
        delegate: Item {
            required property int index
            required property string name
            Component.onCompleted: if (index === root.sessie) root.sessieNaam = name
            Connections { target: root; function onSessieChanged() { if (index === root.sessie) root.sessieNaam = name } }
        }
    }

    function inloggen() {
        const naam = userModel.count > 0 ? gebruikerNaam : naamVeld.text.trim()
        if (naam === "" || bezig)
            return
        bezig = true
        melding = ""
        sddm.login(naam, wachtwoord.text, sessie)
    }
    function volgendeGebruiker(stap) {
        if (userModel.count > 1) {
            gebruiker = (gebruiker + stap + userModel.count) % userModel.count
            wachtwoord.text = ""
            melding = ""
            wachtwoord.forceActiveFocus()
        }
    }
    function volgendeSessie() {
        if (sessionModel.count > 1)
            sessie = (sessie + 1) % sessionModel.count
    }

    Connections {
        target: sddm
        function onLoginFailed() {
            root.bezig = false
            root.melding = root.tr("Het wachtwoord klopt niet. Probeer het nog eens.",
                                   "That password is not right. Please try again.")
            wachtwoord.text = ""
            schud.start()
            wachtwoord.forceActiveFocus()
        }
        function onLoginSucceeded() { root.melding = "" }
        function onInformationMessage(tekst) { root.melding = tekst }
    }

    Timer { interval: 1000; repeat: true; running: true; triggeredOnStart: true; onTriggered: root.nu = new Date() }

    // ------------------------------------------------------------------------------------- achtergrond
    Image {
        anchors.fill: parent
        source: config.background ? "file://" + config.background : ""
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        sourceSize.width: root.width
    }
    Rectangle { anchors.fill: parent; color: "black"; opacity: root.hoofd ? 0.45 : 0.2 }

    // ------------------------------------------------------------------------------------- de klok
    Column {
        visible: root.hoofd
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.margins: 48
        Text {
            text: Qt.formatTime(root.nu, "HH:mm")
            color: "white"
            font.pixelSize: 64
            font.weight: Font.Light
        }
        Text {
            text: root.nu.toLocaleDateString(Qt.locale(), "dddd d MMMM")
            color: Qt.rgba(1, 1, 1, 0.85)
            font.pixelSize: 20
        }
    }

    // ------------------------------------------------------------------------------------- het inlogvak
    ColumnLayout {
        id: blok
        objectName: "inlogBlok"
        visible: root.hoofd
        anchors.centerIn: parent
        width: Math.min(parent.width - 48, 380)
        spacing: 16

        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 18
            // Een andere gebruiker (alleen als er meer dan één is)
            Rectangle {
                objectName: "vorigeGebruiker"
                visible: userModel.count > 1
                width: 36; height: 36; radius: 18
                color: vorigeMuis.containsMouse ? Qt.rgba(1, 1, 1, 0.25) : Qt.rgba(1, 1, 1, 0.12)
                Accessible.role: Accessible.Button
                Accessible.name: root.tr("Vorige gebruiker", "Previous user")
                Text { anchors.centerIn: parent; text: "‹"; color: "white"; font.pixelSize: 22 }
                MouseArea { id: vorigeMuis; anchors.fill: parent; hoverEnabled: true; onClicked: root.volgendeGebruiker(-1) }
            }
            // Je foto, of de eerste letter van je naam in een rode cirkel.
            Rectangle {
                width: 120; height: 120; radius: 60
                color: "#DE2F3E"
                clip: true
                Text {
                    anchors.centerIn: parent
                    visible: foto.status !== Image.Ready
                    text: (root.gebruikerEchteNaam || root.gebruikerNaam || "?").charAt(0).toUpperCase()
                    color: "white"
                    font.pixelSize: 52
                    font.bold: true
                }
                Image {
                    id: foto
                    anchors.fill: parent
                    source: root.gebruikerFoto ? (root.gebruikerFoto.indexOf("/") === 0 ? "file://" + root.gebruikerFoto : root.gebruikerFoto) : ""
                    fillMode: Image.PreserveAspectCrop
                    sourceSize.width: 240
                }
            }
            Rectangle {
                objectName: "volgendeGebruiker"
                visible: userModel.count > 1
                width: 36; height: 36; radius: 18
                color: volgendeMuis.containsMouse ? Qt.rgba(1, 1, 1, 0.25) : Qt.rgba(1, 1, 1, 0.12)
                Accessible.role: Accessible.Button
                Accessible.name: root.tr("Volgende gebruiker", "Next user")
                Text { anchors.centerIn: parent; text: "›"; color: "white"; font.pixelSize: 22 }
                MouseArea { id: volgendeMuis; anchors.fill: parent; hoverEnabled: true; onClicked: root.volgendeGebruiker(1) }
            }
        }
        Text {
            objectName: "naam"
            visible: userModel.count > 0
            Layout.alignment: Qt.AlignHCenter
            text: root.gebruikerEchteNaam || root.gebruikerNaam
            color: "white"
            font.pixelSize: 26
            font.bold: true
            textFormat: Text.PlainText
        }

        // Geen lijst met gebruikers (verborgen of te veel): dan typ je je inlognaam.
        Rectangle {
            visible: userModel.count === 0
            Layout.fillWidth: true
            Layout.preferredHeight: 48
            radius: 10
            color: Qt.rgba(1, 1, 1, 0.92)
            TextInput {
                id: naamVeld
                objectName: "naamVeld"
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                verticalAlignment: TextInput.AlignVCenter
                color: "#16171C"
                font.pixelSize: 17
                Accessible.name: root.tr("Inlognaam", "User name")
                KeyNavigation.tab: wachtwoord
                Keys.onReturnPressed: wachtwoord.forceActiveFocus()
                Text { anchors.verticalCenter: parent.verticalCenter; visible: naamVeld.text === ""; text: root.tr("Inlognaam", "User name"); color: "#6B7080"; font.pixelSize: 17 }
            }
        }

        Rectangle {
            id: veldVlak
            Layout.fillWidth: true
            Layout.preferredHeight: 48
            radius: 10
            color: Qt.rgba(1, 1, 1, 0.92)
            border.width: wachtwoord.activeFocus ? 2 : 0
            border.color: "#DE2F3E"
            transform: Translate { id: schuif }
            TextInput {
                id: wachtwoord
                objectName: "wachtwoord"
                anchors.left: parent.left
                anchors.right: gaan.left
                anchors.verticalCenter: parent.verticalCenter
                anchors.leftMargin: 16
                anchors.rightMargin: 8
                echoMode: TextInput.Password
                passwordCharacter: "●"
                color: "#16171C"
                font.pixelSize: 17
                clip: true
                focus: true
                enabled: !root.bezig
                Accessible.name: root.tr("Wachtwoord", "Password")
                Accessible.role: Accessible.EditableText
                Accessible.passwordEdit: true
                Keys.onReturnPressed: root.inloggen()
                Keys.onEnterPressed: root.inloggen()
                Keys.onUpPressed: root.volgendeGebruiker(-1)
                Keys.onDownPressed: root.volgendeGebruiker(1)
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    visible: wachtwoord.text === ""
                    text: root.bezig ? root.tr("Even wachten…", "Please wait…")
                                     : (root.wachtwoordNodig ? root.tr("Wachtwoord", "Password")
                                                             : root.tr("Geen wachtwoord nodig: druk op Enter", "No password needed: press Enter"))
                    color: "#6B7080"
                    font.pixelSize: 17
                }
            }
            Rectangle {
                id: gaan
                objectName: "inlogKnop"
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.rightMargin: 6
                width: 36; height: 36; radius: 8
                color: "#DE2F3E"
                Accessible.role: Accessible.Button
                Accessible.name: root.tr("Inloggen", "Sign in")
                Text { anchors.centerIn: parent; text: "→"; color: "white"; font.pixelSize: 18; font.bold: true }
                MouseArea { anchors.fill: parent; onClicked: root.inloggen() }
            }
            SequentialAnimation {
                id: schud
                NumberAnimation { target: schuif; property: "x"; to: -12; duration: 50 }
                NumberAnimation { target: schuif; property: "x"; to: 12; duration: 70 }
                NumberAnimation { target: schuif; property: "x"; to: -8; duration: 60 }
                NumberAnimation { target: schuif; property: "x"; to: 0; duration: 50 }
            }
        }

        Text {
            objectName: "melding"
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            wrapMode: Text.Wrap
            visible: text !== ""
            text: {
                const delen = []
                if (root.melding !== "")
                    delen.push(root.melding)
                if (typeof keyboard !== "undefined" && keyboard && keyboard.capsLock)
                    delen.push(root.tr("Hoofdletters staan aan (Caps Lock).", "Caps Lock is on."))
                return delen.join("\n")
            }
            color: "white"
            font.pixelSize: 15
            textFormat: Text.PlainText
            Accessible.role: Accessible.AlertMessage
        }
    }

    // ------------------------------------------------------------------------------------- onderaan
    // Links: de sessie (alleen als er een keus is, zoals de proefsessie met de nieuwe schil).
    Rectangle {
        objectName: "sessieKnop"
        visible: root.hoofd && sessionModel.count > 1
        anchors.left: parent.left
        anchors.bottom: parent.bottom
        anchors.margins: 32
        width: sessieTekst.implicitWidth + 32
        height: 44
        radius: 10
        color: sessieMuis.containsMouse ? Qt.rgba(1, 1, 1, 0.25) : Qt.rgba(1, 1, 1, 0.12)
        Accessible.role: Accessible.Button
        Accessible.name: sessieTekst.text
        Text {
            id: sessieTekst
            anchors.centerIn: parent
            text: root.tr("Sessie: ", "Session: ") + root.sessieNaam
            color: "white"
            font.pixelSize: 15
            textFormat: Text.PlainText
        }
        MouseArea { id: sessieMuis; anchors.fill: parent; hoverEnabled: true; onClicked: root.volgendeSessie() }
    }

    // Rechts: slaapstand, opnieuw opstarten en uitzetten (alleen wat de computer kan).
    Row {
        visible: root.hoofd
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 32
        spacing: 10
        Repeater {
            model: [
                { naam: "slaap", tekst: root.tr("Slaapstand", "Sleep"), kan: sddm.canSuspend },
                { naam: "herstart", tekst: root.tr("Opnieuw opstarten", "Restart"), kan: sddm.canReboot },
                { naam: "uit", tekst: root.tr("Uitzetten", "Shut down"), kan: sddm.canPowerOff }
            ]
            delegate: Rectangle {
                required property var modelData
                // Een naam voor de test (objectName met een binding aan modelData blijft leeg bij een Repeater).
                Component.onCompleted: objectName = "knop-" + modelData.naam
                visible: modelData.kan
                width: knopTekst.implicitWidth + 32
                height: 44
                radius: 10
                color: knopMuis.containsMouse ? Qt.rgba(1, 1, 1, 0.25) : Qt.rgba(1, 1, 1, 0.12)
                Accessible.role: Accessible.Button
                Accessible.name: modelData.tekst
                Text { id: knopTekst; anchors.centerIn: parent; text: parent.modelData.tekst; color: "white"; font.pixelSize: 15 }
                MouseArea {
                    id: knopMuis
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: {
                        if (parent.modelData.naam === "slaap")
                            sddm.suspend()
                        else if (parent.modelData.naam === "herstart")
                            sddm.reboot()
                        else
                            sddm.powerOff()
                    }
                }
            }
        }
    }

    Component.onCompleted: {
        if (userModel.count === 0)
            naamVeld.forceActiveFocus()
        else
            wachtwoord.forceActiveFocus()
    }
}
