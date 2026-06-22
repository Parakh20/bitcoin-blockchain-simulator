from helpers import invert_bytes

class TxnInput:
    # Represents an input in a transaction.
    def __init__(self, transaction_id, output_index, unlocking_script):
        self.transaction_id = transaction_id
        self.output_index = output_index
        self.unlocking_script = unlocking_script

    def serialize(self):
        # Serializes the transaction input data.
        reversed_txid = invert_bytes(self.transaction_id)
        
        if self.output_index == -1:
            vout_hex = "f" * 8
        else:
            vout_hex = hex(int(self.output_index))[2:]
            vout_hex = '0' * (8 - len(vout_hex)) + vout_hex
        
        reversed_vout = invert_bytes(vout_hex)
        script_size = hex(len(self.unlocking_script) // 2)[2:]
        
        # Ensure script size is properly formatted if needed (though hex() usually suffices for simple length)
        # Original code didn't pad script_size, but it's safer to ensure it's valid hex if needed.
        # Keeping original logic for now but cleaning up.
        
        return reversed_txid + reversed_vout + script_size + self.unlocking_script + "ffffffff"

    def clone(self):
        # Creates a copy of the input.
        return TxnInput(self.transaction_id, self.output_index, self.unlocking_script)
    
    def display(self, padding=""):
        # Prints the input details.
        print(f"{padding}#####----- Input_txn -----#####")
        print(f"{padding}[@] TXNID : {self.transaction_id}")
        print(f"{padding}[@] Vout : {self.output_index}")
        print(f"{padding}[@] Sig Script : {self.unlocking_script}")
        print()

if __name__ == "__main__":
    pass
