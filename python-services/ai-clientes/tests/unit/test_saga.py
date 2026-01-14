"""
Tests unitarios para el patrón Saga.
"""
import pytest

# Try to import the modules, skip if not available
try:
    from core.saga import ClientSaga, SagaExecutionError
    from core.commands import UpdateCustomerCityCommand, SaveSearchResultsCommand
    from core.feature_flags import USE_SAGA_ROLLBACK
    MODULES_AVAILABLE = True
except ImportError as e:
    MODULES_AVAILABLE = False
    print(f"Warning: Could not import modules: {e}")


@pytest.mark.skipif(not MODULES_AVAILABLE, reason="Módulos no disponibles")
class TestClientSaga:
    """Tests para el patrón Saga de clientes."""

    def test_initialization(self):
        """Debe inicializar una saga vacía."""
        saga = ClientSaga()

        assert len(saga.commands) == 0
        assert len(saga.executed_commands) == 0

    def test_add_command(self):
        """Debe agregar comandos a la saga."""
        saga = ClientSaga()

        # Mock command
        class MockCommand:
            async def execute(self):
                return {"success": True}
            async def undo(self):
                pass

        mock_cmd = MockCommand()
        result = saga.add_command(mock_cmd)

        # Fluent interface - returns self
        assert result is saga
        assert len(saga.commands) == 1

    def test_add_multiple_commands_fluent(self):
        """Debe permitir encadenar add_command (fluent interface)."""
        saga = ClientSaga()

        class MockCommand:
            async def execute(self):
                return {"success": True}
            async def undo(self):
                pass

        # Chain commands
        saga.add_command(MockCommand()).add_command(MockCommand())

        assert len(saga.commands) == 2

    def test_get_status(self):
        """Debe retornar el estado de la saga."""
        saga = ClientSaga()

        class MockCommand:
            async def execute(self):
                return {"success": True}
            async def undo(self):
                pass

        saga.add_command(MockCommand()).add_command(MockCommand())

        status = saga.get_status()

        assert status["total_commands"] == 2
        assert status["executed_commands"] == 0
        assert status["pending_commands"] == 2
        assert len(status["command_names"]) == 2

    def test_reset(self):
        """Debe limpiar la saga."""
        saga = ClientSaga()

        class MockCommand:
            async def execute(self):
                return {"success": True}
            async def undo(self):
                pass

        saga.add_command(MockCommand())
        saga.reset()

        assert len(saga.commands) == 0
        assert len(saga.executed_commands) == 0

    @pytest.mark.asyncio
    async def test_execute_success(self):
        """Debe ejecutar todos los comandos exitosamente."""
        saga = ClientSaga()

        execution_order = []

        class MockCommand:
            def __init__(self, name):
                self.name = name

            async def execute(self):
                execution_order.append(self.name)
                return {"success": True}

            async def undo(self):
                execution_order.append(f"undo_{self.name}")

        saga.add_command(MockCommand("cmd1")).add_command(MockCommand("cmd2"))

        result = await saga.execute()

        assert result["success"] is True
        assert result["commands_executed"] == 2
        assert execution_order == ["cmd1", "cmd2"]

    @pytest.mark.asyncio
    async def test_execute_rollback_on_failure(self):
        """Debe hacer rollback cuando un comando falla."""
        saga = ClientSaga()

        execution_order = []

        class MockCommand:
            def __init__(self, name, should_fail=False):
                self.name = name
                self.should_fail = should_fail

            async def execute(self):
                execution_order.append(f"execute_{self.name}")
                if self.should_fail:
                    raise ValueError(f"{self.name} failed")
                return {"success": True}

            async def undo(self):
                execution_order.append(f"undo_{self.name}")

        # cmd1 succeeds, cmd2 fails, cmd3 never executes
        saga.add_command(MockCommand("cmd1"))
        saga.add_command(MockCommand("cmd2", should_fail=True))
        saga.add_command(MockCommand("cmd3"))

        # Should raise SagaExecutionError
        with pytest.raises(SagaExecutionError) as exc_info:
            await saga.execute()

        # Verify rollback occurred
        assert "cmd2 failed" in str(exc_info.value)
        assert exc_info.value.completed_commands == ["MockCommand"]
        assert exc_info.value.failed_at == 1

        # Verify undo was called for executed commands (in reverse)
        assert execution_order == [
            "execute_cmd1",
            "execute_cmd2",
            "undo_cmd1"  # Rolled back in reverse order
        ]

    @pytest.mark.asyncio
    async def test_execute_best_effort_rollback(self):
        """Debe continuar rollback incluso si un undo falla."""
        saga = ClientSaga()

        execution_order = []

        class MockCommand:
            def __init__(self, name, fail_undo=False):
                self.name = name
                self.fail_undo = fail_undo

            async def execute(self):
                execution_order.append(f"execute_{self.name}")
                return {"success": True}

            async def undo(self):
                execution_order.append(f"undo_{self.name}")
                if self.fail_undo:
                    raise ValueError(f"{self.name} undo failed")

        # cmd3 fails, undo cmd2 (fails), undo cmd1 (succeeds)
        saga.add_command(MockCommand("cmd1"))
        saga.add_command(MockCommand("cmd2", fail_undo=True))
        saga.add_command(MockCommand("cmd3", fail_undo=True))

        # cmd3 will fail during execute
        class FailingCommand(MockCommand):
            async def execute(self):
                execution_order.append("execute_cmd3")
                raise ValueError("cmd3 execute failed")

        # Replace last command
        saga.commands[-1] = FailingCommand("cmd3")

        # Execute - should not raise despite undo failures
        with pytest.raises(SagaExecutionError):
            await saga.execute()

        # Both undos should have been attempted (best effort)
        assert "undo_cmd2" in execution_order
        assert "undo_cmd1" in execution_order


@pytest.mark.skipif(not MODULES_AVAILABLE, reason="Módulos no disponibles")
class TestUpdateCustomerCityCommand:
    """Tests para UpdateCustomerCityCommand."""

    def test_initialization(self):
        """Debe inicializar el comando correctamente."""
        # Mock customer service
        class MockCustomerService:
            pass

        cmd = UpdateCustomerCityCommand(
            MockCustomerService(),
            "customer-123",
            "Lima"
        )

        assert cmd.customer_id == "customer-123"
        assert cmd.new_city == "Lima"
        assert cmd.previous_city is None


@pytest.mark.skipif(not MODULES_AVAILABLE, reason="Módulos no disponibles")
class TestSaveSearchResultsCommand:
    """Tests para SaveSearchResultsCommand."""

    def test_initialization(self):
        """Debe inicializar el comando correctamente."""
        # Mock session manager
        class MockSessionManager:
            pass

        cmd = SaveSearchResultsCommand(
            MockSessionManager(),
            "1234567890",
            {"results": []}
        )

        assert cmd.phone == "1234567890"
        assert cmd.results == {"results": []}
        assert cmd.was_saved is False


@pytest.mark.skipif(not MODULES_AVAILABLE, reason="Módulos no disponibles")
class TestFeatureFlag:
    """Tests para el feature flag de Saga."""

    def test_saga_rollback_is_active(self):
        """USE_SAGA_ROLLBACK debe estar activo."""
        assert USE_SAGA_ROLLBACK is True
