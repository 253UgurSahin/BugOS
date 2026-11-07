#!/usr/bin/env python3
"""Proefkaart van de Plasma-stijl: taakbalk, pop-up met kop, tooltip en Plasma-knoppen.

Maakt /uit/plasma-<thema>.png. De stijl komt uit ~/.config/plasmarc ([Theme] name=bugos).
Tekent de echte stijlbestanden (KSvg) en de echte Plasma-knoppen (PlasmaComponents 3),
zoals plasmashell dat doet, maar dan zonder bureaublad.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtQuick import QQuickView
from PySide6.QtWidgets import QApplication

THEMA = os.environ.get("BUGOS_THEMA", "licht")
UIT = Path(os.environ.get("BUGOS_UIT", "/uit"))

QML = r'''
import QtQuick
import QtQuick.Layouts
import org.kde.ksvg as KSvg
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PC3
import org.kde.plasma.extras as PlasmaExtras

Rectangle {
    width: 1100; height: 760
    color: THEMA_DONKER ? "#5a1f27" : "#f3c9cc"   // ongeveer de Stip-achtergrond

    // Taakbalk (zwevend), met taken in verschillende standen
    KSvg.FrameSvgItem {
        id: balk
        imagePath: "widgets/panel-background"
        x: 40; y: parent.height - 80; width: parent.width - 80; height: 56
        RowLayout {
            anchors.fill: parent; anchors.leftMargin: balk.margins.left + 8; anchors.rightMargin: balk.margins.right + 8
            spacing: 6
            Repeater {
                model: ["normal", "hover", "focus", "attention", "minimized"]
                delegate: KSvg.FrameSvgItem {
                    imagePath: "widgets/tasks"; prefix: modelData
                    Layout.preferredWidth: 56; Layout.preferredHeight: 44
                    Kirigami.Icon { anchors.centerIn: parent; width: 28; height: 28; source: "system-file-manager" }
                }
            }
            Item { Layout.fillWidth: true }
            Kirigami.Icon { implicitWidth: 22; implicitHeight: 22; source: "audio-volume-high" }
            Kirigami.Icon { implicitWidth: 22; implicitHeight: 22; source: "network-wireless-signal-good" }
            Kirigami.Icon { implicitWidth: 22; implicitHeight: 22; source: "battery-060" }
            Kirigami.Icon { implicitWidth: 22; implicitHeight: 22; source: "preferences-desktop-notification-bell" }
            PC3.Label { text: "9:26 AM"; font.pixelSize: 13 }
        }
    }

    // Pop-up zoals 'Audio Volume' boven het systeemvak
    KSvg.FrameSvgItem {
        id: popup
        imagePath: "dialogs/background"
        x: parent.width - 460; y: 40; width: 420; height: 560
        ColumnLayout {
            anchors.fill: parent
            anchors.leftMargin: popup.margins.left; anchors.rightMargin: popup.margins.right
            anchors.topMargin: popup.margins.top; anchors.bottomMargin: popup.margins.bottom
            spacing: 10
            PlasmaExtras.PlasmoidHeading {
                Layout.fillWidth: true
                contentItem: RowLayout {
                    PlasmaExtras.Heading { text: "Audio Volume"; level: 1; Layout.fillWidth: true }
                    PC3.ToolButton { icon.name: "configure" }
                    PC3.ToolButton { icon.name: "window-pin"; checkable: true; checked: true }
                }
            }
            PC3.TabBar { Layout.fillWidth: true
                PC3.TabButton { text: "Devices" } PC3.TabButton { text: "Applications" } }
            RowLayout { Kirigami.Icon { source: "audio-volume-medium"; implicitWidth: 22; implicitHeight: 22 }
                PC3.Slider { Layout.fillWidth: true; value: 0.4 } PC3.Label { text: "40%" } }
            RowLayout { Kirigami.Icon { source: "audio-input-microphone"; implicitWidth: 22; implicitHeight: 22 }
                PC3.Slider { Layout.fillWidth: true; value: 1.0 } PC3.Label { text: "100%" } }
            PC3.Switch { text: "Raise maximum volume" }
            PC3.CheckBox { text: "Play sound when changing volume"; checked: true }
            PC3.RadioButton { text: "Speakers"; checked: true }
            PC3.RadioButton { text: "Headphones" }
            PC3.TextField { Layout.fillWidth: true; placeholderText: "Search…" }
            PC3.ComboBox { Layout.fillWidth: true; model: ["Built-in Audio Analog Stereo", "HDMI"] }
            PC3.ProgressBar { Layout.fillWidth: true; value: 0.6 }
            PC3.ItemDelegate { Layout.fillWidth: true; text: "Highlighted row"; highlighted: true; icon.name: "audio-card" }
            RowLayout { PC3.Button { text: "Cancel" } PC3.Button { text: "Apply"; icon.name: "dialog-ok-apply" } }
            Item { Layout.fillHeight: true }
        }
    }

    // Tooltip en een kleine kaart (widgets/background)
    KSvg.FrameSvgItem {
        imagePath: "widgets/tooltip"
        x: 60; y: 60; width: 300; height: 80
        PC3.Label { anchors.centerIn: parent; text: "Quick menu\nWi-Fi, sound, Bluetooth and more" }
    }
    KSvg.FrameSvgItem {
        imagePath: "widgets/background"
        x: 60; y: 180; width: 360; height: 260
        PC3.Label { anchors.centerIn: parent; text: "widgets/background" }
    }
    KSvg.FrameSvgItem {
        imagePath: "dialogs/background"
        x: 60; y: 470; width: 360; height: 150
        PC3.Label { anchors.centerIn: parent; text: "dialogs/background (small)" }
    }
}
'''


def main() -> int:
    app = QApplication(sys.argv)
    view = QQuickView()
    qml = Path(f"/tmp/proef-plasma-{THEMA}.qml")
    qml.write_text(QML.replace("THEMA_DONKER", "true" if THEMA == "donker" else "false"), encoding="utf-8")
    view.setSource(QUrl.fromLocalFile(str(qml)))
    for fout in view.errors():
        print("QML:", fout.toString())
    if view.status() != QQuickView.Status.Ready:
        print("Plasma-proef laadt niet")
        return 1
    view.resize(1100, 760)
    view.show()

    def klaar():
        try:
            view.grabWindow().save(str(UIT / f"plasma-{THEMA}.png"))
        finally:
            app.quit()

    QTimer.singleShot(2000, klaar)
    app.exec()
    print("klaar:", UIT / f"plasma-{THEMA}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
