# 单词听写生成器 (Word Dictation Generator)

一个基于Python和Tkinter的图形化工具，用于生成可定制的英语单词听写练习文档。教师或家长可以轻松创建包含重点复习和随机抽查的每日听写练习。

## ✨ 功能特性

- **可视化界面**：直观的GUI操作，无需命令行知识
- **灵活配置**：自定义每日单词总量、重点单词数、练习天数
- **智能单元选择**：支持选择重点单元和多个复习单元
- **严格不重复**：跨天跨池严格去重，同一个英文单词在整个练习周期内只出现一次
- **专业文档输出**：自动生成格式规范的HTML文档，包含表格、标题和统计信息
- **独立预览**：生成前可点击"预览"按钮在浏览器中查看效果，无需保存
- **词库管理**：在界面中直接新增单元和单词，即时生效
- **进度反馈**：生成文档时显示进度条
- **配置持久化**：自动保存用户设置，下次启动无需重复配置

## 📁 项目结构
```
word-dictation-generator/
├── main.py                 # 程序入口点
├── requirements.txt        # 运行时依赖（仅标准库）
├── requirements-dev.txt    # 开发依赖（pyinstaller, pytest）
├── README.md               # 项目说明文档
├── resources/              # 数据资源目录
│   ├── config.json        # 用户配置文件
│   └── words.json         # 单词数据库（核心数据文件）
└── src/                   # 源代码目录
    ├── data_loader.py     # 数据加载与持久化（含 save_word_data）
    ├── word_selector.py   # 单词选择逻辑（严格跨天去重）
    ├── html_generator.py  # HTML文档模板与生成
    └── gui/               # 图形界面模块
        ├── main_window.py # 主窗口类
        └── tabs/          # 标签页组件
            ├── unit_selection.py  # 单元选择
            ├── settings.py        # 参数设置
            └── word_library.py    # 词库管理（仅新增）
```
## 🚀 快速开始
### 环境要求
- Python 3.8+
- 推荐使用虚拟环境
## 📖 使用方法
### 基本流程
1. 启动程序后，在"选择单元"标签页：

- 选择一个重点单元（可选）

- 选择多个复习单元

2. 在"设置参数"标签页调整：

- 每日单词总数（默认：18个）

- 重点单词数（默认：6个）

- 练习天数（默认：5天）

3. 输出文件名

- 点击"预览"按钮可在浏览器中预览效果（不保存）

- 点击"生成HTML听写文档"按钮

- 选择保存位置，等待生成完成

### 词库管理
在"词库管理"标签页中：

- 选择"添加到新单元"并输入单元名称，或选择"添加到已有单元"
- 输入英文单词和中文释义，点击"添加到暂存"
- 可添加多个单词到暂存列表
- 暂存中可移除未保存的项
- 点击"保存到词库"将暂存单词写入词库，即时生效

### 自定义单词库
本程序的核心是 resources/words.json 文件，您可以随时添加新的单元和单词。

## 🔧 扩展单词库 (重点功能)
### 📝 编辑 words.json 文件
打开 resources/words.json 文件，您会看到如下结构：
``` json
{
  "word_list": [
    {
      "unit": "Unit 1",
      "words": [
        {"word": "apple", "translation": "苹果"},
        {"word": "book", "translation": "书"},
        {"word": "cat", "translation": "猫"}
      ]
    },
    {
      "unit": "Unit 2", 
      "words": [
        {"word": "dog", "translation": "狗"},
        {"word": "elephant", "translation": "大象"},
        {"word": "flower", "translation": "花"}
      ]
    }
  ]
}
```
### ➕ 添加新单元
在 "word_list" 数组中添加新的单元对象：
``` json
{
  "unit": "Unit 3",  // 单元名称，可自定义
  "words": [         // 该单元的单词列表
    {"word": "garden", "translation": "花园"},
    {"word": "house", "translation": "房子"},
    {"word": "internet", "translation": "互联网"}
  ]
}
```

### ➕ 在现有单元中添加新单词
找到对应的单元，在其 "words" 数组中添加新的单词对象：
``` json
{
  "unit": "Unit 1",
  "words": [
    {"word": "apple", "translation": "苹果"},
    {"word": "book", "translation": "书"},
    {"word": "cat", "translation": "猫"},
    {"word": "desk", "translation": "书桌"},  // 新添加的单词
    {"word": "egg", "translation": "鸡蛋"}    // 新添加的单词
  ]
}
```

### 🔄 添加后的效果
添加新内容后：

- 新单元会自动出现在程序界面的单元选择列表中
- 新单词会自动参与随机选择
- 无需修改程序代码，立即生效

## ⚙️ 配置说明
配置文件 (config.json)
程序会在 resources/config.json 中保存用户的偏好设置：
``` json
{
  "focus_count": 6,
  "total_count": 18, 
  "days": 5,
  "filename": "每日单词听写"
}
```

## 🔄 去重规则
- **跨天不重复**：同一个英文单词在整个练习周期内只出现一次（即使它在不同单元中有不同释义）
- **跨池不重复**：被重点单元选中的单词不会出现在复习中，反之亦然
- **去重粒度**：按英文单词字符串去重；同一英文单词在不同单元有不同释义时，取首次出现的释义
- **不足报错**：如果可用单词不足以填满所有天数，会提示具体的缺少数量和建议

## 🤝 参与贡献
欢迎提交Issue和Pull Request来改进这个项目。
