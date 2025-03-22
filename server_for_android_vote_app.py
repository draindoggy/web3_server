from flask import Flask, request, jsonify
from web3 import Web3
import json
import re

app = Flask(__name__)

infura_url = "https://sepolia.infura.io/v3/a2a128abd3f841b88748ebcd27e9fdb3"
web3 = Web3(Web3.HTTPProvider(infura_url))

contract_address = Web3.to_checksum_address("0xe71d49813e746cd7c844c483b6791cd310e68bc2")
with open("newest_poll.abi", "r") as abi_file:
    contract_abi = json.load(abi_file)

contract = web3.eth.contract(address=contract_address, abi=contract_abi)

cache = {
    "polls": None,
    "results": {}
}

@app.route('/create_poll', methods=['POST'])
def create_poll():
    data = request.json
    poll_name = data.get('poll_name')
    options = data.get('options')

    if not poll_name or not options:
        return jsonify({"error": "Название опроса или варианты ответа не могут быть пустыми."}), 400

    account = data.get('account')
    private_key = data.get('private_key')

    if not web3.is_address(account):
        return jsonify({"error": "Некорректный адрес кошелька."}), 400

    if not is_valid_private_key(private_key):
        return jsonify({"error": "Некорректный приватный ключ."}), 400

    nonce = web3.eth.get_transaction_count(account)

    try:
        transaction = contract.functions.createPoll(poll_name, options).build_transaction({
            'chainId': 11155111,
            'gas': 2000000,
            'gasPrice': web3.to_wei('25', 'gwei'),
            'nonce': nonce,
        })

        signed_txn = web3.eth.account.sign_transaction(transaction, private_key=private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)

        tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

        if tx_receipt.status == 1:
            cache["polls"] = None
            cache["results"] = {}
            return jsonify({"success": True, "tx_hash": web3.to_hex(tx_hash)}), 200
        else:
            return jsonify({"error": "Транзакция не была подтверждена."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/show_polls', methods=['GET'])
def show_polls():
    try:
        if cache["polls"] is None:
            cache["polls"] = contract.functions.getAllPolls().call()
        titles, all_options = cache["polls"]
        return jsonify({"titles": titles, "options": all_options}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/show_results', methods=['GET'])
def show_results():
    try:
        if cache["polls"] is None:
            cache["polls"] = contract.functions.getAllPolls().call()
        titles, all_options = cache["polls"]
        results = {}
        for i, title in enumerate(titles):
            if i not in cache["results"]:
                cache["results"][i] = contract.functions.getResults(i).call()
            results[title] = cache["results"][i]
        return jsonify(results), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/cast_vote', methods=['POST'])
def cast_vote():
    data = request.json
    poll_index = data.get('poll_index')
    option_index = data.get('option_index')
    account = data.get('account')
    private_key = data.get('private_key')

    if not web3.is_address(account):
        return jsonify({"error": "Некорректный адрес кошелька."}), 400

    if not is_valid_private_key(private_key):
        return jsonify({"error": "Некорректный приватный ключ."}), 400

    nonce = web3.eth.get_transaction_count(account)

    try:
        transaction = contract.functions.vote(poll_index, option_index).build_transaction({
            'chainId': 11155111,
            'gas': 200000,
            'gasPrice': web3.to_wei('20', 'gwei'),
            'nonce': nonce,
        })

        signed_txn = web3.eth.account.sign_transaction(transaction, private_key=private_key)
        tx_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)

        tx_receipt = web3.eth.wait_for_transaction_receipt(tx_hash)

        if tx_receipt.status == 1:
            if poll_index in cache["results"]:
                del cache["results"][poll_index]
            return jsonify({"success": True, "tx_hash": web3.to_hex(tx_hash)}), 200
        else:
            return jsonify({"error": "Транзакция не была подтверждена."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def is_valid_private_key(private_key):
    private_key = private_key.strip().lower()
    if private_key.startswith('0x'):
        private_key = private_key[2:]

    pattern = re.compile(r'^[0-9a-f]{64}$')
    return bool(pattern.match(private_key))

if __name__ == '__main__':
    app.run(debug=True)