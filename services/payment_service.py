import asyncio
from datetime import datetime
from typing import Optional
from uuid import uuid4

from yookassa import Configuration, Payment

from config import YooKassaConfig
from database.pool import get_pool
from database.repositories.payments import Payment as PaymentModel, PaymentRepository


class PaymentService:
    def __init__(self, repository: PaymentRepository, config: YooKassaConfig) -> None:
        self._repository = repository
        self._config = config
        Configuration.account_id = config.shop_id
        Configuration.secret_key = config.api_key

    async def create_payment(
        self,
        event_id: int,
        user_id: int,
        amount: float,
        description: str,
        payment_message_id: Optional[int] = None,
    ) -> tuple[str, Optional[str]]:
        loop = asyncio.get_event_loop()
        payment_data = {
            "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
            "confirmation": {
                "type": "redirect",
                "return_url": self._config.webhook_url,
            },
            "capture": True,
            "description": description,
            "metadata": {
                "event_id": str(event_id),
                "user_id": str(user_id),
            },
        }
        payment_idempotency_key = str(uuid4())
        payment = await loop.run_in_executor(
            None,
            lambda: Payment.create(payment_data, payment_idempotency_key),
        )

        payment_id = payment.id
        confirmation_url = payment.confirmation.confirmation_url if payment.confirmation else None

        await self._repository.create(
            payment_id=payment_id,
            event_id=event_id,
            user_id=user_id,
            amount=amount,
            confirmation_url=confirmation_url,
            payment_message_id=payment_message_id,
        )

        return payment_id, confirmation_url

    async def get_payment(self, payment_id: str) -> Optional[PaymentModel]:
        return await self._repository.get_by_payment_id(payment_id)

    async def update_message_id(self, payment_id: str, message_id: int) -> None:
        await self._repository.update_message_id(payment_id, message_id)

    async def handle_webhook(self, payment_id: str) -> Optional[PaymentModel]:
        try:
            loop = asyncio.get_event_loop()
            payment = await loop.run_in_executor(None, Payment.find_one, payment_id)
        except Exception:
            return None

        db_payment = await self._repository.get_by_payment_id(payment_id)
        if db_payment is None:
            return None

        status = payment.status
        paid_at = None
        if status == "succeeded":
            paid_at = datetime.now()

        await self._repository.update_status(payment_id, status, paid_at)
        return await self._repository.get_by_payment_id(payment_id)


def build_payment_service(config: YooKassaConfig) -> PaymentService:
    pool = get_pool()
    repository = PaymentRepository(pool)
    return PaymentService(repository, config)

