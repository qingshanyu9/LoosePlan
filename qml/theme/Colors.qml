// qml/theme/Colors.qml
pragma Singleton
import QtQuick 2.15

QtObject {
    // From onboarding_*.html :root variables
    readonly property color primary: "#0A84FF"
    readonly property color accentBlue: "#0A84FF"
    readonly property color danger: "#FF453A"
    readonly property color success: "#34C759"

    readonly property color bgGradientStart: "#F5F6F8"
    readonly property color bgGradientEnd: "#ECEFF3"

    readonly property color glassBg: Qt.rgba(1, 1, 1, 0.72)             // rgba(255,255,255,0.72)
    readonly property color glassBorder: Qt.rgba(0, 0, 0, 0.06)         // rgba(0,0,0,0.06)

    readonly property color textPrimary: "#1D1D1F"
    readonly property color textSecondary: "#6E6E73"
    readonly property color textPlaceholder: "#A1A1A6"

    readonly property color inputBorder: Qt.rgba(0, 0, 0, 0.10)         // rgba(0,0,0,0.1)

    // macOS traffic light colors (from html)
    readonly property color winClose: "#FF5F57"
    readonly property color winMinimize: "#FFBD2E"

    // Approximations for icon glyph colors
    readonly property color winCloseGlyph: "#8B0000"
    readonly property color winMinimizeGlyph: "#8A6008"

    // Secondary button background
    readonly property color secondaryBtnBg: Qt.rgba(0, 0, 0, 0.05)
    readonly property color secondaryBtnBgHover: Qt.rgba(0, 0, 0, 0.08)

    // Primary hover blue (from html)
    readonly property color primaryHover: "#0070E0"
}