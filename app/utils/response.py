# utils/response.py

def success_response(message_en: str, message_ar: str = None, data: dict = None):
    """
    Standard success response with both English and Arabic messages.
    If message_ar is not provided, frontend can fallback to English.
    """
    return {
        "success": True,
        "message": message_en,
        "message_ar": message_ar or message_en,
        "data": data
    }


def error_response(message_en: str, message_ar: str = None, error_code: str = None):
    """
    Standard error response with both English and Arabic messages.
    """
    return {
        "success": False,
        "message": message_en,
        "message_ar": message_ar or message_en,
        "error_code": error_code
    }
