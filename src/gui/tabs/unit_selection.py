# src/gui/tabs/unit_selection.py
import tkinter as tk
from tkinter import ttk


class UnitSelectionTab:
    def __init__(self, parent, units):
        self.frame = ttk.Frame(parent)
        self.units = units
        self.setup_ui()

    def setup_ui(self):
        """设置单元选择界面"""
        # 重点单元选择
        focus_frame = ttk.LabelFrame(self.frame, text="选择重点单元", padding=10)
        focus_frame.pack(fill='x', padx=10, pady=5)

        tk.Label(focus_frame, text="选择一个重点单元:").pack(anchor='w')

        self.focus_var = tk.StringVar()
        focus_combobox = ttk.Combobox(focus_frame, textvariable=self.focus_var,
                                      state="readonly")
        focus_combobox['values'] = ["无"] + self.units
        focus_combobox.current(0)  # 默认选择"无"
        focus_combobox.pack(fill='x', pady=5)

        # 复习单元选择
        review_frame = ttk.LabelFrame(self.frame, text="选择复习单元", padding=10)
        review_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # 创建一个Frame来放置Listbox和滚动条
        listbox_frame = ttk.Frame(review_frame)
        listbox_frame.pack(fill='both', expand=True)

        # 滚动条
        scrollbar = tk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 多选Listbox
        self.review_listbox = tk.Listbox(listbox_frame, selectmode=tk.MULTIPLE,
                                         yscrollcommand=scrollbar.set,
                                         height=10)
        self.review_listbox.pack(side=tk.LEFT, fill='both', expand=True)
        scrollbar.config(command=self.review_listbox.yview)

        # 添加所有单元到Listbox
        for unit in self.units:
            self.review_listbox.insert(tk.END, unit)

        # 按钮框架
        button_frame = ttk.Frame(review_frame)
        button_frame.pack(pady=5)

        tk.Button(button_frame, text="全选",
                  command=self.select_all_review_units).pack(side=tk.LEFT, padx=5)
        tk.Button(button_frame, text="清空",
                  command=self.clear_review_units).pack(side=tk.LEFT, padx=5)

    def select_all_review_units(self):
        """选择所有复习单元"""
        self.review_listbox.select_set(0, tk.END)

    def clear_review_units(self):
        """清空复习单元选择"""
        self.review_listbox.selection_clear(0, tk.END)