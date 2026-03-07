import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15

Window {
    id: win
    width: 680
    height: 480
    visible: true
    color: "transparent"
    title: "日程规划"
    flags: Qt.FramelessWindowHint | Qt.Window

    property string selectedDate: ""
    property string currentMonth: ""
    property var jumpYearOptions: []
    property var jumpMonthOptions: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    property int jumpYear: 0
    property int jumpMonth: 0

    function pad2(v) { return (v < 10 ? "0" : "") + v }
    function todayDateStr() {
        const d = new Date()
        return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate())
    }
    function monthOf(dateStr) { return (dateStr || "").substring(0, 7) }
    function buildJumpYearOptions() {
        const base = new Date().getFullYear()
        const out = []
        for (let y = base - 4; y <= base + 4; y++)
            out.push(y)
        return out
    }
    function syncMonthJump() {
        const parts = (currentMonth || monthOf(todayDateStr())).split("-")
        jumpYearOptions = buildJumpYearOptions()
        jumpYear = parseInt(parts[0], 10)
        jumpMonth = parseInt(parts[1], 10)
        if (jumpYearOptions.indexOf(jumpYear) < 0) {
            jumpYearOptions.push(jumpYear)
            jumpYearOptions.sort(function(a, b) { return a - b })
        }
    }
    function openMonthJump() {
        syncMonthJump()
        monthJumpDialog.open()
    }
    function formatTimeLabel(timeText) {
        const t = timeText || "待定"
        if (t === "待定")
            return t
        const p = t.split(":")
        if (p.length !== 2)
            return t
        return parseInt(p[0], 10) + ":" + p[1]
    }
    function formatChannel(channel) {
        return channel === "feishu" ? "飞书端" : "桌面端"
    }
    function openTodoEditor(item) {
        if (!item)
            return
        addDialog.mode = "todo_edit"
        addDialog.editId = item.id || ""
        addDialog.editDone = !!item.done
        addDialog.editDate = selectedDate
        addInput.text = item.text || ""
        addDialog.open()
    }
    function openEventEditor(item) {
        if (!item)
            return
        addDialog.mode = "event_edit"
        addDialog.editId = item.id || ""
        addDialog.editDone = false
        addDialog.editDate = selectedDate
        addInput.text = (item.time && item.time !== "待定" ? item.time + " " : "") + (item.title || "")
        addDialog.open()
    }
    function shiftMonth(delta) {
        let p = (currentMonth || monthOf(todayDateStr())).split("-")
        let y = parseInt(p[0], 10)
        let m = parseInt(p[1], 10) + delta
        while (m <= 0) { y -= 1; m += 12 }
        while (m > 12) { y += 1; m -= 12 }
        currentMonth = y + "-" + pad2(m)
        selectedDate = currentMonth + "-01"
        scheduleService.loadMonth(currentMonth, selectedDate)
    }

    onClosing: function(close) {
        close.accepted = false
        visible = false
    }

    Component.onCompleted: {
        selectedDate = todayDateStr()
        currentMonth = monthOf(selectedDate)
        scheduleService.loadMonth(currentMonth, selectedDate)
        scheduleService.ensureDailyMonthAchievements((typeof chatService !== "undefined" && chatService) ? chatService.kimiConnected : false)
        syncMonthJump()
    }

    Connections {
        target: scheduleService

        function onMonthDataChanged(month) {
            currentMonth = month
            selectedDate = (scheduleService.monthData || {}).selected_date || selectedDate
        }

        function onPendingChanged() {
            const p = scheduleService.pendingAction || {}
            const ops = p.ops || []
            if (ops.length > 0) {
                pendingText.text = p.confirm_text || "确认执行待办操作？"
                pendingDialog.open()
            } else {
                pendingDialog.close()
            }
        }

        function onToastRequested(text) {
            toastText.text = text
            toast.visible = true
            toastTimer.restart()
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
            width: parent.width
            height: 38
            color: "transparent"

            MouseArea {
                anchors.fill: parent
                onPressed: win.startSystemMove()
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
                    color: minMouse.containsMouse ? "#FFC642" : "#FFBD2E"

                    Rectangle {
                        anchors.centerIn: parent
                        visible: minMouse.containsMouse
                        width: 7
                        height: 1.6
                        radius: 1
                        color: "#7D5600"
                    }

                    MouseArea {
                        id: minMouse
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
                    color: closeMouse.containsMouse ? "#FF6B63" : "#FF5F56"

                    Item {
                        anchors.centerIn: parent
                        visible: closeMouse.containsMouse
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
                        id: closeMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: win.visible = false
                    }
                }
            }
        }

        RowLayout {
            x: 20
            y: 38
            width: parent.width - 40
            height: parent.height - 58
            spacing: 16

            ColumnLayout {
                Layout.preferredWidth: 1
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 12

                Column {
                    spacing: 4

                    Row {
                        spacing: 8

                        Text {
                            text: "日程规划"
                            font.pixelSize: 15
                            font.weight: Font.DemiBold
                            color: "#1D1D1F"
                        }

                        Text {
                            text: "⌯"
                            font.pixelSize: 14
                            color: Qt.rgba(0, 0, 0, 0.45)

                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: openMonthJump()
                            }
                        }
                    }

                    Text {
                        text: (scheduleService.monthData || {}).display_date || ""
                        font.pixelSize: 28
                        font.weight: Font.Bold
                        color: "#1D1D1F"
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 220
                    radius: 14
                    color: Qt.rgba(1, 1, 1, 0.85)

                    Column {
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 10

                        Row {
                            width: parent.width

                            Text {
                                text: (scheduleService.monthData || {}).month_label || ""
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                                color: "#1D1D1F"
                            }

                            Item { width: 1; height: 1; anchors.horizontalCenterOffset: 0 }
                            Item { width: Math.max(0, parent.width - 110); height: 1 }

                            Row {
                                spacing: 4

                                Button {
                                    width: 20
                                    height: 20
                                    text: "◀"
                                    onClicked: shiftMonth(-1)
                                }

                                Button {
                                    width: 20
                                    height: 20
                                    text: "▶"
                                    onClicked: shiftMonth(1)
                                }
                            }
                        }

                        Grid {
                            id: calendarGrid
                            width: parent.width
                            columns: 7
                            rowSpacing: 2
                            columnSpacing: 2

                            Repeater {
                                model: ["日", "一", "二", "三", "四", "五", "六"]
                                delegate: Text {
                                    width: (calendarGrid.width - 12) / 7
                                    text: modelData
                                    font.pixelSize: 9
                                    color: "#86868B"
                                    horizontalAlignment: Text.AlignHCenter
                                }
                            }

                            Repeater {
                                model: (scheduleService.monthData || {}).calendar_cells || []
                                delegate: Rectangle {
                                    width: (calendarGrid.width - 12) / 7
                                    height: width
                                    radius: 6
                                    color: modelData.selected ? "#0A84FF" : "transparent"

                                    Text {
                                        anchors.centerIn: parent
                                        text: modelData.day
                                        font.pixelSize: 11
                                        font.weight: modelData.today ? Font.DemiBold : Font.Normal
                                        color: modelData.selected ? "white" : (modelData.in_month ? "#1D1D1F" : "#C7C7CC")
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: {
                                            selectedDate = modelData.date
                                            currentMonth = monthOf(selectedDate)
                                            scheduleService.loadMonth(currentMonth, selectedDate)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 122
                    radius: 14
                    color: Qt.rgba(1, 1, 1, 0.85)

                    Column {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 8

                        Text {
                            text: "STATS | 本月计划统计"
                            font.pixelSize: 11
                            font.weight: Font.DemiBold
                            color: "#86868B"
                        }

                        Row {
                            spacing: 8
                            Rectangle { width: 8; height: 8; radius: 4; color: "#34C759" }
                            Text { text: "已完成"; width: 92; font.pixelSize: 11; color: "#3A3A3C" }
                            Text { text: String(((scheduleService.monthData || {}).stats || {}).done || 0); width: 30; horizontalAlignment: Text.AlignRight; font.pixelSize: 11; font.weight: Font.DemiBold; color: "#1D1D1F" }
                            Text { text: String(((scheduleService.monthData || {}).stats || {}).done_pct || 0) + "%"; width: 40; horizontalAlignment: Text.AlignRight; font.pixelSize: 11; color: "#86868B" }
                        }

                        Row {
                            spacing: 8
                            Rectangle { width: 8; height: 8; radius: 4; color: "#FF453A" }
                            Text { text: "未完成"; width: 92; font.pixelSize: 11; color: "#3A3A3C" }
                            Text { text: String(((scheduleService.monthData || {}).stats || {}).pending || 0); width: 30; horizontalAlignment: Text.AlignRight; font.pixelSize: 11; font.weight: Font.DemiBold; color: "#1D1D1F" }
                            Text { text: String(((scheduleService.monthData || {}).stats || {}).pending_pct || 0) + "%"; width: 40; horizontalAlignment: Text.AlignRight; font.pixelSize: 11; color: "#86868B" }
                        }

                        Row {
                            spacing: 8
                            Rectangle { width: 8; height: 8; radius: 4; color: "#8E8E93" }
                            Text { text: "总计划"; width: 92; font.pixelSize: 11; color: "#3A3A3C" }
                            Text { text: String(((scheduleService.monthData || {}).stats || {}).total || 0); width: 30; horizontalAlignment: Text.AlignRight; font.pixelSize: 11; font.weight: Font.DemiBold; color: "#1D1D1F" }
                            Text { text: "100%"; width: 40; horizontalAlignment: Text.AlignRight; font.pixelSize: 11; color: "#86868B" }
                        }
                    }
                }
            }

            ColumnLayout {
                Layout.preferredWidth: 1
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 12

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 220
                    radius: 14
                    color: Qt.rgba(1, 1, 1, 0.85)

                    Column {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 8

                        Row {
                            width: parent.width

                            Text {
                                text: "TO DO | 本月待办"
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                                color: "#86868B"
                            }

                            Item { width: Math.max(0, parent.width - 110); height: 1 }

                            Rectangle {
                                width: 18
                                height: 18
                                radius: 5
                                color: Qt.rgba(0.039, 0.518, 1.0, 0.1)

                                Text {
                                    anchors.centerIn: parent
                                    text: "+"
                                    font.pixelSize: 14
                                    color: "#0A84FF"
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: {
                                        addDialog.mode = "todo"
                                        addDialog.editId = ""
                                        addDialog.editDone = false
                                        addDialog.editDate = selectedDate
                                        addDialog.open()
                                    }
                                }
                            }
                        }

                        ListView {
                            width: parent.width
                            height: parent.height - 34
                            clip: true
                            spacing: 6
                            model: (scheduleService.monthData || {}).todos || []

                            delegate: Row {
                                width: parent.width
                                height: 28
                                spacing: 8

                                Rectangle {
                                    width: 14
                                    height: 14
                                    radius: 4
                                    border.width: 2
                                    border.color: modelData.done ? "#34C759" : "#C7C7CC"
                                    color: modelData.done ? "#34C759" : "transparent"
                                    anchors.verticalCenter: parent.verticalCenter

                                    Text {
                                        anchors.centerIn: parent
                                        text: modelData.done ? "✓" : ""
                                        font.pixelSize: 9
                                        color: "white"
                                    }

                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: scheduleService.requestToggleTodo(modelData.id)
                                    }
                                }

                                Text {
                                    text: modelData.num
                                    width: 16
                                    font.pixelSize: 10
                                    color: "#86868B"
                                    anchors.verticalCenter: parent.verticalCenter
                                }

                                Text {
                                    text: modelData.text
                                    width: parent.width - 64
                                    font.pixelSize: 11
                                    color: modelData.done ? "#C7C7CC" : "#1D1D1F"
                                    font.strikeout: modelData.done
                                    elide: Text.ElideRight
                                    anchors.verticalCenter: parent.verticalCenter

                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: openTodoEditor(modelData)
                                    }
                                }

                                Text {
                                    text: "×"
                                    font.pixelSize: 12
                                    color: "#C7C7CC"
                                    anchors.verticalCenter: parent.verticalCenter

                                    MouseArea {
                                        anchors.fill: parent
                                        onClicked: scheduleService.requestDeleteTodo(modelData.id)
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 194
                    radius: 14
                    color: Qt.rgba(1, 1, 1, 0.85)

                    Column {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 8

                        Text {
                            text: "NOTES | 本月成果"
                            font.pixelSize: 11
                            font.weight: Font.DemiBold
                            color: "#86868B"
                        }

                        ListView {
                            width: parent.width
                            height: parent.height - 30
                            clip: true
                            spacing: 6
                            model: (scheduleService.monthData || {}).notes || []

                            delegate: Rectangle {
                                width: parent.width
                                height: Math.max(28, noteText.implicitHeight + 12)
                                radius: 8
                                color: Qt.rgba(0.204, 0.780, 0.349, 0.08)

                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.top: parent.top
                                    anchors.bottom: parent.bottom
                                    width: 3
                                    radius: 2
                                    color: "#34C759"
                                }

                                Text {
                                    id: noteText
                                    anchors.fill: parent
                                    anchors.margins: 8
                                    anchors.leftMargin: 12
                                    text: modelData.text || ""
                                    wrapMode: Text.Wrap
                                    font.pixelSize: 11
                                    color: "#3A3A3C"
                                }
                            }
                        }
                    }
                }
            }

            ColumnLayout {
                Layout.preferredWidth: 1
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 12

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 174
                    radius: 14
                    color: Qt.rgba(1, 1, 1, 0.85)

                    Column {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 8

                        Row {
                            width: parent.width

                            Text {
                                text: "SCHEDULE | 今日规划"
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                                color: "#86868B"
                            }

                            Item { width: Math.max(0, parent.width - 134); height: 1 }

                            Rectangle {
                                width: 18
                                height: 18
                                radius: 5
                                color: Qt.rgba(0.039, 0.518, 1.0, 0.1)

                                Text {
                                    anchors.centerIn: parent
                                    text: "+"
                                    font.pixelSize: 14
                                    color: "#0A84FF"
                                }

                                MouseArea {
                                    anchors.fill: parent
                                    onClicked: {
                                        addDialog.mode = "event"
                                        addDialog.editId = ""
                                        addDialog.editDone = false
                                        addDialog.editDate = selectedDate
                                        addDialog.open()
                                    }
                                }
                            }
                        }

                        ListView {
                            width: parent.width
                            height: parent.height - 34
                            clip: true
                            spacing: 8
                            model: (scheduleService.monthData || {}).events || []

                            delegate: Rectangle {
                                width: ListView.view ? ListView.view.width : 0
                                height: Math.max(46, eventTitle.paintedHeight + 16)
                                radius: 10
                                color: Qt.rgba(0.039, 0.518, 1.0, 0.06)

                                Row {
                                    anchors.fill: parent
                                    anchors.leftMargin: 10
                                    anchors.rightMargin: 8
                                    spacing: 8

                                    Text {
                                        text: formatTimeLabel(modelData.time || "待定")
                                        width: 44
                                        font.pixelSize: 12
                                        font.weight: Font.DemiBold
                                        color: "#0A84FF"
                                        anchors.verticalCenter: parent.verticalCenter
                                    }

                                    Text {
                                        id: eventTitle
                                        text: modelData.title || ""
                                        width: parent.width - 92
                                        font.pixelSize: 11
                                        color: "#1D1D1F"
                                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                        maximumLineCount: 2
                                        elide: Text.ElideRight
                                        anchors.verticalCenter: parent.verticalCenter
                                        ToolTip.visible: eventTitleHover.containsMouse && text.length > 0
                                        ToolTip.delay: 350
                                        ToolTip.text: text

                                        MouseArea {
                                            id: eventTitleHover
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: openEventEditor(modelData)
                                        }
                                    }

                                    Text {
                                        text: "🔔"
                                        font.pixelSize: 14
                                        color: "#FF9500"
                                        anchors.verticalCenter: parent.verticalCenter
                                    }

                                    Text {
                                        text: "×"
                                        font.pixelSize: 12
                                        color: "#C7C7CC"
                                        anchors.verticalCenter: parent.verticalCenter

                                        MouseArea {
                                            anchors.fill: parent
                                            onClicked: scheduleService.requestDeleteEvent(modelData.id)
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 234
                    radius: 14
                    color: Qt.rgba(1, 1, 1, 0.85)

                    Column {
                        anchors.fill: parent
                        anchors.margins: 14
                        spacing: 8

                        Text {
                            text: "HISTORY | 历史变化"
                            font.pixelSize: 11
                            font.weight: Font.DemiBold
                            color: "#86868B"
                        }

                        ListView {
                            width: parent.width
                            height: parent.height - 30
                            clip: true
                            spacing: 8
                            model: (scheduleService.monthData || {}).history || []

                            delegate: Rectangle {
                                width: ListView.view ? ListView.view.width : 0
                                height: Math.max(52, historyContent.implicitHeight + 16)
                                radius: 8
                                color: Qt.rgba(0, 0, 0, 0.03)

                                Column {
                                    id: historyContent
                                    anchors.fill: parent
                                    anchors.margins: 8
                                    spacing: 2

                                    Row {
                                        width: parent.width
                                        spacing: 6

                                        Text {
                                            text: modelData.time_text || ""
                                            font.pixelSize: 9
                                            color: "#C7C7CC"
                                        }

                                        Text {
                                            text: formatChannel(modelData.channel || "")
                                            font.pixelSize: 9
                                            color: "#C7C7CC"
                                        }
                                    }

                                    Text {
                                        id: historyText
                                        width: parent.width
                                        text: modelData.summary || ""
                                        wrapMode: Text.WrapAtWordBoundaryOrAnywhere
                                        font.pixelSize: 10
                                        color: "#8E8E93"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Dialog {
        id: addDialog
        property string mode: "todo"
        property string editId: ""
        property bool editDone: false
        property string editDate: ""
        onOpened: {
            if (mode === "todo" || mode === "event")
                addInput.text = ""
        }
        modal: true
        width: 280
        height: 170
        x: (win.width - width) / 2
        y: (win.height - height) / 2
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        standardButtons: Dialog.NoButton

        background: Rectangle {
            radius: 14
            color: Qt.rgba(1, 1, 1, 0.95)
        }

        Column {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 12

            Text {
                text: {
                    if (addDialog.mode === "todo")
                        return "添加待办事项"
                    if (addDialog.mode === "todo_edit")
                        return "编辑待办事项"
                    if (addDialog.mode === "event")
                        return "添加日程"
                    return "编辑日程"
                }
                font.pixelSize: 14
                font.weight: Font.DemiBold
                color: "#1D1D1F"
            }

            TextField {
                id: addInput
                width: parent.width
                placeholderText: (addDialog.mode === "todo" || addDialog.mode === "todo_edit") ? "输入待办内容..." : "输入“时间 事件”..."
            }

            Row {
                anchors.right: parent.right
                spacing: 8

                Button {
                    text: "取消"
                    onClicked: addDialog.close()
                }

                Button {
                    text: "确认"
                    onClicked: {
                        const raw = addInput.text.trim()
                        if (raw.length === 0)
                            return
                        if (addDialog.mode === "todo") {
                            scheduleService.requestAddTodo(raw)
                        } else if (addDialog.mode === "todo_edit") {
                            scheduleService.requestUpdateTodo(addDialog.editId, raw, addDialog.editDone)
                        } else {
                            let time = "待定"
                            let title = raw
                            const m = raw.match(/^(\d{1,2}:\d{2})\s+(.+)$/)
                            if (m) {
                                time = m[1]
                                title = m[2]
                            }
                            const payload = {
                                date: addDialog.editDate || selectedDate,
                                time: time,
                                title: title,
                                duration: "01:00",
                                tags: [],
                                location: "",
                                remind_before_min: 0
                            }
                            if (addDialog.mode === "event") {
                                scheduleService.requestAddEvent(payload)
                            } else {
                                scheduleService.requestUpdateEvent(addDialog.editId, payload)
                            }
                        }
                        addDialog.close()
                    }
                }
            }
        }
    }

    Dialog {
        id: monthJumpDialog
        modal: true
        width: 260
        height: 158
        x: (win.width - width) / 2
        y: (win.height - height) / 2
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        standardButtons: Dialog.NoButton

        background: Rectangle {
            radius: 14
            color: Qt.rgba(1, 1, 1, 0.95)
        }

        Column {
            anchors.fill: parent
            anchors.margins: 18
            spacing: 14

            Text {
                text: "跳转月份"
                font.pixelSize: 14
                font.weight: Font.DemiBold
                color: "#1D1D1F"
            }

            Row {
                spacing: 10

                ComboBox {
                    id: jumpYearBox
                    width: 100
                    model: jumpYearOptions
                    currentIndex: Math.max(0, jumpYearOptions.indexOf(jumpYear))
                }

                ComboBox {
                    id: jumpMonthBox
                    width: 84
                    model: jumpMonthOptions
                    currentIndex: Math.max(0, jumpMonthOptions.indexOf(jumpMonth))
                }
            }

            Row {
                anchors.right: parent.right
                spacing: 8

                Button {
                    text: "取消"
                    onClicked: monthJumpDialog.close()
                }

                Button {
                    text: "确认"
                    onClicked: {
                        jumpYear = parseInt(jumpYearBox.currentText, 10)
                        jumpMonth = parseInt(jumpMonthBox.currentText, 10)
                        currentMonth = jumpYear + "-" + pad2(jumpMonth)
                        selectedDate = currentMonth + "-01"
                        scheduleService.loadMonth(currentMonth, selectedDate)
                        monthJumpDialog.close()
                    }
                }
            }
        }
    }

    Dialog {
        id: pendingDialog
        modal: true
        width: 320
        height: 170
        x: (win.width - width) / 2
        y: (win.height - height) / 2
        closePolicy: Popup.NoAutoClose
        standardButtons: Dialog.NoButton

        background: Rectangle {
            radius: 14
            color: Qt.rgba(1, 1, 1, 0.95)
        }

        Column {
            anchors.fill: parent
            anchors.margins: 20
            spacing: 12

            Text {
                text: "确认操作"
                font.pixelSize: 14
                font.weight: Font.DemiBold
                color: "#1D1D1F"
            }

            Text {
                id: pendingText
                width: parent.width
                wrapMode: Text.Wrap
                font.pixelSize: 12
                color: "#3A3A3C"
            }

            Row {
                anchors.right: parent.right
                spacing: 8

                Button {
                    text: "取消"
                    onClicked: scheduleService.cancelPending()
                }

                Button {
                    text: "确认"
                    onClicked: scheduleService.confirmPending()
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
        y: 10
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
        }
    }

    Timer {
        id: toastTimer
        interval: 2200
        repeat: false
        onTriggered: toast.visible = false
    }
}
