# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import curses
import atexit
import json
import locale
import os
import re
import signal
import threading
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
import httpx

from .cli_http import REQUEST_HEADERS

from .config import DATABASE, MAX_CONTEXT_MESSAGES, PORT, prepare_database_path
from .database import (
    add_message,
    create_session,
    delete_session_for_user,
    ensure_user,
    get_messages,
    get_session_for_user,
    get_sessions,
    init_db,
    update_session_title_for_user,
)
from .services.api_keys import load_api_keys
from .services.exporter import export_md
from .services.model_providers import REMOTE_PROVIDERS, chat_stream, list_remote_models
from .text_utils import ensure_trailing_newline
from .tui.rendering import (
    _is_indented_code_line,
    _render_md_line,
    _render_message_lines,
    _wrap_text,
)
from .tui.state import (
    FOCUS_INPUT,
    FOCUS_SESSIONS,
    KEY_CTRL_D,
    KEY_CTRL_E,
    KEY_CTRL_N,
    KEY_CTRL_P,
    KEY_CTRL_S,
    KEY_END_FALLBACK,
    KEY_ESC,
    KEY_HOME_FALLBACK,
    KEY_PAGE_DOWN_FALLBACK,
    KEY_PAGE_DOWN_SEQUENCE,
    KEY_PAGE_UP_CHAR_FALLBACK,
    KEY_PAGE_UP_FALLBACK,
    KEY_PAGE_UP_SEQUENCE,
    SCROLL_LINE_STEP,
    SCROLL_PAGE_STEP,
    TuiState,
)


def _setup_locale():
    for candidate in ("", "C.UTF-8", "en_US.UTF-8"):
        try:
            locale.setlocale(locale.LC_ALL, candidate)
            return
        except Exception:
            continue

def _tui_trace_path() -> str:
    owner = os.environ.get("USER") or str(os.getuid())
    safe_owner = re.sub(r"[^A-Za-z0-9_.-]+", "_", owner).strip("._") or str(os.getuid())
    return f"/tmp/llmflask-tui-trace-{safe_owner[:64]}.log"


def _trace_state_fields(state: "TuiState | None") -> dict:
    if state is None:
        return {}
    return {
        "tui_user": state.user,
        "focus": state.focus,
        "streaming": state.streaming,
        "scroll_offset": state.scroll_offset,
        "chat_max_scroll": state.chat_max_scroll,
        "follow_tail": state.follow_tail,
        "current_session": state.current_session,
        "messages": len(state.messages),
        "input_len": len(state.input_text),
        "input_cursor": state.input_cursor,
        "provider": state.provider,
    }


def _trace_event(event: str, state: "TuiState | None" = None, **fields):
    if state is None or not state.trace_enabled:
        return
    payload = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "pid": os.getpid(),
        "event": event,
        **_trace_state_fields(state),
        **fields,
    }
    try:
        with open(_tui_trace_path(), "a", encoding="utf-8") as trace:
            trace.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception:
        pass


def _set_api_error(state: "TuiState | None", action: str, error: Exception):
    if state is not None:
        state.error = f"{action}: {error}"


def _api_get(url: str, state: "TuiState | None" = None, action: str = "GET") -> dict | list:
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        _set_api_error(state, action, e)
        return {}


