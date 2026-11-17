# pylint: disable=unused-import, wrong-import-position, ungrouped-imports
# flake8: noqa:E401, E402

"""Mock kivy app with mock threads."""

import os

# M2.1.1: capability probe must run before anything else so the logcat lines
# are the first thing we see. It never raises by design.
from envprobe import run as probe_environment  # noqa:E402

probe_environment()

from kivy.config import Config  # pylint: disable=import-error, E402

import pybitmessage.state as state
from pybitmessage.bitmessagekivy.mpybit import NavigateApp  # noqa:E402
from pybitmessage.mockbm import multiqueue
from pybitmessage.mockbm.class_addressGenerator import FakeAddressGenerator  # noqa:E402
from pybitmessage.mockbm import network  # noqa:E402

stats = network.stats
objectracker = network.objectracker


def main():
    """main method for starting threads"""
    addressGeneratorThread = FakeAddressGenerator()
    addressGeneratorThread.daemon = True
    addressGeneratorThread.start()
    state.kivyapp = NavigateApp()
    state.kivyapp.run()
    addressGeneratorThread.stopThread()


if __name__ == "__main__":
    os.environ['INSTALL_TESTS'] = "True"
    main()
