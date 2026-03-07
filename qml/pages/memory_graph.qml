import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Window 2.15

Window {
    id: win
    width: 680
    height: 520
    visible: true
    color: "transparent"
    title: "记忆图谱"
    flags: Qt.FramelessWindowHint | Qt.Window

    readonly property var memoryApi: (typeof memoryGraphService !== "undefined") ? memoryGraphService : null
    property string pendingSection: ""
    property string pendingTitle: ""

    property var iconBodies: ({
        "user": "<circle cx='12' cy='8' r='4'/><path d='M4 20c0-4 4-6 8-6s8 2 8 6'/>",
        "calendar": "<rect x='3' y='4' width='18' height='18' rx='2'/><path d='M16 2v4M8 2v4M3 10h18'/>",
        "layers": "<path d='M12 2L2 7l10 5 10-5-10-5z'/><path d='M2 17l10 5 10-5'/><path d='M2 12l10 5 10-5'/>",
        "shield": "<path d='M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z'/><path d='M9 12l2 2 4-4'/>",
        "heart": "<path d='M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z'/>",
        "star": "<polygon points='12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2'/>",
        "health": "<path d='M22 12h-4l-3 9L9 3l-3 9H2'/>",
        "network": "<circle cx='12' cy='5' r='3'/><circle cx='5' cy='19' r='3'/><circle cx='19' cy='19' r='3'/><path d='M12 8v4M7.5 17l3-3M16.5 17l-3-3'/>",
        "clock": "<circle cx='12' cy='12' r='10'/><path d='M12 6v6l4 2'/>",
        "moon": "<path d='M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z'/>",
        "food": "<path d='M18 8h1a4 4 0 0 1 0 8h-1'/><path d='M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z'/><path d='M6 1v3M10 1v3M14 1v3'/>",
        "silent": "<path d='M11 5L6 9H2v6h4l5 4V5z'/><path d='M23 9l-6 6M17 9l6 6'/>",
        "message": "<path d='M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z'/>",
        "shopping": "<circle cx='9' cy='21' r='1'/><circle cx='20' cy='21' r='1'/><path d='M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6'/>",
        "device": "<rect x='4' y='2' width='16' height='20' rx='2'/><path d='M12 18h.01'/>",
        "book": "<path d='M4 19.5A2.5 2.5 0 0 1 6.5 17H20'/><path d='M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z'/>",
        "travel": "<circle cx='12' cy='12' r='10'/><polygon points='16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76'/>",
        "lock": "<rect x='3' y='11' width='18' height='11' rx='2'/><path d='M7 11V7a5 5 0 0 1 10 0v4'/>",
        "reply": "<path d='M9 17l-5-5 5-5'/><path d='M20 18v-2a4 4 0 0 0-4-4H4'/>",
        "list": "<path d='M8 6h13M8 12h13M8 18h13'/><path d='M3 6h.01M3 12h.01M3 18h.01'/>",
        "format": "<path d='M12 19l7-7 3 3-7 7-3-3z'/><path d='M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z'/><path d='M2 2l7.586 7.586'/><circle cx='11' cy='11' r='2'/>",
        "save": "<path d='M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z'/><path d='M17 21V13H7v8'/><path d='M7 3v5h8'/>",
        "ai": "<path d='M12 2L2 7l10 5 10-5-10-5z'/><path d='M2 17l10 5 10-5'/><path d='M2 12l10 5 10-5'/>"
    })

    function svgData(svg) {
        return "data:image/svg+xml;utf8," + encodeURIComponent(svg)
    }

    function iconSource(name, color) {
        var body = iconBodies[name] || iconBodies.user
        return svgData("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='" + color + "' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>" + body + "</svg>")
    }

    function sourceBg(style) {
        if (style === "init") return "#E0F2FE"
        if (style === "user") return "#DCFCE7"
        if (style === "chat") return "#F3E8FF"
        if (style === "mention") return "#FEF3C7"
        return "#F3F4F6"
    }

    function sourceFg(style) {
        if (style === "init") return "#0369A1"
        if (style === "user") return "#15803D"
        if (style === "chat") return "#7C3AED"
        if (style === "mention") return "#B45309"
        return "#4B5563"
    }

    onClosing: function(close) {
        close.accepted = false
        visible = false
    }

    Component.onCompleted: {
        if (memoryApi)
            memoryApi.reload()
        requestActivate()
    }

    onVisibleChanged: {
        if (visible && memoryApi) {
            memoryApi.reload()
            memoryApi.refreshGraphOnOpen()
        }
    }

    Connections {
        target: memoryApi
        ignoreUnknownSignals: true

        function onToastRequested(text) {
            toastText.text = text || ""
            toast.visible = true
            toast.opacity = 1
            toastTimer.restart()
        }
    }

    Rectangle {
        id: shell
        anchors.fill: parent
        radius: 18
        color: Qt.rgba(1, 1, 1, 0.72)
        border.width: 1
        border.color: Qt.rgba(0, 0, 0, 0.04)

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

            Row {
                x: 24
                anchors.verticalCenter: parent.verticalCenter
                spacing: 8

                Rectangle {
                    width: 20
                    height: 20
                    radius: 6
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: "#0A84FF" }
                        GradientStop { position: 1.0; color: "#0077ED" }
                    }

                    Text {
                        anchors.centerIn: parent
                        text: "✓"
                        font.pixelSize: 11
                        font.weight: Font.Bold
                        color: "white"
                    }
                }

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "记忆图谱"
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                    color: "#1A1A1A"
                }
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

                    Text {
                        anchors.centerIn: parent
                        visible: minMouse.containsMouse
                        text: "−"
                        font.pixelSize: 9
                        font.weight: Font.DemiBold
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

                    Text {
                        anchors.centerIn: parent
                        visible: closeMouse.containsMouse
                        text: "×"
                        font.pixelSize: 9
                        font.weight: Font.DemiBold
                        color: "#7A1A15"
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
            x: 0
            y: 44
            width: parent.width
            height: 1
            color: Qt.rgba(0, 0, 0, 0.06)
        }

        Rectangle {
            id: sidebar
            x: 0
            y: 45
            width: 160
            height: parent.height - 45
            color: Qt.rgba(1, 1, 1, 0.5)

            Rectangle {
                anchors.right: parent.right
                width: 1
                height: parent.height
                color: Qt.rgba(0, 0, 0, 0.06)
            }

            ListView {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                anchors.topMargin: 16
                anchors.bottomMargin: 16
                spacing: 6
                interactive: false
                model: memoryApi ? memoryApi.categories : []

                delegate: Rectangle {
                    width: ListView.view.width
                    height: 44
                    radius: 10
                    color: (memoryApi && memoryApi.currentCategory === modelData.key) ? "#0A84FF" : "transparent"
                    border.width: 0

                    layer.enabled: color === "#0A84FF"
                    layer.effect: null

                    Row {
                        anchors.left: parent.left
                        anchors.leftMargin: 16
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 10

                        Image {
                            width: 18
                            height: 18
                            source: iconSource(modelData.icon || "user", (memoryApi && memoryApi.currentCategory === modelData.key) ? "#FFFFFF" : "#6B7280")
                            fillMode: Image.PreserveAspectFit
                            sourceSize.width: 36
                            sourceSize.height: 36
                        }

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData.title || ""
                            font.pixelSize: 13
                            font.weight: Font.Medium
                            color: (memoryApi && memoryApi.currentCategory === modelData.key) ? "#FFFFFF" : "#4B5563"
                        }
                    }

                    Rectangle {
                        anchors.fill: parent
                        radius: 10
                        color: "transparent"
                        border.width: hoverMouse.containsMouse && !(memoryApi && memoryApi.currentCategory === modelData.key) ? 1 : 0
                        border.color: "#DCE3EC"
                    }

                    MouseArea {
                        id: hoverMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: if (memoryApi) memoryApi.selectCategory(modelData.key || "")
                    }
                }
            }
        }

        Flickable {
            id: mainPanel
            x: 160
            y: 45
            width: parent.width - 160
            height: parent.height - 45
            clip: true
            contentWidth: width
            contentHeight: cardsColumn.implicitHeight + 36

            ScrollBar.vertical: ScrollBar {
                width: 4
                policy: ScrollBar.AsNeeded
                contentItem: Rectangle {
                    implicitWidth: 4
                    radius: 2
                    color: Qt.rgba(0, 0, 0, 0.14)
                }
                background: Item {}
            }

            Column {
                id: cardsColumn
                x: 20
                y: 16
                width: mainPanel.width - 40
                spacing: 12

                Repeater {
                    model: memoryApi ? memoryApi.currentCards : []

                    delegate: Rectangle {
                        id: card
                        width: cardsColumn.width
                        height: footerRow.y + footerRow.height + 12
                        radius: 14
                        color: Qt.rgba(1, 1, 1, 0.9)
                        border.width: 1
                        border.color: Qt.rgba(0, 0, 0, 0.04)

                        property bool hovering: cardMouse.containsMouse || saveMouse.containsMouse || aiMouse.containsMouse

                        Rectangle {
                            anchors.fill: parent
                            radius: 14
                            color: "transparent"
                            border.width: hovering ? 1 : 0
                            border.color: Qt.rgba(10 / 255, 132 / 255, 255 / 255, 0.10)
                        }

                        Row {
                            id: headerRow
                            x: 16
                            y: 12
                            width: parent.width - 32
                            height: 22
                            spacing: 6

                            Image {
                                width: 14
                                height: 14
                                anchors.verticalCenter: parent.verticalCenter
                                source: iconSource(modelData.icon || "user", "#0A84FF")
                                fillMode: Image.PreserveAspectFit
                                sourceSize.width: 28
                                sourceSize.height: 28
                            }

                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: modelData.title || ""
                                font.pixelSize: 13
                                font.weight: Font.DemiBold
                                color: "#1A1A1A"
                            }
                        }

                        Rectangle {
                            x: 0
                            y: 42
                            width: parent.width
                            height: 1
                            color: Qt.rgba(0, 0, 0, 0.04)
                        }

                        Rectangle {
                            id: bodyBox
                            x: 0
                            y: 43
                            width: parent.width
                            height: Math.max(96, Math.min(156, editor.contentHeight + 32))
                            color: "transparent"

                            TextArea {
                                id: editor
                                x: 16
                                y: 12
                                width: parent.width - 32
                                height: parent.height - 24
                                text: modelData.content || ""
                                placeholderText: modelData.placeholder || "点击输入记忆内容..."
                                font.pixelSize: 12
                                color: "#374151"
                                wrapMode: TextEdit.Wrap
                                selectByMouse: true
                                persistentSelection: true
                                background: Item {}
                            }
                        }

                        Rectangle {
                            x: 0
                            y: bodyBox.y + bodyBox.height
                            width: parent.width
                            height: 1
                            color: Qt.rgba(0, 0, 0, 0.04)
                        }

                        Item {
                            id: footerRow
                            x: 16
                            y: bodyBox.y + bodyBox.height + 10
                            width: parent.width - 32
                            height: 26

                            Row {
                                id: actionsRow
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 6
                                opacity: 1

                                Behavior on opacity { NumberAnimation { duration: 150 } }

                                Rectangle {
                                    width: 26
                                    height: 26
                                    radius: 6
                                    color: saveMouse.containsMouse ? "#0A84FF" : Qt.rgba(0, 0, 0, 0.04)

                                    Image {
                                        anchors.centerIn: parent
                                        width: 14
                                        height: 14
                                        source: iconSource("save", saveMouse.containsMouse ? "#FFFFFF" : "#6B7280")
                                        fillMode: Image.PreserveAspectFit
                                        sourceSize.width: 28
                                        sourceSize.height: 28
                                    }

                                    MouseArea {
                                        id: saveMouse
                                        anchors.fill: parent
                                        enabled: hovering
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: if (memoryApi) memoryApi.saveCard(modelData.section || "", modelData.title || "", editor.text)
                                    }
                                }

                                Rectangle {
                                    width: 26
                                    height: 26
                                    radius: 6
                                    color: aiMouse.containsMouse ? "#0A84FF" : Qt.rgba(0, 0, 0, 0.04)

                                    Image {
                                        anchors.centerIn: parent
                                        width: 14
                                        height: 14
                                        source: iconSource("ai", aiMouse.containsMouse ? "#FFFFFF" : "#6B7280")
                                        fillMode: Image.PreserveAspectFit
                                        sourceSize.width: 28
                                        sourceSize.height: 28
                                    }

                                    MouseArea {
                                        id: aiMouse
                                        anchors.fill: parent
                                        enabled: hovering
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            pendingSection = modelData.section || ""
                                            pendingTitle = modelData.title || ""
                                            confirmOverlay.visible = true
                                        }
                                    }
                                }
                            }

                            Row {
                                id: metaRow
                                anchors.left: parent.left
                                anchors.right: actionsRow.left
                                anchors.rightMargin: 12
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 8
                                clip: true

                                Row {
                                    anchors.verticalCenter: parent.verticalCenter
                                    spacing: 4

                                    Image {
                                        width: 12
                                        height: 12
                                        anchors.verticalCenter: parent.verticalCenter
                                        source: iconSource("clock", "#9CA3AF")
                                        fillMode: Image.PreserveAspectFit
                                        sourceSize.width: 24
                                        sourceSize.height: 24
                                    }

                                    Text {
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: modelData.memory_time_text || "--"
                                        font.pixelSize: 11
                                        color: "#9CA3AF"
                                    }
                                }

                                Rectangle {
                                    visible: (modelData.source_label || "").length > 0
                                    width: sourceText.implicitWidth + 16
                                    height: 22
                                    radius: 11
                                    color: sourceBg(modelData.source_style || "")

                                    Text {
                                        id: sourceText
                                        anchors.centerIn: parent
                                        text: modelData.source_label || ""
                                        font.pixelSize: 10
                                        font.weight: Font.Medium
                                        color: sourceFg(modelData.source_style || "")
                                    }
                                }
                            }
                        }

                        MouseArea {
                            id: cardMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            acceptedButtons: Qt.NoButton
                        }
                    }
                }
            }
        }

        Rectangle {
            id: toast
            visible: false
            opacity: 0
            width: Math.min(360, toastText.implicitWidth + 42)
            height: 40
            radius: 20
            color: Qt.rgba(0, 0, 0, 0.85)
            anchors.horizontalCenter: parent.horizontalCenter
            y: parent.height - 58
            z: 200

            Behavior on opacity { NumberAnimation { duration: 220 } }
            onOpacityChanged: if (opacity === 0) visible = false

            Row {
                anchors.centerIn: parent
                spacing: 8

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: "✓"
                    font.pixelSize: 14
                    font.weight: Font.Bold
                    color: "#34C759"
                }

                Text {
                    id: toastText
                    anchors.verticalCenter: parent.verticalCenter
                    text: ""
                    font.pixelSize: 13
                    font.weight: Font.Medium
                    color: "white"
                }
            }
        }

        Rectangle {
            id: confirmOverlay
            anchors.fill: parent
            visible: false
            color: Qt.rgba(0, 0, 0, 0.25)
            z: 210

            MouseArea {
                anchors.fill: parent
                onClicked: confirmOverlay.visible = false
            }

            Rectangle {
                width: 320
                height: 184
                radius: 14
                color: Qt.rgba(1, 1, 1, 0.95)
                anchors.centerIn: parent

                MouseArea {
                    anchors.fill: parent
                    onClicked: {}
                }

                Row {
                    x: 20
                    y: 20
                    spacing: 10

                    Rectangle {
                        width: 32
                        height: 32
                        radius: 8
                        gradient: Gradient {
                            GradientStop { position: 0.0; color: "#FF9500" }
                            GradientStop { position: 1.0; color: "#FF6B35" }
                        }

                        Text {
                            anchors.centerIn: parent
                            text: "!"
                            font.pixelSize: 18
                            font.weight: Font.Bold
                            color: "white"
                        }
                    }

                    Text {
                        anchors.verticalCenter: parent.verticalCenter
                        text: "AI覆盖提示"
                        font.pixelSize: 15
                        font.weight: Font.DemiBold
                        color: "#1A1A1A"
                    }
                }

                Text {
                    x: 20
                    y: 66
                    width: parent.width - 40
                    wrapMode: Text.Wrap
                    lineHeight: 1.6
                    font.pixelSize: 13
                    color: "#4B5563"
                    text: "AI 即将更新此条记忆，将覆盖当前编辑内容。\n覆盖前会自动备份本地版本。"
                }

                Row {
                    anchors.right: parent.right
                    anchors.rightMargin: 20
                    y: 138
                    spacing: 10

                    Rectangle {
                        width: 72
                        height: 34
                        radius: 8
                        color: Qt.rgba(0, 0, 0, 0.06)

                        Text {
                            anchors.centerIn: parent
                            text: "取消"
                            font.pixelSize: 13
                            color: "#4B5563"
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: confirmOverlay.visible = false
                        }
                    }

                    Rectangle {
                        width: 96
                        height: 34
                        radius: 8
                        color: "#0A84FF"

                        Text {
                            anchors.centerIn: parent
                            text: "确认覆盖"
                            font.pixelSize: 13
                            color: "white"
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                confirmOverlay.visible = false
                                if (memoryApi)
                                    memoryApi.updateCardWithAi(pendingSection, pendingTitle)
                            }
                        }
                    }
                }
            }
        }

        Rectangle {
            anchors.fill: parent
            visible: !!(memoryApi && memoryApi.loading)
            color: Qt.rgba(1, 1, 1, 0.35)
            z: 220

            Column {
                anchors.centerIn: parent
                spacing: 10

                BusyIndicator {
                    width: 32
                    height: 32
                    running: true
                }

                Text {
                    text: "正在更新记忆图谱..."
                    font.pixelSize: 13
                    color: "#111827"
                }
            }
        }
    }

    Timer {
        id: toastTimer
        interval: 2200
        repeat: false
        onTriggered: toast.opacity = 0
    }
}
