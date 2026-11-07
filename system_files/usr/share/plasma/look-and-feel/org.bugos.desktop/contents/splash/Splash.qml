// BugOS-opstartscherm (na het inloggen).
// Donker, rustig: het lieveheersbeestje, het woord BugOS en drie stipjes die
// meelopen terwijl het bureaublad wordt klaargezet.

import QtQuick

Rectangle {
    id: root
    color: "#0E0F13"

    // KSplash zet 'stage' van 1 tot 6 terwijl Plasma opstart.
    property int stage

    onStageChanged: {
        if (stage === 2) { inkomen.start() }
        if (stage === 5) { uitgaan.start() }
    }

    // De donkere BugOS-achtergrond 'Stip', gedimd, zodat inloggen naadloos
    // overgaat in het bureaublad.
    Image {
        anchors.fill: parent
        source: "file:///usr/share/wallpapers/bugos/contents/images_dark/3840x2160.jpg"
        fillMode: Image.PreserveAspectCrop
        asynchronous: false
        smooth: true
    }
    Rectangle {
        anchors.fill: parent
        gradient: Gradient {
            orientation: Gradient.Horizontal
            GradientStop { position: 0.0; color: "#F00E0F13" }
            GradientStop { position: 0.55; color: "#C80E0F13" }
            GradientStop { position: 1.0; color: "#600E0F13" }
        }
    }

    Item {
        id: inhoud
        anchors.centerIn: parent
        width: 320
        height: 220
        opacity: 0

        Image {
            id: merk
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            source: "images/bugos-mark-dark.svg"
            sourceSize.width: 112
            sourceSize.height: 112
            smooth: true
        }
        Image {
            id: woord
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: merk.bottom
            anchors.topMargin: 22
            source: "images/bugos-wordmark.svg"
            sourceSize.height: 40
            smooth: true
        }
        Row {
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: woord.bottom
            anchors.topMargin: 30
            spacing: 10
            Repeater {
                model: 3
                Rectangle {
                    required property int index
                    width: 9; height: 9; radius: 4.5
                    color: "#FFFFFF"
                    opacity: 0.25
                    SequentialAnimation on opacity {
                        loops: Animation.Infinite
                        running: true
                        PauseAnimation { duration: index * 180 }
                        NumberAnimation { to: 0.9; duration: 420; easing.type: Easing.InOutQuad }
                        NumberAnimation { to: 0.25; duration: 420; easing.type: Easing.InOutQuad }
                        PauseAnimation { duration: (2 - index) * 180 }
                    }
                }
            }
        }
    }

    NumberAnimation { id: inkomen; target: inhoud; property: "opacity"; to: 1; duration: 600; easing.type: Easing.OutCubic }
    NumberAnimation { id: uitgaan; target: inhoud; property: "opacity"; to: 0; duration: 400; easing.type: Easing.InCubic }
    Component.onCompleted: inkomen.start()
}
