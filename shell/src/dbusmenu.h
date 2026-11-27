// De gegevenstypen van com.canonical.dbusmenu (het menu achter een pictogram in het systeemvak) en de StatusNotifierItem-
// pictogrammen (IconPixmap), zoals ze over D-Bus gaan, met het in- en uitpakken voor QtDBus.
//
//   menu-onderdeel:  (ia{sv}av)  = id, eigenschappen (label, enabled, visible, type, toggle-type, toggle-state,
//                                  children-display, icon-name), kinderen (elk een variant met weer zo'n onderdeel)
//   pictogram:       a(iiay)     = breedte, hoogte, ARGB32-pixels in netwerkvolgorde
#pragma once

#include <QDBusArgument>
#include <QDBusVariant>
#include <QList>
#include <QMetaType>
#include <QVariantMap>

struct MenuOnderdeel {
    int id = 0;
    QVariantMap eigenschappen;
    QList<MenuOnderdeel> kinderen;
};
Q_DECLARE_METATYPE(MenuOnderdeel)

inline QDBusArgument &operator<<(QDBusArgument &arg, const MenuOnderdeel &o)
{
    arg.beginStructure();
    arg << o.id << o.eigenschappen;
    arg.beginArray(qMetaTypeId<QDBusVariant>());
    for (const MenuOnderdeel &k : o.kinderen)
        arg << QDBusVariant(QVariant::fromValue(k));
    arg.endArray();
    arg.endStructure();
    return arg;
}

inline const QDBusArgument &operator>>(const QDBusArgument &arg, MenuOnderdeel &o)
{
    arg.beginStructure();
    arg >> o.id >> o.eigenschappen;
    o.kinderen.clear();
    arg.beginArray();
    while (!arg.atEnd()) {
        QDBusVariant v;
        arg >> v;
        const QVariant binnen = v.variant();
        MenuOnderdeel kind;
        if (binnen.canConvert<QDBusArgument>()) {
            binnen.value<QDBusArgument>() >> kind;
        } else if (binnen.canConvert<MenuOnderdeel>()) {
            kind = binnen.value<MenuOnderdeel>();
        }
        o.kinderen.append(kind);
    }
    arg.endArray();
    arg.endStructure();
    return arg;
}

struct VakPixmap {
    int breedte = 0;
    int hoogte = 0;
    QByteArray pixels;
};
Q_DECLARE_METATYPE(VakPixmap)
using VakPixmaps = QList<VakPixmap>;
Q_DECLARE_METATYPE(VakPixmaps)

inline QDBusArgument &operator<<(QDBusArgument &arg, const VakPixmap &p)
{
    arg.beginStructure();
    arg << p.breedte << p.hoogte << p.pixels;
    arg.endStructure();
    return arg;
}

inline const QDBusArgument &operator>>(const QDBusArgument &arg, VakPixmap &p)
{
    arg.beginStructure();
    arg >> p.breedte >> p.hoogte >> p.pixels;
    arg.endStructure();
    return arg;
}

// ToolTip: (sa(iiay)ss) = pictogramnaam, pictogrammen, kop, tekst.
struct VakTooltip {
    QString icoon;
    VakPixmaps pixmaps;
    QString kop;
    QString tekst;
};
Q_DECLARE_METATYPE(VakTooltip)

inline QDBusArgument &operator<<(QDBusArgument &arg, const VakTooltip &t)
{
    arg.beginStructure();
    arg << t.icoon << t.pixmaps << t.kop << t.tekst;
    arg.endStructure();
    return arg;
}

inline const QDBusArgument &operator>>(const QDBusArgument &arg, VakTooltip &t)
{
    arg.beginStructure();
    arg >> t.icoon >> t.pixmaps >> t.kop >> t.tekst;
    arg.endStructure();
    return arg;
}

void registreerDbusmenuTypen();
