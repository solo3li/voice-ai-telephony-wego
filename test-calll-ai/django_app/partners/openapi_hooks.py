"""
Preprocessing hooks for drf-spectacular to isolate Partner SaaS API endpoints.
"""

def filter_partner_endpoints(endpoints):
    """
    Filter only /api/partner/v1/ REST endpoints and exclude documentation/internal UI endpoints.
    """
    filtered = []
    for path, path_regex, method, callback in endpoints:
        # Include /api/partner/v1/ endpoints, excluding documentation and internal UI dashboard endpoints
        if path.startswith('/api/partner/v1/') and '/docs/' not in path and '/apply/' not in path and '/dashboard/' not in path and '/settings/' not in path:
            filtered.append((path, path_regex, method, callback))
    return filtered
