// One character of the clock. When `ch` changes, the old one slides out and
// the new one slides in (from the top when direction = 1, from below when -1).
import QtQuick

Item {
    id: digit
    property string ch: ""
    property int direction: 1
    property color color: "black"
    property font font

    property string shown: ""
    property real t: 1                  // 0 -> 1 while rolling

    implicitWidth: current.implicitWidth
    implicitHeight: current.implicitHeight
    clip: true

    onChChanged: {
        if (shown === "") {             // first value: no roll
            shown = ch
            return
        }
        previous.text = shown
        shown = ch
        roll.restart()
    }
    Component.onCompleted: shown = ch

    NumberAnimation {
        id: roll
        target: digit
        property: "t"
        from: 0
        to: 1
        duration: digit.direction > 0 ? 260 : 380
        easing.type: Easing.OutCubic
    }

    Text {
        id: current
        text: digit.shown
        color: digit.color
        font: digit.font
        y: (digit.t - 1) * digit.height * digit.direction
    }
    Text {
        id: previous
        visible: digit.t < 1
        color: digit.color
        font: digit.font
        y: digit.t * digit.height * digit.direction
    }
}
