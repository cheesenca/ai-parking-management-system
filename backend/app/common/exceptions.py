class AppError(Exception):
    """Base class for all application errors"""


class NotFoundError(AppError):
    """Resource requested not found"""


class ValidationError(AppError):
    """Input is not valid"""


class ConflictError(AppError):
    """State conflict"""


class UnauthorizedError(AppError):
    """Invalid or missing credentials"""


class ForbiddenError(AppError):
    """Valid credentials but not allowed to access resource"""