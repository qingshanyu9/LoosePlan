// qml/components/PrimaryButton.qml
import QtQuick 2.15
import QtQuick.Controls 2.15

import "../theme" as Theme

Button {
    id: control
    hoverEnabled: true

    implicitHeight: Theme.Metrics.buttonH
    implicitWidth: Math.max(96, contentItem.implicitWidth + Theme.Metrics.buttonPadH * 2)

    font.pixelSize: Theme.Metrics.baseFontPx
    font.weight: Font.Medium

    contentItem: Text {
        text: control.text
        font: control.font
        color: "white"
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        id: bg
        radius: Theme.Metrics.buttonRadius
        color: control.enabled
               ? (control.down ? Theme.Colors.primaryHover : (control.hovered ? Theme.Colors.primaryHover : Theme.Colors.primary))
               : Theme.Colors.primary
        opacity: control.enabled ? 1.0 : 0.6

        transform: Translate {
            y: (control.hovered && control.enabled && !control.down) ? -1 : 0
        }

        Behavior on color { ColorAnimation { duration: Theme.Easing.tFast; easing.type: Theme.Easing.easeOut } }
        Behavior on opacity { NumberAnimation { duration: Theme.Easing.tFast } }
    }
}