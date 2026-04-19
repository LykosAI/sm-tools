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

- **`git pr-fork-to-private` command.** Symmetric with the existing
  `pr_fork_to_public`, but routes through the cross-repo `_pr_merge_cross_repo`
  helper — since the fork is a GitHub fork of `public`, not of `private`, there
  is no native fork-PR mechanism for this direction. Clones `private`, fetches
  `fork/main` as a remote, pushes a merge branch, and opens the PR inside
  `private` for team review.

- **`git release` aggregator.** Stages an outbound release up to the review
  step:

  ```shell
  sm-tools git release --new-tag v2.15.0 --title "Release v2.15.0"
  ```

  Chains `push_private_to_fork(new_tag=…)` → `pr_fork_to_public(title, body)`.
  The tag is pushed to `fork` but **not** to `public`. A single confirmation
  prompt gates the whole flow. The public PR is opened but not merged
  programmatically — public releases always get a human review, and must be
  merged as a merge commit (never squash or rebase — see `docs/git-flow.md`).

- **`git release-finalize` command.** Run manually **after** the public
  release PR opened by `release` has been merged on github.com:

  ```shell
  sm-tools git release-finalize
  ```

  Pushes tags from `private` to `public` via `push_tags_private_to_public`.
  Splitting the tag push out of `release` guarantees tags only land on public
  when the tagged commit is actually on `public/main`'s history — so an
  abandoned or rejected release PR never leaves a dangling tag on `public`,
  and the tag ordering can't accidentally imply "this is the shipped version"
  before review. The confirm prompt explicitly warns that this should only be
  run post-merge.

- **`git sync-contributions` aggregator.** Runs the full inbound contribution
  sync in one command:

  ```shell
  sm-tools git sync-contributions
  ```

  Chains `merge_public_to_fork()` → `pr_fork_to_private()`. The follow-on
  downmerge `private/main → private/dev` is deliberately left out — timing is
  case-by-case, run `pr-branches --from private/main --to private/dev` when
  ready.

- Planning document added at `docs/git-flow.md` capturing the three-repo model,
  the flow matrix, tag placement policy (merge commits only — squash/rebase on
  release PRs would leave tags pointing at dangling commits in `public`), and
  the Phase 1 / Phase 2 / non-goals breakdown that drove this release.

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
- `push_tags_private_to_public` gained `--dry-run` and `--yes` / `-y` options,
  matching the other `git` subcommands. In dry-run mode the clone + remote
  setup still happens in its tempdir but the final `push public --tags` is
  gated behind the confirm check, so no remote side effects occur. This is
  what lets `release-finalize --dry-run` exercise the real code path safely.

### Fixed

- `github_pr_merge_branch` previously opened every PR with the hardcoded title
  `"Merge main to dev"` regardless of direction. Now derived from the actual branches.
- Console "Created PR" link now uses `pr.html_url` (the browser-facing
  `/pull/N` page) instead of `pr.url` (the `api.github.com` endpoint).
- `GitProcess.run_cmd` no longer passes `shell=True` together with an argv list.
  On Windows this routed through `cmd.exe /c` and re-quoted argv, which would have
  broken on any source URL or ref containing shell metacharacters.
- `push_private_to_fork --dry-run` previously pushed the release tag to the
  `origin` (private) remote *before* the dry-run check, leaking a real tag on
  every dry run. The tag is now created locally in the tempdir and only
  pushed after the confirm/dry-run gate, so `--dry-run` leaves no remote side
  effects. This same fix is what lets `release --dry-run` exercise step 1
  end-to-end without touching any remote.
