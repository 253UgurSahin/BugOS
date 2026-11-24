#include "osd.h"

#include <QDBusConnection>
#include <QLocale>

namespace {
// Nederlands of Engels (zoals de rest van BugOS); de schermmelding is kort, dus een paar woorden.
QString tr(const char *nl, const char *en)
{
    static const bool nederlands = QLocale().name().startsWith(QLatin1String("nl"));
    return QString::fromUtf8(nederlands ? nl : en);
}
} // namespace

Osd::Osd(QObject *ouder)
    : QObject(ouder)
{
}

bool Osd::aanmelden()
{
    return QDBusConnection::sessionBus().registerObject(QStringLiteral("/org/kde/osdService"), this,
                                                        QDBusConnection::ExportAllSlots | QDBusConnection::ExportAllSignals);
}

void Osd::balk(const QString &icoon, int waarde, int maximum, const QString &tekst)
{
    m_icoon = icoon;
    m_waarde = qMax(0, waarde);
    m_maximum = maximum > 0 ? maximum : 100;
    m_tekst = tekst;
    Q_EMIT osdProgress(icoon, waarde, m_maximum, tekst);
    Q_EMIT getoond();
}

void Osd::showText(const QString &icon, const QString &text)
{
    m_icoon = icon;
    m_tekst = text;
    m_waarde = -1;
    Q_EMIT osdText(icon, text);
    Q_EMIT getoond();
}

void Osd::brightnessChanged(int percent)
{
    balk(QStringLiteral("video-display-brightness"), percent, 100);
}

void Osd::screenBrightnessChanged(int percent, const QString &, const QString &displayLabel, int, const QRect &)
{
    balk(QStringLiteral("video-display-brightness"), percent, 100, displayLabel);
}

void Osd::keyboardBrightnessChanged(int percent)
{
    balk(QStringLiteral("input-keyboard-brightness"), percent, 100);
}

void Osd::volumeChanged(int percent)
{
    volumeChanged(percent, 100);
}

void Osd::volumeChanged(int percent, int maximumPercent)
{
    if (percent <= 0) {
        showText(QStringLiteral("audio-volume-muted"), tr("Geluid uit", "Sound off"));
        return;
    }
    const QString icoon = percent <= 25 ? QStringLiteral("audio-volume-low")
        : percent <= 75                 ? QStringLiteral("audio-volume-medium")
        : percent <= 100                ? QStringLiteral("audio-volume-high")
                                        : QStringLiteral("audio-volume-high-warning");
    balk(icoon, percent, maximumPercent);
}

void Osd::microphoneVolumeChanged(int percent)
{
    if (percent <= 0) {
        showText(QStringLiteral("microphone-sensitivity-muted"), tr("Microfoon uit", "Microphone off"));
        return;
    }
    balk(percent <= 25 ? QStringLiteral("microphone-sensitivity-low")
         : percent <= 75 ? QStringLiteral("microphone-sensitivity-medium")
                         : QStringLiteral("microphone-sensitivity-high"),
         percent, 100);
}

void Osd::mediaPlayerVolumeChanged(int percent, const QString &playerName, const QString &playerIconName)
{
    if (percent == 0)
        showText(playerIconName, playerName + tr(": geluid uit", ": sound off"));
    else
        balk(playerIconName, percent, 100, playerName);
}

void Osd::kbdLayoutChanged(const QString &layoutName)
{
    showText(QStringLiteral("input-keyboard"), layoutName);
}

void Osd::virtualDesktopChanged(const QString &currentVirtualDesktopName)
{
    showText(QStringLiteral("virtual-desktops"), currentVirtualDesktopName);
}

void Osd::touchpadEnabledChanged(bool aan)
{
    showText(aan ? QStringLiteral("input-touchpad-on") : QStringLiteral("input-touchpad-off"),
             aan ? tr("Touchpad aan", "Touchpad on") : tr("Touchpad uit", "Touchpad off"));
}

void Osd::wifiEnabledChanged(bool aan)
{
    showText(aan ? QStringLiteral("network-wireless-on") : QStringLiteral("network-wireless-off"),
             aan ? tr("Wifi aan", "Wi-Fi on") : tr("Wifi uit", "Wi-Fi off"));
}

void Osd::bluetoothEnabledChanged(bool aan)
{
    showText(aan ? QStringLiteral("preferences-system-bluetooth") : QStringLiteral("preferences-system-bluetooth-inactive"),
             aan ? tr("Bluetooth aan", "Bluetooth on") : tr("Bluetooth uit", "Bluetooth off"));
}

void Osd::wwanEnabledChanged(bool aan)
{
    showText(aan ? QStringLiteral("network-mobile-on") : QStringLiteral("network-mobile-off"),
             aan ? tr("Mobiel internet aan", "Mobile internet on") : tr("Mobiel internet uit", "Mobile internet off"));
}

void Osd::virtualKeyboardEnabledChanged(bool aan)
{
    showText(aan ? QStringLiteral("input-keyboard-virtual-on") : QStringLiteral("input-keyboard-virtual-off"),
             aan ? tr("Schermtoetsenbord aan", "On-screen keyboard on") : tr("Schermtoetsenbord uit", "On-screen keyboard off"));
}

void Osd::powerManagementInhibitedChanged(bool geblokkeerd)
{
    showText(geblokkeerd ? QStringLiteral("system-suspend-inhibited") : QStringLiteral("system-suspend-uninhibited"),
             geblokkeerd ? tr("Slaapstand en vergrendelen staan even uit", "Sleep and locking are paused")
                         : tr("Slaapstand en vergrendelen werken weer", "Sleep and locking work again"));
}

void Osd::powerProfileChanged(const QString &profiel)
{
    if (profiel == QLatin1String("power-saver"))
        showText(QStringLiteral("battery-profile-powersave"), tr("Zuinig", "Power saving"));
    else if (profiel == QLatin1String("performance"))
        showText(QStringLiteral("battery-profile-performance"), tr("Volle kracht", "Full power"));
    else
        showText(QStringLiteral("speedometer"), tr("Gebalanceerd", "Balanced"));
}
