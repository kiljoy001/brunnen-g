import contextlib
import pytest
import keyring
from keyring.backend import KeyringBackend
from keyring.errors import KeyringError, PasswordSetError
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

class ErrorRaisingKeyringBackend(KeyringBackend):
    """A mock keyring that alwasy raises exceptions for testing error handling"""
    
    def set_password(self, service_name: str, username: str, password: str):
        raise KeyringError("Simulated error in set password method")
    
    def get_password(self, service_name: str, username: str):
        raise KeyringError("Simulated error in get_password")

    def delete_password(self, service_name, username):
        raise KeyringError("Simulated error in delete_password")

@contextlib.contextmanager
def keyring_context(backend_instance: KeyringBackend):
    original_backend = keyring.get_keyring()
    keyring.set_keyring(backend_instance)
    try:
        yield backend_instance
    finally:
        keyring.set_keyring(original_backend)

@st.composite
def different_passwords(draw):
    """Strategy to generate two different passwords"""
    password1 = draw(st.text(min_size=1))
    password2 = draw(st.text(min_size=1).filter(lambda p: p != password1))
    return (password1, password2)

@given(username=st.text(min_size=1), password=st.text(min_size=1))
def test_config_save_load_credentials(username, password):
    with keyring_context(MockKeyringBackend()) as mock_keyring:
        # Arrange
        config = ConfigManager()
        service_name = "emercoin"
        mock_keyring.set_password(service_name, username, password)
        config.save_emercoin_login(username, password)

        # Act
        result = config.load_emercoin_login(username)

        # Assert
        assert result == mock_keyring.get_password(service_name, username)

@given(username=st.text(min_size=1), password=st.text(min_size=1))
def test_config_removes_password(username, password):
    with keyring_context(MockKeyringBackend()) as mock_keyring:
        # Arrange
        config = ConfigManager()
        config.save_emercoin_login(username, password)

        # Act - remove passwords from both keyrings
        config.remove_emercoin_password(username)
        result = config.load_emercoin_login(username)

        # Assert
        assert result  is  None

@given(username=st.text(min_size=1), passwords=different_passwords())
def test_config_resets_new_password(username, passwords):
    password, new_password = passwords
    with keyring_context(MockKeyringBackend()) as mock_keyring:
        # Arrange
        config = ConfigManager()
        config.save_emercoin_login(username, password)

        # Act
        config.reset_emercoin_login(username, new_password)
        result = config.load_emercoin_login(username) 
        
        # Assert
        assert result == new_password
        assert result != password, "New password should be different from the original."

@given(username=st.text(min_size=1, max_size=50), password=st.text(min_size=1, max_size=50))
def test_appropiate_errors_raised(self, username, password):
    pass
