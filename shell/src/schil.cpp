#include "schil.h"

#include <QDBusConnection>
#include <QDBusMessage>
#include <QMargins>
#include <QTimer>
#include <QWindow>

#include <memory>

#ifdef BUGOS_LAYERSHELL
#include <LayerShellQt/Window>
#endif

Schil::Schil(QObject *ouder)
    : QObject(ouder)
{
}

bool Schil::aanmelden()
{
    auto bus = QDBusConnection::sessionBus();
    if (!bus.isConnected())
        return false;
    bus.registerObject(QStringLiteral("/PlasmaShell"), this, QDBusConnection::ExportScriptableSlots);
    if (bus.registerService(QStringLiteral("org.kde.plasmashell")))
        return true;
    // De naam is (nog) van een ander: een Plasma die net stopt, of die er per ongeluk ook is. Zonder die naam doet de
    // Windows-toets niets (KWin roept activateLauncherMenu aan op org.kde.plasmashell). Elke twee seconden opnieuw
    // proberen, een minuut lang.
    auto *klok = new QTimer(this);
    klok->setInterval(2000);
    auto pogingen = std::make_shared<int>(0);
    connect(klok, &QTimer::timeout, this, [klok, pogingen]() {
        if (QDBusConnection::sessionBus().registerService(QStringLiteral("org.kde.plasmashell")) || ++*pogingen >= 30)
            klok->deleteLater();
    });
    klok->start();
    return false;
}

void Schil::activateLauncherMenu()
{
    Q_EMIT startmenu();
}

void Schil::toggleDashboard()
{
    Q_EMIT startmenu();
}

void Schil::showDesktop(bool tonen)
{
    Q_EMIT bureaublad(tonen);
}

bool Schil::heeftLagen() const
{
#ifdef BUGOS_LAYERSHELL
    return qEnvironmentVariable("XDG_SESSION_TYPE") == QLatin1String("wayland")
        || qEnvironmentVariableIsSet("WAYLAND_DISPLAY");
#else
    return false;
#endif
}

bool Schil::laag(QWindow *venster, const QString &soort, int marge)
{
#ifdef BUGOS_LAYERSHELL
    if (!venster || !heeftLagen())
        return false;
    using W = LayerShellQt::Window;
    W *l = W::get(venster);
    if (!l)
        return false;
    l->setScope(QStringLiteral("bugos-") + soort);
#ifdef BUGOS_LAYERSHELL_SCHERM
    // De taakbalk en de achtergrond horen bij één scherm: vast aan dat scherm, niet 'waar de compositor wil'. Zonder
    // dit kwamen de taakbalken van alle schermen soms op één scherm terecht, op elkaar gestapeld (2026-11).
    if (soort == QLatin1String("paneel") || soort == QLatin1String("achtergrond"))
        l->setScreen(venster->screen());
#endif
    if (soort == QLatin1String("paneel")) {
        l->setLayer(W::LayerTop);
        l->setAnchors(W::Anchors(W::AnchorBottom | W::AnchorLeft | W::AnchorRight));
        l->setExclusiveZone(venster->height());
        l->setKeyboardInteractivity(W::KeyboardInteractivityOnDemand);
    } else if (soort == QLatin1String("links") || soort == QLatin1String("rechts")) {
        l->setLayer(W::LayerTop);
        l->setAnchors(W::Anchors(W::AnchorBottom | (soort == QLatin1String("links") ? W::AnchorLeft : W::AnchorRight)));
        l->setMargins(QMargins(marge, 0, marge, marge));
        l->setExclusiveZone(0);
        // Het startmenu moet je kunnen intypen (zoeken), ook als het met de Meta-toets openging.
        l->setKeyboardInteractivity(W::KeyboardInteractivityExclusive);
    } else if (soort == QLatin1String("melding")) {
        l->setLayer(W::LayerOverlay);
        l->setAnchors(W::Anchors(W::AnchorBottom | W::AnchorRight));
        l->setMargins(QMargins(0, 0, marge, marge));
        l->setExclusiveZone(0);
        l->setKeyboardInteractivity(W::KeyboardInteractivityNone);
    } else if (soort == QLatin1String("osd")) {
        l->setLayer(W::LayerOverlay);
        l->setAnchors(W::Anchors(W::AnchorBottom));
        l->setMargins(QMargins(0, 0, 0, marge));
        l->setExclusiveZone(0);
        l->setKeyboardInteractivity(W::KeyboardInteractivityNone);
    } else if (soort == QLatin1String("achtergrond")) {
        l->setLayer(W::LayerBackground);
        l->setAnchors(W::Anchors(W::AnchorTop | W::AnchorBottom | W::AnchorLeft | W::AnchorRight));
        l->setExclusiveZone(-1);
        l->setKeyboardInteractivity(W::KeyboardInteractivityNone);
    } else if (soort == QLatin1String("menu")) {
        l->setLayer(W::LayerOverlay);
        l->setAnchors(W::Anchors(W::AnchorTop | W::AnchorLeft));
        l->setMargins(QMargins(marge, marge, 0, 0));
        l->setExclusiveZone(0);
        l->setKeyboardInteractivity(W::KeyboardInteractivityExclusive);
    } else if (soort == QLatin1String("vangnet")) {
        l->setLayer(W::LayerTop);
        l->setAnchors(W::Anchors(W::AnchorTop | W::AnchorBottom | W::AnchorLeft | W::AnchorRight));
        l->setExclusiveZone(-1);
        l->setKeyboardInteractivity(W::KeyboardInteractivityNone);
    } else {
        return false;
    }
    return true;
#else
    Q_UNUSED(venster)
    Q_UNUSED(soort)
    Q_UNUSED(marge)
    return false;
#endif
}

bool Schil::plaats(QWindow *venster, int x, int y)
{
#ifdef BUGOS_LAYERSHELL
    if (!venster || !heeftLagen())
        return false;
    LayerShellQt::Window *l = LayerShellQt::Window::get(venster);
    if (!l)
        return false;
    l->setMargins(QMargins(qMax(0, x), qMax(0, y), 0, 0));
    return true;
#else
    if (venster)
        venster->setPosition(x, y);
    return false;
#endif
}

void Schil::bureaubladTonen(bool tonen)
{
    QDBusMessage m = QDBusMessage::createMethodCall(QStringLiteral("org.kde.KWin"), QStringLiteral("/KWin"),
                                                    QStringLiteral("org.kde.KWin"), QStringLiteral("showDesktop"));
    m << tonen;
    QDBusConnection::sessionBus().call(m, QDBus::NoBlock);
}
