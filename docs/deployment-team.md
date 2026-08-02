# Team User Deployment

For team users who need read-only Git access and SSH port forwarding.

## Git Access

```bash
git clone ssh://team01@SERVER_IP:PORT/path/to/llmflask.git
cd llmflask
git pull
```

Replace `team01` with `team02` through `team10`.

## SSH Tunnel

```bash
ssh -p PORT -L 60010:SERVER_IP:5000 team01@SERVER_HOST
```

This forwards the server's LLMFlask port (5000) to local port 60010.

## Client Usage

Select a `MODELREF` from `llmflask --models` and pass it unchanged to
`--model`, for example:

```bash
llmflask --tui --port 60010 --user team01
llmflask --cmd --text "Hello" --model ollama/qwen3:14b --port 60010
```

## Server-Side ACL

See [docs/git-server-acl.md](git-server-acl.md) for server administrator setup.
