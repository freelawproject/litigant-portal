"""The visitor's address, for per-IP rate limits.

Behind CloudFront and the ALB, ``REMOTE_ADDR`` is a proxy. CloudFront
sets ``CloudFront-Viewer-Address`` to the visitor's ``IP:port`` and
overwrites any value the client sent. The header is read only when
``TRUST_CLOUDFRONT_VIEWER_ADDRESS`` is on: without CloudFront in front,
a client could send its own. ``X-Forwarded-For`` is never read.
"""

import ipaddress
import logging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Always returns an address: the rate limiters parse the result."""
    if settings.TRUST_CLOUDFRONT_VIEWER_ADDRESS:
        header = request.META.get("HTTP_CLOUDFRONT_VIEWER_ADDRESS", "")
        # IPv6 arrives unbracketed (2600:1f18::1234:51396), so the port is
        # whatever follows the last colon.
        host = header.rpartition(":")[0].strip("[]")
        try:
            ip = ipaddress.ip_address(host)
        except ValueError:
            logger.warning(
                "CloudFront-Viewer-Address missing or invalid; "
                "rate limits are counting REMOTE_ADDR"
            )
        else:
            return str(getattr(ip, "ipv4_mapped", None) or ip)
    remote_addr = request.META.get("REMOTE_ADDR")
    if not remote_addr:
        raise ImproperlyConfigured("REMOTE_ADDR is empty")
    return remote_addr
