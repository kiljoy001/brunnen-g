import pytest
import tempfile
import string
import os
from hypothesis import given, settings, event, strategies as st
from configuration.password_screener import PasswordScreener

class TestPasswordScreener:
    @pytest.fixture
    def common_password_file(self):
        """Create a temorary file with common passwords for testing"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("password\nqwerty123456\nadmin\nwelcome2025\nletmein1234")
        filename = f.name
        yield filename
        # clean up after tests
        os.unlink(filename)

    @pytest.fixture
    def rare_password_file(self):
        """Create a temporary file with rare passwords for testing"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write("war19411945\nWarcraft1\nm820\nm!6jAnlik0Mt97")
        filename = f.name
        yield filename
        os.unlink(filename)

    @pytest.fixture
    def password_screener(self, common_password_file, rare_password_file):
        """Create a password screener with test files"""
        return PasswordScreener(common_password_file, rare_password_file)

    @pytest.fixture(scope="module")
    def full_password_screener(self):
        """Create a password screener using the production lists"""
        config_dir = os.path.join(os.path.dirname(__file__), "..", "configuration")
        return PasswordScreener(
            os.path.join(config_dir, "100k_common_passwords.txt"),
            os.path.join(config_dir, "10_million_common_passwords.txt")
        )

    def test_common_password_detection(self, password_screener):
        """Tests that common passwords are detected"""
        assert password_screener.is_password_compromised("password") == True
        assert password_screener.is_password_compromised("qwerty123456") == True

    def test_rare_password_detection(self, password_screener):
        """Test that rare passwords in the bloom filter are detected"""
        assert password_screener.is_password_compromised("war19411945") == True
        assert password_screener.is_password_compromised("warcraft1") == True

    def test_handles_case_senstivity(self, password_screener):
        assert password_screener.is_password_compromised("PASSWORD") != password_screener.is_password_compromised("password")
    
    @settings(max_examples=1000)
    @given(random_password=st.text(alphabet=string.ascii_letters + string.digits + string.punctuation, min_size=15, max_size=50))
    def test_random_password_false_positive_rate(self, full_password_screener, random_password):
        """Test that bloom filter false postive rate is acceptable"""
        result = full_password_screener.is_password_compromised(random_password)
        event("Password accepted" if not result else "Password rejected")

    def test_performance(self, password_screener):
        """Test that password screener is performant"""
        import time

        start_time = time.time()
        iterations = 1000


        for _ in range(iterations):
            password_screener.is_password_compromised("password")
            password_screener.is_password_compromised("warcraft1")
            password_screener.is_password_compromised("notinthelist")

        elapsed = time.time() - start_time
        avg_time = elapsed / (iterations * 3)

        print(f"Average check time: {avg_time*1000:.2f}ms")
        assert avg_time < 0.001, "Password checking too slow"