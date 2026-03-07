// qml/pages/onboarding_6_profile_result.qml
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15

import theme 1.0 as Theme
import components 1.0 as C

C.GlassWindow {
    id: win
    title: "Onboarding - Profile Result"

    property var profileResult: ({})
    property var labels: ({})
    property string summaryText: ""
    property string quickSummaryText: ""
    property string finishError: ""

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

    function openChatPage() {
        if (typeof windowManager !== "undefined" && windowManager && windowManager.openPage) {
            windowManager.openPage("chat", "chat.qml")
            Qt.callLater(function() {
                try { win.close() } catch (e) {
                    try { win.destroy() } catch (e2) {}
                }
            })
            return
        }

        var comp = Qt.createComponent("chat.qml")
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

    // 你说 onboarding 页关闭/取消就是退出程序：这里保持不改
    function exitAndClean() {
        try { onboardingDraft.clearDraft() } catch (e) {}
        Qt.quit()
    }

    function retakeQuiz() {
        onboardingDraft.clearQuizAndProfile()
        onboardingDraft.saveDraft()
        onboardingQuiz.resetQuiz()
        openStep("onboarding_5_quiz.qml")
    }

    function finish() {
        finishError = ""

        console.log("[finish] clicked. finalizer=", onboardingFinalizer)

        try {
            // 防抖答题的最终落盘（避免最后一刻答案没写进 draft）
            try { onboardingQuiz.flushPending() } catch (e) {}

            if (!onboardingFinalizer) {
                finishError = "onboardingFinalizer 未注入"
                console.log("[finish] " + finishError)
                return
            }

            var ok = onboardingFinalizer.finalizeFromDraft()
            console.log("[finish] finalize ok=", ok, " lastError=", onboardingFinalizer.lastError)

            if (!ok) {
                finishError = onboardingFinalizer.lastError ? onboardingFinalizer.lastError : "保存失败"
                return
            }

            // ✅ 关键：把“选中的 data_dir”写入 runtimeStore，保证后续都从正确目录读 config/data
            try {
                if (runtimeStore && onboardingDraft && onboardingDraft.getDraftDataDir) {
                    runtimeStore.lastDataDir = onboardingDraft.getDraftDataDir()
                    console.log("[finish] runtimeStore.lastDataDir=", runtimeStore.lastDataDir)
                }
            } catch (e) {
                console.log("[finish] set runtimeStore.lastDataDir failed:", e)
            }

            try { onboardingDraft.clearDraft() } catch (e) {}

            // onboarding 首次完成后立即按正式 config 启动飞书长连
            Qt.callLater(function() {
                try { feishuSocket.autoStart() } catch (e) {}
            })

            // ✅ 用 WindowManager 打开聊天页（保证窗口唯一实例策略）
            if (windowManager && windowManager.openPage) {
                openChatPage()
                win.close()
                return
            }

            // 兜底：没有 windowManager 就用旧方式
            openStep("chat.qml")

        } catch (e) {
            finishError = "" + e
            console.log("[finish] exception:", e)
    }
}

    function computeQuickSummary() {
        var parts = []
        function add(k) {
            var v = (labels && labels[k]) ? ("" + labels[k]).trim() : ""
            if (v.length) parts.push(v)
        }
        add("mbti")
        add("time_personality")
        add("schedule_style")
        add("task_preference")
        add("energy_peak")
        if (parts.length) return parts.join(" · ")

        var s = (summaryText || "").trim()
        if (!s.length) return ""
        var p = s.indexOf("。")
        if (p < 0) p = s.indexOf("！")
        if (p < 0) p = s.indexOf("？")
        if (p < 0) p = s.indexOf(".")
        if (p < 0) p = Math.min(30, s.length - 1)
        return s.substring(0, p + 1).trim()
    }

    Item {
        anchors.fill: parent

        Item {
            id: titleBar
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: 44

            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton
                onPressed: {
                    if (Window.window) Window.window.startSystemMove()
                }
                propagateComposedEvents: true
            }

            Row {
                spacing: 8
                anchors.right: parent.right
                anchors.rightMargin: 20
                anchors.verticalCenter: parent.verticalCenter
                z: 10

                Rectangle {
                    width: 12; height: 12; radius: 6
                    color: "white"
                    border.width: 1
                    border.color: Qt.rgba(0,0,0,0.10)

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onEntered: parent.color = "#FFBD2E"
                        onExited: parent.color = "white"
                        onClicked: win.showMinimized()
                    }
                }

                Rectangle {
                    width: 12; height: 12; radius: 6
                    color: "white"
                    border.width: 1
                    border.color: Qt.rgba(0,0,0,0.10)

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onEntered: parent.color = "#FF5F56"
                        onExited: parent.color = "white"
                        onClicked: exitAndClean()
                    }
                }
            }
        }

        Item {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: titleBar.bottom
            anchors.bottom: parent.bottom
            anchors.leftMargin: 40
            anchors.rightMargin: 40
            anchors.topMargin: 20
            anchors.bottomMargin: 30

            ColumnLayout {
                anchors.fill: parent
                spacing: 12

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Label {
                        text: "✓ 初始化完成"
                        font.pixelSize: 13
                        font.weight: Font.Medium
                        color: Theme.Colors.success
                    }
                    Label {
                        text: "你的专属档案已生成"
                        font.pixelSize: 24
                        font.weight: Font.DemiBold
                        color: Theme.Colors.textPrimary
                    }
                    Label {
                        Layout.fillWidth: true
                        text: "这是 LoosePlan 为你创建的工作画像，会随时间不断进化"
                        font.pixelSize: 14
                        color: Theme.Colors.textSecondary
                        wrapMode: Text.Wrap
                    }
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    spacing: 10

                    GridLayout {
                        Layout.fillWidth: true
                        columns: 4
                        rowSpacing: 8
                        columnSpacing: 8

                        Repeater {
                            model: [
                                { key: "mbti", label: "MBTI", color: Theme.Colors.accentBlue },
                                { key: "time_personality", label: "时间性格", color: "#AF52DE" },
                                { key: "industry", label: "所属行业", color: "#FF9500" },
                                { key: "schedule_style", label: "日程风格", color: Theme.Colors.success },
                                { key: "strength", label: "你更擅长", color: Theme.Colors.accentBlue },
                                { key: "rhythm", label: "你的节奏", color: "#AF52DE" },
                                { key: "energy_peak", label: "精力高峰", color: "#FF9500" },
                                { key: "task_preference", label: "任务偏好", color: Theme.Colors.success }
                            ]
                            delegate: Rectangle {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 76
                                radius: 10
                                color: Qt.rgba(1, 1, 1, 0.6)
                                border.width: 1
                                border.color: Theme.Colors.glassBorder

                                Column {
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    spacing: 4

                                    Text {
                                        text: modelData.label
                                        font.pixelSize: 13
                                        color: Theme.Colors.textSecondary
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        text: (labels && labels[modelData.key]) ? labels[modelData.key] : ""
                                        font.pixelSize: 18
                                        font.weight: Font.DemiBold
                                        color: modelData.color
                                        elide: Text.ElideRight
                                    }
                                }
                            }
                        }
                    }

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 72
                        radius: 14
                        color: Qt.rgba(1, 1, 1, 0.6)
                        border.width: 1
                        border.color: Theme.Colors.glassBorder
                        visible: quickSummaryText.length > 0

                        Column {
                            anchors.fill: parent
                            anchors.margins: 14
                            spacing: 6

                            Text {
                                text: "总结"
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                                color: Theme.Colors.accentBlue
                            }
                            Text {
                                text: summaryText.length ? ("\"" + summaryText + "\"") : "\"\""
                                font.pixelSize: 14
                                font.weight: Font.Medium
                                color: Theme.Colors.textPrimary
                                wrapMode: Text.Wrap
                                elide: Text.ElideRight
                            }
                        }
                    }

                    Item { Layout.fillHeight: true }

                    // ✅ 新增：错误提示（否则你会觉得“点了没反应”）
                    Text {
                        Layout.fillWidth: true
                        visible: finishError.length > 0
                        text: finishError
                        font.pixelSize: 12
                        color: Theme.Colors.danger
                        wrapMode: Text.Wrap
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12

                        C.SecondaryButton {
                            text: "重新答题"
                            implicitHeight: 44
                            onClicked: retakeQuiz()
                        }

                        Item { Layout.fillWidth: true }

                        C.PrimaryButton {
                            text: "完成，进入 LoosePlan"
                            implicitHeight: 44
                            implicitWidth: 260
                            enabled: !(onboardingFinalizer && onboardingFinalizer.busy)
                            onClicked: finish()
                        }
                    }
                }
            }
        }

        Rectangle {
            anchors.fill: parent
            color: Qt.rgba(0, 0, 0, 0.25)
            visible: onboardingFinalizer && onboardingFinalizer.busy
            z: 200

            Rectangle {
                width: 280
                height: 140
                radius: 16
                anchors.centerIn: parent
                color: Qt.rgba(1, 1, 1, 0.92)
                border.width: 1
                border.color: Theme.Colors.glassBorder

                Column {
                    anchors.centerIn: parent
                    spacing: 10

                    BusyIndicator {
                        width: 32
                        height: 32
                        running: parent.parent.visible
                    }

                    Text {
                        text: "正在保存配置..."
                        font.pixelSize: 13
                        color: Theme.Colors.textPrimary
                        horizontalAlignment: Text.AlignHCenter
                        width: parent.width
                    }
                    Text {
                        text: "完成后将进入 LoosePlan"
                        font.pixelSize: 12
                        color: Theme.Colors.textSecondary
                        horizontalAlignment: Text.AlignHCenter
                        width: parent.width
                    }
                }
            }
        }
    }

    Component.onCompleted: {
        try { onboardingDraft.loadDraft() } catch(e) {}
        profileResult = onboardingDraft.getDraftProfileResult()
        if (profileResult && profileResult.profile) {
            labels = profileResult.profile.labels || ({})
            summaryText = profileResult.profile.summary || ""
        } else {
            labels = ({})
            summaryText = ""
        }
        quickSummaryText = computeQuickSummary()
    }
}
