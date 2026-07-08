# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

import unreal  # type: ignore[import]

from deadline.client.job_bundle.submission import AssetReferences
from deadline.client.submitter_api import SubmitterAPI, SubmitterSettings


@dataclass
class UnrealSubmitterSettings(SubmitterSettings):
    """Unreal Engine-specific submission settings."""

    level_path: str = ""
    level_sequence_path: str = ""
    render_preset: str = ""
    extra_cmd_args: str = ""
    description: str = ""


class UnrealSubmitterAPI(SubmitterAPI):
    """SubmitterAPI implementation for Unreal Engine submissions."""

    def get_settings(self) -> UnrealSubmitterSettings:
        settings = UnrealSubmitterSettings()

        project_dir = unreal.Paths.project_dir()
        settings.project_path = unreal.Paths.convert_relative_path_to_full(project_dir)
        settings.name = unreal.Paths.get_project_file_path().split("/")[-1].replace(".uproject", "")

        settings.input_directories = [settings.project_path]
        settings.output_path = os.path.join(settings.project_path, "Saved", "MovieRenders")
        settings.output_directories = [settings.output_path]

        return settings

    def get_job_template(
        self,
        settings: SubmitterSettings,
        host_requirements: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        parameter_definitions: list[dict[str, Any]] = [
            {
                "name": "UnrealProjectPath",
                "type": "PATH",
                "objectType": "FILE",
                "dataFlow": "IN",
            },
        ]
        command_args: list[str] = ["{{Param.UnrealProjectPath}}"]

        # Optional parameters MUST mirror exactly what get_parameter_values emits:
        # any value emitted under a non-"deadline:" name without a matching
        # parameterDefinition here makes the bundle fail validation (the bundle
        # loader rejects "a value provided for an undefined parameter", and
        # split_parameter_args raises KeyError on the missing "type"). Guard each
        # definition with the same truthiness check used when emitting its value
        # so the two sides stay in lockstep.
        if isinstance(settings, UnrealSubmitterSettings):
            if settings.level_path:
                parameter_definitions.append(
                    {"name": "LevelPath", "type": "STRING", "minLength": 1}
                )
                command_args.append("{{Param.LevelPath}}")
            if settings.level_sequence_path:
                parameter_definitions.append(
                    {"name": "LevelSequencePath", "type": "STRING", "minLength": 1}
                )
                command_args.append("{{Param.LevelSequencePath}}")
            if settings.extra_cmd_args:
                parameter_definitions.append(
                    {"name": "ExtraCmdArgs", "type": "STRING", "minLength": 1}
                )
                command_args.append("{{Param.ExtraCmdArgs}}")

        job_template: dict[str, Any] = {
            "specificationVersion": "jobtemplate-2023-09",
            # OpenJD requires a non-empty job name; fall back if the scene had no
            # resolvable .uproject name so CreateJob does not reject the template.
            "name": settings.name or "UnrealJob",
            "parameterDefinitions": parameter_definitions,
            "steps": [
                {
                    "name": "Render",
                    "script": {
                        "actions": {
                            "onRun": {
                                "command": "UnrealEditor-Cmd",
                                "args": command_args,
                            }
                        }
                    },
                }
            ],
        }

        if isinstance(settings, UnrealSubmitterSettings) and settings.description:
            job_template["description"] = settings.description

        if host_requirements:
            for step in job_template.get("steps", []):
                step["hostRequirements"] = host_requirements

        return job_template

    def get_parameter_values(
        self,
        settings: SubmitterSettings,
        queue_parameters: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        parameter_values: list[dict[str, Any]] = [
            {"name": "UnrealProjectPath", "value": settings.project_path},
            {"name": "deadline:priority", "value": settings.priority},
            {"name": "deadline:targetTaskRunStatus", "value": settings.initial_status},
            {"name": "deadline:maxFailedTasksCount", "value": settings.max_failed_tasks_count},
            {"name": "deadline:maxRetriesPerTask", "value": settings.max_retries_per_task},
        ]

        if isinstance(settings, UnrealSubmitterSettings):
            if settings.level_path:
                parameter_values.append({"name": "LevelPath", "value": settings.level_path})
            if settings.level_sequence_path:
                parameter_values.append(
                    {"name": "LevelSequencePath", "value": settings.level_sequence_path}
                )
            if settings.extra_cmd_args:
                parameter_values.append({"name": "ExtraCmdArgs", "value": settings.extra_cmd_args})

        parameter_values.extend(
            {"name": param["name"], "value": param["value"]} for param in queue_parameters
        )

        return parameter_values

    def get_asset_references(self, settings: SubmitterSettings) -> dict[str, Any]:
        asset_refs = AssetReferences(
            input_filenames=set(settings.input_filenames),
            input_directories=set(settings.input_directories),
            output_directories=set(settings.output_directories),
        )
        return asset_refs.to_dict()
