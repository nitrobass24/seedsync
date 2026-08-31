# Copyright 2017, Inderpreet Singh, All rights reserved.

import json

from controller import AutoQueuePattern


class SerializeAutoQueue:
    @staticmethod
    def patterns(patterns: list[AutoQueuePattern]) -> str:
        return json.dumps([{"pattern": p.pattern} for p in patterns])
