#include "instellingen.h"

#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QFileSystemWatcher>
#include <QRegularExpression>
#include <QSaveFile>
#include <QStandardPaths>

Instellingen::Instellingen(QObject *ouder)
    : QObject(ouder)
    , m_wachter(new QFileSystemWatcher(this))
{
    QDir().mkpath(map());
    m_wachter->addPath(map());
    // Een bestand dat verandert (schrijven op zijn plek) en een map waar een bestand bijkomt of vervangen wordt
    // (bewaar() en de meeste programma's schrijven een nieuw bestand en hernoemen het).
    connect(m_wachter, &QFileSystemWatcher::fileChanged, this, [this](const QString &pad) {
        Q_EMIT veranderd(QFileInfo(pad).fileName());
        kijkOpnieuw();
    });
    connect(m_wachter, &QFileSystemWatcher::directoryChanged, this, [this](const QString &) {
        const QStringList bekend = m_wachter->files();
        const QDir d(map());
        for (const QString &naam : d.entryList(QDir::Files)) {
            const QString pad = d.filePath(naam);
            if (!bekend.contains(pad))
                Q_EMIT veranderd(naam);
        }
        kijkOpnieuw();
    });
    kijkOpnieuw();
}

QString Instellingen::map() const
{
    return QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) + QStringLiteral("/bugos");
}

QString Instellingen::bureaubladMap() const
{
    return QStandardPaths::writableLocation(QStandardPaths::DesktopLocation);
}

bool Instellingen::geldigeNaam(const QString &naam)
{
    static const QRegularExpression vorm(QStringLiteral("^[A-Za-z0-9_][A-Za-z0-9._-]{0,63}$"));
    return vorm.match(naam).hasMatch() && !naam.contains(QLatin1String(".."));
}

QString Instellingen::lees(const QString &naam) const
{
    if (!geldigeNaam(naam))
        return QString();
    QFile f(map() + QLatin1Char('/') + naam);
    if (!f.open(QIODevice::ReadOnly))
        return QString();
    return QString::fromUtf8(f.read(1024 * 1024));
}

bool Instellingen::bewaar(const QString &naam, const QString &tekst)
{
    if (!geldigeNaam(naam))
        return false;
    QDir().mkpath(map());
    QSaveFile f(map() + QLatin1Char('/') + naam);
    if (!f.open(QIODevice::WriteOnly))
        return false;
    f.write(tekst.toUtf8());
    return f.commit();
}

void Instellingen::kijkOpnieuw()
{
    // Alle bestanden in de map in de gaten houden (ook nieuwe); een vervangen bestand valt uit de lijst.
    const QDir d(map());
    QStringList paden;
    for (const QString &naam : d.entryList(QDir::Files))
        paden << d.filePath(naam);
    const QStringList al = m_wachter->files();
    for (const QString &p : paden) {
        if (!al.contains(p))
            m_wachter->addPath(p);
    }
}

QString Instellingen::achtergrondBeeld(bool donker) const
{
    const QString standaard = qEnvironmentVariable("BUGOS_ACHTERGROND_PAKKET", QStringLiteral("/usr/share/wallpapers/bugos"));
    QString pad = lees(QStringLiteral("achtergrond")).section(QLatin1Char('\n'), 0, 0).trimmed();
    if (pad.startsWith(QLatin1String("file://")))
        pad = pad.mid(7);
    if (pad.isEmpty() || !QFileInfo::exists(pad))
        pad = standaard;
    const QFileInfo info(pad);
    if (info.isFile())
        return info.absoluteFilePath();
    if (!info.isDir())
        return QString();
    QStringList mappen;
    if (donker)
        mappen << pad + QStringLiteral("/contents/images_dark");
    mappen << pad + QStringLiteral("/contents/images");
    for (const QString &m : std::as_const(mappen)) {
        const QFileInfoList beelden = QDir(m).entryInfoList(
            {QStringLiteral("*.jpg"), QStringLiteral("*.jpeg"), QStringLiteral("*.png"), QStringLiteral("*.webp")},
            QDir::Files, QDir::Size);
        if (!beelden.isEmpty())
            return beelden.first().absoluteFilePath();   // QDir::Size: de grootste eerst
    }
    return QString();
}
