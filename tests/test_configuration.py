import contextlib
import pytest
import keyring
import string
import re
import hashlib
from keyring.backend import KeyringBackend
from keyring.errors import KeyringError, PasswordSetError
from hypothesis import given, strategies as st
from configuration.config_manager import ConfigManager, PasswordGetError

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

class RemoveFailureKeyring(MockKeyringBackend):
    def delete_password(self, service_name, username):
        raise KeyringError("Simulated delete failure")
    
    def get_password(self, service_name, username):
        return "original_password"

class SaveNewFailureKeyring(MockKeyringBackend):
    def __init__(self):
        super().__init__()
        self.deleted = False

    def delete_password(self, service_name, username):
        self.deleted = True
        return None
    
    def get_password(self, service_name, username):
        return "original password"

    def set_password(self, service_name, username, password):
        if self.deleted:
            raise keyring.errors.PasswordSetError("Simulated new password failure")
        return None

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

@given(credentials=non_overlapping_credentials())
def test_appropiate_errors_raised(credentials):

    def capture_error(error_class, function, *args, **kwargs):
        """helper function to capture errors"""
        with pytest.raises(error_class) as error_info:
            function(*args, **kwargs)
        return error_info.value.args[0]
    
    def has_special_characters(text):
        return bool(re.search(r'[^\w\s]', text))

    def tokenize_text(text):
        """Use regex to tokenize text into words, handles delimiters and special characters"""
        return set(word for word in text.split() if word)

    def check_password_not_leaked(error_message, password):
        """Check if a password has been leaked in an error message"""
        if password in error_message:
            if len(password) > 3:
                pattern = r'\b' + re.escape(password) + r'\b'
                if not re.search(pattern, error_message):
                    return True
            return False
        
        tokenized_error = tokenize_text(error_message)

        if has_special_characters(password):
            password_hash = hashlib.sha256(password.encode()).hexdigest()[:8]
            hashed_tokens = (hashlib.sha256(x.encode()).hexdigest()[:8] for x in tokenized_error)
            for ht in hashed_tokens:
                if ht == password_hash:
                    return False
        else:
            if password in tokenized_error:
                return False
        
        return True

    with keyring_context(ErrorRaisingKeyringBackend()):
        # Arrange
        config = ConfigManager()
        username, passwords = credentials
        password, new_password = passwords

        # Act
        save_error = capture_error(
            keyring.errors.PasswordSetError,
            config.save_emercoin_login,
            username,
            password
        )

        load_error = capture_error(
            PasswordGetError,
            config.load_emercoin_login,
            username
        )

        remove_error = capture_error(
            keyring.errors.PasswordDeleteError,
            config.remove_emercoin_password,
            username
        )

        reset_error = capture_error(
            keyring.errors.KeyringError,
            config.reset_emercoin_login,
            username,
            new_password
        )

        with keyring_context(RemoveFailureKeyring()):
            config = ConfigManager()
            remove_fail_error = capture_error(
                keyring.errors.PasswordDeleteError,
                config.reset_emercoin_login,
                username, 
                new_password
            )
            assert f"Unable to remove password for {username}" in remove_fail_error
            assert "Simulated delete failure" in remove_fail_error
            assert check_password_not_leaked(remove_fail_error, new_password), "New password leaked in remove error"

        with keyring_context(SaveNewFailureKeyring()):
            config = ConfigManager()
            save_new_fail_error = capture_error(
                keyring.errors.PasswordSetError,
                config.reset_emercoin_login,
                username,
                new_password
            )
            assert "Saving the new password failed" in save_new_fail_error
            assert "Simulated new password failure" in save_new_fail_error
            assert check_password_not_leaked(save_new_fail_error, new_password), "New password leaked in save error"
        
        #Assert
        # Basic error messages
        assert "Saving the emercoin password failed:" in save_error
        assert f"Retriving the password for {username} failed:" in load_error
        assert "Unable to remove password for emercoin" in remove_error

        #Reset error
        assert f"Unexepected error resetting login {username}:" in reset_error

        # Test for sensistive data exposure
        assert check_password_not_leaked(save_error, password), "Password leaked in save error"
        assert check_password_not_leaked(reset_error, new_password), "New password leaked in reset error"
        



        

