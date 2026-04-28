# Copyright 2017, Inderpreet Singh, All rights reserved.

import collections
import configparser
from abc import ABC
from collections.abc import Callable
from io import StringIO
from typing import Any, TypeVar

from .error import AppError
from .persist import Persist, PersistError
from .types import overrides


def _strtobool(val: str) -> bool:
    val = val.strip().lower()
    if val in ("y", "yes", "t", "true", "on", "1"):
        return True
    if val in ("n", "no", "f", "false", "off", "0"):
        return False
    raise ValueError(f"invalid truth value {val!r}")


class ConfigError(AppError):
    """
    Exception indicating a bad config value
    """

    pass


InnerConfigType = dict[str, str]
OuterConfigType = dict[str, InnerConfigType]


# Source: https://stackoverflow.com/a/39205612/8571324
T = TypeVar("T", bound="InnerConfig")


class Converters:
    @staticmethod
    def null(_: T, __: str, value: str) -> str:  # type: ignore[reportInvalidTypeVarUse]
        return value

    @staticmethod
    def int(cls: T, name: str, value: str) -> int:  # type: ignore[reportInvalidTypeVarUse, reportSelfClsParameterName]
        if not value:
            raise ConfigError(f"Bad config: {cls.__name__}.{name} is empty")
        try:
            val = int(value)
        except ValueError:
            raise ConfigError(f"Bad config: {cls.__name__}.{name} ({value}) must be an integer value") from None
        return val

    @staticmethod
    def bool(cls: T, name: str, value: str) -> bool:  # type: ignore[reportInvalidTypeVarUse, reportSelfClsParameterName]
        if not value:
            raise ConfigError(f"Bad config: {cls.__name__}.{name} is empty")
        try:
            val = bool(_strtobool(value))
        except ValueError:
            raise ConfigError(f"Bad config: {cls.__name__}.{name} ({value}) must be a boolean value") from None
        return val


class Checkers:
    @staticmethod
    def null(_: T, __: str, value: Any) -> Any:  # type: ignore[reportInvalidTypeVarUse]
        return value

    @staticmethod
    def string_nonempty(cls: T, name: str, value: str) -> str:  # type: ignore[reportInvalidTypeVarUse, reportSelfClsParameterName]
        if not value or not value.strip():
            raise ConfigError(f"Bad config: {cls.__name__}.{name} is empty")
        return value

    @staticmethod
    def string_allow_empty(cls: T, name: str, value: str) -> str:  # type: ignore[reportInvalidTypeVarUse, reportSelfClsParameterName]
        return value

    @staticmethod
    def int_non_negative(cls: T, name: str, value: int) -> int:  # type: ignore[reportInvalidTypeVarUse, reportSelfClsParameterName]
        if value < 0:
            raise ConfigError(f"Bad config: {cls.__name__}.{name} ({value}) must be zero or greater")
        return value

    @staticmethod
    def int_positive(cls: T, name: str, value: int) -> int:  # type: ignore[reportInvalidTypeVarUse, reportSelfClsParameterName]
        if value < 1:
            raise ConfigError(f"Bad config: {cls.__name__}.{name} ({value}) must be greater than 0")
        return value

    @staticmethod
    def algorithm_allowed(cls: T, name: str, value: str) -> str:  # type: ignore[reportInvalidTypeVarUse, reportSelfClsParameterName]
        allowed = {"md5", "sha1", "sha256"}
        normalized = value.strip().lower() if value else ""
        if normalized not in allowed:
            raise ConfigError(
                "Bad config: {}.{} ({}) must be one of: {}".format(
                    cls.__name__, name, value, ", ".join(sorted(allowed))
                )
            )
        return normalized

    @staticmethod
    def log_level_allowed(cls: T, name: str, value: str) -> str:  # type: ignore[reportInvalidTypeVarUse, reportSelfClsParameterName]
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        normalized = value.strip().upper() if value else ""
        if normalized not in allowed:
            raise ConfigError(
                "Bad config: {}.{} ({}) must be one of: {}".format(
                    cls.__name__, name, value, ", ".join(sorted(allowed))
                )
            )
        return normalized


