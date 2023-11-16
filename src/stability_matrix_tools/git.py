"""Git routines and tools."""

from tempfile import TemporaryDirectory

import rich
import typer

from github import Auth, Github
from github.GitRef import GitRef
from github.Repository import Repository
from github.Commit import Commit

from stability_matrix_tools.models.keyring_config import ConfigKey, KeyringConfig
from stability_matrix_tools.models.settings import env

app = typer.Typer(no_args_is_help=True)
cp = rich.print


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

    @staticmethod
    def compare(base_repo: Repository, base: Commit, head_repo: Repository, head: Commit):
        head_part = f"{head_repo.owner.login}:{head_repo.name}:{head.sha}"
        return base_repo.compare(base.sha, head_part)


def format_repo(repo: Repository) -> str:
    return repo.url.removeprefix("https://github.com/")


@app.command()
def auth():
    """Test GitHub authentication."""
    ctx = GitContext()

    cp(f"Authenticated with GitHub as: {ctx.gh_user.login}")


@app.command()
def private_main_to_dev():
    """Creates a PR to merge private/main into private/dev."""
    ctx = GitContext()

    private_repo = ctx.get_private_repo()
    private_repo_str = format_repo(private_repo)
    private_main = private_repo.get_branch("main")

    # create a new branch from private/main
    merge_branch_name = f"merge-main-to-dev-{private_main.commit.sha[:7]}"
    private_repo.create_git_ref(
        ref=f"refs/heads/{merge_branch_name}",
        sha=private_main.commit.sha,
    )

    cp(f"Creating branch: {private_repo_str}/{merge_branch_name} from {private_repo_str}/main @ {private_main.commit.sha[:7]}")
    cp(f"Creating PR: {private_repo_str}/{merge_branch_name} -> {private_repo_str}/dev")

    # create a PR from private/main to private/dev
    pr = private_repo.create_pull(
        title="Merge main to dev",
        body="",
        base="dev",
        head=merge_branch_name,
    )

    cp(f"✅  Created PR: [cyan link={pr.url}]{pr.title} #{pr.number}[/cyan link]")


@app.command()
def private_dev_to_main():
    """Creates a PR to merge private/dev into private/main."""
    ctx = GitContext()

    private_repo = ctx.get_private_repo()
    private_repo_str = format_repo(private_repo)
    private_dev = private_repo.get_branch("dev")

    # create a new branch from private/dev
    merge_branch_name = f"merge-dev-to-main-{private_dev.commit.sha[:7]}"
    private_repo.create_git_ref(
        ref=f"refs/heads/{merge_branch_name}",
        sha=private_dev.commit.sha,
    )

    cp(f"Creating branch: {private_repo_str}/{merge_branch_name} from {private_repo_str}/dev @ {private_dev.commit.sha[:7]}")
    cp(f"Creating PR: {private_repo_str}/{merge_branch_name} -> {private_repo_str}/main")

    # create a PR from private/main to private/dev
    pr = private_repo.create_pull(
        title="Merge dev to main",
        body="",
        base="main",
        head=merge_branch_name,
    )

    cp(f"✅  Created PR: [cyan link={pr.url}]{pr.title} #{pr.number}[/cyan link]")

