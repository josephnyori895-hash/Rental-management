"""Configuration tests: defaults must be portable and honest."""

from __future__ import annotations

from pathlib import Path

from app.core.config import PROJECT_ROOT, Settings


def _defaults() -> Settings:
    """Settings with the .env file deliberately ignored."""
    return Settings(_env_file=None)


def test_project_root_points_at_repository():
    assert (PROJECT_ROOT / "backend" / "app").is_dir()


def test_default_storage_path_derives_from_project_root():
    """
    Regression: this default used to be the literal
    "/home/nyorii/Projects/rental-os/storage", which silently broke on any
    other machine. It must now track the module's own location.
    """
    assert _defaults().STORAGE_LOCAL_PATH == PROJECT_ROOT / "storage"


def test_config_source_has_no_hardcoded_absolute_paths():
    """Guard against absolute path literals creeping back into config.py."""
    source = (PROJECT_ROOT / "backend" / "app" / "core" / "config.py").read_text()
    assert 'Path("/' not in source
    assert "Path('/" not in source


def test_removed_settings_are_gone():
    """
    These were declared but had no implementing code anywhere in the project,
    so they were pruned rather than left to imply working features.
    """
    removed = [
        "REDIS_URL",
        "STORAGE_BACKEND",
        "GOOGLE_DRIVE_CLIENT_ID",
        "GOOGLE_DRIVE_CLIENT_SECRET",
        "CCTV_STORAGE_PATH",
        "CCTV_RETAIN_DAYS",
        "OLLAMA_BASE_URL",
        "AI_MODEL",
        "OPENAI_API_KEY",
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USER",
        "SMTP_PASSWORD",
        "EMAIL_FROM",
        "DEFAULT_CURRENCY",
        "TRIAL_DAYS",
    ]
    defaults = _defaults()
    for name in removed:
        assert not hasattr(defaults, name), f"{name} should have been pruned"


def test_kept_settings_still_resolve():
    defaults = _defaults()
    assert defaults.API_PREFIX == "/api/v1"
    assert defaults.MPESA_ENVIRONMENT == "sandbox"
    assert defaults.DEFAULT_TAX_RATE == 0.16
    assert defaults.ACCESS_TOKEN_EXPIRE_MINUTES > 0
    assert defaults.DATABASE_POOL_SIZE > 0


def test_effective_jwt_secret_prefers_jwt_secret():
    assert _defaults().model_copy(
        update={"JWT_SECRET": None, "SECRET_KEY": "a"}
    ).effective_jwt_secret == "a"

    both = _defaults().model_copy(update={"JWT_SECRET": "b", "SECRET_KEY": "a"})
    assert both.effective_jwt_secret == "b"


def test_database_url_is_async():
    assert str(_defaults().DATABASE_URL).startswith("postgresql+asyncpg://")


def test_paths_are_path_objects():
    assert isinstance(_defaults().STORAGE_LOCAL_PATH, Path)


def test_production_rejects_default_security_secrets():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="Invalid production security configuration"):
        Settings(_env_file=None, APP_ENV="production", SECRET_KEY="change-me-in-production", JWT_SECRET=None, ENCRYPTION_KEY="change-me-in-production")


def test_production_accepts_explicit_strong_secrets():
    settings = Settings(
        _env_file=None,
        APP_ENV="production",
        SECRET_KEY="s" * 48,
        JWT_SECRET="j" * 48,
        ENCRYPTION_KEY="ab" * 32,
    )
    assert settings.effective_jwt_secret == "j" * 48


def test_production_rejects_malformed_encryption_key():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="ENCRYPTION_KEY"):
        Settings(
            _env_file=None,
            APP_ENV="production",
            SECRET_KEY="s" * 48,
            JWT_SECRET="j" * 48,
            ENCRYPTION_KEY="not-a-hex-key",
        )
