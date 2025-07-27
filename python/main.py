from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException
import os

# Node access params
RPC_URL = "http://alice:password@127.0.0.1:18443"

def main():
    try:
        # General client for non-wallet-specific commands
        client = AuthServiceProxy(RPC_URL)

        # Get blockchain info
        blockchain_info = client.getblockchaininfo()

        print("Blockchain Info:", blockchain_info)

        # Create/Load the wallets, named 'Miner' and 'Trader'. Have logic to optionally create/load them if they do not exist or are not loaded already.
        wallets = ['Miner', 'Trader']
        for wallet in wallets:
            if wallet in client.listwallets():
                client.loadwallet(wallet)
                print(f"Loaded existing wallet: {wallet}")
            else:
                client.createwallet(wallet)
                print(f"Created new wallet: {wallet}")

        # Create wallet-specific RPC connections
        miner_rpc = AuthServiceProxy(f"{RPC_URL}/wallet/Miner")
        trader_rpc = AuthServiceProxy(f"{RPC_URL}/wallet/Trader")

        # Generate mining reward address with label
        mining_reward_address = miner_rpc.getnewaddress("Mining Reward")
        print(f"Mining Reward Address: {mining_reward_address}")

        # Mine blocks to get posi+tive balance
        block_count = 101
        mined_blocks = client.generatetoaddress(block_count, mining_reward_address)
        print(f"Mined {block_count} blocks to address: {mining_reward_address}")


        """
        Why wallet balance behaves this way:
        Bitcoin coinbase transactions (block rewards) require 100 confirmations 
        before they become spendable. By mining 101 blocks:
        - The first block's reward becomes mature (after 100 confirmations)
        - The 101st block provides an immediately spendable balance
        This ensures we have spendable funds in the Miner wallet.
        """

        # Get and print miner balance
        miner_balance = miner_rpc.getbalance()
        print(f"Miner Balance: {miner_balance} BTC")

        # Generate trader receiving address with label
        trader_receive_address = trader_rpc.getnewaddress("Received")
        print(f"Trader Receive Address: {trader_receive_address}")

        # Send 20 BTC from Miner to Trader
        send_amount = 20
        txid = miner_rpc.sendtoaddress(trader_receive_address, send_amount)
        print(f"Sent {send_amount} BTC to Trader. TXID: {txid}")

        # Check the transaction in the mempool
        mempool_entry = client.getmempoolentry(txid)
        print("Mempool Entry:", mempool_entry)

        # Mine 1 block to confirm the transaction.
        confirm_block_hash = client.generatetoaddress(1, mining_reward_address)[0]
        print(f"Transaction confirmed in block: {confirm_block_hash}")

        # Extract all required transaction details.
        raw_tx = client.getrawtransaction(txid)
        decoded_tx = client.decoderawtransaction(raw_tx)

        # Get block info
        block_info = client.getblock(confirm_block_hash)
        block_height = block_info['height']

        # Calculate transaction fee
        fee = calculate_transaction_fee(client, decoded_tx)

        # Extract input details (from Miner)
        input_address, input_amount = extract_input_details(client, decoded_tx)

        # Extract output details (to Trader and change back to Miner)
        change_address, change_amount, trader_amount = extract_output_details(
            decoded_tx, 
            trader_receive_address
        )
        # Write data to output file
        write_output_file(
            txid, 
            input_address, 
            input_amount, 
            trader_receive_address, 
            trader_amount, 
            change_address, 
            change_amount, 
            fee, 
            block_height, 
            confirm_block_hash
        )
        # Write the data to ../out.txt in the specified format given in readme.md.
    except JSONRPCException as e:
        print(f"JSON-RPC Error: {e.error}")
    except Exception as e:
        print(f"Error occurred: {str(e)}")

def calculate_transaction_fee(client, decoded_tx):
    """Calculate transaction fee by comparing inputs and outputs"""
    total_input = 0
    # Sum all inputs
    for vin in decoded_tx['vin']:
        prev_tx = client.getrawtransaction(vin['txid'])
        prev_decoded = client.decoderawtransaction(prev_tx)
        prev_output = prev_decoded['vout'][vin['vout']]
        total_input += prev_output['value']
    
    total_output = sum(vout['value'] for vout in decoded_tx['vout'])
    return total_output - total_input

def extract_input_details(client, decoded_tx):
    """Extract details of the first input (from Miner)"""
    first_vin = decoded_tx['vin'][0]
    prev_tx = client.getrawtransaction(first_vin['txid'])
    prev_decoded = client.decoderawtransaction(prev_tx)
    prev_output = prev_decoded['vout'][first_vin['vout']]
    
    # Get address and amount
    input_address = prev_output['scriptPubKey']['addresses'][0]
    input_amount = prev_output['value']
    return input_address, input_amount

def extract_output_details(decoded_tx, trader_address):
    """Extract output details including trader and change amounts"""
    trader_amount = 0
    change_amount = 0
    change_address = ""
    
    for vout in decoded_tx['vout']:
        script_pubkey = vout['scriptPubKey']
        if 'addresses' in script_pubkey:
            # Identify trader output
            if trader_address in script_pubkey['addresses']:
                trader_amount = vout['value']
            # Identify change output (back to miner)
            else:
                change_address = script_pubkey['addresses'][0]
                change_amount = vout['value']
    
    return change_address, change_amount, trader_amount

def write_output_file(
    txid, 
    input_address, 
    input_amount, 
    trader_address, 
    trader_amount, 
    change_address, 
    change_amount, 
    fee, 
    block_height, 
    block_hash
):
    """Write all required details to output file in specified format"""
    output_dir = os.path.join(os.path.dirname(__file__), '..')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'out.txt')

    with open(output_path, 'w') as f:
        f.write(f"{txid}\n")
        f.write(f"{input_address}\n")
        if input_amount.is_integer():
            f.write(f"{int(input_amount)}\n")
        else:
            f.write(f"{input_amount}\n")
        f.write(f"{trader_address}\n")
        if trader_amount.is_integer():
            f.write(f"{int(trader_amount)}\n")
        else:
            f.write(f"{trader_amount}\n")
        f.write(f"{change_address}\n")
        f.write(f"{change_amount}\n")
        f.write(f"{fee}\n")
        f.write(f"{block_height}\n")
        f.write(f"{block_hash}\n")
    
    print(f"Output written to: {output_path}")

if __name__ == "__main__":
    main()
