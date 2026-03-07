// qml/components/SecondaryButton.qml
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
        color: Theme.Colors.textPrimary
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }

    background: Rectangle {
        radius: Theme.Metrics.buttonRadius
        color: control.enabled
               ? (control.hovered ? Theme.Colors.secondaryBtnBgHover : Theme.Colors.secondaryBtnBg)
               : Theme.Colors.secondaryBtnBg
        opacity: control.enabled ? 1.0 : 0.5
        Behavior on color { ColorAnimation { duration: Theme.Easing.tFast; easing.type: Theme.Easing.easeOut } }
        Behavior on opacity { NumberAnimation { duration: Theme.Easing.tFast } }
    }
}