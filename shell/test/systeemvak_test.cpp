// Test van het systeemvak van bugos-shell (Systeemvak, Vakwachter, de menu's) met twee nep-apps op een eigen D-Bus.
// Draai binnen dbus-run-session (tools/test_shell_dbus.sh doet dat). Eén programma met twee verbindingen met de bus:
// de schil (de host, en zelf de watcher, want er is geen kded) en de nep-apps (een eigen naam op de bus).
//   app 1: KDE-stijl (een dienstnaam), pictogram als naam, een menu met een scheiding, een vinkje, een verborgen regel
//          en een sneltoets-teken (_Openen)
//   app 2: Ayatana-stijl (alleen een pad), pictogram als pixels (IconPixmap)
#include "../src/dbusmenu.h"
#include "../src/systeemvak.h"

#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusMessage>
#include <QDBusMetaType>
#include <QDBusObjectPath>
#include <QElapsedTimer>
#include <QGuiApplication>
#include <QThread>
#include <QtEndian>

#include <cstdio>
#include <functional>

static int fouten = 0;
static void klopt(bool goed, const char *wat)
{
    std::printf("%s%s\n", goed ? "OK    " : "FOUT  ", wat);
    if (!goed)
        ++fouten;
}

static bool wacht(const std::function<bool()> &klaar, int ms = 5000)
{
    QElapsedTimer t;
    t.start();
    while (!klaar() && t.elapsed() < ms)
        QCoreApplication::processEvents(QEventLoop::AllEvents, 20);
    return klaar();
}

class NepItem : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.kde.StatusNotifierItem")
    Q_PROPERTY(QString Id READ id)
    Q_PROPERTY(QString Title READ title)
    Q_PROPERTY(QString Status READ status)
    Q_PROPERTY(QString Category READ category)
    Q_PROPERTY(QString IconName READ iconName)
    Q_PROPERTY(VakPixmaps IconPixmap READ iconPixmap)
    Q_PROPERTY(bool ItemIsMenu READ itemIsMenu)
    Q_PROPERTY(QDBusObjectPath Menu READ menu)
    Q_PROPERTY(VakTooltip ToolTip READ toolTip)
public:
    QString titel = QStringLiteral("Nep-app");
    QString naam = QStringLiteral("steam");
    VakPixmaps pixmaps;
    QString menuPad = QStringLiteral("/MenuBar");
    int geactiveerd = 0;

    QString id() const { return QStringLiteral("nep"); }
    QString title() const { return titel; }
    QString status() const { return QStringLiteral("Active"); }
    QString category() const { return QStringLiteral("ApplicationStatus"); }
    QString iconName() const { return naam; }
    VakPixmaps iconPixmap() const { return pixmaps; }
    bool itemIsMenu() const { return false; }
    QDBusObjectPath menu() const { return QDBusObjectPath(menuPad); }
    VakTooltip toolTip() const { return VakTooltip{QString(), {}, titel, QStringLiteral("Draait")}; }

public Q_SLOTS:
    Q_SCRIPTABLE void Activate(int, int) { ++geactiveerd; }
    Q_SCRIPTABLE void SecondaryActivate(int, int) {}
    Q_SCRIPTABLE void ContextMenu(int, int) {}
    Q_SCRIPTABLE void Scroll(int, const QString &) {}
};

class NepMenu : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "com.canonical.dbusmenu")
public:
    QList<int> geklikt;
    int voorbereid = 0;

