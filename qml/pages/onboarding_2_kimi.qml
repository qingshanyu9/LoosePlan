// qml/pages/onboarding_2_kimi.qml
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15
import QtQuick.Shapes 1.15

import theme 1.0 as Theme
import components 1.0 as C

C.GlassWindow {
    id: win
    title: "Onboarding - Step 2"

    // Python(main.py) 暴露：engine.rootContext().setContextProperty("kimiClient", kimi_client)
    property var _kimi: (typeof kimiClient !== "undefined") ? kimiClient : null

    property bool initializing: true
    property string kimiApiKey: ""
    property string kimiBaseUrl: "https://api.moonshot.cn/v1"
    property string kimiModel: "kimi-k2-thinking-turbo"

    property bool apiKeyVisible: false
    property bool testing: false
    property bool testSucceeded: false
    property string errorText: ""

    // 打开页面时自动做一次轻量 test（有 key 才测）
    property bool autoTestOnOpen: true
    property bool autoTestDone: false

    readonly property var modelOptions: [
        "kimi-k2-thinking-turbo",
        "kimi-k2-thinking",
        "kimi-k2",
        "kimi-k1.5",
        "kimi-latest"
    ]

    readonly property string eyeOpenPath:
        "M12 4.5C7 4.5 2.73 7.61 1 12c1.73 4.39 6 7.5 11 7.5s9.27-3.11 11-7.5c-1.73-4.39-6-7.5-11-7.5zM12 17c-2.76 0-5-2.24-5-5s2.24-5 5-5 5 2.24 5 5-2.24 5-5 5zm0-8c-1.66 0-3 1.34-3 3s1.34 3 3 3 3-1.34 3-3-1.34-3-3-3z"
    readonly property string eyeClosedPath:
        "M12 7c2.76 0 5 2.24 5 5 0 .65-.13 1.26-.36 1.83l2.92 2.92c1.51-1.26 2.7-2.89 3.43-4.75-1.73-4.39-6-7.5-11-7.5-1.4 0-2.74.25-3.98.7l2.16 2.16C10.74 7.13 11.35 7 12 7zM2 4.27l2.28 2.28.46.46C3.08 8.3 1.78 10.02 1 12c1.73 4.39 6 7.5 11 7.5 1.55 0 3.03-.3 4.38-.84l.42.42L19.73 22 21 20.73 3.27 3 2 4.27zM7.53 9.8l1.55 1.55c-.05.21-.08.43-.08.65 0 1.66 1.34 3 3 3 .22 0 .44-.03.65-.08l1.55 1.55c-.67.33-1.41.53-2.2.53-2.76 0-5-2.24-5-5 0-.79.2-1.53.53-2.2zm4.31-.78l3.15 3.15.02-.16c0-1.66-1.34-3-3-3l-.17.01z"

    Component.onCompleted: {
        try {
            x = Math.max(0, (Screen.width - width) / 2)
            y = Math.max(0, (Screen.height - height) / 2)
        } catch (e) {}
        initFromDraft()
        maybeAutoTest()
    }

    Connections {
        target: win._kimi
        ignoreUnknownSignals: true

        function onTestStarted() {
            win.testing = true
            win.testSucceeded = false
            win.errorText = ""
        }

        function onTestFinished(ok, message) {
            win.testing = false
            win.testSucceeded = ok
            win.errorText = ok ? "" : (message || "连接失败")
            if (ok) {
                showToast("连接成功")
                persistDraft()
            }
        }

        function onConnectedChanged() {
            if (!win._kimi) return
            win.testSucceeded = !!win._kimi.connected
        }
        function onLastErrorChanged() {
            if (!win._kimi) return
            if (!win._kimi.connected) win.errorText = win._kimi.lastError || ""
        }
        function onTestingChanged() {
            if (!win._kimi) return
            win.testing = !!win._kimi.testing
        }
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

    function doCancelAndQuit() {
        try { onboardingDraft.clearDraft() } catch (e) {}
        Qt.quit()
    }

    function normalizeBaseUrl(u) {
        var s = (u || "").trim()
        while (s.length > 0 && s.endsWith("/")) s = s.substring(0, s.length - 1)
        return s
    }

    function initFromDraft() {
        initializing = true
        try { onboardingDraft.loadDraft() } catch (e) {}

        var k = ""
        var u = ""
        var m = ""
        try { k = onboardingDraft.getDraftKimiApiKey() } catch (e1) { k = "" }
        try { u = onboardingDraft.getDraftKimiBaseUrl() } catch (e2) { u = "" }
        try { m = onboardingDraft.getDraftKimiModel() } catch (e3) { m = "" }

        kimiApiKey = (k || "").trim()
        kimiBaseUrl = (u || "").trim()
        kimiModel = (m || "").trim()

        if (kimiBaseUrl.length === 0) kimiBaseUrl = "https://api.moonshot.cn/v1"
        if (kimiModel.length === 0) kimiModel = "kimi-k2-thinking-turbo"

        apiKeyField.text = kimiApiKey
        baseUrlField.text = kimiBaseUrl
        modelCombo.editText = kimiModel

        testing = false
        testSucceeded = false
        errorText = ""

        try { onboardingDraft.setDraftStep(2) } catch (e4) {}
        initializing = false
    }

    function invalidateTest() {
        if (initializing) return
        testSucceeded = false
        errorText = ""
        if (win._kimi && win._kimi.resetStatus) {
            win._kimi.resetStatus()
        }
    }

    function scheduleSave() {
        if (initializing) return
        saveTimer.restart()
    }

    function persistDraft() {
        try {
            onboardingDraft.setDraftKimiApiKey(kimiApiKey)
            onboardingDraft.setDraftKimiBaseUrl(kimiBaseUrl)
            onboardingDraft.setDraftKimiModel(kimiModel)
            onboardingDraft.setDraftStep(2)
            onboardingDraft.saveDraft()
        } catch (e) {
            console.log("[kimi draft] save failed:", e)
        }
    }

    function showToast(text) {
        toastText.text = text
        toast.show()
    }

    function doTestConnection() {
        invalidateTest()

        var key = (kimiApiKey || "").trim()
        var base = normalizeBaseUrl(kimiBaseUrl)
        var model = (kimiModel || "").trim()

        if (key.length === 0) { errorText = "请先输入 API Key"; return }
        if (base.length === 0) { errorText = "Base URL 不能为空"; return }
        if (model.length === 0) { errorText = "Model 不能为空"; return }

        if (!win._kimi) {
            errorText = "未初始化 kimiClient（请在 Python 侧注册 context property）"
            return
        }

        win._kimi.testConnection(key, base, model)
    }

    function maybeAutoTest() {
        if (!autoTestOnOpen || autoTestDone) return
        autoTestDone = true

        var key = (kimiApiKey || "").trim()
        if (key.length === 0) return

        doTestConnection()
    }

    Timer {
        id: saveTimer
        interval: 300
        repeat: false
        onTriggered: persistDraft()
    }

    // ===== Toast =====
    Item {
        id: toast
        anchors.top: parent.top
        anchors.topMargin: 24
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.min(parent.width - 40, toastRow.implicitWidth + 28)
        height: 40
        z: 1000
        visible: false
        opacity: 0

        function show() { visible = true; opacity = 1; toastHideTimer.restart() }

        Rectangle {
            anchors.fill: parent
            radius: 10
            color: Qt.rgba(52/255, 199/255, 89/255, 0.95)
        }

        Row {
            id: toastRow
            anchors.centerIn: parent
            spacing: 8
            Text { text: "✓"; font.pixelSize: 16; color: "white" }
            Text { id: toastText; text: ""; font.pixelSize: 14; font.weight: Font.Medium; color: "white" }
        }

        Behavior on opacity { NumberAnimation { duration: 220; easing.type: Easing.OutCubic } }

        Timer {
            id: toastHideTimer
            interval: 1600
            repeat: false
            onTriggered: { toast.opacity = 0; toastVisibleTimer.restart() }
        }
        Timer {
            id: toastVisibleTimer
            interval: 260
            repeat: false
            onTriggered: toast.visible = false
        }
    }

    // ===== Icons =====
    Component {
        id: eyeIconComp
        Item {
            id: iconRoot
            property bool open: true
            width: 18
            height: 18
            Shape {
                anchors.fill: parent
                ShapePath {
                    fillColor: Theme.Colors.textSecondary
                    strokeColor: "transparent"
                    PathSvg { path: iconRoot.open ? win.eyeOpenPath : win.eyeClosedPath }
                }
            }
        }
    }

    Component {
        id: chevronDownComp
        Item {
            width: 10
            height: 10
            Shape {
                anchors.fill: parent
                ShapePath {
                    fillColor: Theme.Colors.textSecondary
                    strokeColor: "transparent"
                    PathSvg { path: "M7 10l5 5 5-5z" }
                }
            }
        }
    }

    C.WizardScaffold {
        id: wizard
        anchors.fill: parent

        stepIndex: 2
        stepTotal: 5
        titleText: "Kimi 配置"
        footerMode: "middle"

        prevEnabled: true
        nextEnabled: win.testSucceeded && (win.kimiApiKey.trim().length > 0)

        onMinimizeRequested: win.showMinimized()
        onCloseRequested: doCancelAndQuit()
        onCancelClicked: doCancelAndQuit()

        onPrevClicked: {
            persistDraft()
            try { onboardingDraft.setDraftStep(1); onboardingDraft.saveDraft() } catch (e) {}
            openStep("onboarding_1_data_dir.qml")
        }

        onNextClicked: {
            if (!win.testSucceeded) return
            try {
                onboardingDraft.setDraftKimiApiKey(win.kimiApiKey)
                onboardingDraft.setDraftKimiBaseUrl(win.kimiBaseUrl)
                onboardingDraft.setDraftKimiModel(win.kimiModel)
                onboardingDraft.setDraftStep(3)
                onboardingDraft.saveDraft()
            } catch (e) {}
            openStep("onboarding_3_feishu.qml")
        }

        Item {
            anchors.fill: parent

            ColumnLayout {
                anchors.fill: parent
                spacing: 0

                Rectangle {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    implicitHeight: formCol.implicitHeight + 48
                    Layout.preferredHeight: implicitHeight

                    radius: Theme.Metrics.cardRadius
                    color: Qt.rgba(1, 1, 1, 0.50)
                    border.width: Theme.Metrics.borderW
                    border.color: Theme.Colors.glassBorder

                    Item {
                        anchors.fill: parent
                        anchors.margins: 24

                        ColumnLayout {
                            id: formCol
                            anchors.fill: parent
                            spacing: 16

                            // ===== API Key =====
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 6

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 4
                                    Label {
                                        text: "API Key"
                                        font.pixelSize: 13
                                        font.weight: Font.DemiBold
                                        color: Theme.Colors.textPrimary
                                    }
                                    Label {
                                        text: "*"
                                        font.pixelSize: 13
                                        font.weight: Font.DemiBold
                                        color: Theme.Colors.danger
                                    }
                                    Item { Layout.fillWidth: true }
                                }

                                Item {
                                    Layout.fillWidth: true
                                    height: Theme.Metrics.inputH

                                    TextField {
                                        id: apiKeyField
                                        anchors.fill: parent
                                        anchors.rightMargin: 44

                                        echoMode: win.apiKeyVisible ? TextInput.Normal : TextInput.Password
                                        placeholderText: "请输入您的 Kimi API Key"
                                        font.pixelSize: 14
                                        color: Theme.Colors.textPrimary
                                        inputMethodHints: Qt.ImhNoPredictiveText | Qt.ImhNoAutoUppercase

                                        leftPadding: 14
                                        rightPadding: 14

                                        background: Rectangle {
                                            radius: Theme.Metrics.inputRadius
                                            color: Qt.rgba(1, 1, 1, 0.85)
                                            border.width: Theme.Metrics.borderW
                                            border.color: apiKeyField.activeFocus ? Theme.Colors.primary : Theme.Colors.inputBorder
                                        }

                                        onTextChanged: {
                                            if (win.initializing) return
                                            win.kimiApiKey = text
                                            invalidateTest()
                                            scheduleSave()
                                        }
                                    }

                                    ToolButton {
                                        id: toggleKeyBtn
                                        anchors.right: parent.right
                                        anchors.rightMargin: 12
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 26
                                        height: 26
                                        hoverEnabled: true
                                        background: Rectangle { color: "transparent" }

                                        contentItem: Loader {
                                            anchors.centerIn: parent
                                            sourceComponent: eyeIconComp
                                            onLoaded: item.open = !win.apiKeyVisible
                                        }

                                        opacity: hovered ? 0.8 : 0.5

                                        onClicked: {
                                            win.apiKeyVisible = !win.apiKeyVisible
                                            if (contentItem && contentItem.item) contentItem.item.open = !win.apiKeyVisible
                                        }
                                    }
                                }
                            }

                            // ===== Base URL =====
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 6

                                Label {
                                    text: "Base URL"
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                    color: Theme.Colors.textPrimary
                                }

                                TextField {
                                    id: baseUrlField
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: Theme.Metrics.inputH
                                    placeholderText: "https://api.moonshot.cn/v1"
                                    font.pixelSize: 14
                                    color: Theme.Colors.textPrimary
                                    inputMethodHints: Qt.ImhUrlCharactersOnly | Qt.ImhNoAutoUppercase

                                    leftPadding: 14
                                    rightPadding: 14

                                    background: Rectangle {
                                        radius: Theme.Metrics.inputRadius
                                        color: Qt.rgba(1, 1, 1, 0.85)
                                        border.width: Theme.Metrics.borderW
                                        border.color: baseUrlField.activeFocus ? Theme.Colors.primary : Theme.Colors.inputBorder
                                    }

                                    onTextChanged: {
                                        if (win.initializing) return
                                        win.kimiBaseUrl = text
                                        invalidateTest()
                                        scheduleSave()
                                    }
                                }
                            }

                            // ===== Model =====
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 6

                                Label {
                                    text: "Model"
                                    font.pixelSize: 13
                                    font.weight: Font.DemiBold
                                    color: Theme.Colors.textPrimary
                                }

                                ComboBox {
                                    id: modelCombo
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: Theme.Metrics.inputH

                                    editable: true
                                    model: win.modelOptions
                                    font.pixelSize: 14

                                    contentItem: TextField {
                                        id: modelEdit
                                        text: modelCombo.editText
                                        font.pixelSize: 14
                                        color: Theme.Colors.textPrimary
                                        leftPadding: 14
                                        rightPadding: 36
                                        background: null
                                        selectByMouse: true
                                        inputMethodHints: Qt.ImhNoPredictiveText | Qt.ImhNoAutoUppercase
                                        onTextEdited: modelCombo.editText = text
                                        Keys.onPressed: function(ev) {
                                            if (ev.key === Qt.Key_Down) {
                                                modelCombo.popup.open()
                                                ev.accepted = true
                                            }
                                        }
                                    }

                                    indicator: Item {
                                        width: 36
                                        height: parent.height
                                        anchors.right: parent.right

                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: {
                                                if (modelCombo.popup.visible) modelCombo.popup.close()
                                                else modelCombo.popup.open()
                                            }
                                        }

                                        Loader {
                                            anchors.verticalCenter: parent.verticalCenter
                                            anchors.verticalCenterOffset: -3
                                            anchors.right: parent.right
                                            anchors.rightMargin: 14
                                            sourceComponent: chevronDownComp
                                            opacity: 0.55
                                        }
                                    }

                                    background: Rectangle {
                                        radius: Theme.Metrics.inputRadius
                                        color: Qt.rgba(1, 1, 1, 0.85)
                                        border.width: Theme.Metrics.borderW
                                        border.color: modelCombo.activeFocus ? Theme.Colors.primary : Theme.Colors.inputBorder
                                    }

                                    popup: Popup {
                                        y: modelCombo.height + 6
                                        width: modelCombo.width
                                        implicitHeight: Math.min(contentItem.implicitHeight, 240)
                                        padding: 6

                                        background: Rectangle {
                                            radius: 10
                                            color: Qt.rgba(1, 1, 1, 0.98)
                                            border.width: 1
                                            border.color: Theme.Colors.inputBorder
                                        }

                                        contentItem: ListView {
                                            implicitHeight: contentHeight
                                            model: modelCombo.delegateModel
                                            currentIndex: modelCombo.highlightedIndex
                                            clip: true
                                            ScrollIndicator.vertical: ScrollIndicator { }
                                        }
                                    }

                                    delegate: ItemDelegate {
                                        width: modelCombo.width - 12
                                        text: modelData
                                        font.pixelSize: 14
                                        highlighted: modelCombo.highlightedIndex === index
                                    }

                                    onActivated: {
                                        if (win.initializing) return
                                        win.kimiModel = currentText
                                        invalidateTest()
                                        scheduleSave()
                                    }

                                    onEditTextChanged: {
                                        if (win.initializing) return
                                        win.kimiModel = editText
                                        invalidateTest()
                                        scheduleSave()
                                    }
                                }
                            }

                            // ===== Test section =====
                            ColumnLayout {
                                Layout.fillWidth: true
                                spacing: 10
                                Layout.topMargin: 20

                                RowLayout {
                                    Layout.fillWidth: true

                                    Item { Layout.fillWidth: true }

                                    C.PrimaryButton {
                                        id: testBtn
                                        enabled: !win.testing
                                        implicitWidth: 120
                                        text: win.testing ? "检查中..." : "测试连接"
                                        Layout.alignment: Qt.AlignHCenter
                                        onClicked: doTestConnection()
                                    }

                                    Item { Layout.fillWidth: true }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    spacing: 6
                                    visible: win.testing || win.testSucceeded || ((win.kimiApiKey.trim().length > 0) && (win.errorText.length > 0))

                                    Text {
                                        text: win.testing ? "⟲︎" : (win.testSucceeded ? "✓" : "⚠")
                                        font.pixelSize: 16
                                        color: win.testing ? Theme.Colors.textSecondary : (win.testSucceeded ? Theme.Colors.success : Theme.Colors.danger)
                                    }

                                    Label {
                                        Layout.fillWidth: true
                                        text: win.testing
                                              ? "正在检查连接，稍等片刻..."
                                              : (win.testSucceeded
                                                 ? "已连接"
                                                 : (win.errorText.length > 0 ? win.errorText : "不可用：请检查网络或 Key"))
                                        font.pixelSize: 13
                                        font.weight: Font.Medium
                                        color: win.testing ? Theme.Colors.textSecondary : (win.testSucceeded ? Theme.Colors.success : Theme.Colors.danger)
                                        wrapMode: Text.WordWrap
                                    }
                                }

                            }
                        }
                    }
                }

                Item { Layout.fillHeight: true }
            }
        }
    }
}
