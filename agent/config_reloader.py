"""Config Reloader - 配置热重载模块

支持手动触发和文件监控两种方式重新加载配置文件。
"""

import asyncio
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, cast

from watchdog.events import FileSystemEventHandler, FileModifiedEvent
from watchdog.observers import Observer

from agent.state_manager import StateManager


class ConfigReloader:
    """配置热重载器

    支持两种重载方式:
    1. 手动触发: 通过 reload() 方法显式重载
    2. 文件监控: 监控配置文件变化自动重载

    监控配置文件:
    - config.json
    - feature_list.json
    """

    def __init__(self, agent_dir: str | None = None) -> None:
        """初始化配置重载器。

        Args:
            agent_dir: 可选的 .agent 目录路径。
        """
        self.state_manager = StateManager(agent_dir)
        self.agent_dir = self.state_manager.agent_dir

        # 缓存配置和文件修改时间
        self._config_cache: Dict[str, Any] | None = None
        self._feature_list_cache: Dict[str, Any] | None = None
        self._config_mtime: float = 0.0
        self._feature_list_mtime: float = 0.0
        self._last_reload_time: float = 0.0

        # 回调函数 - 配置重载后调用
        self._on_reload_callbacks: list[Callable[[], None]] = []

        # 初始化缓存
        self._init_cache()

    def _init_cache(self) -> None:
        """初始化配置缓存。"""
        # 加载并缓存 config.json
        config_path = self.agent_dir / "config.json"
        if config_path.exists():
            self._config_mtime = config_path.stat().st_mtime
            self._config_cache = self.state_manager.load_config()

        # 加载并缓存 feature_list.json
        feature_list_path = self.agent_dir / "feature_list.json"
        if feature_list_path.exists():
            self._feature_list_mtime = feature_list_path.stat().st_mtime
            self._feature_list_cache = self.state_manager.load_feature_list()

    def _get_file_mtime(self, filename: str) -> float:
        """获取文件的修改时间。

        Args:
            filename: 文件名。

        Returns:
            文件修改时间，如果文件不存在返回 0.0。
        """
        file_path = self.agent_dir / filename
        if file_path.exists():
            return file_path.stat().st_mtime
        return 0.0

    def check_for_changes(self) -> Dict[str, bool]:
        """检查配置文件是否有变化。

        Returns:
            包含变化状态的字典 {'config': bool, 'feature_list': bool}。
        """
        config_changed = False
        feature_list_changed = False

        # 检查 config.json
        current_config_mtime = self._get_file_mtime("config.json")
        if current_config_mtime > self._config_mtime:
            config_changed = True

        # 检查 feature_list.json
        current_feature_mtime = self._get_file_mtime("feature_list.json")
        if current_feature_mtime > self._feature_list_mtime:
            feature_list_changed = True

        return {
            "config": config_changed,
            "feature_list": feature_list_changed,
        }

    def reload(self, force: bool = False) -> Dict[str, Any]:
        """手动触发配置重载。

        Args:
            force: 是否强制重载，忽略文件变化检查。

        Returns:
            重载结果字典。
        """
        result: Dict[str, Any] = {
            "success": True,
            "reloaded": [],
            "errors": [],
            "timestamp": datetime.now().isoformat(),
        }

        try:
            # 检查是否有变化（除非强制重载）
            if not force:
                changes = self.check_for_changes()
                if not changes["config"] and not changes["feature_list"]:
                    result["message"] = "No changes detected"
                    return result

            # 重载 config.json
            try:
                config_path = self.agent_dir / "config.json"
                if config_path.exists():
                    self._config_mtime = config_path.stat().st_mtime
                    self._config_cache = self.state_manager.load_config()
                    cast(List[str], result["reloaded"]).append("config.json")
            except Exception as e:
                cast(List[str], result["errors"]).append(f"config.json: {str(e)}")

            # 重载 feature_list.json
            try:
                feature_list_path = self.agent_dir / "feature_list.json"
                if feature_list_path.exists():
                    self._feature_list_mtime = feature_list_path.stat().st_mtime
                    self._feature_list_cache = self.state_manager.load_feature_list()
                    cast(List[str], result["reloaded"]).append("feature_list.json")
            except Exception as e:
                cast(List[str], result["errors"]).append(f"feature_list.json: {str(e)}")

            # 更新重载时间
            self._last_reload_time = time.time()

            # 触发回调
            for callback in self._on_reload_callbacks:
                try:
                    callback()
                except Exception as e:
                    cast(List[str], result["errors"]).append(f"callback: {str(e)}")

            if result["errors"]:
                result["success"] = False

            reloaded_items = cast(List[str], result["reloaded"])
            result["message"] = f"Reloaded: {', '.join(reloaded_items) if reloaded_items else 'nothing'}"

        except Exception as e:
            result["success"] = False
            result["message"] = f"Reload failed: {str(e)}"

        return result

    def get_cached_config(self) -> Dict[str, Any]:
        """获取缓存的配置（如果可用）。

        Returns:
            配置字典。
        """
        if self._config_cache is None:
            self._config_cache = self.state_manager.load_config()
        return self._config_cache

    def get_cached_feature_list(self) -> Dict[str, Any]:
        """获取缓存的功能列表（如果可用）。

        Returns:
            功能列表字典。
        """
        if self._feature_list_cache is None:
            self._feature_list_cache = self.state_manager.load_feature_list()
        return self._feature_list_cache

    def add_reload_callback(self, callback: Callable[[], None]) -> None:
        """添加配置重载回调函数。

        Args:
            callback: 重载后调用的回调函数。
        """
        self._on_reload_callbacks.append(callback)

    def remove_reload_callback(self, callback: Callable[[], None]) -> None:
        """移除配置重载回调函数。

        Args:
            callback: 要移除的回调函数。
        """
        if callback in self._on_reload_callbacks:
            self._on_reload_callbacks.remove(callback)

    def start_watching(self, interval: float = 1.0) -> "ConfigWatcher":
        """启动文件监控。

        Args:
            interval: 检查文件变化的时间间隔（秒）。

        Returns:
            ConfigWatcher 实例。
        """
        return ConfigWatcher(self, interval)


