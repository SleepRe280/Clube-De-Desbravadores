import warnings

from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect

db = SQLAlchemy()
csrf = CSRFProtect()

try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address

    limiter = Limiter(
        key_func=get_remote_address, storage_uri="memory://", default_limits=[]
    )
except ImportError:

    class _NoOpLimiter:
        """Substitui o limitador se Flask-Limiter não estiver instalado no interpretador atual."""

        def init_app(self, app):
            warnings.warn(
                "Flask-Limiter não está instalado: rate limiting desativado para esta sessão. "
                "Execute: python -m pip install -r requirements.txt (com o mesmo Python que rode o app).",
                stacklevel=2,
            )

        def limit(self, *args, **kwargs):

            def decorator(f):
                return f

            return decorator

    limiter = _NoOpLimiter()
