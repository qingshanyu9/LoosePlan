// qml/pages/onboarding_3_feishu.qml
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15

import theme 1.0 as Theme
import components 1.0 as C

C.GlassWindow {
    id: win
    title: "LoosePlan - Onboarding 3"

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

    // --- Toast ---
    function showToast(msg) {
        toastText.text = msg
        toast.visible = true
        toast.opacity = 0.0
        toast.y = 16
        toastAnim.restart()
        toastHideTimer.restart()
    }

    Timer {
        id: toastHideTimer
        interval: 2500
        repeat: false
        onTriggered: toast.visible = false
    }

    NumberAnimation {
        id: toastAnim
        target: toast
        property: "opacity"
        from: 0
        to: 1
        duration: 180
    }

    // Draft save debounce
    Timer {
        id: saveDebounce
        interval: 250
        repeat: false
        onTriggered: onboardingDraft.saveDraft()
    }

    function scheduleSave() { saveDebounce.restart() }

    function persistDraft() {
        onboardingDraft.setDraftStep(3)
        onboardingDraft.setDraftFeishuEnabled(!skipCheck.checked)
        onboardingDraft.setDraftFeishuAppId(appIdField.text)
        onboardingDraft.setDraftFeishuAppSecret(appSecretField.text)
        onboardingDraft.saveDraft()
    }

    Component.onCompleted: {
        onboardingDraft.loadDraft()

        appIdField.text = onboardingDraft.getDraftFeishuAppId()
        appSecretField.text = onboardingDraft.getDraftFeishuAppSecret()

        var enabled = onboardingDraft.getDraftFeishuEnabled()
        skipCheck.checked = !enabled

        updateUiEnabledState()

        onboardingDraft.setDraftStep(3)
        scheduleSave()
    }

    function updateUiEnabledState() {
        var isSkipped = skipCheck.checked
        appIdField.enabled = !isSkipped
        appSecretField.enabled = !isSkipped
        connectBtn.enabled = !isSkipped && (feishuSocket.state !== feishuSocket.StateConnecting)

        // Visual opacity like HTML
        appIdField.opacity = isSkipped ? 0.5 : 1.0
        appSecretField.opacity = isSkipped ? 0.5 : 1.0
    }

    function startConnection() {
        var appId = appIdField.text.trim()
        var appSecret = appSecretField.text.trim()
        if (appId.length === 0 || appSecret.length === 0) {
            showToast("请填写 App ID 和 App Secret")
            return
        }

        onboardingDraft.setDraftFeishuEnabled(true)
        onboardingDraft.setDraftFeishuAppId(appId)
        onboardingDraft.setDraftFeishuAppSecret(appSecret)
        onboardingDraft.saveDraft()

        feishuSocket.startLongConnection(appId, appSecret, onboardingDraft.getDraftFeishuBoundReceiveId())
    }

    // Keep UI in sync with service
    Connections {
        target: feishuSocket

        function onStateChanged(s) {
            updateUiEnabledState()
            if (s === feishuSocket.StateConnected) {
                showToast("✓ 飞书连接成功")
            }
        }

        function onLastErrorChanged(msg) {
            if (msg && msg.length > 0) showToast(msg)
        }

        function onToastRequested(msg) {
            if (msg && msg.length > 0) showToast(msg)
        }

        function onBoundReceiveIdChanged(id) {
            if (id && id.length > 0) showToast("✓ 飞书机器人绑定成功")
        }
    }

    C.WizardScaffold {
        anchors.fill: parent

        stepIndex: 3
        stepTotal: 5
        titleText: "配置飞书机器人"
        footerMode: "middle"

        // 启用飞书：必须连接成功才能下一步；跳过则直接下一步（对齐 html 逻辑）
        nextEnabled: skipCheck.checked || feishuSocket.state === feishuSocket.StateConnected
        prevEnabled: true

        onMinimizeRequested: win.showMinimized()
        onCloseRequested: {
            onboardingDraft.clearDraft()
            Qt.quit()
        }

        onCancelClicked: {
            onboardingDraft.clearDraft()
            Qt.quit()
        }
        onPrevClicked: {
            persistDraft()
            openStep("onboarding_2_kimi.qml")
        }
        onNextClicked: {
            persistDraft()
            openStep("onboarding_4_naming.qml")
        }

        // --- Content ---
        ColumnLayout {
            anchors.fill: parent
            anchors.leftMargin: 8   // content host is 32; +8 => 40 like html
            anchors.rightMargin: 8
            spacing: 16

            // Subtitle
            Label {
                Layout.fillWidth: true
                text: "连接飞书以在移动端接收日程提醒和进行对话"
                font.pixelSize: 14
                color: Theme.Colors.textSecondary
                wrapMode: Text.WordWrap
            }

            // App ID
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8

                Label {
                    text: "App ID"
                    font.pixelSize: 13
                    font.weight: Font.Medium
                    color: Theme.Colors.textPrimary
                }

                TextField {
                    id: appIdField
                    Layout.fillWidth: true
                    height: 44
                    placeholderText: "cli_xxxxxxxxxx"
                    font.pixelSize: 14
                    color: Theme.Colors.textPrimary
                    background: Rectangle {
                        radius: Theme.Metrics.inputRadius
                        border.width: 1
                        border.color: appIdField.activeFocus ? Theme.Colors.accentBlue : Theme.Colors.glassBorder
                        color: appIdField.activeFocus ? Qt.rgba(1, 1, 1, 0.8) : Qt.rgba(1, 1, 1, 0.5)
                    }
                    onTextChanged: {
                        onboardingDraft.setDraftFeishuAppId(text)
                        scheduleSave()
                    }
                }
            }

            // App Secret
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8

                Label {
                    text: "App Secret"
                    font.pixelSize: 13
                    font.weight: Font.Medium
                    color: Theme.Colors.textPrimary
                }

                TextField {
                    id: appSecretField
                    Layout.fillWidth: true
                    height: 44
                    echoMode: TextInput.Password
                    placeholderText: "输入你的 App Secret"
                    font.pixelSize: 14
                    color: Theme.Colors.textPrimary
                    background: Rectangle {
                        radius: Theme.Metrics.inputRadius
                        border.width: 1
                        border.color: appSecretField.activeFocus ? Theme.Colors.accentBlue : Theme.Colors.glassBorder
                        color: appSecretField.activeFocus ? Qt.rgba(1, 1, 1, 0.8) : Qt.rgba(1, 1, 1, 0.5)
                    }
                    onTextChanged: {
                        onboardingDraft.setDraftFeishuAppSecret(text)
                        scheduleSave()
                    }
                }
            }

            // Status section
            Rectangle {
                Layout.fillWidth: true
                radius: 14
                border.width: 1
                border.color: Theme.Colors.glassBorder
                color: Qt.rgba(1, 1, 1, 0.5)
                implicitHeight: 72

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 16
                    spacing: 12

                    // Icon
                    Rectangle {
                        width: 40
                        height: 40
                        radius: 20

                        property int st: feishuSocket.state

                        color: feishuSocket.state === feishuSocket.StateConnected
                            ? Qt.rgba(0.204, 0.780, 0.349, 0.10)   // success 10%
                            : (feishuSocket.state === feishuSocket.StateConnecting
                                ? Qt.rgba(1.0, 0.584, 0.0, 0.10)
                                : Qt.rgba(0.42, 0.45, 0.50, 0.10))

                        Label {
                            anchors.centerIn: parent
                            text: feishuSocket.state === feishuSocket.StateConnected ? "✓"
                                : (feishuSocket.state === feishuSocket.StateConnecting ? "⟲" : "📡")
                            font.pixelSize: 18
                            color: Theme.Colors.textPrimary
                        }                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        Label {
                            text: feishuSocket.state === feishuSocket.StateConnected ? "已连接"
                                  : (feishuSocket.state === feishuSocket.StateConnecting ? "连接中..." : "未连接")
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            color: Theme.Colors.textPrimary
                        }

                        Label {
                            Layout.fillWidth: true
                            wrapMode: Text.WordWrap
                            font.pixelSize: 13
                            color: Theme.Colors.textSecondary
                            text: {
                                if (skipCheck.checked) return "已跳过此步骤"
                                if (feishuSocket.state === feishuSocket.StateConnecting) return "正在与飞书服务器建立连接"
                                if (feishuSocket.state === feishuSocket.StateConnected) {
                                    return (feishuSocket.boundReceiveId && feishuSocket.boundReceiveId.length > 0)
                                           ? "机器人已绑定，可以开始使用飞书交互"
                                           : "机器人已就绪，请在飞书中发送任意消息完成绑定"
                                }
                                return "点击\"启动长连接\"开始连接飞书"
                            }
                        }
                    }

                    // Connect button
                    Button {
                        id: connectBtn
                        Layout.preferredHeight: 44
                        Layout.preferredWidth: 140
                        enabled: !skipCheck.checked && (feishuSocket.state !== feishuSocket.StateConnecting)

                        text: feishuSocket.state === feishuSocket.StateConnected ? "重新连接" : "启动长连接"

                        onClicked: startConnection()

                        contentItem: Row {
                            anchors.centerIn: parent
                            spacing: 8

                            BusyIndicator {
                                running: feishuSocket.state === feishuSocket.StateConnecting
                                visible: running
                                width: 16
                                height: 16
                            }

                            Text {
                                text: feishuSocket.state === feishuSocket.StateConnecting ? "连接中..." : connectBtn.text
                                font.pixelSize: 14
                                font.weight: Font.Medium
                                color: "white"
                            }
                        }

                        background: Rectangle {
                            radius: Theme.Metrics.inputRadius
                            color: connectBtn.enabled
                                   ? (connectBtn.down ? Theme.Colors.primaryHover : (connectBtn.hovered ? Theme.Colors.primaryHover : Theme.Colors.primary))
                                   : Theme.Colors.primary
                            opacity: connectBtn.enabled ? 1.0 : 0.5
                        }
                    }
                }
            }

            Item { Layout.fillHeight: true }

            // Skip section (custom checkbox)
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Item {
                    id: skipCheck
                    property bool checked: false
                    width: 18
                    height: 18

                    Rectangle {
                        anchors.fill: parent
                        radius: 3
                        border.width: 1
                        border.color: Theme.Colors.glassBorder
                        color: "transparent"
                    }

                    Rectangle {
                        anchors.fill: parent
                        radius: 3
                        color: Qt.rgba(Theme.Colors.accentBlue.r, Theme.Colors.accentBlue.g, Theme.Colors.accentBlue.b, 0.12)
                        border.width: 1
                        border.color: Theme.Colors.accentBlue
                        visible: skipCheck.checked
                    }

                    Text {
                        anchors.centerIn: parent
                        text: "✓"
                        font.pixelSize: 12
                        color: Theme.Colors.accentBlue
                        visible: skipCheck.checked
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            skipCheck.checked = !skipCheck.checked
                            onboardingDraft.setDraftFeishuEnabled(!skipCheck.checked)
                            if (skipCheck.checked) feishuSocket.stopLongConnection()
                            scheduleSave()
                            updateUiEnabledState()
                        }
                    }
                }

                Text {
                    text: "暂不启用飞书 / 跳过此步骤"
                    font.pixelSize: 14
                    color: Theme.Colors.textSecondary
                    verticalAlignment: Text.AlignVCenter

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            skipCheck.checked = !skipCheck.checked
                            onboardingDraft.setDraftFeishuEnabled(!skipCheck.checked)
                            if (skipCheck.checked) feishuSocket.stopLongConnection()
                            scheduleSave()
                            updateUiEnabledState()
                        }
                    }
                }
            }
        }
    }

    // Toast overlay (top-center)
    Rectangle {
        id: toast
        visible: false
        opacity: 0
        radius: 24
        color: Qt.rgba(0, 0, 0, 0.80)
        anchors.horizontalCenter: parent.horizontalCenter
        y: 24
        z: 2000

        height: 36
        width: Math.min(parent.width - 80, toastText.implicitWidth + 36)

        Text {
            id: toastText
            anchors.centerIn: parent
            font.pixelSize: 13
            color: "white"
            text: ""
        }
    }
}
