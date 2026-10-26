# src/gui/tabs/word_library.py
"""仅新增式词库管理标签页：追加新单元、向新/已有单元追加新单词。"""
import tkinter as tk
from tkinter import ttk

from src.data_loader import save_word_data


class WordLibraryTab:
    """词库管理标签页（仅新增）。

    数据变更遵守 alias 规则：原地 append/extend，不重新赋值，
    以保证 data['unit_words'][U] 与 data['word_list'][i]['words'] 保持同步。
    """

    def __init__(self, parent, data, on_data_changed=None):
        self.frame = ttk.Frame(parent)
        self.data = data  # load_word_data() 返回的 dict（含 units/unit_words/word_list）
        self.on_data_changed = on_data_changed  # 词库变更后的回调
        self.staging = []  # 暂存列表：[(word, translation), ...]
        self.setup_ui()

    def setup_ui(self):
        """设置词库管理界面"""
        # ── 目标单元选择 ──
        target_frame = ttk.LabelFrame(self.frame, text="添加目标", padding=10)
        target_frame.pack(fill='x', padx=10, pady=5)

        self.target_mode = tk.StringVar(value="new")
        ttk.Radiobutton(target_frame, text="添加到新单元",
                        variable=self.target_mode, value="new",
                        command=self._on_target_mode_change).pack(anchor='w')

        new_unit_frame = ttk.Frame(target_frame)
        new_unit_frame.pack(fill='x', padx=20, pady=2)
        tk.Label(new_unit_frame, text="单元名称:").pack(side=tk.LEFT)
        self.new_unit_var = tk.StringVar()
        self.new_unit_entry = tk.Entry(new_unit_frame, textvariable=self.new_unit_var, width=30)
        self.new_unit_entry.pack(side=tk.LEFT, padx=5)

        ttk.Radiobutton(target_frame, text="添加到已有单元",
                        variable=self.target_mode, value="existing",
                        command=self._on_target_mode_change).pack(anchor='w')

        existing_frame = ttk.Frame(target_frame)
        existing_frame.pack(fill='x', padx=20, pady=2)
        tk.Label(existing_frame, text="选择单元:").pack(side=tk.LEFT)
        self.existing_unit_var = tk.StringVar()
        self.existing_unit_combobox = ttk.Combobox(
            existing_frame, textvariable=self.existing_unit_var,
            state="readonly", width=28
        )
        self.existing_unit_combobox['values'] = self.data.get('units', [])
        self.existing_unit_combobox.pack(side=tk.LEFT, padx=5)

        # ── 单词输入 ──
        input_frame = ttk.LabelFrame(self.frame, text="添加单词", padding=10)
        input_frame.pack(fill='x', padx=10, pady=5)

        word_row = ttk.Frame(input_frame)
        word_row.pack(fill='x', pady=2)
        tk.Label(word_row, text="英文单词:").pack(side=tk.LEFT)
        self.word_var = tk.StringVar()
        self.word_entry = tk.Entry(word_row, textvariable=self.word_var, width=30)
        self.word_entry.pack(side=tk.LEFT, padx=5)

        trans_row = ttk.Frame(input_frame)
        trans_row.pack(fill='x', pady=2)
        tk.Label(trans_row, text="中文释义:").pack(side=tk.LEFT)
        self.translation_var = tk.StringVar()
        self.translation_entry = tk.Entry(trans_row, textvariable=self.translation_var, width=30)
        self.translation_entry.pack(side=tk.LEFT, padx=5)

        btn_row = ttk.Frame(input_frame)
        btn_row.pack(fill='x', pady=5)
        tk.Button(btn_row, text="添加到暂存", command=self._add_to_staging).pack(side=tk.LEFT, padx=5)

        # ── 暂存列表 ──
        staging_frame = ttk.LabelFrame(self.frame, text="暂存单词", padding=10)
        staging_frame.pack(fill='both', expand=True, padx=10, pady=5)

        listbox_frame = ttk.Frame(staging_frame)
        listbox_frame.pack(fill='both', expand=True)

        scrollbar = tk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.staging_listbox = tk.Listbox(
            listbox_frame, yscrollcommand=scrollbar.set, height=6
        )
        self.staging_listbox.pack(side=tk.LEFT, fill='both', expand=True)
        scrollbar.config(command=self.staging_listbox.yview)

        staging_btn_row = ttk.Frame(staging_frame)
        staging_btn_row.pack(fill='x', pady=5)
        tk.Button(staging_btn_row, text="移除暂存项",
                  command=self._remove_staging_item).pack(side=tk.LEFT, padx=5)
        tk.Button(staging_btn_row, text="保存到词库",
                  command=self._save_to_library,
                  bg="#4CAF50", fg="white").pack(side=tk.LEFT, padx=5)

        # ── 状态栏 ──
        self.status_var = tk.StringVar()
        self.status_label = tk.Label(self.frame, textvariable=self.status_var,
                                    fg="gray", anchor='w')
        self.status_label.pack(fill='x', padx=10, pady=2)

    # ── 内部方法 ─────────────────────────────────────────────────────

    def _on_target_mode_change(self):
        """切换目标模式时更新 Combobox 列表"""
        self.existing_unit_combobox['values'] = self.data.get('units', [])

    def _add_to_staging(self):
        """将当前输入的单词添加到暂存列表"""
        word = self.word_var.get().strip()
        translation = self.translation_var.get().strip()

        if not word or not translation:
            self.status_var.set("⚠️ 英文单词和中文释义不能为空")
            self.status_label.config(fg="red")
            return

        # 检查暂存内是否重复
        for w, _ in self.staging:
            if w == word:
                self.status_var.set(f"⚠️ 暂存中已有单词 \"{word}\"")
                self.status_label.config(fg="red")
                return

        self.staging.append((word, translation))
        self.staging_listbox.insert(tk.END, f"{word} — {translation}")

        # 清空输入
        self.word_var.set("")
        self.translation_var.set("")
        self.word_entry.focus_set()

        self.status_var.set(f"已添加到暂存（共 {len(self.staging)} 项）")
        self.status_label.config(fg="gray")

    def _remove_staging_item(self):
        """移除选中的暂存项"""
        selection = self.staging_listbox.curselection()
        if not selection:
            self.status_var.set("⚠️ 请先选择要移除的暂存项")
            self.status_label.config(fg="red")
            return

        idx = selection[0]
        self.staging.pop(idx)
        self.staging_listbox.delete(idx)

        self.status_var.set(f"已移除（剩余 {len(self.staging)} 项）")
        self.status_label.config(fg="gray")

    def _save_to_library(self):
        """将暂存单词保存到词库"""
        if not self.staging:
            self.status_var.set("⚠️ 暂存列表为空，请先添加单词")
            self.status_label.config(fg="red")
            return

        mode = self.target_mode.get()

        if mode == "new":
            unit_name = self.new_unit_var.get().strip()
            if not unit_name:
                self.status_var.set("⚠️ 请输入新单元名称")
                self.status_label.config(fg="red")
                return
            # 检查单元名是否重复
            if unit_name in self.data.get('unit_words', {}):
                self.status_var.set(f"⚠️ 单元 \"{unit_name}\" 已存在，请选择「添加到已有单元」")
                self.status_label.config(fg="red")
                return
            self._save_new_unit(unit_name)
        else:
            unit_name = self.existing_unit_var.get().strip()
            if not unit_name:
                self.status_var.set("⚠️ 请选择一个已有单元")
                self.status_label.config(fg="red")
                return
            self._save_existing_unit(unit_name)

    def _save_new_unit(self, unit_name: str):
        """保存为新单元（原地变更，遵守 alias）"""
        # 构建新单词列表
        new_words = [{"word": w, "translation": t} for w, t in self.staging]

        # 原地 append 到 word_list
        self.data['word_list'].append({"unit": unit_name, "words": new_words})
        # 同步 units 列表
        self.data['units'].append(unit_name)
        # alias 刚 append 的 words 列表
        self.data['unit_words'][unit_name] = self.data['word_list'][-1]['words']

        # 持久化
        if save_word_data(self.data['word_list']):
            self._after_save(unit_name)
        else:
            self.status_var.set("❌ 保存失败，请检查文件权限")
            self.status_label.config(fg="red")

    def _save_existing_unit(self, unit_name: str):
        """保存到已有单元（原地变更，遵守 alias）"""
        existing_words = self.data['unit_words'].get(unit_name, [])
        existing_word_set = {w['word'] for w in existing_words}

        # 检查目标单元内重复
        duplicates = [w for w, _ in self.staging if w in existing_word_set]
        if duplicates:
            dup_str = "、".join(duplicates)
            self.status_var.set(f"⚠️ 单元内已有重复单词: {dup_str}")
            self.status_label.config(fg="red")
            return

        # 原地 extend（经 alias 同步到 word_list[i]['words']）
        new_words = [{"word": w, "translation": t} for w, t in self.staging]
        existing_words.extend(new_words)

        # 持久化
        if save_word_data(self.data['word_list']):
            self._after_save(unit_name)
        else:
            self.status_var.set("❌ 保存失败，请检查文件权限")
            self.status_label.config(fg="red")

    def _after_save(self, unit_name: str):
        """保存成功后的清理和通知"""
        # 清空暂存
        self.staging.clear()
        self.staging_listbox.delete(0, tk.END)
        # 新单元模式清空输入
        if self.target_mode.get() == "new":
            self.new_unit_var.set("")
        # 刷新已有单元 Combobox
        self.existing_unit_combobox['values'] = self.data.get('units', [])
        # 通知主窗口
        if self.on_data_changed:
            self.on_data_changed()
        # 状态提示
        self.status_var.set(f"✅ 已保存到 \"{unit_name}\"")
        self.status_label.config(fg="green")
