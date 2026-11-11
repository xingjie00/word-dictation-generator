# src/gui/tabs/unit_selection.py
from typing import List, Optional

from PyQt6.QtWidgets import (QAbstractItemView, QComboBox, QGroupBox, QHBoxLayout,
                             QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget)


class UnitSelectionTab(QWidget):
    def __init__(self, parent: Optional[QWidget] = None, units: Optional[List[str]] = None):
        super().__init__(parent)
        self.units = units or []
        self._build_ui()

    def _build_ui(self):
        """设置单元选择界面"""
        layout = QVBoxLayout(self)

        # 重点单元选择（标题染橙色 accent，见 main.py 集中样式表）
        focus_group = QGroupBox("选择重点单元")
        focus_group.setProperty("accent", "focus")
        focus_layout = QVBoxLayout(focus_group)

        self.focus_combo = QComboBox()  # 默认不可编辑 = readonly 语义
        self.focus_combo.addItems(["无"] + self.units)
        self.focus_combo.setCurrentIndex(0)  # 默认选择"无"
        focus_layout.addWidget(self.focus_combo)

        layout.addWidget(focus_group)

        # 复习单元选择（标题染蓝色 accent；与重点组同款边框，仅标题色区分）
        review_group = QGroupBox("选择复习单元")
        review_group.setProperty("accent", "review")
        review_layout = QVBoxLayout(review_group)

        self.review_list = QListWidget()
        self.review_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        for unit in self.units:
            self.review_list.addItem(unit)
        review_layout.addWidget(self.review_list)

        # 词库为空时的占位引导（与列表互斥显示）
        self.review_empty_label = QLabel("词库为空，请先到「词库管理」导入单词")
        self.review_empty_label.setWordWrap(True)
        self.review_empty_label.setProperty("status", "muted")
        review_layout.addWidget(self.review_empty_label)

        # 按钮行
        btn_row = QHBoxLayout()
        select_all_btn = QPushButton("全选")
        select_all_btn.setToolTip("选中列表中的全部单元")
        select_all_btn.clicked.connect(self.select_all_review_units)
        btn_row.addWidget(select_all_btn)

        clear_btn = QPushButton("清空")
        clear_btn.setToolTip("清空已选复习单元")
        clear_btn.clicked.connect(self.clear_review_units)
        btn_row.addWidget(clear_btn)

        btn_row.addStretch(1)

        # 已选计数：多选列表只靠行首细条标记选中态，行数多时无法一眼数清
        self.review_count_label = QLabel("已选 0 个单元")
        self.review_count_label.setProperty("status", "muted")
        btn_row.addWidget(self.review_count_label)
        self.review_list.itemSelectionChanged.connect(self._update_review_count)
        review_layout.addLayout(btn_row)

        layout.addWidget(review_group)
        self._update_empty_state()

    # ── 内部状态 ─────────────────────────────────────────────────────

    def _update_review_count(self):
        """同步「已选 N 个单元」计数"""
        self.review_count_label.setText(f"已选 {len(self.get_review_units())} 个单元")

    def _update_empty_state(self):
        """词库为空时以引导文字替代空白列表"""
        empty = not self.units
        self.review_list.setVisible(not empty)
        self.review_empty_label.setVisible(empty)

    # ── 对外接口 ─────────────────────────────────────────────────────

    def get_focus_unit(self) -> str:
        """当前重点单元（"无" 或单元名）"""
        return self.focus_combo.currentText()

    def get_review_units(self) -> List[str]:
        """选中的复习单元（按行序，selectedItems 按点击顺序返回会破坏确定性）"""
        return [self.review_list.item(i).text()
                for i in range(self.review_list.count())
                if self.review_list.item(i).isSelected()]

    def select_all_review_units(self):
        """选择所有复习单元"""
        self.review_list.selectAll()

    def clear_review_units(self):
        """清空复习单元选择"""
        self.review_list.clearSelection()

    def refresh_units(self, units: List[str]):
        """刷新单元列表（词库变更后调用）。

        保留仍有效的当前重点选择；复习选择会被清空（与旧版行为对齐）。
        """
        self.units = units
        # 重点单元下拉框
        current_focus = self.focus_combo.currentText()
        self.focus_combo.clear()
        self.focus_combo.addItems(["无"] + self.units)
        idx = self.focus_combo.findText(current_focus)
        self.focus_combo.setCurrentIndex(idx if idx >= 0 else 0)  # "无" 恒在 0
        # 复习单元列表
        self.review_list.clear()
        for unit in self.units:
            self.review_list.addItem(unit)
        self._update_empty_state()
        self._update_review_count()
