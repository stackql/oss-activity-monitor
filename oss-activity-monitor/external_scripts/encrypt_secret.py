import sys
import json
from base64 import b64encode
from nacl import encoding, public

def encrypt(public_key: str, secret_value: str) -> str:
    """Encrypt a Unicode string using the public key."""
    public_key = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted = sealed_box.encrypt(secret_value.encode("utf-8"))
    return b64encode(encrypted).decode("utf-8")

def main():
    if len(sys.argv) != 4:
        print("Usage: python encrypt_string.py {name} {plaintextval} {key}")
        sys.exit(1)
    
    name = sys.argv[1]
    plaintextval = sys.argv[2]
    key = sys.argv[3]

    try:
        ciphertext = encrypt(key, plaintextval)
        # Create JSON object
        result = json.dumps({name: ciphertext})
        print(result)
    except Exception as e:
        print(f"Error occurred: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
