#!/usr/bin/env python3
"""Proefvenster voor de KDE-programmastijl (Kvantum): QtWidgets en Kirigami.

Maakt /uit/kvantum-widgets-<thema>.png (zoals Dolphin, Schijfbeheer, oude KDE-
instellingen) en /uit/kvantum-kirigami-<thema>.png (zoals KDE Instellingen).
De stijl komt uit de omgeving (QT_STYLE_OVERRIDE=kvantum, ~/.config/Kvantum).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl, Qt
from PySide6.QtGui import QAction
from PySide6.QtQuick import QQuickView
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QMenu, QProgressBar, QPushButton, QRadioButton, QSlider,
                               QSpinBox, QTabWidget, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

THEMA = os.environ.get("BUGOS_THEMA", "licht")
UIT = Path(os.environ.get("BUGOS_UIT", "/uit"))

KIRIGAMI = r'''
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Rectangle {
    width: 980; height: 700
    color: Kirigami.Theme.backgroundColor
    RowLayout {
        anchors.fill: parent
        spacing: 0
        // Zijbalk zoals in KDE Instellingen
        Rectangle {
            Layout.fillHeight: true; Layout.preferredWidth: 260
            color: Kirigami.Theme.backgroundColor
            Kirigami.Theme.colorSet: Kirigami.Theme.View
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 8; spacing: 4
                Kirigami.SearchField { Layout.fillWidth: true }
                Repeater {
                    model: [["preferences-desktop-display-randr", "Display Configuration"], ["redshift-status-on", "Night Light"],
                            ["preferences-desktop-sound", "Sound"], ["preferences-system-network", "Wi-Fi & Networking"],
                            ["preferences-desktop-mouse", "Mouse"], ["preferences-desktop-keyboard", "Keyboard"]]
                    delegate: QQC2.ItemDelegate {
                        Layout.fillWidth: true
                        highlighted: index === 0
                        icon.name: modelData[0]
                        text: modelData[1]
                    }
                }
                Item { Layout.fillHeight: true }
            }
        }
        Kirigami.Separator { Layout.fillHeight: true }
        ColumnLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.margins: 20; spacing: 14
            Kirigami.Heading { text: "Display Configuration"; level: 1 }
            Kirigami.InlineMessage { Layout.fillWidth: true; visible: true; type: Kirigami.MessageType.Information
                text: "Changes are applied right away." }
            QQC2.TabBar { QQC2.TabButton { text: "Display" } QQC2.TabButton { text: "Advanced" } }
            Kirigami.FormLayout {
                Layout.fillWidth: true
                QQC2.ComboBox { Kirigami.FormData.label: "Resolution:"; model: ["1920 × 1080 (16:9)", "1280 × 800"] }
                RowLayout { Kirigami.FormData.label: "Scale:"
                    QQC2.Slider { from: 50; to: 300; value: 100; Layout.preferredWidth: 220 }
                    QQC2.SpinBox { from: 50; to: 300; value: 100 } }
                QQC2.Switch { Kirigami.FormData.label: "Night light:"; checked: true; text: "On" }
                QQC2.CheckBox { Kirigami.FormData.label: "Screen tearing:"; checked: true; text: "Allow in fullscreen windows" }
                QQC2.RadioButton { Kirigami.FormData.label: "Legacy apps:"; checked: true; text: "Apply scaling themselves" }
                QQC2.RadioButton { text: "Scaled by the system" }
                QQC2.TextField { Kirigami.FormData.label: "Name:"; placeholderText: "My screen" }
                QQC2.ProgressBar { Kirigami.FormData.label: "Busy:"; value: 0.6; Layout.preferredWidth: 220 }
            }
            Item { Layout.fillHeight: true }
            RowLayout {
                Layout.fillWidth: true
                QQC2.Button { text: "Help"; icon.name: "help-contents" }
                Item { Layout.fillWidth: true }
                QQC2.Button { text: "Defaults"; icon.name: "edit-undo" }
                QQC2.Button { text: "Reset"; icon.name: "edit-reset"; enabled: false }
                QQC2.Button { text: "Apply"; icon.name: "dialog-ok-apply"; highlighted: true }
            }
        }
    }
}
'''


def widgets() -> QWidget:
    w = QWidget()
    w.setWindowTitle("BugOS proef")
    lay = QGridLayout(w)

    knoppen = QGroupBox("Buttons")
    kl = QHBoxLayout(knoppen)
    gewoon = QPushButton("Cancel")
    hoofd = QPushButton("Install")
    hoofd.setDefault(True)
    uit = QPushButton("Disabled")
    uit.setEnabled(False)
    tb = QToolButton()
    tb.setText("Tool")
    tb.setIcon(w.style().standardIcon(w.style().StandardPixmap.SP_DialogOpenButton))
    tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
    for x in (gewoon, hoofd, uit, tb):
        kl.addWidget(x)
    lay.addWidget(knoppen, 0, 0, 1, 2)

    invoer = QGroupBox("Input")
    il = QVBoxLayout(invoer)
    le = QLineEdit()
    le.setPlaceholderText("Search settings")
    cb = QComboBox()
    cb.addItems(["Automatically (recommended)", "Manually"])
    sp = QSpinBox()
    sp.setValue(42)
    sl = QSlider(Qt.Orientation.Horizontal)
    sl.setValue(60)
    pb = QProgressBar()
    pb.setValue(60)
    for x in (le, cb, sp, sl, pb):
        il.addWidget(x)
    lay.addWidget(invoer, 1, 0)

    keuze = QGroupBox("Choices")
    ch = QVBoxLayout(keuze)
    for tekst, aan in (("Show hidden files", True), ("Open folders in a new tab", False)):
        c = QCheckBox(tekst)
        c.setChecked(aan)
        ch.addWidget(c)
    for tekst, aan in (("Light", True), ("Dark", False)):
        r = QRadioButton(tekst)
        r.setChecked(aan)
        ch.addWidget(r)
    lay.addWidget(keuze, 1, 1)

    tabs = QTabWidget()
    lijst = QListWidget()
    lijst.addItems([f"Document {i}.odt" for i in range(1, 30)])
    lijst.setCurrentRow(2)
    tabs.addTab(lijst, "Recent")
    boom = QTreeWidget()
    boom.setHeaderLabels(["Name", "Size"])
    for n in ("Documents", "Pictures", "Music"):
        it = QTreeWidgetItem([n, "1.2 GB"])
        it.addChild(QTreeWidgetItem(["Holiday", "300 MB"]))
        boom.addTopLevelItem(it)
    boom.expandAll()
    tabs.addTab(boom, "Folders")
    tabs.addTab(QLabel("Nothing here"), "Other")
    lay.addWidget(tabs, 2, 0, 1, 2)
    w.resize(760, 640)
    return w


def menu_plaatje(parent: QWidget) -> None:
    m = QMenu(parent)
    for t in ("Open", "Open with…", "Copy", "Move to Trash"):
        m.addAction(QAction(t, m))
    m.addSeparator()
    a = QAction("Show hidden files", m)
    a.setCheckable(True)
    a.setChecked(True)
    m.addAction(a)
    m.popup(parent.mapToGlobal(parent.rect().center()))
    QApplication.processEvents()
    m.grab().save(str(UIT / f"kvantum-menu-{THEMA}.png"))
    m.close()


def main() -> int:
    app = QApplication(sys.argv)
    print("stijl:", app.style().objectName(), "| thema:", THEMA, flush=True)
    w = widgets()
    w.show()
    app.processEvents()
    w.grab().save(str(UIT / f"kvantum-widgets-{THEMA}.png"))
    menu_plaatje(w)

    view = QQuickView()
    view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
    qml = Path(f"/tmp/proef-kirigami-{THEMA}.qml")
    qml.write_text(KIRIGAMI, encoding="utf-8")
    view.setSource(QUrl.fromLocalFile(str(qml)))
    for fout in view.errors():
        print("QML:", fout.toString())
    if view.status() != QQuickView.Status.Ready:
        print("Kirigami-proef laadt niet")
        return 1
    view.resize(980, 700)
    view.show()

    def klaar():
        try:
            view.grabWindow().save(str(UIT / f"kvantum-kirigami-{THEMA}.png"))
        finally:
            app.quit()

    QTimer.singleShot(1500, klaar)
    app.exec()
    print("klaar:", sorted(p.name for p in UIT.glob(f"kvantum-*-{THEMA}.png")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
