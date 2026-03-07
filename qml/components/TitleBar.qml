// qml/components/TitleBar.qml
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15

import "../theme" as Theme

Item {
    id: root
    width: parent ? parent.width : Theme.Metrics.windowW

    property string stepText: "步骤 1/5"
    property string titleText: "标题"

    signal minimizeRequested()
    signal closeRequested()

    // Header height is driven by content; keep minimum for comfortable drag
    implicitHeight: Theme.Metrics.headerPadTop + stepLabel.implicitHeight + 8 + titleLabel.implicitHeight + Theme.Metrics.headerPadBottom

    // Drag region (avoid stealing clicks on window buttons)
    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton
        onPressed: {
            if (Window.window) Window.window.startSystemMove()
        }
        // Let child controls receive events
        propagateComposedEvents: true
    }

    // Window controls (top-right)
    Row {
        id: winBtns
        spacing: Theme.Metrics.windowBtnGap
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.topMargin: Theme.Metrics.windowBtnInset
        anchors.rightMargin: Theme.Metrics.windowBtnInset
        z: 10

        // Minimize
        Item {
            id: minBtn
            width: Theme.Metrics.windowBtnSize
            height: Theme.Metrics.windowBtnSize

            property bool hovering: minMa.containsMouse

            Rectangle {
                anchors.fill: parent
                radius: width / 2
                color: Theme.Colors.winMinimize
            }

            Rectangle {
                width: 7
                height: 2
                radius: 1
                color: Theme.Colors.winMinimizeGlyph
                anchors.centerIn: parent
                opacity: minBtn.hovering ? 1.0 : 0.0
                Behavior on opacity { NumberAnimation { duration: Theme.Easing.tFast } }
            }

            MouseArea {
                id: minMa
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.minimizeRequested()
            }
        }

        // Close
        Item {
            id: closeBtn
            width: Theme.Metrics.windowBtnSize
            height: Theme.Metrics.windowBtnSize

            property bool hovering: closeMa.containsMouse

            Rectangle {
                anchors.fill: parent
                radius: width / 2
                color: Theme.Colors.winClose
            }

            // simple "x" glyph on hover
            Item {
                anchors.centerIn: parent
                width: 8
                height: 8
                opacity: closeBtn.hovering ? 1.0 : 0.0
                Behavior on opacity { NumberAnimation { duration: Theme.Easing.tFast } }

                Rectangle {
                    anchors.centerIn: parent
                    width: 8
                    height: 1.8
                    radius: 1
                    color: Theme.Colors.winCloseGlyph
                    rotation: 45
                    transformOrigin: Item.Center
                }
                Rectangle {
                    anchors.centerIn: parent
                    width: 8
                    height: 1.8
                    radius: 1
                    color: Theme.Colors.winCloseGlyph
                    rotation: -45
                    transformOrigin: Item.Center
                }
            }

            MouseArea {
                id: closeMa
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: root.closeRequested()
            }
        }
    }

    // Header text (match html paddings)
    Column {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.leftMargin: Theme.Metrics.headerPadH
        anchors.rightMargin: Theme.Metrics.headerPadH
        anchors.topMargin: Theme.Metrics.headerPadTop
        spacing: 8

        Label {
            id: stepLabel
            text: root.stepText
            font.pixelSize: Theme.Metrics.stepFontPx
            font.weight: Font.Medium
            color: Theme.Colors.accentBlue
        }

        Label {
            id: titleLabel
            text: root.titleText
            font.pixelSize: Theme.Metrics.titleFontPx
            font.weight: Font.Bold
            color: Theme.Colors.textPrimary
        }
    }
}