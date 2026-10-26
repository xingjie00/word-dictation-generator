# src/gui/main_window.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import tempfile
import urllib.request
import webbrowser

from src.data_loader import load_word_data, load_config, save_config
from src.word_selector import select_words, SelectionError, DayPlan
from src.html_generator import build_full_document
from src.gui.tabs.unit_selection import UnitSelectionTab
from src.gui.tabs.settings import SettingsTab
from src.gui.tabs.word_library import WordLibraryTab


class WordDictationGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("单词听写生成器 v2.0")
        self.root.geometry("700x650")

        # 窗口关闭时保存配置
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 加载配置
        self.config = load_config()

        # 加载数据
        try:
            self.data = load_word_data()
            self.units = self.data['units']
        except Exception as e:
            messagebox.showerror("错误", f"加载单词数据失败: {e}")
            self.root.destroy()
            return

        self._last_temp_html = None

        self.setup_ui()

    def setup_ui(self):
        """设置用户界面"""
        # 标题
        title_label = tk.Label(self.root, text="单词听写生成器 v2.0",
                               font=("Microsoft YaHei", 16, "bold"))
        title_label.pack(pady=10)

        # 创建Notebook（标签页）
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill='both', expand=True, padx=10, pady=5)

        # 初始化标签页
        self.unit_tab = UnitSelectionTab(self.notebook, self.units)
        self.settings_tab = SettingsTab(self.notebook, self.config)
        self.library_tab = WordLibraryTab(
            self.notebook, self.data,
            on_data_changed=self.on_word_data_changed
        )

        # 添加标签页
        self.notebook.add(self.unit_tab.frame, text="选择单元")
        self.notebook.add(self.settings_tab.frame, text="设置参数")
        self.notebook.add(self.library_tab.frame, text="词库管理")

        # 按钮区域
        btn_frame = tk.Frame(self.root)
        btn_frame.pack(pady=10)

        generate_btn = tk.Button(btn_frame, text="生成HTML听写文档",
                                 command=self.generate_document,
                                 bg="#4CAF50", fg="white",
                                 font=("Microsoft YaHei", 12, "bold"),
                                 padx=20, pady=10)
        generate_btn.pack(side=tk.LEFT, padx=10)

        preview_btn = tk.Button(btn_frame, text="预览",
                                command=self.preview_document,
                                bg="#2196F3", fg="white",
                                font=("Microsoft YaHei", 12, "bold"),
                                padx=20, pady=10)
        preview_btn.pack(side=tk.LEFT, padx=10)

        # 进度条
        self.progress = ttk.Progressbar(self.root, mode='determinate', maximum=100)
        self.progress.pack(fill='x', padx=10, pady=2)

        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_bar = tk.Label(self.root, textvariable=self.status_var,
                              bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def on_word_data_changed(self):
        """词库变更后的回调：刷新单元选择列表"""
        self.units = self.data['units']
        self.unit_tab.refresh_units(self.units)

    def save_current_config(self):
        """保存当前配置到文件"""
        config = {
            'focus_count': int(self.settings_tab.focus_count_var.get()),
            'total_count': int(self.settings_tab.total_count_var.get()),
            'days': int(self.settings_tab.days_var.get()),
            'filename': self.settings_tab.filename_var.get()
        }
        save_config(config)

    def _build_day_plans(self):
        """构建每日单词计划（generate 与 preview 共用）。

        Returns:
            (day_plans, focus_count, total_count, review_count, days, focus_units, review_units)

        Raises:
            SelectionError: 参数无效或单词不足时抛出。
        """
        # 先清理 spinbox 半输文本
        self.settings_tab.update_word_counts()
        self.settings_tab.update_days()

        # 读取单元选择
        focus_unit = self.unit_tab.focus_var.get()
        focus_units = [] if focus_unit == "无" else [focus_unit]

        review_indices = self.unit_tab.review_listbox.curselection()
        review_units = [self.unit_tab.review_listbox.get(i) for i in review_indices]

        # 排除重点单元出现在复习列表中（保留原有行为，留在调用方保持 selector 纯净）
        if focus_units:
            review_units = [unit for unit in review_units if unit != focus_units[0]]

        # 解析参数
        try:
            focus_count = int(self.settings_tab.focus_count_var.get())
            total_count = int(self.settings_tab.total_count_var.get())
            days = int(self.settings_tab.days_var.get())
        except ValueError:
            raise SelectionError("请输入有效的数字！")

        if focus_count < 0 or focus_count > total_count:
            raise SelectionError(f"重点单词数量必须在 0-{total_count} 之间！")

        review_count = total_count - focus_count

        # 放宽单元必选：focus_count>0 时才要求重点单元，review_count>0 时才要求复习单元
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
        self.progress['value'] = cur / total * 100
        self.root.update_idletasks()

    def generate_document(self):
        """生成HTML文档"""
        try:
            day_plans, focus_count, total_count, review_count, days, focus_units, review_units = \
                self._build_day_plans()
        except SelectionError as e:
            messagebox.showwarning("无法生成", str(e))
            return

        # 保存当前配置
        self.save_current_config()

        # 更新状态
        self.status_var.set("正在生成HTML文档...")
        self.progress['value'] = 0
        self.root.update_idletasks()

        try:
            html = build_full_document(
                day_plans, total_count, focus_count, review_count,
                on_progress=self._update_progress
            )

            # 保存文档
            filename = f"{self.settings_tab.filename_var.get()}{days}天.html"
            filepath = filedialog.asksaveasfilename(
                defaultextension=".html",
                initialfile=filename,
                filetypes=[("HTML文档", "*.html"), ("所有文件", "*.*")]
            )

            if filepath:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(html)

                self.progress['value'] = 0
                self.status_var.set(f"HTML文档已保存: {os.path.basename(filepath)}")

                # 显示成功消息
                messagebox.showinfo("成功",
                                    f"HTML听写文档生成成功！\n\n"
                                    f"文件: {os.path.basename(filepath)}\n"
                                    f"天数: {days}天\n"
                                    f"总单词数: {total_count}个/天\n"
                                    f"重点单元: {focus_units[0] if focus_units else '无'}\n"
                                    f"复习单元: {len(review_units)}个\n"
                                    f"每天: {focus_count}个重点单词 + {review_count}个复习单词\n\n"
                                    f"提示：\n"
                                    f"• 可以用浏览器打开查看\n"
                                    f"• 推荐使用Ctrl+P打印\n"
                                    f"• 打印设置选择A4纸张")
            else:
                self.progress['value'] = 0
                self.status_var.set("用户取消了保存")

        except Exception as e:
            self.progress['value'] = 0
            self.status_var.set("生成失败")
            messagebox.showerror("错误", f"生成HTML文档时出错: {str(e)}")

    def preview_document(self):
        """预览HTML文档（生成到临时文件并用浏览器打开，不保存）"""
        try:
            day_plans, focus_count, total_count, review_count, days, focus_units, review_units = \
                self._build_day_plans()
        except SelectionError as e:
            messagebox.showwarning("无法预览", str(e))
            return

        self.status_var.set("正在生成预览...")
        self.root.update_idletasks()

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
            self.status_var.set("已打开预览")

        except Exception as e:
            self.status_var.set("预览失败")
            messagebox.showerror("错误", f"预览HTML文档时出错: {str(e)}")

    def on_closing(self):
        """窗口关闭时保存配置并清理临时文件"""
        self.save_current_config()
        # 清理预览临时文件
        if self._last_temp_html and os.path.exists(self._last_temp_html):
            try:
                os.unlink(self._last_temp_html)
            except OSError:
                pass
        self.root.destroy()

    def run(self):
        """运行GUI"""
        self.root.mainloop()
