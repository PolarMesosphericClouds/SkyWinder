import socket


def get_camera_id():
    hostname = socket.gethostname()
    if hostname.startswith('pmc-camera-'):
        try:  # pragma: no cover
            return int(hostname[-1])  # pragma: no cover
        except Exception:  # pragma: no cover
            pass  # pragma: no cover
    return 255
