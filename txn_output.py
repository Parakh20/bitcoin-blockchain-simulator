from helpers import invert_bytes

class TxnOutput:
    # Represents an output in a transaction.
    def __init__(self, amount, locking_script):
        self.amount = amount
        self.locking_script = locking_script

    def serialize(self):
        # Serializes the transaction output data.
        hex_amount = hex(self.amount)[2:]
        hex_amount = (16 - len(hex_amount)) * '0' + hex_amount
        reversed_amount = invert_bytes(hex_amount)
        
        script_size = hex(len(self.locking_script) // 2)[2:]
        
        return reversed_amount + script_size + self.locking_script

    def clone(self):
        # Creates a copy of the output.
        return TxnOutput(self.amount, self.locking_script)

    def display(self, padding=""):
        # Prints the output details.
        print(f"{padding}#####----- Output TXN -----#####")
        print(f"{padding}[@] Amount : {self.amount}")
        print(f"{padding}[@] Script Pub Key : {self.locking_script}")
        print()

if __name__ == "__main__":
    pass