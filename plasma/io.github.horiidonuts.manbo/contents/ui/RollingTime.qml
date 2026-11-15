// MM:SS where each changed character rolls like an odometer — down while
// counting down, up when the time jumps up (reset, mode switch).
import QtQuick

Row {
    id: time
    property int seconds: 0
    property string placeholder: ""     // shown instead of the time when set
    property color color: "black"
    property font font

    property string text: ""
    property int direction: 1            // 1 = roll down, -1 = roll up
    property int lastSeconds: -1

    function format(secs) {
        const m = Math.floor(secs / 60), s = secs % 60
        return (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s
    }
    function refresh() {
        if (placeholder !== "") {
            direction = 1
            text = placeholder
            lastSeconds = -1
            return
        }
        direction = lastSeconds >= 0 && seconds > lastSeconds ? -1 : 1
        lastSeconds = seconds
        text = format(seconds)
    }
    onSecondsChanged: refresh()
    onPlaceholderChanged: refresh()
    Component.onCompleted: refresh()

    Repeater {
        model: time.text.length
        RollingDigit {
            required property int index
            ch: time.text.charAt(index)
            direction: time.direction
            color: time.color
            font: time.font
        }
    }
}
