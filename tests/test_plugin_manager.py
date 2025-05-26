from plugin.plugin_manager import AbstractPlugin, PluginManager, PluginHealthFSM, PluginLifecycleFSM, PluginStates, HealthStates
import tempfile
import json
import asyncio
import pytest
import os

class MockPlugin(AbstractPlugin):
    async def initialize(self) -> bool:
        return True

    async def start(self) -> bool:
        return True
    
    async def process_event(self, event:dict) -> bool:
        return True

    async def get_status(self) -> dict:
        return {"name": self.name, "status": "active"}
    
    async def stop(self) -> bool:
        return True

class TestPluginManager():
    
    @pytest.mark.asyncio
    async def test_plugin_manager_registers_plugin_succesfully(self):
        # Arrange
        metadata = {
            "name": "mock plugin",
            "class_path": "tests.test_plugin_manager.MockPlugin"
        }
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as file:
            json.dump(metadata, file)
            json_path = file.name
        
        p_manager = PluginManager()

        # Act
        result = await p_manager.register(json_path)
        
        # Assert
        print(f"Reigster returned: {result}, Registry: {p_manager.registry}")
        assert result is True
        assert "mock plugin" in p_manager.registry
        assert isinstance(p_manager.registry["mock plugin"], MockPlugin)
        
        # Clean Up
        os.unlink(json_path)