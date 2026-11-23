"""system.yaml must describe this service as the code really is.

The course's schema says system.yaml has to match the code at the graded
commit, so a change to a setting, a default or a path that forgets
system.yaml makes these tests fail. The first part of this file is the
same in both services; the ladder adds a test for its call to bookings.
"""
import os
import re

import yaml

SERVICE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_ROOT = os.path.dirname(os.path.dirname(SERVICE_DIR))
SERVICE = os.path.basename(SERVICE_DIR)  # "bookings" or "ladder"

# os.environ.get("NAME") or os.environ.get("NAME", "default")
ENV_READ = re.compile(r'os\.environ\.get\(\s*"([A-Z][A-Z0-9_]*)"\s*(?:,\s*"([^"]*)"\s*)?\)')


def load_system():
    with open(os.path.join(REPO_ROOT, "system.yaml"), encoding="utf-8") as file:
        return yaml.safe_load(file)


def this_service():
    return load_system()["services"][SERVICE]


def env_vars_in_code():
    """{name: default or None} for every environment variable the service reads."""
    found = {}
    files = [os.path.join(SERVICE_DIR, "app.py")]
    for folder, _, names in os.walk(os.path.join(SERVICE_DIR, "padel")):
        files += [os.path.join(folder, name) for name in names if name.endswith(".py")]
    for path in files:
        with open(path, encoding="utf-8") as file:
            for name, default in ENV_READ.findall(file.read()):
                found[name] = default or None
    return found


def test_system_yaml_lists_exactly_the_environment_variables_the_code_reads():
    assert set(this_service()["env"]) == set(env_vars_in_code())


def test_defaults_in_system_yaml_are_the_defaults_in_the_code():
    in_code = env_vars_in_code()
    for name, variable in this_service()["env"].items():
        if variable.get("secret"):
            assert in_code[name] is None, f"{name} is a secret, so the code must not have a default"
        else:
            assert str(variable["default"]) == in_code[name], name


def test_port_default_is_the_port_the_code_uses():
    service = this_service()
    assert str(service["port_default"]) == env_vars_in_code()["PORT"]
    assert service["env"]["PORT"]["default"] == service["port_default"]


def test_paths_in_system_yaml_exist():
    service = this_service()
    assert os.path.samefile(os.path.join(REPO_ROOT, service["path"]), SERVICE_DIR)
    assert os.path.isfile(os.path.join(REPO_ROOT, service["openapi"]))
    assert os.path.isdir(os.path.join(REPO_ROOT, service["migrations"]))
