// Meldingen: de meldingendienst van BugOS (org.freedesktop.Notifications), die in Plasma in plasmashell zat.
// Zonder deze dienst werkt notify-send niet, en BugOS meldt veel zo (updates, apps klaar, Steam, ...).
//
// De QML toont de lijst (lijst) als kaartjes rechtsonder. Een melding verdwijnt vanzelf na de tijd die de app vraagt
// (standaard 6 seconden), behalve een dringende (urgency 2). 'Niet storen' (snelmenu) staat in plasmanotifyrc
// [DoNotDisturb] Until, zoals bugos-start-data het schrijft: dan geen kaartje (behalve dringend).
#pragma once

#include <QDateTime>
#include <QHash>
#include <QObject>
#include <QStringList>
#include <QVariantList>
#include <QVariantMap>

class QTimer;

class Meldingen : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.freedesktop.Notifications")
    Q_PROPERTY(QVariantList lijst READ lijst NOTIFY lijstVeranderd)
public:
    explicit Meldingen(QObject *ouder = nullptr);
    bool aanmelden();
    QVariantList lijst() const { return m_lijst; }

    // Vanuit de QML: een kaartje dichtklikken (reden 2) of een knop erop (actie).
    Q_INVOKABLE void sluit(uint id);
    Q_INVOKABLE void actie(uint id, const QString &sleutel);

    // Hulp voor 'niet storen' (ook voor de test): 'jaar,maand,dag,uur,min,sec[,zone]' of een ISO-tijd.
    static bool tijdInToekomst(const QString &tekst, const QDateTime &nu);

public Q_SLOTS:
    Q_SCRIPTABLE QStringList GetCapabilities();
    Q_SCRIPTABLE uint Notify(const QString &app_name, uint replaces_id, const QString &app_icon,
                             const QString &summary, const QString &body, const QStringList &actions,
                             const QVariantMap &hints, int expire_timeout);
    Q_SCRIPTABLE void CloseNotification(uint id);
    Q_SCRIPTABLE QString GetServerInformation(QString &vendor, QString &version, QString &spec_version);

Q_SIGNALS:
    Q_SCRIPTABLE void NotificationClosed(uint id, uint reason);
    Q_SCRIPTABLE void ActionInvoked(uint id, const QString &action_key);
    void lijstVeranderd();

private:
    void weg(uint id, uint reden);
    bool nietStoren() const;

    QVariantList m_lijst;
    QHash<uint, QTimer *> m_klokken;
    uint m_volgende = 1;
};
