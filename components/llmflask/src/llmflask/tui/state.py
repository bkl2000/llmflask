# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
FOCUS_INPUT = 0
FOCUS_SESSIONS = 1

KEY_CTRL_N = 14
KEY_CTRL_D = 4
KEY_CTRL_E = 5
KEY_CTRL_S = 19
KEY_CTRL_P = 16
KEY_ESC = 27
KEY_PAGE_UP_FALLBACK = 339
KEY_PAGE_DOWN_FALLBACK = 338
KEY_PAGE_UP_SEQUENCE = "\x1b[5~"
KEY_PAGE_DOWN_SEQUENCE = "\x1b[6~"
KEY_PAGE_UP_CHAR_FALLBACK = "Ć"
KEY_HOME_FALLBACK = 262
KEY_END_FALLBACK = 360
SCROLL_PAGE_STEP = 10
SCROLL_LINE_STEP = 1


class TuiState:
    def __init__(
        self,
        host: str,
        port: int,
        user: str = "default",
        provider: str = "server",
        system_prompt: str | None = None,
    ):
        self.base = f"http://{host}:{port}"
        self.user = user
        self.provider = provider
        self.system_prompt = system_prompt
        self.sessions: list[dict] = []
        self.messages: list[dict] = []
        self.models: list[dict] = []
        self.current_session: int | None = None
        self.current_model: str = ""
        self.search_enabled: bool = False
        self.input_text: str = ""
        self.input_cursor: int = 0
        self.focus: int = FOCUS_INPUT
        self.session_idx: int = 0
        self.streaming: bool = False
        self.streamed_response: str = ""
        self.error: str = ""
        self.scroll_offset: int = 0
        self.chat_max_scroll: int = 0
        self.follow_tail: bool = True
        self.trace_enabled: bool = False
        self.local_db_path: str | None = None

    @property
    def direct_mode(self) -> bool:
        return self.provider != "server"
