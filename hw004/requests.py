import fields


ADMIN_LOGIN = "admin"


class RequestMetaclass(type):
    def __new__(mcs, name, bases, attributes):
        custom_fields = []
        for key, value in list(attributes.items()):
            if isinstance(value, fields.Field):
                custom_fields.append((key, value))
        new_class = type.__new__(mcs, name, bases, attributes)
        new_class.fields = custom_fields
        return new_class


class BaseRequest(metaclass=RequestMetaclass):
    def __init__(self, data=None):
        self.data = {} if data is None else data
        self.cleaned_data = {}
        self.errors = []

    def __getitem__(self, item):
        return self.cleaned_data[item]

    def is_valid(self):
        self.cleaned_data = {}
        self.errors = []
        for name, field in self.fields:
            try:
                value = self.data.get(name, None)
                self.cleaned_data[name] = field.clean(value)
            except Exception as e:
                self.errors.append('Field: {0}. {1}'.format(name, e))
        return True if not len(self.errors) else False


class ClientsInterestsRequest(BaseRequest):
    client_ids = fields.ClientIDsField(required=True)
    date = fields.DateField(required=False, nullable=True)


class OnlineScoreRequest(BaseRequest):
    first_name = fields.CharField(required=False, nullable=True)
    last_name = fields.CharField(required=False, nullable=True)
    email = fields.EmailField(required=False, nullable=True)
    phone = fields.PhoneField(required=False, nullable=True)
    birthday = fields.BirthDayField(required=False, nullable=True)
    gender = fields.GenderField(required=False, nullable=True)
    valid_combinations = [
        ["phone", "email"],
        ["first_name", "last_name"],
        ["gender", "birthday"]
    ]

    def is_valid(self):
        is_valid = super().is_valid()
        if not is_valid:
            return is_valid

        for cmb in self.valid_combinations:
            flag = True
            for field_name in cmb:
                if self.cleaned_data.get(field_name) is None:
                    flag = False
            if flag:
                return True

        self.errors.append("Online score request must include at least one not null combination: {0}"
                           .format(self.valid_combinations))
        return False

    def get_not_null_fields(self):
        return [key for key, value in self.cleaned_data.items() if value is not None]


class MethodRequest(BaseRequest):
    account = fields.CharField(required=False, nullable=True)
    login = fields.CharField(required=True, nullable=True)
    token = fields.CharField(required=True, nullable=True)
    arguments = fields.ArgumentsField(required=True, nullable=True)
    method = fields.CharField(required=True, nullable=False)

    @property
    def is_admin(self):
        return self['login'] == ADMIN_LOGIN
