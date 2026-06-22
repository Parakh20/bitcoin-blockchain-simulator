from txn_input import TxnInput 
from txn_output import TxnOutput 
from helpers import compute_double_sha256, generate_signature_script, generate_pub_key_script
import settings

class Txn:
    # Represents a transaction in the blockchain.
    def __init__(self, inputs, outputs):
        self.inputs = inputs
        self.outputs = outputs
        self.transaction_id = self.calculate_id()

    def calculate_id(self):
        # Calculates the transaction ID by hashing the serialized data.
        data = self.serialize()
        return compute_double_sha256(data)

    def serialize(self):
        # Serializes the transaction data.
        input_count = hex(len(self.inputs))[2:]
        if len(input_count) == 1:
            input_count = '0' + input_count

        data_parts = [input_count]
        for inp in self.inputs:
            data_parts.append(inp.serialize())

        output_count = hex(len(self.outputs))[2:]
        if len(output_count) == 1:
            output_count = '0' + output_count

        data_parts.append(output_count)
        for out in self.outputs:
            data_parts.append(out.serialize())

        return "".join(data_parts)

    def clone(self):
        # Creates a deep copy of the transaction.
        input_copies = [inp.clone() for inp in self.inputs]
        output_copies = [out.clone() for out in self.outputs]
        return Txn(input_copies, output_copies)

    def display(self, padding=""):
        # Prints the transaction details.
        print(f"{padding}##########---------- TXN ----------##########")
        print(f"{padding}[@] TXNID : {self.transaction_id}")
        for inp in self.inputs:
            inp.display(padding + "    ")
        for out in self.outputs:
            out.display(padding + "    ")
        print()


    @staticmethod
    def create_coinbase_txn(keys):
        # Creates a coinbase transaction (mining reward).
        # Coinbase input has no previous transaction, so we use dummy values
        signature_script = generate_signature_script(keys, "I am inevitable")
        # '0'*64 is the null hash, -1 is the index
        inp = TxnInput('0'*64, -1, signature_script)

        locking_script = generate_pub_key_script(keys['public'])
        out = TxnOutput(settings.MINING_REWARD, locking_script)

        txn = Txn([inp], [out])
        return txn


if __name__ == "__main__":
    pass
