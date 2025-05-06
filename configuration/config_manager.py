import keyring

class PasswordGetError(keyring.errors.KeyringError):
    """Raised when password can't be retrieved"""

class ConfigManager():
    def __init__(self):
        self.service_name = 'emercoin'

    def save_emercoin_login(self, username: str, password: str):
        try:
            keyring.set_password(self.service_name, username, password)
        except keyring.errors.KeyringError as e:
            raise keyring.errors.PasswordSetError(f"Saving the emercoin password failed:\n{e}")
        except Exception as e:
            raise keyring.errors.PasswordSetError(f"Unexpected error saving emercoin password:\n{e}")
    
    def load_emercoin_login(self, username: str):
        try:
            return keyring.get_password(self.service_name, username)
        except keyring.errors.KeyringError as e:
            raise PasswordGetError(f"Retriving the password for {username} failed:\n{e}")
        except Exception as e:
            raise PasswordGetError(f"Unexpected error retriving the password for {username}:\n{e}")

    def remove_emercoin_password(self, username: str):
        try:
            keyring.delete_password(self.service_name, username)
        except keyring.errors.KeyringError as e:
            raise keyring.errors.PasswordDeleteError(f"Unable to remove password for emercoin\n{e}")
        except Exception as e:
            raise keyring.errors.PasswordDeleteError(f"Unexpected error removing emercoin password:\n{e}")