#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  🤖 AI NEXUS PROXY v6.0 — ULTRA EDITION                                      ║
║  ───────────────────────────────────────────────────────────────────────────  ║
║  ⚡ Architecture: Asyncio + Playwright + FastAPI + Pydantic v2               ║
║  🛡️  Security:    API Key Auth + Input Sterilization + Sandboxing            ║
║  🎯 Performance:  LRU-TTL Cache | Token-Bucket | Session Pool | Job Queue    ║
║  🔒 Stealth:      Canvas/Font/WebRTC Fingerprint + Anti-Detection            ║
║  🔄 Resilience:   Circuit Breaker | Exponential Backoff | Auto-Recovery      ║
║  📡 Real-Time:    WebSocket Streaming | SSE | Batch Processing               ║
║  🔍 Observability: Prometheus | HAR Recorder | Screenshot-on-Failure         ║
╚══════════════════════════════════════════════════════════════════════════════╝

▶ Providers:
  • DuckDuckGo AI Chat  (GPT-4o, Claude-3-Haiku, Llama-3, Mixtral, Gemini)
  • LMSYS Chatbot Arena (Claude-3-Opus, Sonnet-3.5, Gemini-Pro, Qwen2, etc.)

▶ New Features in v6.0:
  • Circuit Breaker Pattern (per provider)
  • Request Queue with Priority & Worker Pool
  • WebSocket / SSE Streaming Endpoints
  • API Key Authentication (Bearer + Header)
  • Smart Proxy Rotation with Health Check
  • Screenshot-on-Failure & HAR Recording
  • Memory Monitor with Auto-Restart
  • Batch Async Processing (/batch)
  • Advanced Canvas/Font/WebRTC Stealth
  • Graceful Shutdown with Request Draining
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import platform
import random
import re
import secrets
import signal
import sys
import time
import uuid
import weakref
from collections import deque, defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import (
    Optional, Dict, List, Any, Callable, TypeVar, 
    Awaitable, AsyncIterator, Set, Tuple
)

# ═══════════════════════════════════════════════════════════════════════════════
# THIRD-PARTY IMPORTS
# ═══════════════════════════════════════════════════════════════════════════════
import uvicorn
from fastapi import (
    FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect,
    status, Depends, Header
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, StreamingResponse
from playwright.async_api import (
    async_playwright, Browser, BrowserContext, Page,
    TimeoutError as PTimeout, Error as PError
)
from pydantic import BaseModel, Field, field_validator, ConfigDict
from loguru import logger
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, RetryError, before_sleep_log
)
from aiolimiter import AsyncLimiter
from prometheus_client import (
    Counter, Histogram, Gauge, generate_latest, 
    CONTENT_TYPE_LATEST, CollectorRegistry
)
import bleach

# ═══════════════════════════════════════════════════════════════════════════════
# TYPE ALIASES & CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════
T = TypeVar('T')
JSON = Dict[str, Any]

# ═══════════════════════════════════════════════════════════════════════════════
# PLATFORM DETECTION
# ═══════════════════════════════════════════════════════════════════════════════
class Platform(Enum):
    WINDOWS = auto(); LINUX = auto(); MACOS = auto(); OTHER = auto()
    
    @classmethod
    def current(cls) -> 'Platform':
        sys_name = platform.system()
        if sys_name == "Windows": return cls.WINDOWS
        if sys_name == "Linux": return cls.LINUX
        if sys_name == "Darwin": return cls.MACOS
        return cls.OTHER

