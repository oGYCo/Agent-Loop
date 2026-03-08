"""Slack Notification System - Slack通知模块

当任务完成/失败/需要人工干预时，发送消息到Slack频道
使用Slack Incoming Webhooks和Block Kit进行消息格式化
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from .state_manager import StateManager
from .exceptions import SlackError

logger = logging.getLogger(__name__)


class SlackNotifier:
    """Slack通知器

    支持在以下事件发生时发送Slack消息：
    - 任务完成 (task_completed)
    - 任务失败 (task_failed)
    - 需要人工干预 (human_intervention)

    配置示例 (config.json):
    ```json
    {
        "slack": {
            "enabled": true,
            "webhook_url": "https://hooks.slack.com/services/xxx/xxx/xxx",
            "channel": "#agent-loop",
            "username": "Agent-Loop",
            "icon_emoji": ":robot_face:",
            "events": ["task_completed", "task_failed", "human_intervention"],
            "timeout": 10
        }
    }
    ```
    """

    # 消息模板
    TEMPLATES = {
        "task_completed": {
            "emoji": ":white_check_mark:",
            "color": "#4CAF50",
            "title": "任务已完成"
        },
        "task_failed": {
            "emoji": ":x:",
            "color": "#f44336",
            "title": "任务执行失败"
        },
        "human_intervention": {
            "emoji": ":warning:",
            "color": "#ff9800",
            "title": "需要人工干预"
        }
    }

    def __init__(self, state_manager: Optional[StateManager] = None) -> None:
        """初始化Slack通知器

        Args:
            state_manager: 可选的状态管理器，用于加载配置
        """
        self.state_manager = state_manager or StateManager()
        self._load_config()
        self._client: Optional[httpx.AsyncClient] = None

    def _load_config(self) -> None:
        """从配置加载Slack设置"""
        config = self.state_manager.load_config()
        slack_config = config.get("slack", {})

        self.enabled = slack_config.get("enabled", False)
        self.webhook_url = slack_config.get("webhook_url", "")
        self.channel = slack_config.get("channel", "")
        self.username = slack_config.get("username", "Agent-Loop")
        self.icon_emoji = slack_config.get("icon_emoji", ":robot_face:")
        self.events = slack_config.get("events", [
            "task_completed",
            "task_failed",
            "human_intervention"
        ])
        self.timeout = slack_config.get("timeout", 10)
        self.retry_count = slack_config.get("retry_count", 3)
        self.retry_interval = slack_config.get("retry_interval", 2)

    def reload_config(self) -> None:
        """重新加载配置"""
        self._load_config()

    @property
    def client(self) -> httpx.AsyncClient:
        """获取或创建异步HTTP客户端"""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True
            )
        return self._client

    async def close(self) -> None:
        """关闭HTTP客户端"""
        if self._client:
            await self._client.aclose()
            self._client = None

    def is_enabled(self) -> bool:
        """检查Slack通知是否启用"""
        return self.enabled and bool(self.webhook_url)

    def should_notify(self, event_type: str) -> bool:
        """检查是否应该发送此类型的通知

        Args:
            event_type: 事件类型

        Returns:
            是否应该发送通知
        """
        if not self.is_enabled():
            return False
        return event_type in self.events

    def _build_message_blocks(
        self,
        event_type: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """构建Slack消息Block Kit格式

        Args:
            event_type: 事件类型
            data: 消息数据

        Returns:
            Slack消息payload
        """
        template = self.TEMPLATES.get(event_type, {})
        emoji = template.get("emoji", ":bell:")
        title = template.get("title", "通知")
        color = template.get("color", "#333333")

        # 构建attachment字段
        fields = []

        if "task_name" in data:
            fields.append({
                "type": "mrkdwn",
                "text": f"*任务名称:*\n{data['task_name']}"
            })

        if "task_id" in data:
            fields.append({
                "type": "mrkdwn",
                "text": f"*任务ID:*\n{data['task_id']}"
            })

        if event_type == "task_completed" and "duration_seconds" in data:
            duration = data["duration_seconds"]
            if isinstance(duration, float):
                duration_str = f"{duration:.2f}秒"
            else:
                duration_str = str(duration)
            fields.append({
                "type": "mrkdwn",
                "text": f"*执行时长:*\n{duration_str}"
            })

        if event_type == "task_failed":
            if "retry_count" in data:
                fields.append({
                    "type": "mrkdwn",
                    "text": f"*重试次数:*\n{data['retry_count']}"
                })
            if "error_message" in data:
                error_message = str(data["error_message"])
                prefix = "*错误信息:*\n```"
                suffix = "```"
                max_field_length = 4000
                available = max_field_length - len(prefix) - len(suffix)
                if len(error_message) > available:
                    error_message = error_message[: max(0, available - 3)] + "..."
                fields.append({
                    "type": "mrkdwn",
                    "text": f"{prefix}{error_message}{suffix}"
                })

        if event_type == "human_intervention":
            if "reason" in data:
                fields.append({
                    "type": "mrkdwn",
                    "text": f"*干预原因:*\n{data['reason']}"
                })

        # 添加时间戳
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fields.append({
            "type": "mrkdwn",
            "text": f"*时间:*\n{timestamp}"
        })

        # 构建完整的payload
        payload: Dict[str, Any] = {
            "attachments": [
                {
                    "color": color,
                    "blocks": [
                        {
                            "type": "header",
                            "text": {
                                "type": "plain_text",
                                "text": f"{emoji} {title}",
                                "emoji": True
                            }
                        },
                        {
                            "type": "section",
                            "fields": fields[:10]  # Slack限制最多10个fields
                        }
                    ]
                }
            ]
        }

        # 添加可选字段
        if self.channel:
            payload["channel"] = self.channel
        if self.username:
            payload["username"] = self.username
        if self.icon_emoji:
            payload["icon_emoji"] = self.icon_emoji

        return payload

    async def send_notification(
        self,
        event_type: str,
        data: Dict[str, Any],
        retry: bool = True
    ) -> bool:
        """发送Slack通知

        Args:
            event_type: 事件类型 (task_completed, task_failed, human_intervention)
            data: 通知数据
            retry: 是否在失败时重试

        Returns:
            是否发送成功
        """
        if not self.should_notify(event_type):
            logger.debug(f"Slack notification skipped for event: {event_type}")
            return False

        payload = self._build_message_blocks(event_type, data)

        headers = {
            "Content-Type": "application/json"
        }

        max_attempts = max(1, self.retry_count if retry else 1)
        last_error: SlackError | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"Sending Slack notification: {event_type} to {self.webhook_url}")

                response = await self.client.post(
                    self.webhook_url,
                    json=payload,
                    headers=headers
                )

                # Slack返回200通常表示成功，但也可能在body中返回错误
                if response.status_code == 200:
                    raw_body = response.text
                    if isinstance(raw_body, str):
                        body = raw_body.strip()
                    elif isinstance(raw_body, (bytes, bytearray)):
                        body = raw_body.decode(errors="ignore").strip()
                    else:
                        body = ""
                    if body and body.lower() != "ok":
                        parsed: Dict[str, Any] | None = None
                        try:
                            loaded = json.loads(body)
                            if isinstance(loaded, dict):
                                parsed = loaded
                        except json.JSONDecodeError:
                            parsed = None

                        if parsed and parsed.get("ok") is False:
                            error_code = str(parsed.get("error", "unknown_error"))
                            is_retryable = error_code in {"rate_limited"}
                            error = SlackError(
                                message=f"Slack notification failed: {error_code}",
                                detail=body[:200],
                                is_retryable=is_retryable,
                            )
                            if not error.is_retryable:
                                raise error
                            last_error = error
                        else:
                            logger.info(f"Slack notification sent successfully: {event_type}")
                            return True
                    else:
                        logger.info(f"Slack notification sent successfully: {event_type}")
                        return True
                else:
                    # HTTP errors - 4xx are client errors (not retryable), 5xx/429 are retryable
                    is_retryable = response.status_code >= 500 or response.status_code == 429
                    error = SlackError(
                        message=f"Slack notification failed with status {response.status_code}",
                        detail=response.text[:200],
                        is_retryable=is_retryable,
                    )
                    if not error.is_retryable:
                        raise error
                    last_error = error

            except httpx.TimeoutException as e:
                logger.warning(
                    f"Slack notification timeout (attempt {attempt}/{max_attempts})"
                )
                last_error = SlackError(
                    message="Slack notification timeout",
                    detail=str(e),
                    is_retryable=True,
                    original_exception=e,
                )
            except httpx.ConnectError as e:
                logger.warning(
                    f"Slack notification connection error (attempt {attempt}/{max_attempts}): {e}"
                )
                last_error = SlackError(
                    message="Slack notification connection error",
                    detail=str(e),
                    is_retryable=True,
                    original_exception=e,
                )
            except SlackError:
                # Re-raise our own exceptions
                raise
            except Exception as e:
                logger.error(f"Slack notification error: {type(e).__name__}: {e}")
                raise SlackError(
                    message="Slack notification failed",
                    detail=str(e),
                    is_retryable=False,
                    original_exception=e,
                )

            if last_error and (not retry or attempt >= max_attempts):
                if not retry and last_error.is_retryable:
                    logger.error(
                        f"Slack notification failed (retry disabled): {event_type}"
                    )
                    return False
                logger.error(f"Slack notification failed after {max_attempts} attempts: {event_type}")
                raise last_error

            if last_error:
                wait_time = self.retry_interval * (2 ** attempt)  # 指数退避
                logger.info(f"Retrying Slack notification in {wait_time}s...")
                await asyncio.sleep(wait_time)

        logger.error(f"Slack notification failed after {max_attempts} attempts: {event_type}")
        return False

    async def notify_task_completed(
        self,
        task_id: str,
        task_name: str,
        duration: Optional[float] = None,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """通知任务完成

        Args:
            task_id: 任务ID
            task_name: 任务名称
            duration: 任务执行时长（秒）
            extra_data: 额外数据

        Returns:
            是否发送成功
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
    ) -> bool:
        """通知任务失败

        Args:
            task_id: 任务ID
            task_name: 任务名称
            error_message: 错误信息
            retry_count: 重试次数
            extra_data: 额外数据

        Returns:
            是否发送成功
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
    ) -> bool:
        """通知需要人工干预

        Args:
            reason: 干预原因
            task_id: 相关任务ID
            task_name: 相关任务名称
            context: 上下文信息

        Returns:
            是否发送成功
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
            # 简化context用于消息显示
            data["context"] = str(context)[:500]

        return await self.send_notification("human_intervention", data)

    async def test_slack(self) -> Dict[str, Any]:
        """测试Slack连接

        Returns:
            测试结果字典
        """
        if not self.is_enabled():
            return {
                "success": False,
                "message": "Slack is not enabled. Please configure slack.webhook_url in config.json"
            }

        try:
            # 发送测试通知
            success = await self.send_notification(
                "task_completed",
                {
                    "task_id": "test-001",
                    "task_name": "测试任务",
                    "duration_seconds": 0.0
                },
                retry=False  # 测试时不重试
            )

            if success:
                return {
                    "success": True,
                    "message": f"Test notification sent successfully to {self.channel or 'default channel'}"
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to send test notification. Check webhook URL and logs."
                }

        except SlackError as e:
            return {
                "success": False,
                "message": f"Test failed: {e.message} (retryable: {e.is_retryable})",
                "detail": e.detail,
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Test failed: {type(e).__name__}: {str(e)}"
            }


# 全局Slack通知器实例
_slack_notifier: Optional[SlackNotifier] = None


def get_slack_notifier(state_manager: Optional[StateManager] = None) -> SlackNotifier:
    """获取全局Slack通知器实例

    Args:
        state_manager: 可选的状态管理器

    Returns:
        SlackNotifier实例
    """
    global _slack_notifier
    if _slack_notifier is None:
        _slack_notifier = SlackNotifier(state_manager)
    return _slack_notifier


def reset_slack_notifier() -> None:
    """重置全局Slack通知器实例（用于测试）"""
    global _slack_notifier
    if _slack_notifier:
        asyncio.run(_slack_notifier.close())
    _slack_notifier = None
