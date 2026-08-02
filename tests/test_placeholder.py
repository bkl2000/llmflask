# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
import json
import re
import tomllib

import pytest


def _read_private_project_file(project_root, relative_path):
    path = project_root / relative_path
    if not path.exists():
        pytest.skip(
            "private-only project file is not part of the public snapshot: "
            f"{relative_path}"
        )
    return path.read_text()


def test_project_root_has_setup_scripts(project_root):
    scripts = [
        "setup-local-ai.sh",
        "setup-opencode.sh",
        "setup-searxng.sh",
        "setup-test-env.sh",
    ]
    for name in scripts:
        assert (project_root / "scripts" / name).is_file(), f"scripts/{name} fehlt"


def test_project_root_has_component_structure(project_root):
    assert (project_root / "components" / "local-ai").is_dir()
    assert (project_root / "components" / "llmflask").is_dir()
    assert (project_root / "docs").is_dir()
    assert (project_root / "tools" / "git-server").is_dir()
    assert (project_root / "tools" / "test").is_dir()
    assert (project_root / "Makefile").is_file()


def test_project_root_has_readme(project_root):
    assert (project_root / "README.md").is_file()


def test_project_rename_is_consistent_in_metadata_and_user_docs(project_root):
    readme = (project_root / "README.md").read_text()
    metadata = tomllib.loads((project_root / "pyproject.toml").read_text())
    team_deployment = (project_root / "docs" / "deployment-team.md").read_text()

    assert readme.startswith("# LLMFlask\n")
    assert metadata["project"]["name"] == "llmflask-setup"
    assert "llmflask --models" in team_deployment
    assert "--model ollama/qwen3:14b" in team_deployment


def test_publication_metadata_is_ready(project_root):
    attributes = (project_root / ".gitattributes").read_text()
    license_text = (project_root / "LICENSE").read_text()

    private_only_paths = [
        "archive/legacy-docs",
        "AGENTS.md",
        "OPENCODE_INSTALLATION_PLAN.md",
        "OPENCODE_REVIEW_PLAN.md",
        "PROJECT_TRACE.md",
        "PYTHON_GROSSREFAKTOR_REVIEW.md",
        "llmflask_local_ai_workbench_pool_phase1_AI_Draft_Unreviewed_2026-07-12.md",
        "opencode.json",
        "prompts/ollama_prompt_pack_pythonic.tar.gz",
    ]
    for private_only_path in private_only_paths:
        assert f"{private_only_path} export-ignore" in attributes
    assert "LLMFlask contributors" in license_text
    assert (project_root / ".github" / "workflows" / "test.yml").is_file()
    assert (project_root / "tools" / "check-publication.sh").is_file()
    assert (project_root / "tools" / "install-public.sh").is_file()
    assert (project_root / "tools" / "publish-github.sh").is_file()


def test_publication_defaults_to_llmflask_repository(project_root):
    publisher = (project_root / "tools" / "github-push.sh").read_text()

    assert 'Repository name [llmflask]' in publisher
    assert 'GITHUB_REPO="${GITHUB_REPO:-llmflask}"' in publisher


def test_opencode_uses_shared_project_instructions(project_root):
    config = json.loads(_read_private_project_file(project_root, "opencode.json"))
    agents = _read_private_project_file(project_root, "AGENTS.md")

    assert config["$schema"] == "https://opencode.ai/config.json"
    assert config["instructions"] == [
        "CONTRIBUTING.md",
        "SECURITY.md",
        "docs/github-workflow.md",
        "PROJECT_TRACE.md",
        "OPENCODE_INSTALLATION_PLAN.md",
        "OPENCODE_REVIEW_PLAN.md",
    ]
    assert "Codex, OpenCode" in agents
    assert "including DeepSeek V4" in agents
    assert "tools/github-push.sh --check" in agents
    assert "minimums, not a" in agents
    assert "OPENCODE_INSTALLATION_PLAN.md" in agents


def test_publication_docs_never_recommend_private_history_push(project_root):
    workflow = (project_root / "docs" / "github-workflow.md").read_text()

    assert "private branch, commit history" in workflow
    assert "Never push the private branch directly" in workflow
    assert "must use the same script" in (
        project_root / "docs" / "github-publish.md"
    ).read_text()


