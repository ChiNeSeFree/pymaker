# This file is part of Maker Keeper Framework.
#
# Copyright (C) 2017 reverendus
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json
import time
from functools import total_ordering

import eth_utils
import pkg_resources
from web3.utils.events import get_event_data

from api.numeric import Wad


class Contract:

    def _assert_contract_exists(self, web3, address):
        code = web3.eth.getCode(address.address)
        if (code == "0x") or (code is None):
            raise Exception(f"No contract found at {address}")

    def _wait_for_receipt(self, web3, transaction_hash):
        while True:
            receipt = web3.eth.getTransactionReceipt(transaction_hash)
            if receipt is not None and receipt['blockNumber'] is not None:
                return receipt
            time.sleep(0.25)

    def _prepare_receipt(self, web3, transaction_hash):
        receipt = self._wait_for_receipt(web3, transaction_hash)
        receipt_logs = receipt['logs']
        if (receipt_logs is not None) and (len(receipt_logs) > 0):
            transfers = []
            for receipt_log in receipt_logs:
                if len(receipt_log['topics']) > 0 and receipt_log['topics'][0] == '0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef':
                    from api.token import ERC20Token
                    transfer_abi = [abi for abi in ERC20Token.abi if abi.get('name') == 'Transfer'][0]
                    event_data = get_event_data(transfer_abi, receipt_log)
                    transfers.append(Transfer(token_address=Address(event_data['address']),
                                              from_address=Address(event_data['args']['from']),
                                              to_address=Address(event_data['args']['to']),
                                              value=Wad(event_data['args']['value'])))
            return Receipt(transaction_hash=transaction_hash, transfers=transfers)
        else:
            return False

    @staticmethod
    def _to_bytes32(value):
        return value.to_bytes(32, byteorder='big')

    @staticmethod
    def _load_abi(package, resource):
        return json.loads(pkg_resources.resource_string(package, resource))


@total_ordering
class Address:
    """Represents an Ethereum address.

    Addresses get normalized automatically, so instances of this class can be safely compared to each other.

    Args:
        address: Can be any address representation allowed by web3.py
            or another instance of the Address class.

    Attributes:
        address: Normalized hexadecimal representation of the Ethereum address.
    """
    def __init__(self, address):
        if isinstance(address, Address):
            self.address = address.address
        else:
            self.address = eth_utils.to_normalized_address(address)

    def __str__(self):
        return f"{self.address}"

    def __repr__(self):
        return f"Address('{self.address}')"

    def __hash__(self):
        return self.address.__hash__()

    def __eq__(self, other):
        assert(isinstance(other, Address))
        return self.address == other.address

    def __lt__(self, other):
        assert(isinstance(other, Address))
        return self.address < other.address


class Receipt:
    """Represents a confirmation of a successful Ethereum transaction.

    Attributes:
        transaction_hash: Hash of the Ethereum transaction.
        transfers: A list of ERC20 token transfers resulting from the execution
            of this Ethereum transaction. Each transfer is an instance of the
            `Transfer` class.
    """
    def __init__(self, transaction_hash: str, transfers: list):
        assert(isinstance(transaction_hash, str))
        assert(isinstance(transfers, list))
        self.transaction_hash = transaction_hash
        self.transfers = transfers


class Transfer:
    """Represents an ERC20 token transfer.

    Designed to enable monitoring transfers resulting from smart contract method execution.
    A list of transfers can be found in the `Receipt` class.

    Attributes:
        token_address: Address of the ERC20 token that has been transferred.
        from_address: Source address of the transfer.
        to_address: Destination address of the transfer.
        value: Value transferred.
    """
    def __init__(self, token_address: Address, from_address: Address, to_address: Address, value: Wad):
        assert(isinstance(token_address, Address))
        assert(isinstance(from_address, Address))
        assert(isinstance(to_address, Address))
        assert(isinstance(value, Wad))
        self.token_address = token_address
        self.from_address = from_address
        self.to_address = to_address
        self.value = value

    @staticmethod
    def incoming(our_address: Address):
        return lambda transfer: transfer.to_address == our_address

    @staticmethod
    def outgoing(our_address: Address):
        return lambda transfer: transfer.from_address == our_address