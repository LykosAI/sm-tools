# Changelog

All notable changes to `sm-tools` are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.4.0] — Unreleased

### Added

- **`git pr-branches` command.** Opens a merge PR between any two repo/branch pairs,
  with a single code path for same-repo and cross-repo merges. Accepts full git URLs
  or the `private` / `fork` / `public` preset keys from `EnvSettings`.

  ```shell
  # Downmerge main into dev in the private repo
  sm-tools git pr-branches --from private/main --to private/dev

  # Release PR: dev into main in the private repo
  sm-tools git pr-branches --from private/dev --to private/main

  # Cross-repo: sync private/main out to fork/main
  sm-tools git pr-branches --from private/main --to fork/main

  # Full URLs also work
  sm-tools git pr-branches \
      --from https://github.com/ionite34/StabilityMatrix/main \
      --to   https://github.com/LykosAI/StabilityMatrix-Dev/main
  ```

  Same-repo merges use the GitHub API directly (create ref + open PR). Cross-repo
  merges clone the target, fetch the source as a remote, push a merge branch to the
  target, then open the PR inside the target repo — which is what GitHub requires
  when the two repos aren't fork-linked and `gh pr create` can't span them.

- `GithubContext` extracted to `stability_matrix_tools.utils.git_context` so it can
  be reused outside `git.py`.

### Changed

- Unified the same-repo and cross-repo PR helpers behind a single `(source, target)`
  signature with shared title, body, and merge-branch-name generators. Titles are
  now derived from the actual source/target instead of a fixed string, and PR bodies
  include the source SHA and a `sm-tools git pr-branches` attribution line.
- `pr-branches` now short-circuits when there's nothing to merge:
  - same-repo via `repo.compare(target, source).total_commits == 0`
  - cross-repo via `git merge-base --is-ancestor <source_sha> <target_sha>`
- Cross-repo merge branch names now slugify the source repo (e.g.
  `merge-ionite34-StabilityMatrix-main-to-main-abc1234`) instead of slashes in the branch name.

### Fixed

- `github_pr_merge_branch` previously opened every PR with the hardcoded title
  `"Merge main to dev"` regardless of direction. Now derived from the actual branches.
- Console "Created PR" link now uses `pr.html_url` (the browser-facing
  `/pull/N` page) instead of `pr.url` (the `api.github.com` endpoint).
- `GitProcess.run_cmd` no longer passes `shell=True` together with an argv list.
  On Windows this routed through `cmd.exe /c` and re-quoted argv, which would have
  broken on any source URL or ref containing shell metacharacters.
