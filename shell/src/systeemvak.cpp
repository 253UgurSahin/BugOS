#include "systeemvak.h"

#include <QCoreApplication>
#include <QDBusConnectionInterface>
#include <QDBusMetaType>
#include <QDBusObjectPath>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusServiceWatcher>
#include <QDateTime>
#include <QDirIterator>
#include <QFileInfo>
#include <QtEndian>

namespace {
const QString WATCHER = QStringLiteral("org.kde.StatusNotifierWatcher");
const QString WATCHER_PAD = QStringLiteral("/StatusNotifierWatcher");
const QString ITEM = QStringLiteral("org.kde.StatusNotifierItem");
const QString MENU = QStringLiteral("com.canonical.dbusmenu");
const QString EIGENSCHAPPEN = QStringLiteral("org.freedesktop.DBus.Properties");
constexpr int MENU_WACHT_MS = 1500;   // een app die niet antwoordt, houdt de schil hooguit zo lang op

// 'dienst/pad' of alleen een dienst (dan het standaardpad).
void splits(const QString &sleutel, QString &dienst, QString &pad)
{
    const int i = sleutel.indexOf(QLatin1Char('/'));
    if (i < 0) {
        dienst = sleutel;
        pad = QStringLiteral("/StatusNotifierItem");
    } else {
        dienst = sleutel.left(i);
        pad = sleutel.mid(i);
    }
}

QString zonderSneltoets(QString label)
{
    // '_Openen' -> 'Openen'; '__' is een echte '_'.
    label.replace(QLatin1String("__"), QStringLiteral("\x01"));
    label.remove(QLatin1Char('_'));
    label.replace(QStringLiteral("\x01"), QStringLiteral("_"));
    return label;
}
} // namespace

void registreerDbusmenuTypen()
{
    static bool gedaan = false;
    if (gedaan)
        return;
    gedaan = true;
    qDBusRegisterMetaType<MenuOnderdeel>();
    qDBusRegisterMetaType<VakPixmap>();
    qDBusRegisterMetaType<VakPixmaps>();
    qDBusRegisterMetaType<VakTooltip>();
}

// ============================================================================================== Vakwachter ===

Vakwachter::Vakwachter(const QDBusConnection &bus, QObject *ouder)
    : QObject(ouder)
    , m_bus(bus)
    , m_diensten(new QDBusServiceWatcher(this))
{
    m_diensten->setConnection(m_bus);
    m_diensten->setWatchMode(QDBusServiceWatcher::WatchForUnregistration);
    connect(m_diensten, &QDBusServiceWatcher::serviceUnregistered, this, [this](const QString &dienst) {
        m_diensten->removeWatchedService(dienst);
        m_hosts.removeAll(dienst);
        for (const QString &item : QStringList(m_items)) {
            if (item.startsWith(dienst + QLatin1Char('/')) || item == dienst) {
                m_items.removeAll(item);
                Q_EMIT StatusNotifierItemUnregistered(item);
            }
        }
    });
}

bool Vakwachter::aanmelden()
{
    if (!m_bus.registerService(WATCHER))
        return false;
    m_bus.registerObject(WATCHER_PAD, this, QDBusConnection::ExportScriptableSlots
                                               | QDBusConnection::ExportScriptableSignals
                                               | QDBusConnection::ExportAllProperties);
    return true;
}

void Vakwachter::RegisterStatusNotifierItem(const QString &dienst, const QDBusMessage &bericht)
{
    // Twee vormen: een dienstnaam (KDE, Qt), of alleen een pad (Ayatana/libappindicator): dan de afzender zelf.
    QString naam = dienst;
    QString pad = QStringLiteral("/StatusNotifierItem");
    if (dienst.startsWith(QLatin1Char('/'))) {
        naam = bericht.service();
        pad = dienst;
    }
    const QString item = naam + pad;
    if (m_items.contains(item))
        return;
    m_items.append(item);
    m_diensten->addWatchedService(naam);
    Q_EMIT StatusNotifierItemRegistered(item);
}

void Vakwachter::RegisterStatusNotifierHost(const QString &dienst)
{
    if (!m_hosts.contains(dienst)) {
        m_hosts.append(dienst);
        m_diensten->addWatchedService(dienst);
    }
    Q_EMIT StatusNotifierHostRegistered();
}

