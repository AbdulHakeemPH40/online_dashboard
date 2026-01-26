"""
URL configuration for middleware_dashboard project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.contrib.auth.views import LogoutView
from django.conf import settings
from django.conf.urls.static import static
from integration.views import login_view, dashboard, talabat_dashboard, dashboard_stats_api, system_health_check, quick_stats, change_password

def api_root(request):
    """API root endpoint"""
    return JsonResponse({
        'message': 'Middleware Dashboard API',
        'version': '1.0',
        'endpoints': {
            'admin': '/admin/',
            'api': '/integration/api/',
            'dashboard': '/dashboard/',
        }
    })

urlpatterns = [
    path('admin/', admin.site.urls),
    path('integration/', include('integration.urls', namespace='integration')),
    path('api/', api_root, name='api-root'),
    path('dashboard-stats/', dashboard_stats_api, name='dashboard_stats'),
    path('health/', system_health_check, name='health_check'),
    path('quick-stats/', quick_stats, name='quick_stats'),

    path('dashboard/', dashboard, name='dashboard'),
    path('talabat/', talabat_dashboard, name='talabat_dashboard'),
    path('change-password/', change_password, name='change_password'),
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),
    path('', login_view, name='login'),
]

# Serve media files during development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
