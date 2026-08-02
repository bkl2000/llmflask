# GitHub Publication Checklist

The detailed and authoritative procedure is in
[GitHub Workflow](github-workflow.md).

## One-time SSH setup

- [ ] Keep the empty GitHub repository private during initial validation.
- [ ] Run `./tools/publish-github.sh --auth-help`.
- [ ] Do **not** use `ssh-copy-id` for GitHub.
- [ ] Open <https://github.com/settings/ssh/new> and select
      **Authentication Key**.
- [ ] Copy only the complete output of `cat ~/.ssh/id_ed25519.pub` (or the
      `.pub` file reported by the helper). Never copy the file without `.pub`.
- [ ] Run `ssh -T git@github.com` and confirm it reports successful
      authentication. Status 1 is expected for GitHub's no-shell response.

## Before the first publication

- [ ] Create an empty GitHub repository without a README or license.
- [ ] Configure and verify the GitHub SSH key as described above.
- [ ] Confirm public clone and installer URLs point to `bkl2000/llmflask`.
- [ ] Review `git status`, `git diff`, and the selectively staged diff.
- [ ] Commit and push the approved state to the private SSH server.
- [ ] Run `./tools/publish-github.sh --dry-run`.
- [ ] Confirm that no private hostname, IP address, email, API key, database,
      package artifact, or generated build directory is in the snapshot.

## Publish

```bash
./tools/publish-github.sh
```

Do not add the private `master` as a GitHub push source. Future publications
must use the same script so private history remains private.

## Validate privately

- [ ] Confirm `main` contains only the managed public snapshot history.
- [ ] Inspect every commit in that history, not only the current `main` tree.
- [ ] Inspect the complete file list and rendered project documents.
- [ ] Confirm the GitHub Actions test succeeds.
- [ ] Read the complete Actions log and remove unsafe runs before publication.
- [ ] Confirm no unintended release, artifact, secret, variable, or
      collaborator exists.

## Make public

- [ ] In **Settings → General → Danger Zone**, change repository visibility to
      public only after private validation.
- [ ] Confirm anonymous access in a signed-out browser.
- [ ] Remember that existing Actions history and logs become public too.
- [ ] Download and test `tools/install-public.sh` from a fresh directory.

## GitHub settings and checks

- [ ] Confirm `main` is the default branch.
- [ ] Enable Actions and require the test workflow before merging.
- [ ] Enable private vulnerability reporting when available.
- [ ] Confirm `LICENSE`, `README.md`, `SECURITY.md`, and `CONTRIBUTING.md` render.
- [ ] Add suitable topics such as `llmflask`, `ollama`, `llm`, `python`, and
      `docker`.
