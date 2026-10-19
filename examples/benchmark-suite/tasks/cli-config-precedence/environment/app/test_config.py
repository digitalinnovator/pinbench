from config import load_settings


def test_defaults():
    assert load_settings({}) == {"timeout": 30, "retries": 3, "prefix": "app"}


def test_env_timeout_zero():
    assert load_settings({"APP_TIMEOUT": "0"})["timeout"] == 0
