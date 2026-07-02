from django_mongodb_backend.fields import ObjectIdAutoField
from django.db import models

class Vote(models.Model):
    id = ObjectIdAutoField(primary_key=True)
    preferences = models.TextField() # Encrypted string


    class Meta:
        db_table = 'vote'
