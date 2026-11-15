// Manbo's orthographic-3D push button (a port of manbo/pushbutton.py):
// a cylinder in a round housing, seen from above at an angle. `p` is the
// press amount: 0 = up, 1 = sunk.
import QtQuick

Canvas {
    id: btn
    property bool down: false
    property color bg: "#FFE5D9"
    property color face: "#F4ACB7"
    property color ink: "#7E6770"
    signal activated()

    // same tuning as pushbutton.py
    readonly property real viewAngle: 27
    readonly property real buttonWidth: 0.8
    readonly property real buttonHeight: 0.66
    readonly property real buttonHeightDown: 0.09
    readonly property real housingHeight: 0.15
    readonly property real housingR: 1.22
    readonly property real holeR: 1.045
    readonly property real squash: Math.sin(viewAngle * Math.PI / 180)
    readonly property real heightScale: Math.cos(viewAngle * Math.PI / 180)

    property real p: down ? 1 : 0
    property var geom: null

    Behavior on p {
        NumberAnimation {
            duration: btn.down ? 150 : 100
            easing.type: btn.down ? Easing.OutBack : Easing.OutBounce
            easing.amplitude: 0.35         // a small rebound, like the app's pop
            easing.overshoot: 1.70158
        }
    }
    Behavior on bg { ColorAnimation { duration: 450; easing.type: Easing.OutCubic } }
    Behavior on face { ColorAnimation { duration: 450; easing.type: Easing.OutCubic } }
    Behavior on ink { ColorAnimation { duration: 450; easing.type: Easing.OutCubic } }

    onPChanged: requestPaint()
    onBgChanged: requestPaint()
    onFaceChanged: requestPaint()
    onInkChanged: requestPaint()
    onDownChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()

    // -- color helpers ---------------------------------------------------------
    function mix(a, b, t) {
        return Qt.rgba(a.r + (b.r - a.r) * t, a.g + (b.g - a.g) * t, a.b + (b.b - a.b) * t, 1)
    }
    function lum(c) {
        function lin(v) { return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4) }
        return 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b)
    }
    readonly property color white: Qt.rgba(1, 1, 1, 1)
    readonly property color black: Qt.rgba(0, 0, 0, 1)

    // -- geometry --------------------------------------------------------------
    function layout(w, h) {
        const k = squash
        const above = buttonHeight * heightScale + buttonWidth * k
        const below = buttonWidth * housingR * k + housingHeight * heightScale + 0.04
        const r = Math.min(w * 0.34, h * 0.92 / (above + below))
        const cb = h / 2 + r * (above - below) / 2
        return {cx: w / 2, cb: cb, r: r}
    }
    function ellipse(ctx, cx, cy, rx, ry) {
        ctx.beginPath()
        ctx.ellipse(cx - rx, cy - ry, 2 * rx, 2 * ry)
    }
    function cylinderSide(ctx, cx, ytop, ybot, rx, ry) {
        ctx.beginPath()
        ctx.moveTo(cx - rx, ytop)
        ctx.lineTo(cx - rx, ybot)
        // front half of the bottom ellipse, left -> right
        const n = 32
        for (let i = 1; i <= n; i++) {
            const a = Math.PI - Math.PI * i / n
            ctx.lineTo(cx + rx * Math.cos(a), ybot + ry * Math.sin(a))
        }
        ctx.lineTo(cx + rx, ytop)
        ctx.closePath()
    }

    onPaint: {
        const ctx = getContext("2d")
        ctx.reset()
        const g = layout(width, height)
        geom = g
        const k = squash, rb = g.r * buttonWidth, R = rb * housingR

        // housing: side + top
        cylinderSide(ctx, g.cx, g.cb, g.cb + g.r * housingHeight * heightScale, R, R * k)
        ctx.fillStyle = mix(bg, ink, 0.28); ctx.fill()
        ellipse(ctx, g.cx, g.cb, R, R * k)
        ctx.fillStyle = mix(bg, white, 0.45); ctx.fill()
        // hole
        const hr = rb * holeR
        ellipse(ctx, g.cx, g.cb, hr, hr * k)
        ctx.fillStyle = mix(bg, ink, 0.45); ctx.fill()

        // button
        const h = buttonHeight - (buttonHeight - buttonHeightDown) * p
        const ytop = g.cb - g.r * Math.max(0, h) * heightScale
        cylinderSide(ctx, g.cx, ytop, g.cb, rb, rb * k)
        ctx.fillStyle = mix(mix(face, black, 0.22), ink, 0.18); ctx.fill()
        ellipse(ctx, g.cx, ytop, rb, rb * k)
        ctx.fillStyle = face; ctx.fill()

        // icon, laid flat on the top face
        const icon = lum(face) > 0.68 ? mix(face, ink, 0.75) : mix(face, white, 0.9)
        const s = rb * 0.42
        ctx.save()
        ctx.translate(g.cx, ytop)
        ctx.scale(1, k)
        ctx.beginPath()
        if (down) {
            const bw = s * 0.24, bh = s * 0.9, gap = s * 0.38
            roundRect(ctx, -gap / 2 - bw, -bh / 2, bw, bh, bw * 0.4)
            roundRect(ctx, gap / 2, -bh / 2, bw, bh, bw * 0.4)
        } else {
            ctx.moveTo(-s * 0.32, -s * 0.5)
            ctx.lineTo(-s * 0.32, s * 0.5)
            ctx.lineTo(s * 0.52, 0)
            ctx.closePath()
        }
        ctx.fillStyle = icon
        ctx.strokeStyle = icon
        ctx.lineJoin = "round"
        ctx.lineWidth = s * 0.16
        ctx.fill()
        ctx.stroke()
        ctx.restore()
    }
    function roundRect(ctx, x, y, w, h, rad) {
        ctx.moveTo(x + rad, y)
        ctx.arcTo(x + w, y, x + w, y + h, rad)
        ctx.arcTo(x + w, y + h, x, y + h, rad)
        ctx.arcTo(x, y + h, x, y, rad)
        ctx.arcTo(x, y, x + w, y, rad)
        ctx.closePath()
    }

    // -- input: only the button + housing are clickable --------------------------
    function hit(x, y) {
        const g = geom
        if (!g) return false
        const k = squash, rb = g.r * buttonWidth, R = rb * housingR
        const ytop = g.cb - g.r * buttonHeight * heightScale
        function inEl(ex, ey, rx, ry) { return Math.pow((x - ex) / rx, 2) + Math.pow((y - ey) / ry, 2) <= 1 }
        return inEl(g.cx, g.cb, R, R * k) || inEl(g.cx, ytop, rb, rb * k)
            || (Math.abs(x - g.cx) <= rb && y >= ytop && y <= g.cb)
    }
    MouseArea {
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: btn.hit(mouseX, mouseY) ? Qt.PointingHandCursor : Qt.ArrowCursor
        onClicked: mouse => { if (btn.hit(mouse.x, mouse.y)) btn.activated() }
    }
}
