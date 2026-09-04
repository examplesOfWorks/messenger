from pwdlib import PasswordHash


password_hash = PasswordHash.recommended()

SECRET_KEY = "secret-key"
ALGORITHM = "HS256"



def hash_password(password: str) -> str:
    return password_hash.hash(password)