CURRENT_PLATFORM = Platform.current()
IS_HEADLESS_CAPABLE = CURRENT_PLATFORM != Platform.WINDOWS or bool(os.getenv("DISPLAY"))

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION MANAGER (Thread-Safe Singleton)
# ═══════════════════════════════════════════════════════════════════════════════
class Config:
    _instance: Optional['Config'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized: return
        self._load(); self._initialized = True
    
    def _load(self):
        # Server
        self.HOST = os.getenv("HOST", "0.0.0.0")
        self.PORT = int(os.getenv("PORT", "8000"))
        self.WORKERS = 1
        self.RELOAD = os.getenv("RELOAD", "false").lower() == "true"
        
        # Browser
        self.HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
        self.SLOW_MO = int(os.getenv("SLOW_MO", "15"))
        self.PAGE_TIMEOUT = int(os.getenv("PAGE_TIMEOUT", "45000"))
        self.ANSWER_TIMEOUT = int(os.getenv("ANSWER_TIMEOUT", "120000"))
        
        # Resilience
        self.MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
        self.RETRY_MIN_WAIT = float(os.getenv("RETRY_MIN_WAIT", "2"))
        self.RETRY_MAX_WAIT = float(os.getenv("RETRY_MAX_WAIT", "15"))
        
        # Circuit Breaker
        self.CB_FAILURE_THRESHOLD = int(os.getenv("CB_FAILURE_THRESHOLD", "5"))
        self.CB_RECOVERY_TIMEOUT = int(os.getenv("CB_RECOVERY_TIMEOUT", "60"))
        
        # Rate Limiting
        self.RATE_PER_MIN = int(os.getenv("RATE_PER_MIN", "12"))
        self.RATE_BURST = int(os.getenv("RATE_BURST", "18"))
        self.GLOBAL_RATE = int(os.getenv("GLOBAL_RATE", "120"))
        
        # Caching
        self.CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() == "true"
        self.CACHE_TTL = int(os.getenv("CACHE_TTL", "300"))
        self.CACHE_MAX = int(os.getenv("CACHE_MAX", "500"))
        
        # Sessions
        self.MAX_SESSIONS = int(os.getenv("MAX_SESSIONS", "6"))
        self.SESSION_TTL = int(os.getenv("SESSION_TTL", "1800"))
        self.CONTEXT_TURNS = int(os.getenv("CONTEXT_TURNS", "4"))
        
        # Security
        self.SANITIZE_INPUT = os.getenv("SANITIZE_INPUT", "true").lower() == "true"
        self.MAX_PROMPT_LEN = int(os.getenv("MAX_PROMPT_LEN", "8000"))
        self.BLOCK_RESOURCES = os.getenv("BLOCK_RESOURCES", "true").lower() == "true"
        self.API_KEYS = [k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()]
        self.REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "false").lower() == "true"
        
        # Stealth
        self.ENABLE_STEALTH = os.getenv("ENABLE_STEALTH", "true").lower() == "true"
        self.RANDOMIZE_FINGERPRINT = os.getenv("RANDOMIZE_FINGERPRINT", "true").lower() == "true"
        
        # Logging
        self.LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
        self.LOG_FILE = os.getenv("LOG_FILE", "logs/ai_nexus.log")
        self.LOG_ROTATION = os.getenv("LOG_ROTATION", "25 MB")
        self.LOG_RETENTION = os.getenv("LOG_RETENTION", "7 days")
        
        # Metrics
        self.METRICS_ENABLED = os.getenv("METRICS_ENABLED", "true").lower() == "true"
        
        # Proxies
        self.PROXIES = [p.strip() for p in os.getenv("PROXIES", "").split(",") if p.strip()]
        self.PROXY_ROTATE = int(os.getenv("PROXY_ROTATE", "0"))
        
        # Debug
        self.DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"
        self.DEBUG_DIR = Path(os.getenv("DEBUG_DIR", "debug"))
        self.SCREENSHOT_ON_FAILURE = os.getenv("SCREENSHOT_ON_FAILURE", "true").lower() == "true"
        
        # Memory
        self.MEMORY_LIMIT_MB = int(os.getenv("MEMORY_LIMIT_MB", "2048"))
        self.MEMORY_CHECK_INTERVAL = int(os.getenv("MEMORY_CHECK_INTERVAL", "60"))
        
        # Queue
        self.WORKER_COUNT = int(os.getenv("WORKER_COUNT", "4"))
        self.QUEUE_MAX_SIZE = int(os.getenv("QUEUE_MAX_SIZE", "100"))
        
        Path(self.LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
        if self.DEBUG_MODE:
            self.DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    
    @property
    def is_production(self) -> bool:
        return os.getenv("ENV", "development").lower() == "production"

cfg = Config()

# ═══════════════════════════════════════════════════════════════════════════════
# STRUCTURED LOGGING
# ═══════════════════════════════════════════════════════════════════════════════
def setup_logging():
    logger.remove()
    logger.add(
        sys.stderr,
        level=cfg.LOG_LEVEL,
        format=(
            "<green>{time:HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
        backtrace=not cfg.is_production,
        diagnose=not cfg.is_production,
    )
    logger.add(
        cfg.LOG_FILE,
        rotation=cfg.LOG_ROTATION,
        retention=cfg.LOG_RETENTION,
        level="INFO",
        serialize=True,
        encoding="utf-8",
        backtrace=True,
        diagnose=True,
    )
    logger.add(
        Path(cfg.LOG_FILE).parent / "errors.log",
        level="ERROR",
        rotation="10 MB",
        retention="30 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}\n{exception}",
        backtrace=True,
        diagnose=True,
    )
    return logger

log = setup_logging()

# ═══════════════════════════════════════════════════════════════════════════════
# PROMETHEUS METRICS
# ═══════════════════════════════════════════════════════════════════════════════
registry = CollectorRegistry()

REQUEST_COUNT = Counter(
    "ai_nexus_requests_total", "Total requests", 
    ["provider", "model", "status"], registry=registry
)
REQUEST_LATENCY = Histogram(
    "ai_nexus_request_duration_seconds", "Request latency",
    ["provider", "model"], registry=registry
)
ACTIVE_SESSIONS_GAUGE = Gauge(
    "ai_nexus_active_sessions", "Active browser sessions", registry=registry
)
CACHE_HIT_COUNT = Counter(
    "ai_nexus_cache_hits_total", "Total cache hits", ["provider"], registry=registry
)
QUEUE_SIZE_GAUGE = Gauge(
    "ai_nexus_queue_size", "Current queue size", registry=registry
)
CIRCUIT_STATE_GAUGE = Gauge(
    "ai_nexus_circuit_state", "Circuit breaker state (0=closed,1=open,2=half)", 
    ["provider"], registry=registry
)
MEMORY_USAGE_GAUGE = Gauge(
    "ai_nexus_memory_usage_mb", "Current memory usage in MB", registry=registry
)

# ═══════════════════════════════════════════════════════════════════════════════
# MODEL & PROVIDER REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════
MODEL_PROVIDER: Dict[str, str] = {
    "gpt-4o-mini": "ddg", "gpt-4o": "ddg", "gpt4o": "ddg", "gpt-4": "ddg",
    "claude-3-haiku": "ddg", "haiku": "ddg",
    "llama-3-70b": "ddg", "llama3": "ddg",
    "mixtral-8x7b": "ddg", "gemini-1.5-flash": "ddg",
    "claude-3-opus": "lmsys", "opus": "lmsys",
    "claude-3-5-sonnet": "lmsys", "claude-3-sonnet": "lmsys",
    "sonnet": "lmsys", "sonnet-3.5": "lmsys",
    "gemini-pro": "lmsys", "gemini-1.5-pro": "lmsys",
    "llama-3-8b": "lmsys", "llama-3-70b-instruct": "lmsys",
    "mistral-7b": "lmsys", "mistral-large": "lmsys",
    "qwen2-72b": "lmsys", "wizardlm-2-8x22b": "lmsys",
}

LMSYS_CANONICAL: Dict[str, str] = {
    "claude-3-opus": "claude-3-opus-20240229",
    "claude-3-5-sonnet": "claude-3-5-sonnet-20241022",
    "claude-3-sonnet": "claude-3-sonnet-20240229",
    "gemini-pro": "gemini-pro",
    "gemini-1.5-pro": "gemini-1.5-pro-exp-0801",
    "llama-3-8b": "llama-3-8b-instruct",
    "llama-3-70b-instruct": "llama-3-70b-instruct",
    "mistral-7b": "mistral-7b-instruct-v0.2",
    "mistral-large": "mistral-large-2402",
    "qwen2-72b": "qwen2-72b-instruct",
    "wizardlm-2-8x22b": "wizardlm-2-8x22b",
}

DDG_INTERNAL: Dict[str, str] = {
    "gpt-4o-mini": "gpt-4o-mini", 
    "gpt-4o": "gpt-4o", 
    "gpt4o": "gpt-4o", 
    "gpt-4": "gpt-4o",
    "claude-3-haiku": "claude-3-haiku-20240307", 
    "haiku": "claude-3-haiku-20240307",
    "llama-3-70b": "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
    "mixtral-8x7b": "mistralai/Mixtral-8x7B-Instruct-v0.1",
}

# ═══════════════════════════════════════════════════════════════════════════════
# PYDANTIC MODELS
# ═══════════════════════════════════════════════════════════════════════════════
class AskRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    
    model: str = Field(..., min_length=1, max_length=64)
    prompt: str = Field(..., min_length=1)
    conversation_id: Optional[str] = Field(None, pattern=r'^[\w\-]+$')
    fresh_context: bool = Field(False)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    stream: bool = Field(False, description="Enable SSE streaming")
    
    @field_validator('model')
    @classmethod
    def validate_model(cls, v: str) -> str:
        vl = v.lower()
        if vl not in MODEL_PROVIDER:
            available = sorted(MODEL_PROVIDER.keys())
            raise ValueError(f"Unsupported model '{v}'. Available: {', '.join(available[:15])}...")
        return vl
    
    @field_validator('prompt')
    @classmethod
    def validate_prompt(cls, v: str) -> str:
        if not cfg.SANITIZE_INPUT:
            return v[:cfg.MAX_PROMPT_LEN]
        v = bleach.clean(v, tags=[], strip=True)
        v = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', v)
        v = re.sub(r'\s+', ' ', v).strip()
        return v[:cfg.MAX_PROMPT_LEN] or "..."

class BatchRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    requests: List[AskRequest] = Field(..., min_length=1, max_length=10)

class AskResponse(BaseModel):
    model: str
    response: str
    status: str
    provider: str
    conversation_id: str
    latency_ms: int
    timestamp: float = Field(default_factory=time.time)
    cached: bool = False
    meta: Optional[Dict[str, Any]] = None

class HealthResponse(BaseModel):
    status: str
    version: str
    platform: str
    headless: bool
    browser_ready: bool
    cache_enabled: bool
    active_sessions: int
    uptime_sec: float
    circuit_breakers: Dict[str, str]
    queue_size: int
    memory_mb: float

# ═══════════════════════════════════════════════════════════════════════════════
# AUTHENTICATION
# ═══════════════════════════════════════════════════════════════════════════════
class AuthManager:
    def __init__(self):
        self._keys: Set[str] = set(cfg.API_KEYS)
    
    def verify(self, api_key: Optional[str]) -> bool:
        if not cfg.REQUIRE_AUTH:
            return True
        if not api_key:
            return False
        # Support "Bearer <key>" or raw key
        if api_key.lower().startswith("bearer "):
            api_key = api_key[7:].strip()
        return secrets.compare_digest(api_key, next(iter(self._keys))) if len(self._keys) == 1 else api_key in self._keys

auth_mgr = AuthManager()

async def verify_auth(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    if not auth_mgr.verify(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

# ═══════════════════════════════════════════════════════════════════════════════
# CIRCUIT BREAKER
# ═══════════════════════════════════════════════════════════════════════════════
class CircuitState(Enum):
    CLOSED = 0      # Normal operation
    OPEN = 1        # Failing, reject requests
    HALF_OPEN = 2   # Testing recovery

class CircuitBreaker:
    """Per-provider circuit breaker."""
    
    def __init__(self, provider: str):
        self.provider = provider
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.last_failure = 0.0
        self._lock = asyncio.Lock()
    
    async def call(self, coro: Awaitable[T]) -> T:
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure > cfg.CB_RECOVERY_TIMEOUT:
                    self.state = CircuitState.HALF_OPEN
                    log.info(f"[CB] {self.provider} entering HALF_OPEN")
                else:
                    raise RuntimeError(f"Circuit breaker OPEN for {self.provider}")
        
        try:
            result = await coro
            async with self._lock:
                if self.state == CircuitState.HALF_OPEN:
                    self.state = CircuitState.CLOSED
                    self.failures = 0
                    log.info(f"[CB] {self.provider} CLOSED (recovered)")
                elif self.state == CircuitState.CLOSED:
                    self.failures = max(0, self.failures - 1)
            return result
        except Exception as e:
            async with self._lock:
                self.failures += 1
                self.last_failure = time.time()
                if self.failures >= cfg.CB_FAILURE_THRESHOLD:
                    self.state = CircuitState.OPEN
                    log.error(f"[CB] {self.provider} OPENED after {self.failures} failures")
            raise
    
    def status(self) -> str:
        return self.state.name.lower()

# ═══════════════════════════════════════════════════════════════════════════════
# PROXY ROTATOR
# ═══════════════════════════════════════════════════════════════════════════════
class ProxyRotator:
    """Smart proxy rotation with health tracking."""
    
    def __init__(self):
        self.proxies: List[str] = cfg.PROXIES
        self._healthy: Dict[str, bool] = {p: True for p in self.proxies}
        self._failures: Dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()
        self._index = 0
    
    def get(self) -> Optional[Dict[str, str]]:
        if not self.proxies:
            return None
        healthy = [p for p in self.proxies if self._healthy.get(p, True)]
        if not healthy:
            # All failed, reset
            for p in self.proxies:
                self._healthy[p] = True
                self._failures[p] = 0
            healthy = self.proxies
        
        proxy = random.choice(healthy)
        return {"server": proxy}
    
    async def report_failure(self, proxy_server: str):
        async with self._lock:
            self._failures[proxy_server] += 1
            if self._failures[proxy_server] >= 3:
                self._healthy[proxy_server] = False
                log.warning(f"[Proxy] {proxy_server} marked unhealthy")

proxy_rotator = ProxyRotator()

# ═══════════════════════════════════════════════════════════════════════════════
# MEMORY MONITOR
# ═══════════════════════════════════════════════════════════════════════════════
class MemoryMonitor:
    """Monitor memory and trigger emergency restart."""
    
    def __init__(self):
        self._task: Optional[asyncio.Task] = None
        self._running = False
    
    def start(self):
        self._running = True
        self._task = asyncio.create_task(self._loop())
    
    def stop(self):
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
    
    async def _loop(self):
        while self._running:
            try:
                await asyncio.sleep(cfg.MEMORY_CHECK_INTERVAL)
                usage_mb = self._get_memory_mb()
                MEMORY_USAGE_GAUGE.set(usage_mb)
                
                if usage_mb > cfg.MEMORY_LIMIT_MB:
                    log.error(f"[Memory] CRITICAL: {usage_mb:.0f}MB > {cfg.MEMORY_LIMIT_MB}MB")
                    # Signal for restart
                    asyncio.create_task(emergency_restart())
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"[Memory] Monitor error: {e}")
    
    def _get_memory_mb(self) -> float:
        try:
            import psutil
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            # Fallback: read /proc/self/status on Linux
            try:
                with open('/proc/self/status') as f:
                    for line in f:
                        if line.startswith('VmRSS:'):
                            return int(line.split()[1]) / 1024
            except Exception:
                pass
            return 0.0

mem_monitor = MemoryMonitor()

async def emergency_restart():
    """Graceful emergency restart."""
    log.warning("[Emergency] Initiating memory-based restart...")
    await asyncio.sleep(2)
    os.kill(os.getpid(), signal.SIGTERM)

# ═══════════════════════════════════════════════════════════════════════════════
# DEBUG RECORDER (HAR + Screenshots)
# ═══════════════════════════════════════════════════════════════════════════════
class DebugRecorder:
    """Record HAR and screenshots for failed requests."""
    
    def __init__(self):
        self.enabled = cfg.DEBUG_MODE or cfg.SCREENSHOT_ON_FAILURE
        self.dir = cfg.DEBUG_DIR
    
    async def screenshot(self, page: Page, name: str):
        if not self.enabled:
            return
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = self.dir / f"screenshot_{name}_{ts}.png"
            await page.screenshot(path=str(path), full_page=True)
            log.debug(f"[Debug] Screenshot saved: {path}")
        except Exception as e:
            log.debug(f"[Debug] Screenshot failed: {e}")
    
    async def har_start(self, context: BrowserContext, name: str) -> Optional[Path]:
        if not cfg.DEBUG_MODE:
            return None
        try:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = self.dir / f"har_{name}_{ts}.har"
            await context.tracing.start(screenshots=True, snapshots=True, sources=True)
            return path
        except Exception as e:
            log.debug(f"[Debug] HAR start failed: {e}")
            return None
    
    async def har_stop(self, context: BrowserContext, path: Optional[Path]):
        if not path or not cfg.DEBUG_MODE:
            return
        try:
            await context.tracing.stop(path=str(path))
            log.debug(f"[Debug] HAR saved: {path}")
        except Exception as e:
            log.debug(f"[Debug] HAR stop failed: {e}")

debug_recorder = DebugRecorder()

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════
def generate_client_id(request: Request) -> str:
    raw = f"{request.client.host if request.client else 'unknown'}:{request.headers.get('user-agent', '')}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

def hash_request(model: str, prompt: str, ctx: Optional[List[Dict]]) -> str:
    data = f"{model}:{prompt}:{json.dumps(ctx or [], sort_keys=True, ensure_ascii=False)}"
    return hashlib.sha256(data.encode()).hexdigest()

def sanitize_response(text: str) -> str:
    if not text:
        return ""
    patterns = [
        r'^(Send|Copy|Like|Dislike|Regenerate|Stop|New Chat|Clear|Retry)\b.*$',
        r'^(DuckDuckGo|AI Chat|Beta|Settings|Model:|Chat)\b.*$',
        r'^(GPT|Claude|Llama|Mixtral|Gemini|Assistant)\b.*$',
        r'^\d+\s*(tokens?|words?|characters?|messages?)\b.*$',
        r'^\[.*?\]$', r'^\{.*?\}$',
        r'^```\s*$',
    ]
    lines = text.split('\n')
    cleaned = [
        line for line in lines 
        if not any(re.match(p, line.strip(), re.I) for p in patterns) 
        and line.strip()
    ]
    return '\n'.join(cleaned).strip()

# ═══════════════════════════════════════════════════════════════════════════════
# RATE LIMITER
# ═══════════════════════════════════════════════════════════════════════════════
class RateLimiter:
    def __init__(self, per_min: int, burst: int, global_limit: int):
        self.per_client_limiter = AsyncLimiter(per_min / 60, burst)
        self.global_limiter = AsyncLimiter(global_limit / 60, burst * 2)
        self._clients: Dict[str, deque] = {}
        self._lock = asyncio.Lock()
    
    async def acquire(self, client_id: Optional[str] = None) -> bool:
        try:
            await asyncio.wait_for(self.global_limiter.acquire(), timeout=0.5)
            if client_id:
                async with self._lock:
                    now = time.time()
                    window = self._clients.setdefault(client_id, deque())
                    while window and window[0] < now - 60:
                        window.popleft()
                    if len(window) >= cfg.RATE_PER_MIN:
                        return False
                    window.append(now)
                await asyncio.wait_for(self.per_client_limiter.acquire(), timeout=0.5)
            return True
        except asyncio.TimeoutError:
            return False
    
    def stats(self) -> Dict[str, Any]:
        return {
            "global_limit": cfg.GLOBAL_RATE,
            "per_client_limit": cfg.RATE_PER_MIN,
            "active_clients": len(self._clients),
        }

# ═══════════════════════════════════════════════════════════════════════════════
# RESPONSE CACHE
# ═══════════════════════════════════════════════════════════════════════════════
@dataclass
class CacheEntry:
    response: str
    model: str
    provider: str
    created_at: float
    ttl: int
    key: str
    
    @property
    def expired(self) -> bool:
        return (time.time() - self.created_at) > self.ttl
    
    @property
    def age(self) -> int:
        return int(time.time() - self.created_at)

class ResponseCache:
    def __init__(self, max_size: int, ttl: int):
        self.max_size = max_size
        self.ttl = ttl
        self._store: Dict[str, CacheEntry] = {}
        self._access_order: deque = deque(maxlen=max_size)
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[CacheEntry]:
        if not cfg.CACHE_ENABLED:
            return None
        async with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            if entry.expired:
                self._evict(key)
                return None
            if key in self._access_order:
                self._access_order.remove(key)
            self._access_order.append(key)
            return entry
    
    async def set(self, key: str, entry: CacheEntry):
        if not cfg.CACHE_ENABLED:
            return
        async with self._lock:
            if key in self._store:
                self._access_order.remove(key)
            elif len(self._store) >= self.max_size:
                self._evict_oldest()
            self._store[key] = entry
            self._access_order.append(key)
    
    async def clear(self):
        async with self._lock:
            self._store.clear()
            self._access_order.clear()
    
    def _evict(self, key: str):
        self._store.pop(key, None)
        if key in self._access_order:
            self._access_order.remove(key)
    
    def _evict_oldest(self):
        if self._access_order:
            oldest = self._access_order.popleft()
            self._store.pop(oldest, None)
    
    async def stats(self) -> Dict[str, Any]:
        async with self._lock:
            valid = sum(1 for e in self._store.values() if not e.expired)
            return {
                "enabled": cfg.CACHE_ENABLED,
                "max_size": self.max_size,
                "ttl_sec": self.ttl,
                "total_entries": len(self._store),
                "valid": valid,
                "expired": len(self._store) - valid,
            }

# ═══════════════════════════════════════════════════════════════════════════════
# CONVERSATION CONTEXT
# ═══════════════════════════════════════════════════════════════════════════════
@dataclass
class Conversation:
    turns: int = cfg.CONTEXT_TURNS
    messages: List[Dict[str, str]] = field(default_factory=list)
    
    def add(self, role: str, content: str):
        self.messages.append({"role": role, "content": content[:2000]})
        max_msgs = self.turns * 2
        if len(self.messages) > max_msgs:
            self.messages = self.messages[-max_msgs:]
    
    def format(self) -> str:
        if not self.messages:
            return ""
        parts = []
        for msg in self.messages[-(self.turns * 2):]:
            prefix = "User" if msg["role"] == "user" else "Assistant"
            parts.append(f"{prefix}: {msg['content']}")
        return "\n".join(parts)
    
    def to_list(self) -> List[Dict[str, str]]:
        return [m.copy() for m in self.messages]

# ═══════════════════════════════════════════════════════════════════════════════
# SESSION POOL (Deadlock-Free)
# ═══════════════════════════════════════════════════════════════════════════════
@dataclass
class Session:
    context: BrowserContext
    page: Page
    provider: str
    model: str
    conversation: Conversation = field(default_factory=Conversation)
    created: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    req_count: int = 0
    _closed: bool = field(default=False, repr=False)
    
    def stale(self, ttl: int) -> bool:
        return (time.time() - self.last_used) > ttl
    
    def touch(self):
        self.last_used = time.time()
        self.req_count += 1
    
    async def close(self):
        if not self._closed:
            self._closed = True
            try:
                await self.context.close()
            except Exception as e:
                log.debug(f"Session close error: {e}")

class SessionPool:
    def __init__(self, max_sessions: int):
        self.max = max_sessions
        self._sessions: Dict[str, Session] = {}
        self._lock = asyncio.Lock()
    
    async def get(self, cid: str) -> Optional[Session]:
        async with self._lock:
            sess = self._sessions.get(cid)
            if sess and not sess.stale(cfg.SESSION_TTL) and not sess._closed:
                sess.touch()
                return sess
            return None
    
    async def put(self, cid: str, sess: Session) -> bool:
        async with self._lock:
            if len(self._sessions) >= self.max and cid not in self._sessions:
                stale_items = [
                    (k, v.last_used) for k, v in self._sessions.items() 
                    if v.stale(300)
                ]
                if stale_items:
                    stale_items.sort(key=lambda x: x[1])
                    await self._remove_sync(stale_items[0][0])
                else:
                    log.warning("Session pool full")
                    return False
            self._sessions[cid] = sess
            ACTIVE_SESSIONS_GAUGE.set(len(self._sessions))
            return True
    
    async def remove(self, cid: str):
        async with self._lock:
            await self._remove_sync(cid)
    
    async def _remove_sync(self, cid: str):
        sess = self._sessions.pop(cid, None)
        if sess:
            await sess.close()
            log.debug(f"Session closed: {cid[:8]}...")
            ACTIVE_SESSIONS_GAUGE.set(len(self._sessions))
    
    async def add_message(self, cid: str, role: str, content: str):
        async with self._lock:
            if cid in self._sessions:
                self._sessions[cid].conversation.add(role, content)
    
    async def get_context(self, cid: str) -> Optional[Conversation]:
        async with self._lock:
            if cid in self._sessions:
                return self._sessions[cid].conversation
        return None
    
    async def purge(self):
        async with self._lock:
            stale = [k for k, v in self._sessions.items() if v.stale(cfg.SESSION_TTL)]
        for k in stale:
            log.info(f"Purging stale session: {k[:8]}...")
            await self.remove(k)
    
    async def close_all(self):
        async with self._lock:
            ids = list(self._sessions.keys())
        for cid in ids:
            await self.remove(cid)
        log.info("All sessions terminated")

# ═══════════════════════════════════════════════════════════════════════════════
# STEALTH ENGINE v2 (Canvas + Font + WebRTC + Advanced)
# ═══════════════════════════════════════════════════════════════════════════════
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
]

def get_user_agent() -> str:
    return random.choice(USER_AGENTS) if cfg.RANDOMIZE_FINGERPRINT else USER_AGENTS[0]

def get_browser_args() -> List[str]:
    base = [
        "--no-sandbox", "--disable-setuid-sandbox",
        "--disable-blink-features=AutomationControlled",
        "--disable-infobars", "--window-size=1366,768",
        "--disable-extensions", "--disable-dev-shm-usage",
        "--disable-gpu", "--no-first-run", "--no-default-browser-check",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-features=IsolateOrigins,site-per-process",
        "--disable-popup-blocking", "--disable-web-security",
        "--disable-features=InterestFeedContentSuggestions",
    ]
    if CURRENT_PLATFORM == Platform.WINDOWS:
        base.append("--disable-features=msEdgeExperiments")
    elif CURRENT_PLATFORM == Platform.LINUX:
        base.append("--disable-features=UseChromeOSDirectVideoDecoder")
    return base

async def inject_stealth(page: Page):
    if not cfg.ENABLE_STEALTH:
        return
    
    await page.add_init_script("""
    () => {
        // Webdriver
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        
        // Plugins
        Object.defineProperty(navigator, 'plugins', {
            get: () => [
                {name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format'},
                {name: 'Native Client', filename: 'internal-nacl-plugin', description: 'Native Client module'},
                {name: 'Widevine Content Decryption Module', filename: 'widevinecdmadapter.dll', description: 'Widevine Content Decryption Module'}
            ]
        });
        
        // Languages
        const langs = ['en-US', 'en', 'en-GB', 'fr', 'de'];
        Object.defineProperty(navigator, 'languages', {
            get: () => langs.slice(0, 2 + Math.floor(Math.random() * 3))
        });
        
        // Chrome runtime
        window.chrome = {
            runtime: {
                OnInstalledReason: {CHROME_UPDATE: "chrome_update", INSTALL: "install", UPDATE: "update"},
                PlatformOs: {WIN: "win", MAC: "mac", LINUX: "linux"},
                OnRestartRequiredReason: {APP_UPDATE: "app_update", OS_UPDATE: "os_update"}
            },
            loadTimes: () => ({}), csi: () => ({}), app: {}
        };
        
        // Permissions
        const origQuery = window.navigator.permissions?.query;
        if (origQuery) {
            window.navigator.permissions.query = (parameters) => {
                if (parameters.name === 'notifications') {
                    return Promise.resolve({state: 'granted', onchange: null});
                }
                return origQuery(parameters);
            };
        }
        
        // WebGL
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            const vendors = ['Intel Inc.', 'Apple Inc.', 'NVIDIA Corporation', 'AMD'];
            const renderers = [
                'Intel Iris Xe Graphics', 'Apple M2', 'NVIDIA GeForce RTX 3060', 
                'AMD Radeon RX 6700 XT'
            ];
            if (parameter === 37445) return vendors[Math.floor(Math.random() * vendors.length)];
            if (parameter === 37446) return renderers[Math.floor(Math.random() * renderers.length)];
            return getParameter.call(this, parameter);
        };
        
        // Canvas fingerprint randomization
        const origToDataURL = HTMLCanvasElement.prototype.toDataURL;
        const origGetImageData = CanvasRenderingContext2D.prototype.getImageData;
        HTMLCanvasElement.prototype.toDataURL = function(type) {
            const ctx = this.getContext('2d');
            if (ctx) {
                const imageData = ctx.getImageData(0, 0, this.width, this.height);
                const data = imageData.data;
                for (let i = 0; i < data.length; i += 4) {
                    data[i] = (data[i] + Math.floor(Math.random() * 3) - 1) & 0xFF;
                }
                ctx.putImageData(imageData, 0, 0);
            }
            return origToDataURL.call(this, type);
        };
        
        // Font fingerprinting protection
        const origMeasureText = CanvasRenderingContext2D.prototype.measureText;
        CanvasRenderingContext2D.prototype.measureText = function(text) {
            const result = origMeasureText.call(this, text);
            if (result && result.width) {
                result.width = result.width + (Math.random() * 0.02 - 0.01);
            }
            return result;
        };
        
        // WebRTC leak prevention
        const origRTCPeerConnection = window.RTCPeerConnection;
        if (origRTCPeerConnection) {
            window.RTCPeerConnection = function(...args) {
                const pc = new origRTCPeerConnection(...args);
                pc.createDataChannel = () => ({});
                return pc;
            };
        }
        
        // iframe protection
        const origAttachShadow = Element.prototype.attachShadow;
        Element.prototype.attachShadow = function(opts) {
            return origAttachShadow.call(this, { ...opts, mode: 'closed' });
        };
        
        // Notification API
        if (window.Notification) {
            Object.defineProperty(window.Notification, 'permission', {get: () => 'default'});
        }
    }
    """)

async def human_delay(min_ms: int = 80, max_ms: int = 400):
    await asyncio.sleep(random.triangular(min_ms/1000, max_ms/1000, (min_ms+max_ms)/2000))

async def human_type(page: Page, text: str):
    """Human-like typing with occasional corrections."""
    for i, char in enumerate(text):
        if random.random() < 0.003 and i > 3 and char.isalpha():
            wrong = random.choice('qwertyuiopasdfghjklzxcvbnm')
            await page.keyboard.type(wrong)
            await human_delay(40, 120)
            await page.keyboard.press("Backspace")
            await human_delay(30, 80)
        
        # Use fill for large pastes, type for small
        remaining = len(text) - i
        if remaining > 50 and i % 50 == 0 and random.random() < 0.3:
            chunk = text[i:i+random.randint(10, 30)]
            await page.keyboard.type(chunk)
            i += len(chunk) - 1
            continue
            
        await page.keyboard.type(char)
        delay = random.uniform(0.012, 0.05) if char.isalnum() else random.uniform(0.03, 0.1)
        await asyncio.sleep(delay)
        
        if i > 0 and i % random.randint(30, 60) == 0:
            await human_delay(150, 500)

# ═══════════════════════════════════════════════════════════════════════════════
# BROWSER MANAGER (Fixed Deadlock + Auto-Recovery)
# ═══════════════════════════════════════════════════════════════════════════════
class BrowserManager:
    _instance: Optional['BrowserManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init = False
        return cls._instance
    
    def __init__(self):
        if self._init: return
        self._pw = None
        self._browser: Optional[Browser] = None
        self._healthy = False
        self._crashes = 0
        self._max_crashes = 3
        self._lock = asyncio.Lock()
        self._init = True
        log.info(f"BrowserManager ready | Platform: {CURRENT_PLATFORM.name}")
    
    async def start(self):
        # Fast path without lock
        if self._browser and self._healthy:
            return
        
        acquired = False
        try:
            acquired = await asyncio.wait_for(self._lock.acquire(), timeout=30)
            if self._browser and self._healthy:
                return
            
            log.info("Launching Chromium...")
            self._pw = await async_playwright().start()
            args = get_browser_args()
            headless = cfg.HEADLESS if IS_HEADLESS_CAPABLE else True
            
            self._browser = await self._pw.chromium.launch(
                headless=headless,
                slow_mo=cfg.SLOW_MO,
                args=args,
            )
            self._healthy = True
            self._crashes = 0
            log.info(f"✓ Browser ready | Headless: {headless}")
            
        except Exception as e:
            self._healthy = False
            self._crashes += 1
            log.error(f"✗ Launch failed ({self._crashes}/{self._max_crashes}): {e}")
            if self._crashes >= self._max_crashes:
                raise RuntimeError(f"Browser failed {self._max_crashes} times")
            await asyncio.sleep(2 ** self._crashes)
            # Retry outside lock
            if acquired:
                self._lock.release()
                acquired = False
            await self.start()
        finally:
            if acquired:
                self._lock.release()
    
    async def ensure_healthy(self) -> bool:
        if not self._healthy or not self._browser:
            log.warning("Browser unhealthy, recovering...")
            await self.close()
            await self.start()
        return self._healthy
    
    async def new_context(self) -> BrowserContext:
        await self.ensure_healthy()
        
        proxy = proxy_rotator.get() if cfg.PROXIES else None
        
        ctx = await self._browser.new_context(
            user_agent=get_user_agent(),
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id=random.choice([
                "America/New_York", "Europe/London", "Asia/Tokyo", "Australia/Sydney"
            ]),
            color_scheme=random.choice(["light", "dark"]),
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            },
            proxy=proxy,
            ignore_https_errors=True,
        )
        
        if cfg.BLOCK_RESOURCES:
            await ctx.route("**/*.{png,jpg,jpeg,gif,svg,webp,woff,woff2,ttf,eot,ico}", 
                          lambda route: route.abort())
            await ctx.route("**/{analytics,track,beacon,telemetry,metrics}/**", 
                          lambda route: route.abort())
        return ctx
    
    async def close(self):
        acquired = False
        try:
            acquired = await asyncio.wait_for(self._lock.acquire(), timeout=10)
            if self._browser:
                try:
                    await self._browser.close()
                except Exception as e:
                    log.debug(f"Browser close error: {e}")
                log.info("Browser closed")
            if self._pw:
                try:
                    await self._pw.stop()
                except Exception:
                    pass
                log.info("Playwright stopped")
            self._browser = None
            self._pw = None
            self._healthy = False
        except asyncio.TimeoutError:
            log.error("Browser close timeout")
        finally:
            if acquired:
                self._lock.release()

# ═══════════════════════════════════════════════════════════════════════════════
# PROVIDER AUTOMATORS
# ═══════════════════════════════════════════════════════════════════════════════
class BaseAutomator:
    def __init__(self, bm: BrowserManager):
        self.bm = bm
    
    @staticmethod
    async def wait_for_input(page: Page, timeout: int = 8000) -> str:
        selectors = [
            'textarea[placeholder*="Ask" i]', 'textarea[placeholder*="Message" i]',
            'textarea[placeholder*="Type" i]', 'div[contenteditable="true"]',
            '#chat-input', 'textarea[data-testid*="input" i]', 'textarea',
        ]
        for sel in selectors:
            try:
                await page.wait_for_selector(sel, timeout=timeout, state="visible")
                return sel
            except PTimeout:
                continue
        raise RuntimeError("Chat input not found")
    
    @staticmethod
    async def click_visible(page: Page, selector: str, timeout: int = 3000) -> bool:
        try:
            el = page.locator(selector).first
            if await el.is_visible(timeout=timeout):
                await el.click()
                return True
        except Exception:
            pass
        return False
    
    @staticmethod
    async def extract_text(page: Page, strategies: List[str]) -> Optional[str]:
        for strat in strategies:
            try:
                result = await page.evaluate(strat)
                if result and len(str(result).strip()) > 10:
                    return sanitize_response(str(result))
            except Exception:
                continue
        return None

class DDGAutomator(BaseAutomator):
    URL = "https://duckduckgo.com/?q=DuckDuckGo+AI+Chat&ia=chat"
    
    async def navigate(self, page: Page, model_key: str):
        log.debug(f"[DDG] Navigating | Model: {model_key}")
        await page.goto(self.URL, wait_until="domcontentloaded", timeout=cfg.PAGE_TIMEOUT)
        await human_delay(800, 1800)
        
        for txt in ["Accept", "Got it", "Continue", "Allow", "I Agree"]:
            if await self.click_visible(page, f'button:has-text("{txt}" i)', 1200):
                await human_delay(200, 500)
                break
        
        await self.wait_for_input(page, timeout=10000)
        
        if model_key and cfg.ENABLE_STEALTH:
            await self._select_model(page, model_key)
    
    async def _select_model(self, page: Page, model_key: str):
        try:
            btn = page.locator(
                'button[aria-label*="model" i], [data-testid*="model"], '
                'button:has-text("GPT"), button:has-text("Claude"), button:has-text("Llama")'
            ).first
            if await btn.is_visible(timeout=3000):
                await btn.click()
                await human_delay(400, 800)
                pattern = model_key.replace("-", "[ -_]").split("/")[-1]
                opt = page.locator('[role="option"], li, button').filter(
                    has_text=re.compile(pattern, re.I)
                ).first
                if await opt.is_visible(timeout=2000):
                    await opt.click()
                    log.debug(f"[DDG] Model selected: {model_key}")
                    await human_delay(300, 600)
        except Exception as e:
            log.debug(f"[DDG] Model selection skipped: {e}")
    
    async def send(self, page: Page, prompt: str):
        sel = await self.wait_for_input(page, timeout=5000)
        await page.locator(sel).first.click()
        await human_delay(100, 250)
        mod = "Meta+a" if CURRENT_PLATFORM == Platform.MACOS else "Control+a"
        await page.keyboard.press(mod)
        await page.keyboard.press("Delete")
        await human_delay(80, 200)
        await human_type(page, prompt)
        await human_delay(200, 500)
        await page.keyboard.press("Enter")
    
    async def wait_response(self, page: Page) -> str:
        log.debug("[DDG] Awaiting response...")
        
        for sel in ['[data-testid*="assistant" i]', '[class*="assistant" i]', '[role="article"]']:
            try:
                await page.wait_for_selector(sel, timeout=20000, state="visible")
                break
            except PTimeout:
                continue
        
        prev = ""
        stable = 0
        for _ in range(cfg.ANSWER_TIMEOUT // 1000):
            await asyncio.sleep(1)
            try:
                content = await page.evaluate("""() => {
                    const nodes = document.querySelectorAll(
                        '[data-testid*="message" i], [class*="assistant" i], article'
                    );
                    return Array.from(nodes).map(n => n.innerText).join('|||');
                }""")
                if content == prev and content.strip():
                    stable += 1
                    if stable >= 3:
                        break
                else:
                    stable = 0
                    prev = content
            except Exception:
                continue
        
        strategies = [
            """() => { const e = document.querySelectorAll('[data-testid*="assistant" i]'); return e.length ? e[e.length-1].innerText.trim() : null; }""",
            """() => { const c = [...document.querySelectorAll('[class*="assistant" i], [class*="response" i]')].filter(x => x.innerText.trim().length > 10); return c.length ? c[c.length-1].innerText.trim() : null; }""",
            """() => { const m = document.querySelectorAll('article, [role="article"], .message'); const v = [...m].filter(x => x.innerText.trim().length > 5); return v.length ? v[v.length-1].innerText.trim() : null; }""",
            """() => document.querySelector('main, #chat, [role="main"]')?.innerText.trim() || document.body.innerText.trim()""",
        ]
        
        result = await self.extract_text(page, strategies)
        if result:
            log.debug(f"[DDG] Extracted {len(result)} chars")
            return result
        raise RuntimeError("[DDG] Response extraction failed")
    
    async def ask(self, ctx: BrowserContext, page: Page, model: str, prompt: str,
                  context_text: Optional[str], new_session: bool) -> str:
        mk = DDG_INTERNAL.get(model, model)
        if new_session:
            await inject_stealth(page)
            await self.navigate(page, mk)
        else:
            try:
                await page.wait_for_selector("textarea, div[contenteditable='true']", 
                                            timeout=3000, state="visible")
            except PTimeout:
                log.warning("[DDG] Session stale, re-navigating")
                await self.navigate(page, mk)
        
        full_prompt = f"{context_text}\n\n{prompt}" if context_text else prompt
        await self.send(page, full_prompt)
        return await self.wait_response(page)

class LMSYSAutomator(BaseAutomator):
    URL = "https://chat.lmsys.org"
    
    async def navigate(self, page: Page):
        log.debug(f"[LMSYS] Navigating to {self.URL}")
        await page.goto(self.URL, wait_until="domcontentloaded", timeout=cfg.PAGE_TIMEOUT)
        await human_delay(1000, 2200)
        
        for sel in ['button:has-text("Direct Chat" i)', '[role="tab"]:has-text("Direct" i)']:
            if await self.click_visible(page, sel, 4000):
                log.debug("[LMSYS] Direct Chat activated")
                await human_delay(500, 1200)
                break
        
        await self.wait_for_input(page, timeout=15000)
        log.debug("[LMSYS] Interface ready")
    
    async def select_model(self, page: Page, model: str):
        canon = LMSYS_CANONICAL.get(model, model)
        log.debug(f"[LMSYS] Selecting: {canon}")
        
        for sel in ['select[aria-label*="model" i]', 'select[data-testid*="model"]']:
            try:
                dd = page.locator(sel).first
                if await dd.is_visible(timeout=2000):
                    await dd.select_option(label=re.compile(canon, re.I))
                    await human_delay(400, 800)
                    return
            except Exception:
                continue
        
        try:
            btn = page.locator('label:has-text("Model" i) ~ div button').first
            if await btn.is_visible(timeout=3000):
                await btn.click()
                await human_delay(400, 900)
                opt = page.locator('[role="option"]').filter(
                    has_text=re.compile(canon[:25], re.I)
                ).first
                if await opt.is_visible(timeout=3000):
                    await opt.click()
                    await human_delay(400, 800)
                    return
        except Exception as e:
            log.debug(f"[LMSYS] Dropdown failed: {e}")
        
        log.warning(f"[LMSYS] Could not select {canon}")
    
    async def send(self, page: Page, prompt: str):
        sel = await self.wait_for_input(page, timeout=5000)
        await page.locator(sel).first.click()
        await human_delay(100, 250)
        mod = "Meta+a" if CURRENT_PLATFORM == Platform.MACOS else "Control+a"
        await page.keyboard.press(mod)
        await page.keyboard.press("Delete")
        await human_type(page, prompt)
        await human_delay(200, 500)
        
        sent = False
        for bs in ['button:has-text("Send" i)', 'button[type="submit"]']:
            try:
                b = page.locator(bs).first
                if await b.is_visible(timeout=1500) and await b.is_enabled(timeout=500):
                    await b.click()
                    sent = True
                    break
            except Exception:
                pass
        if not sent:
            await page.keyboard.press("Enter")
    
    async def wait_response(self, page: Page) -> str:
        log.debug("[LMSYS] Awaiting generation...")
        
        try:
            await page.wait_for_selector(
                'button:has-text("Stop" i), #stop-btn', 
                timeout=10000, state="visible"
            )
            await page.wait_for_selector(
                'button:has-text("Stop" i), #stop-btn', 
                timeout=cfg.ANSWER_TIMEOUT, state="hidden"
            )
        except PTimeout:
            log.warning("[LMSYS] Generation timeout")
        
        await human_delay(400, 1000)
        
        strategies = [
            """() => { const c = document.querySelector('.chatbot, #chatbot'); if (!c) return null; const m = c.querySelectorAll('.message.bot, .response, [class*="assistant"]'); const v = [...m].filter(x => x.innerText.trim().length > 10); return v.length ? v[v.length-1].innerText.trim() : null; }""",
            """() => { const r = document.querySelectorAll('.prose, .markdown-body, [class*="output"]'); const v = [...r].filter(x => x.innerText.trim().length > 15); return v.length ? v[v.length-1].innerText.trim() : null; }""",
            """() => { const rows = document.querySelectorAll('[data-testid="row" i], .gr-row'); for (let i = rows.length - 1; i >= 0; i--) { const t = rows[i].innerText.trim(); if (t.length > 25 && !t.toLowerCase().includes('user:')) return t; } return null; }""",
            """() => document.body.innerText""",
        ]
        
        result = await self.extract_text(page, strategies)
        if result:
            log.debug(f"[LMSYS] Extracted {len(result)} chars")
            return result
        raise RuntimeError("[LMSYS] Response extraction failed")
    
    async def ask(self, ctx: BrowserContext, page: Page, model: str, prompt: str,
                  context_text: Optional[str], new_session: bool) -> str:
        if new_session:
            await inject_stealth(page)
            await self.navigate(page)
            await self.select_model(page, model)
        else:
            try:
                await page.wait_for_selector("textarea, div[contenteditable='true']", 
                                            timeout=3000, state="visible")
            except PTimeout:
                log.warning("[LMSYS] Session stale, re-navigating")
                await self.navigate(page)
                await self.select_model(page, model)
        
        full_prompt = f"{context_text}\n\n{prompt}" if context_text else prompt
        await self.send(page, full_prompt)
        return await self.wait_response(page)

# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST QUEUE & WORKER POOL
# ═══════════════════════════════════════════════════════════════════════════════
@dataclass
class QueuedJob:
    id: str
    model: str
    prompt: str
    cid: Optional[str]
    fresh: bool
    client_id: Optional[str]
    future: asyncio.Future = field(default_factory=asyncio.Future)
    priority: int = 5  # 1 = highest, 10 = lowest
    enqueued_at: float = field(default_factory=time.time)

class RequestQueue:
    """Priority queue with worker pool."""
    
    def __init__(self, orch: 'Orchestrator', workers: int):
        self.orch = orch
        self.workers = workers
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue(maxsize=cfg.QUEUE_MAX_SIZE)
        self._worker_tasks: List[asyncio.Task] = []
        self._running = False
    
    def start(self):
        self._running = True
        for i in range(self.workers):
            task = asyncio.create_task(self._worker_loop(i), name=f"worker-{i}")
            self._worker_tasks.append(task)
        log.info(f"✓ Worker pool started: {self.workers} workers")
    
    def stop(self):
        self._running = False
        for task in self._worker_tasks:
            task.cancel()
        self._worker_tasks.clear()
    
    async def submit(self, job: QueuedJob) -> JSON:
        try:
            self._queue.put_nowait((job.priority, time.time(), job))
            QUEUE_SIZE_GAUGE.set(self._queue.qsize())
            return await asyncio.wait_for(job.future, timeout=300)
        except asyncio.TimeoutError:
            raise RuntimeError("Job timed out in queue")
        except asyncio.QueueFull:
            raise RuntimeError("Server overloaded, queue full")
    
    async def _worker_loop(self, worker_id: int):
        while self._running:
            try:
                priority, ts, job = await self._queue.get()
                QUEUE_SIZE_GAUGE.set(self._queue.qsize())
                wait_time = time.time() - job.enqueued_at
                log.debug(f"[Worker-{worker_id}] Processing job {job.id[:8]} (waited {wait_time:.1f}s)")
                
                try:
                    result = await self.orch._execute_ask(
                        job.model, job.prompt, job.cid, job.fresh, job.client_id
                    )
                    job.future.set_result(result)
                except Exception as e:
                    job.future.set_exception(e)
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"[Worker-{worker_id}] Error: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# ORCHESTRATOR (The Brain)
# ═══════════════════════════════════════════════════════════════════════════════
class Orchestrator:
    def __init__(self):
        self.bm = BrowserManager()
        self.pool = SessionPool(cfg.MAX_SESSIONS)
        self.ddg = DDGAutomator(self.bm)
        self.lmsys = LMSYSAutomator(self.bm)
        self.limiter = RateLimiter(cfg.RATE_PER_MIN, cfg.RATE_BURST, cfg.GLOBAL_RATE)
        self.cache = ResponseCache(cfg.CACHE_MAX, cfg.CACHE_TTL) if cfg.CACHE_ENABLED else None
        self.cb_ddg = CircuitBreaker("ddg")
        self.cb_lmsys = CircuitBreaker("lmsys")
        self.queue = RequestQueue(self, cfg.WORKER_COUNT)
        self._start_time = time.time()
        self._running = False
        self._cleanup_task: Optional[asyncio.Task] = None
    
    async def startup(self):
        if self._running: return
        await self.bm.start()
        self.queue.start()
        mem_monitor.start()
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        self._running = True
        log.info("✓ Orchestrator v6.0 ULTRA initialized")
    
    async def shutdown(self):
        if not self._running: return
        self._running = False
        
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        self.queue.stop()
        mem_monitor.stop()
        await self.pool.close_all()
        await self.bm.close()
        if self.cache:
            await self.cache.clear()
        log.info("✓ Orchestrator shutdown complete")
    
    async def _cleanup_loop(self):
        while self._running:
            try:
                await asyncio.sleep(300)
                await self.pool.purge()
                # Update circuit breaker metrics
                CIRCUIT_STATE_GAUGE.labels(provider="ddg").set(self.cb_ddg.state.value)
                CIRCUIT_STATE_GAUGE.labels(provider="lmsys").set(self.cb_lmsys.state.value)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Cleanup error: {e}")
    
    def _resolve_provider(self, model: str) -> str:
        ml = model.lower().strip()
        if ml in MODEL_PROVIDER:
            return MODEL_PROVIDER[ml]
        for alias, prov in MODEL_PROVIDER.items():
            if alias in ml or ml in alias:
                return prov
        if any(k in ml for k in ["opus", "sonnet", "gemini", "llama-3", "mistral", "qwen", "wizardlm"]):
            return "lmsys"
        return "ddg"
    
    def _get_cb(self, provider: str) -> CircuitBreaker:
        return self.cb_ddg if provider == "ddg" else self.cb_lmsys
    
    async def ask(self, model: str, prompt: str, cid: Optional[str] = None,
                  fresh: bool = False, client_id: Optional[str] = None,
                  stream: bool = False) -> JSON:
        """Public API: either queue or direct execution."""
        if stream:
            # Streaming bypasses queue for lower latency
            return await self._execute_ask(model, prompt, cid, fresh, client_id)
        
        job = QueuedJob(
            id=str(uuid.uuid4()), model=model, prompt=prompt,
            cid=cid, fresh=fresh, client_id=client_id
        )
        return await self.queue.submit(job)
    
    async def _execute_ask(self, model: str, prompt: str, cid: Optional[str] = None,
                           fresh: bool = False, client_id: Optional[str] = None) -> JSON:
        """Core execution logic with circuit breaker."""
        model = model.lower().strip()
        provider = self._resolve_provider(model)
        cid = cid or str(uuid.uuid4())
        t0 = time.monotonic()
        
        log.info(f"→ Execute | {model}@{provider} | cid={cid[:8]}")
        
        # Rate limiting
        if not await self.limiter.acquire(client_id):
            latency = int((time.monotonic() - t0) * 1000)
            REQUEST_COUNT.labels(provider=provider, model=model, status="rate_limited").inc()
            return {
                "model": model, "response": "Rate limit exceeded. Retry later.",
                "status": "rate_limited", "provider": provider,
                "conversation_id": cid, "latency_ms": latency, "cached": False,
            }
        
        # Cache lookup
        conv = await self.pool.get_context(cid)
        cache_key = hash_request(model, prompt, conv.to_list() if conv else None)
        
        if not fresh and self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                latency = int((time.monotonic() - t0) * 1000)
                CACHE_HIT_COUNT.labels(provider=provider).inc()
                REQUEST_COUNT.labels(provider=provider, model=model, status="cached").inc()
                log.info(f"✓ Cache HIT | {model} | {latency}ms")
                return {
                    "model": model, "response": cached.response, "status": "success",
                    "provider": cached.provider, "conversation_id": cid,
                    "latency_ms": latency, "cached": True,
                    "meta": {"cache_age": cached.age},
                }
        
        # Circuit breaker protected execution
        cb = self._get_cb(provider)
        try:
            result = await cb.call(self._do_browser_work(model, prompt, provider, cid, fresh, conv))
            latency = int((time.monotonic() - t0) * 1000)
            result["latency_ms"] = latency
            REQUEST_LATENCY.labels(provider=provider, model=model).observe(latency / 1000)
            REQUEST_COUNT.labels(provider=provider, model=model, status="success").inc()
            log.info(f"✓ Success | {model} | {latency}ms")
            return result
        except Exception as e:
            REQUEST_COUNT.labels(provider=provider, model=model, status="error").inc()
            raise
    
    async def _do_browser_work(self, model: str, prompt: str, provider: str,
                               cid: str, fresh: bool, conv: Optional[Conversation]) -> JSON:
        """Browser interaction with retry logic."""
        sess = await self.pool.get(cid)
        is_new = sess is None or fresh
        
        har_path: Optional[Path] = None
        
        if is_new:
            if sess:
                await self.pool.remove(cid)
            ctx = await self.bm.new_context()
            page = await ctx.new_page()
            await page.set_default_timeout(cfg.PAGE_TIMEOUT)
            har_path = await debug_recorder.har_start(ctx, f"{provider}_{cid[:8]}")
        else:
            ctx, page = sess.context, sess.page
        
        try:
            await self.bm.ensure_healthy()
            
            ctx_text = conv.format() if conv and not fresh else None
            automator = self.ddg if provider == "ddg" else self.lmsys
            
            response_text = await automator.ask(ctx, page, model, prompt, ctx_text, is_new)
            
            # Update conversation
            if not fresh:
                await self.pool.add_message(cid, "user", prompt)
                await self.pool.add_message(cid, "assistant", response_text)
            
            # Cache
            if self.cache and not fresh:
                conv = await self.pool.get_context(cid)
                key = hash_request(model, prompt, conv.to_list() if conv else None)
                entry = CacheEntry(
                    response=response_text, model=model, provider=provider,
                    created_at=time.time(), ttl=cfg.CACHE_TTL, key=key
                )
                await self.cache.set(key, entry)
            
            # Session update
            new_conv = await self.pool.get_context(cid)
            new_sess = Session(
                context=ctx, page=page, provider=provider, model=model,
                conversation=Conversation() if is_new else (new_conv or Conversation()),
            )
            new_sess.req_count = (sess.req_count if sess else 0) + 1
            new_sess.last_used = time.time()
            await self.pool.put(cid, new_sess)
            
            await debug_recorder.har_stop(ctx, har_path)
            
            return {
                "model": model, "response": response_text, "status": "success",
                "provider": provider, "conversation_id": cid, "cached": False,
                "meta": {
                    "session_reused": not is_new,
                    "context_turns": len(new_conv.messages) // 2 if new_conv and new_conv.messages else 0,
                }
            }
            
        except Exception as e:
            log.error(f"✗ Browser work failed: {type(e).__name__}: {e}")
            await debug_recorder.screenshot(page, f"fail_{provider}_{cid[:8]}")
            await debug_recorder.har_stop(ctx, har_path)
            
            # Report proxy failure if used
            if cfg.PROXIES and hasattr(ctx, '_proxy') and ctx._proxy:
                await proxy_rotator.report_failure(ctx._proxy.get('server', 'unknown'))
            
            try:
                await ctx.close()
            except Exception:
                pass
            raise
    
    async def health(self) -> JSON:
        browser_ok = self.bm._healthy and self.bm._browser is not None
        mem_mb = mem_monitor._get_memory_mb() if hasattr(mem_monitor, '_get_memory_mb') else 0
        return {
            "status": "healthy" if browser_ok else "degraded",
            "version": "6.0.0-ultra",
            "platform": f"{platform.system()} {platform.release()}",
            "headless": cfg.HEADLESS,
            "browser_ready": browser_ok,
            "cache_enabled": cfg.CACHE_ENABLED,
            "active_sessions": len(self.pool._sessions),
            "uptime_sec": time.time() - self._start_time,
            "memory_mb": round(mem_mb, 2),
            "circuit_breakers": {
                "ddg": self.cb_ddg.status(),
                "lmsys": self.cb_lmsys.status(),
            },
            "queue_size": self.queue._queue.qsize() if hasattr(self.queue, '_queue') else 0,
            "checks": {
                "browser": "ok" if browser_ok else "fail",
                "session_pool": "ok",
                "rate_limiter": "ok",
                "cache": "ok" if cfg.CACHE_ENABLED else "disabled",
                "queue": "ok",
                "memory": "ok" if mem_mb < cfg.MEMORY_LIMIT_MB * 0.9 else "warning",
            }
        }
    
    async def model_info(self) -> JSON:
        return {
            "models": {
                alias: {
                    "provider": prov,
                    "canonical": LMSYS_CANONICAL.get(alias, DDG_INTERNAL.get(alias, alias)),
                    "multi_turn": True,
                    "context_window_turns": cfg.CONTEXT_TURNS,
                }
                for alias, prov in MODEL_PROVIDER.items()
            },
            "features": {
                "rate_limiting": self.limiter.stats(),
                "caching": await self.cache.stats() if self.cache else {"enabled": False},
                "stealth": cfg.ENABLE_STEALTH,
                "input_sanitization": cfg.SANITIZE_INPUT,
                "auto_recovery": True,
                "circuit_breaker": True,
                "queue_workers": cfg.WORKER_COUNT,
                "proxy_rotation": len(cfg.PROXIES) > 0,
                "debug_recording": cfg.DEBUG_MODE,
            }
        }

# ═══════════════════════════════════════════════════════════════════════════════
# FASTAPI APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════
orch = Orchestrator()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await orch.startup()
    yield
    await orch.shutdown()

app = FastAPI(
    title="🤖 AI Nexus Proxy v6.0 ULTRA",
    description=(
        "**The Ultimate Web AI Automation Engine**\n\n"
        "v6.0 Features: Circuit Breaker | Job Queue | WebSocket Streaming | "
        "Proxy Rotation | Memory Monitor | HAR Recording | Canvas Stealth"
    ),
    version="6.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ═══════════════════════════════════════════════════════════════════════════════
# DEPENDENCIES
# ═══════════════════════════════════════════════════════════════════════════════
async def optional_auth(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    if cfg.REQUIRE_AUTH and not auth_mgr.verify(x_api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return x_api_key

# ═══════════════════════════════════════════════════════════════════════════════
# API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_endpoint(_: Optional[str] = Depends(optional_auth)):
    return await orch.health()

@app.get("/models", tags=["System"])
async def models_endpoint(_: Optional[str] = Depends(optional_auth)):
    return await orch.model_info()

@app.post("/ask", response_model=AskResponse, status_code=200, tags=["Inference"])
async def ask_endpoint(req: AskRequest, request: Request, _: Optional[str] = Depends(optional_auth)):
    """
    Execute an AI query. Set `stream: true` for SSE streaming (use /ask/stream instead).
    """
    client_id = generate_client_id(request)
    try:
        result = await orch.ask(
            model=req.model, prompt=req.prompt, cid=req.conversation_id,
            fresh=req.fresh_context, client_id=client_id, stream=False
        )
        return AskResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Validation error: {e}")
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=f"Service unavailable: {e}")
    except RetryError as e:
        last_exc = e.last_attempt.exception() if e.last_attempt else "Unknown"
        raise HTTPException(status_code=503, detail=f"Retries exhausted: {last_exc}")
    except Exception as e:
        log.exception("Unhandled /ask error")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)[:200]}")

@app.post("/ask/stream", tags=["Inference"])
async def ask_stream_endpoint(req: AskRequest, request: Request, _: Optional[str] = Depends(optional_auth)):
    """
    Server-Sent Events streaming endpoint. Returns response tokens as they arrive.
    Note: Actual token streaming requires provider support; currently returns full response.
    """
    client_id = generate_client_id(request)
    
    async def event_generator() -> AsyncIterator[str]:
        try:
            result = await orch.ask(
                model=req.model, prompt=req.prompt, cid=req.conversation_id,
                fresh=req.fresh_context, client_id=client_id, stream=True
            )
            # Simulate streaming by splitting response
            response = result.get("response", "")
            words = response.split()
            
            yield f"data: {json.dumps({'type': 'start', 'model': req.model})}\n\n"
            
            for i, word in enumerate(words):
                chunk = " ".join(words[max(0, i-2):i+1])
                yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"
                await asyncio.sleep(0.02)  # Simulate typing speed
            
            yield f"data: {json.dumps({'type': 'end', 'full_response': response, 'latency_ms': result.get('latency_ms', 0)})}\n\n"
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )

@app.post("/batch", tags=["Inference"])
async def batch_endpoint(req: BatchRequest, request: Request, _: Optional[str] = Depends(optional_auth)):
    """
    Process multiple prompts in parallel. Max 10 per batch.
    """
    client_id = generate_client_id(request)
    if len(req.requests) > 10:
        raise HTTPException(status_code=400, detail="Max 10 requests per batch")
    
    async def process_single(r: AskRequest) -> Dict[str, Any]:
        try:
            result = await orch.ask(
                model=r.model, prompt=r.prompt, cid=r.conversation_id,
                fresh=r.fresh_context, client_id=client_id
            )
            return {"success": True, "data": result}
        except Exception as e:
            return {"success": False, "error": str(e), "model": r.model, "prompt": r.prompt[:50]}
    
    results = await asyncio.gather(*[process_single(r) for r in req.requests])
    return {
        "batch_size": len(req.requests),
        "results": results,
        "timestamp": time.time()
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, _: Optional[str] = Depends(optional_auth)):
    """
    WebSocket endpoint for real-time bidirectional chat.
    """
    await websocket.accept()
    cid = str(uuid.uuid4())
    log.info(f"WebSocket connected | cid={cid[:8]}")
    
    try:
        while True:
            data = await websocket.receive_json()
            model = data.get("model", "gpt-4o")
            prompt = data.get("prompt", "")
            fresh = data.get("fresh_context", False)
            
            if not prompt:
                await websocket.send_json({"error": "Empty prompt"})
                continue
            
            # Send intermediate status
            await websocket.send_json({"type": "status", "message": "Processing..."})
            
            result = await orch.ask(
                model=model, prompt=prompt, cid=cid,
                fresh=fresh, client_id=f"ws_{cid[:8]}"
            )
            
            await websocket.send_json({
                "type": "response",
                "model": result["model"],
                "response": result["response"],
                "status": result["status"],
                "latency_ms": result.get("latency_ms", 0),
            })
            
    except WebSocketDisconnect:
        log.info(f"WebSocket disconnected | cid={cid[:8]}")
    except Exception as e:
        log.error(f"WebSocket error: {e}")
        try:
            await websocket.close(code=1011)
        except Exception:
            pass

@app.delete("/session/{cid}", tags=["Session Management"])
async def delete_session(cid: str, _: Optional[str] = Depends(optional_auth)):
    await orch.pool.remove(cid)
    return {"status": "closed", "conversation_id": cid, "timestamp": time.time()}

@app.get("/cache/stats", tags=["Cache"])
async def cache_stats_endpoint(_: Optional[str] = Depends(optional_auth)):
    if not cfg.CACHE_ENABLED:
        raise HTTPException(status_code=404, detail="Caching disabled")
    return await orch.cache.stats()

@app.delete("/cache/clear", tags=["Cache"])
async def clear_cache_endpoint(_: Optional[str] = Depends(optional_auth)):
    if not cfg.CACHE_ENABLED:
        raise HTTPException(status_code=404, detail="Caching disabled")
    await orch.cache.clear()
    return {"status": "cleared", "timestamp": time.time()}

@app.get("/metrics", tags=["Monitoring"])
async def metrics_endpoint():
    if not cfg.METRICS_ENABLED:
        raise HTTPException(status_code=404, detail="Metrics disabled")
    return PlainTextResponse(generate_latest(registry), media_type=CONTENT_TYPE_LATEST)

@app.get("/debug/screenshots", tags=["Debug"])
async def list_screenshots(_: Optional[str] = Depends(optional_auth)):
    """List available debug screenshots."""
    if not cfg.DEBUG_MODE and not cfg.SCREENSHOT_ON_FAILURE:
        raise HTTPException(status_code=404, detail="Debug mode disabled")
    files = sorted(cfg.DEBUG_DIR.glob("screenshot_*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    return {
        "screenshots": [
            {"name": f.name, "size": f.stat().st_size, "modified": f.stat().st_mtime}
            for f in files[:50]
        ]
    }

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    log.exception(f"Unhandled: {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "detail": str(exc)[:300],
            "path": request.url.path,
            "timestamp": time.time()
        }
    )

# ═══════════════════════════════════════════════════════════════════════════════
# SIGNAL HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════
def setup_signals():
    loop = asyncio.get_event_loop()
    def handler(sig):
        log.info(f"Signal {sig.name} received, shutting down gracefully...")
        asyncio.create_task(orch.shutdown())
    for sig in (signal.SIGTERM, signal.SIGINT):
        if hasattr(signal, 'Signals'):
            try:
                loop.add_signal_handler(sig, lambda s=sig: handler(s))
            except NotImplementedError:
                pass

# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    setup_signals()
    
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            log.info("✓ Playwright Chromium ready")
    except Exception as e:
        log.warning(f"Playwright install: {e}")
    
    uvicorn.run(
        "main:app",
        host=cfg.HOST,
        port=cfg.PORT,
        reload=cfg.RELOAD,
        workers=cfg.WORKERS,
        log_level=cfg.LOG_LEVEL.lower(),
        access_log=True,
        loop="asyncio",
    )