// ========================================================================================= VakPictogrammen ===

VakPictogrammen::VakPictogrammen()
    : QQuickImageProvider(QQuickImageProvider::Image)
{
}

QHash<QString, QImage> &VakPictogrammen::opslag()
{
    static QHash<QString, QImage> h;
    return h;
}

QString VakPictogrammen::bewaar(const QImage &beeld)
{
    static int volgende = 1;
    const QString sleutel = QString::number(volgende++);
    opslag().insert(sleutel, beeld);
    // Niet eindeloos bewaren: oude pictogrammen (een app die elke seconde een nieuw stuurt) weg.
    if (opslag().size() > 400) {
        const int grens = volgende - 300;
        for (auto it = opslag().begin(); it != opslag().end();) {
            if (it.key().toInt() < grens)
                it = opslag().erase(it);
            else
                ++it;
        }
    }
    return sleutel;
}

QImage VakPictogrammen::requestImage(const QString &id, QSize *maat, const QSize &gevraagd)
{
    QImage beeld = opslag().value(id);
    if (!beeld.isNull() && gevraagd.isValid() && !gevraagd.isEmpty())
        beeld = beeld.scaled(gevraagd, Qt::KeepAspectRatio, Qt::SmoothTransformation);
    if (maat)
        *maat = beeld.size();
    return beeld;
}

// ============================================================================================== Systeemvak ===

Systeemvak::Systeemvak(const QDBusConnection &bus, QObject *ouder)
    : QAbstractListModel(ouder)
    , m_bus(bus)
{
    registreerDbusmenuTypen();
}

void Systeemvak::start()
{
    if (!m_bus.isConnected())
        return;
    // Is er nog geen watcher (geen kded), dan zijn we hem zelf.
    if (!m_bus.interface()->isServiceRegistered(WATCHER)) {
        m_eigenWachter = new Vakwachter(m_bus, this);
        if (!m_eigenWachter->aanmelden()) {
            delete m_eigenWachter;
            m_eigenWachter = nullptr;
        }
    }
    m_hostNaam = QStringLiteral("org.kde.StatusNotifierHost-%1").arg(QCoreApplication::applicationPid());
    m_bus.registerService(m_hostNaam);
    m_bus.connect(WATCHER, WATCHER_PAD, WATCHER, QStringLiteral("StatusNotifierItemRegistered"), this, SLOT(erbij(QString)));
    m_bus.connect(WATCHER, WATCHER_PAD, WATCHER, QStringLiteral("StatusNotifierItemUnregistered"), this, SLOT(eraf(QString)));
    // Alle apps: een nieuw pictogram, titel, status of uitleg (van welke app ook: we zoeken hem op aan de afzender).
    for (const char *sein : {"NewIcon", "NewAttentionIcon", "NewOverlayIcon", "NewTitle", "NewToolTip", "NewStatus", "NewMenu"}) {
        m_bus.connect(QString(), QString(), ITEM, QString::fromLatin1(sein), this, SLOT(watcherTerug(QDBusMessage)));
    }
    // Komt de watcher opnieuw (kded herstart), dan opnieuw aanmelden.
    auto *terug = new QDBusServiceWatcher(WATCHER, m_bus, QDBusServiceWatcher::WatchForRegistration, this);
    connect(terug, &QDBusServiceWatcher::serviceRegistered, this, &Systeemvak::watcherWeer);
    aanmeldenBijWatcher();
}

void Systeemvak::aanmeldenBijWatcher()
{
    QDBusMessage m = QDBusMessage::createMethodCall(WATCHER, WATCHER_PAD, WATCHER,
                                                    QStringLiteral("RegisterStatusNotifierHost"));
    m << m_hostNaam;
    m_bus.call(m, QDBus::NoBlock);
    QDBusMessage vraag = QDBusMessage::createMethodCall(WATCHER, WATCHER_PAD, EIGENSCHAPPEN, QStringLiteral("Get"));
    vraag << WATCHER << QStringLiteral("RegisteredStatusNotifierItems");
    auto *wacht = new QDBusPendingCallWatcher(m_bus.asyncCall(vraag), this);
    connect(wacht, &QDBusPendingCallWatcher::finished, this, [this](QDBusPendingCallWatcher *w) {
        QDBusPendingReply<QDBusVariant> antwoord = *w;
        w->deleteLater();
        if (antwoord.isError())
            return;
        for (const QString &sleutel : antwoord.value().variant().toStringList())
            erbij(sleutel);
    });
}

