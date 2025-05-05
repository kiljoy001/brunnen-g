import contextlib
import pytest
import keyring
from keyring.backend import KeyringBackend
from hypothesis import given, strategies as st
from configuration.config_manager import ConfigManager

class MockKeyringBackend(KeyringBackend):
    """A mock keyring implementation for testing"""

    def __init__(self):
        self.passwords = {}

    def set_password(self, service_name, username, password):
        self.passwords[(service_name, username)] = password
        return None

    def get_password(self, service_name, username):
        return self.passwords.get((service_name, username))

    def delete_password(self, service_name, username):
        if (service_name, username) in self.passwords:
            del self.passwords[(service_name, username)]
        else:
            raise keyring.errors.PasswordDeleteError("Password not found!")

@contextlib.contextmanager
def mock_keyring_context():
    mock_backend = MockKeyringBackend()
    original_backend = keyring.get_keyring()
    keyring.set_keyring(mock_backend)
    try:
        yield mock_backend
    finally:
        keyring.set_keyring(original_backend)

@given(username=st.text(min_size=1), password=st.text(min_size=1))
def test_config_save_load_credentials(username, password):
    with mock_keyring_context() as mock_keyring:
        # Arrange
        config = ConfigManager()
        service_name = "emercoin"
        mock_keyring.set_password(service_name, username, password)
        config.save_emercoin_login(username, password)

        # Act
        result = config.load_emercoin_login(username)

        # Assert
        assert result == mock_keyring.get_password(service_name, username)