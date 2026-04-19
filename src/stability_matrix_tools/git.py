"""Git routines and tools."""
import re
import tempfile
from subprocess import CalledProcessError

import typer
from github import Auth, Github
from github.Commit import Commit
from github.Repository import Repository
from rich import print as cp
from typer import Option
from typing import NamedTuple
from typing_extensions import Annotated

from stability_matrix_tools.models.keyring_config import ConfigKey, KeyringConfig
from stability_matrix_tools.models.settings import env
from stability_matrix_tools.utils.git_context import GithubContext
from stability_matrix_tools.utils.git_process import GitProcess

app = typer.Typer(no_args_is_help=True)

ConfirmType = Annotated[bool, Option("--yes", "-y", help="Confirm")]

class RepoBranch(NamedTuple):
    repo: str
    branch: str

    @property
    def formatted_repo(self):
        return format_repo(self.repo)

    def __str__(self):
        return f"{format_repo(self.repo)}/{self.branch}"

RE_REPO_BRANCH = re.compile(r"""
(
  (?:
    # Match a well-formed git repo URI
    (?:git@|https?://)(?P<host>[\w.-]+)[:/](?P<user>[\w.-]+)/(?P<repo>[\w.-]+)(?:\.git)?
  )
  |
  # Otherwise, capture a plain string repo preset
  (?P<preset>\w+)
)
/
# Capture the branch name
(?P<branch>[\w.-]+)
""", re.VERBOSE)

REPO_PRESETS: dict[str, str] = {
    "private": env.git_repo_private,
    "fork": env.git_repo_fork,
    "public": env.git_repo_public
}

def try_match_repo_branch(repo_branch: str) -> RepoBranch | None:
    if match := RE_REPO_BRANCH.match(repo_branch):
        if not match.group("branch"):
            return None
        if host := match.group("host"):
            return RepoBranch(repo=host, branch=match.group("branch"))
        if preset := match.group("preset"):
            # Check presets
            if resolved_preset := REPO_PRESETS.get(preset):
                return RepoBranch(repo=resolved_preset, branch=match.group("branch"))
            else:
                return None
    return None


def format_repo(repo: Repository | str) -> str:
    if isinstance(repo, Repository):
        return repo.url.removeprefix("https://github.com/")
    elif isinstance(repo, str):
        if preset := REPO_PRESETS.get(repo):
            return preset
        else:
            repo_url = repo
            repo_url = repo_url.removeprefix("https://github.com/")
            return repo_url

    raise ValueError(f"Invalid repo type: {type(repo)}")


def _make_merge_branch_name(source: RepoBranch, target: RepoBranch, source_sha: str) -> str:
    """Build the ephemeral branch name for a merge PR."""
    if source.repo == target.repo:
        return f"merge-{source.branch}-to-{target.branch}-{source_sha[:7]}"
    # Cross-repo: include the source's owner/name slug so the branch is unambiguous
    # inside the target repo (which may receive merges from multiple sources).
    source_slug = format_repo(source.repo).replace("/", "-")
    return f"merge-{source_slug}-{source.branch}-to-{target.branch}-{source_sha[:7]}"


def _make_pr_title(source: RepoBranch, target: RepoBranch) -> str:
    if source.repo == target.repo:
        return f"Merge {source.branch} into {target.branch}"
    return f"Merge {source} into {target.branch}"


def _make_pr_body(source: RepoBranch, target: RepoBranch, source_sha: str) -> str:
    return (
        f"Merges `{source}` into `{target}` @ `{source_sha[:7]}`.\n\n"
        f"_Created by `sm-tools git pr-branches`._"
    )


