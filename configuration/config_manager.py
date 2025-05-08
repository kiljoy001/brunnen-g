import keyring

class PasswordGetError(keyring.errors.KeyringError):
    """Raised when password can't be retrieved"""

class ConfigManager():
    def __init__(self):
        self.service_name = 'emercoin'

    def save_emercoin_login(self, username: str, password: str):
        """Saves the username & password in a os level keyring for safe storage"""
        try:
            keyring.set_password(self.service_name, username, password)
        except keyring.errors.KeyringError as e:
            raise keyring.errors.PasswordSetError(f"Saving the emercoin password failed:\n{e}")
        except Exception as e:
            raise keyring.errors.PasswordSetError(f"Unexpected error saving emercoin password:\n{e}")
    
    def load_emercoin_login(self, username: str):
        """Retrives the emercoin login from the keyring"""
        try:
            return keyring.get_password(self.service_name, username)
        except keyring.errors.KeyringError as e:
            raise PasswordGetError(f"Retriving the password for {username} failed:\n{e}")
        except Exception as e:
            raise PasswordGetError(f"Unexpected error retriving the password for {username}:\n{e}")

    def remove_emercoin_password(self, username: str):
        """Removes emercoin node password, which deactivates the user"""
        try:
            keyring.delete_password(self.service_name, username)
        except keyring.errors.KeyringError as e:
            raise keyring.errors.PasswordDeleteError(f"Unable to remove password for emercoin\n{e}")
        except Exception as e:
            raise keyring.errors.PasswordDeleteError(f"Unexpected error removing emercoin password:\n{e}")

    def reset_emercoin_login(self, username: str, password: str):
        """Resets stored login for emercoin node"""
        original_password = None

        def handle_restoration(error_message, error_type):
            """Helper function to handle error and restoration logic"""
            if original_password:
                try:
                    self.save_emercoin_login(username, original_password)
                except Exception:
                    pass
            return error_type(f"{error_message}\n{e}")

        try:
            original_password = self.load_emercoin_login(username)
            self.remove_emercoin_password(username)
            self.save_emercoin_login(username, password)
        except keyring.errors.PasswordDeleteError as e:
            raise handle_restoration(
                f"Unable to remove password for {username}",
                keyring.errors.PasswordDeleteError
            )
        except keyring.errors.PasswordSetError as e:
            raise handle_restoration(
                "Saving the new password failed!",
                keyring.errors.PasswordSetError
            )
        except Exception as e:
            raise handle_restoration(
                f"Unexepected error resetting login {username}:",
                keyring.errors.KeyringError
            )