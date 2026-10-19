from envfile import parse_env


def test_basic():
    text = "# settings\nNAME=demo\nexport PORT=8080\n"
    assert parse_env(text) == {"NAME": "demo", "PORT": "8080"}


def test_single_quoted():
    assert parse_env("GREETING='hello world'") == {"GREETING": "hello world"}