def test_publication_docs_include_private_first_ssh_setup(project_root):
    workflow = (project_root / "docs" / "github-workflow.md").read_text()

    assert "https://github.com/settings/ssh/new" in workflow
    assert "Do **not** use `ssh-copy-id`" in workflow
    assert "cat ~/.ssh/id_ed25519.pub" in workflow
    assert "Actions history and logs public" in workflow
    assert "tools/publish-github.sh --dry-run" in workflow


def test_public_docs_use_concrete_repository_urls_and_disclose_scope(project_root):
    readme = (project_root / "README.md").read_text()
    deployment = (project_root / "docs" / "deployment-server.md").read_text()
    security = (project_root / "SECURITY.md").read_text()
    public_docs = "\n".join((readme, deployment, security))
    readme_words = " ".join(readme.split())

    assert "<repository-url>" not in public_docs
    assert "github.com/USER/llmflask" not in public_docs
    assert "git clone https://github.com/bkl2000/llmflask.git llmflask" in readme
    assert "git clone https://github.com/bkl2000/llmflask.git llmflask" in deployment
    assert "AI-assisted project" in readme
    assert "sometimes described as vibe coding" in readme_words
    assert "not an independent human or third-party security audit" in readme_words
    assert "intended for trusted local users and protected networks" in readme_words
    assert "has no authentication, authorization, or tenant isolation" in readme_words
    assert "operate an approved Ollama or other LLM service" in readme_words
    assert "not a way to bypass organizational restrictions" in readme_words
    assert "Treat this as a local-first project for trusted users" in security


def test_publication_help_keeps_commits_and_private_push_manual(project_root):
    publisher = (project_root / "tools" / "publish-github.sh").read_text()
    workflow = (project_root / "docs" / "github-workflow.md").read_text()
    publisher_words = " ".join(publisher.split())

    assert "publishes committed HEAD only" in publisher
    assert "never stages files, creates a private commit" in publisher_words
    assert "git add -p" in publisher
    assert "Agents and automation must not commit or push" in workflow


def test_public_version_is_consistent_and_manually_released(project_root):
    setup_metadata = tomllib.loads((project_root / "pyproject.toml").read_text())
    app_metadata = tomllib.loads(
        (project_root / "components" / "llmflask" / "pyproject.toml").read_text()
    )
    version = app_metadata["project"]["version"]
    readme = (project_root / "README.md").read_text()
    workflow = (project_root / "docs" / "github-workflow.md").read_text()
    workflow_words = " ".join(workflow.split())
    main_cli = (
        project_root / "components" / "llmflask" / "src" / "llmflask" / "__main__.py"
    ).read_text()
    compatibility_cli = (
        project_root
        / "components"
        / "llmflask"
        / "src"
        / "llmflask"
        / "cli_parser.py"
    ).read_text()

    assert re.fullmatch(r"(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)", version)
    assert setup_metadata["project"]["version"] == version
    assert f"LLMFlask {version}" in readme
    assert f"llmflask {version}" in main_cli
    assert f"llmflask {version}" in compatibility_cli
    assert "does not automatically change the version" in workflow_words
    assert "Never tag or publish a private-history commit" in workflow_words


def test_publishable_scripts_do_not_name_private_server_or_user(project_root):
    paths = [
        project_root / "components" / "local-ai" / "setup-local-ai.sh",
        project_root / "components" / "local-ai" / "setup-opencode.sh",
        project_root / "components" / "local-ai" / "setup-searxng.sh",
        project_root / "tools" / "test" / "setup-test-env.sh",
        project_root / "components" / "llmflask" / "setup-venv.sh",
        project_root / "components" / "llmflask" / "build-client-tgz.sh",
    ]
    contents = "\n".join(path.read_text() for path in paths)

    private_hostname = "homelinux" + ".com"
    private_user = "--user " + "b" + "kl"
    assert private_hostname not in contents
    assert private_user not in contents


def test_readme_has_team_user_pull_commands(project_root):
    readme = (project_root / "README.md").read_text()

    assert "git pull" in readme
    assert "deployment-team.md" in readme


def test_readme_introduces_all_llmflask_interfaces(project_root):
    readme = (project_root / "README.md").read_text()

    assert "Web GUI" in readme
    assert "llmflask --tui" in readme
    assert "llmflask --cmd" in readme
    assert "make install-ai" in readme
    assert "MODELREF" in readme
    assert "llmflask --models --host 127.0.0.1 --port 60010" in readme
    assert "Remote servers and API keys" in readme


