"""Email Notification System - 邮件通知模块

当任务完成/失败/需要人工干预时，发送邮件通知到配置的收件人
支持SMTP配置，使用TLS/SSL安全连接
"""

import asyncio
import logging
import os
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

import aiosmtplib

from .state_manager import StateManager

logger = logging.getLogger(__name__)


class EmailNotificationError(Exception):
    """邮件通知错误"""

    def __init__(self, message: str = "Email notification failed") -> None:
        self.message = message
        super().__init__(self.message)


class EmailNotifier:
    """邮件通知器

    支持在以下事件发生时发送邮件通知：
    - 任务完成 (task_completed)
    - 任务失败 (task_failed)
    - 需要人工干预 (human_intervention)

    配置示例 (config.json):
    ```json
    {
        "email": {
            "enabled": true,
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587,
            "smtp_user": "your-email@gmail.com",
            "smtp_password": "your-app-password",
            "use_tls": true,
            "from_name": "Agent-Loop",
            "from_email": "agent-loop@example.com",
            "to_emails": ["admin@example.com", "team@example.com"],
            "events": ["task_completed", "task_failed", "human_intervention"]
        }
    }
    ```
    """

    # 邮件模板
    TEMPLATES = {
        "task_completed": {
            "subject": "[Agent-Loop] 任务完成: {{task_name}}",
            "body": """<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #4CAF50; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background: #f9f9f9; }}
        .footer {{ padding: 10px; text-align: center; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>任务已完成</h2>
        </div>
        <div class="content">
            <p><strong>任务名称:</strong> {{task_name}}</p>
            <p><strong>任务ID:</strong> {{task_id}}</p>
            <p><strong>执行时间:</strong> {{duration}}</p>
            <p><strong>完成时间:</strong> {{timestamp}}</p>
        </div>
        <div class="footer">
            <p>此邮件由 Agent-Loop 自动发送</p>
        </div>
    </div>
</body>
</html>"""
        },
        "task_failed": {
            "subject": "[Agent-Loop] 任务失败: {{task_name}}",
            "body": """<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #f44336; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background: #f9f9f9; }}
        .error {{ background: #ffebee; padding: 10px; border-left: 4px solid #f44336; }}
        .footer {{ padding: 10px; text-align: center; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>任务执行失败</h2>
        </div>
        <div class="content">
            <p><strong>任务名称:</strong> {{task_name}}</p>
            <p><strong>任务ID:</strong> {{task_id}}</p>
            <p><strong>重试次数:</strong> {{retry_count}}</p>
            <p><strong>失败时间:</strong> {{timestamp}}</p>
            <div class="error">
                <p><strong>错误信息:</strong></p>
                <pre>{{error_message}}</pre>
            </div>
        </div>
        <div class="footer">
            <p>此邮件由 Agent-Loop 自动发送</p>
        </div>
    </div>
</body>
</html>"""
        },
        "human_intervention": {
            "subject": "[Agent-Loop] 需要人工干预: {{task_name}}",
            "body": """<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #ff9800; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background: #f9f9f9; }}
        .warning {{ background: #fff3e0; padding: 10px; border-left: 4px solid #ff9800; }}
        .footer {{ padding: 10px; text-align: center; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>需要人工干预</h2>
        </div>
        <div class="content">
            <p><strong>任务名称:</strong> {{task_name}}</p>
            <p><strong>任务ID:</strong> {{task_id}}</p>
            <p><strong>发生时间:</strong> {{timestamp}}</p>
            <div class="warning">
                <p><strong>干预原因:</strong></p>
                <pre>{{reason}}</pre>
            </div>
            {% if context %}
            <p><strong>上下文信息:</strong></p>
            <pre>{{context}}</pre>
            {% endif %}
        </div>
        <div class="footer">
            <p>此邮件由 Agent-Loop 自动发送</p>
        </div>
    </div>
</body>
</html>"""
        }
    }

    def __init__(self, state_manager: Optional[StateManager] = None) -> None:
        """初始化邮件通知器

        Args:
            state_manager: 可选的状态管理器，用于加载配置
        """
        self.state_manager = state_manager or StateManager()
        self._load_config()

    def _load_config(self) -> None:
        """从配置加载邮件设置"""
        config = self.state_manager.load_config()
        email_config = config.get("email", {})

        self.enabled = email_config.get("enabled", False)
        self.smtp_host = email_config.get("smtp_host", "localhost")
        self.smtp_port = email_config.get("smtp_port", 587)
        self.smtp_user = email_config.get("smtp_user", "")
        self.smtp_password = email_config.get("smtp_password", os.environ.get("SMTP_PASSWORD", ""))
        self.use_tls = email_config.get("use_tls", True)
        self.from_name = email_config.get("from_name", "Agent-Loop")
        self.from_email = email_config.get("from_email", "agent-loop@example.com")
        self.to_emails = email_config.get("to_emails", [])
        self.events = email_config.get("events", [
            "task_completed",
            "task_failed",
            "human_intervention"
        ])
        self.timeout = email_config.get("timeout", 30)

    def reload_config(self) -> None:
        """重新加载配置"""
        self._load_config()

    def is_enabled(self) -> bool:
        """检查邮件通知是否启用"""
        return self.enabled and bool(self.smtp_host) and bool(self.to_emails)

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

    def _render_template(self, template_name: str, variables: Dict[str, Any]) -> tuple[str, str]:
        """渲染邮件模板

        Args:
            template_name: 模板名称
            variables: 模板变量

        Returns:
            (subject, body) 元组
        """
        template = self.TEMPLATES.get(template_name, {})
        subject = template.get("subject", "")
        body = template.get("body", "")

        # 简单的变量替换
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            subject = subject.replace(placeholder, str(value))
            body = body.replace(placeholder, str(value))

        # 处理可选字段 (用空字符串替换未提供的变量)
        import re
        # 处理 {% if field %} ... {% endif %} 块
        body = re.sub(r'\{% if \w+ %\}.*?\{% endif %\}', '', body, flags=re.DOTALL)

        return subject, body

    def _create_message(
        self,
        to_email: str,
        subject: str,
        body: str
    ) -> MIMEMultipart:
        """创建邮件消息

        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            body: 邮件正文

        Returns:
            MIMEMultipart 邮件对象
        """
        msg = MIMEMultipart("alternative")
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = to_email
        msg["Subject"] = subject
        msg["Date"] = datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")

        # 添加纯文本版本 (简化处理，使用去除HTML标签的版本)
        import re
        text_body = re.sub(r'<[^>]+>', '', body)
        text_body = re.sub(r'\s+', ' ', text_body).strip()

        part1 = MIMEText(text_body, "plain", "utf-8")
        part2 = MIMEText(body, "html", "utf-8")

        msg.attach(part1)
        msg.attach(part2)

        return msg

    async def send_email(
        self,
        subject: str,
        body: str,
        to_email: Optional[str] = None
    ) -> bool:
        """发送邮件

        Args:
            subject: 邮件主题
            body: 邮件正文
            to_email: 收件人邮箱，默认为配置中的第一个收件人

        Returns:
            是否发送成功
        """
        if not self.is_enabled():
            logger.debug("Email notification is disabled")
            return False

        recipients = [to_email] if to_email else self.to_emails
        if not recipients:
            logger.warning("No recipients configured for email notification")
            return False

        success = True
        for recipient in recipients:
            try:
                msg = self._create_message(recipient, subject, body)

                logger.info(f"Sending email to {recipient}: {subject}")

                await aiosmtplib.send(
                    msg,
                    hostname=self.smtp_host,
                    port=self.smtp_port,
                    username=self.smtp_user,
                    password=self.smtp_password,
                    use_tls=self.use_tls,
                    timeout=self.timeout
                )

                logger.info(f"Email sent successfully to {recipient}")

            except Exception as e:
                logger.error(f"Failed to send email to {recipient}: {type(e).__name__}: {e}")
                success = False

        return success

    async def send_notification(
        self,
        event_type: str,
        data: Dict[str, Any]
    ) -> bool:
        """发送邮件通知

        Args:
            event_type: 事件类型
            data: 通知数据

        Returns:
            是否发送成功
        """
        if not self.should_notify(event_type):
            logger.debug(f"Email notification skipped for event: {event_type}")
            return False

        # 准备模板变量
        variables = {
            "task_id": data.get("task_id", "N/A"),
            "task_name": data.get("task_name", "Unknown Task"),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        if event_type == "task_completed":
            variables["duration"] = data.get("duration_seconds", "N/A")
        elif event_type == "task_failed":
            variables["error_message"] = data.get("error_message", "Unknown error")
            variables["retry_count"] = data.get("retry_count", 0)
        elif event_type == "human_intervention":
            variables["reason"] = data.get("reason", "Unknown reason")
            if data.get("context"):
                import json
                variables["context"] = json.dumps(data.get("context"), indent=2, ensure_ascii=False)

        # 渲染模板
        subject, body = self._render_template(event_type, variables)

        return await self.send_email(subject, body)

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
        data = {
            "task_id": task_id,
            "task_name": task_name,
            "status": "completed"
        }
        if duration is not None:
            data["duration_seconds"] = f"{duration:.2f}秒"
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
        data = {
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

    async def test_email(self) -> Dict[str, Any]:
        """测试邮件发送

        Returns:
            测试结果字典
        """
        if not self.is_enabled():
            return {
                "success": False,
                "message": "Email is not enabled. Please configure email settings in config.json"
            }

        try:
            # 发送测试邮件
            subject = "Agent-Loop 测试邮件"
            body = """
            <html>
            <body>
                <h2>测试邮件</h2>
                <p>这是一封来自 Agent-Loop 的测试邮件。</p>
                <p>如果收到此邮件，说明邮件通知配置正确。</p>
            </body>
            </html>
            """

            success = await self.send_email(subject, body)

            if success:
                return {
                    "success": True,
                    "message": f"Test email sent successfully to {', '.join(self.to_emails)}"
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to send test email. Check SMTP configuration and logs."
                }

        except Exception as e:
            return {
                "success": False,
                "message": f"Test failed: {type(e).__name__}: {str(e)}"
            }


# 全局邮件通知器实例
_email_notifier: Optional[EmailNotifier] = None


def get_email_notifier(state_manager: Optional[StateManager] = None) -> EmailNotifier:
    """获取全局邮件通知器实例

    Args:
        state_manager: 可选的状态管理器

    Returns:
        EmailNotifier实例
    """
    global _email_notifier
    if _email_notifier is None:
        _email_notifier = EmailNotifier(state_manager)
    return _email_notifier


def reset_email_notifier() -> None:
    """重置全局邮件通知器实例（用于测试）"""
    global _email_notifier
    _email_notifier = None
