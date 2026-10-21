from __future__ import annotations
import sys
from pathlib import Path
from PySide6.QtWidgets import (QApplication, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QPlainTextEdit, QProgressBar, QVBoxLayout, QWidget)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI 口播智能体 · 第一版")
        self.resize(900, 720)
        self.video = QLineEdit()
        self.avatar = QLineEdit()
        self.audio = QLineEdit()
        self.output = QLineEdit(str(Path.home() / "Desktop" / "口播成片.mp4"))
        self.source_text = QPlainTextEdit()
        self.rewrite_text = QPlainTextEdit()
        self.status = QLabel("就绪：这是可运行的桌面 UI 骨架，AI 和视频合成模块尚未接入。")
        self.build()

    def pick(self, field, filt):
        name, _ = QFileDialog.getOpenFileName(self, "选择文件", str(Path.home()), filt)
        if name:
            field.setText(name)

    def row(self, field, filt):
        box = QHBoxLayout()
        box.addWidget(field, 1)
        btn = QPushButton("选择…")
        btn.clicked.connect(lambda: self.pick(field, filt))
        box.addWidget(btn)
        return box

    def build(self):
        root = QWidget()
        layout = QVBoxLayout(root)
        title = QLabel("素材选择 → 文案编辑 → 语音/数字人 → MP4 导出")
        title.setStyleSheet("font-size:18px;font-weight:600;padding:8px")
        layout.addWidget(title)

        group = QGroupBox("一、选择素材")
        form = QFormLayout(group)
        form.addRow("参考视频：", self.row(self.video, "视频 (*.mp4 *.mov *.mkv *.webm);;所有文件 (*.*)"))
        form.addRow("本人照片/视频：", self.row(self.avatar, "媒体 (*.png *.jpg *.jpeg *.webp *.mp4 *.mov);;所有文件 (*.*)"))
        form.addRow("配音音频（可选）：", self.row(self.audio, "音频 (*.wav *.mp3 *.m4a *.aac);;所有文件 (*.*)"))
        layout.addWidget(group)

        texts = QGroupBox("二、口播文案")
        vl = QVBoxLayout(texts)
        vl.addWidget(QLabel("原始文案（可粘贴）："))
        vl.addWidget(self.source_text)
        vl.addWidget(QLabel("改写文案（目前手动编辑，AI 接口待接入）："))
        vl.addWidget(self.rewrite_text)
        layout.addWidget(texts, 1)

        out = QGroupBox("三、导出设置")
        of = QFormLayout(out)
        line = QHBoxLayout()
        line.addWidget(self.output, 1)
        save_as = QPushButton("选择保存位置…")
        save_as.clicked.connect(self.pick_output)
        line.addWidget(save_as)
        of.addRow("目标 MP4：", line)
        layout.addWidget(out)

        buttons = QHBoxLayout()
        save_text = QPushButton("保存文案为 TXT")
        save_text.clicked.connect(self.save_text)
        check = QPushButton("检查输入")
        check.clicked.connect(self.check_inputs)
        buttons.addWidget(save_text)
        buttons.addWidget(check)
        layout.addLayout(buttons)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.setCentralWidget(root)

    def pick_output(self):
        name, _ = QFileDialog.getSaveFileName(self, "选择输出位置", self.output.text(), "MP4 视频 (*.mp4)")
        if name:
            self.output.setText(name if name.lower().endswith(".mp4") else name + ".mp4")

    def save_text(self):
        name, _ = QFileDialog.getSaveFileName(self, "保存文案", str(Path.home() / "Desktop" / "口播文案.txt"), "文本 (*.txt)")
        if not name:
            return
        data = "【原始文案】\n" + self.source_text.toPlainText() + "\n\n【改写文案】\n" + self.rewrite_text.toPlainText()
        try:
            Path(name).write_text(data, encoding="utf-8")
            self.status.setText(f"文案已保存：{name}")
        except OSError as exc:
            QMessageBox.critical(self, "保存失败", str(exc))

    def check_inputs(self):
        missing = []
        if not self.source_text.toPlainText().strip():
            missing.append("原始文案")
        if not self.rewrite_text.toPlainText().strip():
            missing.append("改写文案")
        if missing:
            QMessageBox.information(self, "检查结果", "请补充：\n- " + "\n- ".join(missing))
        else:
            QMessageBox.information(self, "检查结果", "文案已填写。注意：当前版本尚未接入 AI、数字人口型和 MP4 渲染模块。")
        self.status.setText("输入检查完成；自动处理模块待后续集成。")

def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