def test_readme_puts_backend_preflight_before_quick_start(project_root):
    readme = (project_root / "README.md").read_text()
    preflight_start = readme.index("## Before the first start")
    quick_start = readme.index("## Quick start on Linux")
    preflight = readme[preflight_start:quick_start]

    assert preflight_start < quick_start
    assert "Ollama must be reachable" in preflight
    assert "http://127.0.0.1:11434" in preflight
    assert "systemctl is-active ollama" in preflight
    assert "ollama list" in preflight
    assert "~/bin/llmflask --models" in preflight
    assert "Ollama is not required for direct provider access" in preflight
    assert "~/bin/llmflask --configure-api-keys" in preflight
    assert "~/.config/llmflask/api.txt" in preflight


def test_readme_keeps_detailed_remote_and_key_placement_late(project_root):
    readme = (project_root / "README.md").read_text()
    remote_start = readme.index("## Remote servers and API keys")
    troubleshooting_start = readme.index("## Common startup problems")
    remote = readme[remote_start:troubleshooting_start]

    assert readme.index("## Search and code workbench") < remote_start
    assert remote_start < troubleshooting_start
    assert "Direct local Ollama" in remote
    assert "Direct remote Ollama" in remote
    assert "LLMFlask server" in remote
    assert "Direct OpenAI/DeepSeek" in remote
    assert "OLLAMA_URL=http://OLLAMA_SERVER:11434" in remote
    assert "On the server account" in remote
    assert "On the client account" in remote
    assert "clients do not receive the server's keys" in remote


def test_readme_fenced_code_blocks_are_balanced(project_root):
    readme = (project_root / "README.md").read_text()
    fences = [line for line in readme.splitlines() if line.startswith("```")]

    assert len(fences) % 2 == 0
    assert "```bash\n```bash" not in readme


def test_readme_documents_fresh_install_dependencies(project_root):
    readme = (project_root / "README.md").read_text()
    readme_words = " ".join(readme.split())

    for dependency in (
        "ca-certificates",
        "git",
        "curl",
        "make",
        "tar",
        "python3-venv",
        "python3-pip",
    ):
        assert dependency in readme
    assert "docker info" in readme
    assert "docker compose version" in readme
    assert "Python 3.12" in readme
    assert "https://github.com/bkl2000/llmflask.git" in readme
    assert "make all" in readme
    assert "Debian 13 or newer" in readme_words
    assert "Ubuntu 24.04 or newer" in readme_words
    assert "Linux Mint 22 or newer" in readme_words
    assert "not an upper-version allowlist" in readme_words
    assert "future Debian 14" in readme_words
    assert "A release is described as *tested* only after" in readme_words
    assert "not supported or tested there out of the box" in readme_words
    assert "`pip` rejects Python 3.11 before installation" in readme_words
    assert "does not run its compatibility suite on 3.11" in readme_words


def test_ci_checks_minimum_and_forward_python_versions(project_root):
    workflow = (
        project_root / ".github" / "workflows" / "test.yml"
    ).read_text()

    assert 'python-version: ["3.12", "3.x"]' in workflow
    assert "python-version: ${{ matrix.python-version }}" in workflow
    assert "check-latest: true" in workflow


def test_readme_documents_explicit_pool_model_and_common_failures(project_root):
    readme = (project_root / "README.md").read_text()

    assert "always require an explicit" in readme
    assert "experimental but runnable Phase 1" in readme
    assert "make install-sandbox" in readme
    assert "docker image inspect llmflask-sandbox:1" in readme
    assert "There is no persistent pool container to start" in readme
    assert "LLMFLASK_WORKBENCH_ENABLED=1" in readme
    assert "--usepool --host 127.0.0.1 --port 60010" in readme
    assert "Broader toolchains" in readme
    assert "No models found" in readme
    assert "No server at" in readme
    assert "Docker permission" in readme


def test_architecture_distinguishes_pool_and_install_test_containers(project_root):
    architecture = (project_root / "docs" / "architecture.md").read_text()

    assert "experimental Phase 1" in architecture
    assert "not the planned fresh-install test container" in architecture
    assert "make install-sandbox" in architecture
    assert "persistent pool container to start" in " ".join(architecture.split())


def test_readme_documents_api_key_file_safely(project_root):
    readme = (project_root / "README.md").read_text()

    assert "OPENAI_API_KEY" in readme
    assert "DEEPSEEK_API_KEY" in readme
    assert "LLMFLASK_API_KEYS_FILE" in readme
    assert "~/bin/llmflask --configure-api-keys" in readme
    assert "permissions `700`" in readme
    assert "file with `600`" in readme
    assert "Never commit API keys" in readme


