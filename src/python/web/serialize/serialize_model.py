# Copyright 2017, Inderpreet Singh, All rights reserved.

import json
from datetime import datetime
from enum import Enum
from typing import Any

from model import ModelFile

from .serialize import Serialize


class SerializeModel(Serialize):
    """
    This class defines the serialization interface between the python backend
    and the EventSource client frontend for the model stream.
    """

    class UpdateEvent:
        class Change(Enum):
            ADDED = 0
            REMOVED = 1
            UPDATED = 2

        def __init__(self, change: Change, old_file: ModelFile | None, new_file: ModelFile | None):
            self.change = change
            self.old_file = old_file
            self.new_file = new_file

    # Event keys
    __EVENT_INIT = "model-init"
    __EVENT_UPDATE = {
        UpdateEvent.Change.ADDED: "model-added",
        UpdateEvent.Change.REMOVED: "model-removed",
        UpdateEvent.Change.UPDATED: "model-updated",
    }
    __KEY_UPDATE_OLD_FILE = "old_file"
    __KEY_UPDATE_NEW_FILE = "new_file"

    @staticmethod
    def __model_file_to_json_dict(model_file: ModelFile) -> dict[str, Any]:
        """JSON dict for one file. Key order and value formats are the SSE wire
        contract parsed by the Angular frontend — see the golden test."""

        def ts(t: datetime | None) -> str | None:
            return str(t.timestamp()) if t else None

        return {
            "name": model_file.name,
            "pair_id": model_file.pair_id,
            "is_dir": model_file.is_dir,
            # State enum names lowercased are exactly the wire values
            "state": model_file.state.name.lower(),
            "remote_size": model_file.remote_size,
            "local_size": model_file.local_size,
            "downloading_speed": model_file.downloading_speed,
            "eta": model_file.eta,
            "is_extractable": model_file.is_extractable,
            "local_created_timestamp": ts(model_file.local_created_timestamp),
            "local_modified_timestamp": ts(model_file.local_modified_timestamp),
            "remote_created_timestamp": ts(model_file.remote_created_timestamp),
            "remote_modified_timestamp": ts(model_file.remote_modified_timestamp),
            "full_path": model_file.full_path,
            "children": [SerializeModel.__model_file_to_json_dict(child) for child in model_file.iter_children()],
        }

    def model(self, model_files: list[ModelFile]) -> str:
        """
        Serialize the model
        :return:
        """
        model_json_list = [SerializeModel.__model_file_to_json_dict(f) for f in model_files]
        model_json = json.dumps(model_json_list)
        return self._sse_pack(event=SerializeModel.__EVENT_INIT, data=model_json)

    def update_event(self, event: UpdateEvent):
        model_file_json_dict = {
            SerializeModel.__KEY_UPDATE_OLD_FILE: SerializeModel.__model_file_to_json_dict(event.old_file)
            if event.old_file
            else None,
            SerializeModel.__KEY_UPDATE_NEW_FILE: SerializeModel.__model_file_to_json_dict(event.new_file)
            if event.new_file
            else None,
        }
        model_file_json = json.dumps(model_file_json_dict)
        return self._sse_pack(event=SerializeModel.__EVENT_UPDATE[event.change], data=model_file_json)
