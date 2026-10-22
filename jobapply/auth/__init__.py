"""jobapply.auth — authentication, token management, and FastAPI dependencies.

Modules
-------
passwords.py    bcrypt hash / verify helpers
tokens.py       JWT access + refresh token creation / decoding; raw-token hashing
email.py        send verification and password-reset emails
dependencies.py get_current_user FastAPI dependency
router.py       /api/auth/* route handlers
"""
