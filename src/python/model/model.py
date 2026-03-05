# Copyright 2017, Inderpreet Singh, All rights reserved.

import logging
from abc import ABC, abstractmethod
from typing import Set, Optional, List

# my libs
from common import AppError
from .file import ModelFile


class ModelError(AppError):
    """
    Exception indicating a model error
    """
    pass


class IModelListener(ABC):
    """
    Interface to listen to model events
    """
    @abstractmethod
    def file_added(self, file: ModelFile):
        """
        Event indicating a file was added to the model
        :param file:
        :return:
        """
        pass

    @abstractmethod
    def file_removed(self, file: ModelFile):
        """
        Event indicating that the given file was removed from the model
        :param file:
        :return:
        """
        pass

    @abstractmethod
    def file_updated(self, old_file: ModelFile, new_file: ModelFile):
        """
        Event indicating that the given file was updated
        :param old_file:
        :param new_file:
        :return:
        """
        pass


class Model:
    """
    Represents the entire state of lftp
    """

    @staticmethod
    def file_key(file: ModelFile) -> str:
        """Return the unique key for a ModelFile: 'pair_id:name' or just 'name'."""
        if file.pair_id:
            return "{}:{}".format(file.pair_id, file.name)
        return file.name

    @staticmethod
    def make_key(name: str, pair_id: Optional[str] = None) -> str:
        """Build a key from name and optional pair_id."""
        if pair_id:
            return "{}:{}".format(pair_id, name)
        return name

    def __init__(self):
        self.logger = logging.getLogger("Model")
        self.__files = {}  # key->ModelFile (key is pair_id:name or just name)
        self.__listeners = []

    def set_base_logger(self, base_logger: logging.Logger):
        self.logger = base_logger.getChild("Model")

    def add_listener(self, listener: IModelListener):
        """
        Add a model listener
        :param listener:
        :return:
        """
        self.logger.debug("LftpModel: Adding a listener")
        if listener not in self.__listeners:
            self.__listeners.append(listener)

    def remove_listener(self, listener: IModelListener):
        """
        Add a model listener
        :param listener:
        :return:
        """
        self.logger.debug("LftpModel: Removing a listener")
        if listener not in self.__listeners:
            self.logger.error("LftpModel: listener does not exist!")
        else:
            self.__listeners.remove(listener)

    def add_file(self, file: ModelFile):
        """
        Add a file to the model
        :param file:
        :return:
        """
        key = Model.file_key(file)
        self.logger.debug("LftpModel: Adding file '{}'".format(key))
        if key in self.__files:
            raise ModelError("File already exists in the model")
        self.__files[key] = file
        for listener in self.__listeners:
            listener.file_added(self.__files[key])

    def remove_file(self, filename: str, pair_id: Optional[str] = None):
        """
        Remove the file from the model
        :param filename:
        :param pair_id:
        :return:
        """
        key = Model.make_key(filename, pair_id)
        self.logger.debug("LftpModel: Removing file '{}'".format(key))
        if key not in self.__files:
            raise ModelError("File does not exist in the model")
        file = self.__files[key]
        del self.__files[key]
        for listener in self.__listeners:
            listener.file_removed(file)

    def update_file(self, file: ModelFile):
        """
        Update an already existing file
        :param file:
        :return:
        """
        key = Model.file_key(file)
        self.logger.debug("LftpModel: Updating file '{}'".format(key))
        if key not in self.__files:
            raise ModelError("File does not exist in the model")
        old_file = self.__files[key]
        new_file = file
        self.__files[key] = new_file
        for listener in self.__listeners:
            listener.file_updated(old_file, new_file)

    def get_file(self, name: str, pair_id: Optional[str] = None) -> ModelFile:
        """
        Returns the file of the given name (and optional pair_id)
        :param name:
        :param pair_id:
        :return:
        """
        key = Model.make_key(name, pair_id)
        if key not in self.__files:
            raise ModelError("File does not exist in the model")
        return self.__files[key]

    def get_file_keys(self) -> Set[str]:
        """Return the set of composite keys (pair_id:name or name)."""
        return set(self.__files.keys())

    def get_file_names(self) -> Set[str]:
        """Return all file names (without pair_id prefix) for backward compat."""
        return {f.name for f in self.__files.values()}

    def get_all_files(self) -> List[ModelFile]:
        """Return all files in the model."""
        return list(self.__files.values())
