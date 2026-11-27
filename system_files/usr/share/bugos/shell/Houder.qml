// De wortel van de schil: een QtObject dat vensters en hulpjes bevat (Shell.qml). Geen Item: vensters in een Item
// worden niet zelf getoond, ze wachten op het venster van dat Item (en de schil heeft er geen).
import QtQuick

QtObject {
    default property list<QtObject> onderdelen
}
