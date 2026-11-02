# SPDX-License-Identifier: Apache-2.0
"""
Global context processor for language and localization across all templates.
"""

def language_context(request):
    """
    Exposes uniform language and localization context to all Django templates.
    Resolves language using 4-tier hierarchy:
    1. URL query parameters: ?lang= or ?locale=
    2. Cookies: app_lang, django_language, voice_app_lang
    3. Session language if set
    4. Default: 'ar'
    """
    raw_lang = (
        request.GET.get('lang') or
        request.GET.get('locale') or
        request.COOKIES.get('app_lang') or
        request.COOKIES.get('django_language') or
        request.COOKIES.get('voice_app_lang') or
        'ar'
    ).lower().strip()
    valid_langs = ('ar', 'en', 'tr', 'fr', 'de', 'es')
    lang = raw_lang if raw_lang in valid_langs else 'ar'
    return {
        'current_lang': lang,
        'locale': lang,
        'user_lang': lang,
        'is_ar': (lang == 'ar'),
        'valid_languages': valid_langs,
    }
