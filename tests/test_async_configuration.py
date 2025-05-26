import keyring
import pytest
import contextlib
from hypothesis import given, strategies as st, settings
from keyring.backend import KeyringBackend
from keyring.errors import KeyringError

class MockKeyringBackendAsync(KeyringBackend):
    """Async version of the mock keyring"""
    def __init__(self):
        self.passwords = {}

    async def set_password(self, service_name: str, username: str, password: str) -> None:
        self.passwords[(service_name, username)] = password
        return None
    
    async def get_password(self, service_name: str, username: str) -> str:
        return self.passwords.get((service_name, username))
    
    async def delete_password(self, service_name: str, username: str) -> None:
        if (service_name, username) in self.passwords:
            del self.passwords[(service_name, username)]
        else:
            raise keyring.errors.PasswordDeleteError("Password not found!")

class RemoveFailureKeyringAsync(KeyringBackend):
    """Async version of the remove failure keyring"""
    async def delete_password(self, service_name: str, username: str) -> KeyringError:
        raise KeyringError("Simulated delete failure")
    
    async def get_password(self, service_name: str, username: str) -> str:
        return "original_password"


class ErrorRaisingKeyringBackendAsync(KeyringBackend):
    """A mock keyring that alwasy raises exceptions for testing error handling"""
    async def get_password(self, service_name: str, username: str) -> KeyringError:
        raise KeyringError("Simulated error in get password method")
    
    async def set_password(self, service_name: str, username: str, password: str) -> KeyringError:
        raise KeyringError("Simulated error in set password method")
    
    async def delete_password(self, service_name: str, username: str) -> KeyringError:
        raise KeyringError("Simulated error in delete password method")

@contextlib.asynccontextmanager
async def keyring_context(backend_instance: KeyringBackend) -> KeyringBackend:
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

@st.composite
def non_overlapping_credentials(draw):
    """
    Strategy to generate a username and two different passwords
    where none is a substring of another
    """
    # First generate a username
    username = draw(st.text(min_size=1, max_size=20, alphabet=string.ascii_letters + string.digits))
    
    # define common error text not use as a password for false postives
    common_error_terms = {
        'emercoin', 'password', 'login', 'failed', 'simulated', 'error',
        'retriving', 'remove', 'unable', 'saving', 'method', 'unexpected'
    }
    
    # Use the existing different_passwords strategy but add non-overlap constraint
    passwords = draw(different_passwords().filter(
        lambda pwd_pair: (username not in pwd_pair[0]) and (pwd_pair[0] not in username) and
                         (username not in pwd_pair[1]) and (pwd_pair[1] not in username) and
                         not any(term.lower() in pwd_pair[0].lower() or pwd_pair[0].lower() in term.lower()
                         for term in common_error_terms) and
                         not any(term.lower() in pwd_pair[1].lower() or pwd_pair[1].lower() in term.lower() 
                         for term in common_error_terms)
    ))
    
    return (username, passwords)

@pytest.mark.asyncio
@given(username=st.text(min_size=1), password=st.text(min_size=1))
async def test_config_load_save_credentials(username, password):
    #Arrange
    with keyring_context(MockKeyringBackendAsync()) as mock_keyring:
        config = ConfigManagerAsync()
        service_name = "emercoin"
        mock_keyring.set_password(service_name, username, password)
        await config.save_login(service_name, username, password)
    #Act
        result = await config.load_login(service_name, username)
    #Assert
        result == mock_keyring.get_password(service_name, username)
