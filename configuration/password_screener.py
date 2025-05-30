import hashlib
import mmh3
import numpy as np
from typing import Set, List

class BloomFilter():
    """Creates a bloom filter for detecting breached passwords from a list"""
    
class PasswordScreener():
    """
    Hybrid password screener that uses a hash table and bloom filter
    Args:
        common_passwords_file: path the most common passwords
        rare_passwords_file: path to file with additonal rare but compromised passwords
    """

    def __init__(self, common_password_file: str, rare_password_file: str = None):
         pass

    def is_password_compromised(self, password):
        pass
