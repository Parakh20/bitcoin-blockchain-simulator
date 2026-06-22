import helpers
from ecdsa import SigningKey, SECP256k1, VerifyingKey

class ScriptEngine:
    # Handles script execution and signature verification.
    
    @staticmethod
    def execute_p2pkh(script_signature, public_key_script, message):
        # Verifies a Pay-to-Public-Key-Hash script.
        
        # Bitcoin version:
        #     out: scriptPubKey: OP_DUP OP_HASH160 <pubKeyHash> OP_EQUALVERIFY OP_CHECKSIG
        #     inp: scriptSig: <digital-signature> <pubKey>

        # Extract signature and public key from scriptSig
        # Assuming fixed length for simplicity as per original code, though real Bitcoin uses length prefixes
        signature_hex = script_signature[:128]
        public_key_hex = script_signature[128:]
        
        # Verify public key hash matches the scriptPubKey
        pub_key_hash = helpers.compute_hash160(public_key_hex)
        if not (pub_key_hash.strip() == public_key_script.strip()):
            return False

        # Verify digital signature
        message_bytes = str.encode(message)
        verifying_key = VerifyingKey.from_string(bytearray.fromhex(public_key_hex), curve=SECP256k1)
        
        try:
            return verifying_key.verify(bytearray.fromhex(signature_hex), message_bytes)
        except Exception:
            return False

    @staticmethod
    def create_digital_signature(message, private_key_hex):
        # Signs a message with a private key.
        # message: string
        # private_key_hex: hex string
        signing_key = SigningKey.from_string(bytearray.fromhex(private_key_hex), curve=SECP256k1)
        signature = signing_key.sign(str.encode(message))
        return bytearray(signature).hex()