// qml/components/WizardScaffold.qml
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15

import "../theme" as Theme
import "./" as C

Item {
    id: root
    anchors.fill: parent

    // Header
    property int stepIndex: 1
    property int stepTotal: 5
    property string titleText: "标题"

    // Footer modes: "none" | "first" | "middle" | "quiz"
    property string footerMode: "middle"

    property bool nextEnabled: true
    property bool prevEnabled: true

    property string nextText: "下一步"
    property string prevText: "上一步"
    property string cancelText: "取消"

    // Quiz footer
    property real quizProgress: 0.0    // 0..1
    property string quizLeftText: ""   // optional

    // Content slot
    default property alias content: contentHost.data

    signal nextClicked()
    signal prevClicked()
    signal cancelClicked()

    // window control passthrough
    signal minimizeRequested()
    signal closeRequested()

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        C.TitleBar {
            Layout.fillWidth: true
            stepText: "步骤 " + root.stepIndex + "/" + root.stepTotal
            titleText: root.titleText
            onMinimizeRequested: root.minimizeRequested()
            onCloseRequested: root.closeRequested()
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            Item {
                id: contentHost
                anchors.fill: parent
                anchors.leftMargin: Theme.Metrics.contentPadH
                anchors.rightMargin: Theme.Metrics.contentPadH
                // html content area has no top padding beyond header; pages decide their own internal spacing
            }
        }

        Rectangle {
            Layout.fillWidth: true
            visible: root.footerMode !== "none"
            height: Theme.Metrics.footerPadTop + Theme.Metrics.buttonH + Theme.Metrics.footerPadBottom
            color: "transparent"
            border.width: Theme.Metrics.borderW
            border.color: Theme.Colors.glassBorder

            // Only draw top border like html
            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                height: Theme.Metrics.borderW
                color: Theme.Colors.glassBorder
            }

            Item {
                anchors.fill: parent
                anchors.leftMargin: Theme.Metrics.footerPadH
                anchors.rightMargin: Theme.Metrics.footerPadH
                anchors.topMargin: Theme.Metrics.footerPadTop
                anchors.bottomMargin: Theme.Metrics.footerPadBottom

                // FIRST: Cancel | Next
                RowLayout {
                    id: footerFirst
                    anchors.fill: parent
                    visible: root.footerMode === "first"

                    C.SecondaryButton {
                        text: root.cancelText
                        onClicked: root.cancelClicked()
                    }

                    Item { Layout.fillWidth: true }

                    C.PrimaryButton {
                        text: root.nextText
                        enabled: root.nextEnabled
                        onClicked: root.nextClicked()
                    }
                }

                // MIDDLE: Prev + Cancel | Next
                RowLayout {
                    id: footerMiddle
                    anchors.fill: parent
                    visible: root.footerMode === "middle"
                    spacing: Theme.Metrics.buttonGap

                    RowLayout {
                        spacing: Theme.Metrics.buttonGap

                        C.SecondaryButton {
                            text: root.prevText
                            enabled: root.prevEnabled
                            onClicked: root.prevClicked()
                        }
                        C.SecondaryButton {
                            text: root.cancelText
                            onClicked: root.cancelClicked()
                        }
                    }

                    Item { Layout.fillWidth: true }

                    C.PrimaryButton {
                        text: root.nextText
                        enabled: root.nextEnabled
                        onClicked: root.nextClicked()
                    }
                }

                // QUIZ: Progress bar | Prev + Next
                RowLayout {
                    id: footerQuiz
                    anchors.fill: parent
                    visible: root.footerMode === "quiz"
                    spacing: Theme.Metrics.buttonGap

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 6

                        // optional left text (e.g. "7/21")
                        Label {
                            visible: root.quizLeftText.length > 0
                            text: root.quizLeftText
                            font.pixelSize: 12
                            color: Theme.Colors.textSecondary
                        }

                        ProgressBar {
                            Layout.fillWidth: true
                            from: 0
                            to: 1
                            value: Math.max(0, Math.min(1, root.quizProgress))

                            background: Rectangle {
                                radius: 6
                                color: Qt.rgba(0, 0, 0, 0.06)
                            }
                            contentItem: Rectangle {
                                radius: 6
                                color: Theme.Colors.primary
                            }
                        }
                    }

                    RowLayout {
                        spacing: Theme.Metrics.buttonGap

                        C.SecondaryButton {
                            text: "上一题"
                            enabled: root.prevEnabled
                            onClicked: root.prevClicked()
                        }
                        C.PrimaryButton {
                            text: "下一题"
                            enabled: root.nextEnabled
                            onClicked: root.nextClicked()
                        }
                    }
                }
            }
        }
    }
}