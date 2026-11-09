import os

from django.conf import settings


def asset_version(request):
    """Cache-busting token: changes whenever our CSS/JS files change."""
    latest = 0
    for rel in ("css/healio.css", "js/healio.js"):
        path = os.path.join(settings.BASE_DIR, "static", rel)
        try:
            latest = max(latest, int(os.path.getmtime(path)))
        except OSError:
            pass
    return {"ASSET_VERSION": latest}
