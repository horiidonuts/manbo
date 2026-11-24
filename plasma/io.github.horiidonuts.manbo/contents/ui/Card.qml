// Desktop / popup view: a little Manbo — mode switcher, rolling clock,
// session dots, the 3D push button and reset. Everything scales with width.
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Rectangle {
    id: card
    required property var widget

    readonly property real s: width / 360          // 1 = the full Manbo window's scale
    readonly property color textColor: widget.palette.text
    readonly property string fontFamily: Kirigami.Theme.defaultFont.family

    Layout.preferredWidth: Kirigami.Units.gridUnit * 14
    Layout.preferredHeight: Layout.preferredWidth * 1.42
    Layout.minimumWidth: Kirigami.Units.gridUnit * 9
    Layout.minimumHeight: Layout.minimumWidth * 1.42

    radius: 24 * s
    color: widget.palette.bg
    border.width: 1
    border.color: Qt.rgba(0, 0, 0, 0.06)
    Behavior on color { ColorAnimation { duration: 450; easing.type: Easing.OutCubic } }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 18 * card.s
        anchors.topMargin: 22 * card.s
        spacing: 10 * card.s
        opacity: card.widget.connected ? 1 : 0.45
        Behavior on opacity { NumberAnimation { duration: 250 } }

        // ‹ FOCUS ›
        Rectangle {
            id: pill
            Layout.alignment: Qt.AlignHCenter
            implicitWidth: modeLabel.implicitWidth + 2 * arrowZone
            implicitHeight: 32 * card.s
            radius: height / 2
            color: Qt.rgba(1, 1, 1, 0.35)
            border.width: 1
            border.color: Qt.alpha(card.textColor, 0.18)
            readonly property real arrowZone: 30 * card.s

            Text {
                id: modeLabel
                anchors.centerIn: parent
                text: card.widget.modeTitles[card.widget.mode]
                color: card.textColor
                font.family: card.fontFamily
                font.pixelSize: 12 * card.s
                font.weight: Font.ExtraBold
                font.variableAxes: { "wght": 800 }
                font.letterSpacing: 2 * card.s
            }
            Repeater {
                model: [-1, 1]
                Item {
                    required property int modelData
                    width: pill.arrowZone
                    height: pill.height
                    x: modelData < 0 ? 0 : pill.width - width
                    Kirigami.Icon {
                        anchors.centerIn: parent
                        width: 14 * card.s
                        height: width
                        source: parent.modelData < 0 ? "go-previous-symbolic" : "go-next-symbolic"
                        color: card.textColor
                        isMask: true
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: card.widget.stepMode(parent.modelData)
                    }
                }
            }
        }

        RollingTime {
            id: clock
            Layout.alignment: Qt.AlignHCenter
            color: card.textColor
            font.family: card.fontFamily
            font.pixelSize: 76 * card.s
            font.weight: Font.ExtraBold
            font.variableAxes: { "wght": 800 }   // variable fonts ignore font.weight
            font.letterSpacing: -1 * card.s
            font.features: { "tnum": 1 }
            seconds: card.widget.remaining
            placeholder: card.widget.connected ? "" : "--:--"
        }

        Row {
            Layout.alignment: Qt.AlignHCenter
            spacing: 8 * card.s
            Repeater {
                model: card.widget.interval
                Rectangle {
                    required property int index
                    width: 10 * card.s
                    height: width
                    radius: width / 2
                    color: index < card.widget.cyclePosition ? card.textColor : Qt.alpha(card.textColor, 0.18)
                    Behavior on color { ColorAnimation { duration: 300 } }
                }
            }
        }

        PushButton3D {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.minimumHeight: 80 * card.s
            down: card.widget.running
            bg: card.widget.palette.bg
            face: card.widget.palette.button
            ink: card.textColor
            onActivated: card.widget.toggle()
        }

        Item {
            Layout.alignment: Qt.AlignHCenter
            implicitWidth: 40 * card.s
            implicitHeight: 40 * card.s
            Kirigami.Icon {
                anchors.centerIn: parent
                width: 18 * card.s
                height: width
                source: "view-refresh-symbolic"
                color: card.textColor
                isMask: true
            }
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                onClicked: card.widget.reset()
            }
        }
    }

    // Manbo isn't running: say so; a click anywhere opens it
    Text {
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 14 * card.s
        visible: !card.widget.connected
        text: card.widget.t("Manbo's napping 💤 click to wake it", "Manbo uyuyor 💤 uyandırmak için tıkla")
        color: card.textColor
        font.family: card.fontFamily
        font.pixelSize: 12 * card.s
        font.weight: Font.DemiBold
        font.variableAxes: { "wght": 600 }
    }
    MouseArea {
        anchors.fill: parent
        visible: !card.widget.connected
        cursorShape: Qt.PointingHandCursor
        onClicked: card.widget.openApp()
    }
}
