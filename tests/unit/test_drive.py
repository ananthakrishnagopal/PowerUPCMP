import pytest

from semifab_poc.simulation.drive import DriveSubsystem


def test_vfd_command_and_motor_speed_are_bounded() -> None:
    drive = DriveSubsystem()
    state = drive.reset()
    # Fourteen 0.01 s steps per 0.1 s gives 1.4 s = seven motor time constants,
    # enough to assert the stated ±1 rad/s steady-state bound without changing
    # the documented transient model.
    for _ in range(140):
        state = drive.step(state, {"vfd_command_pu": 1.0}, {"ups_output_voltage_pu": 1.0}, 0.01)
    assert state.vfd_available_output_pu == pytest.approx(1.0)
    assert state.motor_speed_rad_s == pytest.approx(drive.config.nominal_motor_speed_rad_s, abs=1.0)


def test_undervoltage_derates_and_trips() -> None:
    drive = DriveSubsystem()
    state = drive.reset()
    state = drive.step(state, {"vfd_command_pu": 1.0}, {"ups_output_voltage_pu": 0.70}, 0.01)
    assert 0.0 < state.vfd_available_output_pu < 1.0
    state = drive.step(state, {"vfd_command_pu": 1.0}, {"ups_output_voltage_pu": 0.40}, 0.01)
    assert state.tripped is True
    assert state.vfd_available_output_pu == 0.0


def test_trip_requires_restart_dwell() -> None:
    drive = DriveSubsystem()
    state = drive.reset()
    state = drive.step(state, {"vfd_command_pu": 1.0}, {"force_trip": True, "ups_output_voltage_pu": 1.0}, 0.01)
    assert state.tripped
    for _ in range(10):
        state = drive.step(state, {"vfd_command_pu": 1.0, "restart_request": True}, {"ups_output_voltage_pu": 1.0}, 0.01)
    assert state.tripped
    for _ in range(20):
        state = drive.step(state, {"vfd_command_pu": 1.0, "restart_request": True}, {"ups_output_voltage_pu": 1.0}, 0.01)
    assert state.tripped is False
    assert state.motor_speed_rad_s > 0.0


def test_invalid_timestep_is_rejected() -> None:
    drive = DriveSubsystem()
    with pytest.raises(Exception, match="positive"):
        drive.step(drive.reset(), None, None, 0.0)
