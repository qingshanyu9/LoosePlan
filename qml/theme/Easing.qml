// qml/theme/Easing.qml
pragma Singleton
import QtQuick 2.15

QtObject {
    // html: --transition: 160ms ease-out;
    readonly property int tFast: 160
    readonly property int tMed: 220

    readonly property int easeOut: Easing.OutCubic
}