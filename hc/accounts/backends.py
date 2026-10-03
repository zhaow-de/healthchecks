from __future__ import annotations

from django.contrib.auth.models import User
from django.http import HttpRequest

from hc.accounts.models import Profile


class BasicBackend:
    def get_user(self, user_id: int) -> User | None:
        try:
            q = User.objects.select_related("profile")

            return q.get(pk=user_id)
        except User.DoesNotExist:
            return None


# Authenticate against the token in user's profile.
class ProfileBackend(BasicBackend):
    def authenticate(
        self,
        request: HttpRequest,
        username: str | None = None,
        token: str | None = None,
    ) -> User | None:
        if not token:
            return None

        try:
            profiles = Profile.objects.select_related("user")
            profile = profiles.get(user__username=username)
        except Profile.DoesNotExist:
            return None

        if not profile.check_token(token):
            return None

        return profile.user


class EmailBackend(BasicBackend):
    def authenticate(
        self,
        request: HttpRequest,
        username: str | None = None,
        password: str | None = None,
    ) -> User | None:
        if not password:
            return None

        try:
            user = User.objects.get(email=username)
        except User.DoesNotExist:
            return None

        if not user.check_password(password):
            return None

        return user
