from src.config import Settings, get_settings


def test_live_mode_is_default_without_dotenv(monkeypatch):
    monkeypatch.delenv("YOJANA_MOCK_MODE", raising=False)
    assert Settings(_env_file=None).yojana_mock_mode is False


def test_mock_mode_requires_explicit_opt_in(monkeypatch):
    monkeypatch.setenv("YOJANA_MOCK_MODE", "true")
    assert Settings(_env_file=None).yojana_mock_mode is True


def test_settings_refresh_after_environment_change(monkeypatch):
    monkeypatch.setenv("YOJANA_MOCK_MODE", "true")
    assert get_settings().yojana_mock_mode is True
    monkeypatch.setenv("YOJANA_MOCK_MODE", "false")
    assert get_settings().yojana_mock_mode is False
