// qml/pages/onboarding_1_data_dir.qml
import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Window 2.15
import Qt.labs.platform 1.1

import theme 1.0 as Theme
import components 1.0 as C

C.GlassWindow {
    id: win
    title: "Onboarding - Step 1"

    property string selectedDir: ""
    property bool hasSelectedDir: selectedDir.length > 0

    Component.onCompleted: {
        x = Math.max(0, (Screen.width - width) / 2)
        y = Math.max(0, (Screen.height - height) / 2)
        initFromDraft()
    }

    function safeDecode(s) {
        try { return decodeURIComponent(s) } catch(e) { return s }
    }

    function urlToLocalPath(u) {
        if (!u) return ""
        var s = u.toString ? u.toString() : ("" + u)

        // Qt url: file:///C:/xxx  or  file:///home/xxx
        if (s.startsWith("file:///")) {
            var p = safeDecode(s.substring(7))  // 得到 "/C:/xxx" 或 "/home/xxx"
            // Windows: "/C:/..." -> "C:/..."
            if (/^\/[A-Za-z]:\//.test(p)) p = p.substring(1)
            return p
        }
        if (s.startsWith("file://")) {
            return safeDecode(s.substring(7))
        }
        return safeDecode(s)
    }

    function localPathToUrl(p) {
        if (!p) return ""
        var s = ("" + p).replace(/\\/g, "/")
        if (/^[A-Za-z]:\//.test(s)) return "file:///" + s
        if (s.startsWith("/")) return "file://" + s
        return "file:///" + s
    }

    function initFromDraft() {
        try { onboardingDraft.loadDraft() } catch (e) {}

        var p = ""
        try { p = onboardingDraft.getDraftDataDir() } catch (e1) { p = "" }

        if (!p || p.trim().length === 0) {
            try { p = onboardingDraft.getSuggestedDefaultDataDir() } catch (e2) { p = "" }
        }

        // 关键：初始化只显示，不写入临时文件，避免覆盖
        if (p && p.trim().length > 0) {
            setSelectedDir(p.trim(), /*persist*/ false)
        }
    }

    function setSelectedDir(p, persist) {
        selectedDir = p || ""
        dataPathField.text = selectedDir

        if (persist) {
            try {
                onboardingDraft.setDraftDataDir(selectedDir)
                onboardingDraft.setDraftStep(1)
                onboardingDraft.saveDraft()
                console.log("[draft saved] data_dir =", onboardingDraft.getDraftDataDir())
            } catch (e) {
                console.log("save draft failed:", e)
            }
        }
    }

    function getDialogFolderUrl() {
        var u = ""
        // 兼容不同 Qt 版本字段
        try { if (folderDialog.folder) u = folderDialog.folder } catch(e) {}
        try { if ((!u || u === "") && folderDialog.selectedFolder) u = folderDialog.selectedFolder } catch(e2) {}
        try { if ((!u || u === "") && folderDialog.currentFolder) u = folderDialog.currentFolder } catch(e3) {}
        return u
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

    FolderDialog {
        id: folderDialog
        title: "选择数据目录"
        onAccepted: {
            var u = getDialogFolderUrl()
            var p = urlToLocalPath(u).trim()
            console.log("[folderDialog accepted] url =", u, " path =", p)

            if (p.length > 0) {
                setSelectedDir(p, /*persist*/ true)
            }
        }
    }

    C.WizardScaffold {
        id: wizard
        anchors.fill: parent

        stepIndex: 1
        stepTotal: 5
        titleText: "数据存储位置"
        footerMode: "first"

        nextEnabled: win.hasSelectedDir

        onMinimizeRequested: win.showMinimized()
        onCloseRequested: doCancelAndQuit()

        onCancelClicked: doCancelAndQuit()
        onNextClicked: {
            // 再保险：Next 时也写一次
            try {
                onboardingDraft.setDraftDataDir(win.selectedDir)
                onboardingDraft.setDraftStep(2)
                onboardingDraft.saveDraft()
                console.log("[draft saved on next] data_dir =", onboardingDraft.getDraftDataDir())
            } catch (e) {}

            openStep("onboarding_2_kimi.qml")
        }

        // 内容区（不动背景/顶部/底部，只补内容）
        Item {
            anchors.fill: parent

            ColumnLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                anchors.topMargin: 16
                spacing: 18

                Label {
                    Layout.fillWidth: true
                    text: "LoosePlan 需要一个地方存储你的日程、记忆和配置"
                    wrapMode: Text.WordWrap
                    font.pixelSize: 14
                    color: Theme.Colors.textSecondary
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 8

                    Label {
                        text: "数据存储位置"
                        font.pixelSize: 13
                        font.weight: Font.Medium
                        color: Theme.Colors.textPrimary
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 12

                        TextField {
                            id: dataPathField
                            Layout.fillWidth: true
                            Layout.preferredHeight: 44
                            readOnly: true
                            placeholderText: "请点击右侧按钮选择目录..."
                            font.pixelSize: 14
                            color: Theme.Colors.textPrimary

                            background: Rectangle {
                                radius: Theme.Metrics.inputRadius
                                color: Qt.rgba(1, 1, 1, 0.50)
                                border.width: Theme.Metrics.borderW
                                border.color: Theme.Colors.glassBorder
                            }
                        }

                        C.SecondaryButton {
                            text: "选择"
                            Layout.preferredHeight: 44
                            Layout.preferredWidth: 86
                            onClicked: {
                                if (win.selectedDir && win.selectedDir.length > 0) {
                                    // 兼容：优先设置 currentFolder（若存在）
                                    try { folderDialog.currentFolder = localPathToUrl(win.selectedDir) } catch(e) {}
                                    try { folderDialog.folder = localPathToUrl(win.selectedDir) } catch(e2) {}
                                }
                                folderDialog.open()
                            }
                        }
                    }
                }

                Item { Layout.fillHeight: true }

                Rectangle {
                    Layout.fillWidth: true
                    radius: Theme.Metrics.cardRadius
                    color: Qt.rgba(1, 1, 1, 0.50)
                    border.width: Theme.Metrics.borderW
                    border.color: Theme.Colors.glassBorder
                    height: infoText.implicitHeight + 28

                    Text {
                        id: infoText
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: parent.top
                        anchors.margins: 16
                        wrapMode: Text.WordWrap
                        textFormat: Text.RichText
                        font.pixelSize: 13
                        color: Theme.Colors.textSecondary
                        text: "<b>建议：</b>选择一个有充足空间的本地目录。所有数据将加密存储在该位置，包括聊天记录、日程安排和生成的记忆档案。"
                    }
                }
            }
        }
    }
}
