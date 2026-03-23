from django.urls import path

from .views import (LoginView, ObjetivoActivoView, ObjetivoUsuarioView,
                     PerfilView, RegistroView, SafeTokenRefreshView, SexoListView)

urlpatterns = [
    path('registro/',         RegistroView.as_view(),          name='registro'),
    path('login/',            LoginView.as_view(),              name='login'),
    path('token/refresh/',    SafeTokenRefreshView.as_view(),   name='token_refresh'),
    path('perfil/',           PerfilView.as_view(),             name='perfil'),
    path('objetivo/',         ObjetivoUsuarioView.as_view(),    name='objetivo'),
    path('objetivo/activo/',  ObjetivoActivoView.as_view(),     name='objetivo_activo'),
    path('sexos/',            SexoListView.as_view(),           name='sexos'),
]
