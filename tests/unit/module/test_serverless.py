"""Test runway.module.serverless."""
# pylint: disable=no-self-use,unused-argument
# pyright: basic, reportFunctionMemberAccess=none
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Union, cast

import pytest
import yaml
from mock import ANY, MagicMock
from pydantic import ValidationError

from runway.config.models.runway.options.serverless import (
    RunwayServerlessModuleOptionsDataModel,
)
from runway.module.serverless import Serverless, ServerlessOptions, gen_sls_config_files

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import LogCaptureFixture
    from pytest_mock import MockerFixture
    from pytest_subprocess.core import FakeProcess

    from ..factories import MockRunwayContext

MODULE = "runway.module.serverless"


@pytest.mark.usefixtures("patch_module_npm")
class TestServerless:
    """Test runway.module.serverless.Serverless."""

    def test___init__(self, runway_context: MockRunwayContext, tmp_path: Path) -> None:
        """Test __init__ and the attributes set in __init__."""
        obj = Serverless(
            runway_context, module_root=tmp_path, options={"skip_npm_ci": True}
        )
        assert isinstance(obj.options, ServerlessOptions)
        assert obj.region == runway_context.env.aws_region
        assert obj.stage == runway_context.env.name

        with pytest.raises(ValidationError):
            assert not Serverless(
                runway_context,
                module_root=tmp_path,
                options={"promotezip": {"invalid": "value"}},
            )

    def test_cli_args(self, runway_context: MockRunwayContext, tmp_path: Path) -> None:
        """Test cli_args."""
        obj = Serverless(runway_context, module_root=tmp_path)

        assert obj.cli_args == [
            "--region",
            runway_context.env.aws_region,
            "--stage",
            runway_context.env.name,
        ]

        runway_context.env.vars["DEBUG"] = "1"
        assert obj.cli_args == [
            "--region",
            runway_context.env.aws_region,
            "--stage",
            runway_context.env.name,
            "--verbose",
        ]

    def test_deploy(
        self, mocker: MockerFixture, runway_context: MockRunwayContext, tmp_path: Path
    ) -> None:
        """Test deploy."""
        mock_extend_serverless_yml = mocker.patch.object(
            Serverless, "extend_serverless_yml"
        )
        mock_sls_deploy = mocker.patch.object(Serverless, "sls_deploy")
        obj = Serverless(runway_context, module_root=tmp_path)

        mocker.patch.object(Serverless, "skip", True)
        assert not obj.deploy()
        mock_extend_serverless_yml.assert_not_called()
        mock_sls_deploy.assert_not_called()

        mocker.patch.object(Serverless, "skip", False)
        mocker.patch.object(obj.options, "extend_serverless_yml", True)
        assert not obj.deploy()
        mock_extend_serverless_yml.assert_called_once_with(mock_sls_deploy)
        mock_sls_deploy.assert_not_called()

        mocker.patch.object(obj.options, "extend_serverless_yml", False)
        assert not obj.deploy()
        mock_extend_serverless_yml.assert_called_once()
        mock_sls_deploy.assert_called_once_with()

    def test_destroy(
        self, mocker: MockerFixture, runway_context: MockRunwayContext, tmp_path: Path
    ) -> None:
        """Test destroy."""
        # pylint: disable=no-member
        mocker.patch.object(Serverless, "extend_serverless_yml")
        mocker.patch.object(Serverless, "sls_remove", MagicMock())
        obj = Serverless(runway_context, module_root=tmp_path)

        mocker.patch.object(Serverless, "skip", True)
        assert not obj.destroy()
        obj.extend_serverless_yml.assert_not_called()  # type: ignore
        obj.sls_remove.assert_not_called()

        mocker.patch.object(Serverless, "skip", False)
        mocker.patch.object(obj.options, "extend_serverless_yml", True)
        assert not obj.destroy()
        obj.extend_serverless_yml.assert_called_once_with(obj.sls_remove)
        obj.sls_remove.assert_not_called()

        mocker.patch.object(obj.options, "extend_serverless_yml", False)
        assert not obj.destroy()
        obj.extend_serverless_yml.assert_called_once()
        obj.sls_remove.assert_called_once_with()

    def test_env_file(self, runway_context: MockRunwayContext, tmp_path: Path) -> None:
        """Test env_file.

        Testing the precedence of each path, create the files in order from
        lowerst to highest. After creating the file, the property's value
        is checked then cleared since the value is cached after the first
        time it is resolved.

        """
        env_dir = tmp_path / "env"
        env_dir.mkdir()
        obj = Serverless(runway_context, module_root=tmp_path)
        assert not obj.env_file
        del obj.env_file

        config_test_json = tmp_path / "config-test.json"
        config_test_json.touch()
        assert obj.env_file == config_test_json
        del obj.env_file

        env_test_json = env_dir / "test.json"
        env_test_json.touch()
        assert obj.env_file == env_test_json
        del obj.env_file

        config_test_us_east_1_json = tmp_path / "config-test-us-east-1.json"
        config_test_us_east_1_json.touch()
        assert obj.env_file == config_test_us_east_1_json
        del obj.env_file

        env_test_us_east_1_json = env_dir / "test-us-east-1.json"
        env_test_us_east_1_json.touch()
        assert obj.env_file == env_test_us_east_1_json
        del obj.env_file

        config_test_yml = tmp_path / "config-test.yml"
        config_test_yml.touch()
        assert obj.env_file == config_test_yml
        del obj.env_file

        env_test_yml = env_dir / "test.yml"
        env_test_yml.touch()
        assert obj.env_file == env_test_yml
        del obj.env_file

        config_test_us_east_1_yml = tmp_path / "config-test-us-east-1.yml"
        config_test_us_east_1_yml.touch()
        assert obj.env_file == config_test_us_east_1_yml
        del obj.env_file

        env_test_us_east_1_yml = env_dir / "test-us-east-1.yml"
        env_test_us_east_1_yml.touch()
        assert obj.env_file == env_test_us_east_1_yml
        del obj.env_file

    def test_extend_serverless_yml(
        self,
        caplog: LogCaptureFixture,
        mocker: MockerFixture,
        runway_context: MockRunwayContext,
        tmp_path: Path,
    ) -> None:
        """Test extend_serverless_yml."""
        # pylint: disable=no-member
        mock_merge = mocker.patch("runway.module.serverless.merge_dicts")
        caplog.set_level(logging.DEBUG, logger="runway")
        mock_func = MagicMock()
        mock_merge.return_value = {"key": "val"}
        mocker.patch.object(Serverless, "npm_install", MagicMock())
        mocker.patch.object(Serverless, "sls_print", MagicMock(return_value="original"))
        mocker.patch.object(ServerlessOptions, "update_args", MagicMock())

        options = {"extend_serverless_yml": {"new-key": "val"}}
        obj = Serverless(runway_context, module_root=tmp_path, options=options)

        assert not obj.extend_serverless_yml(mock_func)
        obj.npm_install.assert_called_once()
        obj.sls_print.assert_called_once()
        mock_merge.assert_called_once_with("original", options["extend_serverless_yml"])
        mock_func.assert_called_once_with(skip_install=True)
        obj.options.update_args.assert_called_once_with("config", ANY)

        tmp_file = obj.options.update_args.call_args[0][1]
        # 'no way to check the prefix since it will be a uuid'
        assert tmp_file.endswith(".tmp.serverless.yml")
        assert not (
            tmp_path / tmp_file
        ).exists(), 'should always be deleted after calling "func"'

        caplog.clear()
        mocker.patch(
            "pathlib.Path.unlink", MagicMock(side_effect=OSError("test OSError"))
        )
        assert not obj.extend_serverless_yml(mock_func)
        assert (
            "{}:encountered an error when trying to delete the "
            "temporary Serverless config".format(tmp_path.name) in caplog.messages
        )

    @pytest.mark.parametrize("command", [("deploy"), ("remove"), ("print")])
    def test_gen_cmd(
        self,
        command: str,
        mocker: MockerFixture,
        runway_context: MockRunwayContext,
        tmp_path: Path,
    ) -> None:
        """Test gen_cmd."""
        # pylint: disable=no-member
        mock_cmd = mocker.patch(
            "runway.module.serverless.generate_node_command", return_value=["success"]
        )
        mocker.patch.object(runway_context, "no_color", False)
        obj = Serverless(
            runway_context, module_root=tmp_path, options={"args": ["--config", "test"]}
        )
        expected_opts = [
            command,
            "--region",
            runway_context.env.aws_region,
            "--stage",
            runway_context.env.name,
            "--config",
            "test",
            "--extra-arg",
        ]

        assert obj.gen_cmd(command, args_list=["--extra-arg"]) == ["success"]
        mock_cmd.assert_called_once_with(
            command="sls", command_opts=expected_opts, logger=obj.logger, path=tmp_path
        )
        mock_cmd.reset_mock()

        obj.ctx.env.vars["CI"] = "1"
        mocker.patch.object(runway_context, "no_color", True)
        expected_opts.append("--no-color")
        if command not in ["remove", "print"]:
            expected_opts.append("--conceal")
        assert obj.gen_cmd(command, args_list=["--extra-arg"]) == ["success"]
        mock_cmd.assert_called_once_with(
            command="sls", command_opts=expected_opts, logger=obj.logger, path=tmp_path
        )

    def test_init(
        self,
        caplog: LogCaptureFixture,
        runway_context: MockRunwayContext,
        tmp_path: Path,
    ) -> None:
        """Test init."""
        caplog.set_level(logging.WARNING, logger=MODULE)
        obj = Serverless(runway_context, module_root=tmp_path)
        assert not obj.init()
        assert (
            f"init not currently supported for {Serverless.__name__}" in caplog.messages
        )

    def test_plan(
        self,
        caplog: LogCaptureFixture,
        runway_context: MockRunwayContext,
        tmp_path: Path,
    ) -> None:
        """Test plan."""
        caplog.set_level(logging.INFO, logger="runway")
        obj = Serverless(runway_context, module_root=tmp_path)

        assert not obj.plan()
        assert [
            f"{tmp_path.name}:plan not currently supported for Serverless"
        ] == caplog.messages

    def test_skip(
        self,
        caplog: LogCaptureFixture,
        mocker: MockerFixture,
        runway_context: MockRunwayContext,
        tmp_path: Path,
    ) -> None:
        """Test skip."""
        caplog.set_level(logging.INFO, logger="runway")
        obj = Serverless(runway_context, module_root=tmp_path)
        mocker.patch.object(obj, "package_json_missing", lambda: True)
        mocker.patch.object(obj, "env_file", False)

        assert obj.skip
        assert [
            '{}:skipped; package.json with "serverless" in devDependencies'
            " is required for this module type".format(tmp_path.name)
        ] == caplog.messages
        caplog.clear()

        mocker.patch.object(obj, "package_json_missing", lambda: False)
        assert obj.skip
        assert [
            "{}:skipped; config file for this stage/region not found"
            " -- looking for one of: {}".format(
                tmp_path.name, ", ".join(gen_sls_config_files(obj.stage, obj.region))
            )
        ] == caplog.messages
        caplog.clear()

        obj.explicitly_enabled = True
        assert not obj.skip
        obj.explicitly_enabled = False

        obj.parameters = True  # type: ignore
        assert not obj.skip
        obj.parameters = False  # type: ignore

        obj.env_file = True  # type: ignore
        assert not obj.skip

    def test_sls_deploy(
        self, mocker: MockerFixture, runway_context: MockRunwayContext, tmp_path: Path
    ) -> None:
        """Test sls_deploy."""
        # pylint: disable=no-member
        mock_deploy = mocker.patch("runway.module.serverless.deploy_package")
        mock_run = mocker.patch("runway.module.serverless.run_module_command")
        mocker.patch.object(runway_context, "no_color", False)
        mocker.patch.object(Serverless, "gen_cmd", MagicMock(return_value=["deploy"]))
        mocker.patch.object(Serverless, "npm_install", MagicMock())
        obj = Serverless(
            runway_context,
            module_root=tmp_path,
            options={"args": ["--config", "test.yml"]},
        )

        assert not obj.sls_deploy()
        obj.npm_install.assert_called_once()
        obj.gen_cmd.assert_called_once_with("deploy")
        mock_run.assert_called_once_with(
            cmd_list=["deploy"], env_vars=runway_context.env.vars, logger=obj.logger
        )

        obj.options.promotezip["bucketname"] = "test-bucket"
        assert not obj.sls_deploy(skip_install=True)
        obj.npm_install.assert_called_once()
        mock_deploy.assert_called_once_with(
            [
                "deploy",
                "--region",
                runway_context.env.aws_region,
                "--stage",
                runway_context.env.name,
                "--config",
                "test.yml",
            ],
            "test-bucket",
            runway_context,
            tmp_path,
            obj.logger,
        )
        mock_run.assert_called_once()

        mocker.patch.object(runway_context, "no_color", True)
        assert not obj.sls_deploy(skip_install=True)
        mock_deploy.assert_called_with(
            [
                "deploy",
                "--region",
                runway_context.env.aws_region,
                "--stage",
                runway_context.env.name,
                "--config",
                "test.yml",
                "--no-color",
            ],
            "test-bucket",
            runway_context,
            tmp_path,
            obj.logger,
        )

    def test_sls_print(
        self, mocker: MockerFixture, runway_context: MockRunwayContext, tmp_path: Path
    ) -> None:
        """Test sls_print."""
        # pylint: disable=no-member
        expected_dict = {"status": "success"}
        mock_check_output = MagicMock(return_value=yaml.safe_dump(expected_dict))
        mocker.patch.object(Serverless, "gen_cmd", MagicMock(return_value=["print"]))
        mocker.patch.object(Serverless, "npm_install", MagicMock())
        mocker.patch("subprocess.check_output", mock_check_output)
        obj = Serverless(runway_context, module_root=tmp_path)

        assert obj.sls_print() == expected_dict
        obj.npm_install.assert_called_once()
        mock_check_output.assert_called_once_with(
            ["print"], env={"SLS_DEPRECATION_DISABLE": "*", **runway_context.env.vars}
        )
        obj.gen_cmd.assert_called_once_with("print", args_list=["--format", "yaml"])
        obj.gen_cmd.reset_mock()

        assert (
            obj.sls_print(item_path="something.status", skip_install=True)
            == expected_dict
        )
        obj.npm_install.assert_called_once()
        obj.gen_cmd.assert_called_once_with(
            "print", args_list=["--format", "yaml", "--path", "something.status"]
        )

    def test_sls_remove(
        self,
        fake_process: FakeProcess,
        mocker: MockerFixture,
        runway_context: MockRunwayContext,
        tmp_path: Path,
    ) -> None:
        """Test sls_remove."""
        # pylint: disable=no-member
        sls_error_01: List[Union[bytes, str]] = [
            "  Serverless Error ---------------------------------------",
            "",
            "  Stack 'test-stack' does not exist",
            "",
            "  Get Support --------------------------------------------",
            "     Docs:          docs.serverless.com",
            "     Bugs:          github.com/serverless/serverless/issues",
            "     Issues:        forum.serverless.com",
        ]
        sls_error_02 = sls_error_01.copy()
        sls_error_02[2] = "  Some other error"
        fake_process.register_subprocess("remove", stdout="success")
        fake_process.register_subprocess("remove", stdout=sls_error_01, returncode=1)
        fake_process.register_subprocess("remove", stdout=sls_error_02, returncode=1)
        mocker.patch.object(Serverless, "gen_cmd", MagicMock(return_value=["remove"]))
        mocker.patch.object(Serverless, "npm_install", MagicMock())

        obj = Serverless(runway_context, module_root=tmp_path)
        assert not obj.sls_remove()
        obj.npm_install.assert_called_once()
        obj.gen_cmd.assert_called_once_with("remove")

        assert not obj.sls_remove(skip_install=True)
        obj.npm_install.assert_called_once()

        with pytest.raises(SystemExit):
            assert not obj.sls_remove()


