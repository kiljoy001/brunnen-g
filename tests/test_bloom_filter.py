import os
import string
import pytest
from pathlib import Path
from hypothesis import settings, given, strategies as st
from concurrent.futures import ProcessPoolExecutor

from configuration.password_screener import BloomFilter

class TestBloomFilter:
    """Tests for the BloomFilter class"""

    @pytest.fixture
    def bloom_filter_factory():
        """Factory fixture that returns a function to greacte bloom filters with specified size"""
        def _create_bloom_filter(size="small", **kwargs):
            configs = {
                "small": {"capacity": 100, "error_rate": 0.01},
                "medium": {"capacity": 10000, "error_rate": 0.001},
                "large": {"capacity": 1000000, "error_rate": 0.0001},
            }

            base_config = configs.get(size, config["small"])
            base_config.update(kwargs)
            return BloomFilter(**base_config)
        return _create_bloom_filter

    def test_initialzation(self, bloom_filter_factory):
        """Test that bloom filter initailizes with the correct parameters"""
        # Arrange & Act
        bf = bloom_filter_factory()

        #Assert

        # Check basic properties
        assert bf.capacity == 100
        assert bf.error_rate == 0.01
        assert bf.items_added == 0

        # Check derived properties
        assert bf.size > 0
        assert bf.hash_count > 0
        assert isinstance(bf.bit_array, np.ndarray)
        assert bf.bit_array.dtype == np.bool_

    def test_adding_items(self, bloom_filter_factory):
        """Test adding items to the bloom filter"""
        # Arrange
        bf = bloom_filter_factory()

        # Act
        items = ["password1", "test123", "securepass"]
        for item in items:
            bf.add(item)
        
        for item in items:
            bf.check(item)

        # Assert
        assert bf.items_added == len(items)
        assert np.sum(bf.bit_array) > 0

    def test_check_missing_items(self, bloom_filter_factory):
        """Test checking for items not in the bloom filter"""
        # Arrange 
        bf = bloom_filter_factory()

        # Act
        bf.add("password1")
        bf.add("test123")

        # Assert 
        assert not bf.check("missing_item")
        assert not bf.check("some other item")

    @given(items=st.lists(
        st.text(min_size=1, max_size=20, alphabet=st.characters(
            blacklist_catagories('Cs',))),
             min_size=5, max_size=50, unique=True
             ))
    def test_all_items_found(self, items, bloom_filter_factory):
        """Property test - all added items must be found"""
        # Arrange
        bf = bloom_filter_factory()

        # Act
        for item in items:
            bf.add(item)

        # Assert
        for item in items:
            assert bf.check(item)

    @settings(max_examples=150)
    @given(
        items=st.lists(
            st.text(min_size=5, max_size=20),
            min_size=90, max_size=100, unique=True
        )
    )
    def test_false_positive_rate(self, items, bloom_filter_factory):
        """Test that false positive rate is within expected bounds"""
        # Arrange
        bf = bloom_filter_factory()
        added_items = items[:80]
        test_items = items[80:]

        #Act
        for item in items:
            bf.add(item)
        fales_positives = sum(1 for item in test_items if bf.check(item))
        assert fales_positives <= 3, f"Got {fales_positives} false positives, expected less than or equal to 3"

    