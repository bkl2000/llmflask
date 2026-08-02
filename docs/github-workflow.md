# GitHub Workflow

The private SSH repository remains the authoritative development repository.
GitHub receives a separate history containing only reviewed public snapshots.

## Private-first publication

Keep a new GitHub repository private during the first upload. Publish the
sanitized snapshot, let GitHub Actions finish, and inspect the files and logs
before making the repository public. Changing a repository from private to
public also makes its existing Actions history and logs public.

The GitHub repository must be empty: do not let GitHub create an initial
README, license, or `.gitignore` commit.

## One-time SSH authentication

Signing in to github.com with Google authenticates the browser only. Git over
SSH uses a public key. Do **not** use `ssh-copy-id`; GitHub is not a normal
interactive SSH server.

1. Show the guided instructions:

   ```bash
   ./tools/publish-github.sh --auth-help
   ```

2. Open <https://github.com/settings/ssh/new> while signed in to the intended
   GitHub account and select **Authentication Key**.
3. Display only the public key and paste its complete line into GitHub:

   ```bash
   cat ~/.ssh/id_ed25519.pub
   ```

   If that file does not exist, follow GitHub's key-generation documentation
   or use the `.pub` path reported by `--auth-help`. Never display, copy,
   commit, or upload the matching file without `.pub`; that is the private key.
4. Verify the connection:

   ```bash
   ssh -T git@github.com
   ```

   Success says `Hi USERNAME! You've successfully authenticated, but GitHub
   does not provide shell access.` GitHub deliberately returns status 1 for
   this successful test because it does not provide an interactive shell.
   `Permission denied (publickey)` means that the key is not available to SSH
   or was added to a different account. When port 22 is blocked, use GitHub's
   documented SSH-over-HTTPS-port configuration.

## Prerequisites

- Create an empty GitHub repository without an initial README or license.
- Complete and verify the SSH setup above.
- Commit all intended changes on the private repository first.
- Keep the working tree clean.

The GitHub CLI (`gh`) is optional. Publication uses standard Git over SSH.

## Check the public snapshot

```bash
./tools/publish-github.sh --dry-run
```

This runs the complete tests, legal/privacy audit, and existing snapshot audit.
It applies `export-ignore` rules and rejects private-looking hostnames,
personal paths, secrets, databases, package files, and generated build
directories. It does not contact GitHub or change the GitHub repository.
Maintainer-only agent configuration, work queues, project traces, historical
review drafts, and generated prompt archives remain in the authoritative
private repository but are excluded from the public source snapshot.

To run only the fast committed-snapshot checks:

```bash
./tools/check-publication.sh
./tools/github-push.sh --check
```

Install the optional staged-snapshot pre-commit check with:

```bash
./tools/check-publication.sh --install-hooks
```

The installer is idempotent and refuses to overwrite an unrelated hook.

## First publication

```bash
./tools/publish-github.sh
```

The wrapper repeats the tests and audits, verifies GitHub SSH authentication,
then asks once for the GitHub username and repository name and stores them in
the ignored, mode-0600 `.github-config`. It then:

1. exports only the committed project state;
2. creates a temporary repository with a neutral GitHub noreply author;
3. adds a marker identifying the managed public history;
4. pushes the new `main` branch over SSH.

The private branch, commit history, remotes, configured Git email, Google
login, SSH private key, and credentials are not copied or modified.

## Validate while private

Before changing visibility, inspect the private GitHub repository:

1. Confirm the branch is `main` and the public history contains only managed
   snapshot commits.
2. Inspect the complete file list, especially `README.md`, `LICENSE`,
   `SECURITY.md`, and `CONTRIBUTING.md`.
3. Confirm that no database, API key, personal path/email, generated package,
   standalone binary, or private archive is present.
4. Open **Actions**, require the `Tests` workflow to pass, and inspect its
   complete logs for private information. Delete an unsafe workflow run and
   correct the source before proceeding.
5. Confirm there are no unintended releases, packages, artifacts, deploy keys,
   collaborators, Actions secrets, or repository variables.

Only after this review, use **Settings → General → Danger Zone → Change
repository visibility** to make the repository public. Confirm that the files
are readable in a signed-out browser. Add topics such as `llmflask`, `ollama`,
`llm`, `python`, and `docker`, and enable private vulnerability reporting.

Changing visibility makes the source, activity, Actions history, and Actions
logs public, and anyone can fork the repository. Visibility is therefore a
manual approval step and is never changed by project scripts.

## Versioning and releases

LLMFlask uses semantic version numbers. `0.1.0` is the initial development
version: the leading zero communicates that interfaces and behavior may still
change. Pulling changes, committing work, or publishing another GitHub
snapshot does not automatically change the version.

Use the following convention while the project is below `1.0.0`:

- increment the patch number, for example `0.1.0` to `0.1.1`, for a compatible
  bug-fix release;
- increment the minor number, for example `0.1.1` to `0.2.0`, for a substantial
  feature or an intentionally incompatible development change;
- use `1.0.0` only after the supported interfaces, installation workflow, and
  security model are considered stable.

The application version in `components/llmflask/pyproject.toml` is the primary
version source. The setup-package metadata, CLI output, and README must match;
the test suite checks this consistency. A version change is a reviewed manual
release action and must be committed explicitly.

Do not create a public release tag merely to test a private GitHub snapshot.
After the snapshot and GitHub Actions have been reviewed, the maintainer may
explicitly approve a `vX.Y.Z` tag on the sanitized public `main` commit. Never
tag or publish a private-history commit as the public release.

After publication, test the public installer from a fresh directory:

```bash
curl -fLO https://raw.githubusercontent.com/bkl2000/llmflask/main/tools/install-public.sh
less install-public.sh
bash install-public.sh --directory "$PWD/llmflask"
```

Use `--full-ai` for the complete Ollama/SearXNG/OpenCode/sandbox stack. The
default installs the minimal Ollama model, LLMFlask venv, standalone binary,
and convenience tools. Docker Engine and Compose must already be installed.

## Updates

Publication is deliberately manual. `tools/publish-github.sh` publishes the
committed `HEAD` only: it never stages files, creates a private commit, or
pushes `origin/master`. Review and selectively commit each intended update
first:

```bash
git status
git diff
git add -p
git diff --cached
git commit
git push origin master
./tools/publish-github.sh --dry-run
./tools/publish-github.sh
```

`git add -p` covers changes to tracked files. Review and name a new file
explicitly with `git add path/to/new-file` before committing it. Do not stage
all workspace changes blindly. Agents and automation must not commit or push
unless the maintainer explicitly requests that action.

The publisher fetches the managed public `main`, replaces its files with the
new snapshot, and appends one public commit. If there is no content change, it
does not create a commit. If `main` exists without the publisher marker, the
script stops instead of overwriting it.

Never push the private branch directly to GitHub. In particular, do not run
`git push github master:main`, because that would publish private history and
commit metadata.

## Configuration

Delete `.github-config` to select another GitHub user or repository. SSH is the
default transport. `GITHUB_REMOTE_URL` can override the destination for GitHub
Enterprise or local testing. `tools/github-push.sh` remains the low-level
snapshot engine; normal users should invoke `tools/publish-github.sh`.
