"""
test_podman_compose_up_down.py

Tests the podman compose up and down commands used to create and remove services.
"""
# pylint: disable=redefined-outer-name
from pathlib import Path
from typing import Iterable, List, Optional, Set

from test_podman_compose import capture
import pytest


@pytest.fixture
def profile_env_file(test_path: Path) -> Path:
    """ "Returns the path to the dotenv file used for this test module"""
    return test_path / "profile" / "profile.env"


@pytest.fixture
def profile_compose_file(test_path: Path) -> Path:
    """ "Returns the path to the `profile` compose file used for this test module"""
    return test_path / "profile" / "docker-compose.yml"


def podman_command_base(
    podman_compose_path: Path,
    env_file: Path,
    compose_file: Path,
    profiles: Optional[Iterable[str]] = None,
) -> List[str]:
    return [
        "python3",
        podman_compose_path,
        "--env-file",
        env_file,
        *(_ for profile in profiles for _ in ("--profile", profile)),
        "-f",
        compose_file,
    ]


@pytest.fixture(autouse=True)
def teardown(
    podman_compose_path: Path, profile_env_file: Path, profile_compose_file: Path
):
    """Ensures that the services within the "profile compose file" are removed between each test case.

    :param podman_compose_path: The path to the podman compose script.
    :param profile_compose_file: The path to the compose file used for this test module.
    """
    # run the test case
    yield

    down_cmd = [
        *podman_command_base(
            profiles=("profile-1", "profile-2"),
            podman_compose_path=podman_compose_path,
            env_file=profile_env_file,
            compose_file=profile_compose_file,
        ),
        "down",
    ]
    capture(down_cmd)


@pytest.mark.parametrize(
    "profiles, expected_services",
    [
        (
            set(),
            {"default-service"},
        ),
        (
            {"profile-1"},
            {"default-service", "service-1"},
        ),
        (
            {"profile-2"},
            {"default-service", "service-2"},
        ),
        (
            {"profile-1", "profile-2"},
            {"default-service", "service-1", "service-2"},
        ),
    ],
)
def test_up_down(
    podman_compose_path: Path,
    profile_compose_file: Path,
    profile_env_file: Path,
    profiles: Set[str],
    expected_services: Set[str],
):
    command_base = podman_command_base(
        profiles=profiles,
        podman_compose_path=podman_compose_path,
        env_file=profile_env_file,
        compose_file=profile_compose_file,
    )
    up_cmd = (*command_base, "up", "-d")

    out, _, return_code = capture(up_cmd)
    assert return_code == 0

    check_cmd = [
        "podman",
        "container",
        "ps",
        "--format",
        '{{index .Labels "com.docker.compose.service"}}',
    ]
    out, _, return_code = capture(check_cmd)
    assert return_code == 0
    actual_services = set(out.decode("utf-8").splitlines())

    extra_services = actual_services - expected_services
    assert not extra_services, f"Extra services were started: {extra_services}"
    missing_services = expected_services - actual_services
    assert (
        not missing_services
    ), f"Expected services were not started: {missing_services}"

    down_cmd = (*command_base, "down")
    _, _, return_code = capture(down_cmd)
    assert return_code == 0

    out, _, return_code = capture(check_cmd)
    assert return_code == 0
    leftover_services = set(out.decode("utf-8").splitlines())
    assert not leftover_services, f"Failed to stop services: {leftover_services}"
