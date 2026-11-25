"""Static checks for dev and container choreography proxy ownership."""
import re
import unittest

from tests._support import ROOT


class ChoreographyProxy(unittest.TestCase):
    def test_vite_routes(self):
        config = (ROOT / "web/vite.config.ts").read_text()
        run_pattern = re.search(r'"(\^/choreography/[^\"]+)": \{ target: "http://localhost:7000"', config).group(1)
        for path in ("/choreography/aaaaaaaa/run",):
            self.assertIsNotNone(re.fullmatch(run_pattern, path))
        for path in ("/choreography/list", "/choreography/create", "/choreography/aaaaaaaa"):
            self.assertIsNone(re.fullmatch(run_pattern, path))
        self.assertIn('"/choreography": { target: "http://localhost:7001"', config)
        self.assertIn('"^/run(?:/|$)": { target: "http://localhost:7000"', config)

    def test_nginx_routes(self):
        configs = (
            (ROOT / "web/nginx-conf/default.conf", "translatorapi:7000"),
            (ROOT / "k8s/web/configmap.yaml", "translator:7000"),
        )
        for path, translator_target in configs:
            with self.subTest(path=path):
                config = path.read_text()
                route = re.search(r'location ~ (\^/choreography/[^ {]+) \{\s*proxy_pass http://([^;]+);', config)
                self.assertIsNotNone(route)
                pattern, target = route.groups()
                self.assertEqual(target, translator_target)
                for url in ("/choreography/aaaaaaaa/run",):
                    self.assertIsNotNone(re.fullmatch(pattern, url))
                for url in ("/choreography/list", "/choreography/create", "/choreography/aaaaaaaa"):
                    self.assertIsNone(re.fullmatch(pattern, url))
                self.assertRegex(config, r'location /choreography/ \{\s*proxy_pass http://exercise-config-service:7001/choreography/;')
                self.assertIn(f'location /run/ {{\n', config)
                self.assertIn(f'proxy_pass http://{translator_target}/run/;', config)
