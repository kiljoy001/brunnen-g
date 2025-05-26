import keyring
import asyncio

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

class ConfigManagerAsync():
    """Configuration Manager that handles methods async"""
    OPERATION_MAPPING = {
        'set_password': {
            'exception': keyring.errors.PasswordSetError,
            'error_template': "Saving the {service} password failed",
            'unexpected_template': "Unexpected error saving {service} password"
        },
        'get_password': {
            'exception': PasswordGetError,
            'error_template': "Retrieving the password for {username} failed",
            'unexpected_template': "Unexpected error retrieving the password for {username}"
        },
        'delete_password': {
            'exception': keyring.errors.PasswordDeleteError,
            'error_template': "Unable to remove password for {service}",
            'unexpected_template': "Unexpected error removing {service} password"
        },
    }
    
        # Default mapping for unregistered operations
    DEFAULT_MAPPING = {
        'exception': keyring.errors.KeyringError,
        'error_template': "Operation on {service} failed",
        'unexpected_template': "Unexpected error during operation on {service}"
    }
    def __init__(self, keyring_backend=None):
        self.keyring = keyring_backend
        self._locks = {}
    
    
    def _get_lock(self, username: str) -> asyncio.Lock():
        if username not in self._locks:
            self._locks[username] = asyncio.Lock()
        return self._locks[username]
    
    async def _execute_keyring_operation(self, username: str, operation_name: str, error_msg: str, *args, **kwargs):
        """Generic Method to execute keyring operations with proper locking and error handling
        Args:
            username: Username to acquire lock for
            operation_name: Name of the keyring method
            error_msg: Base error messae for the exceptions
            *args, **kwargs: Arguments to pass to the keyring method
        """
        async with self._get_lock(username):
            try:
                if not hasattr(self.keyring, operation_name):
                    raise AttributeError(f"Keyring has no method for {operation_name}.")
                method = getattr(self.keyring, operation_name)
                if asyncio.iscoroutinefunction(method):
                    return await method(*args, **kwargs)
                else:
                    return methodd(*args, **kwargs)
            except keyring.errors.KeyringError as error:
                match operation_name:
                    case op if op in self.OPERATION_MAPPING:
                        mapping = self.OPERATION_EXCEPTIONS[op]
                        template = mapping['error_template']
                        exception_class = mapping['exception']
                    case _:
                        mapping = self.DEFAULT_MAPPING
                        template = mapping['error_template']
                        exception_class = mapping['exception']
                message = template.format(serivce=service, username=username)
                raise exception_class(f"{message}:\n{error}")
            except Exception as error:
                match operation_name:
                    case op if op in self.OPERATION_MAPPING:
                        mapping = self.OPERATION_MAPPING[op]
                        template = mapping['unexpected_template']
                        exception_class = mapping['exception']
                    case _:
                        mapping = self.DEFAULT_MAPPING
                        template = mapping['unexpected_template']
                        exception_class = mapping['exception']
                message = template.format(serivce=service, username=username)
                raise exception_class(f"{message}:\n{error}")

    async def save_login(self, service_name: str, username: str, password: str):
        await self._execute_keyring_operation(
            username, 'set_password', service_name, *[service_name, username, password]
            )
    
    async def load_login(service_name: str, username: str, password: str) -> str:
        return "false"
