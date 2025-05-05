import pytest
from hypothesis import given, strategies as st
import responses
import json
import requests
from emercoin.rpc_client import EmercoinRpcClient

class TestEmercoinClient:

    def test_successful_connection_to_node():

        # Arrange
        username = ""
        password = ""
        location = ""
        client = EmercoinRpcClient()

        # Act
        result = client.get_info()

        assert result is not None
        assert "version" in result 
