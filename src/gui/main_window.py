# src/gui/main_window.py
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import random
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

from src.word_formatter import WordFormatter
from src.data_loader import load_word_data, load_config, save_config
from src.gui.tabs.unit_selection import UnitSelectionTab
from src.gui.tabs.settings import SettingsTab


class WordDictationGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("单词听写生成器 v3.0")
        self.root.geometry("700x600")

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

        # 添加标签页
        self.notebook.add(self.unit_tab.frame, text="选择单元")
        self.notebook.add(self.settings_tab.frame, text="设置参数")

        # 生成按钮
        generate_btn = tk.Button(self.root, text="生成听写文档",
                                 command=self.generate_document,
                                 bg="#4CAF50", fg="white",
                                 font=("Microsoft YaHei", 12, "bold"),
                                 padx=20, pady=10)
        generate_btn.pack(pady=10)

        # 状态栏
        self.status_var = tk.StringVar()
        self.status_var.set("就绪")
        status_bar = tk.Label(self.root, textvariable=self.status_var,
                              bd=1, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def save_current_config(self):
        """保存当前配置到文件"""
        config = {
            'focus_count': int(self.settings_tab.focus_count_var.get()),
            'total_count': int(self.settings_tab.total_count_var.get()),
            'days': int(self.settings_tab.days_var.get()),
            'filename': self.settings_tab.filename_var.get()
        }
        save_config(config)

    def on_closing(self):
        """窗口关闭时保存配置"""
        self.save_current_config()
        self.root.destroy()

    def create_daily_dictation_page(self, doc, day_num, focus_units, review_units,
                                    focus_count, review_count):
        """创建一天的听写页面"""
        # 选择单词
        focus_words = []
        review_words = []

        # 选择重点单词
        if focus_units:
            all_focus_words = []
            for unit in focus_units:
                words = self.data['unit_words'].get(unit, [])
                for word in words:
                    word_with_unit = word.copy()
                    word_with_unit["unit"] = unit
                    all_focus_words.append(word_with_unit)

            if all_focus_words:
                focus_count = min(focus_count, len(all_focus_words))
                focus_words = random.sample(all_focus_words, focus_count)

        # 选择复习单词
        if review_units:
            all_review_words = []
            for unit in review_units:
                words = self.data['unit_words'].get(unit, [])
                for word in words:
                    word_with_unit = word.copy()
                    word_with_unit["unit"] = unit
                    all_review_words.append(word_with_unit)

            if all_review_words:
                review_count = min(review_count, len(all_review_words))
                review_words = random.sample(all_review_words, review_count)

        # 添加标题
        title = doc.add_paragraph()
        formatter = WordFormatter()
        formatter.add_text_with_font(title, f"英语单词听写练习 第{day_num}天",
                                     size=Pt(18), bold=True, color=RGBColor(0, 0, 139))
        title.alignment = WD_ALIGN_PARAGRAPH.CENTER

        # 创建表格
        total_rows = len(focus_words) + len(review_words) + 4
        if len(focus_words) > 0 and len(review_words) > 0:
            total_rows += 1  # 分隔行

        table = doc.add_table(rows=total_rows, cols=5)
        table.style = 'Table Grid'
        table.alignment = WD_TABLE_ALIGNMENT.CENTER

        # 设置表格列宽
        table.autofit = False
        widths = [Inches(0.6), Inches(2.2), Inches(2.0), Inches(0.6), Inches(2.0)]
        for i, width in enumerate(widths):
            table.columns[i].width = width
            for cell in table.columns[i].cells:
                cell.width = width

        # 设置表头
        headers = table.rows[0].cells
        header_texts = ["序号", "学生填写(英文单词)", "中文释义", "批改", "单元"]
        for i, text in enumerate(header_texts):
            formatter.set_cell_text_with_font(headers[i], text, bold=True)
            headers[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

        row_idx = 1

        # 添加重点单词
        if focus_words:
            for i, item in enumerate(focus_words, 1):
                cells = table.rows[row_idx].cells

                formatter.set_cell_text_with_font(cells[0], str(i))
                cells[0].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

                # 学生填写区域（留空）
                cells[1].text = ""
                if len(cells[1].paragraphs) == 0:
                    cells[1].add_paragraph()
                formatter.add_text_with_font(cells[1].paragraphs[0], "          ", size=Pt(11))

                # 中文释义
                formatter.set_cell_text_with_font(cells[2], item["translation"])

                # 批改（留空）
                cells[3].text = ""

                # 单元
                formatter.set_cell_text_with_font(cells[4], item["unit"])
                cells[4].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

                row_idx += 1

        # 如果有重点和复习单词，添加分隔行
        if focus_words and review_words:
            sep_cell = table.rows[row_idx].cells[0]
            formatter.set_cell_text_with_font(sep_cell, f"复习单词",
                                              bold=True, italic=True)
            sep_cell.merge(table.rows[row_idx].cells[4])
            row_idx += 1

        # 添加复习单词
        if review_words:
            start_num = len(focus_words) + 1
            for i, item in enumerate(review_words, start_num):
                cells = table.rows[row_idx].cells

                formatter.set_cell_text_with_font(cells[0], str(i))
                cells[0].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

                # 学生填写区域（留空）
                cells[1].text = ""
                if len(cells[1].paragraphs) == 0:
                    cells[1].add_paragraph()
                formatter.add_text_with_font(cells[1].paragraphs[0], "          ", size=Pt(11))

                # 中文释义
                formatter.set_cell_text_with_font(cells[2], item["translation"])

                # 批改（留空）
                cells[3].text = ""

                # 单元
                formatter.set_cell_text_with_font(cells[4], item["unit"])
                cells[4].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

                row_idx += 1

        # 添加统计信息
        total_words = len(focus_words) + len(review_words)

        stats_row = table.rows[row_idx]
        stats_cell = stats_row.cells[0]
        formatter.set_cell_text_with_font(stats_cell, "今日总计", bold=True)
        stats_cell.merge(stats_row.cells[1])

        formatter.set_cell_text_with_font(stats_row.cells[2], f"{total_words}个单词")
        row_idx += 1

        # 添加签名行
        sign_row = table.rows[row_idx]
        sign_cell = sign_row.cells[0]
        formatter.set_cell_text_with_font(sign_cell, "家长/老师签字:           ")
        sign_cell.merge(sign_row.cells[2])

        sign_row.cells[3].text = "批改日期:           "
        if sign_row.cells[3].paragraphs and sign_row.cells[3].paragraphs[0].runs:
            run = sign_row.cells[3].paragraphs[0].runs[0]
            formatter.set_chinese_font(run, 'Microsoft YaHei')
        sign_row.cells[3].merge(sign_row.cells[4])

    def generate_document(self):
        """生成文档"""
        # 验证并获取参数
        self.settings_tab.update_word_counts()
        self.settings_tab.update_days()

        # 保存当前配置
        self.save_current_config()

        focus_unit = self.unit_tab.focus_var.get()
        if focus_unit == "无":
            focus_units = []
        else:
            focus_units = [focus_unit]

        # 获取选择的复习单元
        review_indices = self.unit_tab.review_listbox.curselection()
        review_units = [self.unit_tab.review_listbox.get(i) for i in review_indices]

        # 排除重点单元（如果选择了）
        if focus_units:
            review_units = [unit for unit in review_units if unit != focus_units[0]]

        # 检查参数
        if not review_units:
            messagebox.showwarning("警告", "请至少选择一个复习单元！")
            return

        try:
            focus_count = int(self.settings_tab.focus_count_var.get())
            total_count = int(self.settings_tab.total_count_var.get())
            days = int(self.settings_tab.days_var.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字！")
            return

        if focus_count < 0 or focus_count > total_count:
            messagebox.showerror("错误", f"重点单词数量必须在0-{total_count}之间！")
            return

        review_count = total_count - focus_count

        # 检查单词数量是否足够
        if focus_units:
            total_focus_words = sum(len(self.data['unit_words'].get(unit, []))
                                    for unit in focus_units)
            if total_focus_words < focus_count:
                messagebox.showwarning("警告",
                                       f"重点单元只有{total_focus_words}个单词，少于设定的{focus_count}个！")
                return

        total_review_words = sum(len(self.data['unit_words'].get(unit, []))
                                 for unit in review_units)
        if total_review_words < review_count:
            messagebox.showwarning("警告",
                                   f"复习单元总共只有{total_review_words}个单词，少于设定的{review_count}个！")
            return

        # 更新状态
        self.status_var.set("正在生成文档...")
        self.root.update()

        try:
            # 创建Word文档
            doc = Document()
            WordFormatter.set_global_chinese_font(doc, 'Microsoft YaHei')

            # 生成每一天的听写页
            for day in range(1, days + 1):
                if day > 1:
                    doc.add_page_break()
                self.create_daily_dictation_page(doc, day, focus_units, review_units,
                                                 focus_count, review_count)

            # 保存文档
            filename = f"{self.settings_tab.filename_var.get()}{days}天.docx"
            filepath = filedialog.asksaveasfilename(
                defaultextension=".docx",
                initialfile=filename,
                filetypes=[("Word文档", "*.docx"), ("所有文件", "*.*")]
            )

            if filepath:
                doc.save(filepath)
                self.status_var.set(f"文档已保存: {os.path.basename(filepath)}")

                # 显示成功消息
                messagebox.showinfo("成功",
                                    f"听写文档生成成功！\n\n"
                                    f"文件: {os.path.basename(filepath)}\n"
                                    f"天数: {days}天\n"
                                    f"总单词数: {total_count}个/天\n"
                                    f"重点单元: {focus_units[0] if focus_units else '无'}\n"
                                    f"复习单元: {len(review_units)}个\n"
                                    f"每天: {focus_count}个重点单词 + {review_count}个复习单词")
            else:
                self.status_var.set("用户取消了保存")

        except Exception as e:
            self.status_var.set("生成失败")
            messagebox.showerror("错误", f"生成文档时出错: {str(e)}")

    def run(self):
        """运行GUI"""
        self.root.mainloop()