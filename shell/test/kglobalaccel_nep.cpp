// kglobalaccel-nep: een nagemaakte kglobalaccel (de sneltoetsdienst van KDE, in KWin) voor tools/test_shell_dbus.sh.
//
// Neemt de naam org.kde.kglobalaccel op een eigen testbus, schrijft elke aanroep op /kglobalaccel op (één regel per
// aanroep: methode en argumenten), en 'drukt' daarna de sneltoets van het startmenu in: het signaal
// globalShortcutPressed("plasmashell", "activate application launcher") op /component/plasmashell, zoals KWin doet als
// je op de Windows-toets drukt. Stopt na een paar seconden.
#include <QCoreApplication>
#include <QDBusArgument>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusVirtualObject>
#include <QDateTime>
#include <QTimer>
#include <QVariant>

#include <cstdio>

namespace {

QString tekst(const QVariant &v)
{
    if (v.canConvert<QDBusArgument>()) {
        // a(ai): de sneltoetsen, elk een rijtje toetscodes.
        const QDBusArgument arg = v.value<QDBusArgument>();
        QStringList toetsen;
        if (arg.currentSignature() == QLatin1String("a(ai)")) {
            arg.beginArray();
            while (!arg.atEnd()) {
                QList<int> codes;
                arg.beginStructure();
                arg >> codes;
                arg.endStructure();
                QStringList c;
                for (int code : codes)
                    c << QString::number(code);
                toetsen << c.join(QLatin1Char(','));
            }
            arg.endArray();
            return QLatin1Char('[') + toetsen.join(QLatin1Char(' ')) + QLatin1Char(']');
        }
        return QStringLiteral("<%1>").arg(arg.currentSignature());
    }
    if (v.metaType().id() == QMetaType::QStringList)
        return v.toStringList().join(QLatin1Char('|'));
    return v.toString();
}

class Nep : public QDBusVirtualObject
{
public:
    int aanroepen = 0;
    bool aangemeld = false;

    QString introspect(const QString &) const override { return QString(); }

    bool handleMessage(const QDBusMessage &bericht, const QDBusConnection &bus) override
    {
        QStringList delen{bericht.member()};
        for (const QVariant &a : bericht.arguments())
            delen << tekst(a);
        std::printf("aanroep %s\n", qPrintable(delen.join(QLatin1Char(' '))));
        std::fflush(stdout);
        ++aanroepen;
        QDBusMessage antwoord = bericht.createReply();
        if (bericht.member() == QLatin1String("setShortcutKeys") && bericht.arguments().size() >= 2) {
            antwoord << bericht.arguments().at(1);   // 'dit geldt nu': dezelfde toetsen terug
            // SetPresent (2): de schil is er klaar voor. Dan even later de Windows-toets 'indrukken'.
            if (bericht.arguments().size() >= 3 && (bericht.arguments().at(2).toUInt() & 2) && !aangemeld) {
                aangemeld = true;
                QTimer::singleShot(800, [bus]() mutable {
                    QDBusMessage signaal = QDBusMessage::createSignal(QStringLiteral("/component/plasmashell"),
                                                                      QStringLiteral("org.kde.kglobalaccel.Component"),
                                                                      QStringLiteral("globalShortcutPressed"));
                    signaal << QStringLiteral("plasmashell") << QStringLiteral("activate application launcher")
                            << qlonglong(0);
                    bus.send(signaal);
                    std::printf("ingedrukt %.3f\n", QDateTime::currentMSecsSinceEpoch() / 1000.0);
                    std::fflush(stdout);
                });
            }
        }
        bus.send(antwoord);
        return true;
    }
};

} // namespace

int main(int argc, char *argv[])
{
    QCoreApplication app(argc, argv);
    auto bus = QDBusConnection::sessionBus();
    Nep nep;
    if (!bus.registerVirtualObject(QStringLiteral("/kglobalaccel"), &nep)
        || !bus.registerService(QStringLiteral("org.kde.kglobalaccel"))) {
        std::fprintf(stderr, "kglobalaccel-nep: kon de naam niet krijgen\n");
        return 1;
    }
    std::printf("klaar\n");
    std::fflush(stdout);
    QTimer::singleShot(argc > 1 ? QString::fromLocal8Bit(argv[1]).toInt() : 6000, &app, &QCoreApplication::quit);
    return app.exec();
}
