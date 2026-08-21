SHELL := /usr/bin/env bash

.DEFAULT_GOAL := help

.PHONY: help all test setup-test-env install-ai install-ai-minimal install-searxng install-opencode install-sandbox install-dev install-server install-tools install-standalone llmflask-venv client-tgz standalone clean fix-permissions

fix-permissions:
	./tools/fix-permissions.sh

help:
	@echo "Targets:"
	@echo ""
	@echo "  Recommended first installation:"
	@echo "  make all             Ollama + small model + installed standalone (no Docker)"
	@echo ""
	@echo "  For development:"
	@echo "  make install-dev     Python venv, test deps, sandbox image (needs apt, Docker)"
	@echo "  make test            Run all project tests"
	@echo ""
	@echo "  For server:"
	@echo "  make install-server  AI stack + sandbox image + LLMFlask venv (needs Docker)"
	@echo "  make install-ai      Full AI stack (Docker for SearXNG/sandbox, not Ollama)"
	@echo "  make install-ai-minimal  Ollama + llama3.2:3b only (quick test, no SearXNG/OpenCode/sandbox)"
	@echo ""
	@echo "  For client:"
	@echo "  make standalone      Build single binary for current architecture"
	@echo "  make install-standalone  Build and install the binary to ~/bin"
	@echo "  make client-tgz      Build offline venv package"
	@echo ""
	@echo "  Individual:"
	@echo "  make install-sandbox Build Docker sandbox image"
	@echo "  make llmflask-venv   Prepare LLMFlask venv"
	@echo "  make setup-test-env  Install test dependencies (needs apt)"
	@echo "  make install-tools   Install llm-* convenience scripts"
	@echo "  make clean           Remove generated build artifacts"

all: fix-permissions
	@echo "make all installs and manages Ollama as a system service and may request sudo."
	$(MAKE) install-ai-minimal
	$(MAKE) standalone
	$(MAKE) install-tools
	@echo ""
	@echo "Local installation ready. Ollama is running and LLMFlask is installed."
	@echo "  Check Ollama:  systemctl is-active ollama && ollama list"
	@echo "  Check models:  ~/bin/llmflask --models"
	@echo "  Start server:  ~/bin/llmflask --server production"
	@echo "  Open browser:  http://localhost:5000"
	@echo "  Optional keys: ~/bin/llmflask --configure-api-keys"
	@echo "  Standalone:    components/llmflask/standalone/llmflask-linux-$$(uname -m)/llmflask"
	@echo "  Install it:    cp components/llmflask/standalone/llmflask-linux-$$(uname -m)/llmflask ~/bin/llmflask"
	@echo "  Full stack:    make install-server  # requires Docker"

test: fix-permissions
	./tools/test/run-tests.sh

setup-test-env: fix-permissions
	./tools/test/setup-test-env.sh

install-ai: fix-permissions
	./tools/check-install-prerequisites.sh --full
	./components/local-ai/setup-local-ai.sh
	./components/local-ai/setup-searxng.sh
	./components/local-ai/setup-opencode.sh
	./components/llmflask/setup-sandbox.sh

install-ai-minimal: fix-permissions
	./tools/check-install-prerequisites.sh --local
	MODELS="llama3.2:3b" ./components/local-ai/setup-local-ai.sh

install-searxng: fix-permissions
	./tools/check-install-prerequisites.sh --full
	./components/local-ai/setup-searxng.sh

install-opencode: fix-permissions
	./tools/check-install-prerequisites.sh --build
	./components/local-ai/setup-opencode.sh

install-sandbox: fix-permissions
	./tools/check-install-prerequisites.sh --full
	./components/llmflask/setup-sandbox.sh

install-dev: setup-test-env llmflask-venv install-sandbox fix-permissions
	@echo ""
	@echo "Development ready."
	@echo "  source ~/.venvs/llmflask/bin/activate"
	@echo "  llmflask --server"
	@echo "  make test"

install-server: install-ai llmflask-venv
	@echo ""
	@echo "Server ready."
	@echo "  source ~/.venvs/llmflask/bin/activate"
	@echo "  llmflask --server"
	@echo "  llmflask --server production  # Gunicorn"

install-tools: fix-permissions
	mkdir -p "$(HOME)/bin"
	cp tools/llm-models ~/bin/llm-models
	cp tools/llm-ask ~/bin/llm-ask
	cp tools/llm-pool ~/bin/llm-pool
	cp tools/llm-chat ~/bin/llm-chat
	cp tools/llm-pools ~/bin/llm-pools
	cp tools/llm-results ~/bin/llm-results
	cp tools/llm-sessions ~/bin/llm-sessions
	cp tools/llmflaskcmd ~/bin/llmflaskcmd
	cp tools/llm-runresult ~/bin/llm-runresult
	cp tools/llmflask-model-test ~/bin/llmflask-model-test
	chmod +x ~/bin/llm-{models,ask,pool,chat,pools,results,sessions}
	chmod +x ~/bin/llmflaskcmd ~/bin/llm-runresult ~/bin/llmflask-model-test
	@echo "Tools installed to ~/bin/. Set LLMFLASK_HOST and LLMFLASK_PORT for defaults."

llmflask-venv: fix-permissions
	./tools/check-install-prerequisites.sh --build
	cd components/llmflask && ./setup-venv.sh

client-tgz: fix-permissions llmflask-venv
	cd components/llmflask && ./build-client-tgz.sh

standalone: fix-permissions llmflask-venv
	cd components/llmflask && ./build-standalone.sh

install-standalone: standalone
	mkdir -p "$(HOME)/bin"
	install -m 0755 "components/llmflask/standalone/llmflask-linux-$$(uname -m)/llmflask" "$(HOME)/bin/llmflask"
	@echo "Standalone installed to ~/bin/llmflask"

clean:
	rm -rf components/llmflask/build components/llmflask/dist components/llmflask/standalone
	rm -rf components/llmflask/*.egg-info components/llmflask/src/*.egg-info components/llmflask/*.tgz
	rm -rf .pytest_cache tests/__pycache__ tests/llmflask/__pycache__
	rm -rf components/llmflask/__pycache__ components/llmflask/src/llmflask/__pycache__
	rm -rf components/llmflask/src/llmflask/routes/__pycache__ components/llmflask/src/llmflask/services/__pycache__
	rm -f llmflask-tui-trace-*.log
