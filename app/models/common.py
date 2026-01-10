from mongoengine import EmbeddedDocument, StringField, BooleanField


class Contact(EmbeddedDocument):
    name = StringField()
    title = StringField()
    email = StringField()
    phone = StringField()
    is_primary = BooleanField(default=False)


class Address(EmbeddedDocument):
    label = StringField()
    line1 = StringField()
    line2 = StringField()
    city = StringField()
    state = StringField()
    postal = StringField()
    country = StringField()
    is_default = BooleanField(default=False)
