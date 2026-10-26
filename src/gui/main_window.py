# src/gui/main_window.py
import os
import sqlite3
import tempfile
import urllib.request
import webbrowser

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (QApplication, QFileDialog, QHBoxLayout, QLabel,
                             QMainWindow, QMessageBox, QPushButton, QProgressBar,
                             QTabWidget, QVBoxLayout, QWidget)

import src.db as db
from src.data_loader import load_config, save_config
from src.word_selector import select_words, SelectionError
from src.html_generator import build_full_document
from src.gui.tabs.unit_selection import UnitSelectionTab
from src.gui.tabs.settings import SettingsTab
from src.gui.tabs.word_library import WordLibraryTab


class WordDictationGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self._last_temp_html = None

        # 初始化词库数据库（首次运行从 words.json 种子导入）
        try:
            quarantine = db.init_db()
        except (RuntimeError, sqlite3.Error) as e:
            QMessageBox.critical(None, "词库初始化失败", str(e))
            raise SystemExit(1)
        if quarantine:
            QMessageBox.warning(
                None, "词库已重置",
                f"检测到词库数据库损坏，原文件已备份为：\n{quarantine}\n\n"
                f"词库已从 words.json 种子重新导入。"
            )

        self.data = db.load_word_data()
        self.units = self.data['units']

        self._build_ui()

    def _build_ui(self):
        """设置用户界面"""
        self.setWindowTitle("单词听写生成器 v3.0")
        self.resize(700, 650)
        self.setMinimumSize(640, 560)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 标题
        title = QLabel("单词听写生成器 v3.0")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # 标签页
        self.tabs = QTabWidget()
        self.unit_tab = UnitSelectionTab(self.tabs, self.units)
        self.settings_tab = SettingsTab(self.tabs, self.config)
        self.library_tab = WordLibraryTab(self.tabs, on_data_changed=self.on_word_data_changed)
        self.tabs.addTab(self.unit_tab, "选择单元")
        self.tabs.addTab(self.settings_tab, "设置参数")
        self.tabs.addTab(self.library_tab, "词库管理")
        layout.addWidget(self.tabs)

        # 按钮区域
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)

        self.generate_btn = QPushButton("生成HTML听写文档")
        self.generate_btn.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white;"
            " font-weight: bold; padding: 8px 20px; }"
        )
        self.generate_btn.clicked.connect(self.generate_document)
        btn_row.addWidget(self.generate_btn)

        self.preview_btn = QPushButton("预览")
        self.preview_btn.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white;"
            " font-weight: bold; padding: 8px 20px; }"
        )
        self.preview_btn.clicked.connect(self.preview_document)
        btn_row.addWidget(self.preview_btn)

        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # 进度条
        self.progress = QProgressBar()
        layout.addWidget(self.progress)

        # 状态栏（QMainWindow 自带）
        self.statusBar().showMessage("就绪")

    def on_word_data_changed(self):
        """词库变更后的回调：从数据库重载并刷新单元选择列表"""
        self.data = db.load_word_data()
        self.units = self.data['units']
        self.unit_tab.refresh_units(self.units)

    def save_current_config(self):
        """保存当前配置到文件"""
        config = {
            'focus_count': self.settings_tab.focus_count(),
            'total_count': self.settings_tab.total_count(),
            'days': self.settings_tab.days(),
            'filename': self.settings_tab.filename()
        }
        save_config(config)

    def _build_day_plans(self):
        """构建每日单词计划（generate 与 preview 共用）。

        Returns:
            (day_plans, focus_count, total_count, review_count, days, focus_units, review_units)

        Raises:
            SelectionError: 参数无效或单词不足时抛出。
        """
        # 读取单元选择
        focus_unit = self.unit_tab.get_focus_unit()
        focus_units = [] if focus_unit == "无" else [focus_unit]

        review_units = self.unit_tab.get_review_units()

        # 排除重点单元出现在复习列表中（保留原有行为，留在调用方保持 selector 纯净）
        if focus_units:
            review_units = [unit for unit in review_units if unit != focus_units[0]]

        # QSpinBox 恒返回合法范围内的 int，无需字符串解析与钳制
        focus_count = self.settings_tab.focus_count()
        total_count = self.settings_tab.total_count()
        days = self.settings_tab.days()

        # 兜底校验（正常情况下 spinbox 范围与动态上限已保证）
        if focus_count < 0 or focus_count > total_count:
            raise SelectionError(f"重点单词数量必须在 0-{total_count} 之间！")

        review_count = total_count - focus_count

        # 单元必选：focus_count>0 时才要求重点单元，review_count>0 时才要求复习单元
        if focus_count > 0 and not focus_units:
            raise SelectionError("请选择一个重点单元（重点单词数 > 0）！")
        if review_count > 0 and not review_units:
            raise SelectionError("请至少选择一个复习单元（复习单词数 > 0）！")

        # 调用纯选择逻辑
        day_plans = select_words(
            self.data, focus_units, review_units,
            focus_count, review_count, days
        )

        return day_plans, focus_count, total_count, review_count, days, focus_units, review_units

    def _update_progress(self, cur, total):
        """进度回调"""
        self.progress.setValue(int(cur / total * 100))
        QApplication.processEvents()

    def generate_document(self):
        """生成HTML文档"""
        # processEvents 会派发输入事件（可重入），生成期间禁用按钮
        self.generate_btn.setEnabled(False)
        self.preview_btn.setEnabled(False)
        try:
            try:
                day_plans, focus_count, total_count, review_count, days, focus_units, review_units = \
                    self._build_day_plans()
            except SelectionError as e:
                QMessageBox.warning(self, "无法生成", str(e))
                return

            # 保存当前配置
            self.save_current_config()

            self.statusBar().showMessage("正在生成HTML文档...")
            self.progress.setValue(0)
            QApplication.processEvents()

            try:
                html = build_full_document(
                    day_plans, total_count, focus_count, review_count,
                    on_progress=self._update_progress
                )

                filename = f"{self.settings_tab.filename()}{days}天.html"
                # 返回 (path, filter) 元组；取消时 path 为空串
                path, _ = QFileDialog.getSaveFileName(
                    self, "保存文档", filename,
                    "HTML文档 (*.html);;所有文件 (*)"
                )

                if path:
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(html)

                    self.progress.setValue(0)
                    self.statusBar().showMessage(f"HTML文档已保存: {os.path.basename(path)}")

                    QMessageBox.information(
                        self, "成功",
                        f"HTML听写文档生成成功！\n\n"
                        f"文件: {os.path.basename(path)}\n"
                        f"天数: {days}天\n"
                        f"总单词数: {total_count}个/天\n"
                        f"重点单元: {focus_units[0] if focus_units else '无'}\n"
                        f"复习单元: {len(review_units)}个\n"
                        f"每天: {focus_count}个重点单词 + {review_count}个复习单词\n\n"
                        f"提示：\n"
                        f"• 可以用浏览器打开查看\n"
                        f"• 推荐使用Ctrl+P打印\n"
                        f"• 打印设置选择A4纸张"
                    )
                else:
                    self.progress.setValue(0)
                    self.statusBar().showMessage("用户取消了保存")

            except Exception as e:
                self.progress.setValue(0)
                self.statusBar().showMessage("生成失败")
                QMessageBox.critical(self, "错误", f"生成HTML文档时出错: {str(e)}")
        finally:
            self.generate_btn.setEnabled(True)
            self.preview_btn.setEnabled(True)

    def preview_document(self):
        """预览HTML文档（生成到临时文件并用浏览器打开，不保存）"""
        self.generate_btn.setEnabled(False)
        self.preview_btn.setEnabled(False)
        try:
            try:
                day_plans, focus_count, total_count, review_count, days, focus_units, review_units = \
                    self._build_day_plans()
            except SelectionError as e:
                QMessageBox.warning(self, "无法预览", str(e))
                return

            self.statusBar().showMessage("正在生成预览...")
            QApplication.processEvents()

            try:
                html = build_full_document(day_plans, total_count, focus_count, review_count)

                # 写入临时文件
                with tempfile.NamedTemporaryFile(
                    suffix='.html', delete=False, mode='w', encoding='utf-8'
                ) as f:
                    f.write(html)
                    path = f.name

                # 清理上一次的临时文件
                if self._last_temp_html and os.path.exists(self._last_temp_html):
                    try:
                        os.unlink(self._last_temp_html)
                    except OSError:
                        pass
                self._last_temp_html = path

                # 用默认浏览器打开
                webbrowser.open('file:' + urllib.request.pathname2url(path))
                self.statusBar().showMessage("已打开预览")

            except Exception as e:
                self.statusBar().showMessage("预览失败")
                QMessageBox.critical(self, "错误", f"预览HTML文档时出错: {str(e)}")
        finally:
            self.generate_btn.setEnabled(True)
            self.preview_btn.setEnabled(True)

    def closeEvent(self, event):
        """窗口关闭时保存配置并清理临时文件"""
        self.save_current_config()
        # 清理预览临时文件
        if self._last_temp_html and os.path.exists(self._last_temp_html):
            try:
                os.unlink(self._last_temp_html)
            except OSError:
                pass
        event.accept()
