# ---------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# ---------------------------------------------------------
import os.path

from dotenv import dotenv_values
from marshmallow import fields, post_load, pre_load

from promptflow._sdk._utils import is_remote_uri
from promptflow._sdk.schemas._base import PatchedSchemaMeta, YamlFileSchema
from promptflow._sdk.schemas._fields import LocalPathField, NestedField, UnionField
from promptflow._utils.logger_utils import get_cli_sdk_logger

logger = get_cli_sdk_logger()


def _resolve_dot_env_file(data, **kwargs):
    """Resolve .env file to environment variables."""
    env_var = data.get("environment_variables", None)
    try:
        if env_var and os.path.exists(env_var):
            env_dict = dotenv_values(env_var)
            data["environment_variables"] = env_dict
    except TypeError:
        pass
    return data


class ResourcesSchema(metaclass=PatchedSchemaMeta):
    """Schema for resources."""

    instance_type = fields.Str()
    idle_time_before_shutdown_minutes = fields.Int()


class RemotePathStr(fields.Str):
    default_error_messages = {
        "invalid_path": "Invalid remote path. "
        "Currently only azureml://xxx or public URL(e.g. https://xxx) are supported.",
    }

    def _validate(self, value):
        # inherited validations like required, allow_none, etc.
        super(RemotePathStr, self)._validate(value)

        if value is None:
            return
        if not is_remote_uri(value):
            raise self.make_error(
                "invalid_path",
            )


class RemoteFlowStr(fields.Str):
    default_error_messages = {
        "invalid_path": "Invalid remote flow path. Currently only azureml:<flow-name> is supported",
    }

    def _validate(self, value):
        # inherited validations like required, allow_none, etc.
        super(RemoteFlowStr, self)._validate(value)

        if value is None:
            return
        if not isinstance(value, str) or not value.startswith("azureml:"):
            raise self.make_error(
                "invalid_path",
            )


class RunSchema(YamlFileSchema):
    """Base schema for all run schemas."""

    # TODO(2898455): support directly write path/flow + entry in run.yaml
    # region: common fields
    name = fields.Str()
    display_name = fields.Str(required=False)
    tags = fields.Dict(keys=fields.Str(), values=fields.Str(allow_none=True))
    status = fields.Str(dump_only=True)
    description = fields.Str(attribute="description")
    properties = fields.Dict(keys=fields.Str(), values=fields.Str(allow_none=True))
    # endregion: common fields

    flow = UnionField([LocalPathField(required=True), RemoteFlowStr(required=True)])
    # inputs field
    data = UnionField([LocalPathField(), RemotePathStr()])
    column_mapping = fields.Dict(keys=fields.Str)
    # runtime field, only available for cloud run
    runtime = fields.Str()
    resources = NestedField(ResourcesSchema)
    run = fields.Str()

    # region: context
    variant = fields.Str()
    environment_variables = UnionField(
        [
            fields.Dict(keys=fields.Str(), values=fields.Str()),
            # support load environment variables from .env file
            LocalPathField(),
        ]
    )
    connections = fields.Dict(keys=fields.Str(), values=fields.Dict(keys=fields.Str()))
    # endregion: context

    # region: command node
    command = fields.Str(dump_only=True)
    outputs = fields.Dict(key=fields.Str(), dump_only=True)
    # endregion: command node

    @post_load
    def resolve_dot_env_file(self, data, **kwargs):
        return _resolve_dot_env_file(data, **kwargs)

    @pre_load
    def warning_unknown_fields(self, data, **kwargs):
        # log warnings for unknown schema fields
        unknown_fields = set(data) - set(self.fields)
        if unknown_fields:
            logger.warning("Run schema validation warnings. Unknown fields found: %s", unknown_fields)

        return data
