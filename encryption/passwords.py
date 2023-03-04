import hashlib
from encryption.utils import *


class PasswordHasher:
    hash_algorithms = {name: getattr(hashlib, name) for name in hashlib.algorithms_guaranteed}

    def __init__(self, alg):
        self.alg = self.hash_algorithms[alg]
        self.alg_name = alg

    def hash_password(self, password):

        salt = generate_salt()

        m = self.alg()
        m.update(salt)
        m.update(password.encode("utf-8"))
        return f"{self.alg_name}${salt.decode('utf-8')}${m.hexdigest()}"

    def check_password(self, password, hashed_password):
        alg_name, salt, digest = hashed_password.split('$')

        alg = self.hash_algorithms[alg_name]

        m = alg()
        m.update(salt.encode("utf-8"))
        m.update(password.encode("utf-8"))
        return m.hexdigest() == digest


if __name__ == '__main__':
    hasher = PasswordHasher("sha3_256")

    pw = "super_secure_password"

    hsd = hasher.hash_password(pw)
    print(hsd)

    print(hasher.check_password(pw, hsd))
