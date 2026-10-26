# build.py - 构建和部署脚本
import os
import shutil
import subprocess
import sys


def clean_build():
    """清理旧的构建文件"""
    print("🧹 清理旧文件...")
    folders = ['build', 'dist']
    for folder in folders:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
            except PermissionError:
                # 常见原因：上次构建的 exe 还在运行，Windows 不允许删除
                print(f"❌ 无法删除 {folder}：请先关闭正在运行的「单词听写生成器.exe」")
                print("   （任务管理器中结束该进程后重试）")
                sys.exit(1)
            print(f"  已删除: {folder}")


def run_pyinstaller():
    """运行PyInstaller打包"""
    print("🔨 正在打包为单文件exe...")

    cmd = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        f"--name=单词听写生成器",
        # 只内置 words.json 种子（删 words.db 后的重置来源）；words.db 走外部随包分发
        "--add-data=resources/words.json;resources",
        "--hidden-import=src.data_loader",
        "--hidden-import=src.db",
        "--hidden-import=src.word_selector",
        "--hidden-import=src.html_generator",
        "--hidden-import=src.gui.main_window",
        "--hidden-import=src.gui.tabs.unit_selection",
        "--hidden-import=src.gui.tabs.settings",
        "--hidden-import=src.gui.tabs.word_library",
        "main.py"
    ]

    # 如果有图标文件，添加图标参数
    if os.path.exists("resources/icon.ico"):
        cmd.insert(-1, "--icon=resources/icon.ico")

    # pyinstaller 输出为 UTF-8（含中文 exe 名），默认按 GBK 解码会在读取线程崩溃
    result = subprocess.run(cmd, capture_output=True, text=True,
                            encoding='utf-8', errors='replace')

    if result.returncode != 0:
        print(f"❌ 打包失败:\n{result.stderr}")
        return False

    print("✅ 打包完成！")
    return True


def ensure_word_db():
    """确保 resources/words.db 存在（缺失时从 words.json 种子生成）。"""
    print("🗄️ 检查词库数据库...")
    import src.db
    quarantine = src.db.init_db()
    if quarantine:
        print(f"  ⚠️ 开发词库损坏，已备份为 {os.path.basename(quarantine)} 并从种子重建")
    print("  ✅ resources/words.db 就绪")


def organize_distribution():
    """整理发布文件结构"""
    print("📂 整理文件结构...")

    # 源目录和目标目录
    source_exe = "dist/单词听写生成器.exe"
    target_dir = "dist"

    if not os.path.exists(source_exe):
        print(f"❌ 找不到exe文件: {source_exe}")
        return False

    # 确保resources文件夹在dist目录中
    resources_source = "resources"
    resources_target = os.path.join(target_dir, "resources")

    if os.path.exists(resources_source):
        if os.path.exists(resources_target):
            shutil.rmtree(resources_target)

        print(f"  复制resources文件夹到dist目录...")
        # words.db 随包分发（当前词库开箱即用）；words.json 不放外部
        # （初始种子已内置 exe，作为删除 words.db 后的重置来源）
        shutil.copytree(resources_source, resources_target,
                        ignore=shutil.ignore_patterns('words.json',
                                                      'words.db.corrupt-*'))

        # 检查关键文件
        required_files = ['config.json', 'words.db']
        for file in required_files:
            file_path = os.path.join(resources_target, file)
            if not os.path.exists(file_path):
                print(f"  ⚠️  警告: 缺少 {file}")
    else:
        print(f"❌ 找不到resources源文件夹: {resources_source}")
        return False

    print(f"✅ 文件结构整理完成！")
    print(f"   发布目录: {os.path.abspath(target_dir)}")
    print(f"   包含文件:")
    print(f"     - 单词听写生成器.exe")
    print(f"     - resources/ 文件夹")
    print(f"       ├── config.json")
    print(f"       └── words.db")

    return True


def create_readme():
    """创建README文件"""
    readme_content = """# 单词听写生成器

## 使用方法
1. 双击运行 `单词听写生成器.exe`
2. 在界面中选择单元和设置参数，点击"生成HTML听写文档"或"预览"

## 文件说明
- `resources/config.json`: 程序配置（界面参数会自动保存）
- `resources/words.db`:   词库数据库（随包提供，开箱即用）

## 词库维护
- 添加单词：用程序内"词库管理"标签页，保存后即时生效
- 批量导入：词库管理标签页可粘贴或从 .txt 文件导入词表（每行"英文 释义"）
- 重置词库：删除 resources/words.db 后重启程序，将从内置初始词库重建

## 技术支持
如有问题，请联系开发者。
"""

    readme_path = os.path.join("dist", "README.txt")
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)

    print(f"📝 已创建说明文件: README.txt")


def main():
    """主构建流程"""
    print("=" * 50)
    print("单词听写生成器 - 构建工具")
    print("=" * 50)

    # 1. 清理
    clean_build()

    # 2. 确保词库数据库存在（随包分发的数据源）
    ensure_word_db()

    # 3. 打包
    if not run_pyinstaller():
        return

    # 4. 整理文件
    if not organize_distribution():
        return

    # 5. 创建说明文件
    create_readme()

    print("\n🎉 构建完成！")
    print("=" * 50)
    print(f"最终发布文件在: {os.path.abspath('dist')}")
    print(f"├── 单词听写生成器.exe")
    print(f"├── resources/")
    print(f"│   ├── config.json")
    print(f"│   └── words.db    (当前词库，随包提供)")
    print(f"└── README.txt")
    print("=" * 50)

    # 6. 可选：打开文件夹
    open_folder = input("\n是否打开dist文件夹？(y/n): ").lower()
    if open_folder == 'y':
        if sys.platform == 'win32':
            os.startfile("dist")
        elif sys.platform == 'darwin':
            os.system('open "dist"')
        else:
            os.system('xdg-open "dist"')


if __name__ == "__main__":
    main()
