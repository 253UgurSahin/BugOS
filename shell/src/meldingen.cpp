#include "meldingen.h"

#include <QDBusConnection>
#include <QDir>
#include <QSettings>
#include <QStandardPaths>
#include <QTimer>
#include <QTimeZone>

namespace {
constexpr int STANDAARD_MS = 6000;   // zoals Plasma: een melding zonder eigen tijd blijft 6 seconden staan
constexpr int MAX_KAARTJES = 5;      // nooit meer dan vijf tegelijk op het scherm
}

Meldingen::Meldingen(QObject *ouder)
    : QObject(ouder)
{
}

bool Meldingen::aanmelden()
{
    auto bus = QDBusConnection::sessionBus();
    if (!bus.isConnected())
        return false;
    bus.registerObject(QStringLiteral("/org/freedesktop/Notifications"), this,
                       QDBusConnection::ExportScriptableSlots | QDBusConnection::ExportScriptableSignals);
    return bus.registerService(QStringLiteral("org.freedesktop.Notifications"));
}

QStringList Meldingen::GetCapabilities()
{
    return {QStringLiteral("body"), QStringLiteral("actions"), QStringLiteral("icon-static"),
            QStringLiteral("persistence")};
}

QString Meldingen::GetServerInformation(QString &vendor, QString &version, QString &spec_version)
{
    vendor = QStringLiteral("BugOS");
    version = QStringLiteral("1");
    spec_version = QStringLiteral("1.2");
    return QStringLiteral("BugOS");
}

bool Meldingen::tijdInToekomst(const QString &tekst, const QDateTime &nu)
{
    const QString t = tekst.trimmed();
    if (t.isEmpty())
        return false;
    const QStringList delen = t.split(QLatin1Char(','));
    QDateTime tot;
    if (delen.size() >= 3) {
        int g[6] = {0, 0, 0, 0, 0, 0};
        for (int i = 0; i < 6 && i < delen.size(); ++i)
            g[i] = int(delen.at(i).trimmed().toDouble());
        tot = QDateTime(QDate(g[0], g[1], g[2]), QTime(g[3], g[4], g[5]));
        if (delen.size() > 6) {
            const QTimeZone zone(delen.at(6).trimmed().toUtf8());
            if (zone.isValid())
                tot.setTimeZone(zone);
        }
    } else {
        tot = QDateTime::fromString(t, Qt::ISODate);
    }
    return tot.isValid() && tot > nu;
}

bool Meldingen::nietStoren() const
{
    const QString pad = QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation)
        + QStringLiteral("/plasmanotifyrc");
    QSettings ini(pad, QSettings::IniFormat);
    // KConfig zet een waarde met komma's niet tussen aanhalingstekens: QSettings leest die dan als lijst.
    const QVariant waarde = ini.value(QStringLiteral("DoNotDisturb/Until"));
    const QString tekst = waarde.typeId() == QMetaType::QStringList ? waarde.toStringList().join(QLatin1Char(','))
                                                                    : waarde.toString();
    return tijdInToekomst(tekst, QDateTime::currentDateTime());
}

uint Meldingen::Notify(const QString &app_name, uint replaces_id, const QString &app_icon, const QString &summary,
                       const QString &body, const QStringList &actions, const QVariantMap &hints, int expire_timeout)
{
    const bool dringend = hints.value(QStringLiteral("urgency")).toUInt() == 2;
    uint id = replaces_id;
    int plek = -1;
    if (id != 0) {
        for (int i = 0; i < m_lijst.size(); ++i) {
            if (m_lijst.at(i).toMap().value(QStringLiteral("id")).toUInt() == id) {
                plek = i;
                break;
            }
        }
    }
    if (plek < 0)
        id = m_volgende++;

    // Het pictogram: de app_icon, anders image-path, anders het pictogram van de app (desktop-entry).
    QString icoon = app_icon;
    if (icoon.isEmpty())
        icoon = hints.value(QStringLiteral("image-path")).toString();
    if (icoon.isEmpty())
        icoon = hints.value(QStringLiteral("desktop-entry")).toString();
    if (icoon.startsWith(QLatin1String("file://")))
        icoon = icoon.mid(7);

    QVariantList knoppen;
    for (int i = 0; i + 1 < actions.size(); i += 2) {
        if (actions.at(i) == QLatin1String("default"))
            continue;   // de 'standaard'-actie is klikken op het kaartje zelf
        knoppen.append(QVariantMap{{QStringLiteral("sleutel"), actions.at(i)}, {QStringLiteral("tekst"), actions.at(i + 1)}});
    }
    const bool heeftStandaard = actions.contains(QStringLiteral("default"));

    if (nietStoren() && !dringend) {
        // Niet storen: geen kaartje. De app hoort dat de melding 'vervallen' is, zodat hij niet blijft wachten.
        QTimer::singleShot(0, this, [this, id]() { Q_EMIT NotificationClosed(id, 1); });
        return id;
    }

    const QVariantMap kaartje{
        {QStringLiteral("id"), id},
        {QStringLiteral("app"), app_name},
        {QStringLiteral("icoon"), icoon},
        {QStringLiteral("kop"), summary},
        {QStringLiteral("tekst"), body},
        {QStringLiteral("knoppen"), knoppen},
        {QStringLiteral("standaard"), heeftStandaard},
        {QStringLiteral("dringend"), dringend},
    };
    if (plek >= 0) {
        m_lijst[plek] = kaartje;
    } else {
        m_lijst.append(kaartje);
        while (m_lijst.size() > MAX_KAARTJES)
            weg(m_lijst.first().toMap().value(QStringLiteral("id")).toUInt(), 1);
    }

    delete m_klokken.take(id);
    if (!dringend && expire_timeout != 0) {
        auto *klok = new QTimer(this);
        klok->setSingleShot(true);
        connect(klok, &QTimer::timeout, this, [this, id]() { weg(id, 1); });
        klok->start(expire_timeout > 0 ? expire_timeout : STANDAARD_MS);
        m_klokken.insert(id, klok);
    }
    Q_EMIT lijstVeranderd();
    return id;
}

void Meldingen::CloseNotification(uint id)
{
    weg(id, 3);
}

void Meldingen::sluit(uint id)
{
    weg(id, 2);
}

void Meldingen::actie(uint id, const QString &sleutel)
{
    Q_EMIT ActionInvoked(id, sleutel.isEmpty() ? QStringLiteral("default") : sleutel);
    weg(id, 2);
}

void Meldingen::weg(uint id, uint reden)
{
    delete m_klokken.take(id);
    for (int i = 0; i < m_lijst.size(); ++i) {
        if (m_lijst.at(i).toMap().value(QStringLiteral("id")).toUInt() == id) {
            m_lijst.removeAt(i);
            Q_EMIT lijstVeranderd();
            Q_EMIT NotificationClosed(id, reden);
            return;
        }
    }
}
