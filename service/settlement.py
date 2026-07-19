"""Settlement logic for transferring balances and writing the ledger."""

import time
from model.database import get_db
from model.schemas import PaymentInstruction


class InsufficientFundsError(Exception):
    pass


class AccountNotFoundError(Exception):
    pass


class OptimisticLockError(Exception):
    pass


def settle(instruction: PaymentInstruction, packet_hash: str) -> int:
    with get_db() as cur:
        cur.execute(
            "SELECT id, balance, version FROM accounts WHERE id = ?",
            (instruction.sender_id,),
        )
        sender_row = cur.fetchone()
        if sender_row is None:
            raise AccountNotFoundError(f"Sender {instruction.sender_id!r} not found")

        cur.execute(
            "SELECT id, balance, version FROM accounts WHERE id = ?",
            (instruction.receiver_id,),
        )
        receiver_row = cur.fetchone()
        if receiver_row is None:
            raise AccountNotFoundError(f"Receiver {instruction.receiver_id!r} not found")

        sender_balance  = sender_row["balance"]
        sender_version  = sender_row["version"]
        receiver_balance = receiver_row["balance"]
        receiver_version = receiver_row["version"]

        if sender_balance < instruction.amount:
            raise InsufficientFundsError(
                f"{instruction.sender_id} has ₹{sender_balance:.2f}, "
                f"needs ₹{instruction.amount:.2f}"
            )

        rows = cur.execute(
            "UPDATE accounts SET balance = ?, version = ? WHERE id = ? AND version = ?",
            (
                round(sender_balance - instruction.amount, 2),
                sender_version + 1,
                instruction.sender_id,
                sender_version,
            ),
        ).rowcount
        if rows == 0:
            raise OptimisticLockError("Concurrent modification on sender account")

        rows = cur.execute(
            "UPDATE accounts SET balance = ?, version = ? WHERE id = ? AND version = ?",
            (
                round(receiver_balance + instruction.amount, 2),
                receiver_version + 1,
                instruction.receiver_id,
                receiver_version,
            ),
        ).rowcount
        if rows == 0:
            raise OptimisticLockError("Concurrent modification on receiver account")

        cur.execute(
            """
            INSERT INTO transactions
                (packet_hash, sender_id, receiver_id, amount, settled_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                packet_hash,
                instruction.sender_id,
                instruction.receiver_id,
                instruction.amount,
                int(time.time() * 1000),
            ),
        )
        tx_id = cur.lastrowid

    return tx_id
