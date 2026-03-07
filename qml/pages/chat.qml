import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15

Window {
    id: win
    width: 600
    height: 520
    visible: true
    color: "transparent"
    title: "聊天"
    flags: Qt.FramelessWindowHint | Qt.Window

    readonly property var chatApi: (typeof chatService !== "undefined") ? chatService : null
    readonly property var scheduleApi: (typeof scheduleService !== "undefined") ? scheduleService : null

    property string selectedDate: ""
    property int pickerYear: 0
    property int pickerMonth: 0
    property int pickerDay: 0
    property var yearOptions: []
    property var monthOptions: []
    property var dayOptions: []
    property bool hasPendingAction: false
    property string pendingConfirmText: ""
    property bool syncingPicker: false
    property string lastSentText: ""
    property double lastSentAtMs: 0

    function pad2(v) {
        return (v < 10 ? "0" : "") + v
    }

    function todayDateStr() {
        const d = new Date()
        return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate())
    }

    function assistantName() {
        return chatApi && chatApi.assistantName ? chatApi.assistantName : "助手"
    }

    function userName() {
        return "\u6211"
    }

    function formatDateCn(dateStr) {
        const p = (dateStr || "").split("-")
        if (p.length !== 3)
            return dateStr
        return parseInt(p[0], 10) + "年" + parseInt(p[1], 10) + "月" + parseInt(p[2], 10) + "日"
    }

    function formatTs(ts) {
        if (!ts || ts.length < 19)
            return ""
        return formatDateCn(ts.substring(0, 10)) + "  " + ts.substring(11, 19)
    }

    function scrollToBottom() {
        Qt.callLater(function() {
            if (messagesArea.count > 0)
                messagesArea.positionViewAtEnd()
        })
    }

    function daysInMonth(year, month) {
        return new Date(year, month, 0).getDate()
    }

    function buildYearOptions() {
        const today = new Date()
        const years = []
        for (let year = 1990; year <= today.getFullYear(); year++)
            years.push(year)
        return years
    }

    function buildMonthOptions() {
        const months = []
        for (let i = 1; i <= 12; i++)
            months.push(i)
        return months
    }

    function buildDayOptions(year, month) {
        const out = []
        const total = daysInMonth(year, month)
        for (let i = 1; i <= total; i++)
            out.push(i)
        return out
    }

    function syncPickerFromDate(dateStr) {
        syncingPicker = true
        const useDate = dateStr && dateStr.length > 0 ? dateStr : todayDateStr()
        const p = useDate.split("-")
        const currentYear = new Date().getFullYear()
        pickerYear = Math.max(1990, Math.min(currentYear, parseInt(p[0], 10)))
        pickerMonth = parseInt(p[1], 10)
        pickerDay = parseInt(p[2], 10)
        yearOptions = buildYearOptions()
        monthOptions = buildMonthOptions()
        dayOptions = buildDayOptions(pickerYear, pickerMonth)
        if (pickerDay > dayOptions.length)
            pickerDay = dayOptions.length
        syncingPicker = false
    }

    function refreshDayOptions() {
        dayOptions = buildDayOptions(pickerYear, pickerMonth)
        if (pickerDay > dayOptions.length)
            pickerDay = dayOptions.length
    }

    function applyPickedDate() {
        selectedDate = pickerYear + "-" + pad2(pickerMonth) + "-" + pad2(pickerDay)
        if (chatApi)
            chatApi.loadMessages(selectedDate)
    }

    function openDatePicker() {
        syncPickerFromDate(selectedDate || todayDateStr())
        dateDialog.open()
    }

    function refreshPendingState() {
        if (!scheduleApi || !scheduleApi.pendingAction) {
            hasPendingAction = false
            pendingConfirmText = ""
            return
        }
        const pending = scheduleApi.pendingAction || {}
        const ops = pending.ops || []
        hasPendingAction = Array.isArray(ops) && ops.length > 0
        pendingConfirmText = hasPendingAction ? (pending.confirm_text || "有待确认操作。") : ""
    }

    function sendCurrentMessage() {
        if (!chatApi)
            return
        const t = messageInput.text.trim()
        if (t.length === 0)
            return
        const nowMs = Date.now()
        if (t === lastSentText && (nowMs - lastSentAtMs) < 1200)
            return
        lastSentText = t
        lastSentAtMs = nowMs
        chatApi.sendMessage(t, selectedDate)
        messageInput.clear()
    }

    onClosing: function(close) {
        close.accepted = false
        visible = false
    }

    Component.onCompleted: {
        selectedDate = todayDateStr()
        syncPickerFromDate(selectedDate)
        if (chatApi) {
            selectedDate = chatApi.forceTodayDate()
            chatApi.loadMessages(selectedDate)
        }
        refreshPendingState()
        scrollToBottom()
    }

    onVisibleChanged: {
        if (visible)
            refreshPendingState()
    }

    Connections {
        target: chatApi

        function onMessagesChanged(date) {
            if (date === selectedDate)
                scrollToBottom()
        }

        function onDateAutoSwitched(today) {
            selectedDate = today
            syncPickerFromDate(today)
            if (chatApi)
                chatApi.loadMessages(selectedDate)
        }

        function onToastRequested(text) {
            toastText.text = text
            toast.visible = true
            toastTimer.restart()
        }

        function onNamesChanged() {
            title = assistantName() + " | 聊天"
        }
    }

    Connections {
        target: scheduleApi

        function onPendingChanged() {
            refreshPendingState()
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
                text: "聊天"
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
                    color: minArea.containsMouse ? "#FFC642" : "#FFBD2E"

                    Rectangle {
                        anchors.centerIn: parent
                        visible: minArea.containsMouse
                        width: 7
                        height: 1.6
                        radius: 1
                        color: "#7D5600"
                    }

                    MouseArea {
                        id: minArea
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
            id: header
            x: 0
            y: 44
            width: parent.width
            height: 76
            color: "transparent"

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 1
                color: Qt.rgba(0, 0, 0, 0.06)
            }

            Column {
                anchors.left: parent.left
                anchors.leftMargin: 20
                anchors.right: headerControls.left
                anchors.rightMargin: 18
                anchors.verticalCenter: parent.verticalCenter
                spacing: 4

                Text {
                    text: "与" + assistantName() + "的对话"
                    font.pixelSize: 16
                    font.weight: Font.DemiBold
                    color: "#111827"
                }

                Text {
                    text: "日程和待办改动请直接回复“确定”或“取消”"
                    font.pixelSize: 12
                    color: "#6B7280"
                }
            }

            Row {
                id: headerControls
                anchors.right: parent.right
                anchors.rightMargin: 20
                anchors.verticalCenter: parent.verticalCenter
                spacing: 12

                Rectangle {
                    width: dateChipContent.implicitWidth + 20
                    height: 24
                    radius: 12
                    color: Qt.rgba(1, 1, 1, 0.60)
                    border.width: 1
                    border.color: Qt.rgba(0, 0, 0, 0.06)

                    Row {
                        id: dateChipContent
                        anchors.centerIn: parent
                        spacing: 8

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: formatDateCn(selectedDate || todayDateStr())
                            font.pixelSize: 11
                            color: "#111827"
                        }

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: "\u25BE"
                            font.pixelSize: 8
                            color: "#6B7280"
                        }
                    }

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: openDatePicker()
                    }
                }

                Row {
                    spacing: 8

                    Rectangle {
                        width: 62
                        height: 24
                        radius: 12
                        color: chatApi && chatApi.kimiConnected ? Qt.rgba(0.039, 0.518, 1.0, 0.1) : Qt.rgba(0, 0, 0, 0.05)

                        Row {
                            anchors.centerIn: parent
                            spacing: 4

                            Rectangle {
                                width: 6
                                height: 6
                                radius: 3
                                color: chatApi && chatApi.kimiConnected ? "#0A84FF" : "#A0A0A0"
                            }

                            Text {
                                text: "Kimi"
                                font.pixelSize: 11
                                color: chatApi && chatApi.kimiConnected ? "#0A84FF" : "#888888"
                            }
                        }
                    }

                    Rectangle {
                        width: 62
                        height: 24
                        radius: 12
                        color: chatApi && chatApi.feishuConnected ? Qt.rgba(0.204, 0.780, 0.349, 0.1) : Qt.rgba(0, 0, 0, 0.05)

                        Row {
                            anchors.centerIn: parent
                            spacing: 4

                            Rectangle {
                                width: 6
                                height: 6
                                radius: 3
                                color: chatApi && chatApi.feishuConnected ? "#34C759" : "#A0A0A0"
                            }

                            Text {
                                text: "飞书"
                                font.pixelSize: 11
                                color: chatApi && chatApi.feishuConnected ? "#34C759" : "#888888"
                            }
                        }
                    }
                }
            }
        }

        Item {
            id: chatContainer
            x: 0
            y: 120
            width: parent.width
            height: parent.height - 120

            Rectangle {
                id: pendingBanner
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.leftMargin: 20
                anchors.rightMargin: 20
                height: visible ? pendingLabel.implicitHeight + 24 : 0
                radius: 14
                color: Qt.rgba(0.039, 0.518, 1.0, 0.08)
                border.width: 1
                border.color: Qt.rgba(0.039, 0.518, 1.0, 0.18)
                visible: hasPendingAction

                Text {
                    id: pendingLabel
                    anchors.fill: parent
                    anchors.margins: 12
                    text: {
                        if (!hasPendingAction)
                            return ""
                        return pendingConfirmText + "\n请在输入框回复“确定”执行，或回复“取消”放弃。"
                    }
                    wrapMode: Text.Wrap
                    font.pixelSize: 12
                    lineHeight: 1.4
                    color: "#0A4F9F"
                }
            }

            ListView {
                id: messagesArea
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: pendingBanner.bottom
                anchors.bottom: inputArea.top
                anchors.topMargin: pendingBanner.visible ? 12 : 0
                clip: true
                spacing: 16
                model: chatApi ? chatApi.messages : []
                boundsBehavior: Flickable.StopAtBounds
                leftMargin: 20
                rightMargin: 20
                topMargin: 16
                bottomMargin: 16

                delegate: Item {
                    id: messageDelegate
                    width: messagesArea.width - 40
                    height: messageColumn.implicitHeight
                    property bool isUser: (modelData.role || "") === "user"

                    Column {
                        id: messageColumn
                        width: parent.width
                        spacing: 4

                        Row {
                            width: parent.width
                            layoutDirection: messageDelegate.isUser ? Qt.RightToLeft : Qt.LeftToRight
                            spacing: 6

                            Text {
                                text: messageDelegate.isUser ? "\u6211" : assistantName()
                                font.pixelSize: 12
                                color: "#6B7280"
                            }

                            Text {
                                text: formatTs(modelData.ts || "")
                                font.pixelSize: 12
                                color: "#6B7280"
                            }
                        }

                        Row {
                            width: parent.width
                            layoutDirection: messageDelegate.isUser ? Qt.RightToLeft : Qt.LeftToRight

                            Rectangle {
                                width: Math.min(parent.width * 0.78, bubbleText.implicitWidth + 32)
                                height: bubbleText.implicitHeight + 24
                                radius: 16
                                color: messageDelegate.isUser ? "#0A84FF" : Qt.rgba(1, 1, 1, 0.86)
                                border.width: messageDelegate.isUser ? 0 : 1
                                border.color: Qt.rgba(0, 0, 0, 0.06)

                                Text {
                                    id: bubbleText
                                    anchors.fill: parent
                                    anchors.margins: 12
                                    text: modelData.text || ""
                                    wrapMode: Text.Wrap
                                    verticalAlignment: Text.AlignVCenter
                                    font.pixelSize: 14
                                    lineHeight: 1.5
                                    color: messageDelegate.isUser ? "white" : "#111827"
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    anchors.centerIn: parent
                    width: 220
                    height: 90
                    radius: 12
                    color: "transparent"
                    visible: !chatApi || (chatApi.messages || []).length === 0

                    Column {
                        anchors.centerIn: parent
                        spacing: 10

                        Text {
                            text: "暂无聊天记录"
                            font.pixelSize: 14
                            color: "#6B7280"
                            horizontalAlignment: Text.AlignHCenter
                        }

                        Text {
                            text: "输入消息开始对话"
                            font.pixelSize: 12
                            color: "#A0A0A0"
                            horizontalAlignment: Text.AlignHCenter
                        }
                    }
                }
            }

            Rectangle {
                id: inputArea
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 86
                color: "transparent"

                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    height: 1
                    color: Qt.rgba(0, 0, 0, 0.06)
                }

                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.leftMargin: 20
                    anchors.rightMargin: 20
                    anchors.top: parent.top
                    anchors.topMargin: 12
                    height: 56
                    radius: 10
                    color: Qt.rgba(1, 1, 1, 0.6)
                    border.width: 1
                    border.color: Qt.rgba(0, 0, 0, 0.06)

                    TextArea {
                        id: messageInput
                        anchors.left: parent.left
                        anchors.right: sendBtn.left
                        anchors.leftMargin: 16
                        anchors.rightMargin: 8
                        anchors.top: parent.top
                        anchors.bottom: parent.bottom
                        anchors.topMargin: 8
                        anchors.bottomMargin: 8
                        placeholderText: "输入消息...（Enter 发送）"
                        wrapMode: TextArea.Wrap
                        selectByMouse: true
                        font.pixelSize: 14
                        color: "#111827"
                        topPadding: 2
                        bottomPadding: 2
                        leftPadding: 0
                        rightPadding: 0
                        background: null

                        Keys.onPressed: function(event) {
                            if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && !(event.modifiers & Qt.ShiftModifier)) {
                                event.accepted = true
                                sendCurrentMessage()
                            }
                        }
                    }

                    Rectangle {
                        id: sendBtn
                        anchors.right: parent.right
                        anchors.rightMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        width: 36
                        height: 36
                        radius: 8
                        color: messageInput.text.trim().length > 0 ? "#0A84FF" : Qt.rgba(0.039, 0.518, 1.0, 0.4)

                        Text {
                            anchors.centerIn: parent
                            text: "➜"
                            font.pixelSize: 14
                            color: "white"
                        }

                        MouseArea {
                            anchors.fill: parent
                            enabled: messageInput.text.trim().length > 0
                            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: sendCurrentMessage()
                        }
                    }
                }
            }
        }
    }

    Dialog {
        id: dateDialog
        modal: true
        x: (win.width - width) / 2
        y: (win.height - height) / 2
        width: 360
        height: 200
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        standardButtons: Dialog.NoButton

        background: Rectangle {
            radius: 16
            color: Qt.rgba(1, 1, 1, 0.94)
            border.width: 1
            border.color: Qt.rgba(0, 0, 0, 0.08)
        }

        Column {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 16

            Text {
                text: "选择聊天记录日期"
                font.pixelSize: 16
                font.weight: Font.DemiBold
                color: "#111827"
            }

            Row {
                spacing: 10

                ComboBox {
                    id: yearBox
                    width: 110
                    height: 36
                    model: yearOptions
                    currentIndex: Math.max(0, yearOptions.indexOf(pickerYear))
                    onActivated: {
                        pickerYear = parseInt(currentText, 10)
                        refreshDayOptions()
                    }
                }

                ComboBox {
                    id: monthBox
                    width: 84
                    height: 36
                    model: monthOptions
                    currentIndex: Math.max(0, monthOptions.indexOf(pickerMonth))
                    onActivated: {
                        pickerMonth = parseInt(currentText, 10)
                        refreshDayOptions()
                    }
                }

                ComboBox {
                    id: dayBox
                    width: 84
                    height: 36
                    model: dayOptions
                    currentIndex: Math.max(0, dayOptions.indexOf(pickerDay))
                    onActivated: pickerDay = parseInt(currentText, 10)
                }
            }

            Row {
                spacing: 12
                anchors.right: parent.right

                Button {
                    text: "取消"
                    onClicked: dateDialog.close()
                }

                Button {
                    text: "确认"
                    onClicked: {
                        pickerYear = parseInt(yearBox.currentText, 10)
                        pickerMonth = parseInt(monthBox.currentText, 10)
                        pickerDay = parseInt(dayBox.currentText, 10)
                        applyPickedDate()
                        dateDialog.close()
                    }
                }
            }
        }
    }

    Rectangle {
        id: toast
        visible: false
        opacity: visible ? 1 : 0
        radius: 16
        color: Qt.rgba(0, 0, 0, 0.8)
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
            color: "white"
            font.pixelSize: 12
            text: ""
        }
    }

    Timer {
        id: toastTimer
        interval: 2000
        repeat: false
        onTriggered: toast.visible = false
    }
}
