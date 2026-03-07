import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Window 2.15

Window {
    id: win
    width: 680
    height: 520
    visible: true
    color: "transparent"
    title: "每周回顾"
    flags: Qt.FramelessWindowHint | Qt.Window

    readonly property var reviewApi: (typeof reviewService !== "undefined") ? reviewService : null

    property var yearOptions: []
    property var monthOptions: [
        { "label": "全部月份", "value": 0 },
        { "label": "1月", "value": 1 },
        { "label": "2月", "value": 2 },
        { "label": "3月", "value": 3 },
        { "label": "4月", "value": 4 },
        { "label": "5月", "value": 5 },
        { "label": "6月", "value": 6 },
        { "label": "7月", "value": 7 },
        { "label": "8月", "value": 8 },
        { "label": "9月", "value": 9 },
        { "label": "10月", "value": 10 },
        { "label": "11月", "value": 11 },
        { "label": "12月", "value": 12 }
    ]
    property int filterYear: new Date().getFullYear()
    property int filterMonth: 0
    property string filterStartDate: ""
    property string filterEndDate: ""
    property var filteredReports: []
    property string selectedKey: ""
    property int yearPopupX: 0
    property int yearPopupY: 0
    property int monthPopupX: 0
    property int monthPopupY: 0
    property var selectedReportData: (reviewApi && reviewApi.selectedReport) ? reviewApi.selectedReport : ({})
    property var selectedReportReport: selectedReportData.report || ({})
    property var selectedRetrospective: selectedReportReport.retrospective || ({})
    property var selectedLearningEnergy: selectedReportReport.learning_and_energy || ({})
    property var selectedNextWeekPlan: selectedReportReport.next_week_plan || ({})
    property var selectedMoodInterest: selectedReportReport.mood_and_interest || ({})

    function pad2(v) {
        return (v < 10 ? "0" : "") + v
    }

    function todayDateStr() {
        var d = new Date()
        return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate())
    }

    function mondayDateStr() {
        var d = new Date()
        var delta = d.getDay() === 0 ? -6 : 1 - d.getDay()
        d.setDate(d.getDate() + delta)
        return d.getFullYear() + "-" + pad2(d.getMonth() + 1) + "-" + pad2(d.getDate())
    }

    function isValidDateText(text) {
        return /^\d{4}-\d{2}-\d{2}$/.test((text || "").trim())
    }

    function updateYearOptions() {
        var years = {}
        years[new Date().getFullYear()] = true
        var list = (reviewApi && reviewApi.reportList) ? reviewApi.reportList : []
        for (var i = 0; i < list.length; i++) {
            var year = parseInt((list[i].period_end || "").substring(0, 4), 10)
            if (year > 0)
                years[year] = true
        }
        var values = Object.keys(years).map(function(v) { return parseInt(v, 10) })
        values.sort(function(a, b) { return b - a })
        var out = []
        for (var j = 0; j < values.length; j++)
            out.push({ "label": values[j] + "年", "value": values[j] })
        yearOptions = out
        if (yearOptions.length > 0) {
            var exists = false
            for (var k = 0; k < yearOptions.length; k++) {
                if (yearOptions[k].value === filterYear) {
                    exists = true
                    break
                }
            }
            if (!exists)
                filterYear = yearOptions[0].value
        }
    }

    function currentYearLabel() {
        for (var i = 0; i < yearOptions.length; i++) {
            if (yearOptions[i].value === filterYear)
                return yearOptions[i].label
        }
        return filterYear + "年"
    }

    function currentMonthLabel() {
        for (var i = 0; i < monthOptions.length; i++) {
            if (monthOptions[i].value === filterMonth)
                return monthOptions[i].label
        }
        return "全部月份"
    }

    function applyFilters() {
        updateYearOptions()
        var list = (reviewApi && reviewApi.reportList) ? reviewApi.reportList : []
        var out = []
        var hasRange = isValidDateText(filterStartDate) && isValidDateText(filterEndDate)
        for (var i = 0; i < list.length; i++) {
            var item = list[i]
            var itemYear = parseInt((item.period_end || "").substring(0, 4), 10)
            var itemMonth = parseInt((item.period_end || "").substring(5, 7), 10)
            if (filterYear > 0 && itemYear !== filterYear)
                continue
            if (filterMonth > 0 && itemMonth !== filterMonth)
                continue
            if (hasRange && ((item.period_start || "") > filterEndDate || (item.period_end || "") < filterStartDate))
                continue
            out.push(item)
        }
        filteredReports = out
        if (selectedKey.length > 0) {
            for (var j = 0; j < out.length; j++) {
                if ((out[j].key || "") === selectedKey)
                    return
            }
        }
        selectedKey = out.length > 0 ? (out[0].key || "") : ""
        if (selectedKey.length > 0 && reviewApi)
            reviewApi.selectReport(selectedKey)
    }

    function openYearPopup() {
        var pos = yearFilter.mapToItem(rootRect, 0, yearFilter.height + 6)
        yearPopupX = pos.x
        yearPopupY = pos.y
        yearPopup.open()
    }

    function openMonthPopup() {
        var pos = monthFilter.mapToItem(rootRect, 0, monthFilter.height + 6)
        monthPopupX = pos.x
        monthPopupY = pos.y
        monthPopup.open()
    }

    function submitDateRange(force) {
        filterStartDate = (startDateInput.text || "").trim()
        filterEndDate = (endDateInput.text || "").trim()
        applyFilters()
        if (reviewApi && isValidDateText(filterStartDate) && isValidDateText(filterEndDate))
            reviewApi.generatePeriod(filterStartDate, filterEndDate, !!force)
    }

    function sectionHeight(textItem) {
        return Math.max(44, textItem.implicitHeight + 14)
    }

    onClosing: function(close) {
        close.accepted = false
        visible = false
    }

    Component.onCompleted: {
        filterStartDate = mondayDateStr()
        filterEndDate = todayDateStr()
        updateYearOptions()
        startDateInput.text = filterStartDate
        endDateInput.text = filterEndDate
        if (reviewApi) {
            reviewApi.ensureCurrentWeekReview()
            reviewApi.reloadReports()
        }
        applyFilters()
    }

    Connections {
        target: reviewApi
        ignoreUnknownSignals: true

        function onReportListChanged() {
            applyFilters()
        }

        function onSelectedReportChanged() {
            selectedKey = (reviewApi && reviewApi.selectedReport) ? (reviewApi.selectedReport.key || "") : ""
            applyFilters()
        }

        function onToastRequested(text) {
            toastText.text = text
            toast.visible = true
            toast.opacity = 1
            toastTimer.restart()
        }
    }

    Rectangle {
        id: rootRect
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
                x: 24
                anchors.verticalCenter: parent.verticalCenter
                text: "每周回顾"
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

        Rectangle {
            id: header
            x: 0
            y: 44
            width: parent.width
            height: 64
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
                text: "历史报告"
                font.pixelSize: 18
                font.weight: Font.DemiBold
                color: "#111827"
            }

            Row {
                anchors.right: parent.right
                anchors.rightMargin: 20
                anchors.verticalCenter: parent.verticalCenter
                spacing: 12

                Rectangle {
                    id: yearFilter
                    width: 110
                    height: 36
                    radius: 10
                    color: Qt.rgba(1, 1, 1, 0.60)
                    border.width: 1
                    border.color: Qt.rgba(0, 0, 0, 0.06)

                    Text {
                        x: 12
                        anchors.verticalCenter: parent.verticalCenter
                        text: currentYearLabel()
                        font.pixelSize: 13
                        color: "#111827"
                    }

                    Text {
                        anchors.right: parent.right
                        anchors.rightMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        text: "⌄"
                        font.pixelSize: 16
                        color: "#111827"
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: openYearPopup()
                    }
                }

                Rectangle {
                    id: monthFilter
                    width: 132
                    height: 36
                    radius: 10
                    color: Qt.rgba(1, 1, 1, 0.60)
                    border.width: 1
                    border.color: Qt.rgba(0, 0, 0, 0.06)

                    Text {
                        x: 12
                        anchors.verticalCenter: parent.verticalCenter
                        text: currentMonthLabel()
                        font.pixelSize: 13
                        color: "#111827"
                    }

                    Text {
                        anchors.right: parent.right
                        anchors.rightMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        text: "⌄"
                        font.pixelSize: 16
                        color: "#111827"
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: openMonthPopup()
                    }
                }

                Row {
                    spacing: 8
                    anchors.verticalCenter: parent.verticalCenter

                    Rectangle {
                        width: 116
                        height: 36
                        radius: 10
                        color: Qt.rgba(1, 1, 1, 0.60)
                        border.width: 1
                        border.color: Qt.rgba(0, 0, 0, 0.06)

                        TextInput {
                            id: startDateInput
                            anchors.left: parent.left
                            anchors.leftMargin: 12
                            anchors.right: calendarIcon1.left
                            anchors.rightMargin: 8
                            anchors.verticalCenter: parent.verticalCenter
                            font.pixelSize: 12
                            color: "#111827"
                            selectByMouse: true
                            onEditingFinished: submitDateRange(false)
                        }

                        Item {
                            id: calendarIcon1
                            anchors.right: parent.right
                            anchors.rightMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            width: 14
                            height: 14

                            Rectangle { x: 0; y: 2; width: 14; height: 12; radius: 2; color: "transparent"; border.width: 1; border.color: "#111827" }
                            Rectangle { x: 0; y: 2; width: 14; height: 3; color: "#111827"; radius: 1 }
                            Rectangle { x: 3; y: 0; width: 2; height: 4; radius: 1; color: "#111827" }
                            Rectangle { x: 9; y: 0; width: 2; height: 4; radius: 1; color: "#111827" }
                        }
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "至"
                        font.pixelSize: 13
                        color: "#6B7280"
                    }

                    Rectangle {
                        width: 116
                        height: 36
                        radius: 10
                        color: Qt.rgba(1, 1, 1, 0.60)
                        border.width: 1
                        border.color: Qt.rgba(0, 0, 0, 0.06)

                        TextInput {
                            id: endDateInput
                            anchors.left: parent.left
                            anchors.leftMargin: 12
                            anchors.right: calendarIcon2.left
                            anchors.rightMargin: 8
                            anchors.verticalCenter: parent.verticalCenter
                            font.pixelSize: 12
                            color: "#111827"
                            selectByMouse: true
                            onEditingFinished: submitDateRange(false)
                        }

                        Item {
                            id: calendarIcon2
                            anchors.right: parent.right
                            anchors.rightMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            width: 14
                            height: 14

                            Rectangle { x: 0; y: 2; width: 14; height: 12; radius: 2; color: "transparent"; border.width: 1; border.color: "#111827" }
                            Rectangle { x: 0; y: 2; width: 14; height: 3; color: "#111827"; radius: 1 }
                            Rectangle { x: 3; y: 0; width: 2; height: 4; radius: 1; color: "#111827" }
                            Rectangle { x: 9; y: 0; width: 2; height: 4; radius: 1; color: "#111827" }
                        }
                    }
                }
            }
        }

        Rectangle {
            id: reportListPanel
            x: 20
            y: header.y + header.height + 16
            width: 220
            height: rootRect.height - y - 20
            radius: 16
            color: Qt.rgba(1, 1, 1, 0.50)
            border.width: 1
            border.color: Qt.rgba(0, 0, 0, 0.06)

            Text {
                x: 16
                y: 14
                text: "共 " + filteredReports.length + " 份报告"
                font.pixelSize: 13
                font.weight: Font.DemiBold
                color: "#111827"
            }

            Rectangle {
                x: 0
                y: 46
                width: parent.width
                height: 1
                color: Qt.rgba(0, 0, 0, 0.06)
            }

            ListView {
                id: reportListView
                x: 0
                y: 47
                width: parent.width
                height: parent.height - 47
                clip: true
                model: filteredReports

                ScrollBar.vertical: ScrollBar {
                    width: 4
                    policy: ScrollBar.AsNeeded
                    contentItem: Rectangle {
                        implicitWidth: 4
                        radius: 2
                        color: Qt.rgba(0, 0, 0, 0.10)
                    }
                    background: Item {}
                }

                delegate: Rectangle {
                    width: reportListView.width
                    height: 88
                    color: (modelData.key || "") === selectedKey ? Qt.rgba(10 / 255, 132 / 255, 255 / 255, 0.05) : "transparent"

                    Rectangle {
                        visible: (modelData.key || "") === selectedKey
                        x: 0
                        y: 0
                        width: 3
                        height: parent.height
                        color: "#0A84FF"
                    }

                    Rectangle {
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.bottom: parent.bottom
                        height: 1
                        color: Qt.rgba(0, 0, 0, 0.06)
                    }

                    Text {
                        x: 16
                        y: 14
                        width: parent.width - 32
                        elide: Text.ElideRight
                        text: modelData.title || ""
                        font.pixelSize: 13
                        font.weight: Font.Medium
                        color: "#111827"
                    }

                    Text {
                        x: 16
                        y: 38
                        text: modelData.range_text || ""
                        font.pixelSize: 11
                        color: "#6B7280"
                    }

                    Rectangle {
                        id: statusTag
                        x: 16
                        y: 56
                        width: pushedTag.implicitWidth + 12
                        height: 20
                        radius: 4
                        color: (modelData.status_label || "") === "已推送"
                               ? Qt.rgba(52 / 255, 199 / 255, 89 / 255, 0.10)
                               : Qt.rgba(10 / 255, 132 / 255, 255 / 255, 0.10)

                        Text {
                            id: pushedTag
                            anchors.centerIn: parent
                            text: modelData.status_label || "已生成"
                            font.pixelSize: 10
                            color: (modelData.status_label || "") === "已推送" ? "#34C759" : "#0A84FF"
                        }
                    }

                    Text {
                        x: statusTag.x + statusTag.width + 8
                        y: 59
                        width: parent.width - x - 16
                        elide: Text.ElideRight
                        text: modelData.status_time || ""
                        font.pixelSize: 10
                        color: "#6B7280"
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            selectedKey = modelData.key || ""
                            if (reviewApi)
                                reviewApi.selectReport(selectedKey)
                        }
                    }
                }
            }
        }

        Rectangle {
            id: detailPanel
            x: reportListPanel.x + reportListPanel.width + 16
            y: reportListPanel.y
            width: rootRect.width - x - 20
            height: reportListPanel.height
            radius: 16
            color: Qt.rgba(1, 1, 1, 0.60)
            border.width: 1
            border.color: Qt.rgba(0, 0, 0, 0.06)

            Item {
                id: detailHeader
                x: 0
                y: 0
                width: parent.width
                height: 70
            }

            Rectangle {
                x: 0
                y: detailHeader.height
                width: parent.width
                height: 1
                color: Qt.rgba(0, 0, 0, 0.06)
            }

            Text {
                anchors.left: parent.left
                anchors.leftMargin: 20
                anchors.right: detailActions.left
                anchors.rightMargin: 16
                anchors.verticalCenter: detailHeader.verticalCenter
                elide: Text.ElideRight
                text: selectedKey.length > 0 ? (selectedReportData.detail_title || "") : ""
                font.pixelSize: 15
                font.weight: Font.DemiBold
                color: "#111827"
            }

            Row {
                id: detailActions
                anchors.right: parent.right
                anchors.rightMargin: 20
                anchors.verticalCenter: detailHeader.verticalCenter
                spacing: 8

            Rectangle {
                id: exportAction
                width: Math.max(76, exportActionLabel.implicitWidth + 28)
                height: 34
                radius: 6
                color: Qt.rgba(0, 0, 0, 0.05)
                opacity: selectedKey.length > 0 ? 1.0 : 0.5

                Text {
                    id: exportActionLabel
                    anchors.centerIn: parent
                    text: "导出"
                    font.pixelSize: 12
                    color: "#111827"
                }

                MouseArea {
                    anchors.fill: parent
                    enabled: selectedKey.length > 0
                    cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: if (reviewApi) reviewApi.exportSelectedReport()
                }
            }

            Rectangle {
                id: shareAction
                width: Math.max(76, shareActionLabel.implicitWidth + 28)
                height: 34
                radius: 6
                color: "#0A84FF"
                opacity: selectedKey.length > 0 ? 1.0 : 0.5

                Text {
                    id: shareActionLabel
                    anchors.centerIn: parent
                    text: "分享"
                    font.pixelSize: 12
                    color: "white"
                }

                MouseArea {
                    anchors.fill: parent
                    enabled: selectedKey.length > 0
                    cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                    onClicked: if (reviewApi) reviewApi.shareSelectedReport()
                }
            }

            }

            Flickable {
                id: detailFlick
                x: 0
                y: 71
                width: parent.width
                height: parent.height - 71
                contentWidth: width
                contentHeight: detailContent.implicitHeight + 40
                clip: true

                ScrollBar.vertical: ScrollBar {
                    width: 4
                    policy: ScrollBar.AsNeeded
                    contentItem: Rectangle {
                        implicitWidth: 4
                        radius: 2
                        color: Qt.rgba(0, 0, 0, 0.10)
                    }
                    background: Item {}
                }

                Column {
                    id: detailContent
                    x: 20
                    y: 20
                    width: detailFlick.width - 40
                    spacing: 20

                    Column {
                        width: parent.width
                        spacing: 12
                        visible: selectedKey.length > 0

                        Text {
                            width: parent.width
                            text: "1. 项目与工作回顾"
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                            color: "#111827"
                        }

                        Rectangle { width: parent.width; height: 1; color: Qt.rgba(0, 0, 0, 0.06) }

                        Repeater {
                            model: selectedKey.length > 0 ? (selectedReportReport.projects || []) : []
                            delegate: Text {
                                width: detailContent.width
                                text: "<b>" + (modelData.title || "") + "：</b>" + (modelData.content || "")
                                textFormat: Text.RichText
                                wrapMode: Text.Wrap
                                font.pixelSize: 13
                                lineHeight: 1.8
                                color: "#111827"
                            }
                        }
                    }

                    Column {
                        width: parent.width
                        spacing: 12
                        visible: selectedKey.length > 0

                        Text { text: "2. 问题与复盘"; font.pixelSize: 14; font.weight: Font.DemiBold; color: "#111827" }
                        Rectangle { width: parent.width; height: 1; color: Qt.rgba(0, 0, 0, 0.06) }
                        Text {
                            width: parent.width
                            text: "<b>遇到的困难：</b>" + ((selectedRetrospective.difficulties || []).join("；"))
                            textFormat: Text.RichText
                            wrapMode: Text.Wrap
                            font.pixelSize: 13
                            lineHeight: 1.8
                            color: "#111827"
                        }
                        Text {
                            width: parent.width
                            text: "<b>改进措施：</b>" + ((selectedRetrospective.improvements || []).join("；"))
                            textFormat: Text.RichText
                            wrapMode: Text.Wrap
                            font.pixelSize: 13
                            lineHeight: 1.8
                            color: "#111827"
                        }
                    }

                    Column {
                        width: parent.width
                        spacing: 12
                        visible: selectedKey.length > 0

                        Text { text: "3. 学习与状态评估"; font.pixelSize: 14; font.weight: Font.DemiBold; color: "#111827" }
                        Rectangle { width: parent.width; height: 1; color: Qt.rgba(0, 0, 0, 0.06) }
                        Text {
                            width: parent.width
                            text: "<b>知识获取：</b>" + ((selectedLearningEnergy.learning || []).join("；"))
                            textFormat: Text.RichText
                            wrapMode: Text.Wrap
                            font.pixelSize: 13
                            lineHeight: 1.8
                            color: "#111827"
                        }
                        Text {
                            width: parent.width
                            text: "<b>精力管理：</b>" + (selectedLearningEnergy.energy || "")
                            textFormat: Text.RichText
                            wrapMode: Text.Wrap
                            font.pixelSize: 13
                            lineHeight: 1.8
                            color: "#111827"
                        }
                    }

                    Column {
                        width: parent.width
                        spacing: 12
                        visible: selectedKey.length > 0

                        Text { text: "4. 下周行动计划"; font.pixelSize: 14; font.weight: Font.DemiBold; color: "#111827" }
                        Rectangle { width: parent.width; height: 1; color: Qt.rgba(0, 0, 0, 0.06) }
                        Text {
                            width: parent.width
                            text: "<b>关键任务：</b>" + ((selectedNextWeekPlan.key_tasks || []).join("；"))
                            textFormat: Text.RichText
                            wrapMode: Text.Wrap
                            font.pixelSize: 13
                            lineHeight: 1.8
                            color: "#111827"
                        }
                        Text {
                            width: parent.width
                            text: "<b>常规推进：</b>" + ((selectedNextWeekPlan.routine || []).join("；"))
                            textFormat: Text.RichText
                            wrapMode: Text.Wrap
                            font.pixelSize: 13
                            lineHeight: 1.8
                            color: "#111827"
                        }
                    }

                    Column {
                        width: parent.width
                        spacing: 12
                        visible: selectedKey.length > 0

                        Text { text: "5. 状态与兴趣动态评估"; font.pixelSize: 14; font.weight: Font.DemiBold; color: "#111827" }
                        Rectangle { width: parent.width; height: 1; color: Qt.rgba(0, 0, 0, 0.06) }
                        Text {
                            width: parent.width
                            text: "<b>情绪与能量波动：</b>" + (selectedMoodInterest.mood || "")
                            textFormat: Text.RichText
                            wrapMode: Text.Wrap
                            font.pixelSize: 13
                            lineHeight: 1.8
                            color: "#111827"
                        }
                        Text {
                            width: parent.width
                            text: "<b>兴趣与关注点偏移：</b>" + ((selectedMoodInterest.interest_shift || []).join("；"))
                            textFormat: Text.RichText
                            wrapMode: Text.Wrap
                            font.pixelSize: 13
                            lineHeight: 1.8
                            color: "#111827"
                        }

                        Flow {
                            width: parent.width
                            spacing: 8
                            Repeater {
                                model: selectedKey.length > 0 ? (selectedReportData.interest_tags || []) : []
                                delegate: Rectangle {
                                    width: tagLabel.implicitWidth + 20
                                    height: 24
                                    radius: 12
                                    color: index === 0 ? Qt.rgba(175 / 255, 82 / 255, 222 / 255, 0.10) : Qt.rgba(0, 0, 0, 0.05)

                                    Text {
                                        id: tagLabel
                                        anchors.centerIn: parent
                                        text: modelData
                                        font.pixelSize: 11
                                        color: index === 0 ? "#AF52DE" : "#6B7280"
                                    }
                                }
                            }
                        }
                    }

                    Item {
                        width: 1
                        height: 12
                    }
                }
            }
        }

        Rectangle {
            anchors.fill: parent
            radius: 18
            color: Qt.rgba(1, 1, 1, 0.35)
            visible: !!(reviewApi && reviewApi.loading)
            z: 50

            Column {
                anchors.centerIn: parent
                spacing: 10

                BusyIndicator {
                    width: 32
                    height: 32
                    running: true
                }

                Text {
                    text: "正在生成本期回顾..."
                    font.pixelSize: 13
                    color: "#111827"
                }
            }
        }
    }

    Popup {
        id: yearPopup
        x: yearPopupX
        y: yearPopupY
        width: 132
        height: Math.min(220, yearRepeater.count * 36 + 12)
        padding: 6
        modal: false
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle {
            radius: 10
            color: "white"
            border.width: 1
            border.color: Qt.rgba(0, 0, 0, 0.08)
        }

        Column {
            anchors.fill: parent
            spacing: 2

            Repeater {
                id: yearRepeater
                model: yearOptions
                delegate: Rectangle {
                    width: yearPopup.width - 12
                    height: 34
                    radius: 8
                    color: modelData.value === filterYear ? Qt.rgba(10 / 255, 132 / 255, 255 / 255, 0.08) : "transparent"

                    Text {
                        anchors.centerIn: parent
                        text: modelData.label
                        font.pixelSize: 13
                        color: "#111827"
                    }

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            filterYear = modelData.value
                            yearPopup.close()
                            applyFilters()
                        }
                    }
                }
            }
        }
    }

    Popup {
        id: monthPopup
        x: monthPopupX
        y: monthPopupY
        width: 148
        height: Math.min(300, monthRepeater.count * 30 + 12)
        padding: 6
        modal: false
        focus: true
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
        background: Rectangle {
            radius: 10
            color: "white"
            border.width: 1
            border.color: Qt.rgba(0, 0, 0, 0.08)
        }

        Flickable {
            anchors.fill: parent
            contentWidth: width
            contentHeight: monthColumn.implicitHeight
            clip: true

            Column {
                id: monthColumn
                width: monthPopup.width - 12
                spacing: 2

                Repeater {
                    id: monthRepeater
                    model: monthOptions
                    delegate: Rectangle {
                        width: monthColumn.width
                        height: 28
                        radius: 8
                        color: modelData.value === filterMonth ? Qt.rgba(10 / 255, 132 / 255, 255 / 255, 0.08) : "transparent"

                        Text {
                            anchors.centerIn: parent
                            text: modelData.label
                            font.pixelSize: 13
                            color: "#111827"
                        }

                        MouseArea {
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                filterMonth = modelData.value
                                monthPopup.close()
                                applyFilters()
                            }
                        }
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
        width: Math.min(380, toastText.implicitWidth + 24)
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

    Timer {
        id: toastTimer
        interval: 2200
        repeat: false
        onTriggered: toast.opacity = 0
    }
}
