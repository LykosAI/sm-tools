import yaspin
from yaspin.core import Yaspin


class Yaspin2(Yaspin):
    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.ok(f"[✔] {self.text}")
        super().__exit__(exc_type, exc_value, traceback)


def spinner(text: str = "", **kwargs) -> Yaspin:
    return yaspin.yaspin(text=text, timer=True, **kwargs)
