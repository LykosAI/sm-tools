from urllib.parse import urljoin

import dotenv
from pydantic.v1 import BaseSettings


class EnvSettings(BaseSettings):
    update_manifest_url: str = "https://cdn.lykos.ai/update.json"

    cdn_root: str = "https://cdn.lykos.ai"

    # apis
    b2_api_id: str
    b2_api_key: str
    b2_bucket_name: str = "lykos-1"
    b2_bucket_secure_name: str = "lykos-s1"

    cf_zone_id: str
    cf_cache_purge_token: str

    # git repos
    git_repo_private: str = "https://github.com/ionite34/StabilityMatrix"
    git_repo_fork: str = "https://github.com/LykosAI/StabilityMatrix-Dev"
    git_repo_public: str = "https://github.com/LykosAI/StabilityMatrix"

    # override signing key
    signing_private_key: str | None = None

    # debug
    verbose: bool = False

    @property
    def cdn_root_secure(self) -> str:
        return urljoin(self.cdn_root, self.b2_bucket_secure_name.replace("lykos-", "", 1))

    class Config:
        env_file = dotenv.find_dotenv(usecwd=True)
        env_prefix = "sm_"


env = EnvSettings()