def _pr_merge_same_repo(source: RepoBranch, target: RepoBranch):
    """Creates a merge PR when source and target live in the same repo (GitHub API only)."""
    ctx = GithubContext()

    repo = ctx.get_repo_from_url(target.repo)
    repo_str = format_repo(repo)

    src_branch = repo.get_branch(source.branch)
    source_sha = src_branch.commit.sha

    # Check that there's actually something to merge. GitHub compare uses base...head;
    # total_commits is the number of commits in `head` that are not in `base`.
    comparison = repo.compare(target.branch, source.branch)
    if comparison.total_commits == 0:
        cp(
            f"[yellow]Nothing to merge: {repo_str}/{target.branch} already contains "
            f"{repo_str}/{source.branch} @ {source_sha[:7]}[/yellow]"
        )
        return

    cp(f"[dim]{comparison.total_commits} commit(s) ahead of {target.branch}[/dim]")

    merge_branch_name = _make_merge_branch_name(source, target, source_sha)

    cp(
        f"Creating branch: {repo_str}/{merge_branch_name} from "
        f"{repo_str}/{source.branch} @ {source_sha[:7]}"
    )
    repo.create_git_ref(
        ref=f"refs/heads/{merge_branch_name}",
        sha=source_sha,
    )

    cp(f"Creating PR: {repo_str}/{merge_branch_name} -> {repo_str}/{target.branch}")
    pr = repo.create_pull(
        title=_make_pr_title(source, target),
        body=_make_pr_body(source, target, source_sha),
        base=target.branch,
        head=merge_branch_name,
    )

    cp(f"✅  Created PR: [cyan link={pr.html_url}]{pr.title} #{pr.number}[/cyan link]")


def _pr_merge_cross_repo(source: RepoBranch, target: RepoBranch):
    """Creates a merge PR across two different repos.

    GitHub only allows PRs between branches in the same repository (or between a
    fork and its upstream). For arbitrary cross-repo merges — e.g. private/main ->
    fork/main — we clone the target, fetch the source as a remote, push the
    resulting merge branch to the target, then open the PR inside the target repo.
    """
    with tempfile.TemporaryDirectory() as target_repo_dir:
        git = GitProcess(target_repo_dir)

        cp(f"Cloning target repo: {target.repo}")
        git.run_cmd("clone", target.repo, ".")

        cp(f"Checking out branch: {target.branch}")
        git.run_cmd("checkout", target.branch)

        target_sha = git.run_cmd("rev-parse", target.branch).strip()

        cp(f"Adding source repo as remote: {source.repo}")
        git.run_cmd("remote", "add", "source", source.repo)

        cp(f"Fetching source branch: {source.branch}")
        git.run_cmd("fetch", "source", source.branch)

        source_sha = git.run_cmd("rev-parse", f"source/{source.branch}").strip()

        # Short-circuit if target already contains every commit from source.
        # merge-base --is-ancestor exits 0 when source_sha is an ancestor of
        # target_sha (which includes the case where they're equal) and 1 otherwise.
        try:
            git.run_cmd("merge-base", "--is-ancestor", source_sha, target_sha)
            cp(
                f"[yellow]Nothing to merge: {target} already contains "
                f"{source} @ {source_sha[:7]}[/yellow]"
            )
            return
        except CalledProcessError:
            pass  # not an ancestor — there's real work to do

        merge_branch_name = _make_merge_branch_name(source, target, source_sha)

        cp(f"Creating branch: {merge_branch_name} from {source} @ {source_sha[:7]}")
        git.run_cmd("checkout", "-b", merge_branch_name, f"source/{source.branch}")

        cp(f"Pushing branch to target repo: {target.repo}")
        git.run_cmd("push", "origin", merge_branch_name)

    cp(f"Creating PR: {merge_branch_name} -> {target}")
    gh_ctx = GithubContext()
    target_repo = gh_ctx.get_repo_from_url(target.repo)

    pr = target_repo.create_pull(
        title=_make_pr_title(source, target),
        body=_make_pr_body(source, target, source_sha),
        base=target.branch,
        head=merge_branch_name,
    )

    cp(f"✅  Created PR: [cyan link={pr.html_url}]{pr.title} #{pr.number}[/cyan link]")

