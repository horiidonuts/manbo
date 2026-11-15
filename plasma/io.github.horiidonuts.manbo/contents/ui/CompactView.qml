// Panel view: a mode-colored dot and the time. Click opens the card,
// middle-click starts/pauses without opening it.
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami

MouseArea {
    id: compact
    required property var widget

    readonly property bool vertical: Plasmoid.formFactor === PlasmaCore.Types.Vertical

    Layout.minimumWidth: vertical ? 0 : row.implicitWidth + Kirigami.Units.smallSpacing * 2
    Layout.minimumHeight: vertical ? row.implicitHeight : 0
    acceptedButtons: Qt.LeftButton | Qt.MiddleButton
    hoverEnabled: true
    onClicked: mouse => {
        if (mouse.button === Qt.MiddleButton)
            widget.toggle()
        else
            widget.expanded = !widget.expanded
    }

    Row {
        id: row
        anchors.centerIn: parent
        spacing: Kirigami.Units.smallSpacing
        opacity: compact.widget.connected ? 1 : 0.55

        // filled while running, a ring while paused
        Rectangle {
            anchors.verticalCenter: parent.verticalCenter
            width: Math.round(label.font.pixelSize * 0.62)
            height: width
            radius: width / 2
            color: compact.widget.running ? compact.widget.palette.button : "transparent"
            border.width: Math.max(1.5, width * 0.18)
            border.color: compact.widget.palette.button
            Behavior on color { ColorAnimation { duration: 300 } }
        }

        Text {
            id: label
            visible: !compact.vertical
            anchors.verticalCenter: parent.verticalCenter
            text: compact.widget.connected ? compact.widget.timeText : "--:--"
            color: Kirigami.Theme.textColor
            font.family: Kirigami.Theme.defaultFont.family
            font.pixelSize: Math.max(11, Math.min(compact.height * 0.5, 18))
            font.weight: Font.Bold
            font.variableAxes: { "wght": 700 }   // variable fonts ignore font.weight
            font.features: { "tnum": 1 }
        }
    }
}
