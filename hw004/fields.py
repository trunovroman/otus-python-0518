import re
import datetime

UNKNOWN = 0
MALE = 1
FEMALE = 2
GENDERS = {
    UNKNOWN: "unknown",
    MALE: "male",
    FEMALE: "female",
}


class Field:
    empty_values = ('', [], (), {})

    def __init__(self, required=True, nullable=False):
        self.required, self.nullable = required, nullable

    def validate(self, value):
        if value is None and self.required:
            raise Exception("This field is required.")
        if value in self.empty_values and not self.nullable:
            raise Exception("Empty value is not allowed.")

    def to_python(self, value):
        return value

    def clean(self, value):
        self.validate(value)
        return self.to_python(value)


class CharField(Field):
    def validate(self, value):
        super().validate(value)
        if value is not None and not isinstance(value, str):
            raise Exception("This field must be str.")


class ArgumentsField(Field):
    pass


class EmailField(CharField):
    def validate(self, value):
        super().validate(value)
        if value is not None and "@" not in value:
            raise Exception("Email field must include @.")


class PhoneField(Field):
    regex = re.compile("^7[0-9]{10}$")

    def validate(self, value):
        super().validate(value)
        if value is not None:
            if self.regex.match(str(value)) is None:
                raise Exception("Phone number is invalid: {0}.".format(value))


class DateField(Field):
    def validate(self, value):
        super().validate(value)
        if value is not None:
            try:
                datetime.datetime.strptime(value, "%d.%m.%Y").date()
            except ValueError:
                return "Date must have format: DD.MM.YYYY."

    def to_python(self, value):
        return datetime.datetime.strptime(value, "%d.%m.%Y") if value is not None else None


class BirthDayField(DateField):
    def validate(self, value):
        super().validate(value)
        if value is not None:
            if (datetime.datetime.now() - self.to_python(value)).days / 365 > 70:
                raise Exception("Birthday must be later than 70 years ago.")


class GenderField(Field):
    def validate(self, value):
        super().validate(value)
        if value is not None:
            if not isinstance(value, int):
                raise Exception("Gender must be a digit.")
            if int(value) not in GENDERS:
                raise Exception("Gender must be equal to {0}".format(list(GENDERS.keys())))


class ClientIDsField(Field):
    def validate(self, value):
        super().validate(value)
        if not isinstance(value, list):
            raise Exception('Field must be a list.')
        for item in value:
            if not isinstance(item, int):
                raise Exception('Items must be int.')
