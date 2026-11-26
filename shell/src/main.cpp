// bugos-shell: de eigen schil van BugOS (taakbalk, startmenu, snelmenu, klok, achtergrond en meldingen).
// Zie docs/STANDALONE.md. De QML staat in /usr/share/bugos/shell/Shell.qml.
//
//   bugos-shell                   de schil (in de sessie 'BugOS (nieuwe schil, proef)')
//   bugos-shell --qml <pad>       een ander QML-bestand (tests, ontwikkelen)
//   bugos-shell --geen-dbus       zonder de D-Bus-namen (naast een draaiende Plasma, tests)
//   bugos-shell --stop-na <ms>    na zoveel milliseconden stoppen (de rooktest in CI)

#include "instellingen.h"
#include "meldingen.h"
#include "opdracht.h"
#include "osd.h"
#include "schil.h"
#include "systeemvak.h"

#include <QCommandLineParser>
#include <QDir>
#include <QLockFile>
#include <QStandardPaths>
#include <QFileInfo>
#include <QGuiApplication>
#include <QDBusConnection>
#include <QIcon>
#include <QMimeDatabase>
#include <QSettings>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickImageProvider>
#include <QTimer>

#include <cstdio>

// image://icon/<naam of pad>: een pictogram uit het thema (QIcon::fromTheme), of een bestand.
// image://icon/bestand:<pad>: het pictogram van een bestand op het bureaublad (een starter: zijn eigen Icon=,
// een map: een map, anders het pictogram van de soort bestand).
static QIcon bestandIcoon(const QString &pad)
{
    const QFileInfo info(pad);
    if (info.isDir())
        return QIcon::fromTheme(QStringLiteral("folder"));
    if (pad.endsWith(QLatin1String(".desktop"))) {
        QSettings starter(pad, QSettings::IniFormat);
        const QString naam = starter.value(QStringLiteral("Desktop Entry/Icon")).toString();
        if (!naam.isEmpty())
            return naam.startsWith(QLatin1Char('/')) ? QIcon(naam) : QIcon::fromTheme(naam);
    }
    static QMimeDatabase soorten;
    const QMimeType soort = soorten.mimeTypeForFile(info);
    return QIcon::fromTheme(soort.iconName(), QIcon::fromTheme(soort.genericIconName(),
                                                               QIcon::fromTheme(QStringLiteral("text-x-generic"))));
}

class Pictogram : public QQuickImageProvider
{
public:
    Pictogram()
        : QQuickImageProvider(QQuickImageProvider::Pixmap)
    {
    }

    QPixmap requestPixmap(const QString &id, QSize *maat, const QSize &gevraagd) override
    {
        const int b = gevraagd.width() > 0 ? gevraagd.width() : 48;
        const int h = gevraagd.height() > 0 ? gevraagd.height() : b;
        QIcon ic;
        if (id.startsWith(QLatin1String("bestand:")))
            ic = bestandIcoon(id.mid(8));
        else if (id.startsWith(QLatin1Char('/')) && QFileInfo::exists(id))
            ic = QIcon(id);
        else
            ic = QIcon::fromTheme(id, QIcon::fromTheme(QStringLiteral("application-x-executable")));
        const QPixmap pm = ic.pixmap(QSize(b, h));
        if (maat)
            *maat = pm.size();
        return pm;
    }
};

int main(int argc, char *argv[])
{
    QGuiApplication app(argc, argv);
    app.setApplicationName(QStringLiteral("bugos-shell"));
    app.setOrganizationName(QStringLiteral("BugOS"));
    app.setDesktopFileName(QStringLiteral("bugos-shell"));
    // De schil stopt niet als het laatste venster even weg is (een menu dat sluit).
    app.setQuitOnLastWindowClosed(false);

    QCommandLineParser opties;
    opties.addHelpOption();
    QCommandLineOption qmlOptie(QStringLiteral("qml"), QStringLiteral("QML-bestand"), QStringLiteral("pad"),
                                QStringLiteral("/usr/share/bugos/shell/Shell.qml"));
    QCommandLineOption geenDbus(QStringLiteral("geen-dbus"), QStringLiteral("Zonder D-Bus-namen"));
    QCommandLineOption stopNa(QStringLiteral("stop-na"), QStringLiteral("Stoppen na ms"), QStringLiteral("ms"));
    opties.addOptions({qmlOptie, geenDbus, stopNa});
    opties.process(app);

    // Er mag maar één schil tegelijk zijn (per gebruiker). Twee of drie tegelijk gaven twee of drie taakbalken op elkaar
    // (2026-11). Een tweede start stopt meteen; de eerste houdt het slot tot hij stopt (ook na een crash komt het vrij).
    QLockFile slot(QDir(QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation))
                       .filePath(QStringLiteral("bugos-shell.lock")));
    slot.setStaleLockTime(0);   // alleen 'vrij' als de schil die het heeft niet meer draait, nooit na een tijdje
    if (!opties.isSet(geenDbus) && !slot.tryLock(0)) {
        std::fprintf(stderr, "bugos-shell: er draait al een schil; deze stopt\n");
        return 0;
    }

    Opdracht opdracht;
    Meldingen meldingen;
    Schil schil;
    Instellingen instellingen;
    Osd osd;
    Systeemvak systeemvak(QDBusConnection::sessionBus());
    if (!opties.isSet(geenDbus)) {
        // Eerst de meldingen: die zijn nodig vanaf het eerste moment van de sessie.
        if (!meldingen.aanmelden())
            std::fprintf(stderr, "bugos-shell: de meldingendienst is al van een ander programma\n");
        if (!schil.aanmelden())
            std::fprintf(stderr, "bugos-shell: org.kde.plasmashell is al van een ander programma\n");
        osd.aanmelden();   // op dezelfde verbinding als org.kde.plasmashell (Schil)
        systeemvak.start();
    }

    QQmlApplicationEngine engine;
    engine.addImageProvider(QStringLiteral("icon"), new Pictogram);   // dezelfde naam als in StartMenu.qml
    engine.addImageProvider(QStringLiteral("vak"), new VakPictogrammen);
    engine.rootContext()->setContextProperty(QStringLiteral("opdracht"), &opdracht);
    engine.rootContext()->setContextProperty(QStringLiteral("meldingen"), &meldingen);
    engine.rootContext()->setContextProperty(QStringLiteral("schil"), &schil);
    engine.rootContext()->setContextProperty(QStringLiteral("instellingen"), &instellingen);
    engine.rootContext()->setContextProperty(QStringLiteral("systeemvak"), &systeemvak);
    engine.rootContext()->setContextProperty(QStringLiteral("osd"), &osd);
    QObject::connect(&engine, &QQmlApplicationEngine::objectCreationFailed, &app,
                     []() { QCoreApplication::exit(1); }, Qt::QueuedConnection);
    engine.load(QUrl::fromLocalFile(opties.value(qmlOptie)));
    if (engine.rootObjects().isEmpty())
        return 1;

    if (opties.isSet(stopNa)) {
        QTimer::singleShot(opties.value(stopNa).toInt(), &app, []() {
            std::printf("bugos-shell: OK\n");
            std::fflush(stdout);
            QCoreApplication::exit(0);
        });
    }
    return app.exec();
}
