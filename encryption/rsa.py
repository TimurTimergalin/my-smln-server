from Crypto.PublicKey import RSA


class RsaKeyGenerator:
    def __init__(self, key_length):
        self.key_length = key_length

    def generate_key_pair(self, password):
        key = RSA.generate(self.key_length)
        private_key = key.export_key(passphrase=password, pkcs=8, protection="PBKDF2WithHMAC-SHA1AndAES128-CBC").decode(
            "ascii")
        public_key = key.publickey().export_key(pkcs=8).decode("ascii")
        return public_key, private_key


if __name__ == '__main__':
    rsa = RsaKeyGenerator(1024)
    print(rsa.generate_key_pair("lol"))
