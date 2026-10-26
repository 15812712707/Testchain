from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views


urlpatterns = [
    path("health/", views.health, name="health"),
    path("login/", views.sign_in, name="login"),
    path("register/", views.register, name="register"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("account/password/", views.password_change, name="password_change"),
    path("", views.dashboard, name="dashboard"),
    path("projects/new/", views.project_create, name="project_create"),
    path("projects/<int:project_id>/", views.project_detail, name="project"),
    path("projects/<int:project_id>/edit/", views.project_edit, name="project_edit"),
    path("projects/<int:project_id>/archive/", views.project_archive, name="project_archive"),
    path("projects/<int:project_id>/versions/new/", views.version_create, name="version_create"),
    path("projects/<int:project_id>/cases/", views.case_list, name="cases"),
    path("projects/<int:project_id>/cases/new/", views.case_edit, name="case_create"),
    path("projects/<int:project_id>/cases/<int:case_id>/edit/", views.case_edit, name="case_edit"),
    path("projects/<int:project_id>/cases/<int:case_id>/archive/", views.case_archive, name="case_archive"),
    path("projects/<int:project_id>/cases/<int:case_id>/execute/", views.execute_case, name="execute"),
    path("projects/<int:project_id>/executions/", views.execution_list, name="executions"),
    path("projects/<int:project_id>/defects/", views.defect_list, name="defects"),
    path("projects/<int:project_id>/defects/new/", views.defect_edit, name="defect_create"),
    path("projects/<int:project_id>/defects/<int:defect_id>/edit/", views.defect_edit, name="defect_edit"),
    path("projects/<int:project_id>/members/", views.members, name="members"),
    path("projects/<int:project_id>/members/<int:member_id>/remove/", views.member_remove, name="member_remove"),
    path("projects/<int:project_id>/reports/", views.report_list, name="reports"),
    path("projects/<int:project_id>/reports/upload/", views.report_create, name="report_upload"),
    path("projects/<int:project_id>/reports/generate/", views.report_create, {"generate": True}, name="report_generate"),
    path("projects/<int:project_id>/reports/<int:report_id>/", views.report_detail, name="report"),
    path("projects/<int:project_id>/reports/<int:report_id>/download/", views.report_download, name="report_download"),
    path("projects/<int:project_id>/reports/<int:report_id>/anchor/", views.report_anchor, name="report_anchor"),
    path("projects/<int:project_id>/reports/<int:report_id>/verify/", views.report_verify, name="report_verify"),
    path("projects/<int:project_id>/chain/", views.chain_browser, name="chain"),
    path("projects/<int:project_id>/chain/check/", views.chain_check, name="chain_check"),
    path("projects/<int:project_id>/events/", views.events, name="events"),
    path("projects/<int:project_id>/export/", views.export_csv, name="export_csv"),
    path("api/projects/<int:project_id>/", views.project_api, name="project_api"),
]
