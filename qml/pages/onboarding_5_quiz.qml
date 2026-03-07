// qml/pages/onboarding_5_quiz.qml
// Step 5/5 - Quiz (3 groups x 7 questions) + generate profile via Kimi
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15

import theme 1.0 as Theme
import components 1.0 as C

C.GlassWindow {
    id: win
    title: "Onboarding - Step 5"

    property int questionIndex: 0
    property var currentQ: ({})
    property bool ready: false

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

    function refreshQuestion() {
        if (!onboardingQuiz) return
        currentQ = onboardingQuiz.getQuestion(questionIndex)
        optionsModel.clear()
        if (currentQ && currentQ.options) {
            for (var i = 0; i < currentQ.options.length; i++) {
                var opt = currentQ.options[i]
                var sel = false
                if (currentQ.selected && currentQ.selected.length) {
                    for (var j = 0; j < currentQ.selected.length; j++) {
                        if (currentQ.selected[j] === opt.key) { sel = true; break }
                    }
                }
                optionsModel.append({
                    key: opt.key,
                    text: opt.text,
                    selected: sel
                })
            }
        }
        nextBtn.enabled = onboardingQuiz.isAnswered(questionIndex)
        prevBtn.enabled = questionIndex > 0
        nextBtn.text = (questionIndex === onboardingQuiz.totalQuestions() - 1) ? "提交" : "下一题"
        ready = true
    }

    function toggleOption(key) {
        onboardingQuiz.toggleOption(questionIndex, key)
        refreshQuestion()
    }

    function prevQuestion() {
        if (questionIndex <= 0) return
        questionIndex -= 1
        onboardingQuiz.setCurrentIndex(questionIndex)
        refreshQuestion()
    }

    function nextQuestion() {
        if (!onboardingQuiz.isAnswered(questionIndex)) return
        if (questionIndex < onboardingQuiz.totalQuestions() - 1) {
            questionIndex += 1
            onboardingQuiz.setCurrentIndex(questionIndex)
            refreshQuestion()
            return
        }
        // submit
        try { onboardingQuiz.flushPending() } catch(e) {}
        profileGenerator.generateFromDraft()
    }

    function exitAndClean() {
        try { onboardingDraft.clearDraft() } catch (e) {}
        Qt.quit()
    }

    ListModel { id: optionsModel }

    Item {
        anchors.fill: parent

        C.TitleBar {
            id: titleBar
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            stepText: "步骤 5/5"
            titleText: "专属档案生成"
            onMinimizeRequested: win.showMinimized()
            onCloseRequested: exitAndClean()
        }

        Item {
            id: content
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: titleBar.bottom
            anchors.bottom: parent.bottom
            anchors.leftMargin: 32
            anchors.rightMargin: 32
            anchors.topMargin: 12
            anchors.bottomMargin: 16

            ColumnLayout {
                anchors.fill: parent
                spacing: 12

                Label {
                    Layout.fillWidth: true
                    text: "回答几个问题，帮助 LoosePlan 了解你的工作习惯和偏好"
                    font.pixelSize: 13
                    color: Theme.Colors.textSecondary
                    wrapMode: Text.Wrap
                }

                Rectangle {
                    id: questionCard
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    radius: 14
                    color: Qt.rgba(1, 1, 1, 0.5)
                    border.width: 1
                    border.color: Theme.Colors.glassBorder

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 16
                        spacing: 12

                        Label {
                            Layout.fillWidth: true
                            text: (currentQ && currentQ.group_name ? (currentQ.group_name + " · 第 " + (currentQ.q_index_in_group || 1) + " 题") : "")
                            font.pixelSize: 11
                            font.weight: Font.Medium
                            color: Theme.Colors.accentBlue
                            visible: ready
                        }

                        Label {
                            Layout.fillWidth: true
                            text: currentQ && currentQ.title ? currentQ.title : ""
                            font.pixelSize: 16
                            font.weight: Font.Medium
                            color: Theme.Colors.textPrimary
                            wrapMode: Text.Wrap
                            visible: ready
                        }

                        Flickable {
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            clip: true
                            contentWidth: width
                            contentHeight: optionsCol.implicitHeight
                            interactive: contentHeight > height

                            Column {
                                id: optionsCol
                                width: parent.width
                                spacing: 8

                                Repeater {
                                    model: optionsModel
                                    delegate: Rectangle {
                                        id: optItem
                                        width: optionsCol.width
                                        radius: 10
                                        color: model.selected ? Qt.rgba(10/255, 132/255, 255/255, 0.08) : Qt.rgba(1, 1, 1, 0.6)
                                        border.width: 1
                                        border.color: model.selected ? Theme.Colors.accentBlue : "transparent"

                                        property bool isMulti: (currentQ && currentQ.type === "multi")

                                        implicitHeight: Math.max(40, 10 + optionText.implicitHeight + 10)

                                        Row {
                                            anchors.fill: parent
                                            anchors.leftMargin: 12
                                            anchors.rightMargin: 12
                                            anchors.topMargin: 10
                                            anchors.bottomMargin: 10
                                            spacing: 10

                                            Item {
                                                width: 18
                                                height: 18

                                                Rectangle {
                                                    anchors.centerIn: parent
                                                    width: 18
                                                    height: 18
                                                    radius: 9
                                                    color: "transparent"
                                                    border.width: 1
                                                    border.color: model.selected ? Theme.Colors.accentBlue : Qt.rgba(0,0,0,0.18)
                                                    visible: !optItem.isMulti
                                                }
                                                Rectangle {
                                                    anchors.centerIn: parent
                                                    width: 10
                                                    height: 10
                                                    radius: 5
                                                    color: Theme.Colors.accentBlue
                                                    visible: (!optItem.isMulti) && model.selected
                                                }

                                                Rectangle {
                                                    anchors.centerIn: parent
                                                    width: 18
                                                    height: 18
                                                    radius: 4
                                                    color: model.selected ? Theme.Colors.accentBlue : "transparent"
                                                    border.width: 1
                                                    border.color: model.selected ? Theme.Colors.accentBlue : Qt.rgba(0,0,0,0.18)
                                                    visible: optItem.isMulti
                                                }
                                                Text {
                                                    anchors.centerIn: parent
                                                    text: "✓"
                                                    font.pixelSize: 14
                                                    color: "white"
                                                    visible: optItem.isMulti && model.selected
                                                }
                                            }

                                            Text {
                                                id: optionText
                                                width: optItem.width - 18 - 10 - 24
                                                text: model.text
                                                font.pixelSize: 14
                                                color: Theme.Colors.textPrimary
                                                wrapMode: Text.Wrap
                                            }
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: toggleOption(model.key)
                                        }

                                        MouseArea {
                                            id: optHover
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            acceptedButtons: Qt.NoButton
                                        }

                                        states: [
                                            State {
                                                name: "hover"
                                                when: optHover.containsMouse
                                                PropertyChanges {
                                                    target: optItem
                                                    color: model.selected ? Qt.rgba(10/255, 132/255, 255/255, 0.10) : Qt.rgba(1, 1, 1, 0.9)
                                                    border.color: model.selected ? Theme.Colors.accentBlue : Theme.Colors.glassBorder
                                                }
                                            }
                                        ]
                                    }
                                }
                            }
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 12

                            Row {
                                spacing: 6
                                Layout.alignment: Qt.AlignVCenter

                                Repeater {
                                    model: 3
                                    delegate: Rectangle {
                                        width: 28
                                        height: 5
                                        radius: 3

                                        property int idx: index
                                        property int g: onboardingQuiz.groupIndexForQuestion(questionIndex)

                                        color: (idx < g)
                                               ? Theme.Colors.success
                                               : ((idx === g) ? Theme.Colors.accentBlue : Qt.rgba(0,0,0,0.10))
                                    }
                                }
                            }

                            Item { Layout.fillWidth: true }

                            RowLayout {
                                spacing: 12

                                C.SecondaryButton {
                                    id: prevBtn
                                    text: "上一题"
                                    enabled: questionIndex > 0
                                    implicitHeight: 40
                                    onClicked: prevQuestion()
                                }

                                C.PrimaryButton {
                                    id: nextBtn
                                    text: "下一题"
                                    enabled: false
                                    implicitHeight: 40
                                    onClicked: nextQuestion()
                                }
                            }
                        }
                    }
                }
            }
        }

        Rectangle {
            id: loadingOverlay
            anchors.fill: parent
            color: Qt.rgba(0, 0, 0, 0.25)
            visible: profileGenerator && profileGenerator.busy
            z: 200

            Rectangle {
                width: 260
                height: 160
                radius: 16
                anchors.centerIn: parent
                color: Qt.rgba(1, 1, 1, 0.92)
                border.width: 1
                border.color: Theme.Colors.glassBorder

                Column {
                    anchors.centerIn: parent
                    spacing: 10

                    BusyIndicator {
                        width: 34
                        height: 34
                        running: loadingOverlay.visible
                    }

                    Text {
                        text: "正在生成你的专属档案..."
                        font.pixelSize: 13
                        color: Theme.Colors.textPrimary
                        horizontalAlignment: Text.AlignHCenter
                        width: parent.width
                    }
                    Text {
                        text: "AI 正在分析你的工作模式和偏好"
                        font.pixelSize: 12
                        color: Theme.Colors.textSecondary
                        horizontalAlignment: Text.AlignHCenter
                        width: parent.width
                    }
                }
            }
        }
    }

    Connections {
        target: profileGenerator
        function onFinished(ok, errMsg) {
            if (ok) {
                Qt.callLater(function() {
                    openStep("onboarding_6_profile_result.qml")
                })
            } else {
                console.log("profile generation failed: " + errMsg)
            }
        }
    }

    Component.onCompleted: {
        try { onboardingDraft.loadDraft() } catch(e) {}
        onboardingQuiz.loadOrInit()
        questionIndex = onboardingQuiz.getCurrentIndexOrZero()
        refreshQuestion()
    }
}
