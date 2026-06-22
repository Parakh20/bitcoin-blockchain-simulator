# Using secp256k1 curve for Elliptic Curve Cryptography
from ecdsa import SigningKey, SECP256k1
import hashlib
from script_engine import ScriptEngine

def generate_key_pair():
    # Generates an ECDSA key pair.
    private_key = SigningKey.generate(curve=SECP256k1)
    public_key = private_key.verifying_key
    
    return {
            'private': private_key.to_string().hex(), 
            'public': public_key.to_string().hex()
            }

def invert_bytes(hex_string):
    # Reverses the byte order of a hex string (Big-Endian <-> Little-Endian).
    byte_array = bytearray.fromhex(hex_string)
    byte_array.reverse()
    return (''.join(format(x, '02x') for x in byte_array)).upper()

def compute_hash160(data_string):
    # Computes RIPEMD160(SHA256(data)).
    sha256_hash = hashlib.sha256(str.encode(data_string)).digest()
    ripemd160_hash = hashlib.new('ripemd160', sha256_hash).hexdigest()
    return ripemd160_hash

ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

class Base58Encoder:
    ENCODE_MAP = {i: ALPHABET[i] for i in range(58)}
    DECODE_MAP = {ALPHABET[i]: i for i in range(58)}

    @staticmethod
    def encode(hex_string):
        # Encodes a hex string to Base58.
        number = int(hex_string, 16)
        
        output = ""
        while True:
            quotient = number // 58
            remainder = number % 58

            if quotient == number:
                break
    
            output = Base58Encoder.ENCODE_MAP[remainder] + output
            number = quotient
        return output

    @staticmethod    
    def decode(base58_string):
        # Decodes a Base58 string to hex.
        size = len(base58_string)
        value = 0
        for i, char in enumerate(base58_string):
            value += Base58Encoder.DECODE_MAP[base58_string[size-i-1]] * (58**i)
        return hex(value)[2:]

def compute_double_sha256(text):
    # Computes SHA256(SHA256(text)).
    first_hash = hashlib.sha256(str.encode(text)).hexdigest()
    second_hash = hashlib.sha256(str.encode(first_hash)).hexdigest()
    return second_hash

def compute_merkle_root(hashes, arity=2):
    # Recursively computes the Merkle Root of a list of hashes.
    if not hashes:
        return None
    if len(hashes) == 1:
        return compute_double_sha256(hashes[0] + hashes[0])
    
    remaining = (len(hashes) % arity)
    for _ in range(remaining):
        hashes.append(hashes[-1])

    new_hashes = []
    for i in range(0, len(hashes), arity):
        combined_hash = "".join(hashes[i:i+arity])
        new_hashes.append(compute_double_sha256(combined_hash))

    return compute_merkle_root(new_hashes, arity)

def generate_pub_key_script(public_key):
    # Creates a P2PKH script public key.
    return compute_hash160(public_key)

def generate_signature_script(keys, serialized_txn):
    # Generates a signature script for a transaction.
    digital_signature = ScriptEngine.create_digital_signature(serialized_txn, keys['private'])
    return digital_signature + keys['public']

if __name__ == '__main__':
    pass