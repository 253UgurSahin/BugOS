// bugos-shell: de eigen schil van BugOS (taakbalk, startmenu, snelmenu, klok, achtergrond en meldingen).
// Zie docs/STANDALONE.md. De QML staat in /usr/share/bugos/shell/Shell.qml.
//
//   bugos-shell                   de schil (in de sessie 'BugOS (nieuwe schil, proef)')
//   bugos-shell --qml <pad>       een ander QML-bestand (tests, ontwikkelen)
//   bugos-shell --geen-dbus       zonder de D-Bus-namen (naast een draaiende Plasma, tests)
//   bugos-shell --stop-na <ms>    na zoveel milliseconden stoppen (de rooktest in CI)

#include "meldingen.h"
#include "opdracht.h"
#include "schil.h"

#include <QCommandLineParser>
#include <QFileInfo>
#include <QGuiApplication>
#include <QIcon>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickImageProvider>
#include <QTimer>

#include <cstdio>

// image://icon/<naam of pad>: een pictogram uit het thema (QIcon::fromTheme), of een bestand.
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
        if (id.startsWith(QLatin1Char('/')) && QFileInfo::exists(id))
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
    // De schil leest zijn eigen instellingen (vastgezette apps) met XMLHttpRequest uit ~/.config/bugos.
    qputenv("QML_XHR_ALLOW_FILE_READ", "1");
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

    Opdracht opdracht;
    Meldingen meldingen;
    Schil schil;
    if (!opties.isSet(geenDbus)) {
        // Eerst de meldingen: die zijn nodig vanaf het eerste moment van de sessie.
        if (!meldingen.aanmelden())
            std::fprintf(stderr, "bugos-shell: de meldingendienst is al van een ander programma\n");
        if (!schil.aanmelden())
            std::fprintf(stderr, "bugos-shell: org.kde.plasmashell is al van een ander programma\n");
    }

    QQmlApplicationEngine engine;
    engine.addImageProvider(QStringLiteral("icon"), new Pictogram);   // dezelfde naam als in StartMenu.qml
    engine.rootContext()->setContextProperty(QStringLiteral("opdracht"), &opdracht);
    engine.rootContext()->setContextProperty(QStringLiteral("meldingen"), &meldingen);
    engine.rootContext()->setContextProperty(QStringLiteral("schil"), &schil);
    // Waar de achtergronden staan (images/ en images_dark/). BUGOS_ACHTERGROND_MAP voor een test.
    const QString achtergrond = qEnvironmentVariable("BUGOS_ACHTERGROND_MAP",
                                                     QStringLiteral("/usr/share/wallpapers/bugos/contents"));
    engine.rootContext()->setContextProperty(QStringLiteral("achtergrondMap"), achtergrond);
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