public Q_SLOTS:
    Q_SCRIPTABLE uint GetLayout(int, int, const QStringList &, MenuOnderdeel &laag)
    {
        auto regel = [](int id, QVariantMap e) { MenuOnderdeel o; o.id = id; o.eigenschappen = e; return o; };
        laag = MenuOnderdeel();
        laag.kinderen << regel(1, {{QStringLiteral("label"), QStringLiteral("_Openen")}})
                      << regel(2, {{QStringLiteral("type"), QStringLiteral("separator")}})
                      << regel(3, {{QStringLiteral("label"), QStringLiteral("Stil")},
                                   {QStringLiteral("toggle-type"), QStringLiteral("checkmark")},
                                   {QStringLiteral("toggle-state"), 1}})
                      << regel(4, {{QStringLiteral("label"), QStringLiteral("Verborgen")}, {QStringLiteral("visible"), false}})
                      << regel(5, {{QStringLiteral("label"), QStringLiteral("Stoppen")}, {QStringLiteral("enabled"), false}});
        MenuOnderdeel sub = regel(6, {{QStringLiteral("label"), QStringLiteral("Meer")},
                                      {QStringLiteral("children-display"), QStringLiteral("submenu")}});
        sub.kinderen << regel(7, {{QStringLiteral("label"), QStringLiteral("Over__app")}});
        laag.kinderen << sub;
        return 1;
    }
    Q_SCRIPTABLE bool AboutToShow(int) { ++voorbereid; return false; }
    Q_SCRIPTABLE void Event(int id, const QString &soort, const QDBusVariant &, uint)
    {
        if (soort == QLatin1String("clicked"))
            geklikt << id;
    }
};

