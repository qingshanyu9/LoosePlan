// qml/components/GlassWindow.qml
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Window 2.15

import "../theme" as Theme

ApplicationWindow {
    id: win

    width: Theme.Metrics.windowW
    height: Theme.Metrics.windowH
    visible: true

    flags: Qt.FramelessWindowHint | Qt.Window
    color: "transparent"

    // Allow children to be placed directly inside GlassWindow
    default property alias content: contentHost.data

    Rectangle {
        id: chrome
        anchors.fill: parent
        radius: Theme.Metrics.windowRadius
        color: Theme.Colors.glassBg
        border.width: Theme.Metrics.borderW
        border.color: Theme.Colors.glassBorder

        // subtle highlight to mimic glass
        Rectangle {
            anchors.fill: parent
            radius: parent.radius
            color: "transparent"
            border.width: 0
            gradient: Gradient {
                GradientStop { position: 0.0; color: Qt.rgba(1, 1, 1, 0.22) }
                GradientStop { position: 1.0; color: Qt.rgba(1, 1, 1, 0.06) }
            }
        }
    }

    Item {
        id: contentHost
        anchors.fill: parent
        anchors.margins: 0
    }
}