from powermouse.domain.models.profile import Profile


class ProfileManager:
    def create_profile(self, profile: Profile):
        raise NotImplementedError

    def get_profile(self, profile_id: str) -> Profile:
        raise NotImplementedError

    def delete_profile(self, profile_id):
        raise NotImplementedError

    def update_profile(self, profile_id, profile: Profile):
        raise NotImplementedError
