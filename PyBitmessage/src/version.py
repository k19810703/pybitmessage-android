"""Version strings advertised to the network.

``softwareVersion`` is not cosmetic: it goes into the ``version`` message as
``/PyBitmessage:<softwareVersion>/``, so every peer sees it, and it is also the
APK's ``versionName`` (buildozer ``version =`` in
``packages/android/buildozer.spec`` must stay identical -- M5.1.2).
"""

softwareName = 'PyBitmessage'
softwareVersion = '0.6.3.2'
