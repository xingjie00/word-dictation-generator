# src/gui/tabs/settings.py
import tkinter as tk
from tkinter import ttk


class SettingsTab:
    def __init__(self, parent, config):
        self.frame = ttk.Frame(parent)
        self.config = config
        self.setup_ui()

    def setup_ui(self):
        """设置参数界面"""
        # 单词数量设置
        count_frame = ttk.LabelFrame(self.frame, text="单词数量设置", padding=10)
        count_frame.pack(fill='x', padx=10, pady=5)

        tk.Label(count_frame, text="每天重点单词数量:").grid(row=0, column=0, sticky='w', pady=5)
        self.focus_count_var = tk.StringVar(value=str(self.config.get('focus_count', 10)))

        # 创建可输入的 Spinbox
        self.focus_count_spinbox = tk.Spinbox(
            count_frame,
            from_=0,
            to=50,
            textvariable=self.focus_count_var,
            width=10,
            command=self.update_word_counts  # 点击箭头时触发
        )
        self.focus_count_spinbox.grid(row=0, column=1, sticky='w', pady=5, padx=5)

        # 绑定事件
        self.focus_count_spinbox.bind('<Return>', lambda e: self.update_word_counts())
        self.focus_count_spinbox.bind('<FocusOut>', lambda e: self.update_word_counts())

        tk.Label(count_frame, text="每天总单词数:").grid(row=1, column=0, sticky='w', pady=5)
        self.total_count_var = tk.StringVar(value=str(self.config.get('total_count', 18)))

        # 创建总单词数可输入的 Spinbox
        self.total_count_spinbox = tk.Spinbox(
            count_frame,
            from_=1,
            to=100,
            textvariable=self.total_count_var,
            width=10,
            command=self.update_word_counts  # 点击箭头时触发
        )
        self.total_count_spinbox.grid(row=1, column=1, sticky='w', pady=5, padx=5)

        # 绑定事件
        self.total_count_spinbox.bind('<Return>', lambda e: self.update_word_counts())
        self.total_count_spinbox.bind('<FocusOut>', lambda e: self.update_word_counts())

        tk.Label(count_frame, text="每天复习单词数量:").grid(row=2, column=0, sticky='w', pady=5)
        self.review_count_label = tk.Label(count_frame,
                                           text=str(
                                               self.config.get('total_count', 18) - self.config.get('focus_count', 10)),
                                           fg="blue")
        self.review_count_label.grid(row=2, column=1, sticky='w', pady=5, padx=5)

        # 绑定变量更新事件
        self.focus_count_var.trace('w', lambda *args: self.update_word_counts())
        self.total_count_var.trace('w', lambda *args: self.update_word_counts())

        # 生成天数设置
        days_frame = ttk.LabelFrame(self.frame, text="生成设置", padding=10)
        days_frame.pack(fill='x', padx=10, pady=5)

        tk.Label(days_frame, text="生成天数:").grid(row=0, column=0, sticky='w', pady=5)
        self.days_var = tk.StringVar(value=str(self.config.get('days', 5)))

        # 创建可输入的 Spinbox
        self.days_spinbox = tk.Spinbox(
            days_frame,
            from_=1,
            to=30,
            textvariable=self.days_var,
            width=10,
            command=self.update_days  # 点击箭头时触发
        )
        self.days_spinbox.grid(row=0, column=1, sticky='w', pady=5, padx=5)

        # 绑定事件
        self.days_spinbox.bind('<Return>', lambda e: self.update_days())
        self.days_spinbox.bind('<FocusOut>', lambda e: self.update_days())

        # 文件名设置
        tk.Label(days_frame, text="输出文件名:").grid(row=1, column=0, sticky='w', pady=5)
        self.filename_var = tk.StringVar(value=self.config.get('filename', '单词听写'))
        filename_entry = tk.Entry(days_frame, textvariable=self.filename_var, width=30)
        filename_entry.grid(row=1, column=1, sticky='w', pady=5, padx=5)

    def update_word_counts(self, *args):
        """更新单词数量显示"""
        try:
            # 获取总单词数
            total_count = int(self.total_count_var.get())
            if total_count < 1 or total_count > 100:
                total_count = 18
                self.total_count_var.set("18")

            # 获取重点单词数
            focus_count = int(self.focus_count_var.get())
            if focus_count < 0:
                focus_count = 0
                self.focus_count_var.set("0")
            elif focus_count > total_count:
                focus_count = total_count
                self.focus_count_var.set(str(total_count))

            # 计算复习单词数
            review_count = total_count - focus_count

            # 更新显示
            self.review_count_label.config(text=str(review_count))

        except ValueError:
            # 如果输入无效，恢复为默认值
            self.focus_count_var.set("10")
            self.total_count_var.set("18")
            self.review_count_label.config(text="8")

    def update_days(self, event=None):
        """更新天数（整合了验证）"""
        try:
            value = self.days_var.get()
            if value == "":
                self.days_var.set("5")
                return

            value_int = int(value)

            # 验证范围
            if value_int < 1:
                self.days_var.set("1")
            elif value_int > 30:
                self.days_var.set("30")
            else:
                self.days_var.set(str(value_int))

        except ValueError:
            # 如果输入无效，恢复为默认值
            self.days_var.set("5")