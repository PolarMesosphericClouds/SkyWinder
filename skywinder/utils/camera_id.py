import socket


def get_camera_id():
    hostname = socket.gethostname()
    if hostname.startswith('pmc-camera-'):
        try:  # pragma: no cover
            return int(hostname[-1])  # pragma: no cover
        except Exception:  # pragma: no cover
            pass  # pragma: no cover
    if hostname.startswith('balboa-'):
        try:  # pragma: no cover
            return int(hostname[-1])  # pragma: no cover
        except Exception:  # pragma: no cover
            pass  # pragma: no cover
    if hostname.startswith('clouds'):
        try:  # pragma: no cover
            return 6 # pragma: no cover
        except Exception:  # pragma: no cover
            pass  # pragma: no cover
    return 255
