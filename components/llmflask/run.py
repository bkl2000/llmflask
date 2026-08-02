# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
from llmflask.app import create_app
from llmflask.config import HOST, PORT

app = create_app()

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
