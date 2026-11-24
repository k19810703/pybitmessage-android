"""Find where a module on this machine really comes from (diagnostic).

Several PyBitmessage checkouts and stale copies on sys.path made "the file
says X but the process runs Y" happen twice today. This prints the resolved
``__file__`` and a sentinel from the source for every module asked for.

  python3 scripts/which_module.py network.tcp network.bmproto
"""
import os
import sys

SRC = os.path.abspath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'PyBitmessage', 'src'))
sys.path.insert(0, SRC)

os.environ.setdefault('BITMESSAGE_HOME', '/tmp/whichmodule')


def main(names):
    import importlib
    import state  # noqa: F401  (config bootstrap side effects)
    print('SRC on path:', SRC)
    for name in names:
        mod = importlib.import_module(name)
        path = getattr(mod, '__file__', '?')
        real = os.path.realpath(path)
        print('%-24s -> %s' % (name, real))
        same = os.path.realpath(path).startswith(os.path.realpath(SRC))
        print('%-24s    inside %s: %s' % ('', os.path.basename(SRC), same))
        if hasattr(mod, 'TCPConnection'):
            import inspect
            src = inspect.getsource(mod.TCPConnection)
            print('%-24s    has sendBigInv: %s' % ('', 'sendBigInv' in src))
        if hasattr(mod, 'BMProto'):
            import inspect
            src = inspect.getsource(mod.BMProto.peerValidityChecks)
            print('%-24s    PVC sends inv: %s' % (
                '', 'sendBigInv' in src or 'sendAddr' in src))
    print('sys.path[0:4]:', [p for p in sys.path[:4]])


if __name__ == '__main__':
    main(sys.argv[1:] or ['network.tcp', 'network.bmproto'])