def test_web_client_marks_state_changing_api_requests(project_root):
    chat_js = (
        project_root
        / "components"
        / "llmflask"
        / "src"
        / "llmflask"
        / "static"
        / "chat.js"
    ).read_text()

    assert "'X-LLMFlask-Request': '1'" in chat_js.split(
        "fetch('/api/chat'", 1
    )[1][:500]
    assert "['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)" in chat_js


def test_docs_capture_trace_and_project_history_policy(project_root):
    readme = (project_root / "README.md").read_text()
    agents = _read_private_project_file(project_root, "AGENTS.md")
    trace = _read_private_project_file(project_root, "PROJECT_TRACE.md")

    assert "TUI tracing" in agents
    assert "PROJECT_TRACE.md" in agents
    assert "team01" in trace or "team" in trace.lower()
    assert "git pull" in trace


def test_vram_tuning_recommendations_are_documented(project_root):
    trace = _read_private_project_file(project_root, "PROJECT_TRACE.md")
    script = (project_root / "components" / "local-ai" / "setup-local-ai.sh").read_text()

    assert "8 GB" in trace
    assert "12 GB" in script
    assert "OLLAMA_NUM_PARALLEL" in trace or "ollama ps" in trace


def test_project_root_has_pyproject(project_root):
    assert (project_root / "pyproject.toml").is_file()


def test_make_clean_targets_generated_files_only(project_root):
    makefile = (project_root / "Makefile").read_text()

    expected_cleanup_patterns = [
        "components/llmflask/build",
        "components/llmflask/dist",
        "components/llmflask/standalone",
        "components/llmflask/*.tgz",
        ".pytest_cache",
        "__pycache__",
        "llmflask-tui-trace-*.log",
    ]
    for pattern in expected_cleanup_patterns:
        assert pattern in makefile

    forbidden_cleanup_patterns = [
        "api.txt",
        "chat.db",
        "projects/sqa",
    ]
    for pattern in forbidden_cleanup_patterns:
        assert pattern not in makefile


def test_makefile_has_production_server_target(project_root):
    cli_main = (project_root / "components" / "llmflask" / "src" / "llmflask" / "__main__.py").read_text()
    assert '"production"' in cli_main


def test_make_all_creates_a_minimal_runnable_local_install(project_root):
    makefile = (project_root / "Makefile").read_text()
    all_recipe = makefile.split("all: fix-permissions", 1)[1].split("\ntest:", 1)[0]

    assert "$(MAKE) install-ai-minimal" in all_recipe
    assert "$(MAKE) install-standalone" in all_recipe
    assert "$(MAKE) install-tools" in all_recipe
    assert "~/bin/llmflask --models" in all_recipe
    assert "~/bin/llmflask --server production" in all_recipe
    assert (project_root / "tools" / "check-install-prerequisites.sh").is_file()

    install_recipe = makefile.split("install-standalone: standalone", 1)[1]
    assert '"$(HOME)/bin/llmflask"' in install_recipe


def test_make_install_tools_includes_all_convenience_wrappers(project_root):
    makefile = (project_root / "Makefile").read_text()
    wrappers = (
        "llm-ask",
        "llm-models",
        "llm-pool",
        "llm-chat",
        "llm-pools",
        "llm-results",
        "llm-sessions",
    )

    for wrapper in wrappers:
        assert (project_root / "tools" / wrapper).is_file()
        assert f"tools/{wrapper}" in makefile


def test_make_install_ai_orchestrates_local_ai_components(project_root):
    makefile = (project_root / "Makefile").read_text()

    local_ai = makefile.index("./components/local-ai/setup-local-ai.sh")
    searxng = makefile.index("./components/local-ai/setup-searxng.sh")
    opencode = makefile.index("./components/local-ai/setup-opencode.sh")
    sandbox = makefile.index("./components/llmflask/setup-sandbox.sh")

    assert local_ai < searxng < opencode < sandbox


def test_make_install_ai_minimal_uses_only_small_model(project_root):
    makefile = (project_root / "Makefile").read_text()

    assert "install-ai-minimal:" in makefile
    assert 'MODELS="llama3.2:3b" ./components/local-ai/setup-local-ai.sh' in makefile
    assert not any(
        line.strip().startswith("\t./components/") and "setup-local-ai.sh" not in line
        for line in makefile.split("install-ai-minimal:", 1)[1].splitlines()[:4]
    )


