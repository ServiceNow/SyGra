import warnings
import functools


def future_deprecation(reason=None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            msg = f"'{func.__name__}' is scheduled for future deprecation"
            if reason:
                msg += f": {reason}"
            warnings.warn(msg, DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)

        wrapper._future_deprecation = True
        return wrapper

    return decorator
