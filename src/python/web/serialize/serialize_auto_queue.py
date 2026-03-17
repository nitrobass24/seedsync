# Copyright 2017, Inderpreet Singh, All rights reserved.

import json

from controller import AutoQueuePattern


class SerializeAutoQueue:
    __KEY_PATTERN = "pattern"

    @staticmethod
    def patterns(patterns: list[AutoQueuePattern]) -> str:
        patterns_list = []
        for pattern in patterns:
            patterns_list.append({SerializeAutoQueue.__KEY_PATTERN: pattern.pattern})

        return json.dumps(patterns_list)
