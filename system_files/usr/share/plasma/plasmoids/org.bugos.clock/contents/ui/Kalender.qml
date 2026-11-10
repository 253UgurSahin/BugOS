// De maandkalender van KDE (los van de klok: kan hij niet laden, dan werkt de klok gewoon).
import QtQuick
import org.kde.plasma.workspace.calendar as PlasmaCalendar

PlasmaCalendar.MonthView {
    today: new Date()
    showWeekNumbers: false
}
