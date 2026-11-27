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
    // Het meldingencentrum (de bel): de laatste meldingen, nieuwste eerst, ook die je tijdens 'niet storen' niet zag.
    Q_PROPERTY(QVariantList geschiedenis READ geschiedenis NOTIFY geschiedenisVeranderd)
    Q_PROPERTY(int ongelezen READ ongelezen NOTIFY geschiedenisVeranderd)
public:
    explicit Meldingen(QObject *ouder = nullptr);
    bool aanmelden();
    QVariantList lijst() const { return m_lijst; }
    QVariantList geschiedenis() const { return m_geschiedenis; }
    int ongelezen() const { return m_ongelezen; }

    // Het meldingencentrum: alles weg, één weg, alles gezien (de bel opent), of een knop van een oude melding.
    Q_INVOKABLE void wisGeschiedenis();
    Q_INVOKABLE void uitGeschiedenis(uint id);
    Q_INVOKABLE void allesGelezen();
    Q_INVOKABLE void actieUitGeschiedenis(uint id, const QString &sleutel);

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
    void geschiedenisVeranderd();

private:
    void weg(uint id, uint reden);
    bool nietStoren() const;

    void bewaarInGeschiedenis(const QVariantMap &kaartje);
    QVariantList m_lijst;
    QVariantList m_geschiedenis;
    int m_ongelezen = 0;
    QHash<uint, QTimer *> m_klokken;
    uint m_volgende = 1;
};