int main(int argc, char *argv[])
{
    qputenv("QT_QPA_PLATFORM", "offscreen");
    QGuiApplication app(argc, argv);
    registreerDbusmenuTypen();

    QDBusConnection schilBus = QDBusConnection::sessionBus();
    QDBusConnection appBus = QDBusConnection::connectToBus(QDBusConnection::SessionBus, QStringLiteral("nep-app"));
    klopt(schilBus.isConnected() && appBus.isConnected(), "twee verbindingen met de (eigen) sessiebus");

    NepItem item1;
    NepMenu menu1;
    NepItem item2;
    item2.titel = QStringLiteral("Pixels");
    item2.naam.clear();
    item2.menuPad = QStringLiteral("/");
    VakPixmap p;
    p.breedte = p.hoogte = 16;
    p.pixels.resize(16 * 16 * 4);
    auto *px = reinterpret_cast<quint32 *>(p.pixels.data());
    for (int i = 0; i < 16 * 16; ++i)
        px[i] = qToBigEndian<quint32>(0xFFDE2F3E);   // BugOS-rood, ondoorzichtig
    item2.pixmaps << p;
    // De nep-apps op een eigen draad, zoals echte apps eigen programma's zijn: de schil vraagt een menu met een
    // blokkerende aanroep, en op dezelfde draad zou de app dan nooit kunnen antwoorden.
    QThread appDraad;
    item1.moveToThread(&appDraad);
    menu1.moveToThread(&appDraad);
    item2.moveToThread(&appDraad);
    appDraad.start();
    const auto export_ = QDBusConnection::ExportAllProperties | QDBusConnection::ExportScriptableSlots;
    appBus.registerObject(QStringLiteral("/StatusNotifierItem"), &item1, export_);
    appBus.registerObject(QStringLiteral("/MenuBar"), &menu1, QDBusConnection::ExportScriptableSlots);
    appBus.registerObject(QStringLiteral("/org/ayatana/NotificationItem/pixels"), &item2, export_);

    Systeemvak vak(schilBus);
    vak.start();
    klopt(schilBus.interface()->isServiceRegistered(QStringLiteral("org.kde.StatusNotifierWatcher")),
          "zonder kded is bugos-shell zelf de watcher");

    auto meld = [&](const QString &wat) {
        QDBusMessage m = QDBusMessage::createMethodCall(QStringLiteral("org.kde.StatusNotifierWatcher"),
                                                        QStringLiteral("/StatusNotifierWatcher"),
                                                        QStringLiteral("org.kde.StatusNotifierWatcher"),
                                                        QStringLiteral("RegisterStatusNotifierItem"));
        m << wat;
        return appBus.call(m, QDBus::BlockWithGui).type() == QDBusMessage::ReplyMessage;
    };
    klopt(meld(appBus.baseService()), "app 1 meldt zich aan met zijn dienstnaam (KDE-stijl)");
    klopt(meld(QStringLiteral("/org/ayatana/NotificationItem/pixels")), "app 2 meldt zich aan met alleen een pad (Ayatana-stijl)");

    auto rol = [&](int rij, int r) { return vak.data(vak.index(rij), r); };
    wacht([&] { return vak.rowCount() == 2 && !rol(1, Systeemvak::IcoonRol).toString().isEmpty()
                       && !rol(0, Systeemvak::TitelRol).toString().isEmpty(); });
    klopt(vak.rowCount() == 2, "twee pictogrammen in het systeemvak");
    klopt(rol(0, Systeemvak::TitelRol).toString() == QLatin1String("Nep-app")
              && rol(0, Systeemvak::IcoonRol).toString() == QLatin1String("image://icon/steam"),
          "app 1: titel en pictogram uit het thema");
    klopt(rol(0, Systeemvak::UitlegRol).toString() == QLatin1String("Nep-app\nDraait"), "app 1: de uitleg (tooltip)");
    klopt(rol(0, Systeemvak::HeeftMenuRol).toBool() && !rol(1, Systeemvak::HeeftMenuRol).toBool(),
          "app 1 heeft een menu, app 2 niet (Menu = /)");
    const QString icoon2 = rol(1, Systeemvak::IcoonRol).toString();
    klopt(icoon2.startsWith(QLatin1String("image://vak/")), "app 2: het pictogram uit de pixels (IconPixmap)");
    VakPictogrammen pictogrammen;
    QSize maat;
    const QImage beeld = pictogrammen.requestImage(icoon2.mid(12), &maat, QSize());
    klopt(maat == QSize(16, 16) && beeld.pixel(3, 3) == 0xFFDE2F3E, "app 2: de pixels komen goed over (ARGB, netwerkvolgorde)");

    const QVariantList m = vak.menu(0);
    QStringList teksten;
    for (const QVariant &r : m)
        teksten << r.toMap().value(QStringLiteral("tekst")).toString();
    klopt(menu1.voorbereid == 1, "het menu krijgt eerst AboutToShow (sommige apps vullen het dan pas)");
    klopt(teksten == QStringList({QStringLiteral("Openen"), QString(), QStringLiteral("Stil"), QStringLiteral("Stoppen"),
                                  QStringLiteral("Meer")}),
          "het menu: zonder _ (sneltoets), zonder verborgen regel");
    klopt(m.size() == 5 && m.at(1).toMap().value(QStringLiteral("scheiding")).toBool()
              && m.at(2).toMap().value(QStringLiteral("gevinkt")).toBool()
              && !m.at(3).toMap().value(QStringLiteral("aan")).toBool(),
          "het menu: scheiding, vinkje en een regel die (nu) niet kan");
    const QVariantList sub = m.size() == 5 ? m.at(4).toMap().value(QStringLiteral("kinderen")).toList() : QVariantList();
    klopt(sub.size() == 1 && sub.at(0).toMap().value(QStringLiteral("tekst")).toString() == QLatin1String("Over_app"),
          "het menu: een submenu, en __ blijft één _");
    klopt(vak.menu(1).isEmpty(), "app zonder menu: leeg (dan vraagt de schil de app zelf om zijn menu)");

    vak.menuKlik(0, 3);
    klopt(wacht([&] { return menu1.geklikt == QList<int>{3}; }), "een klik in het menu gaat naar de app (Event clicked)");
    klopt(vak.activeer(0, 10, 10) && wacht([&] { return item1.geactiveerd == 1; }), "klikken op het pictogram: Activate");

    item1.titel = QStringLiteral("Nieuwe titel");
    appBus.send(QDBusMessage::createSignal(QStringLiteral("/StatusNotifierItem"), QStringLiteral("org.kde.StatusNotifierItem"),
                                           QStringLiteral("NewTitle")));
    klopt(wacht([&] { return rol(0, Systeemvak::TitelRol).toString() == QLatin1String("Nieuwe titel"); }),
          "NewTitle: de schil leest de app opnieuw");

    // De verbinding gaat pas echt dicht als niemand hem meer vasthoudt (ook appBus hier niet).
    appBus = QDBusConnection(QStringLiteral("niets"));
    QDBusConnection::disconnectFromBus(QStringLiteral("nep-app"));
    klopt(wacht([&] { return vak.rowCount() == 0; }), "de apps stoppen: hun pictogrammen gaan weg");

    appDraad.quit();
    appDraad.wait();
    std::printf("%d fout(en).\n", fouten);
    return fouten ? 1 : 0;
}

#include "systeemvak_test.moc"
