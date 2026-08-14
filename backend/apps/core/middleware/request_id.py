"""Request ID middleware — correlates logs across request/response."""
import uuid

from django.utils.deprecation import MiddlewareMixin

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIDMiddleware(MiddlewareMixin):
    def process_request(self, request):
        request.request_id = (
            request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        )
        return None

    def process_response(self, request, response):
        response[REQUEST_ID_HEADER] = getattr(request, "request_id", "")
        return response
