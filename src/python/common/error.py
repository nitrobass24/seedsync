# Copyright 2017, Inderpreet Singh, All rights reserved.


class AppError(Exception):
    """
    Exception indicating an error
    """

    pass


class ServiceExit(AppError):
    """
    Custom exception which is used to trigger the clean exit
    of all running threads and the main program.
    """

    pass


class ServiceRestart(AppError):
    """
    Exception indicating a restart is requested
    """

    pass


class UnrecoverableError(AppError):
    """
    The controller cannot continue until the user changes a setting (bad
    credentials, wrong paths, missing remote shell, ...). Stops the controller
    and keeps the web app up so Settings stays reachable; everything else that
    reaches the top level still exits the process.
    """

    pass
