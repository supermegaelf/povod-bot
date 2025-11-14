from dataclasses import dataclass

from config import Config
from .event_service import EventService, build_event_service
from .registration_service import RegistrationService, build_registration_service
from .reminder_service import ReminderService, build_reminder_service
from .user_service import UserService, build_user_service


@dataclass(frozen=True)
class ServiceContainer:
    users: UserService
    events: EventService
    registrations: RegistrationService
    reminders: ReminderService


def build_services(config: Config) -> ServiceContainer:
    users = build_user_service(config.bot.admin_ids)
    events = build_event_service()
    registrations = build_registration_service()
    reminders = build_reminder_service(events, registrations, config.reminders)
    return ServiceContainer(
        users=users,
        events=events,
        registrations=registrations,
        reminders=reminders,
    )

