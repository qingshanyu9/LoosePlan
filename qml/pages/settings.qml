import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Window 2.15

Window {
    id: win
    width: 680
    height: 520
    visible: true
    color: "transparent"
    title: "设置"
    flags: Qt.FramelessWindowHint | Qt.Window

    readonly property var settingsApi: (typeof settingsService !== "undefined") ? settingsService : null
    readonly property var kimiApi: (typeof kimiClient !== "undefined") ? kimiClient : null
    readonly property var feishuApi: (typeof feishuSocket !== "undefined") ? feishuSocket : null
    readonly property var chatApi: (typeof chatService !== "undefined") ? chatService : null

    property string currentTab: "api"
    property bool initializing: true
    property string kimiApiKeyText: ""
    property string kimiBaseUrlText: "https://api.moonshot.cn/v1"
    property string kimiModelText: "kimi-k2-thinking-turbo"
    property string feishuAppIdText: ""
    property string feishuAppSecretText: ""
    property int weeklyReviewWeekdayValue: 0
    property bool weeklySyncFeishuValue: true
    property int reminderValue: 10
    property bool startupEnabledValue: false
    property string currentDataDirText: ""
    property bool kimiDirty: false
    property bool feishuDirty: false

    readonly property var tabItems: [
        { "key": "api", "label": "API" },
        { "key": "push", "label": "推送" },
        { "key": "data", "label": "数据" },
        { "key": "appearance", "label": "外观" }
    ]

    readonly property var weekdayItems: [
        { "label": "周日晚上", "value": 0 },
        { "label": "周一早上", "value": 1 },
        { "label": "周五晚上", "value": 5 },
        { "label": "周六晚上", "value": 6 }
    ]

    function weekdayIndexForValue(value) {
        for (var i = 0; i < weekdayItems.length; i++) {
            if (weekdayItems[i].value === value)
                return i
        }
        return 0
    }

    function weekdayValueForIndex(index) {
        if (index >= 0 && index < weekdayItems.length)
            return weekdayItems[index].value
        return 0
    }

    function showToast(message) {
        if (!message || message.length === 0)
            return
        toastText.text = message
        toast.visible = true
        toast.opacity = 1
        toastHideTimer.restart()
    }

    function loadFromSettings() {
        if (!settingsApi)
            return
        initializing = true
        kimiApiKeyText = settingsApi.kimiApiKey || ""
        kimiBaseUrlText = settingsApi.kimiBaseUrl || "https://api.moonshot.cn/v1"
        kimiModelText = settingsApi.kimiModel || "kimi-k2-thinking-turbo"
        feishuAppIdText = settingsApi.feishuAppId || ""
        feishuAppSecretText = settingsApi.feishuAppSecret || ""
        weeklyReviewWeekdayValue = settingsApi.weeklyReviewWeekday
        weeklySyncFeishuValue = settingsApi.weeklyReviewSyncFeishu
        reminderValue = settingsApi.defaultRemindBeforeMin
        startupEnabledValue = settingsApi.autoStartEnabled
        currentDataDirText = settingsApi.dataDir || ""
        weeklyReviewCombo.currentIndex = weekdayIndexForValue(weeklyReviewWeekdayValue)
        kimiDirty = false
        feishuDirty = false
        initializing = false
    }

    function scheduleKimiSave() {
        if (!initializing)
            kimiSaveTimer.restart()
    }

    function scheduleFeishuSave() {
        if (!initializing)
            feishuSaveTimer.restart()
    }

    function schedulePushSave() {
        if (!initializing)
            pushSaveTimer.restart()
    }

    function kimiStatusMode() {
        if (kimiApi && kimiApi.testing)
            return "connecting"
        if ((kimiApiKeyText || "").trim().length === 0)
            return "disconnected"
        if (kimiDirty)
            return "disconnected"
        return (chatApi && chatApi.kimiConnected) ? "connected" : "disconnected"
    }

    function feishuStatusMode() {
        if (feishuApi && feishuApi.state === feishuApi.StateConnecting)
            return "connecting"
        if (feishuApi && feishuApi.state === feishuApi.StateConnected)
            return "connected"
        if (((feishuAppIdText || "").trim().length === 0) || ((feishuAppSecretText || "").trim().length === 0))
            return "disconnected"
        if (feishuDirty)
            return "disconnected"
        return (chatApi && chatApi.feishuConnected) ? "connected" : "disconnected"
    }

    function statusText(mode) {
        if (mode === "connected")
            return "已连接"
        if (mode === "connecting")
            return "连接中"
        return "未连接"
    }

    function statusBackground(mode) {
        if (mode === "connected")
            return Qt.rgba(52 / 255, 199 / 255, 89 / 255, 0.10)
        if (mode === "connecting")
            return Qt.rgba(10 / 255, 132 / 255, 1.0, 0.10)
        return Qt.rgba(1.0, 69 / 255, 58 / 255, 0.10)
    }

    function statusForeground(mode) {
        if (mode === "connected")
            return "#34C759"
        if (mode === "connecting")
            return "#0A84FF"
        return "#FF453A"
    }

    function testKimiConnection() {
        if (!settingsApi || !kimiApi) {
            showToast("Kimi 服务未初始化")
            return
        }
        kimiSaveTimer.stop()
        settingsApi.saveKimi(kimiApiKeyText, kimiBaseUrlText, kimiModelText)
        kimiApi.testConnection(kimiApiKeyText, kimiBaseUrlText, kimiModelText)
    }

    function testFeishuConnection() {
        if (!settingsApi || !feishuApi) {
            showToast("飞书服务未初始化")
            return
        }
        if ((feishuAppIdText || "").trim().length === 0 || (feishuAppSecretText || "").trim().length === 0) {
            showToast("请先填写 App ID 和 App Secret")
            return
        }
        feishuSaveTimer.stop()
        settingsApi.saveFeishu(feishuAppIdText, feishuAppSecretText)
        feishuApi.testConnection(feishuAppIdText, feishuAppSecretText)
    }

    onClosing: function(close) {
        close.accepted = false
        visible = false
    }

    Component.onCompleted: {
        x = Math.max(0, (Screen.width - width) / 2)
        y = Math.max(0, (Screen.height - height) / 2)
        if (settingsApi)
            settingsApi.reload()
        loadFromSettings()
    }

    Timer {
        id: kimiSaveTimer
        interval: 450
        repeat: false
        onTriggered: {
            if (settingsApi)
                settingsApi.saveKimi(kimiApiKeyText, kimiBaseUrlText, kimiModelText)
        }
    }

    Timer {
        id: feishuSaveTimer
        interval: 450
        repeat: false
        onTriggered: {
            if (settingsApi)
                settingsApi.saveFeishu(feishuAppIdText, feishuAppSecretText)
        }
    }

    Timer {
        id: pushSaveTimer
        interval: 300
        repeat: false
        onTriggered: {
            if (settingsApi)
                settingsApi.savePush(weeklyReviewWeekdayValue, weeklySyncFeishuValue, reminderValue)
        }
    }

    Timer {
        id: toastHideTimer
        interval: 2200
        repeat: false
        onTriggered: toast.opacity = 0
    }

    Connections {
        target: settingsApi
        ignoreUnknownSignals: true

        function onChanged() {
            if (!settingsApi)
                return
            currentDataDirText = settingsApi.dataDir || ""
            startupEnabledValue = settingsApi.autoStartEnabled
        }

        function onToastRequested(text) {
            showToast(text)
        }
    }

    Connections {
        target: kimiApi
        ignoreUnknownSignals: true

        function onTestFinished(ok, message) {
            kimiDirty = !ok
            showToast(ok ? "Kimi 连接成功" : (message || "Kimi 连接失败"))
        }
    }

    Connections {
        target: feishuApi
        ignoreUnknownSignals: true

        function onStateChanged(state) {
            if (feishuApi && state === feishuApi.StateConnected)
                feishuDirty = false
        }

        function onLastErrorChanged(message) {
            if (message && message.length > 0)
                showToast(message)
        }

        function onToastRequested(message) {
            if (message && message.length > 0)
                showToast(message)
        }
    }

    Rectangle {
        anchors.fill: parent
        radius: 18
        color: Qt.rgba(1, 1, 1, 0.72)
        border.width: 1
        border.color: Qt.rgba(0, 0, 0, 0.06)

        Rectangle {
            id: titleBar
            x: 0
            y: 0
            width: parent.width
            height: 44
            color: "transparent"

            MouseArea {
                anchors.fill: parent
                onPressed: win.startSystemMove()
            }

            Text {
                anchors.left: parent.left
                anchors.leftMargin: 24
                anchors.verticalCenter: parent.verticalCenter
                text: "设置"
                font.pixelSize: 14
                font.weight: Font.DemiBold
                color: "#111827"
            }

            Row {
                anchors.right: parent.right
                anchors.rightMargin: 24
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8

                Rectangle {
                    width: 12
                    height: 12
                    radius: 6
                    color: minimizeArea.containsMouse ? "#FFC642" : "#FFBD2E"

                    Rectangle {
                        anchors.centerIn: parent
                        visible: minimizeArea.containsMouse
                        width: 7
                        height: 1.6
                        radius: 1
                        color: "#7D5600"
                    }

                    MouseArea {
                        id: minimizeArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: win.showMinimized()
                    }
                }

                Rectangle {
                    width: 12
                    height: 12
                    radius: 6
                    color: closeArea.containsMouse ? "#FF6B63" : "#FF5F56"

                    Item {
                        anchors.centerIn: parent
                        visible: closeArea.containsMouse
                        width: 7
                        height: 7

                        Rectangle {
                            anchors.centerIn: parent
                            width: 7
                            height: 1.6
                            radius: 1
                            color: "#7A1A15"
                            rotation: 45
                            transformOrigin: Item.Center
                        }

                        Rectangle {
                            anchors.centerIn: parent
                            width: 7
                            height: 1.6
                            radius: 1
                            color: "#7A1A15"
                            rotation: -45
                            transformOrigin: Item.Center
                        }
                    }

                    MouseArea {
                        id: closeArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: win.visible = false
                    }
                }
            }
        }

        Rectangle {
            id: tabBar
            x: 0
            y: 44
            width: parent.width
            height: 52
            color: "transparent"

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: Qt.rgba(0, 0, 0, 0.06)
            }

            Row {
                anchors.left: parent.left
                anchors.leftMargin: 20
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8

                Repeater {
                    model: tabItems

                    delegate: Item {
                        width: tabLabel.implicitWidth + 40
                        height: tabBar.height

                        Text {
                            id: tabLabel
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.label
                            font.pixelSize: 14
                            font.weight: Font.Medium
                            color: win.currentTab === modelData.key ? "#0A84FF" : "#6B7280"
                        }

                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: 2
                            color: "#0A84FF"
                            visible: win.currentTab === modelData.key
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: win.currentTab = modelData.key
                        }
                    }
                }
            }
        }

        Flickable {
            id: contentFlickable
            x: 0
            y: 96
            width: parent.width
            height: parent.height - 96
            contentWidth: width
            contentHeight: Math.max(apiPanel.implicitHeight, pushPanel.implicitHeight, dataPanel.implicitHeight, appearancePanel.implicitHeight) + 40
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            ScrollBar.vertical: ScrollBar {
                width: 4
                policy: ScrollBar.AsNeeded
                contentItem: Rectangle {
                    implicitWidth: 4
                    radius: 2
                    color: Qt.rgba(0, 0, 0, 0.10)
                }
                background: Item { }
            }

            Column {
                id: apiPanel
                visible: win.currentTab === "api"
                width: contentFlickable.width
                spacing: 16
                leftPadding: 20
                rightPadding: 20
                topPadding: 20
                bottomPadding: 20

                Rectangle {
                    width: parent.width - 40
                    radius: 14
                    color: Qt.rgba(1, 1, 1, 0.60)
                    border.width: 1
                    border.color: Qt.rgba(0, 0, 0, 0.06)
                    implicitHeight: kimiCardBody.implicitHeight + 58

                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        height: 58
                        color: "transparent"

                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: 1
                            color: Qt.rgba(0, 0, 0, 0.06)
                        }

                        Text {
                            anchors.left: parent.left
                            anchors.leftMargin: 20
                            anchors.verticalCenter: parent.verticalCenter
                            text: "Kimi AI 配置"
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            color: "#111827"
                        }
                    }

                    Column {
                        id: kimiCardBody
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.topMargin: 58
                        anchors.leftMargin: 20
                        anchors.rightMargin: 20
                        anchors.bottomMargin: 20
                        spacing: 16

                        Item { width: 1; height: 4 }

                        Row {
                            width: kimiCardBody.width
                            height: 40
                            spacing: 16

                            Text {
                                width: 100
                                anchors.verticalCenter: parent.verticalCenter
                                text: "API Key"
                                font.pixelSize: 13
                                color: "#111827"
                            }

                            TextField {
                                width: parent.width - 116
                                height: 40
                                text: kimiApiKeyText
                                echoMode: TextInput.Password
                                placeholderText: "请输入你的 API Key"
                                font.pixelSize: 14
                                color: "#111827"
                                selectByMouse: true
                                leftPadding: 14
                                rightPadding: 14
                                background: Rectangle {
                                    radius: 10
                                    color: Qt.rgba(1, 1, 1, 0.50)
                                    border.width: 1
                                    border.color: Qt.rgba(0, 0, 0, 0.06)
                                }
                                onTextChanged: {
                                    kimiApiKeyText = text
                                    kimiDirty = true
                                    scheduleKimiSave()
                                }
                            }
                        }

                        Row {
                            width: kimiCardBody.width
                            height: 40
                            spacing: 16

                            Text {
                                width: 100
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Base URL"
                                font.pixelSize: 13
                                color: "#111827"
                            }

                            TextField {
                                width: parent.width - 116
                                height: 40
                                text: kimiBaseUrlText
                                placeholderText: "https://api.moonshot.cn/v1"
                                font.pixelSize: 14
                                color: "#111827"
                                selectByMouse: true
                                leftPadding: 14
                                rightPadding: 14
                                background: Rectangle {
                                    radius: 10
                                    color: Qt.rgba(1, 1, 1, 0.50)
                                    border.width: 1
                                    border.color: Qt.rgba(0, 0, 0, 0.06)
                                }
                                onTextChanged: {
                                    kimiBaseUrlText = text
                                    kimiDirty = true
                                    scheduleKimiSave()
                                }
                            }
                        }

                        Row {
                            width: kimiCardBody.width
                            height: 40
                            spacing: 16

                            Text {
                                width: 100
                                anchors.verticalCenter: parent.verticalCenter
                                text: "Model"
                                font.pixelSize: 13
                                color: "#111827"
                            }

                            TextField {
                                width: parent.width - 116
                                height: 40
                                text: kimiModelText
                                placeholderText: "kimi-k2-thinking-turbo"
                                font.pixelSize: 14
                                color: "#111827"
                                selectByMouse: true
                                leftPadding: 14
                                rightPadding: 14
                                background: Rectangle {
                                    radius: 10
                                    color: Qt.rgba(1, 1, 1, 0.50)
                                    border.width: 1
                                    border.color: Qt.rgba(0, 0, 0, 0.06)
                                }
                                onTextChanged: {
                                    kimiModelText = text
                                    kimiDirty = true
                                    scheduleKimiSave()
                                }
                            }
                        }

                        Row {
                            width: parent.width
                            height: 40
                            spacing: 16

                            Text {
                                width: 100
                                anchors.verticalCenter: parent.verticalCenter
                                text: "连通性"
                                font.pixelSize: 13
                                color: "#111827"
                            }

                            Rectangle {
                                width: 72
                                height: 32
                                radius: 16
                                color: statusBackground(kimiStatusMode())

                                Text {
                                    anchors.centerIn: parent
                                    text: statusText(kimiStatusMode())
                                    font.pixelSize: 12
                                    color: statusForeground(kimiStatusMode())
                                }
                            }

                            Button {
                                id: kimiTestButton
                                width: 90
                                height: 36
                                enabled: !(kimiApi && kimiApi.testing)
                                text: kimiApi && kimiApi.testing ? "连接中..." : "测试连接"
                                onClicked: testKimiConnection()
                                background: Rectangle {
                                    radius: 10
                                    color: parent.enabled ? Qt.rgba(0, 0, 0, 0.05) : Qt.rgba(0, 0, 0, 0.04)
                                }
                                contentItem: Text {
                                    text: kimiTestButton.text
                                    font.pixelSize: 13
                                    font.weight: Font.Medium
                                    color: "#111827"
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }

                        Item { width: 1; height: 4 }
                    }
                }

                Rectangle {
                    width: parent.width - 40
                    radius: 14
                    color: Qt.rgba(1, 1, 1, 0.60)
                    border.width: 1
                    border.color: Qt.rgba(0, 0, 0, 0.06)
                    implicitHeight: feishuCardBody.implicitHeight + 58

                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        height: 58
                        color: "transparent"

                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: 1
                            color: Qt.rgba(0, 0, 0, 0.06)
                        }

                        Text {
                            anchors.left: parent.left
                            anchors.leftMargin: 20
                            anchors.verticalCenter: parent.verticalCenter
                            text: "飞书配置"
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            color: "#111827"
                        }
                    }

                    Column {
                        id: feishuCardBody
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.topMargin: 58
                        anchors.leftMargin: 20
                        anchors.rightMargin: 20
                        anchors.bottomMargin: 20
                        spacing: 16

                        Item { width: 1; height: 4 }

                        Row {
                            width: feishuCardBody.width
                            height: 40
                            spacing: 16

                            Text {
                                width: 100
                                anchors.verticalCenter: parent.verticalCenter
                                text: "App ID"
                                font.pixelSize: 13
                                color: "#111827"
                            }

                            TextField {
                                width: parent.width - 116
                                height: 40
                                text: feishuAppIdText
                                placeholderText: "cli_xxxxxxxxxx"
                                font.pixelSize: 14
                                color: "#111827"
                                selectByMouse: true
                                leftPadding: 14
                                rightPadding: 14
                                background: Rectangle {
                                    radius: 10
                                    color: Qt.rgba(1, 1, 1, 0.50)
                                    border.width: 1
                                    border.color: Qt.rgba(0, 0, 0, 0.06)
                                }
                                onTextChanged: {
                                    feishuAppIdText = text
                                    feishuDirty = true
                                    scheduleFeishuSave()
                                }
                            }
                        }

                        Row {
                            width: feishuCardBody.width
                            height: 40
                            spacing: 16

                            Text {
                                width: 100
                                anchors.verticalCenter: parent.verticalCenter
                                text: "App Secret"
                                font.pixelSize: 13
                                color: "#111827"
                            }

                            TextField {
                                width: parent.width - 116
                                height: 40
                                text: feishuAppSecretText
                                echoMode: TextInput.Password
                                placeholderText: "请输入 App Secret"
                                font.pixelSize: 14
                                color: "#111827"
                                selectByMouse: true
                                leftPadding: 14
                                rightPadding: 14
                                background: Rectangle {
                                    radius: 10
                                    color: Qt.rgba(1, 1, 1, 0.50)
                                    border.width: 1
                                    border.color: Qt.rgba(0, 0, 0, 0.06)
                                }
                                onTextChanged: {
                                    feishuAppSecretText = text
                                    feishuDirty = true
                                    scheduleFeishuSave()
                                }
                            }
                        }

                        Row {
                            width: parent.width
                            height: 40
                            spacing: 16

                            Text {
                                width: 100
                                anchors.verticalCenter: parent.verticalCenter
                                text: "连通性"
                                font.pixelSize: 13
                                color: "#111827"
                            }

                            Rectangle {
                                width: 72
                                height: 32
                                radius: 16
                                color: statusBackground(feishuStatusMode())

                                Text {
                                    anchors.centerIn: parent
                                    text: statusText(feishuStatusMode())
                                    font.pixelSize: 12
                                    color: statusForeground(feishuStatusMode())
                                }
                            }

                            Button {
                                id: feishuTestButton
                                width: 90
                                height: 36
                                enabled: !(feishuApi && feishuApi.state === feishuApi.StateConnecting)
                                text: feishuApi && feishuApi.state === feishuApi.StateConnecting ? "连接中..." : "测试连接"
                                onClicked: testFeishuConnection()
                                background: Rectangle {
                                    radius: 10
                                    color: parent.enabled ? Qt.rgba(0, 0, 0, 0.05) : Qt.rgba(0, 0, 0, 0.04)
                                }
                                contentItem: Text {
                                    text: feishuTestButton.text
                                    font.pixelSize: 13
                                    font.weight: Font.Medium
                                    color: "#111827"
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }

                        Item { width: 1; height: 4 }
                    }
                }
            }

            Column {
                id: pushPanel
                visible: win.currentTab === "push"
                width: contentFlickable.width
                spacing: 16
                leftPadding: 20
                rightPadding: 20
                topPadding: 20
                bottomPadding: 20

                Rectangle {
                    width: parent.width - 40
                    radius: 14
                    color: Qt.rgba(1, 1, 1, 0.60)
                    border.width: 1
                    border.color: Qt.rgba(0, 0, 0, 0.06)
                    implicitHeight: weeklyCardBody.implicitHeight + 58

                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        height: 58
                        color: "transparent"

                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: 1
                            color: Qt.rgba(0, 0, 0, 0.06)
                        }

                        Text {
                            anchors.left: parent.left
                            anchors.leftMargin: 20
                            anchors.verticalCenter: parent.verticalCenter
                            text: "周回顾推送"
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            color: "#111827"
                        }
                    }

                    Column {
                        id: weeklyCardBody
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.topMargin: 58
                        anchors.leftMargin: 20
                        anchors.rightMargin: 20
                        anchors.bottomMargin: 20
                        spacing: 16

                        Item { width: 1; height: 4 }

                        Row {
                            width: parent.width
                            height: 40
                            spacing: 16

                            Text {
                                width: 100
                                anchors.verticalCenter: parent.verticalCenter
                                text: "推送时间"
                                font.pixelSize: 13
                                color: "#111827"
                            }

                            ComboBox {
                                id: weeklyReviewCombo
                                width: 130
                                height: 40
                                model: weekdayItems
                                textRole: "label"
                                currentIndex: weekdayIndexForValue(weeklyReviewWeekdayValue)
                                onActivated: {
                                    weeklyReviewWeekdayValue = weekdayValueForIndex(currentIndex)
                                    schedulePushSave()
                                }
                                background: Rectangle {
                                    radius: 10
                                    color: Qt.rgba(1, 1, 1, 0.50)
                                    border.width: 1
                                    border.color: Qt.rgba(0, 0, 0, 0.06)
                                }
                                contentItem: Text {
                                    text: weeklyReviewCombo.displayText
                                    font.pixelSize: 14
                                    color: "#111827"
                                    leftPadding: 14
                                    rightPadding: 24
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }

                        Row {
                            width: parent.width
                            height: 40
                            spacing: 16

                            Text {
                                width: 100
                                anchors.verticalCenter: parent.verticalCenter
                                text: "同步飞书"
                                font.pixelSize: 13
                                color: "#111827"
                            }

                            Row {
                                width: parent.width - 116
                                height: 40
                                spacing: 12
                                anchors.verticalCenter: parent.verticalCenter

                                Switch {
                                    id: weeklySyncSwitch
                                    width: 44
                                    height: 24
                                    checked: weeklySyncFeishuValue
                                    anchors.verticalCenter: parent.verticalCenter
                                    onToggled: {
                                        weeklySyncFeishuValue = checked
                                        schedulePushSave()
                                    }
                                    indicator: Rectangle {
                                        anchors.verticalCenter: parent.verticalCenter
                                        implicitWidth: 44
                                        implicitHeight: 24
                                        radius: 12
                                        color: weeklySyncSwitch.checked ? "#34C759" : Qt.rgba(0, 0, 0, 0.10)

                                        Rectangle {
                                            width: 20
                                            height: 20
                                            radius: 10
                                            y: 2
                                            x: weeklySyncSwitch.checked ? 22 : 2
                                            color: "white"
                                        }
                                    }
                                    contentItem: Item { }
                                }

                                Text {
                                    width: parent.width - weeklySyncSwitch.width - parent.spacing
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "推送时同时发送到飞书"
                                    font.pixelSize: 13
                                    color: "#111827"
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }

                        Item { width: 1; height: 4 }
                    }
                }

                Rectangle {
                    width: parent.width - 40
                    radius: 14
                    color: Qt.rgba(1, 1, 1, 0.60)
                    border.width: 1
                    border.color: Qt.rgba(0, 0, 0, 0.06)
                    implicitHeight: reminderCardBody.implicitHeight + 58

                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        height: 58
                        color: "transparent"

                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: 1
                            color: Qt.rgba(0, 0, 0, 0.06)
                        }

                        Text {
                            anchors.left: parent.left
                            anchors.leftMargin: 20
                            anchors.verticalCenter: parent.verticalCenter
                            text: "日程提醒"
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            color: "#111827"
                        }
                    }

                    Column {
                        id: reminderCardBody
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.topMargin: 58
                        anchors.leftMargin: 20
                        anchors.rightMargin: 20
                        anchors.bottomMargin: 20
                        spacing: 16

                        Item { width: 1; height: 4 }

                        Row {
                            width: parent.width
                            height: 40
                            spacing: 16

                            Text {
                                width: 100
                                anchors.verticalCenter: parent.verticalCenter
                                text: "提前提醒"
                                font.pixelSize: 13
                                color: "#111827"
                            }

                            Row {
                                width: parent.width - 116
                                height: 40
                                spacing: 12

                                Slider {
                                    id: reminderSlider
                                    width: parent.width - 56
                                    height: 40
                                    from: 0
                                    to: 60
                                    stepSize: 1
                                    value: reminderValue
                                    onMoved: {
                                        reminderValue = Math.round(value)
                                        schedulePushSave()
                                    }
                                    background: Rectangle {
                                        x: 0
                                        y: parent.height / 2 - height / 2
                                        width: parent.width
                                        height: 4
                                        radius: 2
                                        color: Qt.rgba(0, 0, 0, 0.10)
                                    }
                                    handle: Rectangle {
                                        x: reminderSlider.leftPadding + reminderSlider.visualPosition * (reminderSlider.availableWidth - width)
                                        y: reminderSlider.height / 2 - height / 2
                                        width: 16
                                        height: 16
                                        radius: 8
                                        color: "#0A84FF"
                                    }
                                }

                                Text {
                                    width: 44
                                    anchors.verticalCenter: parent.verticalCenter
                                    horizontalAlignment: Text.AlignRight
                                    text: reminderValue + "分钟"
                                    font.pixelSize: 13
                                    color: "#111827"
                                }
                            }
                        }

                        Item { width: 1; height: 4 }
                    }
                }
            }

            Column {
                id: dataPanel
                visible: win.currentTab === "data"
                width: contentFlickable.width
                spacing: 16
                leftPadding: 20
                rightPadding: 20
                topPadding: 20
                bottomPadding: 20

                Rectangle {
                    width: parent.width - 40
                    radius: 14
                    color: Qt.rgba(1, 1, 1, 0.60)
                    border.width: 1
                    border.color: Qt.rgba(0, 0, 0, 0.06)
                    implicitHeight: dirCardBody.implicitHeight + 58

                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        height: 58
                        color: "transparent"

                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: 1
                            color: Qt.rgba(0, 0, 0, 0.06)
                        }

                        Text {
                            anchors.left: parent.left
                            anchors.leftMargin: 20
                            anchors.verticalCenter: parent.verticalCenter
                            text: "数据目录"
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            color: "#111827"
                        }
                    }

                    Column {
                        id: dirCardBody
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.topMargin: 58
                        anchors.leftMargin: 20
                        anchors.rightMargin: 20
                        anchors.bottomMargin: 20
                        spacing: 16

                        Item { width: 1; height: 4 }

                        Row {
                            width: parent.width
                            height: 40
                            spacing: 16

                            Text {
                                width: 100
                                anchors.verticalCenter: parent.verticalCenter
                                text: "当前目录"
                                font.pixelSize: 13
                                color: "#111827"
                            }

                            TextField {
                                width: parent.width - 222
                                height: 40
                                readOnly: true
                                text: currentDataDirText
                                font.pixelSize: 14
                                color: "#111827"
                                leftPadding: 14
                                rightPadding: 14
                                background: Rectangle {
                                    radius: 10
                                    color: Qt.rgba(1, 1, 1, 0.50)
                                    border.width: 1
                                    border.color: Qt.rgba(0, 0, 0, 0.06)
                                }
                            }

                            Button {
                                id: changeDataDirButton
                                width: 90
                                height: 36
                                text: "更改"
                                onClicked: {
                                    if (settingsApi)
                                        settingsApi.chooseAndMoveDataDir()
                                }
                                background: Rectangle {
                                    radius: 10
                                    color: Qt.rgba(0, 0, 0, 0.05)
                                }
                                contentItem: Text {
                                    text: changeDataDirButton.text
                                    font.pixelSize: 13
                                    font.weight: Font.Medium
                                    color: "#111827"
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }

                        Text {
                            width: parent.width
                            text: "更改数据目录将自动迁移所有数据。建议先备份再操作。"
                            font.pixelSize: 12
                            color: "#6B7280"
                            wrapMode: Text.WordWrap
                        }

                        Item { width: 1; height: 4 }
                    }
                }

                Rectangle {
                    width: parent.width - 40
                    radius: 14
                    color: Qt.rgba(1, 1, 1, 0.60)
                    border.width: 1
                    border.color: Qt.rgba(0, 0, 0, 0.06)
                    implicitHeight: transferCardBody.implicitHeight + 58

                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        height: 58
                        color: "transparent"

                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: 1
                            color: Qt.rgba(0, 0, 0, 0.06)
                        }

                        Text {
                            anchors.left: parent.left
                            anchors.leftMargin: 20
                            anchors.verticalCenter: parent.verticalCenter
                            text: "导入/导出"
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            color: "#111827"
                        }
                    }

                    Column {
                        id: transferCardBody
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.topMargin: 58
                        anchors.leftMargin: 20
                        anchors.rightMargin: 20
                        anchors.bottomMargin: 20
                        spacing: 16

                        Item { width: 1; height: 4 }

                        Row {
                            width: parent.width
                            height: 40
                            spacing: 16

                            Text {
                                width: 100
                                anchors.verticalCenter: parent.verticalCenter
                                text: "导入数据"
                                font.pixelSize: 13
                                color: "#111827"
                            }

                            Button {
                                id: importButton
                                width: 90
                                height: 36
                                text: "选择文件"
                                onClicked: {
                                    if (settingsApi)
                                        settingsApi.importData()
                                }
                                background: Rectangle {
                                    radius: 10
                                    color: Qt.rgba(0, 0, 0, 0.05)
                                }
                                contentItem: Text {
                                    text: importButton.text
                                    font.pixelSize: 13
                                    font.weight: Font.Medium
                                    color: "#111827"
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }

                        Row {
                            width: parent.width
                            height: 40
                            spacing: 16

                            Text {
                                width: 100
                                anchors.verticalCenter: parent.verticalCenter
                                text: "导出数据"
                                font.pixelSize: 13
                                color: "#111827"
                            }

                            Button {
                                id: exportButton
                                width: 108
                                height: 36
                                text: "导出为 ZIP"
                                onClicked: {
                                    if (settingsApi)
                                        settingsApi.exportData()
                                }
                                background: Rectangle {
                                    radius: 10
                                    color: "#0A84FF"
                                }
                                contentItem: Text {
                                    text: exportButton.text
                                    font.pixelSize: 13
                                    font.weight: Font.Medium
                                    color: "white"
                                    horizontalAlignment: Text.AlignHCenter
                                    verticalAlignment: Text.AlignVCenter
                                }
                            }
                        }

                        Item { width: 1; height: 4 }
                    }
                }
            }

            Column {
                id: appearancePanel
                visible: win.currentTab === "appearance"
                width: contentFlickable.width
                spacing: 16
                leftPadding: 20
                rightPadding: 20
                topPadding: 20
                bottomPadding: 20

                Rectangle {
                    width: parent.width - 40
                    radius: 14
                    color: Qt.rgba(1, 1, 1, 0.60)
                    border.width: 1
                    border.color: Qt.rgba(0, 0, 0, 0.06)
                    implicitHeight: shortcutCardBody.implicitHeight + 58

                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        height: 58
                        color: "transparent"

                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: 1
                            color: Qt.rgba(0, 0, 0, 0.06)
                        }

                        Text {
                            anchors.left: parent.left
                            anchors.leftMargin: 20
                            anchors.verticalCenter: parent.verticalCenter
                            text: "快捷键"
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            color: "#111827"
                        }
                    }

                    Column {
                        id: shortcutCardBody
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.topMargin: 58
                        anchors.leftMargin: 20
                        anchors.rightMargin: 20
                        anchors.bottomMargin: 20
                        spacing: 16

                        Item { width: 1; height: 4 }

                        Repeater {
                            model: [
                                { "label": "显示 Orb", "value": "Alt + Shift + L" },
                                { "label": "打开聊天", "value": "Alt + Shift + C" },
                                { "label": "打开日程", "value": "Alt + Shift + S" }
                            ]

                            delegate: Row {
                                width: shortcutCardBody.width
                                height: 40
                                spacing: 16

                                Text {
                                    width: 100
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: modelData.label
                                    font.pixelSize: 13
                                    color: "#111827"
                                }

                                Rectangle {
                                    width: shortcutValue.implicitWidth + 20
                                    height: 30
                                    radius: 6
                                    color: Qt.rgba(0, 0, 0, 0.05)

                                    Text {
                                        id: shortcutValue
                                        anchors.centerIn: parent
                                        text: modelData.value
                                        font.family: "Consolas"
                                        font.pixelSize: 12
                                        color: "#111827"
                                    }
                                }
                            }
                        }

                        Item { width: 1; height: 4 }
                    }
                }

                Rectangle {
                    width: parent.width - 40
                    radius: 14
                    color: Qt.rgba(1, 1, 1, 0.60)
                    border.width: 1
                    border.color: Qt.rgba(0, 0, 0, 0.06)
                    implicitHeight: startupCardBody.implicitHeight + 58

                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        height: 58
                        color: "transparent"

                        Rectangle {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: 1
                            color: Qt.rgba(0, 0, 0, 0.06)
                        }

                        Text {
                            anchors.left: parent.left
                            anchors.leftMargin: 20
                            anchors.verticalCenter: parent.verticalCenter
                            text: "启动设置"
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            color: "#111827"
                        }
                    }

                    Column {
                        id: startupCardBody
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.topMargin: 58
                        anchors.leftMargin: 20
                        anchors.rightMargin: 20
                        anchors.bottomMargin: 20
                        spacing: 16

                        Item { width: 1; height: 4 }

                        Row {
                            width: parent.width
                            height: 40
                            spacing: 16

                            Text {
                                width: 100
                                anchors.verticalCenter: parent.verticalCenter
                                text: "开机自启"
                                font.pixelSize: 13
                                color: "#111827"
                            }

                            Row {
                                width: parent.width - 116
                                height: 40
                                spacing: 12
                                anchors.verticalCenter: parent.verticalCenter

                                Switch {
                                    id: startupSwitch
                                    width: 44
                                    height: 24
                                    checked: startupEnabledValue
                                    anchors.verticalCenter: parent.verticalCenter
                                    onToggled: {
                                        startupEnabledValue = checked
                                        if (settingsApi)
                                            settingsApi.setAutoStartEnabled(checked)
                                    }
                                    indicator: Rectangle {
                                        anchors.verticalCenter: parent.verticalCenter
                                        implicitWidth: 44
                                        implicitHeight: 24
                                        radius: 12
                                        color: startupSwitch.checked ? "#34C759" : Qt.rgba(0, 0, 0, 0.10)

                                        Rectangle {
                                            width: 20
                                            height: 20
                                            radius: 10
                                            y: 2
                                            x: startupSwitch.checked ? 22 : 2
                                            color: "white"
                                        }
                                    }
                                    contentItem: Item { }
                                }

                                Text {
                                    width: parent.width - startupSwitch.width - parent.spacing
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "系统启动时自动运行 LoosePlan"
                                    font.pixelSize: 13
                                    color: "#111827"
                                    wrapMode: Text.WordWrap
                                }
                            }
                        }

                        Item { width: 1; height: 4 }
                    }
                }
            }
        }
    }

    Rectangle {
        id: toast
        visible: false
        opacity: 0
        radius: 16
        color: Qt.rgba(0, 0, 0, 0.82)
        anchors.horizontalCenter: parent.horizontalCenter
        y: 12
        z: 999
        width: Math.min(360, toastText.implicitWidth + 24)
        height: 32

        Behavior on opacity {
            NumberAnimation { duration: 180 }
        }

        Text {
            id: toastText
            anchors.centerIn: parent
            text: ""
            font.pixelSize: 12
            color: "white"
        }

        onOpacityChanged: {
            if (opacity === 0)
                visible = false
        }
    }
}
