// qml/pages/onboarding_4_naming.qml
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15

import theme 1.0 as Theme
import components 1.0 as C

C.GlassWindow {
    id: win
    title: "Onboarding - Step 4"

    // --- Local state (trimmed like the html: value.trim()) ---
    property string botTrim: (botField.text || "").trim()
    property string userTrim: (userField.text || "").trim()
    property int botLen: botTrim.length
    property int userLen: userTrim.length
    property bool isValid: (botLen >= 1 && botLen <= 20 && userLen >= 1 && userLen <= 20)

    Timer {
        id: saveDebounce
        interval: 220
        repeat: false
        onTriggered: {
            try {
                onboardingDraft.setDraftAssistantName(win.botTrim)
                onboardingDraft.setDraftUserDisplayName(win.userTrim)
                onboardingDraft.setDraftStep(4)
                onboardingDraft.saveDraft()
            } catch (e) {
                // ignore when running qmlscene without context
            }
        }
    }

    function persistDraft() {
        // immediate (used on navigation)
        try {
            onboardingDraft.setDraftAssistantName(win.botTrim)
            onboardingDraft.setDraftUserDisplayName(win.userTrim)
            onboardingDraft.setDraftStep(4)
            onboardingDraft.saveDraft()
        } catch (e) {}
    }

    function clearDraftAndQuit() {
        try { onboardingDraft.clearDraft() } catch (e) {}
        Qt.quit()
    }

    function openStep(qmlFile) {
        if (typeof windowManager !== "undefined" && windowManager && windowManager.openPage) {
            windowManager.openPage("onboarding", qmlFile)
            Qt.callLater(function() {
                try { win.close() } catch (e) {
                    try { win.destroy() } catch (e2) {}
                }
            })
            return
        }

        var comp = Qt.createComponent(qmlFile)
        if (comp.status === Component.Ready) {
            var nextWin = comp.createObject(null)
            if (nextWin) {
                nextWin.x = win.x
                nextWin.y = win.y
                nextWin.show()
                Qt.callLater(function() {
                    try { win.close() } catch (e) {
                        try { win.destroy() } catch (e2) {}
                    }
                })
            }
        } else if (comp.status === Component.Error) {
            console.log(comp.errorString())
        }
    }

    C.WizardScaffold {
        anchors.fill: parent

        stepIndex: 4
        stepTotal: 5
        titleText: "设置称呼"
        footerMode: "middle"

        nextEnabled: win.isValid
        prevEnabled: true

        onMinimizeRequested: win.showMinimized()
        onCloseRequested: win.clearDraftAndQuit()

        onCancelClicked: win.clearDraftAndQuit()
        onPrevClicked: {
            win.persistDraft()
            openStep("onboarding_3_feishu.qml")
        }
        onNextClicked: {
            win.persistDraft()
            openStep("onboarding_5_quiz.qml")
        }

        // ---- Content (match onboarding_4_naming.html content area) ----
        ColumnLayout {
            anchors.fill: parent
            anchors.topMargin: 12
            anchors.bottomMargin: 16
            spacing: 12

            // Subtitle (html: .step-subtitle)
            Label {
                Layout.fillWidth: true
                text: "为你们的对话设定一个亲切的称呼方式"
                font.pixelSize: 13
                color: Theme.Colors.textSecondary
                wrapMode: Text.Wrap
            }

            Item { Layout.fillHeight: true }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 14

                // --- Bot name ---
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Label {
                        Layout.fillWidth: true
                        text: "机器人名字"
                        font.pixelSize: 13
                        font.weight: Font.Medium
                        color: Theme.Colors.textPrimary
                    }

                    TextField {
                        id: botField
                        Layout.fillWidth: true
                        implicitHeight: 44
                        placeholderText: "例如：小助手"
                        maximumLength: 20
                        font.pixelSize: 15
                        color: Theme.Colors.textPrimary
                        leftPadding: 16
                        rightPadding: 16
                        background: Item {
                            Rectangle {
                                anchors.fill: parent
                                radius: Theme.Metrics.inputRadius
                                color: botField.activeFocus ? Qt.rgba(1, 1, 1, 0.9) : Qt.rgba(1, 1, 1, 0.6)
                                border.width: 1
                                border.color: botField.activeFocus ? Theme.Colors.accentBlue : Theme.Colors.glassBorder
                            }
                            Rectangle {
                                anchors.fill: parent
                                anchors.margins: -3
                                radius: Theme.Metrics.inputRadius + 3
                                color: Qt.rgba(10/255, 132/255, 255/255, 0.10)
                                visible: botField.activeFocus
                                z: -1
                            }
                        }
                        onEditingFinished: text = (text || "").trim()
                        onTextChanged: saveDebounce.restart()
                    }

                    Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignRight
                        text: win.botLen + " / 20"
                        font.pixelSize: 11
                        color: (win.botLen > 20) ? Theme.Colors.danger : Theme.Colors.textSecondary
                    }
                }

                // --- User display name ---
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Label {
                        Layout.fillWidth: true
                        text: "机器人如何称呼你"
                        font.pixelSize: 13
                        font.weight: Font.Medium
                        color: Theme.Colors.textPrimary
                    }

                    TextField {
                        id: userField
                        Layout.fillWidth: true
                        implicitHeight: 44
                        placeholderText: "例如：主人"
                        maximumLength: 20
                        font.pixelSize: 15
                        color: Theme.Colors.textPrimary
                        leftPadding: 16
                        rightPadding: 16
                        background: Item {
                            Rectangle {
                                anchors.fill: parent
                                radius: Theme.Metrics.inputRadius
                                color: userField.activeFocus ? Qt.rgba(1, 1, 1, 0.9) : Qt.rgba(1, 1, 1, 0.6)
                                border.width: 1
                                border.color: userField.activeFocus ? Theme.Colors.accentBlue : Theme.Colors.glassBorder
                            }
                            Rectangle {
                                anchors.fill: parent
                                anchors.margins: -3
                                radius: Theme.Metrics.inputRadius + 3
                                color: Qt.rgba(10/255, 132/255, 255/255, 0.10)
                                visible: userField.activeFocus
                                z: -1
                            }
                        }
                        onEditingFinished: text = (text || "").trim()
                        onTextChanged: saveDebounce.restart()
                    }

                    Label {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignRight
                        text: win.userLen + " / 20"
                        font.pixelSize: 11
                        color: (win.userLen > 20) ? Theme.Colors.danger : Theme.Colors.textSecondary
                    }
                }

                // --- Preview card ---
                // Rectangle {
                //     Layout.fillWidth: true
                //     radius: 14
                //     color: Qt.rgba(1, 1, 1, 0.5)
                //     border.width: 1
                //     border.color: Theme.Colors.glassBorder
                //
                //     Column {
                //         anchors.fill: parent
                //         anchors.margins: 14
                //         spacing: 10
                //
                //         Label {
                //             text: "对话预览"
                //             font.pixelSize: 11
                //             color: Theme.Colors.textSecondary
                //             font.letterSpacing: 0.5
                //         }
                //
                //         Column {
                //             width: parent.width
                //             spacing: 10
                //
                //             // bot bubble
                //             Item {
                //                 width: parent.width
                //                 height: botBubble.height
                //
                //                 Rectangle {
                //                     id: botBubble
                //                     anchors.left: parent.left
                //                     width: Math.min(parent.width * 0.80, botText.implicitWidth + 28)
                //                     height: botText.implicitHeight + 20
                //                     radius: 16
                //                     color: Qt.rgba(1, 1, 1, 0.8)
                //                     border.width: 1
                //                     border.color: Theme.Colors.glassBorder
                //
                //                     Text {
                //                         id: botText
                //                         anchors.fill: parent
                //                         anchors.margins: 10
                //                         text: (win.botLen > 0 ? win.botTrim : "助手")
                //                               + "：早上好"
                //                               + (win.userLen > 0 ? "，" + win.userTrim : "")
                //                               + "！今天有什么计划吗？"
                //                         font.pixelSize: 13
                //                         color: Theme.Colors.textPrimary
                //                         wrapMode: Text.Wrap
                //                     }
                //                 }
                //             }
                //
                //             // user bubble
                //             Item {
                //                 width: parent.width
                //                 height: userBubble.height
                //
                //                 Rectangle {
                //                     id: userBubble
                //                     anchors.right: parent.right
                //                     width: Math.min(parent.width * 0.80, userText.implicitWidth + 28)
                //                     height: userText.implicitHeight + 20
                //                     radius: 16
                //                     color: Theme.Colors.accentBlue
                //
                //                     Text {
                //                         id: userText
                //                         anchors.fill: parent
                //                         anchors.margins: 10
                //                         text: "帮我安排一下今天的工作"
                //                         font.pixelSize: 13
                //                         color: "white"
                //                         wrapMode: Text.Wrap
                //                     }
                //                 }
                //             }
                //         }
                //     }
                // }
            }

            Item { Layout.fillHeight: true }
        }
    }

    Component.onCompleted: {
        // Pre-fill from draft
        try {
            var a = onboardingDraft.getDraftAssistantName()
            var u = onboardingDraft.getDraftUserDisplayName()
            if (a) botField.text = a
            if (u) userField.text = u
            onboardingDraft.setDraftStep(4)
            onboardingDraft.saveDraft()
        } catch (e) {}
    }
}
