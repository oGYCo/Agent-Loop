"""Notification Router - 通知路由系统

统一管理所有通知的分发，根据事件类型和严重程度决定发送到哪些渠道。
支持以下通知渠道：
- Webhook: HTTP POST 通知
- Email: 邮件通知
- Slack: Slack 消息通知

事件严重程度分级：
- critical: 严重错误，需要立即处理（如 human_intervention）
- error: 错误事件（如 task_failed）
- info: 信息事件（如 task_completed）
"""

import asyncio
import logging
from enum import Enum
from typing import Any, Dict, List, Optional

from .state_manager import StateManager
from .webhook import WebhookNotifier
from .email_notifier import EmailNotifier
from .slack_notifier import SlackNotifier

logger = logging.getLogger(__name__)


class SeverityLevel(Enum):
    """通知严重程度级别"""
    CRITICAL = "critical"  # 严重错误，需要立即处理
    ERROR = "error"        # 错误事件
    INFO = "info"         # 信息事件


# 事件类型到严重程度的映射
EVENT_SEVERITY_MAP = {
    "human_intervention": SeverityLevel.CRITICAL,
    "task_failed": SeverityLevel.ERROR,
    "task_completed": SeverityLevel.INFO,
    "test": SeverityLevel.INFO,
}

# 严重程度到通知渠道的默认映射
SEVERITY_CHANNELS = {
    SeverityLevel.CRITICAL: ["webhook", "email", "slack"],  # 所有渠道
    SeverityLevel.ERROR: ["webhook", "email", "slack"],     # 所有渠道
    SeverityLevel.INFO: ["slack"],                            # 仅 Slack
}


