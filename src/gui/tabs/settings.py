# src/gui/tabs/settings.py
from typing import Optional

from PyQt6.QtWidgets import (QFormLayout, QGroupBox, QLabel, QLineEdit,
                             QSpinBox, QVBoxLayout, QWidget)


class SettingsTab(QWidget):
    def __init__(self, parent: Optional[QWidget] = None, config: Optional[dict] = None):
        super().__init__(parent)
        self._config = config or {}
        self._build_ui()

    def _build_ui(self):
        """设置参数界面"""
        layout = QVBoxLayout(self)

        # 单词数量设置
        count_group = QGroupBox("单词数量设置")
        count_form = QFormLayout(count_group)

        self.focus_spin = QSpinBox()
        self.focus_spin.setRange(0, 50)
        count_form.addRow("每天重点单词数量:", self.focus_spin)

        self.total_spin = QSpinBox()
        self.total_spin.setRange(1, 100)
        count_form.addRow("每天总单词数:", self.total_spin)

        self.review_label = QLabel()
        self.review_label.setStyleSheet("color: blue;")
        count_form.addRow("每天复习单词数量:", self.review_label)

        layout.addWidget(count_group)

        # 生成设置
        gen_group = QGroupBox("生成设置")
        gen_form = QFormLayout(gen_group)

        self.days_spin = QSpinBox()
        self.days_spin.setRange(1, 30)
        gen_form.addRow("生成天数:", self.days_spin)

        self.filename_edit = QLineEdit()
        gen_form.addRow("输出文件名:", self.filename_edit)

        layout.addWidget(gen_group)
        layout.addStretch(1)

        # 顺序关键：先从配置设值，再设动态上限，最后连接信号
        # （先连信号再设值会触发多余的钳制/更新，且 config 中 focus>total 时表现不一致）
        self.focus_spin.setValue(int(self._config.get('focus_count', 10)))
        self.total_spin.setValue(int(self._config.get('total_count', 18)))
        self.days_spin.setValue(int(self._config.get('days', 5)))
        self.filename_edit.setText(self._config.get('filename', '单词听写'))

        # 交互式钳制：total 缩小时 focus 的上限随之缩小，QSpinBox 自动把 value 拉回范围内
        self.focus_spin.setMaximum(self.total_spin.value())
        self.total_spin.valueChanged.connect(self.focus_spin.setMaximum)
        self.total_spin.valueChanged.connect(self._update_review_label)
        self.focus_spin.valueChanged.connect(self._update_review_label)
        self._update_review_label()

    def _update_review_label(self, *_args):
        """更新复习单词数显示（= 总数 - 重点数）"""
        self.review_label.setText(str(self.total_spin.value() - self.focus_spin.value()))

    # ── 对外接口 ─────────────────────────────────────────────────────

    def focus_count(self) -> int:
        return self.focus_spin.value()

    def total_count(self) -> int:
        return self.total_spin.value()

    def days(self) -> int:
        return self.days_spin.value()

    def filename(self) -> str:
        return self.filename_edit.text().strip()
