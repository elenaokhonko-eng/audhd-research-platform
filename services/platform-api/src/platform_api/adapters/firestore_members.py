"""The member store on Firestore: `members/{uid}` and `support_requests/{id}`.

A support request also carries `expires_at`, for Firestore's time-to-live policy; reads
ignore it.
"""

from datetime import timedelta
from typing import Any

from google.cloud import firestore

from platform_api.adapters import in_transaction
from platform_api.identity.models import Member, SupportRequest

SUPPORT_LIFETIME = timedelta(days=365)  # a request's `expires_at` is its `created_at` plus this


class FirestoreMemberStore:
    def __init__(self, client: firestore.Client) -> None:
        self._client = client
        self._members = client.collection("members")
        self._support = client.collection("support_requests")

    def get(self, uid: str) -> Member | None:
        snapshot = self._members.document(uid).get()
        return Member.model_validate(snapshot.to_dict()) if snapshot.exists else None

    def put(self, member: Member) -> None:
        self._members.document(member.uid).set(member.model_dump())

    def create_if_absent(self, member: Member) -> bool:
        ref = self._members.document(member.uid)

        def work(transaction: firestore.Transaction) -> bool:
            if ref.get(transaction=transaction).exists:
                return False
            transaction.set(ref, member.model_dump())
            return True

        return in_transaction(self._client, work)

    def count(self) -> int:
        result: Any = self._members.count().get()  # type: ignore[no-untyped-call]
        return int(result[0][0].value)

    def add_support_request(self, request: SupportRequest) -> None:
        data = {**request.model_dump(), "expires_at": request.created_at + SUPPORT_LIFETIME}
        self._support.document(request.id).set(data)

    def support_requests(self) -> list[SupportRequest]:
        """Oldest first."""
        query = self._support.order_by("created_at")
        return [SupportRequest.model_validate(s.to_dict()) for s in query.stream()]
