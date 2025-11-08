from dataclasses import dataclass

from config import Config
from .discussion_service import DiscussionService, build_discussion_service
from .event_service import EventService, build_event_service
from .registration_service import RegistrationService, build_registration_service
from .user_service import UserService, build_user_service


@dataclass(frozen=True)
class ServiceContainer:
    users: UserService
    events: EventService
    registrations: RegistrationService
    discussions: DiscussionService


def build_services(config: Config) -> ServiceContainer:
    users = build_user_service(config.bot.admin_ids)
    events = build_event_service()
    registrations = build_registration_service()
    discussions = build_discussion_service()
    return ServiceContainer(
        users=users,
        events=events,
        registrations=registrations,
        discussions=discussions,
    )