class TestServerlessOptions:
    """Test runway.module.serverless.ServerlessOptions."""

    @pytest.mark.parametrize(
        "args, expected",
        [
            (["--config", "something"], ["--config", "something"]),
            (
                ["--config", "something", "--unknown-arg", "value"],
                ["--config", "something", "--unknown-arg", "value"],
            ),
            (["-c", "something"], ["--config", "something"]),
            (["-u"], ["-u"]),
        ],
    )
    def test_args(self, args: List[str], expected: List[str]) -> None:
        """Test args."""
        obj = ServerlessOptions.parse_obj({"args": args})
        assert obj.args == expected

    @pytest.mark.parametrize(
        "config",
        [
            ({"args": ["--config", "something"]}),
            ({"extend_serverless_yml": {"new_key": "test_value"}}),
            ({"promotezip": {"bucketname": "test-bucket"}}),
            ({"skip_npm_ci": True}),
            (
                {
                    "args": ["--config", "something"],
                    "extend_serverless_yml": {"new_key": "test_value"},
                }
            ),
            (
                {
                    "args": ["--config", "something"],
                    "extend_serverless_yml": {"new_key": "test_value"},
                    "promotezip": {"bucketname": "test-bucket"},
                }
            ),
            (
                {
                    "args": ["--config", "something"],
                    "extend_serverless_yml": {"new_key": "test_value"},
                    "promotezip": {"bucketname": "test-bucket"},
                    "skip_npm_ci": True,
                }
            ),
            (
                {
                    "args": ["--config", "something"],
                    "extend_serverless_yml": {"new_key": "test_value"},
                    "promotezip": {"bucketname": "test-bucket"},
                    "skip_npm_ci": False,
                }
            ),
        ],
    )
    def test_parse(self, config: Dict[str, Any]) -> None:
        """Test parse."""
        obj = ServerlessOptions.parse_obj(config)

        assert obj.args == config.get("args", [])
        assert obj.extend_serverless_yml == config.get(
            "extend_serverless_yml", cast(Dict[str, Any], {})
        )
        if config.get("promotezip"):
            assert obj.promotezip
        else:
            assert not obj.promotezip
        assert obj.promotezip.bucketname == config.get(
            "promotezip", cast(Dict[str, Any], {})
        ).get("bucketname")
        assert obj.skip_npm_ci == config.get("skip_npm_ci", False)

    def test_parse_invalid_promotezip(self) -> None:
        """Test parse with invalid promotezip value."""
        with pytest.raises(ValidationError):
            assert not ServerlessOptions.parse_obj({"promotezip": {"key": "value"}})

    def test_update_args(self) -> None:
        """Test update_args."""
        obj = ServerlessOptions(
            RunwayServerlessModuleOptionsDataModel(
                args=["--config", "something", "--unknown-arg", "value"],
                extend_serverless_yml={},
                promotezip={},
            )
        )
        assert obj.args == ["--config", "something", "--unknown-arg", "value"]

        obj.update_args("config", "something-else")
        assert obj.args == ["--config", "something-else", "--unknown-arg", "value"]

        with pytest.raises(KeyError):
            obj.update_args("invalid-key", "anything")
