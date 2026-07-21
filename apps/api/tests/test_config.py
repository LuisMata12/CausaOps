from app.config import Settings


def test_cors_origins_accept_comma_separated_environment_value() -> None:
    settings = Settings(CORS_ORIGINS="http://localhost:3000,https://causaops.example")

    assert settings.cors_origins == [
        "http://localhost:3000",
        "https://causaops.example",
    ]
