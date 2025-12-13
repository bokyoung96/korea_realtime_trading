import json
from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class DatabaseConfig:
    supabase_url: str
    supabase_key: str
    postgres_url: str
    pool_settings: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_json(cls, config_path: str = "src/database/config_db.json") -> 'DatabaseConfig':
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        db_config = config.get("database", {})

        if not all(k in db_config for k in ["supabase_url", "supabase_key", "postgres_url"]):
            raise ValueError(
                "Database configuration is missing required keys in config_db.json")

        return cls(
            supabase_url=db_config["supabase_url"],
            supabase_key=db_config["supabase_key"],
            postgres_url=db_config["postgres_url"],
            pool_settings=db_config.get("pool_settings", {})
        )
