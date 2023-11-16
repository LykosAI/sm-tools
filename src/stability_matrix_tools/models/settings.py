import dotenv
from pydantic.v1 import BaseSettings


class EnvSettings(BaseSettings):
    update_manifest_url: str = "https://cdn.lykos.ai/update.json"

    cdn_root: str = "https://cdn.lykos.ai"

    # apis
    b2_api_id: str
    b2_api_key: str
    b2_bucket_name: str = "lykos-1"

    cf_zone_id: str
    cf_cache_purge_token: str

    # git repos
    git_repo_private: str = "https://github.com/ionite34/StabilityMatrix"
    git_repo_fork: str = "https://github.com/LykosAI/StabilityMatrix-Dev"
    git_repo_public: str = "https://github.com/LykosAI/StabilityMatrix"

    # debug
    verbose: bool = False

    class Config:
        env_file = dotenv.find_dotenv(usecwd=True)
        env_prefix = "sm_"


env = EnvSettings()
