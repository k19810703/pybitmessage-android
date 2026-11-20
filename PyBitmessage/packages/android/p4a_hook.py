"""python-for-android build hook (milestone M4.1c).

Why this file exists
--------------------
p4a v2024.01.21 generates the keep-alive service as::

    <service android:name="<pkg>.Service<name>"
             android:process=":service_<name>" />

with no ``android:foregroundServiceType``. On Android 9+ calling
``startForeground()`` from a service declared without a type is fine for
targetSdk < 34, but with targetSdk 34+ the system throws
``MissingForegroundServiceTypeException``. We declare the type explicitly
now so the app keeps working if targetSdk is ever raised, and so the
existing ``startForeground`` path in p4a's PythonService is unambiguous.

How
---
p4a's ``--extra-manifest-xml`` string is written directly inside the
``<manifest>`` element. A second ``<service>`` node with the *same*
``android:name`` is merged by the Android manifest merger; attributes
declared in the extra XML are added to the generated node.

The hook runs ``before_apk_build`` so the value is in place when the
bootstrap renders AndroidManifest.xml.

Wiring: buildozer.spec -> ``p4a.hook = <path to this file>``
"""

EXTRA_MANIFEST_XML = (
    '<service android:name="at.bitmessage.pybitmessage.ServicePybitmessagesvc" '
    'android:foregroundServiceType="dataSync" />'
)


def before_apk_build(toolchain):
    """Add the foreground service type to the generated manifest."""
    try:
        from pythonforandroid.logger import info
    except Exception:  # noqa: BLE001 - older/newer p4a, keep the build alive
        def info(msg):
            print(msg, flush=True)

    args = toolchain.args
    existing = getattr(args, 'extra_manifest_xml', '') or ''
    if 'foregroundServiceType' in existing:
        info('foregroundServiceType already present, leaving it alone')
        return
    args.extra_manifest_xml = existing + EXTRA_MANIFEST_XML
    info('manifest hook: injected foregroundServiceType=dataSync')


# p4a also supports a dict of hooks; the callable above is enough here.
