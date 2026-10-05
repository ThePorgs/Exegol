import asyncio
import importlib
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from docker.errors import NotFound

from exegol.config.EnvInfo import EnvInfo
from exegol.model.ContainerConfig import ContainerConfig
from exegol.model.ExegolNetwork import ExegolNetwork, ExegolNetworkMode
from exegol.model.ExegolContainer import ExegolContainer


@pytest.fixture
def tor_config(monkeypatch):
    monkeypatch.setattr(EnvInfo, "getHostOs", lambda: EnvInfo.HostOs.LINUX)
    config = ContainerConfig()
    config.addLabel(config.ExegolFeatures.tor.value, "Enabled")
    config.getNetworks().append(ExegolNetwork(ExegolNetworkMode.docker))
    config.addCapability("NET_ADMIN")
    return config


@pytest.mark.parametrize("capability", ["NET_RAW", "cap_net_raw", "all", "CAP_ALL"])
def test_tor_rejects_firewall_bypass_capabilities(tor_config, capability):
    tor_config.addCapability(capability)
    with pytest.raises(SystemExit):
        tor_config.validateTor()


def test_tor_rejects_host_network_after_configuration_change(tor_config):
    tor_config.getNetworks()[:] = [ExegolNetwork(ExegolNetworkMode.host)]
    with pytest.raises(SystemExit):
        tor_config.validateTor()


@pytest.mark.parametrize("failure", ["removed", "missing_script"])
def test_tor_readiness_failure_aborts_command_without_retry(monkeypatch, tor_config, failure):
    module = importlib.import_module("exegol.model.ExegolContainer")
    monkeypatch.setattr(module, "ParametersManager", lambda: SimpleNamespace(tor=False, capabilities=[]))
    monkeypatch.setattr(module.OptionResolver, "cliValue", lambda self, name: [])

    async def unexpected_retry(_):
        pytest.fail("A terminal readiness failure must not wait for bootstrap timeout")

    monkeypatch.setattr(module.asyncio, "sleep", unexpected_retry)
    docker_container = Mock(status="running", attrs={"State": {"Status": "running"}})
    docker_container.reload.side_effect = [None, NotFound("removed")] if failure == "removed" else None
    docker_container.exec_run.return_value = SimpleNamespace(exit_code=127)
    container = ExegolContainer.__new__(ExegolContainer)
    container.config = tor_config
    container._ExegolContainer__container = docker_container
    with pytest.raises(SystemExit):
        asyncio.run(container.exec_raw("touch /tmp/must-not-run"))
