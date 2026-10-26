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
            shutil.rmtree(folder)
            print(f"  已删除: {folder}")


def run_pyinstaller():
    """运行PyInstaller打包"""
    print("🔨 正在打包为单文件exe...")

    cmd = [
        "pyinstaller",
        "--onefile",
        "--windowed",
        f"--name=单词听写生成器",
        "--add-data=resources;resources",
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

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"❌ 打包失败:\n{result.stderr}")
        return False

    print("✅ 打包完成！")
    return True


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
        # 排除开发期的 SQLite 词库：发布包只带种子，用户首次运行自动生成
        shutil.copytree(resources_source, resources_target,
                        ignore=shutil.ignore_patterns('words.db*'))

        # 检查关键文件
        required_files = ['config.json', 'words.json']
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
    print(f"       └── words.json")

    return True


def create_readme():
    """创建README文件"""
    readme_content = """# 单词听写生成器

## 使用方法
1. 双击运行 `单词听写生成器.exe`
2. 首次启动会自动从 resources/words.json 导入词库，生成 resources/words.db
3. 在界面中选择单元和设置参数，点击"生成HTML听写文档"或"预览"

## 文件说明
- `resources/config.json`: 程序配置（界面参数会自动保存）
- `resources/words.json`: 初始词库种子（仅在 words.db 缺失时使用）
- `resources/words.db`:   词库数据库（首次运行自动生成）

## 词库维护
- 添加单词：用程序内"词库管理"标签页，保存后即时生效
- 重置词库：删除 resources/words.db 后重启程序，将重新从 words.json 导入
- 直接编辑 words.json 不会影响已生成的 words.db

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

    # 2. 打包
    if not run_pyinstaller():
        return

    # 3. 整理文件
    if not organize_distribution():
        return

    # 4. 创建说明文件
    create_readme()

    print("\n🎉 构建完成！")
    print("=" * 50)
    print(f"最终发布文件在: {os.path.abspath('dist')}")
    print(f"├── 单词听写生成器.exe")
    print(f"├── resources/")
    print(f"│   ├── config.json")
    print(f"│   └── words.json  (words.db 由用户首次运行时自动生成)")
    print(f"└── README.txt")
    print("=" * 50)

    # 5. 可选：打开文件夹
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
