"""
Preprocessing hooks for drf-spectacular to isolate User Developer API endpoints.
"""

def filter_user_endpoints(endpoints):
    """
    Filter only /api/v1/ developer REST endpoints and exclude documentation/keys management.
    """
    filtered = []
    for path, path_regex, method, callback in endpoints:
        # Include /api/v1/ endpoints, excluding documentation endpoints
        if path.startswith('/api/v1/') and '/docs/' not in path and '/keys/' not in path:
            filtered.append((path, path_regex, method, callback))
    return filtered