@app.command()
def pr_branches(
    from_repo_branch: Annotated[str, Option("--from")],
    to_repo_branch: Annotated[str, Option("--to")],
):
    """Creates a PR to merge one repo/branch into another repo/branch.

    Accepts either full git URLs or preset keys (`private`, `fork`, `public`)
    from the environment, e.g. `--from private/main --to private/dev` or
    `--from private/main --to fork/main`.
    """
    if not (from_match := try_match_repo_branch(from_repo_branch)):
        raise typer.BadParameter(f"Invalid parameter format '{from_repo_branch}'")

    if not (to_match := try_match_repo_branch(to_repo_branch)):
        raise typer.BadParameter(f"Invalid parameter format '{to_repo_branch}'")

    if from_match.repo == to_match.repo:
        _pr_merge_same_repo(from_match, to_match)
    else:
        _pr_merge_cross_repo(from_match, to_match)


@app.command()
def pr_fork_to_public(title: str, body: str = ""):
    """Creates a PR to merge a fork's main branch into public/main.

    Uses GitHub's native fork-PR mechanism, which works because `fork` is a real
    GitHub fork of `public`. The resulting PR shows up on public's Pull Requests
    tab with the usual fork-PR affordances.
    """
    ctx = GithubContext()

    fork = ctx.get_fork_repo()
    public = ctx.get_public_repo()

    cp(f"Creating PR: {format_repo(fork)}/main -> {format_repo(public)}/main")

    # create a PR from fork/main to public/main
    pr = public.create_pull(
        title=title,
        body=body,
        base="main",
        head=f"{fork.owner.login}:main",
        maintainer_can_modify=True,
    )

    cp(f"✅  Created PR: [cyan link={pr.html_url}]{pr.title} #{pr.number}[/cyan link]")


@app.command()
def pr_fork_to_private():
    """Creates a PR to merge fork/main into private/main.

    Symmetric with `pr_fork_to_public` but takes the cross-repo path via
    `_pr_merge_cross_repo`, since `fork` is a GitHub fork of `public`, not of
    `private` — so we can't rely on a native fork PR here. The helper clones
    `private`, fetches `fork/main`, pushes a merge branch to `private`, and
    opens the PR inside `private` for team review.
    """
    source = RepoBranch(repo=env.git_repo_fork, branch="main")
    target = RepoBranch(repo=env.git_repo_private, branch="main")
    _pr_merge_cross_repo(source, target)

@app.command()
def push_private_to_fork(
    new_tag: Annotated[str, typer.Option("--new-tag")] = "",
    dry_run: bool = False,
    confirm: ConfirmType = False,
):
    """Pushes private/main into fork/main."""

    # Clone the private repo and add the fork as a remote
    with tempfile.TemporaryDirectory() as private_repo_dir:
        git = GitProcess(private_repo_dir)

        cp("Cloning private repo", env.git_repo_private)
        git.run_cmd("clone", env.git_repo_private, ".")

        cp("Adding fork as remote")
        git.run_cmd("remote", "add", "fork", env.git_repo_fork)

        cp("Checking out main")
        git.run_cmd("checkout", "main")

        # Get current main commit sha
        main_sha = git.run_cmd("rev-parse", "main").strip()
        cp(f"Current main commit sha: {main_sha[:7]}")

        if new_tag:
            cp(f"Creating tag locally: {new_tag}")
            git.run_cmd("tag", "-a", new_tag, "-m", '""', main_sha)

        cp("Pulling fork to main")
        git.run_cmd("pull", "origin")
        git.run_cmd("pull", "fork", "main")

        # git.run_cmd("-c", "pull.rebase=false", "pull", "fork", "main")

        if dry_run or (not confirm and not typer.confirm("Confirm?")):
            # In dry-run mode, the tempdir (and any local tag created above) is
            # cleaned up by the TemporaryDirectory context manager on the way
            # out, so no remote side effects remain.
            raise typer.Abort()

        if new_tag:
            cp(f"Pushing tag to origin: {new_tag}")
            git.run_cmd("push", "origin", new_tag)

        cp("Pushing to fork")
        git.run_cmd("push", "fork", "main")
        git.run_cmd("push", "fork", "--tags")


