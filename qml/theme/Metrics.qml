// qml/theme/Metrics.qml
pragma Singleton
import QtQuick 2.15

QtObject {
    // Window size (main panel == app size)
    readonly property int windowW: 680
    readonly property int windowH: 520

    // Radii
    readonly property int windowRadius: 18
    readonly property int cardRadius: 16
    readonly property int inputRadius: 10
    readonly property int buttonRadius: 8

    // Paddings (match html)
    readonly property int headerPadTop: 24
    readonly property int headerPadH: 32
    readonly property int headerPadBottom: 16

    readonly property int contentPadH: 32

    readonly property int footerPadTop: 20
    readonly property int footerPadH: 32
    readonly property int footerPadBottom: 24

    // Window buttons placement (match html: top/right 16)
    readonly property int windowBtnInset: 16
    readonly property int windowBtnSize: 12
    readonly property int windowBtnGap: 8

    // Typography (match html)
    readonly property int stepFontPx: 13
    readonly property int titleFontPx: 28
    readonly property int baseFontPx: 14

    // Controls
    readonly property int inputH: 40
    readonly property int buttonH: 36
    readonly property int buttonPadH: 20
    readonly property int buttonGap: 12

    // Hairline
    readonly property int borderW: 1
}