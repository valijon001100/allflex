import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

_LETTER_RE = re.compile(r'[A-Za-zА-Яа-яЁё]')
_DIGIT_RE = re.compile(r'\d')
_SYMBOL_RE = re.compile(r'[^\w\s]', re.UNICODE)


class MixedCharacterPasswordValidator:
    """Parol: kamida 8 belgi, harf + raqam + maxsus belgi aralash."""

    def validate(self, password, user=None):
        if len(password) < 8:
            raise ValidationError(
                _('Parol kamida 8 ta belgidan iborat bo\'lishi kerak.'),
                code='password_too_short',
            )
        if not _LETTER_RE.search(password):
            raise ValidationError(
                _('Parolda kamida bitta harf bo\'lishi kerak.'),
                code='password_no_letter',
            )
        if not _DIGIT_RE.search(password):
            raise ValidationError(
                _('Parolda kamida bitta raqam bo\'lishi kerak.'),
                code='password_no_digit',
            )
        if not _SYMBOL_RE.search(password):
            raise ValidationError(
                _('Parolda kamida bitta maxsus belgi bo\'lishi kerak (!@#$% va h.k.).'),
                code='password_no_symbol',
            )

    def get_help_text(self):
        return _(
            'Parol kamida 8 ta belgidan iborat bo\'lishi va harf, raqam hamda '
            'maxsus belgilar aralash bo\'lishi kerak.'
        )
