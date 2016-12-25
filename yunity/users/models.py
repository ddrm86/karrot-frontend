from datetime import timedelta

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.core.mail import send_mail

from django.db.models import EmailField, BooleanField, TextField, OneToOneField, CASCADE, CharField, DateTimeField
from django.utils import crypto
from django.utils import timezone
from django_enumfield import enum

from config import settings
from yunity.base.base_models import BaseModel, LocationModel
from yunity.walls.models import Wall

MAX_DISPLAY_NAME_LENGTH = 80


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, display_name=None, **extra_fields):
        """ Creates and saves a User with the given username, email and password.

        """
        email = self._validate_email(email)

        user = self.model(
            email=email,
            is_active=True,
            display_name=display_name,
            **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        user.send_verification_code()
        return user

    def _validate_email(self, email):
        if email is None:
            raise ValueError('The given email must be set')
        return self.normalize_email(email)

    def create_user(self, email=None, password=None, display_name=None,
                    **extra_fields):
        return self._create_user(email, password, display_name, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        return self._create_user(email, password, None, None, None, **extra_fields)


class ProfileVisibility(enum.Enum):
    PRIVATE = 0
    CONNECTED_USERS = 1
    COMMUNITIES = 2
    REGISTERED_USERS = 3
    PUBLIC = 4


class User(AbstractBaseUser, BaseModel, LocationModel):
    email = EmailField(max_length=255, unique=True)
    is_active = BooleanField(default=True)
    is_staff = BooleanField(default=False)
    display_name = CharField(max_length=settings.NAME_MAX_LENGTH)
    first_name = TextField(null=True)
    last_name = TextField(null=True)
    description = TextField(blank=True)

    activation_key = CharField(max_length=40, blank=True)
    key_expires_at = DateTimeField(null=True)
    mail_verified = BooleanField(default=False)

    wall = OneToOneField(Wall, null=True, on_delete=CASCADE)
    profile_visibility = enum.EnumField(ProfileVisibility, default=ProfileVisibility.PRIVATE)

    objects = UserManager()

    USERNAME_FIELD = 'email'

    def get_full_name(self):
        return self.display_name

    def get_short_name(self):
        return self.display_name

    def verify_mail(self):
        self.mail_verified = True
        self.activation_key = ''
        self.key_expires_at = None
        self.save()

    def _unverify_mail(self):
        key = crypto.get_random_string(length=40)
        self.mail_verified = False
        self.activation_key = key
        self.key_expires_at = timezone.now() + timedelta(days=7)
        self.save()

    def send_verification_code(self):
        self._unverify_mail()

        # TODO: set proper frontend url
        url = self.activation_key

        send_mail('Verify your mail address',
                  'Here is your activation key: {}. It will be valid for 7 days.'.format(url),
                  settings.DEFAULT_FROM_EMAIL,
                  [self.email])

    def reset_password(self):
        new_password = User.objects.make_random_password(length=20)
        self.set_password(new_password)
        self.save()

        send_mail("New password",
                  "Here is your new temporary password: {}. ".format(new_password) +
                  "You can use it to login. Please change it soon.",
                  settings.DEFAULT_FROM_EMAIL,
                  [self.email])
