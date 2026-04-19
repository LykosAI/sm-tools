import re

from github import Auth, Github
from github.Commit import Commit
from github.Repository import Repository

from stability_matrix_tools.models.keyring_config import ConfigKey, KeyringConfig
from stability_matrix_tools.models.settings import env


class GithubContext:
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