"""Webhook Notification System - Webhook通知模块

当任务完成/失败/需要人工干预时，发送HTTP POST请求到配置的URL
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx

from .state_manager import StateManager
from .exceptions import WebhookError

logger = logging.getLogger(__name__)


class WebhookNotifier:
    """Webhook通知器

    支持在以下事件发生时发送Webhook通知：
    - 任务完成 (task_completed)
    - 任务失败 (task_failed)
    - 需要人工干预 (human_intervention)
    """

    def __init__(self, state_manager: Optional[StateManager] = None) -> None:
        """初始化Webhook通知器

        Args:
            state_manager: 可选的状态管理器，用于加载配置
        """
        self.state_manager = state_manager or StateManager()
        self._load_config()
        self._client: Optional[httpx.AsyncClient] = None

    def _load_config(self) -> None:
        """从配置加载Webhook设置"""
        config = self.state_manager.load_config()
        webhook_config = config.get("webhook", {})

        self.enabled = webhook_config.get("enabled", False)
        self.url = webhook_config.get("url", "")
        self.secret = webhook_config.get("secret", "")
        self.timeout = webhook_config.get("timeout", 10)
        self.events = webhook_config.get("events", [
            "task_completed",
            "task_failed",
            "human_intervention"
        ])
        self.retry_count = webhook_config.get("retry_count", 3)
        self.retry_interval = webhook_config.get("retry_interval", 2)

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
        """检查Webhook是否启用"""
        return self.enabled and bool(self.url)

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

    async def send_notification(
        self,
        event_type: str,
        data: Dict[str, Any],
        retry: bool = True
    ) -> bool:
        """发送Webhook通知

        Args:
            event_type: 事件类型 (task_completed, task_failed, human_intervention)
            data: 通知数据
            retry: 是否在失败时重试

        Returns:
            是否发送成功
        """
        if not self.should_notify(event_type):
            logger.debug(f"Webhook notification skipped for event: {event_type}")
            return False

        payload = {
            "event": event_type,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }

        # 如果配置了secret，添加到payload
        if self.secret:
            payload["secret"] = self.secret

        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Agent-Loop-Webhook/1.0"
        }

        # 如果配置了secret，也添加到headers用于验证
        if self.secret:
            headers["X-Webhook-Secret"] = self.secret

        attempt = 0
        max_attempts = self.retry_count if retry else 1
        last_error: Exception | None = None

        while attempt < max_attempts:
            try:
                logger.info(f"Sending webhook notification: {event_type} to {self.url}")

                response = await self.client.post(
                    self.url,
                    json=payload,
                    headers=headers
                )

                if response.status_code >= 200 and response.status_code < 300:
                    logger.info(f"Webhook notification sent successfully: {event_type}")
                    return True
                else:
                    # HTTP errors - 4xx are client errors (not retryable), 5xx are server errors (retryable)
                    is_retryable = response.status_code >= 500
                    raise WebhookError(
                        message=f"Webhook notification failed with status {response.status_code}",
                        detail=response.text[:200],
                        is_retryable=is_retryable,
                    )

            except httpx.TimeoutException as e:
                logger.warning(
                    f"Webhook notification timeout (attempt {attempt + 1}/{max_attempts})"
                )
                last_error = WebhookError(
                    message="Webhook notification timeout",
                    detail=str(e),
                    is_retryable=True,
                    original_exception=e,
                )
            except httpx.ConnectError as e:
                logger.warning(
                    f"Webhook notification connection error (attempt {attempt + 1}/{max_attempts}): {e}"
                )
                last_error = WebhookError(
                    message="Webhook notification connection error",
                    detail=str(e),
                    is_retryable=True,
                    original_exception=e,
                )
            except WebhookError:
                # Re-raise our own exceptions
                raise
            except Exception as e:
                logger.error(f"Webhook notification error: {type(e).__name__}: {e}")
                last_error = WebhookError(
                    message="Webhook notification failed",
                    detail=str(e),
                    is_retryable=False,
                    original_exception=e,
                )
                break

            if attempt < max_attempts - 1:
                attempt += 1
                wait_time = self.retry_interval * (2 ** attempt)  # 指数退避
                logger.info(f"Retrying webhook notification in {wait_time}s...")
                await asyncio.sleep(wait_time)

        if last_error:
            logger.error(f"Webhook notification failed after {max_attempts} attempts: {event_type}")
            raise last_error
        logger.error(f"Webhook notification failed after {max_attempts} attempts: {event_type}")
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
            data["context"] = context

        return await self.send_notification("human_intervention", data)

    async def test_webhook(self) -> Dict[str, Any]:
        """测试Webhook连接

        Returns:
            测试结果字典
        """
        if not self.is_enabled():
            return {
                "success": False,
                "message": "Webhook is not enabled. Please configure webhook.url in config.json"
            }

        try:
            # 发送测试通知
            success = await self.send_notification(
                "test",
                {
                    "message": "This is a test notification from Agent-Loop",
                    "version": "1.0.0"
                },
                retry=False  # 测试时不重试
            )

            if success:
                return {
                    "success": True,
                    "message": f"Test notification sent successfully to {self.url}"
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to send test notification. Check webhook URL and logs."
                }

        except WebhookError as e:
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


# 全局Webhook通知器实例
_webhook_notifier: Optional[WebhookNotifier] = None


def get_webhook_notifier(state_manager: Optional[StateManager] = None) -> WebhookNotifier:
    """获取全局Webhook通知器实例

    Args:
        state_manager: 可选的状态管理器

    Returns:
        WebhookNotifier实例
    """
    global _webhook_notifier
    if _webhook_notifier is None:
        _webhook_notifier = WebhookNotifier(state_manager)
    return _webhook_notifier


def reset_webhook_notifier() -> None:
    """重置全局Webhook通知器实例（用于测试）"""
    global _webhook_notifier
    if _webhook_notifier:
        asyncio.run(_webhook_notifier.close())
    _webhook_notifier = None
