from django.urls import path

from .views import (AdminUsuarioDeleteView, AdminUsuariosView, LoginView,
                    PerfilView, ProcesoDetailView, RecuperarClaveView, RestablecerClaveView, ProcesoEstadoView,
                    ProcesoListCreateView, ProcesoMedicionInicialView, ProcesoQuitarModuloView, ProcesoRenovarView,
                    RegistroView, SafeTokenRefreshView, SexoListView)

urlpatterns = [
    path('registro/',              RegistroView.as_view(),           name='registro'),
    path('recuperar-clave/',       RecuperarClaveView.as_view(),     name='recuperar-clave'),
    path('restablecer-clave/',     RestablecerClaveView.as_view(),   name='restablecer-clave'),
    path('login/',                 LoginView.as_view(),               name='login'),
    path('token/refresh/',         SafeTokenRefreshView.as_view(),    name='token_refresh'),
    path('perfil/',                PerfilView.as_view(),              name='perfil'),
    path('procesos/',              ProcesoListCreateView.as_view(),   name='procesos'),
    path('procesos/estado/',       ProcesoEstadoView.as_view(),       name='procesos-estado'),
    path('procesos/<int:pk>/',     ProcesoDetailView.as_view(),       name='proceso-detail'),
    path('procesos/<int:pk>/medicion-inicial/', ProcesoMedicionInicialView.as_view(), name='proceso-medicion-inicial'),
    path('procesos/<int:pk>/quitar-modulo/', ProcesoQuitarModuloView.as_view(), name='proceso-quitar-modulo'),
    path('procesos/<int:pk>/renovar/', ProcesoRenovarView.as_view(), name='proceso-renovar'),
    path('sexos/',                 SexoListView.as_view(),            name='sexos'),
    path('admin/usuarios/',        AdminUsuariosView.as_view(),       name='admin-usuarios'),
    path('admin/usuarios/<int:pk>/', AdminUsuarioDeleteView.as_view(), name='admin-usuario-delete'),
]
