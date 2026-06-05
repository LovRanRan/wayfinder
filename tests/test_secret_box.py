import pytest

from wayfinder.api.secret_box import decrypt_secret, encrypt_secret


def test_secret_box_round_trips_without_plaintext() -> None:
    envelope = encrypt_secret("sk-test-secret", "unit-test-key")

    assert envelope.startswith("v1:")
    assert "sk-test-secret" not in envelope
    assert decrypt_secret(envelope, "unit-test-key") == "sk-test-secret"


def test_secret_box_rejects_wrong_key_material() -> None:
    envelope = encrypt_secret("sk-test-secret", "unit-test-key")

    with pytest.raises(ValueError, match="authentication failed"):
        decrypt_secret(envelope, "wrong-key")
