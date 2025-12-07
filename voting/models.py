from django.db import models

class Vote(models.Model):
    preferences = models.TextField() # Encrypted string
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'vote'
