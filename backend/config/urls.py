"""Root URL configuration for the restructured Kultiva backend."""
from django.contrib import admin
from django.urls import path

urlpatterns = [path("admin/", admin.site.urls)]