void Systeemvak::watcherWeer()
{
    aanmeldenBijWatcher();
}

void Systeemvak::watcherTerug(const QDBusMessage &m)
{
    // Een sein van een app (NewIcon, ...): welke? De afzender staat in het bericht.
    for (const Item &it : std::as_const(m_items)) {
        const QString eigenaar = m_bus.interface()->serviceOwner(it.dienst).value();
        if ((it.dienst == m.service() || eigenaar == m.service()) && it.pad == m.path()) {
            haal(it.sleutel);
            return;
        }
    }
}

int Systeemvak::rijVan(const QString &sleutel) const
{
    for (int i = 0; i < m_items.size(); ++i) {
        if (m_items.at(i).sleutel == sleutel)
            return i;
    }
    return -1;
}

void Systeemvak::erbij(const QString &sleutel)
{
    if (sleutel.isEmpty() || rijVan(sleutel) >= 0)
        return;
    Item it;
    it.sleutel = sleutel;
    splits(sleutel, it.dienst, it.pad);
    beginInsertRows(QModelIndex(), m_items.size(), m_items.size());
    m_items.append(it);
    endInsertRows();
    Q_EMIT aantalVeranderd();
    haal(sleutel);
}

void Systeemvak::eraf(const QString &sleutel)
{
    const int rij = rijVan(sleutel);
    if (rij < 0)
        return;
    beginRemoveRows(QModelIndex(), rij, rij);
    m_items.removeAt(rij);
    endRemoveRows();
    Q_EMIT aantalVeranderd();
}

void Systeemvak::haal(const QString &sleutel)
{
    const int rij = rijVan(sleutel);
    if (rij < 0)
        return;
    const Item &it = m_items.at(rij);
    QDBusMessage vraag = QDBusMessage::createMethodCall(it.dienst, it.pad, EIGENSCHAPPEN, QStringLiteral("GetAll"));
    vraag << ITEM;
    auto *wacht = new QDBusPendingCallWatcher(m_bus.asyncCall(vraag), this);
    connect(wacht, &QDBusPendingCallWatcher::finished, this, [this, sleutel](QDBusPendingCallWatcher *w) {
        QDBusPendingReply<QVariantMap> antwoord = *w;
        w->deleteLater();
        if (antwoord.isError()) {
            // Een app die zich aanmeldde maar niet antwoordt (al weg): niet laten staan.
            eraf(sleutel);
            return;
        }
        verwerk(sleutel, antwoord.value());
    });
}

QString Systeemvak::icoonVoor(const QVariantMap &e, bool aandacht) const
{
    const QString naamSleutel = aandacht ? QStringLiteral("AttentionIconName") : QStringLiteral("IconName");
    const QString pixSleutel = aandacht ? QStringLiteral("AttentionIconPixmap") : QStringLiteral("IconPixmap");
    const QString naam = e.value(naamSleutel).toString();
    if (!naam.isEmpty()) {
        if (naam.startsWith(QLatin1Char('/')))
            return QStringLiteral("image://icon/") + naam;
        // Een eigen map met pictogrammen van de app (IconThemePath): daar eerst zoeken.
        const QString map = e.value(QStringLiteral("IconThemePath")).toString();
        if (!map.isEmpty() && QFileInfo(map).isDir()) {
            QDirIterator zoek(map, {naam + QStringLiteral(".png"), naam + QStringLiteral(".svg")}, QDir::Files,
                              QDirIterator::Subdirectories);
            if (zoek.hasNext())
                return QStringLiteral("image://icon/") + zoek.next();
        }
        return QStringLiteral("image://icon/") + naam;
    }
    VakPixmaps lijst;
    const QVariant v = e.value(pixSleutel);
    if (v.canConvert<QDBusArgument>())
        v.value<QDBusArgument>() >> lijst;
    // Het beste formaat: het kleinste dat minstens 32 px is, anders het grootste.
    const VakPixmap *beste = nullptr;
    for (const VakPixmap &p : std::as_const(lijst)) {
        if (p.breedte <= 0 || p.hoogte <= 0 || p.pixels.size() < p.breedte * p.hoogte * 4)
            continue;
        if (!beste)
            beste = &p;
        else if (p.breedte >= 32 && (beste->breedte < 32 || p.breedte < beste->breedte))
            beste = &p;
        else if (beste->breedte < 32 && p.breedte > beste->breedte)
            beste = &p;
    }
    if (!beste)
        return aandacht ? QString() : QStringLiteral("image://icon/application-x-executable");
    QImage beeld(beste->breedte, beste->hoogte, QImage::Format_ARGB32);
    const auto *bron = reinterpret_cast<const quint32 *>(beste->pixels.constData());
    for (int y = 0; y < beste->hoogte; ++y) {
        auto *regel = reinterpret_cast<quint32 *>(beeld.scanLine(y));
        for (int x = 0; x < beste->breedte; ++x)
            regel[x] = qFromBigEndian(bron[y * beste->breedte + x]);   // ARGB in netwerkvolgorde
    }
    return QStringLiteral("image://vak/") + VakPictogrammen::bewaar(beeld);
}

