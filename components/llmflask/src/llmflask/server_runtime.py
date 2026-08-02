# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import os


def gunicorn_options(host: str, port: int) -> dict:
    return {
        "bind": f"{host}:{port}",
        "workers": int(os.getenv("LLMFLASK_GUNICORN_WORKERS", "1")),
        "threads": int(os.getenv("LLMFLASK_GUNICORN_THREADS", "16")),
        "worker_class": "gthread",
        "timeout": int(os.getenv("LLMFLASK_GUNICORN_TIMEOUT", "600")),
    }


def gunicorn_base_application():
    from gunicorn.app.base import BaseApplication
    return BaseApplication


def run_gunicorn_app(app, host: str, port: int):
    base_application = gunicorn_base_application()

    class LLMFlaskGunicornApplication(base_application):
        def __init__(self, flask_app, options):
            self.flask_app = flask_app
            self.options = options
            super().__init__()

        def load_config(self):
            for key, value in self.options.items():
                if key in self.cfg.settings and value is not None:
                    self.cfg.set(key.lower(), value)

        def load(self):
            return self.flask_app

    LLMFlaskGunicornApplication(app, gunicorn_options(host, port)).run()
