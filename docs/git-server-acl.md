# Git-Server ACL Setup

Goal: `team01` through `team10` may read the repo but not push.
Write access via `git@git-server.example.com` remains unchanged.
Team users keep normal SSH logins for workshops and port forwarding.
Read-only protection is enforced via POSIX ACLs only.

## Fix After Old git-shell Configuration

If a team user's SSH login breaks with `Interactive git shell is not enabled`,
their login shell was accidentally set to `git-shell`. Fix as root on the server:

```bash
for u in team01 team02 team03 team04 team05 team06 team07 team08 team09 team10; do
  chsh -s /bin/bash "$u"
done
```

## Setup

From the local repo:

```bash
tools/git-server/upload-acl-script.sh
```

This copies to `/tmp` only; nothing is executed remotely.

On the Git server as root:

```bash
su -
bash /tmp/setup-llmflask-acl-readonly.sh
```

## Rename an Existing Repository

Before renaming, stop writes and push the final `master` state to the existing
repository. Then run the migration as root on the Git server:

```bash
test -d /home/git/git/ollama.git
test ! -e /home/git/git/llmflask.git
git --bare --git-dir=/home/git/git/ollama.git rev-parse refs/heads/master
getfacl -R /home/git/git/ollama.git \
  > "/root/ollama.git.acl.$(date +%Y%m%d-%H%M%S)"
mv /home/git/git/ollama.git /home/git/git/llmflask.git
groupmod -n llmflask-read ollama-read
git config --system --unset-all safe.directory /home/git/git/ollama.git || true
git config --system --add safe.directory /home/git/git/llmflask.git
bash /tmp/setup-llmflask-acl-readonly.sh
git --bare --git-dir=/home/git/git/llmflask.git rev-parse refs/heads/master
```

The two printed commit IDs must match. If `llmflask-read` already exists, do
not run `groupmod`; configure `READ_GROUP=llmflask-read` and verify the team
memberships before applying the ACL script.

## Defaults

```text
Repo:        /home/git/git/llmflask.git
Read group:  llmflask-read
Team users:  team01 ... team10
Write user:  git
Admin user:  admin (if present)
```

## Test

Team user:

```bash
ssh -p 2222 team01@git-server.example.com
ssh -N -p 2222 -L 60010:192.0.2.100:5000 team01@git-server.example.com
git clone ssh://team01@git-server.example.com:2222/home/git/git/llmflask.git
cd llmflask
git pull
git push   # must fail
```

Write user:

```bash
git clone ssh://git@git-server.example.com:2222/home/git/git/llmflask.git
cd llmflask
git push   # must succeed
```

## Notes

The script does not manage SSH keys. Password-less SSH access for team users
must be configured separately.

The script intentionally does not set team users to `git-shell` or `nologin`.
These users need normal SSH shells for workshops and tunnels.

Before ACL changes, the root script writes a backup to
`/root/llmflask.git.acl.<timestamp>`.

The script also sets system-wide:

```bash
git config --system --add safe.directory /home/git/git/llmflask.git
```

This is required because `team01` through `team10` read a bare repo owned by
user `git`. Without this entry, Git aborts with "dubious ownership".
