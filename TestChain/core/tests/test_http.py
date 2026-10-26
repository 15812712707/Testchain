import http.cookiejar
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener

from django.contrib.auth import get_user_model
from django.test import LiveServerTestCase

from core.models import Block, ChainState, Execution, Project, Report, TestCase, Version


class HTTPWorkflowTests(LiveServerTestCase):
    def setUp(self):
        ChainState.objects.get_or_create(pk=1)
        get_user_model().objects.create_user("http-user", password="Actual-HTTP-901!")
        self.cookies = http.cookiejar.CookieJar()
        self.browser = build_opener(HTTPCookieProcessor(self.cookies))

    def get(self, path):
        return self.browser.open(self.live_server_url + path, timeout=15)

    def post(self, path, data):
        data["csrfmiddlewaretoken"] = next(cookie.value for cookie in self.cookies if cookie.name == "csrftoken")
        request = Request(self.live_server_url + path, data=urlencode(data).encode(), headers={"Referer": self.live_server_url + path})
        return self.browser.open(request, timeout=30)

    def test_real_http_login_to_download_and_verification(self):
        self.assertEqual(self.get("/login/").status, 200)
        self.assertEqual(self.post("/login/", {"username": "http-user", "password": "Actual-HTTP-901!"}).status, 200)
        self.post("/projects/new/", {"name": "真实 HTTP 项目", "description": "端到端验证"})
        project = Project.objects.get(name="真实 HTTP 项目")
        prefix = f"/projects/{project.pk}"
        self.post(prefix + "/versions/new/", {"name": "v1.0"})
        version = Version.objects.get(project=project)
        self.post(prefix + "/cases/new/", {"title": "登录测试", "steps": "输入账号密码", "expected": "登录成功", "priority": "high"})
        case = TestCase.objects.get(project=project)
        self.post(prefix + f"/cases/{case.pk}/execute/", {"version": version.pk, "status": "passed", "actual": "成功进入主页"})
        self.assertEqual(Execution.objects.get(case=case).status, "passed")
        self.post(prefix + "/reports/generate/", {"title": "验收报告", "version": version.pk})
        report = Report.objects.get(project=project)
        self.post(prefix + f"/reports/{report.pk}/anchor/", {})
        self.assertTrue(Block.objects.filter(report=report).exists())
        data = self.get(prefix + f"/reports/{report.pk}/download/").read()
        self.assertEqual(data, bytes(report.data))
        boundary = "testchain-http-boundary"
        token = next(cookie.value for cookie in self.cookies if cookie.name == "csrftoken")
        body = (
            f'--{boundary}\r\nContent-Disposition: form-data; name="csrfmiddlewaretoken"\r\n\r\n{token}\r\n'
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="report.txt"\r\nContent-Type: text/plain\r\n\r\n'
        ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
        request = Request(self.live_server_url + prefix + f"/reports/{report.pk}/verify/", data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        self.assertIn("文件与链上存证一致", self.browser.open(request, timeout=15).read().decode())