class InnerConfig(ABC):
    """
    Abstract base class for a config section
    Config values are exposed as properties. They must be set using their native type.
    Internal utility methods are provided to convert strings to native types. These are
    only used when creating config from a dict.

    Implementation details:
    Each property has associated with is a checker and a converter function.
    The checker function performs boundary check on the native type value.
    The converter function converts the string representation into the native type.
    """

    class PropMetadata:
        """Tracks property metadata"""

        def __init__(self, checker: Callable[..., Any], converter: Callable[..., Any]):
            self.checker = checker
            self.converter = converter

    # Global map to map a property to its metadata
    # Is there a way for each concrete class to do this separately?
    __prop_addon_map: collections.OrderedDict[property, "InnerConfig.PropMetadata"] = collections.OrderedDict()

    @classmethod
    def _create_property(cls, name: str, checker: Callable[..., Any], converter: Callable[..., Any]) -> property:
        # noinspection PyProtectedMember
        prop = property(fget=lambda s: s._get_property(name), fset=lambda s, v: s._set_property(name, v, checker))
        prop_addon = InnerConfig.PropMetadata(checker=checker, converter=converter)
        InnerConfig.__prop_addon_map[prop] = prop_addon
        return prop

    def _get_property(self, name: str) -> Any:
        return getattr(self, "__" + name, None)

    def _set_property(self, name: str, value: Any, checker: Callable[..., Any]):
        # Allow setting to None for the first time
        if value is None and self._get_property(name) is None:
            setattr(self, "__" + name, None)
        else:
            setattr(self, "__" + name, checker(self.__class__, name, value))

    @classmethod
    def from_dict(cls: type[T], config_dict: InnerConfigType) -> T:
        """
        Construct and return inner config from a dict
        Dict values can be either native types, or str representations
        Missing keys use the default value from the class __init__.
        Extra keys are silently ignored (forward/backward compatibility).
        :param config_dict:
        :return:
        """
        config_dict = dict(config_dict)  # copy that we can modify

        # Create instance with defaults from __init__
        # noinspection PyCallingNonCallable
        inner_config = cls()
        property_map = {p: getattr(cls, p) for p in dir(cls) if isinstance(getattr(cls, p), property)}
        for name in property_map:
            if name in config_dict:
                value = config_dict[name]
                # to_str() serializes None as "". When reading back, treat
                # empty strings as missing if the default is None, so that
                # the None → "" → None round-trip is preserved.
                if type(value) is str and value == "" and getattr(inner_config, name) is None:
                    del config_dict[name]
                    continue
                inner_config.set_property(name, value)
                del config_dict[name]
            # If key is missing, keep the default from __init__

        # Silently ignore extra keys (from newer/older config versions)

        return inner_config

    def as_dict(self) -> InnerConfigType:
        """
        Return the dict representation of the inner config
        :return:
        """
        config_dict: collections.OrderedDict[str, Any] = collections.OrderedDict()
        cls = self.__class__
        my_property_to_name_map = {getattr(cls, p): p for p in dir(cls) if isinstance(getattr(cls, p), property)}
        # Arrange prop names in order of creation. Use the prop map to get the order
        # Prop map contains all properties of all config classes, so filtering is required
        all_properties = InnerConfig.__prop_addon_map.keys()
        for prop in all_properties:
            if prop in my_property_to_name_map:
                name = my_property_to_name_map[prop]
                config_dict[name] = getattr(self, name)
        return config_dict

    def has_property(self, name: str) -> bool:
        """
        Returns true if the given property exists, false otherwise
        :param name:
        :return:
        """
        try:
            return isinstance(getattr(self.__class__, name), property)
        except AttributeError:
            return False

    def set_property(self, name: str, value: Any):
        """
        Set a property dynamically
        Do a str conversion of the value, if necessary
        :param name:
        :param value:
        :return:
        """
        cls = self.__class__
        prop_addon = InnerConfig.__prop_addon_map[getattr(cls, name)]
        # Do the conversion if value is of type str
        native_value = prop_addon.converter(cls, name, value) if type(value) is str else value
        # Set the property, which will invoke the checker
        # noinspection PyProtectedMember
        self._set_property(name, native_value, prop_addon.checker)


