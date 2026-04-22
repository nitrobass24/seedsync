# Copyright 2017, Inderpreet Singh, All rights reserved.

import contextlib
import os


class TestUtils:
    @staticmethod
    def chmod_from_to(from_path: str, to_path: str, mode: int):
        """
        Chmod from_path and all its parents up to and including to_path
        :param from_path:
        :param to_path:
        :param mode:
        :return:
        """
        path = from_path
        with contextlib.suppress(PermissionError):
            os.chmod(path, mode)
        while path != "/" and path != to_path:
            path = os.path.dirname(path)
            with contextlib.suppress(PermissionError):
                os.chmod(path, mode)
