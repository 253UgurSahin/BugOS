// Opdracht: programma's uitvoeren vanuit de QML van de schil (zoals P5Support.DataSource in de Plasma-versie, maar
// zonder shell: de argumenten gaan als lijst naar het programma, dus een naam met ' of ; erin wordt nooit een opdracht).
#pragma once

#include <QObject>
#include <QStringList>

class Opdracht : public QObject
{
    Q_OBJECT
public:
    explicit Opdracht(QObject *ouder = nullptr);

    // Uitvoeren en het antwoord teruggeven (signaal klaar). sleutel: zelf te kiezen, komt terug in klaar.
    Q_INVOKABLE void voerUit(const QStringList &argv, const QString &sleutel = QString());
    // Los starten (een app): de schil wacht niet, en de app loopt door als de schil stopt.
    Q_INVOKABLE bool start(const QStringList &argv);

Q_SIGNALS:
    void klaar(const QString &sleutel, int code, const QString &uitvoer);
};
