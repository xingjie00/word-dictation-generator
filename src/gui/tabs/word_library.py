# src/gui/tabs/word_library.py
"""词库管理标签页：追加新单元、向已有单元追加新单词、批量导入、修改/删除已入库单词。

数据直接读写 SQLite（src/db.py），无内存别名机制；变更后经 on_data_changed
通知主窗口重载词库并刷新单元选择。
"""
import os
import re
import sqlite3
from typing import Callable, List, Optional, Tuple

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QAbstractItemView, QButtonGroup, QComboBox, QDialog,
                             QDialogButtonBox, QFileDialog, QFormLayout, QFrame,
                             QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton,
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


class _EditWordDialog(QDialog):
    """编辑已入库单词的模态对话框（英文 + 释义）。"""

    def __init__(self, word: str, translation: str,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("修改单词")
        form = QFormLayout(self)
        self.word_edit = QLineEdit(word)
        form.addRow("英文单词:", self.word_edit)
        self.translation_edit = QLineEdit(translation)
        form.addRow("中文释义:", self.translation_edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)


class WordLibraryTab(QWidget):
    """词库管理标签页。"""

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

        # ── 已入库单词 ──
        library_group = QGroupBox("已入库单词")
        library_layout = QVBoxLayout(library_group)

        unit_row = QHBoxLayout()
        unit_row.addWidget(QLabel("单元:"))
        self.library_unit_combo = QComboBox()
        self.library_unit_combo.addItems(db.get_unit_names())
        unit_row.addWidget(self.library_unit_combo, 1)
        library_layout.addLayout(unit_row)

        self.library_list = QListWidget()
        self.library_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection)
        library_layout.addWidget(self.library_list)

        lib_btn_row = QHBoxLayout()
        edit_btn = QPushButton("修改所选")
        edit_btn.clicked.connect(self._edit_library_word)
        lib_btn_row.addWidget(edit_btn)

        delete_btn = QPushButton("删除所选")
        delete_btn.clicked.connect(self._delete_library_words)
        lib_btn_row.addWidget(delete_btn)
        lib_btn_row.addStretch(1)
        library_layout.addLayout(lib_btn_row)

        self.library_unit_combo.currentTextChanged.connect(
            lambda _: self._reload_library_list())
        self._reload_library_list()

        layout.addWidget(library_group)

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
        # 刷新已入库单词区（单元下拉 + 单词列表）
        self._refresh_library_units()
        # 通知主窗口
        if self.on_data_changed:
            self.on_data_changed()
        # 状态提示
        self._set_status(f"✅ 已保存到 \"{unit_name}\"", "green")

    # ── 已入库单词的修改 / 删除 ─────────────────────────────────────

    def _reload_library_list(self):
        """重载已入库单词列表（当前选中单元）。"""
        self.library_list.clear()
        unit = self.library_unit_combo.currentText().strip()
        if not unit:
            return
        for w in db.get_unit_words(unit):
            item = QListWidgetItem(f"{w['word']} — {w['translation']}")
            # 英文/释义存入 item 数据；展示文本含分隔符，回读时不做文本解析
            item.setData(Qt.ItemDataRole.UserRole, w['word'])
            item.setData(Qt.ItemDataRole.UserRole + 1, w['translation'])
            self.library_list.addItem(item)

    def _refresh_library_units(self):
        """刷新已入库单元下拉框并重载单词列表（原选中单元仍存在则保持）。"""
        current = self.library_unit_combo.currentText()
        self.library_unit_combo.blockSignals(True)
        self.library_unit_combo.clear()
        self.library_unit_combo.addItems(db.get_unit_names())
        idx = self.library_unit_combo.findText(current)
        if idx >= 0:
            self.library_unit_combo.setCurrentIndex(idx)
        self.library_unit_combo.blockSignals(False)
        self._reload_library_list()

    def _edit_library_word(self):
        """修改选中的一条已入库单词（编辑对话框 → db.update_word）。"""
        unit = self.library_unit_combo.currentText().strip()
        if not unit:
            self._set_status("⚠️ 请先选择单元", "red")
            return
        selected = self.library_list.selectedItems()
        if len(selected) != 1:
            self._set_status("⚠️ 请先选中一条（且仅一条）要修改的单词", "red")
            return
        item = selected[0]
        old_word = item.data(Qt.ItemDataRole.UserRole)
        old_translation = item.data(Qt.ItemDataRole.UserRole + 1)

        dlg = _EditWordDialog(old_word, old_translation, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        new_word = dlg.word_edit.text().strip()
        new_translation = dlg.translation_edit.text().strip()
        if not new_word or not new_translation:
            self._set_status("⚠️ 英文单词和中文释义不能为空", "red")
            return
        if new_word == old_word and new_translation == old_translation:
            self._set_status("未做修改", "gray")
            return
        # 同单元内新单词名重复预检（与保存流程一致，UNIQUE 约束为兜底）
        if new_word != old_word and new_word in {
                w['word'] for w in db.get_unit_words(unit)}:
            self._set_status(f"⚠️ 单元内已有重复单词: {new_word}", "red")
            return
        try:
            ok = db.update_word(unit, old_word, new_word, new_translation)
        except (sqlite3.IntegrityError, OSError):
            self._set_status("❌ 修改失败，请检查数据或文件权限", "red")
            return
        if not ok:
            self._set_status("⚠️ 该记录不存在，列表已刷新", "red")
        else:
            if self.on_data_changed:
                self.on_data_changed()
            self._set_status("✅ 已更新 1 条", "green")
        self._reload_library_list()

    def _delete_library_words(self):
        """删除选中的一条或多条已入库单词（确认框 → 逐条 db.delete_word）。"""
        unit = self.library_unit_combo.currentText().strip()
        if not unit:
            self._set_status("⚠️ 请先选择单元", "red")
            return
        selected = self.library_list.selectedItems()
        if not selected:
            self._set_status("⚠️ 请先选择要删除的单词", "red")
            return
        words = [it.data(Qt.ItemDataRole.UserRole) for it in selected]
        ret = QMessageBox.question(
            self, "删除确认",
            f"确定从单元 \"{unit}\" 删除选中的 {len(words)} 个单词？\n该操作不可恢复。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if ret != QMessageBox.StandardButton.Yes:
            return

        deleted = 0
        try:
            for w in words:
                if db.delete_word(unit, w):
                    deleted += 1
        except (sqlite3.IntegrityError, OSError):
            self._set_status("❌ 删除失败，请检查数据或文件权限", "red")
            self._reload_library_list()
            return
        self._reload_library_list()
        if self.on_data_changed:
            self.on_data_changed()
        if deleted == len(words):
            self._set_status(f"✅ 已删除 {deleted} 条", "green")
        else:
            self._set_status(f"⚠️ 已删除 {deleted}/{len(words)} 条（其余记录不存在）", "gray")
