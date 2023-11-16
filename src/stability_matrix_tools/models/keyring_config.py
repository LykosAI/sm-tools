from __future__ import annotations

import enum
import json
import keyring


class ConfigKey(enum.StrEnum):
    GITHUB_TOKEN = "GITHUB_TOKEN"


class KeyringConfig(dict[ConfigKey, str]):
    KR_SERVICE_NAME: str = "sm-tools"
    KR_USERNAME: str = "config"

    def __enter__(self) -> KeyringConfig:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.save()

    @classmethod
    def load_from_keyring(cls) -> KeyringConfig:
        """Load the configuration from the keyring."""
        json_str = keyring.get_password(cls.KR_SERVICE_NAME, cls.KR_USERNAME)
        if json_str is None:
            return cls()
        return cls(**json.loads(json_str))

    def get_with_prompt(self, key: ConfigKey):
        if key in self:
            return self[key]
        else:
            import rich
            import typer

            rich.print(f"[red]Error:[/red] Required config key '{key.value}' not set. "
                       f"Please run 'sm-tools config set {key.value} {{value}}' to set it.")

            raise typer.Exit(1)

    def save(self):
        """Save the configuration to the keyring."""
        json_str = json.dumps(self)
        keyring.set_password(self.KR_SERVICE_NAME, self.KR_USERNAME, json_str)

    def to_keys_json(self) -> str:
        """Convert the configuration to a keys.json file."""
        result = {}
        for key in ConfigKey:
            if key in self:
                if self[ConfigKey(key)]:
                    # valid key
                    result[key] = "********"
                else:
                    # empty key
                    result[key] = ""
            else:
                # missing key
                result[key] = "(not set)"

        return json.dumps(result, indent=2)
