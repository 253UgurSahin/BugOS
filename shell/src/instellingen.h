// Instellingen: kleine bestanden van de schil in ~/.config/bugos (de vastgezette apps, de achtergrond, de browser),
// lezen en bewaren vanuit de QML, met een seintje als een ander programma (Instellingen, bugos-browser) er een verandert.
#pragma once

#include <QObject>
#include <QString>

class QFileSystemWatcher;

class Instellingen : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QString bureaubladMap READ bureaubladMap CONSTANT)
public:
    explicit Instellingen(QObject *ouder = nullptr);

    // naam: alleen letters, cijfers, . _ en - (nooit een pad). Leeg als het bestand er niet is.
    Q_INVOKABLE QString lees(const QString &naam) const;
    // Veilig bewaren: eerst een tijdelijk bestand, dan in één keer op zijn plek (nooit een half bestand).
    Q_INVOKABLE bool bewaar(const QString &naam, const QString &tekst);
    // De map met de bestanden op je bureaublad (XDG: ~/Bureaublad of ~/Desktop).
    QString bureaubladMap() const;
    // De achtergrond als één beeldbestand. In ~/.config/bugos/achtergrond staat wat je in Instellingen koos: een foto,
    // of een achtergrondpakket (een map met contents/images en contents/images_dark, zoals de BugOS-achtergrond).
    // Een pakket geeft de lichte of donkere versie, de grootste die er is. Niets gekozen: het BugOS-pakket.
    Q_INVOKABLE QString achtergrondBeeld(bool donker) const;

    static bool geldigeNaam(const QString &naam);
    QString map() const;

Q_SIGNALS:
    void veranderd(const QString &naam);

private:
    void kijkOpnieuw();
    QFileSystemWatcher *m_wachter;
};
