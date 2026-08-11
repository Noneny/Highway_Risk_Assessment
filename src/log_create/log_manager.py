"""
日志管理模块
将运行状态同时输出到命令行窗口和日志文件

日志文件生成在项目根目录的 log/ 文件夹下
文件名格式: risk_assessment_YYYYMMDD_HHMMSS.log

支持两种日志模式:
  - normal (默认): 完整记录所有控制台输出
  - simple: 仅记录关键信息（阶段标题、错误、警告、结果摘要、耗时统计）
"""

import sys
import os
import re
import atexit
import io
from pathlib import Path
from datetime import datetime


BASE_DIR = Path(__file__).parent.parent.parent.resolve()
LOG_DIR = BASE_DIR / "log"

_ANSI_ESCAPE_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE_RE.sub('', text)


def _strip_emoji(text: str) -> str:
    """移除常见的装饰性 emoji/符号，保留基本文本"""
    result = text
    for emoji in ['✅', '❌', '⚠️', '⚠', '🎉', '🔴', '🟢', '🟡', '📊', '📈', '📉',
                   '🔍', '⚙️', '⏳', '⌛', '💡', '🚀', '⭐', '✓', '✗', '•', '→']:
        result = result.replace(emoji, '')
    return result


def _is_important_line(line: str) -> bool:
    """判断日志行是否包含关键信息"""
    stripped = _strip_ansi(line).strip()
    if not stripped:
        return False

    # 分隔线 / 阶段标题
    if any(marker in stripped for marker in ['===', '###', '---', '***']):
        return True
    if stripped.startswith('>>') or '阶段' in stripped or '步骤' in stripped:
        return True
    if stripped.startswith('=') and len(stripped) >= 10:
        return True
    if stripped.startswith('#') and len(stripped) >= 10:
        return True

    # 错误 / 异常
    error_keywords = ['错误', '失败', '异常', 'Error', 'Exception', 'Traceback',
                      '❌', '中断', '找不到', '不存在']
    if any(kw in stripped for kw in error_keywords):
        return True

    # 警告
    warn_keywords = ['警告', 'Warning', '⚠', '跳过']
    if any(kw in stripped for kw in warn_keywords):
        return True

    # 完成 / 成功 / 结果
    result_keywords = ['完成', '成功', '✅', '执行完毕', '耗时', '秒', '分钟',
                       '结果:', '输出:', '风险等级', '摘要', '统计', '总结',
                       '总耗时', '执行时间', '输出文件']
    if any(kw in stripped for kw in result_keywords):
        return True

    # 开始 / 初始化 / 运行
    start_keywords = ['开始执行', '初始化', '正在执行', '执行流程', '运行完成']
    if any(kw in stripped for kw in start_keywords):
        return True

    # 阶段报告行（如 "1.1 处理..."）
    if re.match(r'^\d+\.\d+\s', stripped):
        return True

    # 配置 / 数据库状态
    if any(kw in stripped for kw in ['配置更新', '更新配置', '数据库连接',
                                       '数据库初始化', '已保存到', '已启用']):
        return True

    # 数据保存位置
    if any(kw in stripped for kw in ['保存到', '保存成功', '保存失败', '已保存']):
        return True

    return False


class TeeOutput:
    """同时将输出写入原始流和日志文件"""

    def __init__(self, original_stream, log_file, stream_name, simple_mode=False):
        self.original_stream = original_stream
        self.log_file = log_file
        self.stream_name = stream_name
        self._encoding = original_stream.encoding or "utf-8"
        self._buffer = ""
        self.simple_mode = simple_mode

    def write(self, data):
        self.original_stream.write(data)
        self.original_stream.flush()
        try:
            if self.simple_mode:
                self._write_filtered(data)
            else:
                self.log_file.write(data)
                self.log_file.flush()
        except Exception:
            pass

    def _write_filtered(self, data):
        """在 simple 模式下，只写入重要行"""
        self._buffer += data
        while '\n' in self._buffer:
            line, self._buffer = self._buffer.split('\n', 1)
            if _is_important_line(line):
                clean = _strip_ansi(line)
                clean = _strip_emoji(clean)
                self.log_file.write(clean + '\n')

        # 程序结束时 flush 剩余 buffer
        if self._buffer and _is_important_line(self._buffer):
            clean = _strip_ansi(self._buffer)
            clean = _strip_emoji(clean)
            self.log_file.write(clean + '\n')
            self._buffer = ""

    def flush(self):
        self.original_stream.flush()
        try:
            if self.simple_mode and self._buffer:
                clean = _strip_ansi(self._buffer)
                clean = _strip_emoji(clean)
                if clean.strip():
                    self.log_file.write(clean + '\n')
                self._buffer = ""
            self.log_file.flush()
        except Exception:
            pass

    def isatty(self):
        return hasattr(self.original_stream, "isatty") and self.original_stream.isatty()

    def fileno(self):
        return self.original_stream.fileno()


def setup_logging(simple_mode=False):
    """
    初始化日志系统
    - 创建 log/ 目录
    - 打开带时间戳的日志文件
    - 将 stdout/stderr 重定向到同时写入控制台和日志文件的 TeeOutput

    参数:
      simple_mode: True 时仅记录关键信息，减少日志冗余

    返回日志文件路径
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"risk_assessment_{timestamp}.log"
    log_path = LOG_DIR / log_filename

    log_file = io.open(
        str(log_path),
        mode="w",
        encoding="utf-8",
        buffering=1,
    )

    log_file.write(f"高速公路路网通行风险评估系统 - 日志文件\n")
    log_file.write(f"启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    log_file.write(f"日志文件: {log_path}\n")
    log_file.write(f"日志模式: {'简化' if simple_mode else '完整'}\n")
    log_file.write("=" * 80 + "\n\n")
    log_file.flush()

    sys.stdout = TeeOutput(sys.stdout, log_file, "stdout", simple_mode=simple_mode)
    sys.stderr = TeeOutput(sys.stderr, log_file, "stderr", simple_mode=simple_mode)

    def cleanup():
        try:
            log_file.write(f"\n{'=' * 80}\n")
            log_file.write(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            log_file.flush()
            log_file.close()
        except Exception:
            pass

    atexit.register(cleanup)

    return str(log_path)


def shutdown_logging():
    """手动关闭日志系统"""
    if hasattr(sys.stdout, "log_file"):
        try:
            sys.stdout.log_file.close()
        except Exception:
            pass
    if hasattr(sys.stderr, "log_file"):
        try:
            sys.stderr.log_file.close()
        except Exception:
            pass
