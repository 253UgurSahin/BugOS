#include "schil.h"

#include <QDBusConnection>
#include <QDBusArgument>
#include <QDBusConnectionInterface>
#include <QDBusMessage>
#include <QDBusMetaType>
#include <QDBusServiceWatcher>
#include <QGuiApplication>
#include <QMargins>
#include <QScreen>
#include <QTimer>
#include <QWindow>

#include <memory>

#ifdef BUGOS_LAYERSHELL
#include <LayerShellQt/Window>
#endif

// Een sneltoets zoals kglobalaccel hem over D-Bus stuurt: (ai), een rijtje van vier toetscodes (Qt-codes, 0 = leeg).
struct Sneltoets {
    QList<int> codes;
};
Q_DECLARE_METATYPE(Sneltoets)
static QDBusArgument &operator<<(QDBusArgument &arg, const Sneltoets &t)
{
    arg.beginStructure();
    arg << t.codes;
    arg.endStructure();
    return arg;
}
static const QDBusArgument &operator>>(const QDBusArgument &arg, Sneltoets &t)
{
    arg.beginStructure();
    arg >> t.codes;
    arg.endStructure();
    return arg;
}

namespace {
const QString KGLOBALACCEL = QStringLiteral("org.kde.kglobalaccel");
// Dezelfde namen als Plasma (shellcorona.cpp): een eigen keuze in Systeeminstellingen > Sneltoetsen geldt zo ook hier.
const QStringList STARTMENU_ACTIE{QStringLiteral("plasmashell"), QStringLiteral("activate application launcher"),
                                  QStringLiteral("plasmashell"), QStringLiteral("Activate Application Launcher")};
// kglobalaccel: SetShortcutFlag (kglobalaccel_interface): IsDefault = 1, SetPresent = 2.
constexpr uint IS_DEFAULT = 1;
constexpr uint SET_PRESENT = 2;
}

Schil::Schil(QObject *ouder)
    : QObject(ouder)
{
    connect(qGuiApp, &QGuiApplication::primaryScreenChanged, this, &Schil::hoofdSchermVeranderd);
}

void Schil::sneltoetsenAanmelden()
{
    qDBusRegisterMetaType<Sneltoets>();
    qDBusRegisterMetaType<QList<Sneltoets>>();
    auto bus = QDBusConnection::sessionBus();
    // Het signaal van kglobalaccel als de sneltoets wordt ingedrukt (ook als hij er nu nog niet is).
    bus.connect(KGLOBALACCEL, QStringLiteral("/component/plasmashell"), QStringLiteral("org.kde.kglobalaccel.Component"),
                QStringLiteral("globalShortcutPressed"), this, SLOT(sneltoetsIngedrukt(QString, QString, qlonglong)));
    auto aanmelden = [bus]() mutable {
        // Alleen de Meta-toets (Qt::Key_Meta, zoals kglobalaccel hem bij 'alleen Meta' meldt), en Alt+F1.
        const QList<Sneltoets> toetsen{Sneltoets{{int(Qt::Key_Meta), 0, 0, 0}},
                                       Sneltoets{{int(Qt::ALT | Qt::Key_F1), 0, 0, 0}}};
        auto bericht = [](const QString &methode) {
            return QDBusMessage::createMethodCall(KGLOBALACCEL, QStringLiteral("/kglobalaccel"),
                                                  QStringLiteral("org.kde.KGlobalAccel"), methode);
        };
        QDBusMessage registreer = bericht(QStringLiteral("doRegister"));
        registreer << STARTMENU_ACTIE;
        // Zoals KGlobalAccel::setDefaultShortcut en daarna setShortcut (met 'autoloading'): eerst de standaard, dan
        // actief maken. Had je zelf iets anders gekozen, dan houdt kglobalaccel dat (het antwoord is wat er nu geldt).
        QDBusMessage standaard = bericht(QStringLiteral("setShortcutKeys"));
        standaard << STARTMENU_ACTIE << QVariant::fromValue(toetsen) << IS_DEFAULT;
        QDBusMessage actief = bericht(QStringLiteral("setShortcutKeys"));
        actief << STARTMENU_ACTIE << QVariant::fromValue(toetsen) << SET_PRESENT;
        // Op volgorde (D-Bus houdt die vast), zonder te wachten: kglobalaccel zit in KWin, en die mag de schil nooit
        // laten hangen.
        bus.asyncCall(registreer);
        bus.asyncCall(standaard);
        bus.asyncCall(actief);
    };
    auto *wachter = new QDBusServiceWatcher(KGLOBALACCEL, bus, QDBusServiceWatcher::WatchForRegistration, this);
    connect(wachter, &QDBusServiceWatcher::serviceRegistered, this, aanmelden);
    if (bus.interface() && bus.interface()->isServiceRegistered(KGLOBALACCEL))
        aanmelden();
}

void Schil::sneltoetsIngedrukt(const QString &onderdeel, const QString &actie, qlonglong tijd)
{
    Q_UNUSED(tijd)
    if (onderdeel == STARTMENU_ACTIE.at(0) && actie == STARTMENU_ACTIE.at(1))
        Q_EMIT startmenu();
}

QString Schil::hoofdSchermNaam() const
{
    const QScreen *s = QGuiApplication::primaryScreen();
    return s ? s->name() : QString();
}

bool Schil::aanmelden()
{
    auto bus = QDBusConnection::sessionBus();
    if (!bus.isConnected())
        return false;
    bus.registerObject(QStringLiteral("/PlasmaShell"), this, QDBusConnection::ExportScriptableSlots);
    sneltoetsenAanmelden();
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
        // De taakbalk kan van grootte veranderen (Instellingen > Uiterlijk > Taakbalk): vensters laten dan ook
        // precies zoveel ruimte vrij, anders vielen ze achter een grotere taakbalk.
        // (Zonder Qt::UniqueConnection: die werkt niet met een lambda, en laag() komt één keer per venster.)
        QObject::connect(venster, &QWindow::heightChanged, l, [l](int h) { l->setExclusiveZone(h); });
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
