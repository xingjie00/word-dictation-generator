# src/gui/main_window.py
import os
import sqlite3
import tempfile
import urllib.request
import webbrowser
from typing import List, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QKeySequence, QShortcut
from PyQt6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel,
                             QMainWindow, QMessageBox, QPushButton, QProgressBar,
                             QTabWidget, QVBoxLayout, QWidget)

import src.db as db
from src.data_loader import load_config, save_config
from src.word_selector import select_words, SelectionError, DayPlan
from src.html_generator import build_full_document
from src.version import __version__
from src.gui.tabs.unit_selection import UnitSelectionTab
from src.gui.tabs.settings import SettingsTab
from src.gui.tabs.word_library import WordLibraryTab


def write_document_and_record(path: str, html: str, day_plans: List[DayPlan],
                              db_path: Optional[str] = None) -> None:
    """将 HTML 文档写盘；写盘成功后写回入选词的抽查次数。

    写盘抛异常时不写回，保证计数与实际产出的文档一致。同一词在文档中
    出现多次（跨天、或同一天既作重点又作复习）按出现次数累加。
    预览（临时文件）不走此路径，不计数。

    Args:
        path: 目标文件路径。
        html: 完整 HTML 文档字符串。
        day_plans: select_words 返回的 DayPlan 列表。
        db_path: 数据库路径；None 用默认（测试时可注入）。
    """
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)
    word_ids = [
        entry.id
        for plan in day_plans
        for entry in plan.focus_words + plan.review_words
    ]
    db.increment_dictation_counts(word_ids, db_path=db_path)