@app.command()
def merge_public_to_fork(
    dry_run: bool = False,
    confirm: ConfirmType = False,
):
    """Merges public/main into fork/main."""

    with tempfile.TemporaryDirectory() as temp_repo_dir:
        git = GitProcess(temp_repo_dir)

        cp("Cloning fork repo", env.git_repo_fork)
        git.run_cmd("clone", env.git_repo_fork, ".")

        cp("Adding public as remote")
        git.run_cmd("remote", "add", "public", env.git_repo_public)
        git.run_cmd("fetch", "public")

        cp("Checking out main")
        git.run_cmd("checkout", "main")

        cp("Merging public to main")
        git.run_cmd("merge", "public/main")

        if dry_run or (not confirm and not typer.confirm("Confirm?")):
            raise typer.Abort()

        cp("Pushing to fork")
        git.run_cmd("push", "origin", "main")


@app.command()
def push_tags_private_to_public(
    dry_run: bool = False,
    confirm: ConfirmType = False,
):
    with tempfile.TemporaryDirectory() as private_repo_dir:
        git = GitProcess(private_repo_dir)

        cp(f"Cloning private repo: {env.git_repo_private}")
        git.run_cmd("clone", env.git_repo_private, ".")

        cp(f"Adding public as remote: {env.git_repo_public}")
        git.run_cmd("remote", "add", "public", env.git_repo_public)

        if dry_run or (not confirm and not typer.confirm("Confirm?")):
            raise typer.Abort()

        cp("Pushing tags to public")
        git.run_cmd("push", "public", "--tags")


@app.command()
def release(
    new_tag: Annotated[str, typer.Option("--new-tag")],
    title: str = "",
    body: str = "",
    dry_run: bool = False,
    confirm: ConfirmType = False,
):
    """Outbound release flow: private -> fork -> public (stage + PR only).

    Chains two primitives:
      1. `push_private_to_fork` — stage commits and the release tag on the fork.
      2. `pr_fork_to_public` — open the public release PR (manual review/merge).

    The tag is pushed to `fork` in step 1 (so fork mirrors private's tag state)
    but **not** to `public` — that's intentional. Pushing the tag to public
    before the PR merges would leave a dangling tag on public pointing at a
    commit that isn't yet on public/main, and if the PR gets rejected or
    abandoned, the stale tag is awkward to clean up.

    After the public PR has been merged (as a merge commit — see
    docs/git-flow.md), run `sm-tools git release-finalize` to push the tag
    from private to public.

    With `--dry-run`, step 1 still runs end-to-end in its tempdir (including
    the local tag creation) but aborts before any remote push, and step 2 is
    printed as a "would do" line with no remote side effects.
    """
    pr_title = title or f"Release {new_tag}"

    header = "[bold]Release flow[/bold]"
    if dry_run:
        header += " [yellow](dry run)[/yellow]"
    cp(f"{header} (tag: [cyan]{new_tag}[/cyan])")
    cp(f"  1. push private/main -> fork/main (tag {new_tag})")
    cp(f"  2. open PR fork/main -> public/main ({pr_title!r})")

    if not dry_run and not confirm and not typer.confirm("Proceed with release?"):
        raise typer.Abort()

    cp("\n[bold cyan]Step 1/2[/bold cyan] — push private/main -> fork/main")
    try:
        push_private_to_fork(new_tag=new_tag, dry_run=dry_run, confirm=True)
    except typer.Abort:
        if not dry_run:
            raise
        # Expected: push_private_to_fork raises Abort after local tag creation
        # in dry-run mode. The tempdir (and local tag) is cleaned up on exit.

    cp("\n[bold cyan]Step 2/2[/bold cyan] — open PR fork/main -> public/main")
    if dry_run:
        cp(
            f"[yellow][dry run][/yellow] would open PR: "
            f"fork/main -> public/main ({pr_title!r})"
        )
    else:
        pr_fork_to_public(title=pr_title, body=body)

    if dry_run:
        cp(
            "\n✅  [bold green]Dry run complete.[/bold green] "
            "No remote side effects."
        )
    else:
        cp(
            f"\n✅  [bold green]Release {new_tag} staged.[/bold green] "
            f"Review and merge the public PR as a merge commit, then run "
            f"[cyan]sm-tools git release-finalize[/cyan] to push the tag to public."
        )


