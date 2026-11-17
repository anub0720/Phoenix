
from phoenix.domain.restoration import RestoreResult


def test_successful_restore_result():
    result = RestoreResult(
        success=True,
        backup_name="ecommerce-real",
        container_id="container-123",
        duration_seconds=12.5,
    )

    assert result.success is True
    assert result.backup_name == "ecommerce-real"
    assert result.container_id == "container-123"
    assert result.duration_seconds == 12.5
    assert result.error_message is None
    assert result.retained is False


def test_failed_restore_result():
    result = RestoreResult(
        success=False,
        backup_name="ecommerce-real",
        container_id=None,
        duration_seconds=3.2,
        error_message="Docker container failed to start.",
    )

    assert result.success is False
    assert result.container_id is None
    assert result.error_message == "Docker container failed to start."


def test_diagnostic_restore_result():
    result = RestoreResult(
        success=True,
        backup_name="ecommerce-real",
        container_id="container-456",
        duration_seconds=15.0,
        retained=True,
    )

    assert result.retained is True


def test_restore_result_is_immutable():
    result = RestoreResult(
        success=True,
        backup_name="ecommerce-real",
        container_id="container-123",
        duration_seconds=12.5,
    )

    try:
        result.success = False
        assert False, "RestoreResult should be immutable"
    except AttributeError:
        pass