class NotificationRouter:
    """通知路由器

    根据事件类型和严重程度自动选择通知渠道。
    支持配置化的渠道选择策略。

    配置示例 (config.json):
    ```json
    {
        "notifications": {
            "enabled": true,
            "routing": {
                "strategy": "severity",  // "severity" | "event_type" | "all"
                "severity_mapping": {
                    "critical": ["webhook", "email", "slack"],
                    "error": ["webhook", "email", "slack"],
                    "info": ["slack"]
                },
                "event_channel_override": {
                    "task_completed": ["slack"],
                    "task_failed": ["webhook", "email", "slack"],
                    "human_intervention": ["webhook", "email", "slack"]
                }
            }
        }
    }
    ```
    """

    def __init__(self, state_manager: Optional[StateManager] = None) -> None:
        """初始化通知路由器

        Args:
            state_manager: 可选的状态管理器
        """
        self.state_manager = state_manager or StateManager()
        self._load_config()

        # 初始化各个通知器
        self.webhook = WebhookNotifier(self.state_manager)
        self.email = EmailNotifier(self.state_manager)
        self.slack = SlackNotifier(self.state_manager)

    def _load_config(self) -> None:
        """从配置加载通知路由设置"""
        config = self.state_manager.load_config()
        notifications_config = config.get("notifications", {})

        self.enabled = notifications_config.get("enabled", True)
        routing_config = notifications_config.get("routing", {})

        self.routing_strategy = routing_config.get("strategy", "severity")
        self.severity_mapping = routing_config.get("severity_mapping", {
            "critical": ["webhook", "email", "slack"],
            "error": ["webhook", "email", "slack"],
            "info": ["slack"]
        })
        self.event_channel_override = routing_config.get("event_channel_override", {})

    def reload_config(self) -> None:
        """重新加载配置"""
        self._load_config()
        # 重新加载各通知器配置
        self.webhook.reload_config()
        self.email.reload_config()
        self.slack.reload_config()

    def get_severity(self, event_type: str) -> SeverityLevel:
        """获取事件类型的严重程度

        Args:
            event_type: 事件类型

        Returns:
            严重程度级别
        """
        return EVENT_SEVERITY_MAP.get(event_type, SeverityLevel.INFO)

    def get_channels_for_event(self, event_type: str) -> List[str]:
        """获取事件应该发送的渠道列表

        Args:
            event_type: 事件类型

        Returns:
            渠道名称列表
        """
        # 检查事件类型的渠道覆盖配置
        if event_type in self.event_channel_override:
            return self.event_channel_override[event_type]

        # 根据严重程度确定渠道
        if self.routing_strategy == "severity":
            severity = self.get_severity(event_type)
            return self.severity_mapping.get(severity.value, ["slack"])

        # 如果是 "all" 策略，发送所有启用的渠道
        if self.routing_strategy == "all":
            channels = []
            if self.webhook.is_enabled():
                channels.append("webhook")
            if self.email.is_enabled():
                channels.append("email")
            if self.slack.is_enabled():
                channels.append("slack")
            return channels

        # 默认使用严重程度策略
        severity = self.get_severity(event_type)
        return self.severity_mapping.get(severity.value, ["slack"])

    async def send_notification(
        self,
        event_type: str,
        data: Dict[str, Any],
        channels: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """发送通知到指定渠道

        Args:
            event_type: 事件类型
            data: 通知数据
            channels: 指定渠道列表，None 表示自动选择

        Returns:
            各渠道发送结果的字典
        """
        if not self.enabled:
            logger.debug("Notifications are disabled")
            return {}

        # 确定要发送的渠道
        if channels is None:
            channels = self.get_channels_for_event(event_type)

        results: Dict[str, bool] = {}

        # 并发发送到各个渠道
        tasks = []
        channel_names = []

        if "webhook" in channels and self.webhook.should_notify(event_type):
            tasks.append(self._send_webhook(event_type, data))
            channel_names.append("webhook")

        if "email" in channels and self.email.should_notify(event_type):
            tasks.append(self._send_email(event_type, data))
            channel_names.append("email")

        if "slack" in channels and self.slack.should_notify(event_type):
            tasks.append(self._send_slack(event_type, data))
            channel_names.append("slack")

        if not tasks:
            logger.debug(f"No channels available for event: {event_type}")
            return {}

        # 并发执行所有发送任务
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

        for name, result in zip(channel_names, results_list):
            if isinstance(result, Exception):
                logger.error(f"Failed to send {name} notification: {result}")
                results[name] = False
            else:
                results[name] = result

        return results

    async def _send_webhook(self, event_type: str, data: Dict[str, Any]) -> bool:
        """发送 webhook 通知"""
        try:
            return await self.webhook.send_notification(event_type, data)
        except Exception as e:
            logger.error(f"Webhook notification failed: {e}")
            raise

    async def _send_email(self, event_type: str, data: Dict[str, Any]) -> bool:
        """发送邮件通知"""
        try:
            return await self.email.send_notification(event_type, data)
        except Exception as e:
            logger.error(f"Email notification failed: {e}")
            raise

    async def _send_slack(self, event_type: str, data: Dict[str, Any]) -> bool:
        """发送 Slack 通知"""
        try:
            return await self.slack.send_notification(event_type, data)
        except Exception as e:
            logger.error(f"Slack notification failed: {e}")
            raise

    async def notify_task_completed(
        self,
        task_id: str,
        task_name: str,
        duration: Optional[float] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, bool]:
        """通知任务完成

        Args:
            task_id: 任务ID
            task_name: 任务名称
            duration: 任务执行时长（秒）
            extra_data: 额外数据

        Returns:
            各渠道发送结果
        """
        data: Dict[str, Any] = {
            "task_id": task_id,
            "task_name": task_name,
            "status": "completed"
        }
        if duration is not None:
            data["duration_seconds"] = duration
        if extra_data:
            data.update(extra_data)

        return await self.send_notification("task_completed", data)

    async def notify_task_failed(
        self,
        task_id: str,
        task_name: str,
        error_message: str,
        retry_count: int = 0,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, bool]:
        """通知任务失败

        Args:
            task_id: 任务ID
            task_name: 任务名称
            error_message: 错误信息
            retry_count: 重试次数
            extra_data: 额外数据

        Returns:
            各渠道发送结果
        """
        data: Dict[str, Any] = {
            "task_id": task_id,
            "task_name": task_name,
            "status": "failed",
            "error_message": error_message,
            "retry_count": retry_count
        }
        if extra_data:
            data.update(extra_data)

        return await self.send_notification("task_failed", data)

    async def notify_human_intervention(
        self,
        reason: str,
        task_id: Optional[str] = None,
        task_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, bool]:
        """通知需要人工干预

        Args:
            reason: 干预原因
            task_id: 相关任务ID
            task_name: 相关任务名称
            context: 上下文信息

        Returns:
            各渠道发送结果
        """
        data: Dict[str, Any] = {
            "reason": reason,
            "status": "intervention_required"
        }
        if task_id:
            data["task_id"] = task_id
        if task_name:
            data["task_name"] = task_name
        if context:
            data["context"] = context

        return await self.send_notification("human_intervention", data)

    async def close(self) -> None:
        """关闭所有通知器连接"""
        await self.webhook.close()
        await self.slack.close()

    def get_status(self) -> Dict[str, Any]:
        """获取通知系统状态

        Returns:
            状态字典
        """
        return {
            "enabled": self.enabled,
            "routing_strategy": self.routing_strategy,
            "channels": {
                "webhook": {
                    "enabled": self.webhook.is_enabled(),
                    "configured": bool(self.webhook.url)
                },
                "email": {
                    "enabled": self.email.is_enabled(),
                    "configured": bool(self.email.smtp_host)
                },
                "slack": {
                    "enabled": self.slack.is_enabled(),
                    "configured": bool(self.slack.webhook_url)
                }
            }
        }


# 全局通知路由器实例
_notification_router: Optional[NotificationRouter] = None


def get_notification_router(state_manager: Optional[StateManager] = None) -> NotificationRouter:
    """获取全局通知路由器实例

    Args:
        state_manager: 可选的状态管理器

    Returns:
        NotificationRouter 实例
    """
    global _notification_router
    if _notification_router is None:
        _notification_router = NotificationRouter(state_manager)
    return _notification_router


def reset_notification_router() -> None:
    """重置全局通知路由器实例（用于测试）"""
    global _notification_router
    if _notification_router:
        asyncio.run(_notification_router.close())
    _notification_router = None