void Systeemvak::verwerk(const QString &sleutel, const QVariantMap &e)
{
    const int rij = rijVan(sleutel);
    if (rij < 0)
        return;
    Item &it = m_items[rij];
    it.titel = e.value(QStringLiteral("Title")).toString();
    if (it.titel.isEmpty())
        it.titel = e.value(QStringLiteral("Id")).toString();
    it.status = e.value(QStringLiteral("Status")).toString();
    it.alleenMenu = e.value(QStringLiteral("ItemIsMenu")).toBool();
    const QVariant menu = e.value(QStringLiteral("Menu"));
    it.menuPad = menu.canConvert<QDBusObjectPath>() ? menu.value<QDBusObjectPath>().path() : menu.toString();
    if (it.menuPad == QLatin1String("/"))
        it.menuPad.clear();
    QString icoon;
    if (it.status == QLatin1String("NeedsAttention"))
        icoon = icoonVoor(e, true);
    it.icoon = icoon.isEmpty() ? icoonVoor(e, false) : icoon;
    VakTooltip tip;
    const QVariant t = e.value(QStringLiteral("ToolTip"));
    if (t.canConvert<QDBusArgument>())
        t.value<QDBusArgument>() >> tip;
    it.uitleg = tip.kop.isEmpty() ? it.titel : tip.kop;
    if (!tip.tekst.isEmpty())
        it.uitleg += QStringLiteral("\n") + tip.tekst;
    Q_EMIT dataChanged(index(rij), index(rij));
}

int Systeemvak::rowCount(const QModelIndex &ouder) const
{
    return ouder.isValid() ? 0 : m_items.size();
}

QVariant Systeemvak::data(const QModelIndex &i, int rol) const
{
    if (!i.isValid() || i.row() >= m_items.size())
        return {};
    const Item &it = m_items.at(i.row());
    switch (rol) {
    case SleutelRol: return it.sleutel;
    case TitelRol: return it.titel;
    case IcoonRol: return it.icoon;
    case StatusRol: return it.status;
    case UitlegRol: return it.uitleg;
    case AlleenMenuRol: return it.alleenMenu;
    case HeeftMenuRol: return !it.menuPad.isEmpty();
    default: return {};
    }
}

QHash<int, QByteArray> Systeemvak::roleNames() const
{
    return {{SleutelRol, "sleutel"}, {TitelRol, "titel"}, {IcoonRol, "icoon"}, {StatusRol, "status"},
            {UitlegRol, "uitleg"}, {AlleenMenuRol, "alleenMenu"}, {HeeftMenuRol, "heeftMenu"}};
}

bool Systeemvak::activeer(int rij, int x, int y)
{
    if (rij < 0 || rij >= m_items.size())
        return true;
    const Item &it = m_items.at(rij);
    if (it.alleenMenu)
        return false;
    QDBusMessage m = QDBusMessage::createMethodCall(it.dienst, it.pad, ITEM, QStringLiteral("Activate"));
    m << x << y;
    m_bus.call(m, QDBus::NoBlock);
    return true;
}

void Systeemvak::secundair(int rij, int x, int y)
{
    if (rij < 0 || rij >= m_items.size())
        return;
    const Item &it = m_items.at(rij);
    QDBusMessage m = QDBusMessage::createMethodCall(it.dienst, it.pad, ITEM, QStringLiteral("SecondaryActivate"));
    m << x << y;
    m_bus.call(m, QDBus::NoBlock);
}

