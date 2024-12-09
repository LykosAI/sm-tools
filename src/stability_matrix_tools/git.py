"""Git routines and tools."""
import re
import tempfile

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

REPO_PRESETS = {
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


def github_pr_merge_branch(repo_url: str, from_branch: str, to_branch: str):
    """Creates a PR to merge a repo's branch into another branch."""
    ctx = GithubContext()

    repo = ctx.get_repo_from_url(repo_url)
    repo_str = format_repo(repo)

    source = repo.get_branch(from_branch)

    # create a new branch from private/main
    merge_branch_name = f"merge-{from_branch}-to-{to_branch}-{source.commit.sha[:7]}"
    repo.create_git_ref(
        ref=f"refs/heads/{merge_branch_name}",
        sha=source.commit.sha,
    )

    cp(
        f"Creating branch: {repo_str}/{merge_branch_name} from {repo_str}/{from_branch} @ {source.commit.sha[:7]}"
    )
    cp(f"Creating PR: {repo_str}/{merge_branch_name} -> {repo_str}/{to_branch}")

    # create a PR from private/main to private/dev
    pr = repo.create_pull(
        title="Merge main to dev",
        body="",
        base=to_branch,
        head=merge_branch_name,
    )

    cp(f"✅  Created PR: [cyan link={pr.url}]{pr.title} #{pr.number}[/cyan link]")

def git_pr_merge_repo_branch(source: RepoBranch, target: RepoBranch):
    """Creates a PR to merge a repo's branch into another repo's branch."""

    # Clone the target
    with tempfile.TemporaryDirectory() as target_repo_dir:
        git = GitProcess(target_repo_dir)

        cp(f"Cloning target repo: {target.repo}")
        git.run_cmd("clone", target.repo, ".")

        cp(f"Checking out branch: {target.branch}")
        git.run_cmd("checkout", target.branch)

        target_sha = git.run_cmd("rev-parse", target.branch).strip()

        # Add the source repo as a remote
        cp(f"Adding source repo as remote: {source.repo}")
        git.run_cmd("remote", "add", "source", source.repo)

        cp(f"Fetching source branch: {source.branch}")
        git.run_cmd("fetch", "source", source.branch)

        source_sha = git.run_cmd("rev-parse", f"source/{source.branch}").strip()

        # Create a merge branch in the target repo
        merge_branch_name = f"merge-{source}-to-{target.branch}-{source_sha[:7]}"

        cp(f"Creating branch: {merge_branch_name} from {source}/{source.branch} @ {source_sha[:7]}")
        git.run_cmd("checkout", "-b", merge_branch_name, f"source/{source.branch}")

        # Push the merge branch to the target repo
        cp(f"Pushing branch to target repo: {target.repo}")
        git.run_cmd("push", "origin", merge_branch_name)

    # Create PR
    cp(f"Creating PR: {source}/{merge_branch_name} -> {target}")
    gh_ctx = GithubContext()
    target_repo = gh_ctx.get_repo_from_url(target.repo)

    pr = target_repo.create_pull(
        title=f"Merge {source} to {target.branch}",
        body="",
        base=target.branch,
        head=merge_branch_name,
    )

    cp(f"✅  Created PR: [cyan link={pr.url}]{pr.title} #{pr.number}[/cyan link]")

@app.command()
def pr_branches(from_repo_branch: Annotated[str, Option("--from")], to_repo_branch: Annotated[str, Option("--to")]):
    """Creates a PR to merge a repo's branch into another branch."""
    if not (from_match := try_match_repo_branch(from_repo_branch)):
        raise typer.BadParameter(f"Invalid parameter format '{from_repo_branch}'")

    if not (to_match := try_match_repo_branch(to_repo_branch)):
        raise typer.BadParameter(f"Invalid parameter format '{to_repo_branch}'")

    # If same repo, use the GitHub method
    if from_match.repo == to_match.repo:
        github_pr_merge_branch(from_match.repo, from_match.branch, to_match.branch)
    # Otherwise need to do manual git PR
    else:
        git_pr_merge_repo_branch(from_match, to_match)


@app.command()
def pr_fork_to_public(title: str, body: str = ""):
    """Creates a PR to merge a fork's main branch into public/main."""
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

    cp(f"✅  Created PR: [cyan link={pr.url}]{pr.title} #{pr.number}[/cyan link]")

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
            cp(f"Creating tag: {new_tag}")
            git.run_cmd("tag", "-a", new_tag, "-m", '""', main_sha)

            cp(f"Pushing tag to origin: {new_tag}")
            git.run_cmd("push", "origin", new_tag)

        cp("Pulling fork to main")
        git.run_cmd("pull", "origin")
        git.run_cmd("pull", "fork", "main")

        # git.run_cmd("-c", "pull.rebase=false", "pull", "fork", "main")

        if dry_run or (not confirm and not typer.confirm("Confirm?")):
            raise typer.Abort()

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
def push_tags_private_to_public():
    with tempfile.TemporaryDirectory() as private_repo_dir:
        git = GitProcess(private_repo_dir)

        cp(f"Cloning private repo: {env.git_repo_private}")
        git.run_cmd("clone", env.git_repo_private, ".")

        cp(f"Adding public as remote: {env.git_repo_public}")
        git.run_cmd("remote", "add", "public", env.git_repo_public)

        cp("Pushing tags to public")
        git.run_cmd("push", "public", "--tags")


@app.command()
def github_auth():
    """Test GitHub authentication."""
    ctx = GithubContext()

    cp(f"Authenticated with GitHub as: {ctx.gh_user.login}")