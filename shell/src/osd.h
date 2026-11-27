// De schermmelding bij de toetsen voor volume, helderheid, microfoon, wifi, bluetooth en touchpad (OSD).
//
// In Plasma zit die in plasmashell: KDE-diensten (het geluid, powerdevil, kded) roepen org.kde.osdService
// /org/kde/osdService aan op org.kde.plasmashell. bugos-shell heeft die naam (zie Schil), dus dezelfde aanroepen komen
// hier binnen; de QML toont ze (onderaan in het midden, even). Dezelfde namen als in plasma-workspace Plasma/6.5
// (shell/osd.h), ook de seinen osdProgress en osdText waar het vergrendelscherm van KDE naar luistert.
#pragma once

#include <QObject>
#include <QRect>
#include <QString>

class Osd : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.kde.osdService")
    Q_PROPERTY(QString icoon READ icoon NOTIFY getoond)
    Q_PROPERTY(QString tekst READ tekst NOTIFY getoond)
    Q_PROPERTY(int waarde READ waarde NOTIFY getoond)        // -1: alleen tekst, geen balk
    Q_PROPERTY(int maximum READ maximum NOTIFY getoond)
public:
    explicit Osd(QObject *ouder = nullptr);
    bool aanmelden();
    QString icoon() const { return m_icoon; }
    QString tekst() const { return m_tekst; }
    int waarde() const { return m_waarde; }
    int maximum() const { return m_maximum; }

public Q_SLOTS:
    void brightnessChanged(int percent);
    void screenBrightnessChanged(int percent, const QString &displayId, const QString &displayLabel, int priority,
                                 const QRect &screenRect);
    void keyboardBrightnessChanged(int percent);
    void volumeChanged(int percent);
    void volumeChanged(int percent, int maximumPercent);
    void microphoneVolumeChanged(int percent);
    void mediaPlayerVolumeChanged(int percent, const QString &playerName, const QString &playerIconName);
    void kbdLayoutChanged(const QString &layoutName);
    void virtualDesktopChanged(const QString &currentVirtualDesktopName);
    void touchpadEnabledChanged(bool touchpadEnabled);
    void wifiEnabledChanged(bool wifiEnabled);
    void bluetoothEnabledChanged(bool bluetoothEnabled);
    void wwanEnabledChanged(bool wwanEnabled);
    void virtualKeyboardEnabledChanged(bool virtualKeyboardEnabled);
    void powerManagementInhibitedChanged(bool inhibited);
    void powerProfileChanged(const QString &profile);
    void showText(const QString &icon, const QString &text);

Q_SIGNALS:
    void osdProgress(const QString &icon, const int percent, const int maximumPercent, const QString &additionalText);
    void osdText(const QString &icon, const QString &text);
    void getoond();   // voor de QML: er is iets nieuws te tonen

private:
    void balk(const QString &icoon, int waarde, int maximum, const QString &tekst = QString());
    QString m_icoon, m_tekst;
    int m_waarde = -1;
    int m_maximum = 100;
};
