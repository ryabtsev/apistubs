from django.db import models


class Mock(models.Model):
    index = models.IntegerField()
    headers = models.JSONField()
    content = models.JSONField()
    status = models.IntegerField()
    method = models.CharField(max_length=6)
    pattern = models.CharField(max_length=1000)
    spec_name = models.CharField(db_index=True, max_length=100)
    env = models.CharField(db_index=True, max_length=100, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    def get_content(self):
        if isinstance(self.content, list):
            return dict(self.content)
        return self.content

    @staticmethod
    def prep_content(content):
        if isinstance(content, dict):
            return [list(i) for i in content.items()]
        return content
