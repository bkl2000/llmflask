# SPDX-License-Identifier: MIT
# Copyright (c) 2024-2026 LLMFlask contributors
setup() {
  export LC_ALL=C.UTF-8

  export DOCKER_MOCK_PS=""
  export DOCKER_MOCK_INSPECT_CONTAINER=""
  export DOCKER_MOCK_INSPECT_IMAGE=""
  export DOCKER_MOCK_PULL_OUTPUT=""
  export DOCKER_MOCK_RUN_CMD=""
  export DOCKER_MOCK_RM_CMD=""
  export MOCK_DOCKER_IMAGE_MISSING=""
  export MOCK_DOCKER_INFO_FAIL=""
  export MOCK_DOCKER_BUILD_CALLED=""

  export OLLAMA_URL="http://127.0.0.1:11434"

  docker() {
    case "$1" in
      pull)
        echo "${DOCKER_MOCK_PULL_OUTPUT:-Status: Image is up to date}"
        ;;
      ps)
        if [ "$2" = "-a" ]; then
          echo "${DOCKER_MOCK_PS:-searxng}"
        else
          echo "${DOCKER_MOCK_PS:-searxng}"
        fi
        ;;
      inspect)
        case "$2" in
          --format*)
            if echo "$*" | grep -q "Config.Image"; then
              echo "${DOCKER_MOCK_INSPECT_CONTAINER:-searxng/searxng:latest}"
            elif echo "$*" | grep -q ".Image"; then
              echo "${DOCKER_MOCK_INSPECT_CONTAINER:-sha256:aaaaaaaaaaaa}"
            else
              echo "${DOCKER_MOCK_INSPECT_IMAGE:-sha256:aaaaaaaaaaaa}"
            fi
            ;;
          *)
            echo "{}"
            ;;
        esac
        ;;
      image)
        case "$2" in
          inspect)
            if [ "${MOCK_DOCKER_IMAGE_MISSING:-}" = "true" ]; then
              return 1
            fi
            echo "${DOCKER_MOCK_INSPECT_IMAGE:-sha256:aaaaaaaaaaaa}"
            ;;
        esac
        ;;
      build)
        MOCK_DOCKER_BUILD_CALLED="true"
        echo "docker build called: $*"
        ;;
      info)
        if [ "${MOCK_DOCKER_INFO_FAIL:-}" = "true" ]; then
          return 1
        fi
        return 0
        ;;
      run)
        echo "docker run called with: $*" >&2
        DOCKER_MOCK_RUN_CMD="$*"
        ;;
      rm)
        DOCKER_MOCK_RM_CMD="$*"
        ;;
      logs)
        echo "mock logs"
        ;;
      compose)
        echo "compose $*"
        ;;
    esac
  }

  curl() {
    case "$*" in
      *api/tags*)
        echo '{}'
        ;;
      *search*)
        echo '{"results":[]}'
        ;;
      *)
        echo "mock curl: $*" >&2
        return 0
        ;;
    esac
  }

  systemctl() {
    return 0
  }

  ollama() {
    case "$1" in
      --version) echo "ollama version 0.3.0" ;;
      list)
        if [ "${OLLAMA_LIST_MOCK:-}" != "" ]; then
          echo "${OLLAMA_LIST_MOCK}"
        else
          echo "NAME              ID              SIZE      MODIFIED"
        fi
        ;;
      pull) echo "pulling ${*:2}..." ;;
      *) return 0 ;;
    esac
  }

  command() {
    case "$1" in
      -v)
        case "$2" in
          docker) [ "${MOCK_DOCKER_MISSING:-}" != "true" ] && echo /usr/bin/docker || return 1 ;;
          curl) echo /usr/bin/curl ;;
          git) echo /usr/bin/git ;;
          ollama) echo /usr/bin/ollama ;;
          nvidia-smi) return 1 ;;
          docker-compose) [ "${MOCK_COMPOSE_MISSING:-}" != "true" ] && echo /usr/bin/docker-compose || return 1 ;;
          opencode) [ "${MOCK_OPENCODE_MISSING:-}" != "true" ] && echo /usr/local/bin/opencode || return 1 ;;
          *) return 1 ;;
        esac
        ;;
      *) command "$@" ;;
    esac
  }

  hostname() {
    echo "test-host"
  }

  sudo() {
    while [ $# -gt 0 ] && [ "${1#-}" != "$1" ]; do shift; done
    "$@"
  }

  nvidia-smi() {
    return 1
  }

  readlink() {
    builtin command readlink "$@"
  }

  git() {
    case "$1" in
      init) echo "Initialized empty Git repository" ;;
    esac
  }

  opencode() {
    case "$1" in
      --version) echo "opencode 1.0.0" ;;
      *) return 0 ;;
    esac
  }

  mkdir() {
    builtin command mkdir "$@"
  }

  chmod() {
    return 0
  }

  export -f docker curl systemctl ollama command hostname sudo nvidia-smi readlink git opencode mkdir chmod
}