@app.command()
def release_finalize(
    dry_run: bool = False,
    confirm: ConfirmType = False,
):
    """Finalize a release after the public PR has been merged.

    Pushes tags from `private` to `public` via `push_tags_private_to_public`.
    Run this **after** the fork -> public release PR opened by
    `sm-tools git release` has been merged on github.com (as a merge commit).

    Tag push is deferred to this step so that tags only land on public after
    the tagged commit has actually been reviewed and merged — no dangling
    tags on public if a release PR gets rejected or abandoned.
    """
    header = "[bold]Release finalize[/bold]"
    if dry_run:
        header += " [yellow](dry run)[/yellow]"
    cp(header)
    cp("  1. push tags private -> public")

    if not dry_run and not confirm and not typer.confirm(
        "Proceed? Only run this AFTER the public release PR has been merged."
    ):
        raise typer.Abort()

    cp("\n[bold cyan]Step 1/1[/bold cyan] — push tags private -> public")
    try:
        push_tags_private_to_public(dry_run=dry_run, confirm=True)
    except typer.Abort:
        if not dry_run:
            raise
        # Expected: push_tags_private_to_public raises Abort in dry-run mode.

    if dry_run:
        cp(
            "\n✅  [bold green]Dry run complete.[/bold green] "
            "No remote side effects."
        )
    else:
        cp(
            "\n✅  [bold green]Release finalized.[/bold green] "
            "Tags pushed to public."
        )


@app.command()
def sync_contributions(
    dry_run: bool = False,
    confirm: ConfirmType = False,
):
    """Inbound contribution sync: public -> fork -> private.

    Chains two existing primitives:
      1. `merge_public_to_fork` — bring public contributions onto the shuttle.
      2. `pr_fork_to_private` — open a PR into private for team review.

    The follow-on downmerge from `private/main` to `private/dev` is
    intentionally left out — timing is case-by-case. Run
    `sm-tools git pr-branches --from private/main --to private/dev` when ready.

    With `--dry-run`, step 1 still runs end-to-end in its tempdir (including
    the local merge of public/main into fork/main) but aborts before any
    remote push, and step 2 is printed as a "would do" line with no remote
    side effects.
    """
    header = "[bold]Contribution sync flow[/bold]"
    if dry_run:
        header += " [yellow](dry run)[/yellow]"
    cp(header)
    cp("  1. merge public/main -> fork/main")
    cp("  2. open PR fork/main -> private/main")

    if not dry_run and not confirm and not typer.confirm(
        "Proceed with contribution sync?"
    ):
        raise typer.Abort()

    cp("\n[bold cyan]Step 1/2[/bold cyan] — merge public/main -> fork/main")
    try:
        merge_public_to_fork(dry_run=dry_run, confirm=True)
    except typer.Abort:
        if not dry_run:
            raise
        # Expected: merge_public_to_fork raises Abort after local merge in
        # dry-run mode. The tempdir is cleaned up on exit.

    cp("\n[bold cyan]Step 2/2[/bold cyan] — open PR fork/main -> private/main")
    if dry_run:
        cp(
            "[yellow][dry run][/yellow] would open PR: "
            "fork/main -> private/main"
        )
    else:
        pr_fork_to_private()

    if dry_run:
        cp(
            "\n✅  [bold green]Dry run complete.[/bold green] "
            "No remote side effects."
        )
    else:
        cp(
            "\n✅  [bold green]Contribution sync staged.[/bold green] "
            "Review and merge the PR into private/main."
        )


@app.command()
def github_auth():
    """Test GitHub authentication."""
    ctx = GithubContext()

    cp(f"Authenticated with GitHub as: {ctx.gh_user.login}")