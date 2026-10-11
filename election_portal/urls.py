from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # Root redirects directly to Polling Station Terminal Login
    path('', lambda request: redirect('station_login'), name='root_home'),
    path('voting/', include('voting.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
