// Het systeemvak: de pictogrammen van apps (Steam, Discord, Nextcloud, ...) rechts op de taakbalk.
//
// Apps melden zich via StatusNotifierItem (SNI) bij een 'watcher' (org.kde.StatusNotifierWatcher). In de sessie
// van fase 1-2 levert kded die al; is er geen (een latere eigen sessie, of de test), dan is bugos-shell hem zelf
// (Vakwachter). bugos-shell is de 'host': het leest de lijst, de pictogrammen en de menu's (com.canonical.dbusmenu)
// en geeft ze aan de QML (Systeemvak, een lijstmodel). Klikken gaat terug naar de app (Activate, ContextMenu, Event).
#pragma once

#include "dbusmenu.h"

#include <QAbstractListModel>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QHash>
#include <QImage>
#include <QObject>
#include <QQuickImageProvider>
#include <QStringList>

class QDBusServiceWatcher;

// org.kde.StatusNotifierWatcher, voor als er nog geen is.
class Vakwachter : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.kde.StatusNotifierWatcher")
    Q_PROPERTY(QStringList RegisteredStatusNotifierItems READ items)
    Q_PROPERTY(bool IsStatusNotifierHostRegistered READ hostAangemeld)
    Q_PROPERTY(int ProtocolVersion READ protocolVersie)
public:
    explicit Vakwachter(const QDBusConnection &bus, QObject *ouder = nullptr);
    bool aanmelden();
    QStringList items() const { return m_items; }
    bool hostAangemeld() const { return !m_hosts.isEmpty(); }
    int protocolVersie() const { return 0; }

public Q_SLOTS:
    Q_SCRIPTABLE void RegisterStatusNotifierItem(const QString &dienst, const QDBusMessage &bericht);
    Q_SCRIPTABLE void RegisterStatusNotifierHost(const QString &dienst);

Q_SIGNALS:
    Q_SCRIPTABLE void StatusNotifierItemRegistered(const QString &item);
    Q_SCRIPTABLE void StatusNotifierItemUnregistered(const QString &item);
    Q_SCRIPTABLE void StatusNotifierHostRegistered();

private:
    QDBusConnection m_bus;
    QDBusServiceWatcher *m_diensten;
    QStringList m_items;
    QStringList m_hosts;
};

// image://vak/<sleutel>: de pictogrammen die een app als pixels meestuurt (IconPixmap).
class VakPictogrammen : public QQuickImageProvider
{
public:
    VakPictogrammen();
    QImage requestImage(const QString &id, QSize *maat, const QSize &gevraagd) override;
    static QString bewaar(const QImage &beeld);   // geeft de sleutel
private:
    static QHash<QString, QImage> &opslag();
};

class Systeemvak : public QAbstractListModel
{
    Q_OBJECT
    Q_PROPERTY(int aantal READ rowCount NOTIFY aantalVeranderd)
public:
    enum Rol { SleutelRol = Qt::UserRole + 1, TitelRol, IcoonRol, StatusRol, UitlegRol, AlleenMenuRol, HeeftMenuRol };
    explicit Systeemvak(const QDBusConnection &bus, QObject *ouder = nullptr);

    // Host worden: bij de watcher aanmelden (en er zelf een zijn als er geen is).
    void start();

    int rowCount(const QModelIndex &ouder = QModelIndex()) const override;
    QVariant data(const QModelIndex &index, int rol) const override;
    QHash<int, QByteArray> roleNames() const override;

    // Vanuit de QML. x, y: waar op het scherm (sommige apps zetten hun eigen venster daar).
    Q_INVOKABLE bool activeer(int rij, int x, int y);        // false: deze app wil alleen zijn menu
    Q_INVOKABLE void secundair(int rij, int x, int y);       // middelste knop
    Q_INVOKABLE void scroll(int rij, int stappen);
    Q_INVOKABLE QVariantList menu(int rij);                  // het menu, of leeg (dan contextMenu)
    Q_INVOKABLE void contextMenu(int rij, int x, int y);     // de app tekent zijn eigen menu
    Q_INVOKABLE void menuKlik(int rij, int id);

    // Voor de test: een menu-onderdeel zoals de QML het krijgt.
    static QVariantList menuLijst(const MenuOnderdeel &wortel);

Q_SIGNALS:
    void aantalVeranderd();

private Q_SLOTS:
    void erbij(const QString &sleutel);
    void eraf(const QString &sleutel);
    void watcherTerug(const QDBusMessage &bericht);   // een sein van een app (NewIcon, ...)
    void watcherWeer();

private:
    struct Item {
        QString sleutel, dienst, pad, titel, icoon, status, uitleg, menuPad;
        bool alleenMenu = false;
    };
    void haal(const QString &sleutel);
    void verwerk(const QString &sleutel, const QVariantMap &e);
    int rijVan(const QString &sleutel) const;
    QString icoonVoor(const QVariantMap &e, bool aandacht) const;
    void aanmeldenBijWatcher();

    QDBusConnection m_bus;
    Vakwachter *m_eigenWachter = nullptr;
    QList<Item> m_items;
    QString m_hostNaam;
};
