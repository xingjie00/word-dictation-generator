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
        "--hidden-import=src.config_manager",
        "--hidden-import=src.gui.main_window",
        "--hidden-import=src.gui.tabs.unit_selection",
        "--hidden-import=src.gui.tabs.settings",
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
        shutil.copytree(resources_source, resources_target)

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
2. 在界面中选择单元和设置参数
3. 点击"生成HTML听写文档"按钮

## 配置文件
- `config.json`: 程序配置文件，可修改默认参数
- `words.json`: 单词数据库，可添加/修改单词

## 注意事项
- 直接修改 `resources/` 文件夹中的json文件即可更新配置和单词
- 程序会优先使用 `resources/` 文件夹中的文件
- 重新打包exe时，`resources/` 文件夹保持不变

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
    print(f"│   └── words.json")
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
