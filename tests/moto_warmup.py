"""Import every moto service module once, in one thread, before any worker thread runs.

moto imports a service's modules the first time a call reaches that service.
Discovery lists services from a thread pool, so sixteen threads can make that
first call together. Several moto modules import each other in a circle, and
Python then raises ``deadlock detected by _ModuleLock('moto.awslambda.utils')``
(or ``moto.kms.models``, ``moto.iam.exceptions``, ...) in one thread. InvenTag
records that listing as failed, so the same run gives a different result from
one run to the next. Measured on moto 5.2.5 with 16 first-touch threads in a
fresh process: 4 of 4 cold runs raised it, 0 of 3 runs after this warm-up
(about 4 s, once per process).
"""


def warm_moto_modules() -> int:
    """Import all moto service backends; return how many were loaded."""
    from moto import backends

    loaded = 0
    for name in backends.list_of_moto_modules():
        try:
            backends.get_backend(name)
        except AttributeError:
            continue  # helper packages (core, moto_server, ...) have no backend
        loaded += 1
    return loaded
