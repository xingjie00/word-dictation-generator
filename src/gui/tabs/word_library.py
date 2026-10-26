# src/gui/tabs/word_library.py
"""仅新增式词库管理标签页：追加新单元、向已有单元追加新单词、批量导入。

数据直接读写 SQLite（src/db.py），无内存别名机制；保存后经 on_data_changed
通知主窗口重载词库并刷新单元选择。
"""
import os
import re
import sqlite3
from typing import Callable, List, Optional, Tuple

from PyQt6.QtWidgets import (QButtonGroup, QComboBox, QFileDialog, QFormLayout,
                             QFrame, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                             QListWidget, QPlainTextEdit, QPushButton,
                             QRadioButton, QScrollArea, QVBoxLayout, QWidget)

import src.db as db

# 批量导入的行分隔符：空格 / Tab / 中英文逗号 / 中英文分号
_BATCH_SEP_RE = re.compile(r'[\s,，;；]+')


def parse_batch_text(text: str) -> Tuple[List[Tuple[str, str]], List[Tuple[int, str]]]:
    """解析批量导入文本：每行一个单词，格式「英文 释义」（分隔符见 _BATCH_SEP_RE）。

    释义中允许继续含空格/标点（如 "apple n. 苹果" → 释义为 "n. 苹果"）。
    批内英文单词重复时保留首个，后续行计入错误。

    Returns:
        (entries, errors)：entries 为 [(word, translation), ...]；
        errors 为 [(行号, 原因), ...]（行号从 1 计）。
    """
    entries: List[Tuple[str, str]] = []
    errors: List[Tuple[int, str]] = []
    seen = set()
    for line_no, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        parts = _BATCH_SEP_RE.split(line, maxsplit=1)
        if len(parts) < 2 or not parts[1].strip():
            errors.append((line_no, '缺少释义'))
            continue
        word = parts[0].strip()
        translation = ' '.join(parts[1].split())  # 规整释义内空白
        if word in seen:
            errors.append((line_no, f'批内重复: {word}'))
            continue
        seen.add(word)
        entries.append((word, translation))
    return entries, errors


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
        # 内容较多（单个添加 + 批量导入 + 暂存列表），用滚动区承载防止溢出
        outer = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)

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

        # ── 批量导入 ──
        batch_group = QGroupBox("批量导入")
        batch_layout = QVBoxLayout(batch_group)

        batch_hint = QLabel("每行一个单词，格式「英文 释义」（空格 / Tab / 逗号分隔），"
                            "解析后进入下方暂存列表，保存时统一校验")
        batch_hint.setWordWrap(True)
        batch_layout.addWidget(batch_hint)

        self.batch_edit = QPlainTextEdit()
        self.batch_edit.setPlaceholderText("apple 苹果\nbook\t书\ncat,猫")
        self.batch_edit.setMaximumHeight(110)
        batch_layout.addWidget(self.batch_edit)

        batch_btn_row = QHBoxLayout()
        from_file_btn = QPushButton("从文件导入…")
        from_file_btn.clicked.connect(self._import_from_file)
        batch_btn_row.addWidget(from_file_btn)

        parse_btn = QPushButton("解析加入暂存")
        parse_btn.clicked.connect(self._parse_batch)
        batch_btn_row.addWidget(parse_btn)
        batch_btn_row.addStretch(1)
        batch_layout.addLayout(batch_btn_row)

        layout.addWidget(batch_group)

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

        layout.addStretch(1)
        scroll.setWidget(inner)
        outer.addWidget(scroll)

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

    def _import_from_file(self):
        """从 .txt 文件载入词表文本到批量导入输入框"""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择词表文件", "", "文本文件 (*.txt);;所有文件 (*)")
        if not path:
            return
        try:
            with open(path, 'r', encoding='utf-8') as f:
                text = f.read()
        except UnicodeDecodeError:
            # 常见：Windows 记事本保存的 GBK 词表
            try:
                with open(path, 'r', encoding='gbk', errors='replace') as f:
                    text = f.read()
            except OSError as e:
                self._set_status(f"❌ 读取文件失败: {e}", "red")
                return
        except OSError as e:
            self._set_status(f"❌ 读取文件失败: {e}", "red")
            return
        self.batch_edit.setPlainText(text)
        self._set_status(f"已载入 {os.path.basename(path)}，点击「解析加入暂存」", "gray")

    def _parse_batch(self):
        """解析批量导入文本，把结果加入暂存列表"""
        text = self.batch_edit.toPlainText()
        if not text.strip():
            self._set_status("⚠️ 请先粘贴或从文件导入词表文本", "red")
            return

        entries, errors = parse_batch_text(text)

        # 跳过暂存中已有的单词
        existing = {w for w, _ in self.staging}
        added, dup_in_staging = 0, 0
        for word, translation in entries:
            if word in existing:
                dup_in_staging += 1
                continue
            existing.add(word)
            self.staging.append((word, translation))
            self.staging_list.addItem(f"{word} — {translation}")
            added += 1

        # 组装结果提示
        parts = [f"✅ 解析加入暂存 {added} 条"]
        skipped = []
        if errors:
            nos = "、".join(str(n) for n, _ in errors[:10])
            if len(errors) > 10:
                nos += "…"
            reasons = "、".join(sorted({r for _, r in errors}))
            skipped.append(f"格式问题 {len(errors)} 行（第 {nos} 行：{reasons}）")
        if dup_in_staging:
            skipped.append(f"暂存已有 {dup_in_staging} 条被跳过")
        if skipped:
            self._set_status("；".join(parts + skipped), "gray")
        else:
            self._set_status("；".join(parts), "green")

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