# Useful aliases
IC = InnerConfig
# noinspection PyProtectedMember
PROP = InnerConfig._create_property  # type: ignore[reportPrivateUsage]


class Config(Persist):
    """
    Configuration registry
    """

    class General(IC):
        log_level = PROP("log_level", Checkers.log_level_allowed, Converters.null)
        verbose = PROP("verbose", Checkers.null, Converters.bool)
        exclude_patterns = PROP("exclude_patterns", Checkers.string_allow_empty, Converters.null)

        def __init__(self):
            super().__init__()
            self.log_level = "INFO"
            self.verbose = None
            self.exclude_patterns = ""

    class Lftp(IC):
        remote_address = PROP("remote_address", Checkers.string_nonempty, Converters.null)
        remote_username = PROP("remote_username", Checkers.string_nonempty, Converters.null)
        remote_password = PROP("remote_password", Checkers.string_allow_empty, Converters.null)
        remote_port = PROP("remote_port", Checkers.int_positive, Converters.int)
        remote_path = PROP("remote_path", Checkers.string_nonempty, Converters.null)
        local_path = PROP("local_path", Checkers.string_nonempty, Converters.null)
        remote_path_to_scan_script = PROP("remote_path_to_scan_script", Checkers.string_nonempty, Converters.null)
        remote_python_path = PROP("remote_python_path", Checkers.string_allow_empty, Converters.null)
        use_ssh_key = PROP("use_ssh_key", Checkers.null, Converters.bool)
        num_max_parallel_downloads = PROP("num_max_parallel_downloads", Checkers.int_positive, Converters.int)
        num_max_parallel_files_per_download = PROP(
            "num_max_parallel_files_per_download", Checkers.int_positive, Converters.int
        )
        num_max_connections_per_root_file = PROP(
            "num_max_connections_per_root_file", Checkers.int_positive, Converters.int
        )
        num_max_connections_per_dir_file = PROP(
            "num_max_connections_per_dir_file", Checkers.int_positive, Converters.int
        )
        num_max_total_connections = PROP("num_max_total_connections", Checkers.int_non_negative, Converters.int)
        use_temp_file = PROP("use_temp_file", Checkers.null, Converters.bool)
        net_limit_rate = PROP("net_limit_rate", Checkers.string_allow_empty, Converters.null)
        net_socket_buffer = PROP("net_socket_buffer", Checkers.string_allow_empty, Converters.null)
        pget_min_chunk_size = PROP("pget_min_chunk_size", Checkers.string_allow_empty, Converters.null)
        mirror_parallel_directories = PROP("mirror_parallel_directories", Checkers.null, Converters.bool)
        net_timeout = PROP("net_timeout", Checkers.int_non_negative, Converters.int)
        net_max_retries = PROP("net_max_retries", Checkers.int_non_negative, Converters.int)
        net_reconnect_interval_base = PROP("net_reconnect_interval_base", Checkers.int_non_negative, Converters.int)
        net_reconnect_interval_multiplier = PROP(
            "net_reconnect_interval_multiplier", Checkers.int_non_negative, Converters.int
        )

        def __init__(self):
            super().__init__()
            self.remote_address = None
            self.remote_username = None
            self.remote_password = None
            self.remote_port = None
            self.remote_path = None
            self.local_path = None
            self.remote_path_to_scan_script = None
            self.remote_python_path = ""
            self.use_ssh_key = None
            self.num_max_parallel_downloads = None
            self.num_max_parallel_files_per_download = None
            self.num_max_connections_per_root_file = None
            self.num_max_connections_per_dir_file = None
            self.num_max_total_connections = None
            self.use_temp_file = None
            self.net_limit_rate = ""
            self.net_socket_buffer = None
            self.pget_min_chunk_size = None
            self.mirror_parallel_directories = None
            self.net_timeout = None
            self.net_max_retries = None
            self.net_reconnect_interval_base = None
            self.net_reconnect_interval_multiplier = None

    class Controller(IC):
        interval_ms_remote_scan = PROP("interval_ms_remote_scan", Checkers.int_positive, Converters.int)
        interval_ms_local_scan = PROP("interval_ms_local_scan", Checkers.int_positive, Converters.int)
        interval_ms_downloading_scan = PROP("interval_ms_downloading_scan", Checkers.int_positive, Converters.int)
        extract_path = PROP("extract_path", Checkers.string_nonempty, Converters.null)
        use_local_path_as_extract_path = PROP("use_local_path_as_extract_path", Checkers.null, Converters.bool)
        use_staging = PROP("use_staging", Checkers.null, Converters.bool)
        staging_path = PROP("staging_path", Checkers.string_nonempty, Converters.null)

        def __init__(self):
            super().__init__()
            self.interval_ms_remote_scan = None
            self.interval_ms_local_scan = None
            self.interval_ms_downloading_scan = None
            self.extract_path = None
            self.use_local_path_as_extract_path = None
            self.use_staging = None
            self.staging_path = None

    class Web(InnerConfig):
        port = PROP("port", Checkers.int_positive, Converters.int)
        api_key = PROP("api_key", Checkers.string_allow_empty, Converters.null)

        def __init__(self):
            super().__init__()
            self.port = None
            self.api_key = ""

    class AutoQueue(InnerConfig):
        enabled = PROP("enabled", Checkers.null, Converters.bool)
        patterns_only = PROP("patterns_only", Checkers.null, Converters.bool)
        auto_extract = PROP("auto_extract", Checkers.null, Converters.bool)
        auto_delete_remote = PROP("auto_delete_remote", Checkers.null, Converters.bool)

        def __init__(self):
            super().__init__()
            self.enabled = None
            self.patterns_only = None
            self.auto_extract = None
            self.auto_delete_remote = None

    class Logging(IC):
        log_format = PROP("log_format", Checkers.string_allow_empty, Converters.null)

        def __init__(self):
            super().__init__()
            self.log_format = "standard"

    class Notifications(IC):
        webhook_url = PROP("webhook_url", Checkers.string_allow_empty, Converters.null)
        notify_on_download_complete = PROP("notify_on_download_complete", Checkers.null, Converters.bool)
        notify_on_extraction_complete = PROP("notify_on_extraction_complete", Checkers.null, Converters.bool)
        notify_on_extraction_failed = PROP("notify_on_extraction_failed", Checkers.null, Converters.bool)
        notify_on_delete_complete = PROP("notify_on_delete_complete", Checkers.null, Converters.bool)
        discord_webhook_url = PROP("discord_webhook_url", Checkers.string_allow_empty, Converters.null)
        telegram_bot_token = PROP("telegram_bot_token", Checkers.string_allow_empty, Converters.null)
        telegram_chat_id = PROP("telegram_chat_id", Checkers.string_allow_empty, Converters.null)

        def __init__(self):
            super().__init__()
            self.webhook_url = ""
            self.notify_on_download_complete = True
            self.notify_on_extraction_complete = True
            self.notify_on_extraction_failed = True
            self.notify_on_delete_complete = True
            self.discord_webhook_url = ""
            self.telegram_bot_token = ""
            self.telegram_chat_id = ""

    class Validate(IC):
        enabled = PROP("enabled", Checkers.null, Converters.bool)
        algorithm = PROP("algorithm", Checkers.algorithm_allowed, Converters.null)
        auto_validate = PROP("auto_validate", Checkers.null, Converters.bool)
        xfer_verify = PROP("xfer_verify", Checkers.null, Converters.bool)

        def __init__(self):
            super().__init__()
            self.enabled = False
            self.algorithm = "md5"
            self.auto_validate = True
            self.xfer_verify = True

    def __init__(self):
        self.general = Config.General()
        self.lftp = Config.Lftp()
        self.controller = Config.Controller()
        self.web = Config.Web()
        self.autoqueue = Config.AutoQueue()
        self.logging = Config.Logging()
        self.notifications = Config.Notifications()
        self.validate = Config.Validate()

    @staticmethod
    def _check_section(dct: OuterConfigType, name: str) -> InnerConfigType:
        if name not in dct:
            raise ConfigError(f"Missing config section: {name}")
        val = dct[name]
        del dct[name]
        return val

    @staticmethod
    def _check_empty_outer_dict(dct: OuterConfigType):
        # Silently ignore unknown sections for forward/backward compatibility
        pass

    @classmethod
    @overrides(Persist)
    def from_str(cls: type["Config"], content: str) -> "Config":
        config_parser = configparser.ConfigParser()
        try:
            config_parser.read_string(content)
        except (configparser.MissingSectionHeaderError, configparser.ParsingError) as e:
            raise PersistError(f"Error parsing Config - {type(e).__name__}: {e!s}") from e
        config_dict: OuterConfigType = {}
        for section in config_parser.sections():
            config_dict[section] = {}
            for option in config_parser.options(section):
                config_dict[section][option] = config_parser.get(section, option)
        return cls.from_dict(config_dict)

    @overrides(Persist)
    def to_str(self) -> str:
        config_parser = configparser.ConfigParser()
        config_dict = self.as_dict()
        for section in config_dict:
            config_parser.add_section(section)
            section_dict = config_dict[section]
            for key in section_dict:
                value = section_dict[key]
                config_parser.set(section, key, "" if value is None else str(value))  # type: ignore[reportUnnecessaryComparison]
        str_io = StringIO()
        config_parser.write(str_io)
        return str_io.getvalue()

    @staticmethod
    def from_dict(config_dict: OuterConfigType) -> "Config":
        config_dict = dict(config_dict)  # copy that we can modify
        config = Config()

        config.general = Config.General.from_dict(config_dict.pop("General", {}))
        config.lftp = Config.Lftp.from_dict(config_dict.pop("Lftp", {}))
        config.controller = Config.Controller.from_dict(config_dict.pop("Controller", {}))
        config.web = Config.Web.from_dict(config_dict.pop("Web", {}))
        config.autoqueue = Config.AutoQueue.from_dict(config_dict.pop("AutoQueue", {}))
        config.logging = Config.Logging.from_dict(config_dict.pop("Logging", {}))
        config.notifications = Config.Notifications.from_dict(config_dict.pop("Notifications", {}))
        # The legacy [Integrations] section is migrated to integrations.json on
        # startup (see Seedsync._load_integrations_config). Drop it here so
        # subsequent persists rewrite settings.cfg without the section.
        config_dict.pop("Integrations", None)
        config.validate = Config.Validate.from_dict(config_dict.pop("Validate", {}))

        Config._check_empty_outer_dict(config_dict)
        return config

    def as_dict(self) -> OuterConfigType:
        # We convert all values back to strings
        # Use an ordered dict to main section order
        config_dict: collections.OrderedDict[str, InnerConfigType] = collections.OrderedDict()
        config_dict["General"] = self.general.as_dict()
        config_dict["Lftp"] = self.lftp.as_dict()
        config_dict["Controller"] = self.controller.as_dict()
        config_dict["Web"] = self.web.as_dict()
        config_dict["AutoQueue"] = self.autoqueue.as_dict()
        config_dict["Logging"] = self.logging.as_dict()
        config_dict["Notifications"] = self.notifications.as_dict()
        config_dict["Validate"] = self.validate.as_dict()
        return config_dict

    # Sentinel value used to replace sensitive fields in API responses
    REDACTED_SENTINEL = "********"

    @staticmethod
    def sensitive_property_names() -> dict[str, set[str]]:
        """
        Returns a mapping of section name -> set of property names that contain
        sensitive data (passwords, API keys, etc.) and should be redacted in
        API responses.
        """
        return {
            "Lftp": {"remote_password"},
            "Web": {"api_key"},
            "Notifications": {"webhook_url", "discord_webhook_url", "telegram_bot_token"},
        }

    @staticmethod
    def is_sensitive(section_name: str, option_name: str) -> bool:
        """
        Returns True if the given section/option pair refers to a sensitive
        field that should be redacted in API output.
        Section name matching is case-insensitive.
        """
        sensitive = Config.sensitive_property_names()
        section_lower = section_name.lower()
        return any(key.lower() == section_lower and option_name in options for key, options in sensitive.items())

    def has_section(self, name: str) -> bool:
        """
        Returns true if the given section exists, false otherwise
        :param name:
        :return:
        """
        try:
            return isinstance(getattr(self, name), InnerConfig)
        except AttributeError:
            return False