def _api_post(url: str, data: dict, state: "TuiState | None" = None, action: str = "POST") -> dict:
    try:
        resp = httpx.post(url, json=data, headers=REQUEST_HEADERS, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        _set_api_error(state, action, e)
        return {}


def _api_delete(url: str, state: "TuiState | None" = None, action: str = "DELETE") -> bool:
    try:
        resp = httpx.delete(url, headers=REQUEST_HEADERS, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        _set_api_error(state, action, e)
        return False


def _user_query(state: "TuiState") -> str:
    return urlencode({"user": state.user})


def _direct_session_title(state: TuiState) -> str:
    provider = REMOTE_PROVIDERS.get(state.provider)
    label = provider.label if provider else state.provider
    return f"Direct: {label}"


def _direct_key_error(state: TuiState) -> str:
    provider = REMOTE_PROVIDERS[state.provider]
    return f"{provider.label} API key is not set. Set env or LLMFLASK_API_KEYS_FILE/api.txt."


def _direct_db_path(state: TuiState) -> str:
    if state.local_db_path is None:
        state.local_db_path = prepare_database_path(DATABASE)
        init_db(state.local_db_path)
    return state.local_db_path


def _direct_load_messages(state: TuiState, session_id: int):
    db_path = _direct_db_path(state)
    if not get_session_for_user(db_path, session_id, state.user):
        state.current_session = None
        state.messages = []
        state.error = "Could not load local session."
        return
    state.current_session = session_id
    state.messages = get_messages(db_path, session_id)
    state.scroll_offset = 0
    state.chat_max_scroll = 0
    state.follow_tail = True
    _trace_event("direct_session_switch", state, session_id=session_id)


def _load_models(state: TuiState):
    if state.direct_mode:
        provider = REMOTE_PROVIDERS[state.provider]
        api_key = load_api_keys().get(provider.api_key_name, "")
        if not api_key and provider.requires_auth:
            state.models = []
            state.current_model = ""
            state.error = _direct_key_error(state)
            return
        state.models = list_remote_models(provider, api_key)
        if not state.models:
            state.current_model = ""
            state.error = f"No {provider.label} models loaded."
            return
        if not state.current_model or state.current_model not in [m.get("name") for m in state.models]:
            state.current_model = state.models[0].get("name", "")
        return

    data = _api_get(f"{state.base}/api/models", state, "Loading models")
    state.models = data if isinstance(data, list) else []
    if not state.current_model or state.current_model not in [m.get("name") for m in state.models]:
        if state.models:
            state.current_model = state.models[0].get("name", "")


def _current_model_label(state: TuiState) -> str:
    for model in state.models:
        if model.get("name") == state.current_model:
            return model.get("label") or state.current_model
    return state.current_model


def _ensure_user(state: TuiState):
    if state.direct_mode:
        ensure_user(_direct_db_path(state), state.user)
        return
    data = _api_post(f"{state.base}/api/users", {"name": state.user}, state, "Creating user")
    if not data.get("name"):
        state.error = f"Could not create user: {state.user}"


def _load_sessions(state: TuiState):
    if state.direct_mode:
        state.sessions = get_sessions(_direct_db_path(state), state.user)
        if state.current_session:
            for idx, session in enumerate(state.sessions):
                if session.get("id") == state.current_session:
                    state.session_idx = idx
                    break
            else:
                state.session_idx = 0
        else:
            state.session_idx = 0
        return
    data = _api_get(f"{state.base}/api/sessions?{_user_query(state)}", state, "Loading sessions")
    state.sessions = data if isinstance(data, list) else []


def _new_session(state: TuiState):
    if state.direct_mode:
        sid = create_session(
            _direct_db_path(state),
            user=state.user,
            title=_direct_session_title(state),
            model=state.current_model,
        )
        state.current_session = sid
        state.messages = []
        state.streamed_response = ""
        state.streaming = False
        state.session_idx = 0
        state.scroll_offset = 0
        state.chat_max_scroll = 0
        state.follow_tail = True
        state.error = "Local Direct Chat created."
        _load_sessions(state)
        _trace_event("direct_session_new", state, session_id=sid)
        return

    data = _api_post(
        f"{state.base}/api/sessions?{_user_query(state)}",
        {"model": state.current_model},
        state,
        "Creating session",
    )
    sid = data.get("id")
    if sid:
        state.current_session = sid
        state.messages = []
        state.session_idx = 0
        state.scroll_offset = 0
        state.chat_max_scroll = 0
        state.follow_tail = True
        _trace_event("session_new", state, session_id=sid)
    else:
        state.error = "Could not create new session."
    _load_sessions(state)


def _delete_session(state: TuiState):
    if state.direct_mode:
        if not state.sessions or state.session_idx >= len(state.sessions):
            state.error = "No local session to delete."
            return
        sid = state.sessions[state.session_idx]["id"]
        if not delete_session_for_user(_direct_db_path(state), sid, state.user):
            state.error = "Could not delete local session."
            return
        if state.current_session == sid:
            state.current_session = None
            state.messages = []
        _load_sessions(state)
        if state.sessions:
            state.session_idx = min(state.session_idx, len(state.sessions) - 1)
            if state.current_session is None:
                _switch_session(state, state.sessions[state.session_idx]["id"])
        else:
            state.session_idx = 0
        _trace_event("direct_session_delete", state, session_id=sid)
        return
    if state.sessions and state.session_idx < len(state.sessions):
        sid = state.sessions[state.session_idx]["id"]
        deleted = _api_delete(f"{state.base}/api/sessions/{sid}?{_user_query(state)}", state, "Deleting session")
        if not deleted:
            state.error = "Could not delete session."
            return
        if state.current_session == sid:
            state.current_session = None
            state.messages = []
    _load_sessions(state)
    if state.sessions:
        state.session_idx = min(state.session_idx, len(state.sessions) - 1)
        if state.current_session is None:
            _switch_session(state, state.sessions[state.session_idx]["id"])
    else:
        state.session_idx = 0


def _switch_session(state: TuiState, sid: int):
    if state.direct_mode:
        _direct_load_messages(state, sid)
        return
    state.current_session = sid
    data = _api_get(f"{state.base}/api/chat/{sid}/messages?{_user_query(state)}", state, "Loading session")
    if isinstance(data, list):
        state.messages = data
        state.scroll_offset = 0
        state.chat_max_scroll = 0
        state.follow_tail = True
        _trace_event("session_switch", state, session_id=sid)
    else:
        state.current_session = None
        state.messages = []
        state.error = "Could not load session."


def _open_initial_session(state: TuiState):
    if state.direct_mode:
        if state.sessions:
            state.current_session = state.sessions[0]["id"]
            _switch_session(state, state.current_session)
        else:
            state.current_session = None
            state.messages = []
        return
    if state.sessions:
        state.current_session = state.sessions[0]["id"]
        _switch_session(state, state.current_session)
    else:
        state.current_session = None
        state.messages = []


def _send_message(state: TuiState):
    if not state.input_text.strip() or state.streaming:
        return
    if not state.current_session:
        state.error = "Create a chat first with Ctrl+N."
        return
    if not state.current_model:
        state.error = "No model available."
        return

    msg = state.input_text.strip()
    session_id = state.current_session
    model = state.current_model
    state.messages.append({"role": "user", "content": msg})
    state.input_text = ""
    state.input_cursor = 0
    state.streaming = True
    state.streamed_response = ""
    state.follow_tail = True
    _trace_event("stream_start", state, model=model, direct=state.direct_mode)

    def worker():
        try:
            if state.direct_mode:
                db_path = _direct_db_path(state)
                persisted_before = get_messages(db_path, session_id)
                add_message(db_path, session_id, "user", msg)
                if len(persisted_before) == 0:
                    title = msg[:60] + ("..." if len(msg) > 60 else "")
                    update_session_title_for_user(db_path, session_id, state.user, title)
                history = [
                    {"role": m["role"], "content": m["content"]}
                    for m in get_messages(db_path, session_id)
                ]
                if state.system_prompt:
                    history.insert(0, {"role": "system", "content": state.system_prompt})
                if len(history) > MAX_CONTEXT_MESSAGES:
                    history = history[-MAX_CONTEXT_MESSAGES:]
                for token in chat_stream(history, model):
                    state.streamed_response += token
                if state.current_session == session_id:
                    state.streamed_response = ensure_trailing_newline(state.streamed_response)
                    if state.streamed_response:
                        add_message(db_path, session_id, "assistant", state.streamed_response)
                    state.messages = get_messages(db_path, session_id)
                    _load_sessions(state)
            else:
                with httpx.Client(timeout=httpx.Timeout(300, connect=10)) as client:
                    with client.stream(
                        "POST",
                        f"{state.base}/api/chat?{_user_query(state)}",
                        headers=REQUEST_HEADERS,
                        json={
                            "session_id": session_id,
                            "message": msg,
                            "model": model,
                            "search": state.search_enabled,
                            "system_prompt": state.system_prompt,
                        },
                    ) as resp:
                        resp.raise_for_status()
                        for line in resp.iter_lines():
                            if not line.startswith("data: "):
                                continue
                            try:
                                chunk = json.loads(line[6:])
                            except json.JSONDecodeError:
                                continue
                            if chunk.get("done"):
                                break
                            state.streamed_response += chunk.get("token", "")
                if state.current_session == session_id:
                    state.messages.append({"role": "assistant", "content": state.streamed_response})
                _load_sessions(state)
            _trace_event("stream_done", state, response_len=len(state.streamed_response))
        except Exception as e:
            _trace_event("stream_error", state, error=str(e))
            state.error = str(e)
        state.streaming = False

    t = threading.Thread(target=worker, daemon=True)
    t.start()


def draw(stdscr, state):
    h, w = stdscr.getmaxyx()
    sidebar_w = max(24, w // 4)

    if sidebar_w >= w - 1 or h < 4:
        return

    stdscr.erase()

    for y in range(h):
        stdscr.addch(y, sidebar_w - 1, curses.ACS_VLINE)
    stdscr.hline(0, 0, curses.ACS_HLINE, sidebar_w - 1)
    stdscr.addstr(0, 0, " LLMs"[:sidebar_w - 2], curses.A_BOLD | curses.A_REVERSE)

    shown = 0
    for i, s in enumerate(state.sessions):
        if 2 + shown >= h - 8:
            break
        y = 2 + shown
        title = s.get("title", "Chat")[:sidebar_w - 4]
        prefix = ">" if s.get("id") == state.current_session else " "
        attr = curses.A_BOLD if s.get("id") == state.current_session else curses.A_NORMAL
        if state.focus == FOCUS_SESSIONS and i == state.session_idx:
            attr |= curses.A_REVERSE
        stdscr.addstr(y, 1, f"{prefix} {title}"[:sidebar_w - 3], attr)
        shown += 1

    sep_y = h - 7
    stdscr.hline(sep_y, 0, curses.ACS_HLINE, sidebar_w - 1)
    mdl = _current_model_label(state) or "---"
    search_label = "ON" if state.search_enabled else "OFF"
    status_label = "STREAMING..." if state.streaming else ""
    line_width = sidebar_w - 3
    search_status = f"  S: {search_label}"
    model_width = max(0, line_width - len("M: ") - len(search_status))
    stdscr.addstr(
        sep_y + 1,
        1,
        f"M: {mdl[:model_width]}{search_status}"[:line_width],
    )
    if status_label:
        stdscr.addstr(sep_y + 2, 1, status_label[:sidebar_w - 3], curses.A_BOLD)
    else:
        stdscr.addstr(sep_y + 2, 1, "^N=New ^D=Del ^E=MD")
    stdscr.addstr(sep_y + 3, 1, "^S=Search ^P=Model" if not status_label else " " * (sidebar_w - 3))
    stdscr.addstr(sep_y + 4, 1, "Tab=Liste  Esc=Input")

    chat_x = sidebar_w + 1
    chat_w = w - chat_x - 1

    visible = state.messages
    if state.streaming:
        visible = visible + [{"role": "assistant", "content": state.streamed_response}]

    # Multi-line wrapping with markdown rendering
    lines: list[tuple[int, str]] = []  # (attr, text)
    for m in visible:
        role = m["role"].upper()
        role_attr = curses.A_BOLD if role == "ASSISTANT" else curses.A_NORMAL
        for md_attr, md_text in _render_message_lines(m["content"], chat_w - 2):
            combined = role_attr | md_attr if role_attr != curses.A_NORMAL else md_attr
            lines.append((combined, f"  {md_text}"))

    if not lines and not state.current_session:
        lines.append((curses.A_NORMAL, "  No chats. Press Ctrl+N to create one."))

    # Scroll handling: offset is the first visible line from the top.
    chat_h = h - 4
    max_offset = max(0, len(lines) - chat_h)
    state.chat_max_scroll = max_offset
    if state.follow_tail:
        state.scroll_offset = max_offset
    else:
        state.scroll_offset = min(max(0, state.scroll_offset), max_offset)
        if state.scroll_offset >= max_offset:
            state.follow_tail = True

    _trace_event(
        "draw",
        state,
        screen_h=h,
        screen_w=w,
        chat_h=chat_h,
        chat_w=chat_w,
        wrapped_lines=len(lines),
        max_offset=max_offset,
    )

    start = state.scroll_offset
    visible_lines = lines[start:start + chat_h]

    for i, (attr, line_text) in enumerate(visible_lines):
        stdscr.addstr(i, chat_x, line_text[:chat_w - 1], attr)

    if state.error:
        stdscr.addstr(h - 3, 0, state.error[:w - 1], curses.A_REVERSE)
    elif len(lines) > chat_h:
        pct = int(state.scroll_offset / max(max_offset, 1) * 100)
        indicator = f"  {pct}%  ↑/↓ PgUp/PgDn=Scroll"
        stdscr.addstr(h - 3, chat_x, indicator[:chat_w - 1], curses.A_REVERSE)

    stdscr.hline(h - 2, 0, curses.ACS_HLINE, w)
    prompt = "> "
    input_width = max(1, w - len(prompt) - 1)
    state.input_cursor = min(max(0, state.input_cursor), len(state.input_text))
    input_start = 0
    if state.input_cursor > input_width:
        input_start = state.input_cursor - input_width
    visible_input = state.input_text[input_start:input_start + input_width]
    attr = curses.A_REVERSE if state.focus == FOCUS_INPUT else curses.A_NORMAL
    stdscr.addstr(h - 1, 0, f"{prompt}{visible_input}"[:w - 1], attr)

    # Cursor positionieren
    if state.focus == FOCUS_INPUT:
        cursor_x = len(prompt) + state.input_cursor - input_start
        stdscr.move(h - 1, cursor_x if cursor_x < w else w - 1)

    stdscr.refresh()


def _toggle_search(state):
    if state.direct_mode:
        state.search_enabled = False
        state.error = "Direct mode: Search is not available."
        return
    state.search_enabled = not state.search_enabled
    state.error = f"Search {'ON' if state.search_enabled else 'OFF'}"


def _cycle_model(state):
    names = [m.get("name", "") for m in state.models]
    if state.current_model in names:
        idx = names.index(state.current_model)
        idx = (idx + 1) % len(names)
        state.current_model = names[idx]
        state.error = f"Model: {_current_model_label(state)}"


def _export_url(state):
    _export_markdown_file(state)


def _session_title(state: TuiState) -> str:
    for session in state.sessions:
        if session.get("id") == state.current_session:
            return session.get("title") or "Chat"
    return _direct_session_title(state) if state.direct_mode else "Chat"


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip(".-")
    return slug[:64] or "chat"


def _unique_export_path(directory: Path, session_id: int | str | None, title: str) -> Path:
    session_part = session_id if session_id is not None else "local"
    base = f"llmflask-chat-{session_part}-{_slug(title)}"
    path = directory / f"{base}.md"
    counter = 2
    while path.exists():
        path = directory / f"{base}-{counter}.md"
        counter += 1
    return path


def _export_markdown_file(state: TuiState):
    if not state.current_session and not state.messages:
        state.error = "MD: No active chat."
        return

    title = _session_title(state)
    path = _unique_export_path(Path.cwd(), state.current_session, title)
    try:
        path.write_text(export_md(state.messages, title), encoding="utf-8")
    except Exception as e:
        state.error = f"MD export failed: {e}"
        return
    state.error = f"MD: {path}"


def _focus_sessions(state):
    state.focus = FOCUS_SESSIONS
    for i, s in enumerate(state.sessions):
        if s.get("id") == state.current_session:
            state.session_idx = i
            return
    state.session_idx = 0


def _normalize_ch(ch):
    if ch == KEY_PAGE_UP_SEQUENCE:
        return KEY_PAGE_UP_FALLBACK, ""
    if ch == KEY_PAGE_DOWN_SEQUENCE:
        return KEY_PAGE_DOWN_FALLBACK, ""
    if ch == KEY_PAGE_UP_CHAR_FALLBACK:
        return KEY_PAGE_UP_FALLBACK, ""
    if isinstance(ch, str) and len(ch) == 1:
        return ord(ch), ch
    if isinstance(ch, int):
        return ch, chr(ch) if 32 <= ch <= 126 else ""
    return -1, ""


def _is_page_up(code: int) -> bool:
    return code in (
        getattr(curses, "KEY_PPAGE", KEY_PAGE_UP_FALLBACK),
        getattr(curses, "KEY_PREVIOUS", KEY_PAGE_UP_FALLBACK),
        getattr(curses, "KEY_SPREVIOUS", KEY_PAGE_UP_FALLBACK),
        KEY_PAGE_UP_FALLBACK,
    )


def _is_page_down(code: int) -> bool:
    return code in (
        getattr(curses, "KEY_NPAGE", KEY_PAGE_DOWN_FALLBACK),
        getattr(curses, "KEY_NEXT", KEY_PAGE_DOWN_FALLBACK),
        getattr(curses, "KEY_SNEXT", KEY_PAGE_DOWN_FALLBACK),
        KEY_PAGE_DOWN_FALLBACK,
    )


def _is_home(code: int) -> bool:
    return code in (getattr(curses, "KEY_HOME", KEY_HOME_FALLBACK), KEY_HOME_FALLBACK)


def _is_end(code: int) -> bool:
    return code in (getattr(curses, "KEY_END", KEY_END_FALLBACK), KEY_END_FALLBACK)


def _key_name(code: int) -> str:
    names = (
        ("KEY_PPAGE", getattr(curses, "KEY_PPAGE", None)),
        ("KEY_NPAGE", getattr(curses, "KEY_NPAGE", None)),
        ("KEY_PREVIOUS", getattr(curses, "KEY_PREVIOUS", None)),
        ("KEY_NEXT", getattr(curses, "KEY_NEXT", None)),
        ("KEY_SPREVIOUS", getattr(curses, "KEY_SPREVIOUS", None)),
        ("KEY_SNEXT", getattr(curses, "KEY_SNEXT", None)),
        ("KEY_HOME", getattr(curses, "KEY_HOME", None)),
        ("KEY_END", getattr(curses, "KEY_END", None)),
        ("KEY_UP", getattr(curses, "KEY_UP", None)),
        ("KEY_DOWN", getattr(curses, "KEY_DOWN", None)),
        ("KEY_ESC", KEY_ESC),
    )
    for name, value in names:
        if value == code:
            return name
    return str(code)


def _scroll_page_up(state: TuiState):
    state.follow_tail = False
    state.scroll_offset = max(0, state.scroll_offset - SCROLL_PAGE_STEP)


def _scroll_page_down(state: TuiState):
    state.scroll_offset = min(state.chat_max_scroll, state.scroll_offset + SCROLL_PAGE_STEP)
    if state.scroll_offset >= state.chat_max_scroll:
        state.follow_tail = True


def _scroll_line_up(state: TuiState):
    state.follow_tail = False
    state.scroll_offset = max(0, state.scroll_offset - SCROLL_LINE_STEP)


def _scroll_line_down(state: TuiState):
    state.scroll_offset = min(state.chat_max_scroll, state.scroll_offset + SCROLL_LINE_STEP)
    if state.scroll_offset >= state.chat_max_scroll:
        state.follow_tail = True


def _scroll_home(state: TuiState):
    state.follow_tail = False
    state.scroll_offset = 0


def _scroll_end(state: TuiState):
    state.scroll_offset = state.chat_max_scroll
    state.follow_tail = True


def _read_tui_key(stdscr):
    ch = stdscr.get_wch()
    code, _ = _normalize_ch(ch)
    if code != KEY_ESC:
        return ch

    sequence = [ch]
    restore_input_mode = None
    try:
        if hasattr(stdscr, "timeout"):
            stdscr.timeout(25)
            restore_input_mode = lambda: stdscr.timeout(-1)
        else:
            stdscr.nodelay(True)
            restore_input_mode = lambda: stdscr.nodelay(False)
        for _ in range(3):
            try:
                sequence.append(stdscr.get_wch())
            except curses.error:
                break
    finally:
        if restore_input_mode is not None:
            restore_input_mode()

    joined = "".join(part for part in sequence if isinstance(part, str))
    if joined == KEY_PAGE_UP_SEQUENCE:
        return KEY_PAGE_UP_SEQUENCE
    if joined == KEY_PAGE_DOWN_SEQUENCE:
        return KEY_PAGE_DOWN_SEQUENCE
    return ch


CONTROL_INPUT = {
    KEY_CTRL_N: _new_session,
    KEY_CTRL_E: _export_url,
    KEY_CTRL_S: _toggle_search,
    KEY_CTRL_P: _cycle_model,
    9: _focus_sessions,
}

CONTROL_SESSIONS = {
    KEY_CTRL_D: _delete_session,
    KEY_ESC: lambda s: setattr(s, "focus", FOCUS_INPUT),
    9: lambda s: setattr(s, "focus", FOCUS_INPUT),
}


def _handle_global_key(state: TuiState, code: int) -> str | None:
    actions = (
        (_is_page_up, _scroll_page_up, "page_up"),
        (_is_page_down, _scroll_page_down, "page_down"),
        (_is_home, _scroll_home, "home"),
        (_is_end, _scroll_end, "end"),
    )
    for matches, action, name in actions:
        if matches(code):
            action(state)
            return name

    input_scroll = {
        curses.KEY_UP: (_scroll_line_up, "line_up"),
        curses.KEY_DOWN: (_scroll_line_down, "line_down"),
    }
    if state.focus == FOCUS_INPUT and code in input_scroll:
        action, name = input_scroll[code]
        action(state)
        return name
    return None


def _handle_input_key(state: TuiState, code: int, char: str) -> str:
    if code in (curses.KEY_ENTER, 10, 13):
        if state.input_text.strip():
            _send_message(state)
            state.scroll_offset = 0
            state.follow_tail = True
            return "send_message"
        return "enter_empty"
    if code == curses.KEY_LEFT:
        state.input_cursor = max(0, state.input_cursor - 1)
        return "cursor_left"
    if code == curses.KEY_RIGHT:
        state.input_cursor = min(len(state.input_text), state.input_cursor + 1)
        return "cursor_right"
    if code in (curses.KEY_BACKSPACE, 127, 263):
        if state.input_cursor > 0:
            state.input_text = (
                state.input_text[:state.input_cursor - 1]
                + state.input_text[state.input_cursor:]
            )
            state.input_cursor -= 1
        return "backspace"
    if code in CONTROL_INPUT:
        CONTROL_INPUT[code](state)
        return "control_input"
    if char and char.isprintable():
        state.input_text = (
            state.input_text[:state.input_cursor]
            + char
            + state.input_text[state.input_cursor:]
        )
        state.input_cursor += len(char)
        return "text_input"
    if code >= 128:
        state.error = f"Key ignored: {code}"
        return "ignored_key"
    return "noop_input"


def _handle_session_key(state: TuiState, code: int) -> str:
    if code == curses.KEY_UP:
        state.session_idx = max(0, state.session_idx - 1)
        return "session_up"
    if code == curses.KEY_DOWN:
        state.session_idx = min(len(state.sessions) - 1, state.session_idx + 1) if state.sessions else 0
        return "session_down"
    if code in (10, 13):
        if state.sessions:
            _switch_session(state, state.sessions[state.session_idx]["id"])
            state.focus = FOCUS_INPUT
            return "session_enter"
        return "session_enter_empty"
    if code in CONTROL_SESSIONS:
        CONTROL_SESSIONS[code](state)
        return "control_sessions"
    return "noop_sessions"


def _handle_key(state: TuiState, ch: int | str) -> str | None:
    code, char = _normalize_ch(ch)
    before = {
        "before_focus": state.focus,
        "before_streaming": state.streaming,
        "before_scroll_offset": state.scroll_offset,
        "before_chat_max_scroll": state.chat_max_scroll,
        "before_follow_tail": state.follow_tail,
        "before_input_len": len(state.input_text),
        "before_input_cursor": state.input_cursor,
    }

    def finish(action: str, result=None):
        _trace_event(
            "key_action",
            state,
            action=action,
            raw=repr(ch),
            code=code,
            char=repr(char),
            key_name=_key_name(code),
            **before,
        )
        return result

    if code == -1:
        return finish("ignored_invalid")

    if code == 3:
        return finish("quit", "quit")

    state.error = ""

    global_action = _handle_global_key(state, code)
    if global_action is not None:
        return finish(global_action)

    if state.streaming:
        return finish("ignored_streaming")

    if state.focus == FOCUS_INPUT:
        return finish(_handle_input_key(state, code, char))

    if state.focus == FOCUS_SESSIONS:
        return finish(_handle_session_key(state, code))

    return finish("noop")


def _restore_terminal():
    old_handler = signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        for cleanup in (curses.nocbreak, curses.echo, curses.endwin):
            try:
                cleanup()
            except BaseException:
                pass
        try:
            os.system("stty sane 2>/dev/null || true")
        except BaseException:
            pass
    finally:
        signal.signal(signal.SIGINT, old_handler)


def _run_curses(main_loop):
    stdscr = None
    try:
        stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        stdscr.keypad(True)
        try:
            curses.start_color()
        except BaseException:
            pass
        return main_loop(stdscr)
    finally:
        if stdscr is not None:
            try:
                stdscr.keypad(False)
            except BaseException:
                pass
        _restore_terminal()


def run_tui(
    host: str = "127.0.0.1",
    port: int = PORT,
    user: str = "default",
    trace: bool = False,
    provider: str = "server",
    system_prompt: str | None = None,
):
    atexit.register(_restore_terminal)
    _setup_locale()
    os.system("stty -ixon 2>/dev/null || true")
    state = TuiState(host, port, user, provider, system_prompt)
    state.trace_enabled = trace

    def main_loop(stdscr):
        curses.curs_set(2)
        stdscr.nodelay(False)

        _load_models(state)
        _ensure_user(state)
        _load_sessions(state)
        _open_initial_session(state)
        if state.trace_enabled:
            state.error = f"Trace: {_tui_trace_path()}"
        _trace_event("tui_start", state, host=host, port=port, term=os.environ.get("TERM", ""))

        while True:
            try:
                if state.streaming:
                    stdscr.nodelay(True)
                draw(stdscr, state)
                try:
                    ch = _read_tui_key(stdscr)
                except KeyboardInterrupt:
                    _trace_event("tui_stop", state, reason="ctrl_c", streaming=state.streaming)
                    break
                except curses.error:
                    ch = -1
                if state.streaming:
                    stdscr.nodelay(False)
            except Exception as e:
                state.error = f"UI: {e}"
                continue

            read_code, read_char = _normalize_ch(ch)
            _trace_event(
                "key_read",
                state,
                raw=repr(ch),
                code=read_code,
                char=repr(read_char),
                key_name=_key_name(read_code),
            )
            if _handle_key(state, ch) == "quit":
                _trace_event("tui_stop", state, reason="quit")
                break

    try:
        _run_curses(main_loop)
    except KeyboardInterrupt:
        _trace_event("tui_stop", state, reason="keyboard_interrupt")
        pass
