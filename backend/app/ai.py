"""OpenAI-compatible text generation. Never include API credentials in errors."""
from urllib.parse import urlsplit
import httpx
from httpx import TimeoutException


class AIError(Exception):
    pass


async def generate(content: str, settings: dict[str, str], transport=None) -> str:
    base = settings.get("BASE_URL", "").strip().rstrip("/")
    key = settings.get("API_KEY", "").strip()
    model = settings.get("MODEL", "").strip()
    parsed = urlsplit(base)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise AIError("请配置有效的 AI BASE_URL")
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise AIError("非本机 AI 服务必须使用 HTTPS")
    if not key or not model:
        raise AIError("请先配置 API_KEY 和 MODEL")
    endpoint = base + ("/chat/completions" if base.endswith("/v1") else "/v1/chat/completions")
    try:
        timeout = httpx.Timeout(connect=15, read=180, write=30, pool=15)
        async with httpx.AsyncClient(timeout=timeout, transport=transport, follow_redirects=False) as client:
            response = await client.post(endpoint, headers={"Authorization": f"Bearer {key}"}, json={
                "model": model, "messages": [{"role": "user", "content": content}],
            })
            response.raise_for_status()
            reply = response.json()["choices"][0]["message"]["content"]
            if not isinstance(reply, str) or not reply.strip():
                raise ValueError("empty reply")
            return reply.strip()
    except TimeoutException as exc:
        raise AIError("AI 请求超时（最长等待 3 分钟），请检查 API 地址、模型是否支持长文本，或稍后重试；未创建简历版本") from exc
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
        raise AIError("AI 请求失败，请检查服务地址、模型及密钥；未发送任何招聘消息") from exc
