import os
import string
import pytest
import tempfile
import numpy as np
from pathlib import Path
from hypothesis import settings, given, strategies as st
from concurrent.futures import ProcessPoolExecutor

from configuration.password_screener import BloomFilter

class TestBloomFilter:
    """Tests for the BloomFilter class"""

    @pytest.fixture
    @classmethod
    def bloom_filter_factory(cls):
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
    
    @st.composite
    def password_strategy(draw, min_length=8, max_length=30):
        """Generate passwords with various characteristics."""
        complexity = draw(st.sampled_from(['simple', 'mixed', 'complex']))
        if complexity == 'simple':
            # Only letters or digits
            char_type = draw(st.sampled_from['letters', 'digits'])
            if char_type == 'letters':
                return draw(st.text(
                    alphabet=st.characters(whitelist_categories=('Lu', 'Ll')),
                    min_size=min_length, max_size=max_length
                ))
            else:
                return draw(st.text(
                    alphabet=st.characters(whitelist_categories=('Nd',)),
                    min_size=min_length, max_size=max_length
                ))
        elif complexity == 'mixed':
        # Alphanumeric
            return draw(st.text(
                alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd')),
                min_size=min_length, max_size=max_length
            ))
        else:
            # Complex - includes special characters and possible spaces
            include_spaces = draw(st.booleans())
            if include_spaces:
                return draw(st.text(
                    alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'P', 'S', 'Zs')),
                    min_size=min_length, max_size=max_length
                ))
            else:
                return draw(st.text(
                    alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd', 'P', 'S')),
                    min_size=min_length, max_size=max_length
                )) 
    
    @st.composite
    def password_lists_strategy(draw, min_items=5, max_items=100):
        """Generate lists of passwords"""
        n_items = draw(st.integers(min_value=min_items, max_value=max_items))
        return draw(st.lists(
            password_stategy(),
            min_size=n_items,
            max_size=n_items,
            unique=True
        ))
    
    @st.composite
    def password_pair_strategy(draw):
        """Generate a pair of similar but different passwords"""
        original = draw(password_strategy())
        mod_type = draw(st.sampled_from(['change_char', 'add_char', 'remove_char']))
        if len(original) < 2:
            # Create a completely new string if it's too short
            modified = draw(password_strategy().filter(lambda p: p != original))
        elif mod_type == 'change_char':
            # Change one character
            pos = draw(st.integers(min_value=0, max_value=len(original)-1))
            char = draw(st.characters(blacklist_characters=original[pos]))
            modified = original[:pos] + char + original[pos+1:]
        elif mod_type == 'add_char':
            # Adds a character
            pos = draw(st.integers(min_value=0, max_value=len(original)))
            char =draw(st.characters())
            modified = original[:pos] + char + original[pos:]
        else: 
            # Remove a character
            pos = draw(st.integers(min_value=0, max_value=len(original)-1))
            modified = original[:pos] + original[pos+1:]
        return (original, modified)
    
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

    @given(items=password_lists_strategy())
    def test_adding_items(self, items, bloom_filter_factory):
        """Test adding items to the bloom filter"""
        # Arrange
        bf = bloom_filter_factory()

        # Act
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

    @given(items=password_lists_strategy(min_items=5, max_items=50))
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
    @given(password_pairs=st.lists(
        password_pair_strategy(),
        min_size=50, max_size=60, unique_by=lambda pair: (pair[0], pair[1])
    ))
    def test_false_positive_rate(self, password_pairs, bloom_filter_factory):
        """Test that false positive rate is within expected bounds"""
        # Arrange
        originals = [pair[0] for pair in password_pairs]
        variants = [pair[1] for pair in password_pairs]
        bf = bloom_filter_factory(capacity=len(originals), error_rate=0.01)
        

        #Act
        for password in originals:
            bf.add(password)
        fales_positives = sum(1 for variant in variants if bf.check(variant))
        theoretical_error_rate = 0.01
        tolerance_factor = 3.0
        max_expected = len(variants) * theoretical_error_rate * tolerance_factor
        assert fales_positives <= max(3, max_expected), f"Got {fales_positives} false positives, expected less than or equal to {max(3, max_expected)}"
    
    def test_seralization(self, bloom_filter_factory):
        """Test saveing and loading the bloom filter"""
        # Arrange
        bf = bloom_filter_factory()

        # Act
        test_items = draw(password_lists_strategy() for _ in range(10))
        for item in test_items:
            bf.add(item)

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name

         # Assert
        try:
            success = bf.save(tmp_path)
            loaded_bf = BloomFilter.load(tmp_path)
            assert success
            assert loaded_bf is not None
            assert loaded_bf.capacity == bf.capacity
            assert loaded_bf.error_rate == bf.error_rate
            assert loaded_bf.size == bf.size
            assert loaded_bf.hash_count == bf.hash_count
            assert loaded_bf.items_added == bf.items_added

            for item in test_items:
                assert loaded_bf.check(item)
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
    
    def test_serialization_failure(self, bloom_filter_factory):
        """Test handling of serialization failures"""
        # Arrange & Act
        bf = bloom_filter_factory()
        success = bf.save("/invalid/path/somefile.pkl")
        loaded_bf = BloomFilter.load("/another/invalid/path/somefile.pkl")

        # Assert
        assert not success
        assert loaded_bf is None

    def test_get_info(self, bloom_filter_factory):
        """Test the get_info method"""
        # Arrange
        bf = bloom_filter_factory()
        for i in range(10):
            bf.add(f"item_{i}")

        # Act
        info = bf.get_info()

        #Assert
        assert info['capacity'] == 100
        assert info['items_added'] == 10
        assert info['error_rate'] == 0.01
        assert info['size_bits'] > 0
        assert info['size_bytes'] > 0
        assert info['hash_finctions'] > 0
        assert info['load_factor'] == 0.1
        assert info['estimated_prevalence'] > 0
        assert info['adaptations_made'] >= 0
    
    def test_large_capacity(self, bloom_filter_factory):
        """Test bloom filter with large capacity"""
        # Arrange & Act
        bf = bloom_filter_factory(size="large")

        # Assert
        assert bf.size > 1000000
        assert 10 <= bf.hash_count <= 20

    def test_adaptive_error_rate(self, bloom_filter_factory):
        """Test adaptive error rate adjustment"""
        # Arrange (High positive rate)
        bf = bloom_filter_factory(capacity=1000, error_rate=0.01, dynamic_sizing=True)
        bf.total_checks = 10000
        bf.positive_results = 1000
        bf._adapt_error_rate()

        # Assert
        assert bf.error_rate < 0.01
        assert bf.adaptations_made == 1

        # Arrange (Low positive rate)
        bf = bloom_filter_factory(capacity=1000, error_rate=0.01, dynamic_sizing=True)
        bf.total_checks = 10000
        bf.positive_results = 10
        bf._adapt_error_rate()

        # Assert
        assert bf.error_rate > 0.01
        assert bf.adaptations_made == 1

    @given(
        password1=password_strategy(),
        password2=password_strategy().filter(lambda p: p != password1)
    )
    def test_hash_consistency(self, password1, password2, bloom_filter_factory):
        """Test that hash functions produce consistent results"""
        # Arrange
        bf = bloom_filter_factory()
        
        # Act
        positions_1 = bf._get_hash_positions(password1)
        positions_2 = bf._get_hash_positions(password1)
        positions_3 = bf._get_hash_positions(password2)

        # Assert
        assert positions_1 == positions_2, "Same input should produce same hash positions"
        if password1 != password2:
            assert positions_1 != positions_3,  "Different inputs should produce different hash positions"
        assert len(positions_1) == bf.hash_count, "Should generate correct number of positions"



