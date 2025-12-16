# src/config_manager.py
import json
import os
import sys
from typing import Dict, Any


class ConfigManager:
    """配置管理类"""

    def __init__(self, config_file=None):  # 修改：默认值为None
        if config_file is None:
            # 获取正确的配置文件路径
            if getattr(sys, 'frozen', False):
                # 如果是打包后的exe
                base_path = sys._MEIPASS
                # 默认配置在exe内部（只读）
                self.default_config_file = os.path.join(base_path, 'src', 'config.json')
                # 用户配置在exe所在目录（可写）
                exe_dir = os.path.dirname(sys.executable)
                self.user_config_file = os.path.join(exe_dir, 'config.json')
            else:
                # 开发环境
                current_dir = os.path.dirname(os.path.abspath(__file__))
                self.default_config_file = os.path.join(current_dir, 'config.json')
                self.user_config_file = self.default_config_file
        else:
            # 如果传入了具体路径，直接使用
            self.default_config_file = config_file
            self.user_config_file = config_file

        self.default_config = {
            'focus_count': 10,
            'total_count': 18,
            'days': 5,
            'filename': '单词听写'
        }

    def load(self) -> Dict[str, Any]:
        """加载配置：优先读取用户配置，不存在则读取默认配置"""
        try:
            # 优先尝试用户配置
            if os.path.exists(self.user_config_file):
                return self._load_from_file(self.user_config_file)
            # 用户配置不存在，尝试默认配置
            elif os.path.exists(self.default_config_file):
                return self._load_from_file(self.default_config_file)
            else:
                return self.default_config.copy()
        except Exception:
            return self.default_config.copy()

    def _load_from_file(self, filepath: str) -> Dict[str, Any]:
        """从指定文件加载配置"""
        with open(filepath, 'r', encoding='utf-8') as f:
            config = json.load(f)
            # 确保所有配置项都存在
            for key, value in self.default_config.items():
                if key not in config:
                    config[key] = value
            return config

    def save(self, config: Dict[str, Any]) -> bool:
        """保存配置：总是保存到用户配置"""
        try:
            # 确保目录存在
            os.makedirs(os.path.dirname(self.user_config_file), exist_ok=True)

            with open(self.user_config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """验证并修正配置"""
        validated = config.copy()

        # 验证数字范围
        validated['focus_count'] = max(0, min(config.get('focus_count', 10), 50))
        validated['total_count'] = max(1, min(config.get('total_count', 18), 100))
        validated['days'] = max(1, min(config.get('days', 5), 30))

        # 确保重点单词数不超过总单词数
        if validated['focus_count'] > validated['total_count']:
            validated['focus_count'] = validated['total_count']

        return validated
