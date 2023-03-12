from Crypto.PublicKey import RSA


class RsaKeyGenerator:
    def __init__(self, key_length):
        self.key_length = key_length

    def generate_key_pair(self, password):
        key = RSA.generate(self.key_length)
        return key.public_key().export_key(), key.export_key(passphrase=password, pkcs=8,
                                                             protection="scryptAndAES128-CBC")