class GenerateWorker(QThread):
    """后台线程：调用 build_full_document 构建完整 HTML，不触碰任何 UI 对象。

    进度经 progress 信号回主线程；跨线程信号自动 queued 连接，
    主线程事件循环保持完整运行（不再依赖 processEvents）。
    """

    progress = pyqtSignal(int, int)   # (current_day, total_days)
    done = pyqtSignal(str)            # 完整 HTML 文档字符串
    failed = pyqtSignal(str)          # 错误消息

    def __init__(self, day_plans, total_count, focus_count, review_count,
                 parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._args = (day_plans, total_count, focus_count, review_count)

    def run(self):
        try:
            html = build_full_document(
                *self._args,
                on_progress=lambda cur, total: self.progress.emit(cur, total))
            self.done.emit(html)
        except Exception as e:
            self.failed.emit(str(e))


class WordDictationGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self._last_temp_html = None
        self._worker = None      # 当前 GenerateWorker（运行中）或 None
        self._closing = False    # closeEvent 已触发；晚到的回调须直接返回

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
        self.setWindowTitle(f"单词听写生成器 v{__version__}")
        self.resize(700, 650)
        self.setMinimumSize(640, 560)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # 标题
        title = QLabel(f"单词听写生成器 v{__version__}")
        title.setFont(QFont("Microsoft YaHei", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        self.generate_btn.setProperty("role", "primary")
        self.generate_btn.setToolTip("按当前选择生成听写文档并保存（Ctrl+G）")
        self.generate_btn.clicked.connect(self.generate_document)
        btn_row.addWidget(self.generate_btn)

        self.preview_btn = QPushButton("预览")
        self.preview_btn.setProperty("role", "info")
        self.preview_btn.setToolTip("在浏览器中预览，不保存、不计数（Ctrl+P）")
        self.preview_btn.clicked.connect(self.preview_document)
        btn_row.addWidget(self.preview_btn)

        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # 全局快捷键（Qt6 中 QShortcut 已移至 QtGui）
        gen_shortcut = QShortcut(QKeySequence("Ctrl+G"), self)
        gen_shortcut.activated.connect(self.generate_document)
        preview_shortcut = QShortcut(QKeySequence("Ctrl+P"), self)
        preview_shortcut.activated.connect(self.preview_document)

        # 进度条：默认隐藏（空闲时常驻 0% 读起来像分隔线），生成期间显示
        self.progress = QProgressBar()
        self.progress.hide()
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

    def _set_busy(self, busy: bool):
        """生成/预览进行中禁用两个全局动作按钮"""
        self.generate_btn.setEnabled(not busy)
        self.preview_btn.setEnabled(not busy)

    def _start_worker(self, day_plans, total_count, focus_count, review_count,
                      on_done, on_failed):
        """启动后台生成线程。

        worker 以 self 为父对象：防 GC，也保证窗口销毁时线程对象被一并清理；
        引用在 finished 槽释放（run() 返回后置 None 是安全的）。
        """
        worker = GenerateWorker(day_plans, total_count, focus_count, review_count,
                                parent=self)
        self._worker = worker
        worker.progress.connect(self._on_generate_progress)
        worker.done.connect(on_done)
        worker.failed.connect(on_failed)
        worker.finished.connect(self._on_worker_finished)
        worker.start()

    def _on_generate_progress(self, cur, total):
        self.progress.setValue(int(cur / total * 100))

    def _on_worker_finished(self):
        """run() 已返回；释放引用并让事件循环稍后销毁对象"""
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    def generate_document(self):
        """生成HTML文档：先取保存路径（取消则不生成），后台生成，完成后写盘计数"""
        if self._worker is not None:   # 上一次生成尚未结束，忽略重入
            return
        try:
            day_plans, focus_count, total_count, review_count, days, focus_units, review_units = \
                self._build_day_plans()
        except SelectionError as e:
            QMessageBox.warning(self, "无法生成", str(e))
            return

        # 保存当前配置
        self.save_current_config()

        filename = f"{self.settings_tab.filename()}{days}天.html"
        # 先取路径再生成：取消时不白做生成工作（返回 (path, filter)；取消时 path 为空串）
        path, _ = QFileDialog.getSaveFileName(
            self, "保存文档", filename,
            "HTML文档 (*.html);;所有文件 (*)"
        )
        if not path:
            self.statusBar().showMessage("用户取消了保存")
            return

        self.statusBar().showMessage("正在生成HTML文档...")
        self.progress.setValue(0)
        self.progress.show()
        self._set_busy(True)
        summary = (days, total_count, focus_count, review_count, focus_units, review_units)
        self._start_worker(
            day_plans, total_count, focus_count, review_count,
            on_done=lambda html: self._on_generate_done(path, html, day_plans, summary),
            on_failed=self._on_generate_failed)

    def _on_generate_done(self, path, html, day_plans, summary):
        """后台生成完成（主线程）：写盘 → 计数 → 成功反馈"""
        if self._closing:
            return
        days, total_count, focus_count, review_count, focus_units, review_units = summary
        try:
            # 写盘成功后写回入选词的抽查次数（失败不计数）
            write_document_and_record(path, html, day_plans)

            self.progress.setValue(0)
            self.progress.hide()
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
                f"提示：用浏览器打开查看，Ctrl+P 打印（选 A4 纸张）。"
            )
        except Exception as e:
            self.progress.setValue(0)
            self.progress.hide()
            self.statusBar().showMessage("生成失败")
            QMessageBox.critical(self, "错误", f"生成HTML文档时出错: {str(e)}")
        finally:
            self._set_busy(False)

    def _on_generate_failed(self, msg):
        if self._closing:
            return
        self.progress.setValue(0)
        self.progress.hide()
        self.statusBar().showMessage("生成失败")
        QMessageBox.critical(self, "错误", f"生成HTML文档时出错: {msg}")
        self._set_busy(False)

    def preview_document(self):
        """预览HTML文档（后台生成 → 临时文件 → 浏览器打开，不保存、不计数）"""
        if self._worker is not None:
            return
        try:
            day_plans, focus_count, total_count, review_count, days, focus_units, review_units = \
                self._build_day_plans()
        except SelectionError as e:
            QMessageBox.warning(self, "无法预览", str(e))
            return

        self.statusBar().showMessage("正在生成预览...")
        self._set_busy(True)
        self._start_worker(
            day_plans, total_count, focus_count, review_count,
            on_done=self._on_preview_done,
            on_failed=self._on_preview_failed)

    def _on_preview_done(self, html):
        if self._closing:
            return
        try:
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
            self._set_busy(False)

    def _on_preview_failed(self, msg):
        if self._closing:
            return
        self.statusBar().showMessage("预览失败")
        QMessageBox.critical(self, "错误", f"预览HTML文档时出错: {msg}")
        self._set_busy(False)

    def closeEvent(self, event):
        """窗口关闭时等待后台生成结束、保存配置并清理临时文件"""
        self._closing = True   # 晚到的 done/failed 回调直接返回，不对已关闭窗口弹框
        if self._worker is not None and self._worker.isRunning():
            # 生成耗时 <1s，同步等待安全；blockSignals 丢弃后续信号避免退出竞态
            self._worker.blockSignals(True)
            self._worker.wait()
            self._worker = None
        self.save_current_config()
        # 清理预览临时文件
        if self._last_temp_html and os.path.exists(self._last_temp_html):
            try:
                os.unlink(self._last_temp_html)
            except OSError:
                pass
        event.accept()
