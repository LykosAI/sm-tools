from __future__ import annotations

from b2sdk.progress import AbstractProgressListener
from rich.progress import Progress


class RichProgressListener(AbstractProgressListener):
    """
    Progress listener using rich.
    """

    def __init__(
        self,
        description: str,
        provided: Progress | None = None,
        transient: bool = False,
    ):
        super().__init__()
        self.description = description
        self.progress = provided  # set in set_total_bytes()
        self.task = None
        self.total_bytes = None
        self.transient = transient  # don't close the progress bar when done
        self.last = 0

    def set_total_bytes(self, total_byte_count):
        if self.progress is None:
            self.progress = Progress(transient=self.transient)
            self.progress.start()
        self.end_existing()
        self.task = self.progress.add_task(
            self.description, total=total_byte_count, start=True
        )
        self.total_bytes = total_byte_count
        self.progress.update(self.task, advance=50, refresh=True)

    def end_existing(self):
        # Check existing tasks and end them
        for task in self.progress.tasks:
            task.completed = True
            task.visible = False

    def bytes_completed(self, byte_count):
        self.progress.update(self.task, advance=byte_count - self.last)
        self.last = byte_count

    def close(self):
        if self.progress is not None:
            self.progress.update(self.task, completed=self.total_bytes)
            self.progress.stop()
