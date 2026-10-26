# src/gui/tabs/word_library.py
"""仅新增式词库管理标签页：追加新单元、向已有单元追加新单词。

数据直接读写 SQLite（src/db.py），无内存别名机制；保存后经 on_data_changed
通知主窗口重载词库并刷新单元选择。
"""
import sqlite3
from typing import Callable, List, Optional, Tuple

from PyQt5.QtWidgets import (QButtonGroup, QComboBox, QFormLayout, QGroupBox,
                             QHBoxLayout, QLabel, QLineEdit, QListWidget,
                             QPushButton, QRadioButton, QVBoxLayout, QWidget)

import src.db as db


class WordLibraryTab(QWidget):
    """词库管理标签页（仅新增）。"""

    def __init__(self, parent: Optional[QWidget] = None,
                 on_data_changed: Optional[Callable[[], None]] = None):
        super().__init__(parent)
        self.on_data_changed = on_data_changed  # 词库变更后的回调
        self.staging: List[Tuple[str, str]] = []  # 暂存：[(word, translation), ...]
        self._build_ui()

    def _build_ui(self):
        """设置词库管理界面"""
        layout = QVBoxLayout(self)

        # ── 添加目标 ──
        target_group = QGroupBox("添加目标")
        target_layout = QVBoxLayout(target_group)

        self.mode_group = QButtonGroup(self)
        self.new_unit_radio = QRadioButton("添加到新单元")
        self.existing_unit_radio = QRadioButton("添加到已有单元")
        self.new_unit_radio.setChecked(True)
        self.mode_group.addButton(self.new_unit_radio)
        self.mode_group.addButton(self.existing_unit_radio)

        target_layout.addWidget(self.new_unit_radio)
        self.new_unit_edit = QLineEdit()
        self.new_unit_edit.setPlaceholderText("输入新单元名称")
        new_row = QHBoxLayout()
        new_row.addSpacing(20)
        new_row.addWidget(self.new_unit_edit)
        target_layout.addLayout(new_row)

        target_layout.addWidget(self.existing_unit_radio)
        self.existing_unit_combo = QComboBox()
        self.existing_unit_combo.addItems(db.get_unit_names())
        existing_row = QHBoxLayout()
        existing_row.addSpacing(20)
        existing_row.addWidget(self.existing_unit_combo)
        target_layout.addLayout(existing_row)

        layout.addWidget(target_group)

        # ── 单词输入 ──
        input_group = QGroupBox("添加单词")
        input_form = QFormLayout(input_group)

        self.word_edit = QLineEdit()
        self.word_edit.setPlaceholderText("英文单词")
        input_form.addRow("英文单词:", self.word_edit)

        self.translation_edit = QLineEdit()
        self.translation_edit.setPlaceholderText("中文释义")
        input_form.addRow("中文释义:", self.translation_edit)

        add_btn = QPushButton("添加到暂存")
        add_btn.clicked.connect(self._add_to_staging)
        input_form.addRow(add_btn)

        layout.addWidget(input_group)

        # ── 暂存列表 ──
        staging_group = QGroupBox("暂存单词")
        staging_layout = QVBoxLayout(staging_group)

        self.staging_list = QListWidget()
        staging_layout.addWidget(self.staging_list)

        btn_row = QHBoxLayout()
        remove_btn = QPushButton("移除暂存项")
        remove_btn.clicked.connect(self._remove_staging_item)
        btn_row.addWidget(remove_btn)

        save_btn = QPushButton("保存到词库")
        save_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }"
        )
        save_btn.clicked.connect(self._save_to_library)
        btn_row.addWidget(save_btn)

        btn_row.addStretch(1)
        staging_layout.addLayout(btn_row)

        layout.addWidget(staging_group)

        # ── 状态栏 ──
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: gray;")
        layout.addWidget(self.status_label)

    # ── 内部方法 ─────────────────────────────────────────────────────

    def _set_status(self, text: str, color: str):
        """更新状态提示（red=错误 / green=成功 / gray=中性）"""
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color};")

    def _add_to_staging(self):
        """将当前输入的单词添加到暂存列表"""
        word = self.word_edit.text().strip()
        translation = self.translation_edit.text().strip()

        if not word or not translation:
            self._set_status("⚠️ 英文单词和中文释义不能为空", "red")
            return

        # 检查暂存内是否重复
        for w, _ in self.staging:
            if w == word:
                self._set_status(f"⚠️ 暂存中已有单词 \"{word}\"", "red")
                return

        self.staging.append((word, translation))
        self.staging_list.addItem(f"{word} — {translation}")

        # 清空输入
        self.word_edit.clear()
        self.translation_edit.clear()
        self.word_edit.setFocus()

        self._set_status(f"已添加到暂存（共 {len(self.staging)} 项）", "gray")

    def _remove_staging_item(self):
        """移除选中的暂存项"""
        row = self.staging_list.currentRow()
        if row < 0:
            self._set_status("⚠️ 请先选择要移除的暂存项", "red")
            return

        self.staging.pop(row)
        self.staging_list.takeItem(row)
        self._set_status(f"已移除（剩余 {len(self.staging)} 项）", "gray")

    def _save_to_library(self):
        """将暂存单词保存到词库（写 SQLite）"""
        if not self.staging:
            self._set_status("⚠️ 暂存列表为空，请先添加单词", "red")
            return

        if self.new_unit_radio.isChecked():
            unit_name = self.new_unit_edit.text().strip()
            if not unit_name:
                self._set_status("⚠️ 请输入新单元名称", "red")
                return
            if not self._save_new_unit(unit_name):
                return
        else:
            unit_name = self.existing_unit_combo.currentText().strip()
            if not unit_name:
                self._set_status("⚠️ 请选择一个已有单元", "red")
                return
            if not self._save_existing_unit(unit_name):
                return

        self._after_save(unit_name)

    def _save_new_unit(self, unit_name: str) -> bool:
        """保存为新单元；失败时更新状态提示并返回 False。"""
        try:
            if db.unit_exists(unit_name):
                self._set_status(f"⚠️ 单元 \"{unit_name}\" 已存在，请选择「添加到已有单元」", "red")
                return False
            if not db.add_unit(unit_name, self.staging):
                self._set_status(f"⚠️ 单元 \"{unit_name}\" 已存在，请选择「添加到已有单元」", "red")
                return False
        except (sqlite3.IntegrityError, OSError):
            self._set_status("❌ 保存失败，请检查数据或文件权限", "red")
            return False
        return True

    def _save_existing_unit(self, unit_name: str) -> bool:
        """保存到已有单元；失败时更新状态提示并返回 False。"""
        try:
            # 一次性报出全部重复词（与旧版行为一致）
            existing = {w['word'] for w in db.get_unit_words(unit_name)}
            duplicates = [w for w, _ in self.staging if w in existing]
            if duplicates:
                dup_str = "、".join(duplicates)
                self._set_status(f"⚠️ 单元内已有重复单词: {dup_str}", "red")
                return False
            if not db.add_words(unit_name, self.staging):
                self._set_status("⚠️ 未找到该单元，请重新选择", "red")
                return False
        except (sqlite3.IntegrityError, OSError):
            self._set_status("❌ 保存失败，请检查数据或文件权限", "red")
            return False
        return True

    def _after_save(self, unit_name: str):
        """保存成功后的清理和通知"""
        # 清空暂存
        self.staging.clear()
        self.staging_list.clear()
        # 新单元模式清空名称输入
        if self.new_unit_radio.isChecked():
            self.new_unit_edit.clear()
        # 刷新已有单元下拉框
        self.existing_unit_combo.clear()
        self.existing_unit_combo.addItems(db.get_unit_names())
        # 通知主窗口
        if self.on_data_changed:
            self.on_data_changed()
        # 状态提示
        self._set_status(f"✅ 已保存到 \"{unit_name}\"", "green")
