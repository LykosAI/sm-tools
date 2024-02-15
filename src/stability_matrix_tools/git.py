"""Git routines and tools."""
import re
import tempfile

import typer
from github import Auth, Github
from github.Commit import Commit
from github.Repository import Repository
from rich import print as cp
from typer import Option
from typing_extensions import Annotated

from stability_matrix_tools.models.keyring_config import ConfigKey, KeyringConfig
from stability_matrix_tools.models.settings import env
from stability_matrix_tools.utils.git_process import GitProcess

app = typer.Typer(no_args_is_help=True)

ConfirmType = Annotated[bool, Option("--yes", "-y", help="Confirm")]


class GitContext:
    def __init__(self):
        """Initialize a new GitContext."""
        cfg = KeyringConfig.load_from_keyring()
        token = cfg.get_with_prompt(ConfigKey.GITHUB_TOKEN)

        self.gh = Github(auth=Auth.Token(token))
        self.gh_user = self.gh.get_user()

    def get_private_repo(self):
        return self.gh.get_repo(
            env.git_repo_private.removeprefix("https://github.com/"), lazy=True
        )

    def get_fork_repo(self):
        return self.gh.get_repo(
            env.git_repo_fork.removeprefix("https://github.com/"), lazy=True
        )

    def get_public_repo(self):
        return self.gh.get_repo(
            env.git_repo_public.removeprefix("https://github.com/"), lazy=True
        )

    def get_repo_from_url(self, url: str):
        result = re.match(r"(?:https?://github.com/)?(.+?)/(.+?)(?:\.git)?$", url)
        # Only get the first 2 groups
        owner, name = result.groups()[:2]
        return self.gh.get_repo(f"{owner}/{name}", lazy=True)

    @staticmethod
    def compare(
        base_repo: Repository, base: Commit, head_repo: Repository, head: Commit
    ):
        head_part = f"{head_repo.owner.login}:{head_repo.name}:{head.sha}"
        return base_repo.compare(base.sha, head_part)


def format_repo(repo: Repository) -> str:
    return repo.url.removeprefix("https://github.com/")


@app.command()
def auth():
    """Test GitHub authentication."""
    ctx = GitContext()

    cp(f"Authenticated with GitHub as: {ctx.gh_user.login}")


def pr_merge_branch(repo_url: str, from_branch: str, to_branch: str):
    """Creates a PR to merge a repo's branch into another branch."""
    ctx = GitContext()

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


@app.command()
def main_to_dev(repo_url: str):
    """Creates a PR to merge a repo's main branch into dev branch."""
    pr_merge_branch(repo_url, "main", "dev")


@app.command()
def dev_to_main(repo_url: str):
    """Creates a PR to merge a repo's main branch into dev branch."""
    pr_merge_branch(repo_url, "dev", "main")


@app.command()
def private_main_to_dev():
    """Creates a PR to merge private/main into private/dev."""
    main_to_dev(env.git_repo_private)


@app.command()
def private_dev_to_main():
    """Creates a PR to merge private/dev into private/main."""
    dev_to_main(env.git_repo_private)


@app.command()
def private_to_fork(
    new_tag: Annotated[str, typer.Option("--new-tag")] = "",
    dry_run: bool = False,
    confirm: ConfirmType = False,
):
    """Creates a PR to merge private/main into fork/main."""

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
def private_tags_to_public():
    with tempfile.TemporaryDirectory() as private_repo_dir:
        git = GitProcess(private_repo_dir)

        cp(f"Cloning private repo: {env.git_repo_private}")
        git.run_cmd("clone", env.git_repo_private, ".")

        cp(f"Adding public as remote: {env.git_repo_public}")
        git.run_cmd("remote", "add", "public", env.git_repo_public)

        cp("Pushing tags to public")
        git.run_cmd("push", "public", "--tags")


@app.command()
def fork_to_public(title: str, body: str = ""):
    """Creates a PR to merge a fork's main branch into public/main."""
    ctx = GitContext()

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
