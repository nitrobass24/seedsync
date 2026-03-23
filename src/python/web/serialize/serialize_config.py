# Copyright 2017, Inderpreet Singh, All rights reserved.

import collections
import json

from common import Config


class SerializeConfig:
    @staticmethod
    def config(config: Config) -> str:
        config_dict = config.as_dict()

        # Make the section names lower case
        keys = list(config_dict.keys())
        config_dict_lowercase = collections.OrderedDict()
        for key in keys:
            config_dict_lowercase[key.lower()] = config_dict[key]

        # Redact sensitive fields
        for section_name_original in keys:
            section_name_lower = section_name_original.lower()
            if section_name_lower in config_dict_lowercase:
                for option_name in config_dict_lowercase[section_name_lower]:
                    if Config.is_sensitive(section_name_original, option_name):
                        config_dict_lowercase[section_name_lower][option_name] = Config.REDACTED_SENTINEL

        return json.dumps(config_dict_lowercase)
