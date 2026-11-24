"""
Select which node to connect to
"""
# pylint: disable=too-many-branches
import logging
import random
import time

from six.moves import queue

from . import knownnodes
import protocol
import state

from bmconfigparser import config
from network import portCheckerQueue

logger = logging.getLogger('default')


def getDiscoveredPeer():
    """Get a peer from the local peer discovery list"""
    try:
        peer = random.choice(list(state.discoveredPeers.keys()))  # nosec B311
    except (IndexError, KeyError):
        raise ValueError
    try:
        del state.discoveredPeers[peer]
    except KeyError:
        pass
    return peer


def chooseConnection(stream):
    """Returns an appropriate connection"""
    haveOnion = config.safeGet(
        "bitmessagesettings", "socksproxytype")[0:5] == 'SOCKS'
    onionOnly = config.safeGetBoolean(
        "bitmessagesettings", "onionservicesonly")
    try:
        retval = portCheckerQueue.get(False)
        portCheckerQueue.task_done()
        return retval
    except queue.Empty:
        pass
    # with a probability of 0.5, connect to a discovered peer
    if random.choice((False, True)) and not haveOnion:  # nosec B311
        # discovered peers are already filtered by allowed streams
        return getDiscoveredPeer()
    # Snapshot the candidates once. knownNodes is mutated from other threads
    # (addr messages) and later cleaned; a list built inside the loop can go
    # empty between the two calls and random.choice() would raise IndexError
    # out of the pool loop, killing the network thread for good.
    candidates = list(knownnodes.knownNodes.get(stream, {}).keys())
    if not candidates:
        # nothing to try for this stream: let the caller's ValueError path
        # skip it instead of crashing the network thread
        raise ValueError
    for _ in range(50):
        peer = random.choice(candidates)  # nosec B311
        try:
            peer_info = knownnodes.knownNodes[stream][peer]
            if peer_info.get('self'):
                continue
            rating = peer_info["rating"]
        except TypeError:
            logger.warning('Error in %s', peer)
            rating = 0
        if haveOnion:
            # do not connect to raw IP addresses
            # --keep all traffic within Tor overlay
            if onionOnly and not peer.host.endswith('.onion'):
                continue
            # onion addresses have a higher priority when SOCKS
            if peer.host.endswith('.onion') and rating > 0:
                rating = 1
            # TODO: need better check
            elif not peer.host.startswith('bootstrap'):
                encodedAddr = protocol.encodeHost(peer.host)
                # don't connect to local IPs when using SOCKS
                if not protocol.checkIPAddress(encodedAddr, False):
                    continue
        roll = random.random()  # nosec B311
        if rating > 1:
            rating = 1
        if config.safeGetBoolean('bootstrap', 'commands'):
            # Bootstrap server: age-based selection with cooldown
            age = time.time() - peer_info.get('lastseen', 0)
            if age < knownnodes.BOOTSTRAP_RETRY_COOLDOWN:
                continue  # 1h cooldown
            prob = float(knownnodes.BOOTSTRAP_RETRY_COOLDOWN) / age
        else:
            try:
                prob = 0.05 / (1.0 - rating)
            except ZeroDivisionError:
                return peer
        if prob > roll:
            return peer
    raise ValueError
