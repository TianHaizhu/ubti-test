from __future__ import annotations
import json
import os
import sys
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMainWindow, QMessageBox, QPushButton, QPlainTextEdit,
    QProgressBar, QVBoxLayout, QWidget
)

import pipeline

APP_DIR = Path.home() / ".ai_koubo_agent"
APP_DIR.mkdir(parents=True, exist_ok=True)
CONFIG = APP_DIR / "settings.json"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI 口播智能体")
        self.resize(960, 800)
        self.source = QLineEdit()
        self.background = QLineEdit()
        self.output = QLineEdit(str(Path.home() / "Desktop" / "口播成片.mp4"))
        self.api_base = QLineEdit()
        self.api_model = QLineEdit()
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.voice = QLineEdit("zh-CN-XiaoxiaoNeural")
        self.original = QPlainTextEdit()
        self.rewritten = QPlainTextEdit()
        self.status = QLabel("准备就绪。首次语音识别会下载模型；配音需要联网。")
        self.progress = QProgressBar()
        self._load_config()
        self._build()

    def _load_config(self):
        try:
            data = json.loads(CONFIG.read_text(encoding="utf-8"))
            self.api_base.setText(data.get("api_base", ""))
            self.api_model.setText(data.get("api_model", ""))
            self.api_key.setText(data.get("api_key", ""))
            self.voice.setText(data.get("voice", "zh-CN-XiaoxiaoNeural"))
        except (OSError, ValueError):
            pass

    def _save_config(self):
        CONFIG.write_text(json.dumps({
            "api_base": self.api_base.text().strip(),
            "api_model": self.api_model.text().strip(),
            "api_key": self.api_key.text(),
            "voice": self.voice.text().strip() or "zh-CN-XiaoxiaoNeural",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        os.environ["AI_KOUBO_API_BASE"] = self.api_base.text().strip()
        os.environ["AI_KOUBO_MODEL"] = self.api_model.text().strip()
        os.environ["AI_KOUBO_API_KEY"] = self.api_key.text().strip()

    def _browse(self, field, title, filt):
        name, _ = QFileDialog.getOpenFileName(self, title, str(Path.home()), filt)
        if name:
            field.setText(name)

    def _file_row(self, field, title, filt):
        row = QHBoxLayout()
        row.addWidget(field, 1)
        btn = QPushButton("选择文件…")
        btn.clicked.connect(lambda: self._browse(field, title, filt))
        row.addWidget(btn)
        return row

    def _build(self):
        root = QWidget()
        layout = QVBoxLayout(root)
        heading = QLabel("视频导入 → 语音识别 → 文案改写 → 中文配音 → 字幕与 MP4")
        heading.setStyleSheet("font-size:18px;font-weight:600;padding:8px")
        layout.addWidget(heading)

        media = QGroupBox("1. 素材")
        form = QFormLayout(media)
        form.addRow("视频文件或可访问 URL：", self._file_row(
            self.source, "选择参考视频", "视频 (*.mp4 *.mov *.mkv *.webm);;所有文件 (*.*)"))
        form.addRow("成片背景视频：", self._file_row(
            self.background, "选择背景视频", "视频 (*.mp4 *.mov *.mkv *.webm);;所有文件 (*.*)"))
        layout.addWidget(media)

        texts = QGroupBox("2. 文案")
        tv = QVBoxLayout(texts)
        tv.addWidget(QLabel("识别出的原始文案（也可手动粘贴）："))
        tv.addWidget(self.original)
        row = QHBoxLayout()
        transcribe = QPushButton("从视频提取文案")
        transcribe.clicked.connect(self._transcribe)
        row.addWidget(transcribe)
        tv.addLayout(row)
        tv.addWidget(QLabel("改写后的口播文案："))
        tv.addWidget(self.rewritten)
        actions = QHBoxLayout()
        rewrite = QPushButton("AI 改写文案")
        rewrite.clicked.connect(self._rewrite)
        save = QPushButton("保存文案 TXT")
        save.clicked.connect(self._save_text)
        actions.addWidget(rewrite)
        actions.addWidget(save)
        tv.addLayout(actions)
        layout.addWidget(texts, 1)

        config = QGroupBox("3. AI 与配音设置（密钥只保存在本机用户目录）")
        cf = QFormLayout(config)
        cf.addRow("OpenAI 兼容 API 地址：", self.api_base)
        cf.addRow("模型名称：", self.api_model)
        cf.addRow("API Key：", self.api_key)
        cf.addRow("中文语音名称：", self.voice)
        layout.addWidget(config)

        out = QGroupBox("4. 生成与导出")
        of = QFormLayout(out)
        line = QHBoxLayout()
        line.addWidget(self.output, 1)
        btn = QPushButton("选择保存位置…")
        btn.clicked.connect(self._choose_output)
        line.addWidget(btn)
        of.addRow("输出 MP4：", line)
        buttons = QHBoxLayout()
        tts = QPushButton("生成中文配音")
        tts.clicked.connect(self._tts)
        render = QPushButton("合成 MP4 + 字幕轨道")
        render.clicked.connect(self._render)
        buttons.addWidget(tts)
        buttons.addWidget(render)
        of.addRow(buttons)
        layout.addWidget(out)
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.setCentralWidget(root)

    def _set_status(self, text):
        self.status.setText(text)
        QApplication.processEvents()

    def _transcribe(self):
        try:
            source = pipeline.download_media(self.source.text(), self._set_status)
            text = pipeline.transcribe_audio(str(source), progress=self._set_status)
            self.original.setPlainText(text)
            if not self.rewritten.toPlainText().strip():
                self.rewritten.setPlainText(text)
            self._set_status("语音识别完成。请检查专有名词和识别结果。")
            self.progress.setValue(25)
        except Exception as exc:
            QMessageBox.critical(self, "提取失败", str(exc))
            self._set_status("提取失败。")

    def _rewrite(self):
        self._save_config()
        try:
            result = pipeline.rewrite_text(self.original.toPlainText())
            self.rewritten.setPlainText(result)
            self.progress.setValue(45)
            self._set_status("AI 改写完成，请人工核对事实与措辞。")
        except Exception as exc:
            QMessageBox.warning(self, "AI 改写失败", str(exc))

    def _save_text(self):
        name, _ = QFileDialog.getSaveFileName(self, "保存文案", str(Path.home() / "Desktop" / "口播文案.txt"), "文本 (*.txt)")
        if not name:
            return
        Path(name).write_text("【原始文案】\n" + self.original.toPlainText() + "\n\n【改写文案】\n" + self.rewritten.toPlainText(), encoding="utf-8")
        self._set_status("文案已保存。")

    def _tts(self):
        try:
            self._save_config()
            text = self.rewritten.toPlainText().strip() or self.original.toPlainText().strip()
            audio = APP_DIR / "voice.mp3"
            pipeline.synthesize_speech(text, str(audio), self.voice.text().strip() or "zh-CN-XiaoxiaoNeural", self._set_status)
            self.progress.setValue(65)
            QMessageBox.information(self, "配音完成", f"配音文件已生成：\n{audio}")
            self._set_status("中文配音已生成。")
        except Exception as exc:
            QMessageBox.critical(self, "配音失败", str(exc))

    def _render(self):
        try:
            text = self.rewritten.toPlainText().strip() or self.original.toPlainText().strip()
            if not text:
                raise ValueError("请先提取或输入口播文案。")
            audio = APP_DIR / "voice.mp3"
            if not audio.exists():
                pipeline.synthesize_speech(text, str(audio), self.voice.text().strip() or "zh-CN-XiaoxiaoNeural", self._set_status)
            bg = pipeline.download_media(self.background.text(), self._set_status)
            srt = APP_DIR / "subtitles.srt"
            pipeline.write_srt(text, str(srt))
            output = self.output.text().strip()
            if not output:
                raise ValueError("请设置输出 MP4 路径。")
            pipeline.render_video(str(bg), str(audio), str(srt), output, self._set_status)
            self.progress.setValue(100)
            QMessageBox.information(self, "导出完成", f"MP4 已生成：\n{output}\n\n当前字幕为可开关字幕轨道；时间按文本行估算，建议复核。")
            self._set_status("MP4 合成完成。")
        except Exception as exc:
            QMessageBox.critical(self, "合成失败", str(exc))
            self._set_status("合成失败。")

    def _choose_output(self):
        name, _ = QFileDialog.getSaveFileName(self, "选择输出位置", self.output.text(), "MP4 视频 (*.mp4)")
        if name:
            self.output.setText(name if name.lower().endswith(".mp4") else name + ".mp4")


def main():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    return app.exec()

if __name__ == "__main__":
    raise SystemExit(main())
