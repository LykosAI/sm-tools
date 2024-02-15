import subprocess


class GitProcess:
    def __init__(self, cwd: str):
        """Initialize a new GitRunner."""
        self.process_path = "git"
        self.cwd = cwd

    def run_cmd(self, cmd: str, *args: str):
        """Run a command and return the output."""
        return subprocess.check_output(
            [self.process_path, cmd, *args], cwd=self.cwd, shell=True
        ).decode("utf-8")
