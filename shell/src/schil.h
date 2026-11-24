// Schil: wat de rest van het systeem van de schil vraagt, via D-Bus.
//
// KWin en KDE-programma's praten met 'org.kde.plasmashell'. Zonder Plasma neemt bugos-shell die naam over, zodat:
//  - de Meta-toets (Windows-toets) het BugOS-startmenu opent (KWin roept activateLauncherMenu aan);
//  - systemd de dienst als 'gestart' ziet (plasma-plasmashell.service is Type=dbus met die naam).
// Wat de schil niet kent, geeft een gewone D-Bus-fout: niets loopt vast.
#pragma once

#include <QObject>

class QWindow;

class Schil : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.kde.PlasmaShell")
public:
    explicit Schil(QObject *ouder = nullptr);
    bool aanmelden();   // de naam org.kde.plasmashell en het object /PlasmaShell op de sessiebus

    // Een venster van de schil op zijn plek zetten met layer-shell, vóór het getoond wordt. soort:
    //   paneel      onderaan, over de hele breedte, met gereserveerde ruimte (hoogte = exclusieve zone)
    //   links/rechts een menu boven de taakbalk, links of rechts (marge = afstand tot de rand en de taakbalk)
    //   melding     rechtsonder, boven alles, zonder toetsenbord
    //   achtergrond de onderste laag, over het hele scherm
    //   vangnet     een doorzichtige laag over het scherm: een klik ernaast sluit een open menu
    // Zonder layer-shell (een test, of X11) doet dit niets: dan zijn het gewone vensters.
    Q_INVOKABLE bool laag(QWindow *venster, const QString &soort, int marge = 0);
    Q_INVOKABLE bool heeftLagen() const;

public Q_SLOTS:
    Q_SCRIPTABLE void activateLauncherMenu();
    Q_SCRIPTABLE void toggleDashboard();
    Q_SCRIPTABLE void showDesktop(bool tonen);

Q_SIGNALS:
    void startmenu();             // het startmenu openen of sluiten
    void bureaublad(bool tonen);  // 'Bureaublad tonen'
};