def test_setup_local_ai_is_focused_on_ollama_and_models(project_root):
    script = (project_root / "components" / "local-ai" / "setup-local-ai.sh").read_text()

    assert "ollama.com/install.sh" in script
    assert "ollama pull" in script
    assert "docker pull" not in script
    assert "docker run" not in script
    assert "opencode.ai/install" not in script
    assert "openagent_standardprompt" not in script


def test_vram_tuning_recommendations_are_documented(project_root):
    trace = _read_private_project_file(project_root, "PROJECT_TRACE.md")
    script = (project_root / "components" / "local-ai" / "setup-local-ai.sh").read_text()

    assert ("8 GB" in trace or "8 GB" in script)
    assert ("12 GB" in trace or "12 GB" in script)
    assert ("ollama ps" in trace or "ollama ps" in script)


def test_git_server_acl_admin_files_exist(project_root):
    assert (project_root / "docs" / "git-server-acl.md").is_file()
    assert (project_root / "tools" / "git-server" / "setup-llmflask-acl-readonly.sh").is_file()
    assert (project_root / "tools" / "git-server" / "upload-acl-script.sh").is_file()


def test_git_server_acl_script_defaults_and_safety(project_root):
    script = (project_root / "tools" / "git-server" / "setup-llmflask-acl-readonly.sh").read_text()

    assert "REPO_PATH=\"${REPO_PATH:-/home/git/git/llmflask.git}\"" in script
    assert "READ_GROUP=\"${READ_GROUP:-llmflask-read}\"" in script
    assert "WRITE_USER=\"${WRITE_USER:-git}\"" in script
    assert 'ADMIN_USER="${ADMIN_USER:-}"' in script
    assert ("ADMIN_USER=" + "b" + "kl") not in script
    assert "ADMIN_USER=admin" in script
    assert 'if [ -z "$ADMIN_USER" ]; then' in script
    assert "Administrator ACL skipped: ADMIN_USER is not set." in script
    assert "team01 team02 team03 team04 team05" in script
    assert "team06 team07 team08 team09 team10" in script
    assert "git --bare --git-dir=\"$REPO_PATH\" rev-parse --is-bare-repository" in script
    assert "git config --system --get-all safe.directory" in script
    assert "git config --system --add safe.directory \"$REPO_PATH\"" in script
    assert "setfacl -R -m \"g:${READ_GROUP}:rX\"" in script
    assert "setfacl -R -m \"u:${WRITE_USER}:rwX\"" in script
    assert "getfacl -R \"$REPO_PATH\"" in script
    assert "chmod -R o-w \"$REPO_PATH\"" in script
    assert "useradd --create-home --shell /bin/bash \"$user\"" in script
    assert "git-shell" not in script
    assert "usermod --shell" not in script
    assert "nologin" not in script


def test_git_server_acl_docs_keep_team_users_login_capable(project_root):
    docs = (project_root / "docs" / "git-server-acl.md").read_text()
    agents = _read_private_project_file(project_root, "AGENTS.md")
    trace = _read_private_project_file(project_root, "PROJECT_TRACE.md")

    assert "chsh -s /bin/bash" in docs
    assert "Interactive git shell is not enabled" in docs
    assert "ssh" in docs.lower()
    assert "mv /home/git/git/ollama.git /home/git/git/llmflask.git" in docs
    assert "groupmod -n llmflask-read ollama-read" in docs
    assert "Never set team users to `git-shell`" in agents
    assert "Team-User versehentlich auf git-shell gesetzt" in trace


def test_git_server_acl_upload_script_targets_tmp(project_root):
    script = (project_root / "tools" / "git-server" / "upload-acl-script.sh").read_text()

    assert "GIT_SERVER=\"${GIT_SERVER:-git-server.example.com}\"" in script
    assert "GIT_SERVER_PORT=\"${GIT_SERVER_PORT:-2222}\"" in script
    assert "GIT_SERVER_USER=\"${GIT_SERVER_USER:-git}\"" in script
    assert "REMOTE_PATH=\"${REMOTE_PATH:-/tmp/setup-llmflask-acl-readonly.sh}\"" in script
    assert "scp -P \"$GIT_SERVER_PORT\"" in script
