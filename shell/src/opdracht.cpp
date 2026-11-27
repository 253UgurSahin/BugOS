#include "opdracht.h"

#include <QProcess>

Opdracht::Opdracht(QObject *ouder)
    : QObject(ouder)
{
}

void Opdracht::voerUit(const QStringList &argv, const QString &sleutel)
{
    if (argv.isEmpty()) {
        Q_EMIT klaar(sleutel, 127, QString());
        return;
    }
    auto *proces = new QProcess(this);
    proces->setProcessChannelMode(QProcess::SeparateChannels);
    connect(proces, &QProcess::finished, this, [this, proces, sleutel](int code, QProcess::ExitStatus status) {
        const QString uit = QString::fromUtf8(proces->readAllStandardOutput());
        Q_EMIT klaar(sleutel, status == QProcess::NormalExit ? code : 128, uit);
        proces->deleteLater();
    });
    connect(proces, &QProcess::errorOccurred, this, [this, proces, sleutel](QProcess::ProcessError fout) {
        if (fout == QProcess::FailedToStart) {
            Q_EMIT klaar(sleutel, 127, QString());
            proces->deleteLater();
        }
    });
    proces->start(argv.first(), argv.mid(1));
}

bool Opdracht::start(const QStringList &argv)
{
    if (argv.isEmpty())
        return false;
    return QProcess::startDetached(argv.first(), argv.mid(1));
}