void Systeemvak::scroll(int rij, int stappen)
{
    if (rij < 0 || rij >= m_items.size())
        return;
    const Item &it = m_items.at(rij);
    QDBusMessage m = QDBusMessage::createMethodCall(it.dienst, it.pad, ITEM, QStringLiteral("Scroll"));
    m << stappen << QStringLiteral("vertical");
    m_bus.call(m, QDBus::NoBlock);
}

void Systeemvak::contextMenu(int rij, int x, int y)
{
    if (rij < 0 || rij >= m_items.size())
        return;
    const Item &it = m_items.at(rij);
    QDBusMessage m = QDBusMessage::createMethodCall(it.dienst, it.pad, ITEM, QStringLiteral("ContextMenu"));
    m << x << y;
    m_bus.call(m, QDBus::NoBlock);
}

QVariantList Systeemvak::menuLijst(const MenuOnderdeel &wortel)
{
    QVariantList uit;
    for (const MenuOnderdeel &k : wortel.kinderen) {
        const QVariantMap &e = k.eigenschappen;
        if (e.contains(QStringLiteral("visible")) && !e.value(QStringLiteral("visible")).toBool())
            continue;
        QVariantMap regel;
        regel.insert(QStringLiteral("id"), k.id);
        regel.insert(QStringLiteral("tekst"), zonderSneltoets(e.value(QStringLiteral("label")).toString()));
        regel.insert(QStringLiteral("aan"), !e.contains(QStringLiteral("enabled")) || e.value(QStringLiteral("enabled")).toBool());
        regel.insert(QStringLiteral("scheiding"), e.value(QStringLiteral("type")).toString() == QLatin1String("separator"));
        const QString vink = e.value(QStringLiteral("toggle-type")).toString();
        regel.insert(QStringLiteral("vink"), vink);
        regel.insert(QStringLiteral("gevinkt"), (vink == QLatin1String("checkmark") || vink == QLatin1String("radio"))
                                                    && e.value(QStringLiteral("toggle-state")).toInt() == 1);
        regel.insert(QStringLiteral("icoon"), e.value(QStringLiteral("icon-name")).toString());
        regel.insert(QStringLiteral("kinderen"), menuLijst(k));
        uit.append(regel);
    }
    return uit;
}

QVariantList Systeemvak::menu(int rij)
{
    if (rij < 0 || rij >= m_items.size())
        return {};
    const Item &it = m_items.at(rij);
    if (it.menuPad.isEmpty())
        return {};
    // AboutToShow: sommige apps vullen hun menu pas op dat moment.
    QDBusMessage voor = QDBusMessage::createMethodCall(it.dienst, it.menuPad, MENU, QStringLiteral("AboutToShow"));
    voor << 0;
    m_bus.call(voor, QDBus::Block, MENU_WACHT_MS);
    QDBusMessage vraag = QDBusMessage::createMethodCall(it.dienst, it.menuPad, MENU, QStringLiteral("GetLayout"));
    vraag << 0 << -1 << QStringList();
    const QDBusMessage antwoord = m_bus.call(vraag, QDBus::Block, MENU_WACHT_MS);
    if (antwoord.type() != QDBusMessage::ReplyMessage || antwoord.arguments().size() < 2)
        return {};
    MenuOnderdeel wortel;
    const QVariant laag = antwoord.arguments().at(1);
    if (!laag.canConvert<QDBusArgument>())
        return {};
    laag.value<QDBusArgument>() >> wortel;
    return menuLijst(wortel);
}

void Systeemvak::menuKlik(int rij, int id)
{
    if (rij < 0 || rij >= m_items.size())
        return;
    const Item &it = m_items.at(rij);
    if (it.menuPad.isEmpty())
        return;
    QDBusMessage m = QDBusMessage::createMethodCall(it.dienst, it.menuPad, MENU, QStringLiteral("Event"));
    m << id << QStringLiteral("clicked") << QVariant::fromValue(QDBusVariant(QString()))
      << static_cast<uint>(QDateTime::currentSecsSinceEpoch());
    m_bus.call(m, QDBus::NoBlock);
}
