from django.http import HttpResponse

class SimpleCorsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        allowed_headers = "Content-Type, Authorization, X-Requested-With, X-Partner-Key, X-API-Key, Accept, Origin, Cache-Control, Pragma"
        req_headers = request.headers.get("Access-Control-Request-Headers")
        if req_headers:
            allowed_headers = f"{allowed_headers}, {req_headers}"

        if request.method == 'OPTIONS':
            response = HttpResponse()
            response["Access-Control-Allow-Origin"] = "*"
            response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            response["Access-Control-Allow-Headers"] = allowed_headers
            response["Access-Control-Max-Age"] = "86400"
            return response

        response = self.get_response(request)
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
        response["Access-Control-Allow-Headers"] = allowed_headers
        return response