class _ConfigFileEventHandler(FileSystemEventHandler):
    """配置文件事件处理器

    监听 config.json 和 feature_list.json 的变化并触发重载。
    """

    def __init__(self, reloader: ConfigReloader) -> None:
        super().__init__()
        self.reloader = reloader

    def on_modified(self, event: Any) -> None:
        """文件修改事件处理。

        Args:
            event: 文件系统事件。
        """
        if event.is_directory:
            return

        filename = os.path.basename(event.src_path)
        if filename in ("config.json", "feature_list.json"):
            self.reloader.reload()


class ConfigWatcher:
    """配置文件监控器

    使用 watchdog 库实现非阻塞的文件监控。
    支持同步和异步两种监控方式。
    """

    def __init__(self, reloader: ConfigReloader, interval: float = 1.0) -> None:
        """初始化监控器。

        Args:
            reloader: ConfigReloader 实例。
            interval: 检查间隔（秒），仅用于异步轮询模式。
        """
        self.reloader = reloader
        self.interval = interval
        self._running = False
        self._observer: Observer | None = None
        self._async_watcher_task: asyncio.Task[None] | None = None

    def start(self) -> None:
        """启动监控（阻塞方法，使用 watchdog Observer）。

        使用 watchdog 的 Observer 线程进行非阻塞监控，
        但 start() 方法本身会阻塞直到 stop() 被调用。
        """
        self._running = True
        event_handler = _ConfigFileEventHandler(self.reloader)
        self._observer = Observer()
        self._observer.schedule(
            event_handler,
            str(self.reloader.agent_dir),
            recursive=False
        )
        self._observer.start()

        try:
            while self._running:
                time.sleep(0.1)
        finally:
            self.stop()

    def start_async(self) -> None:
        """启动异步监控（非阻塞方法）。

        使用 asyncio 创建异步任务进行文件监控，
        不会阻塞调用线程。
        """
        self._running = True
        self._async_watcher_task = asyncio.create_task(self._async_watch())

    async def _async_watch(self) -> None:
        """异步文件监控任务。"""
        event_handler = _ConfigFileEventHandler(self.reloader)
        self._observer = Observer()
        self._observer.schedule(
            event_handler,
            str(self.reloader.agent_dir),
            recursive=False
        )
        self._observer.start()

        try:
            while self._running:
                await asyncio.sleep(0.1)
        finally:
            self.stop()

    def stop(self) -> None:
        """停止监控。"""
        self._running = False
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None
        if self._async_watcher_task is not None:
            self._async_watcher_task.cancel()
            self._async_watcher_task = None


def reload_config(agent_dir: str | None = None, force: bool = False) -> Dict[str, Any]:
    """便捷函数：重载配置。

    Args:
        agent_dir: 可选的 .agent 目录路径。
        force: 是否强制重载。

    Returns:
        重载结果字典。
    """
    reloader = ConfigReloader(agent_dir)
    return reloader.reload(force=force)
